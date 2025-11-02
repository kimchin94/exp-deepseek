from fastmcp import FastMCP
import sys
import os
from typing import Dict, List, Optional, Any
from pathlib import Path
import platform

# Cross-platform file locking
if platform.system() == 'Windows':
    import msvcrt
else:
    import fcntl

# Add project root directory to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
from tools.price_tools import get_yesterday_date, get_open_prices, get_yesterday_open_and_close_price, get_latest_position, get_yesterday_profit, get_today_init_position
import json
from tools.general_tools import get_config_value,write_config_value
from tools.valuation import calculate_portfolio_value, format_portfolio_summary
mcp = FastMCP("TradeTools")


def _position_lock(signature: str):
    """Context manager for file-based lock to serialize position updates per signature."""
    class _Lock:
        def __init__(self, name: str):
            base_dir = Path(project_root) / "data" / "agent_data" / name
            base_dir.mkdir(parents=True, exist_ok=True)
            self.lock_path = base_dir / ".position.lock"
            # Ensure lock file exists
            self._fh = open(self.lock_path, "a+")
        def __enter__(self):
            if platform.system() == 'Windows':
                # Windows file locking
                msvcrt.locking(self._fh.fileno(), msvcrt.LK_LOCK, 1)
            else:
                # Unix/Linux file locking
                fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX)
            return self
        def __exit__(self, exc_type, exc, tb):
            try:
                if platform.system() == 'Windows':
                    # Windows unlock
                    msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    # Unix/Linux unlock
                    fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
            finally:
                self._fh.close()
    return _Lock(signature)



@mcp.tool()
def buy(symbol: str, amount: int) -> Dict[str, Any]:
    """
    Buy stock function
    
    This function simulates stock buying operations, including the following steps:
    1. Get current position and operation ID
    2. Get stock opening price for the day
    3. Validate buy conditions (sufficient cash)
    4. Update position (increase stock quantity, decrease cash)
    5. Record transaction to position.jsonl file
    
    Args:
        symbol: Stock symbol, such as "AAPL", "MSFT", etc.
        amount: Buy quantity, must be a positive integer, indicating how many shares to buy
        
    Returns:
        Dict[str, Any]:
          - Success: Returns new position dictionary (containing stock quantity and cash balance)
          - Failure: Returns {"error": error message, ...} dictionary
        
    Raises:
        ValueError: Raised when SIGNATURE environment variable is not set
        
    Example:
        >>> result = buy("AAPL", 10)
        >>> print(result)  # {"AAPL": 110, "MSFT": 5, "CASH": 5000.0, ...}
    """
    # Step 1: Get environment variables and basic information
    # Get signature (model name) from environment variable, used to determine data storage path
    signature = get_config_value("SIGNATURE")
    if signature is None:
        raise ValueError("SIGNATURE environment variable is not set")
    
    # Get current trading date from environment variable
    today_date = get_config_value("TODAY_DATE")

    # # Step-gating: Disallow trading in Step 1 (and any step < 2)
    # raw_step = get_config_value("CURRENT_STEP")
    # if raw_step is not None:
    #     try:
    #         step_num = int(raw_step)
    #     except Exception:
    #         step_num = 0
    #     if step_num < 2:
    #         return {
    #             "error": "Trading not allowed in Step 1. Execute research only.",
    #             "symbol": symbol,
    #             "date": today_date,
    #             "step": step_num
    #         }
    
    # Step 2: Get current latest position and operation ID
    # get_latest_position returns two values: position dictionary and current maximum operation ID
    # This ID is used to ensure each operation has a unique identifier
    # Acquire lock for atomic read-modify-write on positions
    with _position_lock(signature):
        try:
            current_position, current_action_id = get_latest_position(today_date, signature)
        except Exception as e:
            print(e)
            print(today_date, signature)
            return {"error": f"Failed to load latest position: {e}", "symbol": symbol, "date": today_date}
    # Step 3: Get stock opening price for the day
    # Use get_open_prices function to get the opening price of specified stock for the day
    # If stock symbol does not exist or price data is missing, KeyError exception will be raised
    try:
        this_symbol_price = get_open_prices(today_date, [symbol])[f'{symbol}_price']
    except KeyError:
        # Stock symbol does not exist or price data is missing, return error message
        return {"error": f"Symbol {symbol} not found! This action will not be allowed.", "symbol": symbol, "date": today_date}

    # Step 4: Validate buy conditions
    # Calculate cash required for purchase: stock price × buy quantity
    try:
        cash_left = current_position["CASH"] - this_symbol_price * amount
    except Exception as e:
        return {
            "error": f"Failed to compute cash after trade: {e}",
            "symbol": symbol,
            "date": today_date
        }

    # Check if cash balance is sufficient for purchase
    if cash_left < 0:
        # Insufficient cash, return error message
        return {"error": "Insufficient cash! This action will not be allowed.", "required_cash": this_symbol_price * amount, "cash_available": current_position.get("CASH", 0), "symbol": symbol, "date": today_date}
    else:
        # Step 5: Execute buy operation, update position
        # Create a copy of current position to avoid directly modifying original data
        new_position = current_position.copy()
        
        # Decrease cash balance
        new_position["CASH"] = cash_left
        
        # Increase stock position quantity (handle first-time buy)
        new_position[symbol] = new_position.get(symbol, 0) + amount
        
        # Step 6: Record transaction to position.jsonl file
        # Build file path: {project_root}/data/agent_data/{signature}/position/position.jsonl
        # Use append mode ("a") to write new transaction record
        # Each operation ID increments by 1, ensuring uniqueness of operation sequence
        position_file_path = os.path.join(project_root, "data", "agent_data", signature, "position", "position.jsonl")
        # os.makedirs(os.path.dirname(position_file_path), exist_ok=True)
        with _position_lock(signature):
            with open(position_file_path, "a") as f:
                # Write JSON format transaction record, containing date, operation ID, transaction details and updated position
                print(f"Writing to position.jsonl: {json.dumps({'date': today_date, 'id': current_action_id + 1, 'this_action':{'action':'buy','symbol':symbol,'amount':amount},'positions': new_position})}")
                f.write(json.dumps({"date": today_date, "id": current_action_id + 1, "this_action":{"action":"buy","symbol":symbol,"amount":amount},"positions": new_position}) + "\n")
        # Step 7: Return updated position
        write_config_value("IF_TRADE", True)
        print("IF_TRADE", get_config_value("IF_TRADE"))
        return new_position

@mcp.tool()
def sell(symbol: str, amount: int) -> Dict[str, Any]:
    """
    Sell stock function
    
    This function simulates stock selling operations, including the following steps:
    1. Get current position and operation ID
    2. Get stock opening price for the day
    3. Validate sell conditions (position exists, sufficient quantity)
    4. Update position (decrease stock quantity, increase cash)
    5. Record transaction to position.jsonl file
    
    Args:
        symbol: Stock symbol, such as "AAPL", "MSFT", etc.
        amount: Sell quantity, must be a positive integer, indicating how many shares to sell
        
    Returns:
        Dict[str, Any]:
          - Success: Returns new position dictionary (containing stock quantity and cash balance)
          - Failure: Returns {"error": error message, ...} dictionary
        
    Raises:
        ValueError: Raised when SIGNATURE environment variable is not set
        
    Example:
        >>> result = sell("AAPL", 10)
        >>> print(result)  # {"AAPL": 90, "MSFT": 5, "CASH": 15000.0, ...}
    """
    # Step 1: Get environment variables and basic information
    # Get signature (model name) from environment variable, used to determine data storage path
    signature = get_config_value("SIGNATURE")
    if signature is None:
        raise ValueError("SIGNATURE environment variable is not set")
    
    # Get current trading date from environment variable
    today_date = get_config_value("TODAY_DATE")

    # NOTE: Step-gating temporarily disabled to allow Step 1 trading as requested
    raw_step = get_config_value("CURRENT_STEP")
    if raw_step is not None:
        try:
            step_num = int(raw_step)
        except Exception:
            step_num = 0
        if step_num < 2:
            return {
                "error": "Trading not allowed in Step 1. Execute research only.",
                "symbol": symbol,
                "date": today_date,
                "step": step_num
            }
    # NOTE: Step-gating temporarily disabled to allow Step 1 trading as requested
    raw_step = get_config_value("CURRENT_STEP")
    if raw_step is not None:
        try:
            step_num = int(raw_step)
        except Exception:
            step_num = 0
        if step_num < 2:
            return {
                "error": "Trading not allowed in Step 1. Execute research only.",
                "symbol": symbol,
                "date": today_date,
                "step": step_num
            }
    
    # Step 2: Get current latest position and operation ID under lock
    # get_latest_position returns two values: position dictionary and current maximum operation ID
    # This ID is used to ensure each operation has a unique identifier
    with _position_lock(signature):
        current_position, current_action_id = get_latest_position(today_date, signature)
    
    # Step 3: Get stock opening price for the day
    # Use get_open_prices function to get the opening price of specified stock for the day
    # If stock symbol does not exist or price data is missing, KeyError exception will be raised
    try:
        this_symbol_price = get_open_prices(today_date, [symbol])[f'{symbol}_price']
    except KeyError:
        # Stock symbol does not exist or price data is missing, return error message
        return {"error": f"Symbol {symbol} not found! This action will not be allowed.", "symbol": symbol, "date": today_date}

    # Step 4: Validate sell conditions
    # Check if holding this stock
    if symbol not in current_position:
        return {"error": f"No position for {symbol}! This action will not be allowed.", "symbol": symbol, "date": today_date}

    # Check if position quantity is sufficient for selling
    if current_position[symbol] < amount:
        return {"error": "Insufficient shares! This action will not be allowed.", "have": current_position.get(symbol, 0), "want_to_sell": amount, "symbol": symbol, "date": today_date}

    # Step 5: Execute sell operation, update position
    # Create a copy of current position to avoid directly modifying original data
    new_position = current_position.copy()
    
    # Decrease stock position quantity
    new_position[symbol] -= amount
    
    # Increase cash balance: sell price × sell quantity
    # Use get method to ensure CASH field exists, default to 0 if not present
    new_position["CASH"] = new_position.get("CASH", 0) + this_symbol_price * amount

    # Step 6: Record transaction to position.jsonl file
    # Build file path: {project_root}/data/agent_data/{signature}/position/position.jsonl
    # Use append mode ("a") to write new transaction record
    # Each operation ID increments by 1, ensuring uniqueness of operation sequence
    position_file_path = os.path.join(project_root, "data", "agent_data", signature, "position", "position.jsonl")
    # os.makedirs(os.path.dirname(position_file_path), exist_ok=True)
    with _position_lock(signature):
        with open(position_file_path, "a") as f:
            # Write JSON format transaction record, containing date, operation ID and updated position
            print(f"Writing to position.jsonl: {json.dumps({'date': today_date, 'id': current_action_id + 1, 'this_action':{'action':'sell','symbol':symbol,'amount':amount},'positions': new_position})}")
            f.write(json.dumps({"date": today_date, "id": current_action_id + 1, "this_action":{"action":"sell","symbol":symbol,"amount":amount},"positions": new_position}) + "\n")

    # Step 7: Return updated position
    write_config_value("IF_TRADE", True)
    return new_position


@mcp.tool()
def get_portfolio_value(date: str = None) -> Dict[str, Any]:
    """
    Get deterministic portfolio valuation for current or specified date.
    
    This tool calculates the EXACT portfolio value using actual positions and market prices.
    DO NOT manually calculate portfolio totals - use this tool instead!
    
    This function returns:
    - total_value: Exact total portfolio value in dollars
    - holdings: Detailed breakdown of each position (shares, price, value)
    - summary: Human-readable summary text
    
    Args:
        date: Optional date in YYYY-MM-DD format. If not provided, uses current trading date.
        
    Returns:
        Dictionary with total_value, holdings breakdown, and formatted summary.
        
    Example:
        result = get_portfolio_value("2025-10-30")
        print(f"Total: ${result['total_value']:,.2f}")
    """
    try:
        # Get current date if not provided
        if date is None:
            date = get_config_value("TODAY_DATE")
            if date is None:
                return {
                    "error": "No date provided and TODAY_DATE not set",
                    "total_value": None,
                    "holdings": {},
                    "summary": "Error: Date not available"
                }
        
        # Get signature for position lookup
        signature = get_config_value("SIGNATURE")
        if signature is None:
            return {
                "error": "SIGNATURE not set in config",
                "total_value": None,
                "holdings": {},
                "summary": "Error: Signature not available"
            }
        
        # Extract date part if timestamp
        valuation_date = date.split()[0] if ' ' in date else date
        
        # Get current positions
        positions = get_today_init_position(date, signature)
        
        if not positions or not isinstance(positions, dict):
            return {
                "error": "No positions found",
                "total_value": None,
                "holdings": {},
                "summary": "Error: Positions not available"
            }
        
        # Get yesterday's date for current prices
        yesterday_date = get_yesterday_date(date)
        if ' ' in yesterday_date:
            yesterday_date = yesterday_date.split()[0]
        
        # Calculate portfolio value
        total_value, details = calculate_portfolio_value(yesterday_date, positions)
        
        # Format summary
        summary = format_portfolio_summary(
            yesterday_date,
            total_value,
            details,
            initial_value=10000.0  # Assuming $10k initial
        )
        
        # Build response
        return {
            "total_value": round(total_value, 2),
            "date": yesterday_date,
            "holdings": {
                symbol: {
                    "shares": info.get("shares"),
                    "price": info.get("price"),
                    "value": round(info.get("value", 0), 2) if info.get("value") is not None else None
                }
                for symbol, info in details.items()
            },
            "summary": summary,
            "message": f"✓ Portfolio total: ${total_value:,.2f} (calculated from positions × prices)"
        }
        
    except Exception as e:
        return {
            "error": str(e),
            "total_value": None,
            "holdings": {},
            "summary": f"Error calculating portfolio value: {str(e)}"
        }


if __name__ == "__main__":
    # new_result = buy("AAPL", 1)
    # print(new_result)
    # new_result = sell("AAPL", 1)
    # print(new_result)
    port = int(os.getenv("TRADE_HTTP_PORT", "8002"))
    mcp.run(transport="streamable-http", port=port)
