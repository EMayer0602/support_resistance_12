"""Crypto trading configuration for Bitpanda (placeholder).
Adjust before live use.
"""

EXCHANGE = "bitpanda"
NETWORK = "mainnet"  # or testnet if supported

# Pairs to trade (quote in EUR or USDT depending on account)
PAIRS = [
    "BTC/EUR",
    "ETH/EUR",
]

# Capital allocation per pair (in quote currency)
PAIR_CAPITAL = {
    "BTC/EUR": 1000.0,
    "ETH/EUR": 800.0,
}

# Risk controls
MAX_OPEN_POSITIONS = 4
MAX_NOTIONAL_PER_TRADE = 1500.0
TAKER_FEE = 0.0015  # 0.15%
MAKER_FEE = 0.0010  # 0.10%

# Candle timeframe (fetch & signal interval)
TIMEFRAME = "1m"  # or 5m/15m
FETCH_LIMIT = 500  # number of candles to pull

# Support/Resistance parameters (reuse from equities style)
P_RANGE = [3,4,5,6,7]
TW_RANGE = [1,2,3]

# Execution settings
SLIPPAGE_ALLOW = 0.001  # 0.1%
RETRY_ATTEMPTS = 3
RETRY_DELAY_SEC = 2

# File paths
DATA_DIR = "crypto_data"
STATE_FILE = "crypto_state.json"
POSITIONS_FILE = "crypto_positions.json"
