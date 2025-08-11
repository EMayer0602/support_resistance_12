from ib_insync import Stock

tickers = {
    "AAPL": {"symbol": "AAPL", "conID": 265598, "long": True,  "short": True,  "initialCapitalLong": 1000, "initialCapitalShort": 1000, "order_round_factor": 1, "trade_on": "Close"},
    "GOOGL": {"symbol": "GOOGL", "conID": 208813720, "long": True,  "short": True,  "initialCapitalLong": 1200, "initialCapitalShort": 1200, "order_round_factor": 1, "trade_on": "Close"},
    "NVDA": {"symbol": "NVDA", "conID": 4815747, "long": True,  "short": False, "initialCapitalLong": 1800, "initialCapitalShort": 1500, "order_round_factor": 1, "trade_on": "Close"},
    "MSFT": {"symbol": "MSFT", "conID": 272093, "long": True,  "short": True,  "initialCapitalLong": 1100, "initialCapitalShort": 1100, "order_round_factor": 1, "trade_on": "Close"},
    "META": {"symbol": "META", "conID": 11263881, "long": True,  "short": True,  "initialCapitalLong": 1000, "initialCapitalShort": 1000, "order_round_factor": 1, "trade_on": "Close"},
    "AMD":  {"symbol": "AMD",  "conID": 4391, "long": True,  "short": True,  "initialCapitalLong": 1000, "initialCapitalShort": 1000, "order_round_factor": 1, "trade_on": "Close"},
    "QBTS": {"symbol": "QBTS", "conID": 532663595, "long": True,  "short": False, "initialCapitalLong": 1000, "initialCapitalShort": 100, "order_round_factor": 1, "trade_on": "Close"},
    "TSLA": {"symbol": "TSLA", "conID": 76792991, "long": True,  "short": True,  "initialCapitalLong": 1000, "initialCapitalShort": 1000, "order_round_factor": 1, "trade_on": "Close"},
    "MRNA": {"symbol": "MRNA", "conID": 41450682, "long": True,  "short": True,  "initialCapitalLong": 1000, "initialCapitalShort": 1000, "order_round_factor": 1, "trade_on": "Close"},
    "NFLX": {"symbol": "NFLX", "conID": 213276, "long": True,  "short": False, "initialCapitalLong": 1500, "initialCapitalShort": 1500, "order_round_factor": 1, "trade_on": "Close"},
    "AMZN": {"symbol": "AMZN", "conID": 3691937, "long": True,  "short": True,  "initialCapitalLong": 1000, "initialCapitalShort": 1000, "order_round_factor": 1, "trade_on": "Close"},
    "INTC": {"symbol": "INTC", "conID": 1977552, "long": True,  "short": True,  "initialCapitalLong": 1000, "initialCapitalShort": 1000, "order_round_factor": 1, "trade_on": "Close"},
    "BRRR": {"symbol": "BRRR", "conID": 582852809, "long": True,  "short": True,  "initialCapitalLong": 1000, "initialCapitalShort": 1000, "order_round_factor": 1, "trade_on": "Close"},
    "QUBT": {"symbol": "QUBT", "conID": 380357230, "long": True,  "short": False, "initialCapitalLong": 2000, "initialCapitalShort": 1000, "order_round_factor": 10, "trade_on": "Close"}
}
