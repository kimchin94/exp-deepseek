"""Focused test for AAPL and key stocks with longer wait times"""
import sys
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass

from ib_insync import IB, Stock
import time

# Focus on the stocks user asked for
symbols = ['AAPL', 'MSFT', 'NVDA', 'AMD', 'TSM', 'GOOGL']

ib = IB()
print("🔌 Connecting to IB Gateway...")
ib.connect('127.0.0.1', 7497, clientId=101, timeout=5)
ib.sleep(0.5)

print(f"✅ Connected! Server time: {ib.reqCurrentTime()}")

# Use delayed data (free for paper accounts)
ib.reqMarketDataType(3)
print("📡 Using DELAYED market data (15-min delay, free)\n")
ib.sleep(0.5)

print("=" * 70)
print("  📈 FETCHING STOCK PRICES FROM IBKR")
print("=" * 70)
print("⏳ Requesting data for all symbols first...\n")

# Request all data first
tickers = []
for sym in symbols:
    try:
        contract = Stock(sym, 'SMART', 'USD')
        ib.qualifyContracts(contract)
        ticker = ib.reqMktData(contract, '', False, False)
        tickers.append((sym, ticker, contract))
        print(f"   ✓ Requested: {sym}")
    except Exception as e:
        print(f"   ✗ Failed to request {sym}: {e}")
        tickers.append((sym, None, None))

# Wait for data to arrive
print(f"\n⏳ Waiting 3 seconds for data to populate...")
ib.sleep(3.0)

# Now check results
print("\n" + "=" * 70)
print("  📊 RESULTS")
print("=" * 70 + "\n")

for sym, ticker, contract in tickers:
    if ticker is None:
        print(f"❌ {sym:6s}: FAILED TO REQUEST")
        continue
    
    # Check what data we have
    has_last = ticker.last and not (isinstance(ticker.last, float) and ticker.last != ticker.last)
    has_bid = ticker.bid and not (isinstance(ticker.bid, float) and ticker.bid != ticker.bid)
    has_ask = ticker.ask and not (isinstance(ticker.ask, float) and ticker.ask != ticker.ask)
    has_close = ticker.close and not (isinstance(ticker.close, float) and ticker.close != ticker.close)
    
    # Determine best price
    if has_last:
        price = ticker.last
        source = "Last"
    elif has_bid and has_ask:
        price = (ticker.bid + ticker.ask) / 2
        source = "Bid/Ask Mid"
    elif has_close:
        price = ticker.close
        source = "Prev Close"
    else:
        price = None
        source = "NO DATA"
    
    if price:
        print(f"✅ {sym:6s}: ${price:>8.2f}  [{source}]")
        last_str = f"${ticker.last:.2f}" if has_last else "N/A"
        bid_str = f"${ticker.bid:.2f}" if has_bid else "N/A"
        ask_str = f"${ticker.ask:.2f}" if has_ask else "N/A"
        close_str = f"${ticker.close:.2f}" if has_close else "N/A"
        print(f"            Last={last_str:>10s}  Bid={bid_str:>10s}  Ask={ask_str:>10s}  Close={close_str:>10s}")
    else:
        print(f"❌ {sym:6s}: NO DATA YET")
        print(f"            Last={ticker.last}  Bid={ticker.bid}  Ask={ticker.ask}  Close={ticker.close}")
    
    print()
    
    # Cancel subscription
    if contract:
        ib.cancelMktData(contract)

ib.disconnect()
print("=" * 70)
print("✅ Test complete!")
print("=" * 70)

