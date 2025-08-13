#!/usr/bin/env python3
"""Compare final capital when executing long strategy on Open vs Close for each ticker.

For every ticker in tickers_config:
 1. Load existing <TICKER>_data.csv (no IB connection required).
 2. For trade_on in ["Open", "Close"]:
    - Copy ticker config overriding trade_on.
    - Optimize (p, tw) with berechne_best_p_tw_long for that mode.
    - Recompute extended long signals using those parameters.
    - Simulate trades to obtain final capital.
 3. Store results in a summary DataFrame and write compare_open_vs_close.csv.

Outputs:
  compare_open_vs_close.csv with columns:
    ticker, initial_capital, final_cap_open, p_open, tw_open, trades_open,
    final_cap_close, p_close, tw_close, trades_close, diff_open_minus_close, pct_diff

Notes:
 - Focuses on LONG side only ("buy" request context).
 - Each mode re-optimizes its own parameters so comparison reflects achievable performance
   under that execution assumption. If you want a fair execution-only delta, fix p/tw to one mode.
"""
import os
import pandas as pd
from copy import deepcopy

from tickers_config import tickers
from signal_utils import (
    calculate_support_resistance,
    assign_long_signals_extended,
    update_level_close_long,
)
from backtesting_core import berechne_best_p_tw_long
from simulation_utils import simulate_trades_compound_extended
from config import DEFAULT_COMMISSION_RATE, MIN_COMMISSION, ORDER_ROUND_FACTOR, backtesting_begin, backtesting_end

RESULT_CSV = "compare_open_vs_close.csv"

def load_price_df(ticker: str) -> pd.DataFrame | None:
    fn = f"{ticker}_data.csv"
    if not os.path.exists(fn):
        print(f"WARN missing data file {fn}, skipping")
        return None
    try:
        df = pd.read_csv(fn, parse_dates=[0])
        # Normalize first column name to 'date'
        if df.columns[0].lower() != 'date':
            df.rename(columns={df.columns[0]: 'date'}, inplace=True)
        # Standardize OHLC capitalization
        rename_map = {}
        for c in df.columns:
            cl = c.lower()
            if cl in ('open','high','low','close','volume'):
                rename_map[c] = c.capitalize() if cl != 'volume' else 'Volume'
        df.rename(columns=rename_map, inplace=True)
        if 'date' in df.columns:
            df.set_index('date', inplace=True)
        df.index = pd.to_datetime(df.index)
        df.sort_index(inplace=True)
        # Keep only needed columns
        needed = [c for c in ['Open','High','Low','Close','Volume'] if c in df.columns]
        return df[needed].dropna(subset=['Open','Close'])
    except Exception as e:
        print(f"ERROR reading {fn}: {e}")
        return None

def run_mode(df: pd.DataFrame, base_cfg: dict, trade_on: str, ticker: str):
    cfg = deepcopy(base_cfg)
    cfg['trade_on'] = trade_on
    # Optimize p, tw for this mode
    p_opt, tw_opt = berechne_best_p_tw_long(df, cfg, backtesting_begin, backtesting_end, verbose=False, ticker=ticker)
    price_col = 'Open' if trade_on.lower() == 'open' else 'Close'
    support, resistance = calculate_support_resistance(df, p_opt, tw_opt, price_col=price_col)
    ext = assign_long_signals_extended(support, resistance, df, tw_opt, '1d', price_col=price_col)
    ext = update_level_close_long(ext, df)
    final_cap, trades = simulate_trades_compound_extended(
        ext, df, cfg,
        commission_rate=DEFAULT_COMMISSION_RATE,
        min_commission=MIN_COMMISSION,
        round_factor=cfg.get('order_round_factor', ORDER_ROUND_FACTOR),
        artificial_close_price=None,
        artificial_close_date=None,
        direction='long'
    )
    return {
        'p': p_opt,
        'tw': tw_opt,
        'final_cap': final_cap,
        'trades': len(trades)
    }

def main():
    rows = []
    for ticker, cfg in tickers.items():
        if not cfg.get('long', True):
            continue  # skip if long disabled
        df = load_price_df(ticker)
        if df is None or df.empty:
            continue
        init_cap = cfg.get('initialCapitalLong', 1000)
        print(f"Processing {ticker} (initial {init_cap}) ...")
        res_open = run_mode(df, cfg, 'Open', ticker)
        res_close = run_mode(df, cfg, 'Close', ticker)
        diff = res_open['final_cap'] - res_close['final_cap']
        pct = (diff / res_close['final_cap'] * 100.0) if res_close['final_cap'] else None
        rows.append({
            'ticker': ticker,
            'initial_capital': init_cap,
            'final_cap_open': res_open['final_cap'],
            'p_open': res_open['p'],
            'tw_open': res_open['tw'],
            'trades_open': res_open['trades'],
            'final_cap_close': res_close['final_cap'],
            'p_close': res_close['p'],
            'tw_close': res_close['tw'],
            'trades_close': res_close['trades'],
            'diff_open_minus_close': diff,
            'pct_diff': pct
        })
    if not rows:
        print("No results produced.")
        return
    df_out = pd.DataFrame(rows)
    df_out.sort_values('pct_diff', ascending=False, inplace=True)
    df_out.to_csv(RESULT_CSV, index=False)
    print(f"\nSaved comparison to {RESULT_CSV}")
    print(df_out.to_string(index=False, float_format=lambda v: f"{v:,.2f}"))

if __name__ == '__main__':
    main()
