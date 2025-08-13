#!/usr/bin/env python3
"""
Reconstructed live_backtest_WORKING.py

Purpose:
- Lightweight on-demand "live" backtest / signal preview using current data.
- Uses existing support/resistance logic (signal_utils) + tickers_config.
- For each enabled ticker, loads local cached daily CSV (e.g. AAPL_data.csv). If missing, pulls from yfinance.
- Computes support / resistance based signals for configured (p, tw) pairs (first valid) and extracts the next actionable signal date (today or tomorrow).
- Outputs BUY/SELL/SHORT/COVER candidates for today.

Usage:
  python live_backtest_WORKING.py              # summary for all tickers
  python live_backtest_WORKING.py --ticker AAPL # single ticker
  python live_backtest_WORKING.py --export todays_signals.json

Notes:
- This is a reconstruction; original file not present in current git history.
- Extend as needed (add P/TW sweeps, performance stats, etc.).

"""
import argparse
import json
import os
from datetime import datetime
import pandas as pd
import yfinance as yf

from tickers_config import tickers
from config import P_RANGE, TW_RANGE
from signal_utils import (
    calculate_support_resistance,
    assign_long_signals_extended,
    assign_short_signals_extended,
)

DATE_FMT = "%Y-%m-%d"
TODAY = datetime.now().strftime(DATE_FMT)

# ---------- Data Loading ----------

def load_price_data(symbol: str) -> pd.DataFrame:
    fn = f"{symbol}_data.csv"
    if os.path.exists(fn):
        try:
            df = pd.read_csv(fn, parse_dates=[0])
            # Try to detect column naming variants
            cols = {c.lower(): c for c in df.columns}
            for required in ["open","high","low","close"]:
                if required not in cols:
                    raise ValueError("Missing column " + required)
            # Normalize
            df.rename(columns={
                cols['open']: 'Open',
                cols['high']: 'High',
                cols['low']: 'Low',
                cols['close']: 'Close'
            }, inplace=True)
            df.rename(columns={df.columns[0]: 'Date'}, inplace=True)
            df.sort_values('Date', inplace=True)
            df.set_index('Date', inplace=True)
            return df
        except Exception:
            pass
    # Fallback yfinance (1y)
    df = yf.Ticker(symbol).history(period='1y')
    if df.empty:
        raise RuntimeError(f"No data for {symbol}")
    df = df[['Open','High','Low','Close']].copy()
    df.reset_index(inplace=True)
    df.rename(columns={'Date':'Date'}, inplace=True)
    df.set_index('Date', inplace=True)
    return df

# ---------- Signal Extraction ----------

def build_signals(symbol: str, df: pd.DataFrame, p: int, tw: int, cfg: dict):
    price_col = "Open" if cfg.get("trade_on","Close").lower()=="open" else "Close"
    support, resistance = calculate_support_resistance(df, p, tw, price_col=price_col)
    ext_long = assign_long_signals_extended(support, resistance, df, tw)
    ext_short = assign_short_signals_extended(support, resistance, df, tw)
    return ext_long, ext_short


def extract_today_actions(symbol: str, ext_long: pd.DataFrame, ext_short: pd.DataFrame):
    actions = []
    # LONG actions
    if not ext_long.empty:
        for _, r in ext_long.iterrows():
            act = r.get('Long Action')
            d = r.get('Long Date detected')
            if pd.notna(d) and str(d)[:10] == TODAY and act in ('buy','sell'):
                actions.append({
                    'ticker': symbol,
                    'strategy': 'LONG',
                    'action': act.upper() if act=='buy' else 'SELL',
                    'date': TODAY,
                    'p_param': None,
                    'tw_param': None,
                    'trade_on': 'CLOSE'
                })
    # SHORT actions
    if not ext_short.empty:
        for _, r in ext_short.iterrows():
            act = r.get('Short Action')
            d = r.get('Short Date detected')
            if pd.notna(d) and str(d)[:10] == TODAY and act in ('short','cover'):
                actions.append({
                    'ticker': symbol,
                    'strategy': 'SHORT',
                    'action': 'SHORT' if act=='short' else 'COVER',
                    'date': TODAY,
                    'p_param': None,
                    'tw_param': None,
                    'trade_on': 'CLOSE'
                })
    return actions

# ---------- Main Routine ----------

def process_symbol(symbol: str):
    cfg = tickers.get(symbol)
    if not cfg:
        return {'symbol': symbol, 'error': 'Not in config'}
    try:
        df = load_price_data(symbol)
    except Exception as e:
        return {'symbol': symbol, 'error': f'data load failed: {e}'}

    # Pick first p, tw that yields any signal window (simple heuristic)
    chosen_p = None
    chosen_tw = None
    ext_long = pd.DataFrame()
    ext_short = pd.DataFrame()
    for p in P_RANGE:
        for tw in TW_RANGE:
            try:
                el, es = build_signals(symbol, df, p, tw, cfg)
                if (not el.empty) or (not es.empty):
                    chosen_p, chosen_tw = p, tw
                    ext_long, ext_short = el, es
                    break
            except Exception:
                continue
        if chosen_p:
            break

    if chosen_p is None:
        return {'symbol': symbol, 'error': 'no signals produced'}

    todays = extract_today_actions(symbol, ext_long, ext_short)
    return {
        'symbol': symbol,
        'p': chosen_p,
        'tw': chosen_tw,
        'today_signals': todays,
        'long_rows': len(ext_long),
        'short_rows': len(ext_short)
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ticker', help='Single ticker')
    ap.add_argument('--export', help='Export today signals JSON file')
    args = ap.parse_args()

    symbols = [args.ticker] if args.ticker else list(tickers.keys())
    summary = []
    today_all = []

    print(f"LIVE BACKTEST (reconstructed) DATE={TODAY}")
    for sym in symbols:
        res = process_symbol(sym)
        summary.append(res)
        for s in res.get('today_signals', []):
            today_all.append(s)

    # Console output
    for res in summary:
        if 'error' in res:
            print(f"{res['symbol']}: ERROR - {res['error']}")
            continue
        print(f"{res['symbol']}: p={res['p']} tw={res['tw']} long_rows={res['long_rows']} short_rows={res['short_rows']}")
        if res['today_signals']:
            for s in res['today_signals']:
                print(f"  -> {s['action']} {s['strategy']} (trade_on {s['trade_on']})")
        else:
            print("  (no today signals)")

    if args.export:
        out = {'date': TODAY, 'signals': today_all}
        with open(args.export, 'w') as f:
            json.dump(out, f, indent=2)
        print(f"Exported {len(today_all)} signals to {args.export}")

if __name__ == '__main__':
    main()
