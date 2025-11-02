"""Quick check of IB paper account balance"""
import sys
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass

from ib_insync import IB

ib = IB()
ib.connect('127.0.0.1', 7497, clientId=99, timeout=5)

print("=" * 60)
print("  YOUR IB PAPER ACCOUNT BALANCE")
print("=" * 60)

account = ib.managedAccounts()[0]
print(f"\nAccount: {account}\n")

for av in ib.accountValues():
    if av.tag in ['NetLiquidation', 'TotalCashValue', 'BuyingPower', 
                   'GrossPositionValue', 'AvailableFunds', 'ExcessLiquidity']:
        print(f"{av.tag:25s}: ${float(av.value):,.2f} {av.currency}")

positions = ib.positions()
if positions:
    print(f"\nCurrent Holdings:")
    for pos in positions:
        print(f"  {pos.contract.symbol}: {pos.position} shares @ ${pos.avgCost:.2f}")
else:
    print(f"\nNo current holdings (all cash)")

ib.disconnect()
print("\n" + "=" * 60)

