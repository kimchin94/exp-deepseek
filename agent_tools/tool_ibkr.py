from fastmcp import FastMCP
import os
from typing import Dict, Any, Optional
from dotenv import load_dotenv
import asyncio

load_dotenv()

# Use ib_insync for a higher-level, reliable IBKR API
try:
    from ib_insync import IB, Stock, MarketOrder, LimitOrder
    # Safe-guard ib_insync Wrapper to avoid 'Error handling fields' when
    # unsolicited completedOrder events arrive while not collecting
    try:
        import ib_insync.wrapper as _ib_wrapper_mod
        _SAFE_WRAPPER_INSTALLED = False

        def _install_safe_completed_order_wrapper():
            global _SAFE_WRAPPER_INSTALLED
            if _SAFE_WRAPPER_INSTALLED:
                return
            _SAFE_WRAPPER_INSTALLED = True
            _orig_completed = _ib_wrapper_mod.Wrapper.completedOrder

            def _safe_completed(self, contract, order, orderState):
                try:
                    res = getattr(self, '_results', None)
                    if not isinstance(res, dict) or 'completedOrders' not in res:
                        # Not collecting completedOrders right now; ignore silently
                        return
                except Exception:
                    return
                try:
                    return _orig_completed(self, contract, order, orderState)
                except Exception:
                    # Swallow handler errors to avoid noisy "Error handling fields" lines
                    return

            _ib_wrapper_mod.Wrapper.completedOrder = _safe_completed

        _install_safe_completed_order_wrapper()
        # Install decoder guard to ignore unknown message ids (e.g., 176 currentTime string)
        try:
            import ib_insync.decoder as _ib_decoder_mod
            if not getattr(_ib_decoder_mod.Decoder, "_safe_interpret_installed", False):
                _orig_interpret = _ib_decoder_mod.Decoder.interpret
                def _safe_interpret(self, fields):
                    try:
                        return _orig_interpret(self, fields)
                    except KeyError:
                        # Unknown/unsupported message id; ignore to keep session healthy
                        return
                _ib_decoder_mod.Decoder.interpret = _safe_interpret
                _ib_decoder_mod.Decoder._safe_interpret_installed = True
        except Exception:
            pass
    except Exception:
        # If wrapper monkey patch cannot be installed, continue without it
        pass
except Exception as e:
    IB = None  # Defer import errors until tool is invoked

mcp = FastMCP("IBKR")

# Global IB instance (created lazily, reused across all tool calls)
_ib_instance: Optional["IB"] = None


async def get_ib() -> "IB":
    """Get or create the global IB instance with async connection"""
    global _ib_instance
    
    if IB is None:
        raise RuntimeError("ib_insync is not installed. Install with: pip install ib-insync")
    
    if _ib_instance is None:
        _ib_instance = IB()
    
    if not _ib_instance.isConnected():
        host = os.getenv("IB_HOST", "127.0.0.1")
        port = int(os.getenv("IB_PORT", "7497"))  # 7497 = paper, 7496 = live
        # Use separate client ID for MCP service to avoid conflicts with agent
        client_id = int(os.getenv("IBKR_SERVICE_CLIENT_ID", os.getenv("IB_CLIENT_ID", "3")))
        print(f"MCP IBKR Service connecting: {host}:{port} with clientId={client_id}")

        try:
            strict = os.getenv("IBKR_STRICT_IDS", "false").lower() in ("1","true","yes","on")
            if strict:
                # Fail fast with the exact clientId
                await _ib_instance.connectAsync(host, port, clientId=client_id, timeout=10)
                print(f"Connected to IBKR with clientId={client_id}")
            else:
                # Compatibility mode: try bumping to next free id (default)
                last_exc: Optional[Exception] = None
                connected = False
                for bump in range(0, 16):
                    try:
                        adjusted_id = client_id + bump
                        await _ib_instance.connectAsync(host, port, clientId=adjusted_id, timeout=10)
                        if bump > 0:
                            print(f"IBKR clientId {client_id} in use; connected with clientId={adjusted_id}")
                        else:
                            print(f"Connected to IBKR with clientId={adjusted_id}")
                        connected = True
                        break
                    except Exception as e2:
                        last_exc = e2
                        if "client id" in str(e2).lower() or "already in use" in str(e2).lower():
                            await asyncio.sleep(0.3)
                            continue
                        raise
                if not connected:
                    raise last_exc or RuntimeError("Unable to obtain a unique IBKR client id")
            # Request delayed market data (free for paper accounts)
            try:
                _ib_instance.reqMarketDataType(3)
                await _ib_instance.sleep(0.3)
                print("Using delayed market data (paper)")
            except Exception:
                pass
            # Install a no-op handler for unknown/optional message ids (e.g., 176 currentTime string)
            try:
                dec = getattr(_ib_instance.client, 'decoder', None)
                if dec and hasattr(dec, 'handlers') and isinstance(dec.handlers, dict):
                    dec.handlers.setdefault(176, lambda fields: None)
            except Exception:
                pass
        except Exception as e:
            # If connection fails, reset instance so next call can retry
            _ib_instance = None
            raise RuntimeError(f"Failed to connect to IBKR: {e}")
    
    return _ib_instance


def is_nan(value) -> bool:
    """Check if a value is NaN"""
    return value is None or (isinstance(value, float) and value != value)


@mcp.tool()
async def get_realtime_price(symbol: str, exchange: str = "SMART", currency: str = "USD") -> Dict[str, Any]:
    """
    Fetch a realtime quote snapshot (last/bid/ask/mid) for a symbol from IBKR.
    Returns a dict with price fields and contract identifiers.
    Uses async API to avoid event loop conflicts.
    """
    ib = await get_ib()
    
    try:
        contract = Stock(symbol, exchange, currency)
        await ib.qualifyContractsAsync(contract)
        ticker = ib.reqMktData(contract, '', False, False)
    except Exception as e:
        return {"error": f"contract/marketdata request failed: {e}", "symbol": symbol}
    
    # Give IB time to populate values
    await ib.sleep(1.0)
    
    # NaN-safe extraction with fallback chain
    last = None if is_nan(ticker.last) else float(ticker.last)
    bid = None if is_nan(ticker.bid) else float(ticker.bid)
    ask = None if is_nan(ticker.ask) else float(ticker.ask)
    close = None if is_nan(ticker.close) else float(ticker.close)
    
    # Calculate mid and select best price
    mid = None
    if bid is not None and ask is not None:
        mid = round((bid + ask) / 2, 4)
    
    # Best price: last > mid > close
    price = last if last is not None else (mid if mid is not None else close)
    
    try:
        ib.cancelMktData(contract)
    except Exception:
        pass
    
    return {
        "symbol": symbol,
        "price": price,
        "last": last,
        "bid": bid,
        "ask": ask,
        "mid": mid,
        "close": close,
        "conId": getattr(contract, 'conId', None),
        "exchange": exchange,
        "currency": currency,
    }


@mcp.tool()
async def place_order(action: str, symbol: str, quantity: int, order_type: str = "MKT", limit_price: Optional[float] = None,
                      exchange: str = "SMART", currency: str = "USD", tif: str = "DAY", outside_rth: bool = False) -> Dict[str, Any]:
    """
    Place a simple market/limit order via IBKR (paper or live depending on gateway).
    Returns order status metadata (orderId, status) immediately without waiting for full fill.
    action: "BUY" or "SELL"
    order_type: "MKT" or "LMT"
    Uses async API to avoid event loop conflicts.
    """
    action = action.upper()
    if action not in ("BUY", "SELL"):
        return {"error": f"Invalid action '{action}'. Use BUY or SELL."}
    if quantity <= 0:
        return {"error": "quantity must be > 0"}

    ib = await get_ib()
    
    contract = Stock(symbol, exchange, currency)
    await ib.qualifyContractsAsync(contract)

    if order_type.upper() == "LMT":
        if limit_price is None:
            return {"error": "limit_price is required for LMT orders"}
        order = LimitOrder(action, int(quantity), float(limit_price), tif=tif, outsideRth=outside_rth)
    else:
        order = MarketOrder(action, int(quantity), tif=tif, outsideRth=outside_rth)

    trade = ib.placeOrder(contract, order)
    # Allow IB time to assign orderId/status
    await ib.sleep(0.5)
    
    status = trade.orderStatus.status if trade.orderStatus else None
    order_id = trade.order.orderId if trade.order else None
    
    return {
        "symbol": symbol,
        "action": action,
        "quantity": quantity,
        "orderType": order.orderType,
        "limitPrice": getattr(order, 'lmtPrice', None),
        "orderId": order_id,
        "status": status,
    }


@mcp.tool()
async def get_positions() -> Dict[str, Any]:
    """
    Return current IBKR positions (paper/live depending on gateway).
    Uses sync method which is more reliable than async for positions.
    """
    ib = await get_ib()
    
    try:
        # Use sync method - more reliable for positions
        positions = ib.positions()
        
        result = []
        for p in positions:
            try:
                result.append({
                    "account": p.account,
                    "symbol": getattr(p.contract, 'symbol', None),
                    "conId": getattr(p.contract, 'conId', None),
                    "exchange": getattr(p.contract, 'exchange', None),
                    "currency": getattr(p.contract, 'currency', None),
                    "position": float(p.position),
                    "avgCost": float(p.avgCost),
                })
            except Exception:
                continue
        return {"positions": result}
    except Exception as e:
        return {"positions": [], "error": f"positions request failed: {e}"}


@mcp.tool()
async def get_account_summary() -> Dict[str, Any]:
    """
    Return IBKR account summary values like NetLiquidation and AvailableFunds.
    Uses sync method which is more reliable than async for account data.
    """
    ib = await get_ib()
    
    tags = 'NetLiquidation,TotalCashValue,AvailableFunds,BuyingPower,EquityWithLoanValue,UnrealizedPnL,RealizedPnL'
    
    try:
        # Use sync method - more reliable for account summary
        summary = ib.accountSummary()
        
        data: Dict[str, Any] = {}
        for tag in summary:
            try:
                if tag.tag in tags:
                    data[tag.tag] = float(tag.value)
            except Exception:
                data[tag.tag] = tag.value
        return data
    except Exception as e:
        return {"error": f"account summary request failed: {e}"}


if __name__ == "__main__":
    port = int(os.getenv("IBKR_HTTP_PORT", "8005"))
    mcp.run(transport="streamable-http", port=port)


