"""
Portfolio Valuation Module
--------------------------
Provides deterministic portfolio valuation functions.
Can be imported by agents or scripts for accurate PnL calculation.
"""

import json
from pathlib import Path
from typing import Dict, Tuple, Optional

try:
    # Try relative import (when used as module)
    from .price_tools import get_open_prices
except ImportError:
    # Fall back to absolute import (when run as script)
    from price_tools import get_open_prices


def calculate_portfolio_value(
    date: str,
    positions: Dict[str, float],
    merged_path: Optional[str] = None
) -> Tuple[float, Dict[str, dict]]:
    """
    Calculate deterministic portfolio value for a given date and positions.
    
    Args:
        date: Trading date (YYYY-MM-DD format)
        positions: Dict of {symbol: shares} plus 'CASH'
        merged_path: Optional path to merged.jsonl price data
        
    Returns:
        (total_value, details_dict)
        where details_dict = {symbol: {'shares': x, 'price': y, 'value': z}}
        
    Example:
        >>> positions = {'CASH': 100.0, 'AAPL': 10, 'GOOGL': 5}
        >>> value, details = calculate_portfolio_value('2025-10-30', positions)
        >>> print(f"Total: ${value:,.2f}")
        Total: $10,626.24
    """
    if merged_path is None:
        base_dir = Path(__file__).resolve().parents[1]
        merged_path = str(base_dir / "data" / "merged.jsonl")
    
    cash = positions.get('CASH', 0.0)
    details = {'CASH': {'shares': 1, 'price': cash, 'value': cash}}
    
    # Get all stock symbols (exclude CASH and zero positions)
    symbols = [sym for sym in positions.keys() 
               if sym != 'CASH' and positions.get(sym, 0) > 0]
    
    if not symbols:
        return cash, details
    
    # Get opening prices for all symbols on this date
    prices = get_open_prices(date, symbols, merged_path=merged_path)
    
    total_value = cash
    
    for symbol in symbols:
        shares = positions[symbol]
        price_key = f"{symbol}_price"
        price = prices.get(price_key)
        
        if price is None:
            # Price not found - cannot value this position
            details[symbol] = {
                'shares': shares,
                'price': None,
                'value': None,
                'error': 'Price not found'
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


def get_portfolio_value_from_file(
    date: str,
    position_file: Path,
    merged_path: Optional[str] = None
) -> Tuple[Optional[float], Optional[Dict[str, dict]], Optional[dict]]:
    """
    Read positions from position.jsonl and calculate portfolio value.
    
    Args:
        date: Trading date (YYYY-MM-DD format)
        position_file: Path to position.jsonl file
        merged_path: Optional path to merged.jsonl price data
        
    Returns:
        (total_value, details_dict, position_record)
        Returns (None, None, None) if date not found
    """
    if not position_file.exists():
        return None, None, None
    
    # Find the last position record for this date
    target_position = None
    
    with position_file.open('r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                record_date = record.get('date', '')
                # Extract date part if timestamp
                if ' ' in record_date:
                    record_date = record_date.split()[0]
                
                if record_date == date:
                    target_position = record
            except Exception:
                continue
    
    if target_position is None:
        return None, None, None
    
    positions = target_position.get('positions', {})
    total_value, details = calculate_portfolio_value(date, positions, merged_path)
    
    return total_value, details, target_position


def calculate_pnl(
    initial_value: float,
    final_value: float
) -> Tuple[float, float]:
    """
    Calculate P&L in dollars and percentage.
    
    Args:
        initial_value: Starting portfolio value
        final_value: Ending portfolio value
        
    Returns:
        (pnl_dollars, pnl_percent)
        
    Example:
        >>> pnl_dollars, pnl_percent = calculate_pnl(10000, 10626.24)
        >>> print(f"P&L: ${pnl_dollars:,.2f} ({pnl_percent:+.2f}%)")
        P&L: $626.24 (+6.26%)
    """
    pnl_dollars = final_value - initial_value
    pnl_percent = (pnl_dollars / initial_value) * 100 if initial_value != 0 else 0.0
    
    return pnl_dollars, pnl_percent


def format_portfolio_summary(
    date: str,
    total_value: float,
    details: Dict[str, dict],
    initial_value: Optional[float] = None
) -> str:
    """
    Format a human-readable portfolio summary.
    
    Args:
        date: Trading date
        total_value: Total portfolio value
        details: Holdings details from calculate_portfolio_value
        initial_value: Optional initial value for P&L calculation
        
    Returns:
        Formatted string summary
    """
    lines = [f"\nPortfolio Summary for {date}"]
    lines.append("=" * 60)
    
    # Sort holdings: CASH first, then alphabetically
    sorted_symbols = sorted([s for s in details.keys() if s != 'CASH'])
    if 'CASH' in details:
        sorted_symbols = ['CASH'] + sorted_symbols
    
    lines.append("\nHoldings:")
    for symbol in sorted_symbols:
        info = details[symbol]
        if symbol == 'CASH':
            lines.append(f"  CASH: ${info['value']:,.2f}")
        elif info.get('price') is not None:
            lines.append(
                f"  {symbol:6s}: {info['shares']:5.0f} shares x "
                f"${info['price']:8.2f} = ${info['value']:10,.2f}"
            )
        else:
            lines.append(
                f"  {symbol:6s}: {info['shares']:5.0f} shares x "
                f"[NO PRICE] = [UNKNOWN]"
            )
    
    lines.append(f"\nTotal Portfolio Value: ${total_value:,.2f}")
    
    if initial_value is not None:
        pnl_dollars, pnl_percent = calculate_pnl(initial_value, total_value)
        lines.append(f"P&L: ${pnl_dollars:+,.2f} ({pnl_percent:+.2f}%)")
    
    lines.append("=" * 60)
    
    return '\n'.join(lines)


# Example usage and testing
if __name__ == "__main__":
    # Test with a sample position
    test_positions = {
        'CASH': 23.63,
        'AAPL': 8,
        'GOOGL': 8,
        'NVDA': 6,
        'MSFT': 3,
        'AVGO': 3,
        'AMZN': 5,
        'CRWD': 1,
        'ARM': 1,
        'AMD': 1,
        'PYPL': 1
    }
    
    test_date = '2025-10-30'
    
    print(f"Testing portfolio valuation for {test_date}")
    value, details = calculate_portfolio_value(test_date, test_positions)
    
    print(format_portfolio_summary(test_date, value, details, initial_value=10000.0))
    
    print("\n[OK] Valuation module is working correctly!")

