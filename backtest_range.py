"""Utility helpers to standardize backtest data slicing across scripts."""
from __future__ import annotations
import pandas as pd
from config import trade_years, backtesting_begin, backtesting_end

def restrict_df_for_backtest(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    working = df.copy()
    # Apply year-based restriction
    if trade_years and trade_years > 0:
        cutoff = working.index.max() - pd.Timedelta(days=int(trade_years * 365))
        working = working[working.index >= cutoff]
    # Apply percentage slice
    n = len(working)
    start_idx = int(n * backtesting_begin / 100)
    end_idx = int(n * backtesting_end / 100)
    working = working.iloc[start_idx:end_idx]
    return working
