"""Test fetching live market data from IBKR during market hours"""
import sys
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass

from ib_insync import IB, Stock
import time

symbols = ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'TSLA', 'META', 'AMZN']

ib = IB()
print("🔌 Connecting to IB Gateway...")
ib.connect('127.0.0.1', 7497, clientId=100, timeout=5)
ib.sleep(0.3)

print(f"✅ Connected! Server time: {ib.reqCurrentTime()}")
print("\n" + "=" * 70)
print("  📈 LIVE MARKET DATA FROM IBKR")
print("=" * 70)

# Use delayed market data (free for paper accounts, 15-min delay)
ib.reqMarketDataType(3)  # 1=live, 3=delayed, 4=delayed-frozen
print("📡 Market Data Type: DELAYED (15-min delay, free for paper accounts)\n")
ib.sleep(0.5)  # Give it time to switch

results = []
for sym in symbols:
    try:
        contract = Stock(sym, 'SMART', 'USD')
        ib.qualifyContracts(contract)
        
        ticker = ib.reqMktData(contract, '', False, False)
        ib.sleep(1.2)  # Wait for data to arrive
        
        # Get the best available price
        price = None
        source = ""
        
        # Check last trade
        if ticker.last and not (isinstance(ticker.last, float) and ticker.last != ticker.last):
            price = ticker.last
            source = "Last Trade"
        # Check bid/ask midpoint
        elif (ticker.bid and ticker.ask and 
              not (isinstance(ticker.bid, float) and ticker.bid != ticker.bid) and
              not (isinstance(ticker.ask, float) and ticker.ask != ticker.ask)):
            price = (ticker.bid + ticker.ask) / 2
            source = f"Bid/Ask ({ticker.bid:.2f}/{ticker.ask:.2f})"
        # Check close
        elif ticker.close and not (isinstance(ticker.close, float) and ticker.close != ticker.close):
            price = ticker.close
            source = "Previous Close"
        
        results.append({
            'symbol': sym,
            'price': price,
            'source': source,
            'bid': ticker.bid,
            'ask': ticker.ask,
            'last': ticker.last,
            'volume': ticker.volume
        })
        
        if price:
            print(f"✅ {sym:6s}: ${price:>8.2f}  ({source})")
        else:
            print(f"❌ {sym:6s}: NO DATA")
        
        ib.cancelMktData(contract)
        
    except Exception as e:
        print(f"❌ {sym:6s}: ERROR - {e}")
        results.append({'symbol': sym, 'price': None, 'source': str(e)})

print("\n" + "=" * 70)
print("  📊 DETAILED TICKER DATA")
print("=" * 70)

for r in results:
    if r.get('price'):
        print(f"\n{r['symbol']:6s}:")
        print(f"  Last:   ${r.get('last', 'N/A')}")
        print(f"  Bid:    ${r.get('bid', 'N/A')}")
        print(f"  Ask:    ${r.get('ask', 'N/A')}")
        print(f"  Volume: {r.get('volume', 'N/A'):,}" if isinstance(r.get('volume'), (int, float)) else f"  Volume: {r.get('volume', 'N/A')}")

ib.disconnect()
print("\n" + "=" * 70)
print("✅ Test complete! Disconnected from IB.")
print("=" * 70)

