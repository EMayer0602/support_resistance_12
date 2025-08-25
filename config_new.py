# 📊 TRADING CONFIGURATION
# Support/Resistance Strategy Parameters

# 💰 CAPITAL SETTINGS
INITIAL_CAPITAL = 50000    # Total starting capital in USD
DEFAULT_COMMISSION_RATE = 0.0018   # 0.18% commission per trade
MIN_COMMISSION = 1.0       # Minimum commission in USD
ORDER_SIZE = 100           # Default order size (overridden by ticker config)
ORDER_ROUND_FACTOR = 0.01  # Global rounding factor (overridden by ticker)

# 📅 BACKTEST TIME SETTINGS
trade_years = 1            # Backtest period in years (1 = 1 year)
# Alternative periods:
# trade_years = 0.5        # 6 months  
# trade_years = 0.25       # 3 months
# trade_years = 1/12       # 1 month
# trade_years = 2          # 2 years
# trade_years = 5          # 5 years

# 🧪 BACKTEST DATA RANGE (percentage of available data)
backtesting_begin = 25     # Start at 25% of data (skip early data)
backtesting_end = 95       # End at 95% of data (reserve recent for validation)

# � DATA SLICE BEHAVIOR FLAGS
# If True, ignore backtesting_begin/end and trade_years restrictions for simulation/equity generation
USE_FULL_DATA = False
# If True, apply percentage slice ONLY for parameter optimization; simulation/equity runs on full (recent) dataset
SLICE_FOR_OPTIMIZATION_ONLY = True
# If True, force any open positions to be flattened on the final available bar (ensures equity[-1] == final_capital)
FORCE_FLAT_AT_END = True

# Console verbosity for extended signals (prices will be auto-filled where possible)
EXTENDED_VERBOSE = True

# �📈 SIGNAL PARAMETERS (ranges for optimization)
P_RANGE = [3, 4, 5, 6, 7, 8, 9, 10, 11, 12]        # Support/resistance period parameters
TW_RANGE = [1, 2, 3, 4, 5, 6]       # Time window parameters
FORCE_TW = None  # Set to an integer (e.g., 1) to force trade window; None disables forcing

# 🧪 OPTIMIZATION STABILITY / PARSIMONY
# Minimum number of trades required for a (p, tw) candidate to be considered stable
OPT_MIN_TRADES = 5
# Percentage tolerance (e.g., 0.02 = 2%) within best final_cap to consider alternative candidates
OPT_TOLERANCE_PCT = 0.02
# If True, among candidates within tolerance pick the smallest tw (parsimony preference)
OPT_PARSIMONY_TW = True
# If True, and parsimony tie persists, pick the candidate with more trades (stability preference)
OPT_PREFER_MORE_TRADES = True
# Set >0 to penalize high trade_window (regularization): effective_score = final_cap - OPT_TW_PENALTY * tw
OPT_TW_PENALTY = 0.0

# 🎯 TRADING EXECUTION SETTINGS
LIMIT_ORDER_OFFSET = 0.01  # Price offset for limit orders (1 cent)
MAX_POSITION_SIZE = 0.1    # Maximum position size as % of capital (10%)
STOP_LOSS_PCT = 0.05       # Stop loss percentage (5%)
TAKE_PROFIT_PCT = 0.10     # Take profit percentage (10%)
USE_STRATEGY_EXITS_ONLY = False  # Use SL/TP; set True to ignore SL/TP and rely on signals

# ⏰ TRADING TIMING (Eastern Time)
MARKET_OPEN_TIME = "09:30"
MARKET_CLOSE_TIME = "16:00"
OPEN_TRADE_DELAY = 5       # Minutes after market open to trade (was 10)
CLOSE_TRADE_ADVANCE = 30   # Minutes before market close to trade (was 15)

# 📊 IB CONNECTION SETTINGS
IB_PAPER_PORT = 7497       # Paper trading port
IB_LIVE_PORT = 7496        # Live trading port
IB_HOST = '127.0.0.1'      # IB Gateway/TWS host
IB_CLIENT_ID = 1           # Client ID for connection
OPEN_SESSION_GRACE_MIN = 60  # Grace (minutes) after open trade time
CLOSE_SESSION_GRACE_MIN = 2   # Grace (minutes) after close
IB_MAX_CONNECT_RETRIES = 3
IB_RETRY_BACKOFF_SEC = 3
IB_HEARTBEAT_SEC = 30
IB_RECONNECT_ON_TIMEOUT = True

# 🔧 PERFORMANCE SETTINGS
MAX_WORKERS = 4            # Number of parallel workers for optimization
CACHE_RESULTS = True       # Cache backtest results
VERBOSE_LOGGING = False    # Detailed logging output

# 📝 FILE PATHS
RESULTS_DIR = 'results'
CHARTS_DIR = 'charts'  
DATA_DIR = 'data'
PORTFOLIO_FILE = 'portfolio_positions.json'
