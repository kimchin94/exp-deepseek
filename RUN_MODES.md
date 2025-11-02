# Trading Simulation Run Modes

## Mode 1: Backtest with Historical Data (LOCAL)
**Use when**: Testing strategies on past data, deterministic results needed

```powershell
# In .env, set:
PRICE_SOURCE=LOCAL

# Run backtest on historical dates
python main.py
```

**Pros**:
- ✅ Fast, repeatable
- ✅ Complete historical data
- ✅ Works 24/7 (no market hours dependency)

**Cons**:
- ❌ Not testing live integration
- ❌ Can't simulate real market conditions

---

## Mode 2: Paper Trading with IBKR Live Data
**Use when**: Testing with real market conditions, live price movements

### Prerequisites:
1. **Market must be OPEN** (Mon-Fri 9:30am-4:00pm ET)
2. **IB Gateway running** on port 7497
3. **Different client IDs** for services vs agent

### Setup:

```powershell
# Terminal A - Start MCP Services
cd O:\dev\exp-deepseek\exp-deepseek
$env:IB_CLIENT_ID = "3"
$env:PRICE_SOURCE = "IBKR"
python agent_tools\start_mcp_services.py
```

```powershell
# Terminal B - Run Agent (after services are up)
cd O:\dev\exp-deepseek\exp-deepseek
$env:IB_CLIENT_ID = "2"
$env:PRICE_SOURCE = "IBKR"
python main.py
```

**Pros**:
- ✅ Real market prices
- ✅ Tests full IB integration
- ✅ Realistic P&L simulation
- ✅ Can place paper orders

**Cons**:
- ❌ Only works during market hours
- ❌ Slower (network latency)
- ❌ Dependent on IB Gateway connection

---

## Mode 3: Test NOW with Static IB Data (Not Recommended)
**Current situation**: Market closed, IB returns Friday's close

```powershell
$env:PRICE_SOURCE = "IBKR"
python main.py
```

**What happens**:
- Agent gets prices from IB (e.g., AAPL=$270.04)
- Prices DON'T change (market closed)
- Trading simulation runs but no realistic price movement
- Good for testing connectivity, NOT for strategy validation

---

## Recommended Workflow

### Phase 1: Development & Backtesting (Now)
```powershell
PRICE_SOURCE=LOCAL
# Use historical data from merged.jsonl
# Fast iteration, deterministic results
```

### Phase 2: Paper Trading (Monday 9:30am ET onwards)
```powershell
PRICE_SOURCE=IBKR
# Switch to live data
# Test in real market conditions
```

### Phase 3: Live Trading (When ready)
```powershell
PRICE_SOURCE=IBKR
IB_PORT=7496  # Live port (not 7497 paper)
# Real money, real trades
```

---

## Quick Test Matrix

| Scenario | PRICE_SOURCE | Market State | Result |
|----------|--------------|--------------|--------|
| Historical backtest | LOCAL | Any | ✅ Works great |
| Test IB connection | IBKR | Closed | ✅ Gets static prices |
| Paper trading | IBKR | Open | ✅ Real simulation |
| Live trading | IBKR | Open | 💰 Real money |

---

## Current Status (Sunday 7:29am ET)

**Can run?** Yes  
**Recommended?** Only for testing connectivity  
**Best action?** Wait for market open Monday OR use LOCAL for backtesting

**Next market open**: Monday 9:30am ET = Monday 9:30pm KL time

