#!/usr/bin/env python3

import pandas as pd
import numpy as np
from signal_utils import assign_long_signals_extended, assign_short_signals_extended

# Create a simple test dataset
dates = pd.date_range('2024-01-01', periods=100, freq='D')
test_data = pd.DataFrame({
    'Date': dates,
    'Open': np.random.randn(100).cumsum() + 100,
    'High': np.random.randn(100).cumsum() + 105,
    'Low': np.random.randn(100).cumsum() + 95,
    'Close': np.random.randn(100).cumsum() + 100
})
test_data.set_index('Date', inplace=True)

print("Testing assign_long_signals_extended...")
try:
    long_signals = assign_long_signals_extended([95, 90], [110, 115], test_data, 5)
    print(f"Long signals type: {type(long_signals)}")
    print(f"Long signals shape: {long_signals.shape}")
    print("✓ assign_long_signals_extended works correctly")
except Exception as e:
    print(f"✗ Error in assign_long_signals_extended: {e}")

print("\nTesting assign_short_signals_extended...")
try:
    short_signals = assign_short_signals_extended([95, 90], [110, 115], test_data, 5)
    print(f"Short signals type: {type(short_signals)}")
    print(f"Short signals shape: {short_signals.shape}")
    print("✓ assign_short_signals_extended works correctly")
except Exception as e:
    print(f"✗ Error in assign_short_signals_extended: {e}")

print("\nAll tests completed!")
