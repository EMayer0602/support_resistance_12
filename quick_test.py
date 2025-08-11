import pandas as pd
from signal_utils import calculate_support_resistance, assign_long_signals_extended

# Load test data
df = pd.read_csv('AAPL_data.csv')
df.set_index('date', inplace=True)
df.index = pd.to_datetime(df.index)

print("Loaded data")

# Test
support, resistance = calculate_support_resistance(df, 5, 5)
print(f"Support type: {type(support)}")

signals = assign_long_signals_extended(support, resistance, df, 5, interval="1D")  
print(f"Signals type: {type(signals)}")

if isinstance(signals, pd.DataFrame):
    print("OK - DataFrame")
else:
    print(f"ERROR - {type(signals)}")
