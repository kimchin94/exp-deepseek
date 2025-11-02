"""
MCP Tool: Get Portfolio Value
------------------------------
Provides deterministic portfolio valuation to prevent arithmetic errors.
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from tools.valuation import calculate_portfolio_value, format_portfolio_summary
from tools.general_tools import get_config_value
from tools.price_tools import get_today_init_position, get_yesterday_date

# Import MCP server
try:
    from mcp_server_instance import mcp
except ImportError:
    print("Warning: MCP server not available")
    mcp = None


@mcp.tool()
def get_portfolio_value(date: str = None) -> Dict[str, Any]:
    """
    Get deterministic portfolio valuation for current or specified date.
    
    This tool calculates the EXACT portfolio value using actual positions and market prices.
    DO NOT manually calculate portfolio totals - use this tool instead!
    
    Args:
        date: Optional date in YYYY-MM-DD format. If not provided, uses current trading date.
        
    Returns:
        Dictionary containing:
        - total_value: Total portfolio value in dollars
        - holdings: Detailed breakdown of each position
        - summary: Human-readable summary text
        
    Example:
        result = get_portfolio_value("2025-10-30")
        # Returns: {"total_value": 10741.63, "holdings": {...}, "summary": "..."}
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
            "message": f"Portfolio total: ${total_value:,.2f}"
        }
        
    except Exception as e:
        return {
            "error": str(e),
            "total_value": None,
            "holdings": {},
            "summary": f"Error calculating portfolio value: {str(e)}"
        }


# For testing
if __name__ == "__main__":
    import os
    os.environ["TODAY_DATE"] = "2025-10-30"
    os.environ["SIGNATURE"] = "deepseek-chat-v3.1"
    
    result = get_portfolio_value()
    print(json.dumps(result, indent=2))

