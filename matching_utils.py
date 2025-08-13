"""Utility functions to normalize trades produced by simulation.

The simulation returns a list of trade dicts with keys depending on the
direction (long vs short). This module provides a helper `match_trades`
that normalizes these into a consistent list that can be rendered or
further analyzed.
"""
from typing import List, Dict

def match_trades(trades: List[Dict], side: str = "long") -> List[Dict]:
    """Normalize trade dictionaries into a common schema.

    Each element from simulate_trades_compound_extended already represents
    a completed round-trip. We just map the fields to a unified naming.
    Returns list of dicts with keys: entry_date, exit_date, entry_price,
    exit_price, shares, fee, pnl.
    """
    normalized = []
    if not trades or side not in ("long", "short"):
        return normalized

    for t in trades:
        if side == "long":
            entry_date = t.get("buy_date")
            exit_date = t.get("sell_date")
            entry_price = t.get("buy_price")
            exit_price = t.get("sell_price")
        else:
            entry_date = t.get("short_date")  # short entry
            exit_date = t.get("cover_date")  # cover exit
            entry_price = t.get("short_price")
            exit_price = t.get("cover_price")

        normalized.append({
            "entry_date": entry_date,
            "exit_date": exit_date,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "shares": t.get("shares"),
            "fee": t.get("fee"),
            "pnl": t.get("pnl"),
        })

    return normalized
