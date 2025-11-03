"""Test placing a single small order on IBKR paper account"""
import sys
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass

from ib_insync import IB, Stock, MarketOrder, LimitOrder
import time

ib = IB()
print("🔌 Connecting to IB Gateway...")
ib.connect('127.0.0.1', 7497, clientId=102, timeout=5)
ib.sleep(0.5)

print(f"✅ Connected! Server time: {ib.reqCurrentTime()}")

# Use delayed market data
ib.reqMarketDataType(3)
ib.sleep(0.3)

print("\n" + "=" * 70)
print("  🧪 TEST: PLACE 1 SMALL ORDER")
print("=" * 70)

# Test with 1 share of AAPL (small, liquid, safe for testing)
symbol = 'AAPL'
quantity = 1
action = 'BUY'

print(f"\n📋 Order Details:")
print(f"   Symbol:   {symbol}")
print(f"   Action:   {action}")
print(f"   Quantity: {quantity} share")
print(f"   Type:     MARKET ORDER")

# Create contract
contract = Stock(symbol, 'SMART', 'USD')
ib.qualifyContracts(contract)
print(f"\n✅ Contract qualified: {contract.symbol} on {contract.primaryExchange}")

# Get current price for reference
ticker = ib.reqMktData(contract, '', False, False)
ib.sleep(1.5)
current_price = ticker.last or ticker.close or (ticker.bid + ticker.ask) / 2 if ticker.bid and ticker.ask else None
if current_price:
    print(f"💰 Current Price: ${current_price:.2f}")
    print(f"💵 Estimated Cost: ${current_price * quantity:.2f}")
ib.cancelMktData(contract)

# Confirm before placing
print(f"\n⚠️  READY TO PLACE ORDER!")
print(f"   This will place a REAL order in your IB PAPER account.")
print(f"\n⏳ Placing order in 2 seconds... (Ctrl+C to cancel)")

try:
    time.sleep(2)
except KeyboardInterrupt:
    print("\n❌ Order cancelled by user")
    ib.disconnect()
    sys.exit(0)

# Create and place order
order = MarketOrder(action, quantity)
print(f"\n📤 Placing order...")

trade = ib.placeOrder(contract, order)
ib.sleep(1.0)

print(f"\n📊 Order Status:")
print(f"   Order ID:     {trade.order.orderId}")
print(f"   Status:       {trade.orderStatus.status}")
print(f"   Filled:       {trade.orderStatus.filled}")
print(f"   Remaining:    {trade.orderStatus.remaining}")

# Wait a bit for order to fill
print(f"\n⏳ Waiting for order to fill (up to 5 seconds)...")
for i in range(5):
    ib.sleep(1.0)
    status = trade.orderStatus.status
    filled = trade.orderStatus.filled
    print(f"   [{i+1}s] Status: {status}, Filled: {filled}/{quantity}")
    
    if status in ['Filled', 'Cancelled']:
        break

# Final status
print(f"\n" + "=" * 70)
print(f"  📈 FINAL RESULT")
print(f"=" * 70)
print(f"Order ID:        {trade.order.orderId}")
print(f"Status:          {trade.orderStatus.status}")
print(f"Filled Quantity: {trade.orderStatus.filled}")
if trade.orderStatus.avgFillPrice and trade.orderStatus.avgFillPrice > 0:
    print(f"Avg Fill Price:  ${trade.orderStatus.avgFillPrice:.2f}")
else:
    print(f"Avg Fill Price:  N/A")

# Commission info from fills
total_commission = 0
if hasattr(trade, 'fills') and trade.fills:
    for fill in trade.fills:
        if hasattr(fill.commissionReport, 'commission'):
            total_commission += abs(fill.commissionReport.commission)
if total_commission > 0:
    print(f"Commission:      ${total_commission:.2f}")
else:
    print(f"Commission:      $0.00 (paper account)")

if trade.orderStatus.status == 'Filled':
    print(f"\n✅ SUCCESS! Order filled successfully!")
    total_cost = trade.orderStatus.avgFillPrice * trade.orderStatus.filled
    print(f"💰 Total Cost: ${total_cost:.2f}")
elif trade.orderStatus.status == 'Submitted':
    print(f"\n⏳ Order is still pending (market might be slow)")
else:
    print(f"\n⚠️  Order status: {trade.orderStatus.status}")

# Check current positions
print(f"\n" + "=" * 70)
print(f"  📊 CURRENT POSITIONS")
print(f"=" * 70)

positions = ib.positions()
if positions:
    for pos in positions:
        print(f"   {pos.contract.symbol:6s}: {pos.position:>6.0f} shares @ ${pos.avgCost:.2f} avg cost")
else:
    print("   No positions (order might still be processing)")

# Check account summary
print(f"\n" + "=" * 70)
print(f"  💰 ACCOUNT SUMMARY")
print(f"=" * 70)

for av in ib.accountValues():
    if av.tag in ['NetLiquidation', 'TotalCashValue', 'BuyingPower']:
        print(f"   {av.tag:25s}: ${float(av.value):,.2f}")

ib.disconnect()
print(f"\n" + "=" * 70)
print(f"✅ Test complete! Disconnected from IB.")
print(f"=" * 70)

