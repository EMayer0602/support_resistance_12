#!/usr/bin/env python3
"""
Debug script to test signal generation
"""
import pandas as pd
import numpy as np
from signal_utils import (
    calculate_support_resistance,
    assign_long_signals_extended,
    assign_short_signals_extended,
)
from tickers_config import tickers

# Load some test data
try:
    df = pd.read_csv('AAPL_data.csv')
    df.set_index(df.columns[0], inplace=True)  # Assume first column is date
    df.index = pd.to_datetime(df.index)
    
    print(f"Loaded {len(df)} bars of AAPL data")
    print(f"Columns: {list(df.columns)}")
    print(f"Data types: {df.dtypes}")
    print(f"First few rows:")
    print(df.head())
    
    # Use the ticker inferred from filename (before first underscore)
    symbol = 'AAPL'
    cfg = tickers.get(symbol, {})
    # Test with small parameters
    p, tw = 5, 5

    print(f"\nTesting calculate_support_resistance with p={p}, tw={tw}")
    price_col = "Open" if cfg.get("trade_on", "Close").lower() == "open" else "Close"
    support, resistance = calculate_support_resistance(df, p, tw, price_col=price_col)
    
    print(f"Support type: {type(support)}")
    print(f"Resistance type: {type(resistance)}")
    print(f"Support length: {len(support) if hasattr(support, '__len__') else 'No length'}")
    print(f"Resistance length: {len(resistance) if hasattr(resistance, '__len__') else 'No length'}")
    
    if isinstance(support, pd.Series):
        print("Support is Series - Good!")
        print(f"Support head: {support.head()}")
    else:
        print(f"Support is NOT Series: {support}")
        
    if isinstance(resistance, pd.Series):
        print("Resistance is Series - Good!")
        print(f"Resistance head: {resistance.head()}")
    else:
        print(f"Resistance is NOT Series: {resistance}")
    
    print(f"\nTesting assign_long_signals_extended")
    try:
        signals_long = assign_long_signals_extended(support, resistance, df, tw, interval="1D")
        print(f"Long signals type: {type(signals_long)}")
        print(f"Long signals length: {len(signals_long) if hasattr(signals_long, '__len__') else 'No length'}")

        if isinstance(signals_long, pd.DataFrame):
            print("Long signals is DataFrame - Good!")
            print(f"Columns: {list(signals_long.columns)}")
            print(f"Head:\n{signals_long.head()}")
        else:
            print(f"Long signals is NOT DataFrame: {signals_long}")

    except Exception as e:
        print(f"Error in assign_long_signals_extended: {e}")
        import traceback
        traceback.print_exc()
        
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
