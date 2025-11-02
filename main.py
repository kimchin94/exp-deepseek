import os
import sys
import asyncio
from datetime import datetime, timedelta
import json
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

# Fix Windows console UTF-8 encoding
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass

# Import tools and prompts
from tools.general_tools import get_config_value, write_config_value
from prompts.agent_prompt import all_nasdaq_100_symbols


# Agent class mapping table - for dynamic import and instantiation
AGENT_REGISTRY = {
    "BaseAgent": {
        "module": "agent.base_agent.base_agent",
        "class": "BaseAgent"
    },
    "BaseAgent_Hour": {
        "module": "agent.base_agent.base_agent_hour",
        "class": "BaseAgent_Hour"
    },
}


def get_agent_class(agent_type):
    """
    Dynamically import and return the corresponding class based on agent type name
    
    Args:
        agent_type: Agent type name (e.g., "BaseAgent")
        
    Returns:
        Agent class
        
    Raises:
        ValueError: If agent type is not supported
        ImportError: If unable to import agent module
    """
    if agent_type not in AGENT_REGISTRY:
        supported_types = ", ".join(AGENT_REGISTRY.keys())
        raise ValueError(
            f"❌ Unsupported agent type: {agent_type}\n"
            f"   Supported types: {supported_types}"
        )
    
    agent_info = AGENT_REGISTRY[agent_type]
    module_path = agent_info["module"]
    class_name = agent_info["class"]
    
    try:
        # Dynamic import module
        import importlib
        module = importlib.import_module(module_path)
        agent_class = getattr(module, class_name)
        print(f"✅ Successfully loaded Agent class: {agent_type} (from {module_path})")
        return agent_class
    except ImportError as e:
        raise ImportError(f"❌ Unable to import agent module {module_path}: {e}")
    except AttributeError as e:
        raise AttributeError(f"❌ Class {class_name} not found in module {module_path}: {e}")


def load_config(config_path=None):
    """
    Load configuration file from configs directory
    
    Args:
        config_path: Configuration file path, if None use default config
        
    Returns:
        dict: Configuration dictionary
    """
    if config_path is None:
        # Default configuration file path
        config_path = Path(__file__).parent / "configs" / "default_config.json"
    else:
        config_path = Path(config_path)
    
    if not config_path.exists():
        print(f"❌ Configuration file does not exist: {config_path}")
        exit(1)
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        print(f"✅ Successfully loaded configuration file: {config_path}")
        return config
    except json.JSONDecodeError as e:
        print(f"❌ Configuration file JSON format error: {e}")
        exit(1)
    except Exception as e:
        print(f"❌ Failed to load configuration file: {e}")
        exit(1)


async def main(config_path=None):
    """Run trading experiment using BaseAgent class
    
    Args:
        config_path: Configuration file path, if None use default config
    """
    # Load configuration file
    config = load_config(config_path)
    
    # Get Agent type
    agent_type = config.get("agent_type", "BaseAgent")
    try:
        AgentClass = get_agent_class(agent_type)
    except (ValueError, ImportError, AttributeError) as e:
        print(str(e))
        exit(1)
    
    # Get date range from configuration file
    INIT_DATE = config["date_range"]["init_date"]
    END_DATE = config["date_range"]["end_date"]
    
    # Environment variables can override dates in configuration file
    if os.getenv("INIT_DATE"):
        INIT_DATE = os.getenv("INIT_DATE")
        print(f"⚠️  Using environment variable to override INIT_DATE: {INIT_DATE}")
    if os.getenv("END_DATE"):
        END_DATE = os.getenv("END_DATE")
        print(f"⚠️  Using environment variable to override END_DATE: {END_DATE}")
    
    # Convert date-only format to include opening hour (10:00:00) for intraday data
    if ' ' not in INIT_DATE:
        INIT_DATE = f"{INIT_DATE} 10:00:00"
        print(f"📅 Converted INIT_DATE to opening hour: {INIT_DATE}")
    if ' ' not in END_DATE:
        END_DATE = f"{END_DATE} 10:00:00"
        print(f"📅 Converted END_DATE to opening hour: {END_DATE}")
    
    # Validate date range
    # Support both YYYY-MM-DD and YYYY-MM-DD HH:MM:SS formats
    if ' ' in INIT_DATE:
        INIT_DATE_obj = datetime.strptime(INIT_DATE, "%Y-%m-%d %H:%M:%S")
    else:
        INIT_DATE_obj = datetime.strptime(INIT_DATE, "%Y-%m-%d")
    
    if ' ' in END_DATE:
        END_DATE_obj = datetime.strptime(END_DATE, "%Y-%m-%d %H:%M:%S")
    else:
        END_DATE_obj = datetime.strptime(END_DATE, "%Y-%m-%d")
    
    if INIT_DATE_obj > END_DATE_obj:
        print("❌ INIT_DATE is greater than END_DATE")
        exit(1)
 
    # Get model list from configuration file (only select enabled models)
    enabled_models = [
        model for model in config["models"] 
        if model.get("enabled", True)
    ]
    
    # Get agent configuration
    agent_config = config.get("agent_config", {})
    log_config = config.get("log_config", {})
    min_steps = agent_config.get("min_steps", 2)
    max_steps = agent_config.get("max_steps", 10)
    max_retries = agent_config.get("max_retries", 3)
    base_delay = agent_config.get("base_delay", 0.5)
    initial_cash = agent_config.get("initial_cash", 10000.0)
    
    # Display enabled model information
    model_names = [m.get("name", m.get("signature")) for m in enabled_models]
    
    print("🚀 Starting trading experiment")
    print(f"🤖 Agent type: {agent_type}")
    print(f"📅 Date range: {INIT_DATE} to {END_DATE}")
    print(f"🤖 Model list: {model_names}")
    print(f"⚙️  Agent config: min_steps={min_steps}, max_steps={max_steps}, max_retries={max_retries}, base_delay={base_delay}, initial_cash={initial_cash}")
                    
    # Optional watchdog: stop after MAX_RUNTIME_MINUTES
    max_runtime_min = os.getenv("MAX_RUNTIME_MINUTES")
    deadline = None
    if max_runtime_min:
        try:
            deadline = datetime.now() + timedelta(minutes=float(max_runtime_min))
            print(f"⏱️  Watchdog enabled: will stop after {max_runtime_min} minutes")
        except Exception:
            deadline = None

    for model_config in enabled_models:
        # Read basemodel and signature directly from configuration file
        model_name = model_config.get("name", "unknown")
        basemodel = model_config.get("basemodel")
        signature = model_config.get("signature")
        openai_base_url = model_config.get("openai_base_url",None)
        openai_api_key = model_config.get("openai_api_key",None)
        
        # Validate required fields
        if not basemodel:
            print(f"❌ Model {model_name} missing basemodel field")
            continue
        if not signature:
            print(f"❌ Model {model_name} missing signature field")
            continue
        
        print("=" * 60)
        print(f"🤖 Processing model: {model_name}")
        print(f"📝 Signature: {signature}")
        print(f"🔧 BaseModel: {basemodel}")
        
        # Initialize per-signature runtime configuration
        # Use a per-signature runtime env file that stores only TODAY_DATE and IF_TRADE
        # Also export SIGNATURE via process env for tools that read it (but do not persist it)
        from pathlib import Path as _Path
        project_root = _Path(__file__).resolve().parent
        runtime_env_dir = project_root / "data" / "agent_data" / signature
        runtime_env_dir.mkdir(parents=True, exist_ok=True)
        # Respect existing RUNTIME_ENV_PATH from .env; only set default if missing
        if not os.environ.get("RUNTIME_ENV_PATH"):
            runtime_env_path = runtime_env_dir / ".runtime_env.json"
            os.environ["RUNTIME_ENV_PATH"] = str(runtime_env_path)
        # Always persist current run values to the runtime file that tools read
        write_config_value("SIGNATURE", signature)
        write_config_value("TODAY_DATE", END_DATE)
        write_config_value("IF_TRADE", False)


        # Get log path configuration
        log_path = log_config.get("log_path", "./data/agent_data")

        try:
            # Dynamically create Agent instance
            agent = AgentClass(
                signature=signature,
                basemodel=basemodel,
                stock_symbols=all_nasdaq_100_symbols,
                log_path=log_path,
                min_steps=min_steps,
                max_steps=max_steps,
                max_retries=max_retries,
                base_delay=base_delay,
                initial_cash=initial_cash,
                init_date=INIT_DATE,
                openai_base_url=openai_base_url,
                openai_api_key=openai_api_key
            )
            
            print(f"✅ {agent_type} instance created successfully: {agent}")
            
            # Initialize MCP connection and AI model
            await agent.initialize()
            print("✅ Initialization successful")
            # Run all trading days in date range, with optional timeout
            if deadline is None:
                await agent.run_date_range(INIT_DATE, END_DATE)
            else:
                remaining = (deadline - datetime.now()).total_seconds()
                if remaining <= 0:
                    print("⏱️  Watchdog timeout reached before run; skipping")
                else:
                    try:
                        await asyncio.wait_for(agent.run_date_range(INIT_DATE, END_DATE), timeout=remaining)
                    except asyncio.TimeoutError:
                        print("⏱️  Watchdog timeout reached during run; stopping early")
            
            # Display final position summary
            summary = agent.get_position_summary()
            print(f"📊 Final position summary:")
            print(f"   - Latest date: {summary.get('latest_date')}")
            print(f"   - Total records: {summary.get('total_records')}")
            print(f"   - Cash balance: ${summary.get('positions', {}).get('CASH', 0):.2f}")
            
            # Calculate and display deterministic portfolio value
            print("\n" + "=" * 60)
            print("📈 DETERMINISTIC PORTFOLIO VALUATION")
            print("=" * 60)
            try:
                from tools.valuation import calculate_portfolio_value
                from tools.price_tools import get_open_prices
                
                latest_date = summary.get('latest_date')
                positions = summary.get('positions', {})
                
                if latest_date and positions:
                    # Calculate portfolio value
                    total_value, details = calculate_portfolio_value(latest_date, positions)
                    
                    print(f"📅 Date: {latest_date}")
                    print(f"💰 Total Portfolio Value: ${total_value:,.2f}")
                    print(f"\n📋 Holdings Breakdown:")
                    
                    # Sort: CASH first, then alphabetically
                    sorted_symbols = sorted([s for s in details.keys() if s != 'CASH'])
                    if 'CASH' in details:
                        sorted_symbols = ['CASH'] + sorted_symbols
                    
                    for symbol in sorted_symbols:
                        info = details[symbol]
                        if symbol == 'CASH':
                            print(f"   💵 CASH: ${info['value']:,.2f}")
                        elif info.get('price') is not None:
                            print(f"   📊 {symbol:6s}: {info['shares']:>6.0f} shares × ${info['price']:>8.2f} = ${info['value']:>10,.2f}")
                        else:
                            print(f"   📊 {symbol:6s}: {info['shares']:>6.0f} shares × [NO PRICE DATA]")
                    
                    # Calculate P&L if we have initial cash
                    pnl = total_value - initial_cash
                    pnl_pct = (pnl / initial_cash) * 100
                    
                    print(f"\n📊 Performance:")
                    print(f"   Initial Investment: ${initial_cash:,.2f}")
                    print(f"   Current Value:      ${total_value:,.2f}")
                    if pnl >= 0:
                        print(f"   Profit/Loss:        +${pnl:,.2f} (+{pnl_pct:.2f}%) 📈")
                    else:
                        print(f"   Profit/Loss:        -${abs(pnl):,.2f} ({pnl_pct:.2f}%) 📉")
                else:
                    print("⚠️  No position data available for valuation")
                    
            except Exception as e:
                print(f"❌ Error calculating portfolio value: {e}")
                import traceback
                traceback.print_exc()
            
            print("=" * 60)
            
        except Exception as e:
            print(f"❌ Error processing model {model_name} ({signature}): {str(e)}")
            print(f"📋 Error details: {e}")
            # Can choose to continue processing next model, or exit
            # continue  # Continue processing next model
            exit()  # Or exit program
        
        print("=" * 60)
        print(f"✅ Model {model_name} ({signature}) processing completed")
        print("=" * 60)
    
    print("🎉 All models processing completed!")
    # If watchdog set, attempt to stop MCP services using PID file
    if max_runtime_min:
        try:
            import subprocess
            subprocess.run([sys.executable, str(Path(__file__).parent / 'agent_tools' / 'start_mcp_services.py'), 'stop'], check=False)
            print("🛑 Requested MCP services stop (from PID file)")
        except Exception as e:
            print(f"⚠️  Failed to stop MCP services automatically: {e}")
    
if __name__ == "__main__":
    import sys
    
    # Support specifying configuration file through command line arguments
    # Usage: python livebaseagent_config.py [config_path]
    # Example: python livebaseagent_config.py configs/my_config.json
    config_path = sys.argv[1] if len(sys.argv) > 1 else None
    
    if config_path:
        print(f"Using specified configuration file: {config_path}")
    else:
        print(f"Using default configuration file: configs/default_config.json")
    
    asyncio.run(main(config_path))

