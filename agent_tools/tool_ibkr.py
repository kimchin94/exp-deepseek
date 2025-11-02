from fastmcp import FastMCP
import os
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

# Use ib_insync for a higher-level, reliable IBKR API
try:
    from ib_insync import IB, Stock, MarketOrder, LimitOrder, util
except Exception as e:
    IB = None  # Defer import errors until tool is invoked

mcp = FastMCP("IBKR")


def _get_ib_connection() -> "IB":
    if IB is None:
        raise RuntimeError("ib_insync is not installed. Install with: pip install ib-insync")

    host = os.getenv("IB_HOST", "127.0.0.1")
    port = int(os.getenv("IB_PORT", "7497"))  # 7497 = paper, 7496 = live
    client_id = int(os.getenv("IB_CLIENT_ID", "123"))

    ib = IB()
    if not ib.isConnected():
        ib.connect(host, port, clientId=client_id, readonly=False, timeout=5)
    return ib


@mcp.tool()
def get_realtime_price(symbol: str, exchange: str = "SMART", currency: str = "USD") -> Dict[str, Any]:
    """
    Fetch a realtime quote snapshot (last/bid/ask/mid) for a symbol from IBKR.
    Returns a dict with price fields and contract identifiers.
    """
    ib = _get_ib_connection()
    contract = Stock(symbol, exchange, currency)
    ib.qualifyContracts(contract)
    ticker = ib.reqMktData(contract, '', False, False)
    # Give IB a brief moment to populate values
    ib.sleep(0.3)
    last = float(ticker.last) if ticker.last is not None else None
    bid = float(ticker.bid) if ticker.bid is not None else None
    ask = float(ticker.ask) if ticker.ask is not None else None
    mid = None
    if bid is not None and ask is not None:
        mid = round((bid + ask) / 2, 4)
    return {
        "symbol": symbol,
        "last": last,
        "bid": bid,
        "ask": ask,
        "mid": mid,
        "conId": getattr(contract, 'conId', None),
        "exchange": exchange,
        "currency": currency,
    }


@mcp.tool()
def place_order(action: str, symbol: str, quantity: int, order_type: str = "MKT", limit_price: Optional[float] = None,
                exchange: str = "SMART", currency: str = "USD", tif: str = "DAY", outside_rth: bool = False) -> Dict[str, Any]:
    """
    Place a simple market/limit order via IBKR (paper or live depending on gateway).
    Returns order status metadata (orderId, status) immediately without waiting for full fill.
    action: "BUY" or "SELL"
    order_type: "MKT" or "LMT"
    """
    action = action.upper()
    if action not in ("BUY", "SELL"):
        return {"error": f"Invalid action '{action}'. Use BUY or SELL."}
    if quantity <= 0:
        return {"error": "quantity must be > 0"}

    ib = _get_ib_connection()
    contract = Stock(symbol, exchange, currency)
    ib.qualifyContracts(contract)

    if order_type.upper() == "LMT":
        if limit_price is None:
            return {"error": "limit_price is required for LMT orders"}
        order = LimitOrder(action, int(quantity), float(limit_price), tif=tif, outsideRth=outside_rth)
    else:
        order = MarketOrder(action, int(quantity), tif=tif, outsideRth=outside_rth)

    trade = ib.placeOrder(contract, order)
    # Allow IB a brief cycle to assign orderId/status
    ib.sleep(0.3)
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
def get_positions() -> Dict[str, Any]:
    """
    Return current IBKR positions (paper/live depending on gateway).
    """
    ib = _get_ib_connection()
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


@mcp.tool()
def get_account_summary() -> Dict[str, Any]:
    """
    Return IBKR account summary values like NetLiquidation and AvailableFunds.
    """
    ib = _get_ib_connection()
    tags = 'NetLiquidation,TotalCashValue,AvailableFunds,BuyingPower,EquityWithLoanValue,UnrealizedPnL,RealizedPnL'
    summary = ib.accountSummary()
    data: Dict[str, Any] = {}
    for tag in summary:
        try:
            if tag.tag in tags:
                data[tag.tag] = float(tag.value)
        except Exception:
            data[tag.tag] = tag.value
    return data


if __name__ == "__main__":
    port = int(os.getenv("IBKR_HTTP_PORT", "8005"))
    mcp.run(transport="streamable-http", port=port)


