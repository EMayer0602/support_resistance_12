"""Support/Resistance signal generation for crypto pairs (simplified)."""
from __future__ import annotations
from typing import List, Dict, Any
import pandas as pd
from .crypto_config import P_RANGE, TW_RANGE


def detect_levels(df: pd.DataFrame, p: int, tw: int) -> List[Dict[str, Any]]:
    sigs: List[Dict[str, Any]] = []
    for i in range(p, len(df)):
        window = df.iloc[i-p:i]
        high_ok = df.high.iloc[i] >= window.high.max()
        low_ok = df.low.iloc[i] <= window.low.min()
        if high_ok:
            sigs.append({"timestamp": int(df.index[i].value/1e6), "action": "SELL", "p_param": p, "tw_param": tw, "price": float(df.close.iloc[i])})
        if low_ok:
            sigs.append({"timestamp": int(df.index[i].value/1e6), "action": "BUY", "p_param": p, "tw_param": tw, "price": float(df.close.iloc[i])})
    return sigs


def generate_signals(candles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not candles:
        return []
    df = pd.DataFrame(candles)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df.set_index("timestamp", inplace=True)
    out: List[Dict[str, Any]] = []
    for p in P_RANGE:
        for tw in TW_RANGE:
            out.extend(detect_levels(df, p, tw))
    return out
