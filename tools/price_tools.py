import os
from dotenv import load_dotenv
load_dotenv()
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import sys
import time
import threading
import atexit

# 将项目根目录加入 Python 路径，便于从子目录直接运行本文件
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
from tools.general_tools import get_config_value

# --- IBKR connection singleton to avoid concurrent per-call connects ---
_IB_SINGLETON = None
_IB_LOCK = threading.RLock()

# Optional debug logging
def _dbg(msg: str) -> None:
    try:
        if os.getenv("IBKR_DEBUG", "false").lower() in ("1", "true", "yes", "on"):
            print(f"IBKR_DEBUG: {msg}")
    except Exception:
        pass

# Install safe wrapper to ignore unsolicited completedOrder events
def _install_safe_completed_order_wrapper() -> None:
    try:
        import ib_insync.wrapper as _ib_wrapper_mod
    except Exception:
        return
    try:
        if getattr(_install_safe_completed_order_wrapper, "_installed", False):
            return
        _install_safe_completed_order_wrapper._installed = True  # type: ignore[attr-defined]
        _orig_completed = _ib_wrapper_mod.Wrapper.completedOrder

        def _safe_completed(self, contract, order, orderState):
            try:
                res = getattr(self, '_results', None)
                if not isinstance(res, dict) or 'completedOrders' not in res:
                    return  # ignore unsolicited events when not collecting
            except Exception:
                return
            try:
                return _orig_completed(self, contract, order, orderState)
            except Exception:
                return

        _ib_wrapper_mod.Wrapper.completedOrder = _safe_completed
        _dbg("Installed safe completedOrder wrapper")
    except Exception:
        pass

def _install_decoder_guard() -> None:
    try:
        import ib_insync.decoder as _ib_decoder_mod
    except Exception:
        return
    try:
        if getattr(_install_decoder_guard, "_installed", False):
            return
        _install_decoder_guard._installed = True  # type: ignore[attr-defined]
        _orig_interpret = _ib_decoder_mod.Decoder.interpret
        def _safe_interpret(self, fields):
            try:
                return _orig_interpret(self, fields)
            except KeyError:
                # Unknown/unsupported message id (e.g., 176 currentTime string); ignore
                return
        _ib_decoder_mod.Decoder.interpret = _safe_interpret
        _dbg("Installed decoder guard for unknown message ids")
    except Exception:
        pass

def _resolve_ib_ids() -> Tuple[str, int, int, Optional[str]]:
    host = os.getenv("IB_HOST", "127.0.0.1")
    port = int(os.getenv("IB_PORT", "7497"))
    chosen_env_key = None
    for key in ("IBKR_AGENT_CLIENT_ID", "IBKR_TRADETOOLS_CLIENT_ID", "IBKR_SERVICE_CLIENT_ID", "IB_CLIENT_ID"):
        if os.getenv(key) is not None:
            chosen_env_key = key
            break
    client_id = int(os.getenv(chosen_env_key, "2"))
    return host, port, client_id, chosen_env_key

def _get_ib_singleton():
    global _IB_SINGLETON
    with _IB_LOCK:
        _install_safe_completed_order_wrapper()
        _install_decoder_guard()
        if _IB_SINGLETON is None:
            from ib_insync import IB
            _IB_SINGLETON = IB()
        if not _IB_SINGLETON.isConnected():
            host, port, client_id, src = _resolve_ib_ids()
            strict = os.getenv("IBKR_STRICT_IDS", "true").lower() in ("1", "true", "yes", "on")
            _dbg(f"singleton connect {host}:{port} clientId={client_id} (source={src}) strict={strict}")
            if strict:
                _IB_SINGLETON.connect(host, port, clientId=client_id, timeout=5)
            else:
                connected = False
                for bump in range(0, 16):
                    try:
                        _IB_SINGLETON.connect(host, port, clientId=client_id + bump, timeout=5)
                        if bump > 0:
                            _dbg(f"clientId {client_id} in use; switched to {client_id + bump}")
                        connected = True
                        break
                    except Exception as e:
                        if "client id" in str(e).lower():
                            time.sleep(0.2)
                            continue
                        raise
                if not connected:
                    raise RuntimeError("IBKR: Unable to obtain a unique client id")
            _IB_SINGLETON.sleep(0.3)
            try:
                _IB_SINGLETON.reqMarketDataType(3)
                _IB_SINGLETON.sleep(0.2)
            except Exception:
                pass
            # No-op handler for optional/unknown message ids (e.g., 176 currentTime string)
            try:
                dec = getattr(_IB_SINGLETON.client, 'decoder', None)
                if dec and hasattr(dec, 'handlers') and isinstance(dec.handlers, dict):
                    dec.handlers.setdefault(176, lambda fields: None)
                    _dbg("Installed no-op decoder handler for msgId 176")
            except Exception:
                pass
    return _IB_SINGLETON

def _ib_disconnect():
    global _IB_SINGLETON
    try:
        if _IB_SINGLETON is not None and _IB_SINGLETON.isConnected():
            _IB_SINGLETON.disconnect()
    except Exception:
        pass

atexit.register(_ib_disconnect)

all_nasdaq_100_symbols = [
    "NVDA", "MSFT", "AAPL", "GOOG", "GOOGL", "AMZN", "META", "AVGO", "TSLA",
    "NFLX", "PLTR", "COST", "ASML", "AMD", "CSCO", "AZN", "TMUS", "MU", "LIN",
    "PEP", "SHOP", "APP", "INTU", "AMAT", "LRCX", "PDD", "QCOM", "ARM", "INTC",
    "BKNG", "AMGN", "TXN", "ISRG", "GILD", "KLAC", "PANW", "ADBE", "HON",
    "CRWD", "CEG", "ADI", "ADP", "DASH", "CMCSA", "VRTX", "MELI", "SBUX",
    "CDNS", "ORLY", "SNPS", "MSTR", "MDLZ", "ABNB", "MRVL", "CTAS", "TRI",
    "MAR", "MNST", "CSX", "ADSK", "PYPL", "FTNT", "AEP", "WDAY", "REGN", "ROP",
    "NXPI", "DDOG", "AXON", "ROST", "IDXX", "EA", "PCAR", "FAST", "EXC", "TTWO",
    "XEL", "ZS", "PAYX", "WBD", "BKR", "CPRT", "CCEP", "FANG", "TEAM", "CHTR",
    "KDP", "MCHP", "GEHC", "VRSK", "CTSH", "CSGP", "KHC", "ODFL", "DXCM", "TTD",
    "ON", "BIIB", "LULU", "CDW", "GFS"
]

def get_yesterday_date(today_date: str, merged_path: Optional[str] = None) -> str:
    """
    获取输入日期的上一个交易日或时间点。
    从 merged.jsonl 读取所有可用的交易时间，然后找到 today_date 的上一个时间。
    
    Args:
        today_date: 日期字符串，格式 YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS。
        merged_path: 可选，自定义 merged.jsonl 路径；默认读取项目根目录下 data/merged.jsonl。

    Returns:
        yesterday_date: 上一个交易日或时间点的字符串，格式与输入一致。
    """
    # 解析输入日期/时间
    if ' ' in today_date:
        input_dt = datetime.strptime(today_date, "%Y-%m-%d %H:%M:%S")
        date_only = False
    else:
        input_dt = datetime.strptime(today_date, "%Y-%m-%d")
        date_only = True
    
    # 获取 merged.jsonl 文件路径
    if merged_path is None:
        base_dir = Path(__file__).resolve().parents[1]
        merged_file = base_dir / "data" / "merged.jsonl"
    else:
        merged_file = Path(merged_path)
    
    if not merged_file.exists():
        # 如果文件不存在，根据输入类型回退
        print(f"merged.jsonl file does not exist at {merged_file}")
        if date_only:
            yesterday_dt = input_dt - timedelta(days=1)
            while yesterday_dt.weekday() >= 5:
                yesterday_dt -= timedelta(days=1)
            return yesterday_dt.strftime("%Y-%m-%d")
        else:
            yesterday_dt = input_dt - timedelta(hours=1)
            return yesterday_dt.strftime("%Y-%m-%d %H:%M:%S")
    
    # 从 merged.jsonl 读取所有可用的交易时间
    all_timestamps = set()
    
    with merged_file.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                doc = json.loads(line)
                # 查找所有以 "Time Series" 开头的键
                for key, value in doc.items():
                    if key.startswith("Time Series"):
                        if isinstance(value, dict):
                            all_timestamps.update(value.keys())
                        break
            except Exception:
                continue
    
    if not all_timestamps:
        # 如果没有找到任何时间戳，根据输入类型回退
        if date_only:
            yesterday_dt = input_dt - timedelta(days=1)
            while yesterday_dt.weekday() >= 5:
                yesterday_dt -= timedelta(days=1)
            return yesterday_dt.strftime("%Y-%m-%d")
        else:
            yesterday_dt = input_dt - timedelta(hours=1)
            return yesterday_dt.strftime("%Y-%m-%d %H:%M:%S")
    
    # 将所有时间戳转换为 datetime 对象，并找到小于 today_date 的最大时间戳
    previous_timestamp = None
    
    for ts_str in all_timestamps:
        try:
            ts_dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
            if ts_dt < input_dt:
                if previous_timestamp is None or ts_dt > previous_timestamp:
                    previous_timestamp = ts_dt
        except Exception:
            continue
    
    # 如果没有找到更早的时间戳，根据输入类型回退
    if previous_timestamp is None:
        if date_only:
            yesterday_dt = input_dt - timedelta(days=1)
            while yesterday_dt.weekday() >= 5:
                yesterday_dt -= timedelta(days=1)
            return yesterday_dt.strftime("%Y-%m-%d")
        else:
            yesterday_dt = input_dt - timedelta(hours=1)
            return yesterday_dt.strftime("%Y-%m-%d %H:%M:%S")

    # 返回结果
    if date_only:
        return previous_timestamp.strftime("%Y-%m-%d")
    else:
        return previous_timestamp.strftime("%Y-%m-%d %H:%M:%S")


def get_open_prices(today_date: str, symbols: List[str], merged_path: Optional[str] = None) -> Dict[str, Optional[float]]:
    """获取指定日期与标的的价格。

    当 PRICE_SOURCE 为 'IBKR' 时，优先使用 IBKR 实时价格（last/中间价）。
    否则读取 data/merged.jsonl（AlphaVantage 合并文件）。
    
    Returns: {symbol_price: price or None}
    """
    source = (get_config_value("PRICE_SOURCE") or os.getenv("PRICE_SOURCE") or "LOCAL").upper()
    results: Dict[str, Optional[float]] = {}

    if source == "IBKR":
        try:
            # Lazy import to avoid dependency when not needed
            from ib_insync import Stock
            ib = _get_ib_singleton()
            for sym in symbols:
                try:
                    contract = Stock(sym, "SMART", "USD")
                    ib.qualifyContracts(contract)
                    t = ib.reqMktData(contract, '', False, False)
                    ib.sleep(1.5)  # Increased from 0.4 to allow delayed data to arrive
                    price = None
                    # Treat NaN as invalid; fall back bid/ask mid, then previous close
                    try:
                        is_last_valid = (t.last is not None) and not (isinstance(t.last, float) and t.last != t.last)
                    except Exception:
                        is_last_valid = False
                    try:
                        is_bid_valid = (t.bid is not None) and not (isinstance(t.bid, float) and t.bid != t.bid)
                    except Exception:
                        is_bid_valid = False
                    try:
                        is_ask_valid = (t.ask is not None) and not (isinstance(t.ask, float) and t.ask != t.ask)
                    except Exception:
                        is_ask_valid = False
                    try:
                        is_close_valid = (t.close is not None) and not (isinstance(t.close, float) and t.close != t.close)
                    except Exception:
                        is_close_valid = False

                    if is_last_valid:
                        price = float(t.last)
                    elif is_bid_valid and is_ask_valid:
                        price = float((t.bid + t.ask) / 2)
                    elif is_close_valid:
                        price = float(t.close)

                    results[f"{sym}_price"] = price
                    ib.cancelMktData(contract)
                except Exception:
                    results[f"{sym}_price"] = None
            return results
        except Exception:
            # Fallback to local data if IBKR unavailable
            pass

    # --- LOCAL (AlphaVantage merged.jsonl) path (kept for backtesting) ---
    wanted = set(symbols)
    if merged_path is None:
        base_dir = Path(__file__).resolve().parents[1]
        merged_file = base_dir / "data" / "merged.jsonl"
    else:
        merged_file = Path(merged_path)
    if not merged_file.exists():
        return results
    with merged_file.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                doc = json.loads(line)
            except Exception:
                continue
            meta = doc.get("Meta Data", {}) if isinstance(doc, dict) else {}
            sym = meta.get("2. Symbol")
            if sym not in wanted:
                continue
            series = None
            for key, value in doc.items():
                if key.startswith("Time Series"):
                    series = value
                    break
            if not isinstance(series, dict):
                continue
            bar = series.get(today_date)
            if bar is None and series:
                matching_entries = {k: v for k, v in series.items() if k.startswith(today_date)}
                if matching_entries:
                    earliest_time = sorted(matching_entries.keys())[0]
                    bar = matching_entries[earliest_time]
            if isinstance(bar, dict):
                open_val = bar.get("1. buy price")
                try:
                    results[f'{sym}_price'] = float(open_val) if open_val is not None else None
                except Exception:
                    results[f'{sym}_price'] = None
    return results

def get_yesterday_open_and_close_price(today_date: str, symbols: List[str], merged_path: Optional[str] = None) -> Tuple[Dict[str, Optional[float]], Dict[str, Optional[float]]]:
    """从 data/merged.jsonl 中读取指定日期与股票的昨日买入价和卖出价。

    Args:
        today_date: 日期字符串，格式 YYYY-MM-DD，代表今天日期。
        symbols: 需要查询的股票代码列表。
        merged_path: 可选，自定义 merged.jsonl 路径；默认读取项目根目录下 data/merged.jsonl。

    Returns:
        (买入价字典, 卖出价字典) 的元组；若未找到对应日期或标的，则值为 None。
    """
    wanted = set(symbols)
    buy_results: Dict[str, Optional[float]] = {}
    sell_results: Dict[str, Optional[float]] = {}

    if merged_path is None:
        base_dir = Path(__file__).resolve().parents[1]
        merged_file = base_dir / "data" / "merged.jsonl"
    else:
        merged_file = Path(merged_path)

    if not merged_file.exists():
        return buy_results, sell_results

    yesterday_date = get_yesterday_date(today_date)

    with merged_file.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                doc = json.loads(line)
            except Exception:
                continue
            meta = doc.get("Meta Data", {}) if isinstance(doc, dict) else {}
            sym = meta.get("2. Symbol")
            if sym not in wanted:
                continue
            # 查找所有以 "Time Series" 开头的键
            series = None
            for key, value in doc.items():
                if key.startswith("Time Series"):
                    series = value
                    break
            if not isinstance(series, dict):
                continue
            
            # 尝试获取昨日买入价和卖出价 - Try exact match first (daily format)
            bar = series.get(yesterday_date)
            
            # If no exact match and series exists, try hourly format (timestamps starting with date)
            if bar is None and series:
                matching_entries = {k: v for k, v in series.items() if k.startswith(yesterday_date)}
                if matching_entries:
                    # Use earliest timestamp for the date
                    earliest_time = sorted(matching_entries.keys())[0]
                    bar = matching_entries[earliest_time]
            
            if isinstance(bar, dict):
                buy_val = bar.get("1. buy price")  # 买入价字段
                sell_val = bar.get("4. sell price")  # 卖出价字段
                
                try:
                    buy_price = float(buy_val) if buy_val is not None else None
                    sell_price = float(sell_val) if sell_val is not None else None
                    buy_results[f'{sym}_price'] = buy_price
                    sell_results[f'{sym}_price'] = sell_price
                except Exception:
                    buy_results[f'{sym}_price'] = None
                    sell_results[f'{sym}_price'] = None
            else:
                # 如果昨日没有数据，尝试向前查找最近的交易日
                # raise ValueError(f"No data found for {sym} on {yesterday_date}")
                # print(f"No data found for {sym} on {yesterday_date}")
                buy_results[f'{sym}_price'] = None
                sell_results[f'{sym}_price'] = None
                # today_dt = datetime.strptime(today_date, "%Y-%m-%d")
                # yesterday_dt = today_dt - timedelta(days=1)
                # current_date = yesterday_dt
                # found_data = False
                
                # # 最多向前查找5个交易日
                # for _ in range(5):
                #     current_date -= timedelta(days=1)
                #     # 跳过周末
                #     while current_date.weekday() >= 5:
                #         current_date -= timedelta(days=1)
                    
                #     check_date = current_date.strftime("%Y-%m-%d")
                #     bar = series.get(check_date)
                #     if isinstance(bar, dict):
                #         buy_val = bar.get("1. buy price")
                #         sell_val = bar.get("4. sell price")
                        
                #         try:
                #             buy_price = float(buy_val) if buy_val is not None else None
                #             sell_price = float(sell_val) if sell_val is not None else None
                #             buy_results[f'{sym}_price'] = buy_price
                #             sell_results[f'{sym}_price'] = sell_price
                #             found_data = True
                #             break
                #         except Exception:
                #             continue
                
                # if not found_data:
                #     buy_results[f'{sym}_price'] = None
                #     sell_results[f'{sym}_price'] = None

    return buy_results, sell_results

def get_yesterday_profit(today_date: str, yesterday_buy_prices: Dict[str, Optional[float]], yesterday_sell_prices: Dict[str, Optional[float]], yesterday_init_position: Dict[str, float]) -> Dict[str, float]:
    """
    获取今日开盘时持仓的收益，收益计算方式为：(昨日收盘价格 - 昨日开盘价格)*当前持仓。
    Args:
        today_date: 日期字符串，格式 YYYY-MM-DD，代表今天日期。
        yesterday_buy_prices: 昨日开盘价格字典，格式为 {symbol_price: price}
        yesterday_sell_prices: 昨日收盘价格字典，格式为 {symbol_price: price}
        yesterday_init_position: 昨日初始持仓字典，格式为 {symbol: weight}

    Returns:
        {symbol: profit} 的字典；若未找到对应日期或标的，则值为 0.0。
    """
    profit_dict = {}
    
    # 遍历所有股票代码
    for symbol in all_nasdaq_100_symbols:
        symbol_price_key = f'{symbol}_price'
        
        # 获取昨日开盘价和收盘价
        buy_price = yesterday_buy_prices.get(symbol_price_key)
        sell_price = yesterday_sell_prices.get(symbol_price_key)
        
        # 获取昨日持仓权重
        position_weight = yesterday_init_position.get(symbol, 0.0)
        
        # 计算收益：(收盘价 - 开盘价) * 持仓权重
        if buy_price is not None and sell_price is not None and position_weight > 0:
            profit = (sell_price - buy_price) * position_weight
            profit_dict[symbol] = round(profit, 4)  # 保留4位小数
        else:
            profit_dict[symbol] = 0.0
    
    return profit_dict

def get_today_init_position(today_date: str, signature: str) -> Dict[str, float]:
    """
    获取今日开盘时的初始持仓（即文件中上一个交易日代表的持仓）。从../data/agent_data/{signature}/position/position.jsonl中读取。
    如果同一日期有多条记录，选择id最大的记录作为初始持仓。
    
    Args:
        today_date: 日期字符串，格式 YYYY-MM-DD，代表今天日期。
        signature: 模型名称，用于构建文件路径。

    Returns:
        {symbol: weight} 的字典；若未找到对应日期，则返回空字典。
    """
    base_dir = Path(__file__).resolve().parents[1]
    position_file = base_dir / "data" / "agent_data" / signature / "position" / "position.jsonl"

    if not position_file.exists():
        print(f"Position file {position_file} does not exist")
        return {}
    
    yesterday_date = get_yesterday_date(today_date)
    
    max_id = -1
    latest_positions = {}
  
    with position_file.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                doc = json.loads(line)
                record_date = doc.get("date", "")
                # Handle both "YYYY-MM-DD" and "YYYY-MM-DD HH:MM:SS" formats
                record_date_only = record_date.split()[0] if ' ' in record_date else record_date
                yesterday_date_only = yesterday_date.split()[0] if ' ' in yesterday_date else yesterday_date
                
                if record_date_only == yesterday_date_only:
                    current_id = doc.get("id", 0)
                    if current_id > max_id:
                        max_id = current_id
                        latest_positions = doc.get("positions", {})
            except Exception:
                continue
    
    return latest_positions

def get_latest_position(today_date: str, signature: str) -> Tuple[Dict[str, float], int]:
    """
    获取最新持仓。从 ../data/agent_data/{signature}/position/position.jsonl 中读取。
    优先选择当天 (today_date) 中 id 最大的记录；
    若当天无记录，则回退到上一个交易日，选择该日中 id 最大的记录。

    Args:
        today_date: 日期字符串，格式 YYYY-MM-DD，代表今天日期。
        signature: 模型名称，用于构建文件路径。

    Returns:
        (positions, max_id):
          - positions: {symbol: weight} 的字典；若未找到任何记录，则为空字典。
          - max_id: 选中记录的最大 id；若未找到任何记录，则为 -1.
    """
    base_dir = Path(__file__).resolve().parents[1]
    position_file = base_dir / "data" / "agent_data" / signature / "position" / "position.jsonl"

    if not position_file.exists():
        return {}, -1
    
    # 先尝试读取当天记录
    max_id_today = -1
    latest_positions_today: Dict[str, float] = {}
    
    with position_file.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                doc = json.loads(line)
                record_date = doc.get("date", "")
                # Handle both "YYYY-MM-DD" and "YYYY-MM-DD HH:MM:SS" formats
                record_date_only = record_date.split()[0] if ' ' in record_date else record_date
                today_date_only = today_date.split()[0] if ' ' in today_date else today_date
                
                if record_date_only == today_date_only:
                    current_id = doc.get("id", -1)
                    if current_id > max_id_today:
                        max_id_today = current_id
                        latest_positions_today = doc.get("positions", {})
            except Exception:
                continue
    
    if max_id_today >= 0:
        return latest_positions_today, max_id_today

    # 当天没有记录，则回退到上一个交易日
    prev_date = get_yesterday_date(today_date)
    
    max_id_prev = -1
    latest_positions_prev: Dict[str, float] = {}

    with position_file.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                doc = json.loads(line)
                record_date = doc.get("date", "")
                # Handle both "YYYY-MM-DD" and "YYYY-MM-DD HH:MM:SS" formats
                record_date_only = record_date.split()[0] if ' ' in record_date else record_date
                prev_date_only = prev_date.split()[0] if ' ' in prev_date else prev_date
                
                if record_date_only == prev_date_only:
                    current_id = doc.get("id", -1)
                    if current_id > max_id_prev:
                        max_id_prev = current_id
                        latest_positions_prev = doc.get("positions", {})
            except Exception:
                continue
    
    return latest_positions_prev, max_id_prev

def add_no_trade_record(today_date: str, signature: str):
    """
    添加不交易记录。从 ../data/agent_data/{signature}/position/position.jsonl 中前一日最后一条持仓，并更新在今日的position.jsonl文件中。
    Args:
        today_date: 日期字符串，格式 YYYY-MM-DD，代表今天日期。
        signature: 模型名称，用于构建文件路径。

    Returns:
        None
    """
    save_item = {}
    # Get yesterday's final position to carry forward (not today's which might be empty/partial)
    yesterday_date = get_yesterday_date(today_date)
    yesterday_position, yesterday_action_id = get_latest_position(yesterday_date, signature)
    
    # Get today's max ID to increment from
    _, today_max_id = get_latest_position(today_date, signature)
    next_id = max(yesterday_action_id, today_max_id) + 1
    
    save_item["date"] = today_date
    save_item["id"] = next_id
    save_item["this_action"] = {"action":"no_trade","symbol":"","amount":0}
    
    save_item["positions"] = yesterday_position
    base_dir = Path(__file__).resolve().parents[1]
    position_file = base_dir / "data" / "agent_data" / signature / "position" / "position.jsonl"

    with position_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(save_item) + "\n")
    return 

if __name__ == "__main__":
    today_date = get_config_value("TODAY_DATE")
    signature = get_config_value("SIGNATURE")
    if signature is None:
        raise ValueError("SIGNATURE environment variable is not set")
    print(today_date, signature)
    yesterday_date = get_yesterday_date(today_date)
    print(yesterday_date)
    # today_buy_price = get_open_prices(today_date, all_nasdaq_100_symbols)
    # print(today_buy_price)
    # yesterday_buy_prices, yesterday_sell_prices = get_yesterday_open_and_close_price(today_date, all_nasdaq_100_symbols)
    # print(yesterday_sell_prices)
    # today_init_position = get_today_init_position(today_date, signature='qwen3-max')
    # print(today_init_position)
    # latest_position, latest_action_id = get_latest_position('2025-10-24', 'qwen3-max')
    # print(latest_position, latest_action_id)
    latest_position, latest_action_id = get_latest_position('2025-10-16 16:00:00', 'test')
    print(latest_position, latest_action_id)
    
    # yesterday_profit = get_yesterday_profit(today_date, yesterday_buy_prices, yesterday_sell_prices, today_init_position)
    # # print(yesterday_profit)
    # add_no_trade_record(today_date, signature)
