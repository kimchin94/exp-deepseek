#!/usr/bin/env python3
"""
Deterministic Portfolio Valuation Script
-----------------------------------------
Calculates true portfolio values from position.jsonl and price data,
without relying on model narrative text.
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import sys

# Add tools directory to path to use get_open_prices
sys.path.insert(0, str(Path(__file__).parent))
from tools.price_tools import get_open_prices


def read_positions_by_date(position_file: Path) -> Dict[str, dict]:
    """
    Read position.jsonl and return the last position for each trading date.
    
    Returns:
        Dict mapping date -> position dict (with 'positions' key containing holdings)
    """
    positions_by_date = {}
    
    with position_file.open('r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                date = record.get('date', '')
                # Extract just the date part if it's a timestamp
                if ' ' in date:
                    date = date.split()[0]
                
                # Store the record (will overwrite with latest for each date)
                positions_by_date[date] = record
            except Exception as e:
                print(f"Warning: Failed to parse line: {e}")
                continue
    
    return positions_by_date


def calculate_portfolio_value(date: str, positions: Dict[str, float], merged_path: Path) -> Tuple[float, Dict[str, dict]]:
    """
    Calculate deterministic portfolio value for a given date and positions.
    
    Args:
        date: Trading date (YYYY-MM-DD format)
        positions: Dict of {symbol: shares} plus 'CASH'
        merged_path: Path to merged.jsonl price data
        
    Returns:
        (total_value, details_dict)
        where details_dict = {symbol: {'shares': x, 'price': y, 'value': z}}
    """
    cash = positions.get('CASH', 0.0)
    details = {'CASH': {'shares': 1, 'price': cash, 'value': cash}}
    
    # Get all stock symbols (exclude CASH)
    symbols = [sym for sym in positions.keys() if sym != 'CASH' and positions[sym] > 0]
    
    if not symbols:
        return cash, details
    
    # Get opening prices for all symbols on this date
    prices = get_open_prices(date, symbols, merged_path=str(merged_path))
    
    total_value = cash
    
    for symbol in symbols:
        shares = positions[symbol]
        price_key = f"{symbol}_price"
        price = prices.get(price_key)
        
        if price is None:
            print(f"  WARNING: No price found for {symbol} on {date}")
            details[symbol] = {
                'shares': shares,
                'price': None,
                'value': None
            }
        else:
            value = shares * price
            total_value += value
            details[symbol] = {
                'shares': shares,
                'price': price,
                'value': value
            }
    
    return total_value, details


def main():
    """Main entry point for portfolio valuation."""
    
    # Configuration
    agent_name = "deepseek-chat-v3.1"
    base_dir = Path(__file__).parent
    
    position_file = base_dir / "data" / "agent_data" / agent_name / "position" / "position.jsonl"
    merged_file = base_dir / "data" / "merged.jsonl"
    
    if not position_file.exists():
        print(f"ERROR: Position file not found: {position_file}")
        return 1
    
    if not merged_file.exists():
        print(f"ERROR: Price data file not found: {merged_file}")
        return 1
    
    # Read all positions by date
    print(f"Reading positions from: {position_file}")
    positions_by_date = read_positions_by_date(position_file)
    
    # Get sorted list of trading dates
    trading_dates = sorted(positions_by_date.keys())
    
    if not trading_dates:
        print("ERROR: No trading dates found in position file")
        return 1
    
    print(f"\nFound {len(trading_dates)} trading dates")
    print("=" * 80)
    
    # Calculate valuation for each date
    initial_value = None
    
    for date in trading_dates:
        record = positions_by_date[date]
        positions = record.get('positions', {})
        
        print(f"\nDate: {date}")
        print(f"   Last Action: {record.get('this_action', {})}")
        
        total_value, details = calculate_portfolio_value(date, positions, merged_file)
        
        print(f"\n   Holdings:")
        for symbol in sorted(details.keys()):
            info = details[symbol]
            if symbol == 'CASH':
                print(f"      CASH: ${info['value']:,.2f}")
            elif info['price'] is not None:
                print(f"      {symbol:6s}: {info['shares']:4.0f} shares x ${info['price']:8.2f} = ${info['value']:10,.2f}")
            else:
                print(f"      {symbol:6s}: {info['shares']:4.0f} shares x [NO PRICE] = [UNKNOWN]")
        
        print(f"\n   >> Total Portfolio Value: ${total_value:,.2f}")
        
        # Track initial value and calculate returns
        if initial_value is None:
            initial_value = total_value
            print(f"   >> Initial Investment")
        else:
            pnl = total_value - initial_value
            pnl_pct = (pnl / initial_value) * 100
            print(f"   >> P&L: ${pnl:+,.2f} ({pnl_pct:+.2f}%)")
        
        print("-" * 80)
    
    # Final Summary
    print("\n" + "=" * 80)
    print("FINAL SUMMARY")
    print("=" * 80)
    
    if trading_dates:
        final_date = trading_dates[-1]
        final_record = positions_by_date[final_date]
        final_positions = final_record.get('positions', {})
        final_value, final_details = calculate_portfolio_value(final_date, final_positions, merged_file)
        
        print(f"\nInitial Value (2025-10-23): ${initial_value:,.2f}")
        print(f"Final Value   ({final_date}): ${final_value:,.2f}")
        
        if initial_value:
            total_pnl = final_value - initial_value
            total_pnl_pct = (total_pnl / initial_value) * 100
            print(f"\nTotal P&L: ${total_pnl:+,.2f} ({total_pnl_pct:+.2f}%)")
            
            if total_pnl_pct < 0:
                print(f"\n** Portfolio is DOWN {abs(total_pnl_pct):.2f}%")
            else:
                print(f"\n** Portfolio is UP {total_pnl_pct:.2f}%")
    
    print("=" * 80)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

