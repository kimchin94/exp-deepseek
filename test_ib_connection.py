"""
Test Interactive Brokers (IB) Gateway/TWS Connection
Tests basic connectivity and market data retrieval
"""
import sys
from datetime import datetime

# Fix Windows console encoding
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass

try:
    from ib_insync import IB, Stock
except ImportError:
    print("ERROR: ib-insync not installed!")
    print("Install with: pip install ib-insync")
    sys.exit(1)


def print_section(title):
    """Print a section header"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def test_connection():
    """Test IB connection"""
    print_section("IB GATEWAY CONNECTION TEST")
    
    # Connection parameters
    host = '127.0.0.1'
    port = 7497  # Paper trading port (live = 7496)
    client_id = 11
    
    print(f"Host:      {host}")
    print(f"Port:      {port}")
    print(f"Client ID: {client_id}")
    print("\nAttempting to connect...")
    
    ib = IB()
    
    try:
        # Try to connect
        ib.connect(host, port, clientId=client_id, timeout=10)
        
        if ib.isConnected():
            print("SUCCESS: Connected to IB Gateway!")
            
            # Get server time
            server_time = ib.reqCurrentTime()
            print(f"Server time: {server_time}")
            
            return ib
        else:
            print("FAILED: Could not connect")
            return None
            
    except Exception as e:
        print(f"ERROR: Connection failed - {e}")
        print("\nTroubleshooting:")
        print("1. Is IB Gateway/TWS running?")
        print("2. Is the port correct? (Paper=7497, Live=7496)")
        print("3. Is 'Enable ActiveX and Socket Clients' checked in Gateway?")
        print("4. Try a different clientId if another connection is active")
        return None


def test_market_data(ib):
    """Test market data retrieval"""
    print_section("MARKET DATA TEST")
    
    try:
        # Request delayed market data (doesn't require live subscription)
        print("Setting market data type to DELAYED (type 3)...")
        ib.reqMarketDataType(3)  # 1=live, 2=frozen, 3=delayed, 4=delayed-frozen
        print("SUCCESS: Delayed market data mode enabled")
        
        # Test stocks
        test_symbols = ['AAPL', 'NVDA', 'MSFT']
        
        for symbol in test_symbols:
            print(f"\n--- Testing {symbol} ---")
            
            try:
                # Create stock contract
                stock = Stock(symbol, 'SMART', 'USD')
                ib.qualifyContracts(stock)
                print(f"Contract qualified: {stock.symbol} ({stock.primaryExchange})")
                
                # Request real-time quote
                ticker = ib.reqMktData(stock, '', False, False)
                ib.sleep(1.5)  # Wait for data
                
                print(f"Bid:    ${ticker.bid}")
                print(f"Ask:    ${ticker.ask}")
                print(f"Last:   ${ticker.last}")
                print(f"Close:  ${ticker.close}")
                print(f"Volume: {ticker.volume}")
                
                # Cancel market data subscription
                ib.cancelMktData(stock)
                
            except Exception as e:
                print(f"ERROR getting {symbol} quote: {e}")
        
        return True
        
    except Exception as e:
        print(f"ERROR: Market data test failed - {e}")
        print("\nTroubleshooting:")
        print("1. Market data permissions may be needed")
        print("2. Try ib.reqMarketDataType(3) for delayed data")
        print("3. Check if you have market data subscriptions in your IB account")
        return False


def test_historical_data(ib):
    """Test historical data retrieval"""
    print_section("HISTORICAL DATA TEST")
    
    try:
        # Get historical bars for AAPL
        symbol = 'AAPL'
        stock = Stock(symbol, 'SMART', 'USD')
        ib.qualifyContracts(stock)
        
        print(f"Requesting historical data for {symbol}...")
        print("Duration: 1 day, Bar size: 1 hour")
        
        bars = ib.reqHistoricalData(
            stock,
            endDateTime='',
            durationStr='1 D',
            barSizeSetting='1 hour',
            whatToShow='TRADES',
            useRTH=True,  # Regular trading hours only
            formatDate=1
        )
        
        if bars:
            print(f"\nReceived {len(bars)} bars")
            print("\nLast 3 bars:")
            print("-" * 60)
            for bar in bars[-3:]:
                print(f"{bar.date} | O:{bar.open:>7.2f} H:{bar.high:>7.2f} L:{bar.low:>7.2f} C:{bar.close:>7.2f} V:{bar.volume:>10}")
            print("-" * 60)
            return True
        else:
            print("WARNING: No historical data received")
            return False
            
    except Exception as e:
        print(f"ERROR: Historical data test failed - {e}")
        return False


def test_account_info(ib):
    """Test account information retrieval"""
    print_section("ACCOUNT INFORMATION TEST")
    
    try:
        # Get account summary
        account = ib.managedAccounts()[0] if ib.managedAccounts() else None
        
        if account:
            print(f"Account: {account}")
            
            # Get account values
            account_values = ib.accountValues()
            
            # Show key values
            key_fields = ['NetLiquidation', 'TotalCashValue', 'BuyingPower', 'GrossPositionValue']
            print("\nKey Account Values:")
            for av in account_values:
                if av.tag in key_fields:
                    print(f"  {av.tag:20s}: {av.value:>15s} {av.currency}")
            
            # Get positions
            positions = ib.positions()
            if positions:
                print(f"\nCurrent Positions: {len(positions)}")
                for pos in positions[:5]:  # Show first 5
                    print(f"  {pos.contract.symbol:6s}: {pos.position:>8.0f} shares @ ${pos.avgCost:.2f}")
            else:
                print("\nNo open positions")
            
            return True
        else:
            print("No managed accounts found")
            return False
            
    except Exception as e:
        print(f"ERROR: Account info test failed - {e}")
        return False


def main():
    """Main test function"""
    print("=" * 60)
    print("  INTERACTIVE BROKERS CONNECTION TEST")
    print("=" * 60)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Test 1: Connection
    ib = test_connection()
    if not ib:
        print("\nABORTED: Could not connect to IB Gateway")
        sys.exit(1)
    
    # Test 2: Market Data
    test_market_data(ib)
    
    # Test 3: Historical Data
    test_historical_data(ib)
    
    # Test 4: Account Info
    test_account_info(ib)
    
    # Disconnect
    print_section("DISCONNECTING")
    ib.disconnect()
    print("Disconnected from IB Gateway")
    
    print("\n" + "=" * 60)
    print("  TEST COMPLETE")
    print("=" * 60)
    print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n\nUNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

