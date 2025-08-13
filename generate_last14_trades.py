#!/usr/bin/env python3
"""
Generate rolling last-14-trading-days trade summary using existing extended signal CSVs.

This DOES NOT re-run the computationally heavy backtest. It reuses the
already generated extended_long_*.csv and extended_short_*.csv files plus
<symbol>_data.csv daily price files.

Output: trades_last14_days.json (date -> list of trade dicts)
Each date (including those with no trades) over the last 14 trading days
(inclusive of today if a trading day, else last trading day) is present.

Trade dict fields: symbol, side (BUY/SELL/SHORT/COVER), price, source (LONG/SHORT)
Price is taken from the configured trade_on (Open/Close) column of the
symbol's daily data file for that date. If price missing -> None.
"""
import os
import json
from datetime import datetime, timedelta
import pandas as pd
from tickers_config import tickers

US_HOLIDAYS_2025 = {
    "2025-01-01","2025-01-20","2025-02-17","2025-04-18","2025-05-26",
    "2025-06-19","2025-07-04","2025-09-01","2025-11-27","2025-12-25"
}

def is_trading_day(d: datetime) -> bool:
    if d.weekday() >= 5:
        return False
    if d.strftime('%Y-%m-%d') in US_HOLIDAYS_2025:
        return False
    return True

def get_recent_trading_days(n: int = 14) -> list[str]:
    days = []
    cur = datetime.now()
    # If today not trading day, back up to last trading day
    while not is_trading_day(cur):
        cur -= timedelta(days=1)
    while len(days) < n:
        if is_trading_day(cur):
            days.append(cur.strftime('%Y-%m-%d'))
        cur -= timedelta(days=1)
    return sorted(days)  # chronological

def load_daily_prices(symbol: str) -> pd.DataFrame | None:
    fn = f"{symbol}_data.csv"
    if not os.path.exists(fn):
        return None
    try:
        df = pd.read_csv(fn, parse_dates=['Date'])
    except Exception:
        # Some files may use lowercase 'date'
        try:
            df = pd.read_csv(fn, parse_dates=['date'])
            df.rename(columns={'date':'Date'}, inplace=True)
        except Exception:
            return None
    df.columns = [c.capitalize() for c in df.columns]
    df.set_index('Date', inplace=True)
    return df

def extract_trades_for_symbol(days: list[str], symbol: str, cfg: dict) -> dict[str, list]:
    trades = {d: [] for d in days}
    # LONG
    long_fn = f"extended_long_{symbol}.csv"
    if os.path.exists(long_fn):
        try:
            ext_long = pd.read_csv(long_fn, parse_dates=['Long Date detected'])
        except Exception:
            ext_long = pd.DataFrame()
        if not ext_long.empty and 'Long Action' in ext_long.columns:
            for _, row in ext_long.iterrows():
                action = str(row.get('Long Action','')).lower()
                trade_date = row.get('Long Date detected')
                if pd.isna(trade_date):
                    continue
                d_str = trade_date.strftime('%Y-%m-%d')
                if d_str in trades and action in ('buy','sell') and cfg.get('long', False):
                    trades[d_str].append({'symbol': symbol,'side': action.upper(),'source':'LONG'})
    # SHORT
    short_fn = f"extended_short_{symbol}.csv"
    if os.path.exists(short_fn):
        try:
            ext_short = pd.read_csv(short_fn, parse_dates=['Short Date detected'])
        except Exception:
            ext_short = pd.DataFrame()
        if not ext_short.empty and 'Short Action' in ext_short.columns:
            for _, row in ext_short.iterrows():
                action = str(row.get('Short Action','')).lower()
                trade_date = row.get('Short Date detected')
                if pd.isna(trade_date):
                    continue
                d_str = trade_date.strftime('%Y-%m-%d')
                if d_str in trades and action in ('short','cover') and cfg.get('short', False):
                    side = 'SHORT' if action == 'short' else 'COVER'
                    trades[d_str].append({'symbol': symbol,'side': side,'source':'SHORT'})
    return trades

def enrich_prices(trade_map: dict[str, list], symbol: str, cfg: dict, daily_df):
    if daily_df is None or daily_df.empty:
        return
    col = 'Open' if cfg.get('trade_on','Open').lower() == 'open' else 'Close'
    for d, lst in trade_map.items():
        if not lst:
            continue
        try:
            # daily_df index is Timestamp
            ts = pd.Timestamp(d)
            if ts in daily_df.index:
                px = daily_df.at[ts, col]
            else:
                # forward fill attempt via searchsorted
                idx = daily_df.index.searchsorted(ts)
                if idx < len(daily_df.index):
                    px = daily_df.iloc[idx][col]
                else:
                    px = None
        except Exception:
            px = None
        for tr in lst:
            tr['price'] = float(px) if px is not None and pd.notna(px) else None
            tr['trade_on'] = col.upper()

def build_last14():
    days = get_recent_trading_days(14)
    aggregate = {d: [] for d in days}
    for symbol, cfg in tickers.items():
        symbol_trades = extract_trades_for_symbol(days, symbol, cfg)
        daily_df = load_daily_prices(symbol)
        enrich_prices(symbol_trades, symbol, cfg, daily_df)
        # merge
        for d in days:
            aggregate[d].extend(symbol_trades[d])
    out_file = 'trades_last14_days.json'
    with open(out_file, 'w') as f:
        json.dump(aggregate, f, indent=2)
    print(f"Wrote {out_file} with {len(aggregate)} days (last trading day window).")
    # Quick summary
    for d in days:
        print(f"{d}: {len(aggregate[d])} trades")

if __name__ == '__main__':
    build_last14()
