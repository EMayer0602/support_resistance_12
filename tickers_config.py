from ib_insync import Stock

tickers = {
    "AAPL": {"symbol": "AAPL", "contract": Stock("AAPL", "SMART", "USD"), "long": True,  "short": True,  "initialCapitalLong": 1000, "initialCapitalShort": 1000, "order_round_factor": 1, "trade_on": "open"},
    "GOOGL": {"symbol": "GOOGL", "contract": Stock("GOOGL", "SMART", "USD"), "long": True,  "short": True,  "initialCapitalLong": 1200, "initialCapitalShort": 1200, "order_round_factor": 1, "trade_on": "open"},
    "NVDA": {"symbol": "NVDA", "contract": Stock("NVDA", "SMART", "USD"), "long": True,  "short": False, "initialCapitalLong": 1800, "initialCapitalShort": 1500, "order_round_factor": 1, "trade_on": "open"},
    "MSFT": {"symbol": "MSFT", "contract": Stock("MSFT", "SMART", "USD"), "long": True,  "short": True,  "initialCapitalLong": 1100, "initialCapitalShort": 1100, "order_round_factor": 1, "trade_on": "open"},
    "META": {"symbol": "META", "contract": Stock("META", "SMART", "USD"), "long": True,  "short": True,  "initialCapitalLong": 1000, "initialCapitalShort": 1000, "order_round_factor": 1, "trade_on": "open"},
    "AMD":  {"symbol": "AMD",  "contract": Stock("AMD", "SMART", "USD"), "long": True,  "short": True,  "initialCapitalLong": 1000, "initialCapitalShort": 1000, "order_round_factor": 1, "trade_on": "open"},
    "QBTS": {"symbol": "QBTS", "contract": Stock("QBTS", "SMART", "USD"), "long": True,  "short": False, "initialCapitalLong": 1000, "initialCapitalShort": 100, "order_round_factor": 1, "trade_on": "open"},
    "TSLA": {"symbol": "TSLA", "contract": Stock("TSLA", "SMART", "USD"), "long": True,  "short": True,  "initialCapitalLong": 1000, "initialCapitalShort": 1000, "order_round_factor": 1, "trade_on": "open"},
    "MRNA": {"symbol": "MRNA", "contract": Stock("MRNA", "SMART", "USD"), "long": True,  "short": True,  "initialCapitalLong": 1000, "initialCapitalShort": 1000, "order_round_factor": 1, "trade_on": "open"},
    "NFLX": {"symbol": "NFLX", "contract": Stock("NFLX", "SMART", "USD"), "long": True,  "short": False, "initialCapitalLong": 1500, "initialCapitalShort": 1500, "order_round_factor": 1, "trade_on": "open"},
    "AMZN": {"symbol": "AMZN", "contract": Stock("AMZN", "SMART", "USD"), "long": True,  "short": True,  "initialCapitalLong": 1000, "initialCapitalShort": 1000, "order_round_factor": 1, "trade_on": "open"},
    "INTC": {"symbol": "INTC", "contract": Stock("INTC", "SMART", "USD"), "long": True,  "short": True,  "initialCapitalLong": 1000, "initialCapitalShort": 1000, "order_round_factor": 1, "trade_on": "open"},
    "BRRR": {"symbol": "BRRR", "contract": Stock("BRRR", "SMART", "USD"), "long": True,  "short": True,  "initialCapitalLong": 1000, "initialCapitalShort": 1000, "order_round_factor": 1, "trade_on": "open"},
    "QUBT": {"symbol": "QUBT", "contract": Stock("QUBT", "SMART", "USD"), "long": True,  "short": False, "initialCapitalLong": 2000, "initialCapitalShort": 1000, "order_round_factor": 10, "trade_on": "open"}
}
