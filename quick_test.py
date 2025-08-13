import pandas as pd
from signal_utils import calculate_support_resistance, assign_long_signals_extended
from tickers_config import tickers

# Load test data
symbol = 'AAPL'
df = pd.read_csv(f'{symbol}_data.csv')
df.set_index(df.columns[0], inplace=True)
df.index = pd.to_datetime(df.index)

print("Loaded data")

# Test
cfg = tickers.get(symbol, {})
price_col = "Open" if cfg.get("trade_on", "Close").lower() == "open" else "Close"
support, resistance = calculate_support_resistance(df, 5, 5, price_col=price_col)
print(f"Support type: {type(support)}")

signals = assign_long_signals_extended(support, resistance, df, 5, interval="1D")  
print(f"Signals type: {type(signals)}")

if isinstance(signals, pd.DataFrame):
    print("OK - DataFrame")
else:
    print(f"ERROR - {type(signals)}")
