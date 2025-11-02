"""
Test IBKR paper trading - place a buy order
"""
import sys
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass

from ib_insync import IB, Stock, MarketOrder, LimitOrder
import time

def test_paper_trading():
    print("=" * 60)
    print("  IBKR PAPER TRADING TEST")
    print("=" * 60)
    
    ib = IB()
    
    # Connect to paper trading
    host = '127.0.0.1'
    port = 7497  # Paper trading port
    client_id = 50
    
    print(f"\n1. Connecting to IB Gateway (Paper)...")
    print(f"   Host: {host}, Port: {port}, ClientID: {client_id}")
    
    try:
        ib.connect(host, port, clientId=client_id, timeout=10)
        print(f"   ✅ Connected!")
        
        # Get account info
        account = ib.managedAccounts()[0]
        print(f"\n2. Account: {account}")
        
        # Get account values
        for av in ib.accountValues():
            if av.tag in ['NetLiquidation', 'TotalCashValue', 'BuyingPower']:
                print(f"   {av.tag}: ${av.value} {av.currency}")
        
        # Create contract
        print(f"\n3. Creating contract for AAPL...")
        stock = Stock('AAPL', 'SMART', 'USD')
        ib.qualifyContracts(stock)
        print(f"   ✅ Contract: {stock.symbol} on {stock.primaryExchange}")
        
        # Get current price
        print(f"\n4. Getting current price...")
        ib.reqMarketDataType(3)  # Delayed data
        ticker = ib.reqMktData(stock, '', False, False)
        ib.sleep(1.5)
        
        print(f"   Last: ${ticker.last}")
        print(f"   Close: ${ticker.close}")
        
        # Place a small market order
        print(f"\n5. Placing PAPER MARKET ORDER...")
        print(f"   Action: BUY 1 share of AAPL")
        
        order = MarketOrder('BUY', 1)
        trade = ib.placeOrder(stock, order)
        
        print(f"   Order ID: {trade.order.orderId}")
        print(f"   Initial Status: {trade.orderStatus.status}")
        
        # Wait for order to fill
        print(f"\n6. Waiting for order execution...")
        for i in range(10):
            ib.sleep(0.5)
            print(f"   Status: {trade.orderStatus.status}")
            if trade.orderStatus.status in ['Filled', 'Cancelled']:
                break
        
        # Final status
        print(f"\n7. Final Order Status:")
        print(f"   Status: {trade.orderStatus.status}")
        print(f"   Filled: {trade.orderStatus.filled}")
        print(f"   Remaining: {trade.orderStatus.remaining}")
        if trade.orderStatus.avgFillPrice:
            print(f"   Avg Fill Price: ${trade.orderStatus.avgFillPrice}")
        
        # Check positions
        print(f"\n8. Current Positions:")
        positions = ib.positions()
        if positions:
            for pos in positions:
                if pos.contract.symbol == 'AAPL':
                    print(f"   ✅ {pos.contract.symbol}: {pos.position} shares @ ${pos.avgCost:.2f}")
        else:
            print(f"   No positions found")
        
        ib.disconnect()
        print(f"\n✅ Test Complete!")
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        try:
            ib.disconnect()
        except:
            pass
        return False

if __name__ == "__main__":
    success = test_paper_trading()
    sys.exit(0 if success else 1)

