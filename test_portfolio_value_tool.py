#!/usr/bin/env python3
"""
Test script to verify get_portfolio_value tool is working
"""

import sys
import os
from pathlib import Path

# Setup environment
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

os.environ["TODAY_DATE"] = "2025-10-24"
os.environ["SIGNATURE"] = "deepseek-chat-v3.1"

# Import the function directly from tool_trade
from agent_tools.tool_trade import get_portfolio_value

print("Testing get_portfolio_value tool...")
print("=" * 60)

result = get_portfolio_value()

print(f"\nResult:")
print(f"  Total Value: ${result.get('total_value', 'N/A'):,.2f}")
print(f"  Date: {result.get('date', 'N/A')}")
print(f"  Message: {result.get('message', 'N/A')}")

if result.get('error'):
    print(f"\n  ERROR: {result['error']}")
else:
    print(f"\n  Holdings count: {len(result.get('holdings', {}))}")
    
    # Show a few holdings
    holdings = result.get('holdings', {})
    print(f"\n  Sample holdings:")
    for symbol in list(holdings.keys())[:5]:
        info = holdings[symbol]
        if symbol == 'CASH':
            print(f"    - CASH: ${info.get('value', 0):,.2f}")
        else:
            print(f"    - {symbol}: {info.get('shares')} shares × ${info.get('price', 0):.2f} = ${info.get('value', 0):,.2f}")

print("\n" + "=" * 60)
print("\nIf you see a valid total value above, the tool is working!")
print("\nNext step: Restart MCP services so the agent can access this tool.")
print("Run: python agent_tools/start_mcp_services.py")

