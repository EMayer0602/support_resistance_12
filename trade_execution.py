# trade_execution.py
# ─── 1. Imports oben im File ────────────────────────────────────────────────────
import sys
import math
import os
from typing import List, Dict
from math import floor
import yfinance as yf
from datetime import datetime
from ib_insync import IB, Stock, MarketOrder, LimitOrder
from tickers_config import tickers
import json
from datetime import date, timedelta

# ─── 1. IB- & YF-Preise ────────────────────────────────────────────────────────
from ib_insync import Stock

def get_price(ib, symbol: str, fallback: bool = True) -> float | None:
    """
    Holt den aktuellen Preis über IB. Optionaler Fallback auf Yahoo.
    - symbol: z. B. 'AAPL'
    - ib: aktives IB-Objekt
    - fallback: True = Yahoo-Fallback aktiv
    """
    try:
        contract = Stock(symbol, "SMART", "USD")
        ticker   = ib.reqMktData(contract, "", False, False)
        ib.sleep(1.5)  # IB braucht kurz Zeit für Preisdaten

        price = ticker.last if ticker.last else ticker.close
        if price is not None and price > 0:
            return round(price, 2)
    except Exception as e:
        print(f"⚠️ IB-Preisfehler für {symbol}: {e}")

    if fallback:
        try:
            import yfinance as yf
            df = yf.Ticker(symbol).history(period="1d")
            val = df["Close"].iloc[-1]
            return round(val, 2)
        except Exception as e:
            print(f"⚠️ Yahoo-Fallback für {symbol} fehlgeschlagen: {e}")
    
    return None
                                                                                       
# ─── 2. Live-Preis-Getter (unverändert) ────────────────────────────────────────
def get_realtime_price(ib: IB, contract: Stock) -> float:
    ib.qualifyContracts(contract)
    ticker = ib.reqMktData(contract, snapshot=True)
    ib.sleep(2)
    price = ticker.last or ticker.close
    return round(price, 2) if price else None

def get_yf_price(symbol: str, field: str = "Close") -> float:
    try:
        df = yf.Ticker(symbol).history(period="1d")
        price = df[field].iloc[-1]
        return round(price, 2)
    except Exception as e:
        print(f"{symbol}: Yahoo-Preis {field} fehlgeschlagen – {e}")
        return None

# ─── 3. Neuer Backtest-Preis-Getter ────────────────────────────────────────────
def get_backtest_price(symbol: str,
                       date_str: str,
                       field: str = "Close") -> float | None:
    """
    Liefert historischen Preis aus lokalem CSV oder von Yahoo.
    """
    field = field.capitalize()

    # 🔁 CACHE-Versuch über CSV-Datei
    fn = f"{symbol}_data.csv"
    try:
        if os.path.exists(fn):
            df_local = pd.read_csv(fn, parse_dates=["Date"], index_col="Date")
            df_local.sort_index(inplace=True)
            row = df_local.loc[pd.to_datetime(date_str)]
            price = row[field] if field in row else None
            if pd.notna(price):
                return float(price)
    except Exception:
        pass  # Ignorieren, falls Cache nicht greift

    # 🌐 Fallback zu Yahoo Finance
    try:
        start_dt = pd.to_datetime(date_str)
        end_dt = (start_dt + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        df = yf.Ticker(symbol).history(start=date_str, end=end_dt, auto_adjust=False)

        if df.empty:
            print(f"{symbol}: keine Yahoo-Daten für {date_str}")
            return None

        if field not in df.columns or pd.isna(df[field].iloc[0]):
            print(f"{symbol}: kein gültiger {field}-Preis am {date_str}")
            return None

        return round(df[field].iloc[0], 2)
    except Exception as e:
        print(f"{symbol}: Yahoo-Fehler am {date_str} → {e}")
        return None

import pandas as pd
import yfinance as yf

def get_backtest_price(symbol: str,
                       date_str: str,
                       field: str = "Close") -> float | None:
    """
    Liefert historischen Preis (Open/Close) von Yahoo Finance für genau einen Tag.
    Gibt None zurück, wenn keine Daten vorhanden sind.
    - date_str: Format 'YYYY-MM-DD'
    - field: 'Open' oder 'Close'
    """

    try:
        # → end = exklusiv, also +1 Tag für den Tagesbar
        start_dt = pd.to_datetime(date_str)
        end_dt   = (start_dt + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

        df = yf.Ticker(symbol).history(start=date_str, end=end_dt, auto_adjust=False)

        if df.empty:
            print(f"{symbol}: keine Daten für {date_str}")
            return None

        # Fallback von Open auf Close, falls Open fehlt
        field = field.capitalize()
        if field == "Open" and "Open" not in df.columns:
            print(f"{symbol}: kein Open am {date_str}, weiche auf Close aus")
            field = "Close"

        if field not in df.columns or pd.isna(df[field].iloc[0]):
            print(f"{symbol}: kein gültiger {field}-Preis am {date_str}")
            return None

        return round(df[field].iloc[0], 2)

    except Exception as e:
        print(f"{symbol}: Yahoo-Fehler am {date_str} → {e}")
        return None


# ─── 2. Grundlegende Helfer ─────────────────────────────────────────────────────

def calculate_shares(capital: float, price: float, round_factor: int) -> int:
    """
    Berechnet, wie viele Aktien mit 'capital' zum aktuellen 'price' gekauft werden
    können, gerundet auf Vielfache von 'round_factor'.
    """
    if price <= 0 or capital <= 0:
        return 0
    raw_amount = capital / price
    rounded = round(raw_amount / round_factor) * round_factor
    return int(rounded)

# ─── 4. Portfolio/Helfer-Funktionen (unverändert) ─────────────────────────────
def get_portfolio(ib: IB) -> dict:
    return {pos.contract.symbol: pos.position for pos in ib.positions()}

def target_qty(symbol: str, side: str, price: float, cfg: dict) -> int:
    """
    Gibt 0 zurück, wenn 'price' fehlt oder nicht zahlbar ist.
    """
    rnd = cfg['order_round_factor']

    # Preis prüfen
    if price is None or not isinstance(price, (int, float)) or math.isnan(price) or price <= 0:
        return 0

    if side == 'BUY':
        raw = cfg['initialCapitalLong'] / price
    elif side == 'SHORT':
        raw = cfg['initialCapitalShort'] / price
    else:
        return 0

    return int(round(raw / rnd) * rnd)

def plan_trade_qty(symbol, side, portfolio, price):
    cfg = tickers[symbol]
    factor = cfg.get("order_round_factor", 1)

    if side in ("SELL", "COVER"):
        return portfolio.get(symbol, 0)
    
    capital = cfg.get("initialCapitalLong", 0) if side == "BUY" else cfg.get("initialCapitalShort", 0)
    qty_raw = capital / price
    qty_rounded = int(qty_raw // factor * factor)

    return qty_rounded


# ─── 5. Trade-Funktionen (unverändert, nutzen plan_trade_qty) ─────────────────
def preview_trades(ib: IB) -> list:
    portfolio = get_portfolio(ib)
    plan      = []

    for symbol, cfg in tickers.items():
        price = get_price(ib, symbol)
        if not price:
            continue
        for side in ("BUY","SHORT","SELL","COVER"):
            if not cfg.get(side.lower(), False):
                continue
            qty = plan_trade_qty(symbol, side, portfolio, price)
            if qty > 0:
                plan.append({"symbol":symbol, "side":side, "qty":qty, "price":price})
    return plan

def execute_trades(ib: IB):
    portfolio = get_portfolio(ib)
    for symbol, cfg in tickers.items():
        price = get_price(ib, symbol)
        if not price:
            continue
        for side in ("BUY","SHORT","SELL","COVER"):
            if not cfg.get(side.lower(), False):
                continue
            qty = plan_trade_qty(symbol, side, portfolio, price)
            if qty <= 0:
                continue
            action   = "BUY" if side in ("BUY","COVER") else "SELL"
            order    = MarketOrder(action, qty)
            contract = ib.qualifyContracts(Stock(symbol,'SMART','USD'))[0]
            ib.placeOrder(contract, order)
            print(f"{action} {qty}×{symbol} @ {price:.2f} (Ziel={target_qty(symbol,side,price,cfg)})")

# ─── 6. Merged Order Utilities ────────────────────────────────────────────────
def merge_reversal_orders(planned: list[dict]) -> list[dict]:
    """Merge same-symbol same-session reversal sequences:
    - SELL followed by SHORT  => single net SELL order (flat then establish short)
    - BUY  followed by COVER  => single net BUY order (flat then establish long)
    We approximate by summing quantities when both actions present.
    planned: list of {symbol, side, qty, price}
    Returns new list with merged entries and metadata 'merged':True when merged.
    """
    by_symbol: dict[str, dict[str, dict]] = {}
    for o in planned:
        by_symbol.setdefault(o['symbol'], {}).setdefault(o['side'], o)
    merged: list[dict] = []
    for symbol, sides in by_symbol.items():
        sell = sides.get('SELL')
        short = sides.get('SHORT')
        buy = sides.get('BUY')
        cover = sides.get('COVER')
        # SELL + SHORT merge -> SELL with qty = sell.qty + short.qty
        if sell and short:
            merged.append({
                'symbol': symbol,
                'side': 'SELL',
                'qty': sell['qty'] + short['qty'],
                'price': sell['price'],
                'merged': True,
                'components': [sell, short]
            })
        else:
            if sell:
                merged.append(sell)
            if short:
                merged.append(short)
        # BUY + COVER merge -> BUY with qty = buy.qty + cover.qty
        if buy and cover:
            merged.append({
                'symbol': symbol,
                'side': 'BUY',
                'qty': buy['qty'] + cover['qty'],
                'price': buy['price'],
                'merged': True,
                'components': [buy, cover]
            })
        else:
            if buy:
                merged.append(buy)
            if cover:
                merged.append(cover)
    return merged

def execute_merged_trades(ib: IB):
    """Preview then execute merged reversal orders for current signals.
    Uses preview_trades() plan, merges, then places market orders.
    """
    plan = preview_trades(ib)
    merged = merge_reversal_orders(plan)
    if not merged:
        print("No trades to execute.")
        return
    print("Placing merged trades:")
    for o in merged:
        side = o['side']
        action = 'BUY' if side == 'BUY' else 'SELL'
        qty = o['qty']
        symbol = o['symbol']
        price = o.get('price')
        contract = ib.qualifyContracts(Stock(symbol,'SMART','USD'))[0]
        order = MarketOrder(action, qty)
        ib.placeOrder(contract, order)
        tag = " (merged)" if o.get('merged') else ""
        print(f"{action} {qty}×{symbol} mkt refPrice≈{price}{tag}")

# ─── 7. Historical Merge Test Utility ─────────────────────────────────────────
def load_trades_by_day(json_path: str = 'trades_by_day.json') -> dict:
    if not os.path.exists(json_path):
        print(f"File {json_path} not found.")
        return {}
    try:
        with open(json_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error reading {json_path}: {e}")
        return {}

def prepare_plan_from_day(trades_for_day: list) -> list:
    plan = []
    for t in trades_for_day:
        side = t.get('side') or t.get('action')
        if side not in ("BUY","SELL","SHORT","COVER"):
            continue
        plan.append({
            'symbol': t.get('symbol') or t.get('ticker'),
            'side': side,
            'qty': int(t.get('qty') or t.get('quantity') or t.get('shares') or 0),
            'price': float(t.get('price') or t.get('entry_price') or t.get('buy_price') or t.get('sell_price') or 0)
        })
    return plan

def test_merged_trades_for_date(date_str: str, execute: bool = False, paper: bool = True, client_id: int = 99):
    """Dry-run (default) or live test of merged reversal orders for a historical backtest day.
    - Loads trades_by_day.json, extracts that date's trades, merges, prints diff.
    - If execute=True connects to IB paper (default) and submits merged market orders.
    """
    all_days = load_trades_by_day()
    trades_for_day = all_days.get(date_str, [])
    if not trades_for_day:
        print(f"No trades found for {date_str} in trades_by_day.json")
        return
    original_plan = prepare_plan_from_day(trades_for_day)
    if not original_plan:
        print(f"No actionable BUY/SELL/SHORT/COVER entries for {date_str}")
        return
    merged_plan = merge_reversal_orders(original_plan)
    print(f"Historical trade merge test for {date_str}")
    print("Original:")
    for o in original_plan:
        print(f"  {o['symbol']:<8} {o['side']:<6} qty={o['qty']:<6} price={o['price']}")
    print("Merged:")
    for m in merged_plan:
        tag = " (merged)" if m.get('merged') else ""
        print(f"  {m['symbol']:<8} {m['side']:<6} qty={m['qty']:<6} price={m['price']}{tag}")
    reduction = len(original_plan) - len(merged_plan)
    print(f"Orders reduced: {len(original_plan)} -> {len(merged_plan)} (−{reduction})")
    if not execute:
        print("Dry run only (set execute=True to send orders).")
        return
    # Execute merged plan
    ib = IB()
    port = 7497 if paper else 7496
    try:
        ib.connect('127.0.0.1', port, clientId=client_id)
    except Exception as e:
        print(f"IB connect failed: {e}")
        return
    for m in merged_plan:
        action = 'BUY' if m['side'] == 'BUY' else 'SELL'
        contract = ib.qualifyContracts(Stock(m['symbol'],'SMART','USD'))[0]
        order = MarketOrder(action, m['qty'])
        ib.placeOrder(contract, order)
        print(f"Submitted {action} {m['qty']} {m['symbol']} (merged test)")
    ib.sleep(2)
    ib.disconnect()

def summarize_net_trades_for_date(date_str: str):
    """List trades for a date showing only net position change per symbol (neutral round-trips removed)."""
    all_days = load_trades_by_day()
    trades_for_day = all_days.get(date_str, [])
    if not trades_for_day:
        print(f"No trades found for {date_str} in trades_by_day.json")
        return
    original_plan = prepare_plan_from_day(trades_for_day)
    if not original_plan:
        print("No actionable trades.")
        return
    # Aggregate
    agg = {}
    for o in original_plan:
        sym = o['symbol']
        side = o['side']
        qty = o['qty']
        if sym not in agg:
            agg[sym] = {'buy_qty':0,'sell_qty':0,'price':o.get('price',0)}
        if side in ('BUY','COVER'):
            agg[sym]['buy_qty'] += qty
        elif side in ('SELL','SHORT'):
            agg[sym]['sell_qty'] += qty
    net_rows = []
    for sym, v in agg.items():
        net = v['buy_qty'] - v['sell_qty']
        if net > 0:
            net_rows.append({'symbol':sym,'action':'BUY','qty':net,'price':v['price']})
        elif net < 0:
            net_rows.append({'symbol':sym,'action':'SELL','qty':-net,'price':v['price']})
        # net == 0 => skip (neutral churn)
    print(f"Net trade summary for {date_str} (neutral BUY/SELL offsets removed):")
    if not net_rows:
        print("  (No net position changes)")
        return
    print(f"  {'Symbol':<8} {'Action':<6} {'Qty':>8} {'RefPrice':>10}")
    print("  " + '-'*36)
    for r in net_rows:
        print(f"  {r['symbol']:<8} {r['action']:<6} {r['qty']:>8} {r['price']:>10}")

def show_full_and_merged_for_date(date_str: str):
    """Print raw trades then merged+net trades for clarity."""
    all_days = load_trades_by_day()
    trades_for_day = all_days.get(date_str, [])
    if not trades_for_day:
        print(f"No trades found for {date_str} in trades_by_day.json")
        return
    original_plan = prepare_plan_from_day(trades_for_day)
    if not original_plan:
        print("No actionable trades.")
        return
    print(f"RAW TRADES for {date_str}:")
    print(f"  {'Symbol':<8} {'Side':<6} {'Qty':>8} {'Price':>10}")
    print("  " + '-'*36)
    for o in original_plan:
        print(f"  {o['symbol']:<8} {o['side']:<6} {o['qty']:>8} {o['price']:>10}")
    # First perform reversal merge (cover+buy, sell+short)
    merged_reversal = merge_reversal_orders(original_plan)
    # Now net them (remove churn) similar to summarize_net_trades_for_date
    agg = {}
    for o in merged_reversal:
        sym = o['symbol']
        side = o['side']
        qty = o['qty']
        agg.setdefault(sym, {'buy':0,'sell':0,'price':o.get('price',0)})
        if side in ('BUY','COVER'):
            agg[sym]['buy'] += qty
        elif side in ('SELL','SHORT'):
            agg[sym]['sell'] += qty
    final_rows = []
    for sym, v in agg.items():
        net = v['buy'] - v['sell']
        if net > 0:
            final_rows.append({'symbol':sym,'action':'BUY','qty':net,'price':v['price']})
        elif net < 0:
            final_rows.append({'symbol':sym,'action':'SELL','qty':-net,'price':v['price']})
    print(f"\nMERGED + NET TRADES for {date_str} (neutral churn removed):")
    if not final_rows:
        print("  (No net position changes)")
        return
    print(f"  {'Symbol':<8} {'Action':<6} {'Qty':>8} {'RefPrice':>10}")
    print("  " + '-'*36)
    for r in final_rows:
        print(f"  {r['symbol']:<8} {r['action']:<6} {r['qty']:>8} {r['price']:>10}")


def list_all_trades_for_date(date_str: str, include_artificial: bool = True):
    """List every long and short trade action (BUY/SELL/SHORT/COVER) occurring on date_str.
    Reads per-ticker trades_long_*.csv and trades_short_*.csv so we can still display
    artificial close exits even though they were suppressed in trades_by_day.json.
    """
    import glob
    rows = []
    # Long trades
    for long_path in glob.glob('trades_long_*.csv'):
        try:
            df = pd.read_csv(long_path, parse_dates=['buy_date','sell_date'])
        except Exception:
            continue
        symbol = long_path.replace('trades_long_','').replace('.csv','')
        for _, tr in df.iterrows():
            shares = int(tr.get('shares',0) or 0)
            bdt = tr.get('buy_date')
            sdt = tr.get('sell_date')
            bpr = tr.get('buy_price')
            spr = tr.get('sell_price')
            art = bool(tr.get('artificial_close'))
            if pd.notna(bdt) and str(pd.Timestamp(bdt).date()) == date_str:
                rows.append({'symbol':symbol,'side':'BUY','qty':shares,'price':bpr,'artificial':'','trade_on': tr.get('entry_price_col')})
            if pd.notna(sdt) and str(pd.Timestamp(sdt).date()) == date_str:
                if art and not include_artificial:
                    pass
                else:
                    rows.append({'symbol':symbol,'side':'SELL','qty':shares,'price':spr,'artificial':'Y' if art else '','trade_on': tr.get('exit_price_col')})
    # Short trades
    for short_path in glob.glob('trades_short_*.csv'):
        try:
            df = pd.read_csv(short_path, parse_dates=['short_date','cover_date'])
        except Exception:
            continue
        symbol = short_path.replace('trades_short_','').replace('.csv','')
        for _, tr in df.iterrows():
            shares = int(tr.get('shares',0) or 0)
            sdt = tr.get('short_date')
            cdt = tr.get('cover_date')
            spr = tr.get('short_price')
            cpr = tr.get('cover_price')
            art = bool(tr.get('artificial_close'))
            if pd.notna(sdt) and str(pd.Timestamp(sdt).date()) == date_str:
                rows.append({'symbol':symbol,'side':'SHORT','qty':shares,'price':spr,'artificial': '','trade_on': tr.get('entry_price_col')})
            if pd.notna(cdt) and str(pd.Timestamp(cdt).date()) == date_str:
                if art and not include_artificial:
                    pass
                else:
                    rows.append({'symbol':symbol,'side':'COVER','qty':shares,'price':cpr,'artificial':'Y' if art else '','trade_on': tr.get('exit_price_col')})
    if not rows:
        print(f"No trade actions on {date_str}.")
        return
    # Sort for stable output (symbol then side)
    rows.sort(key=lambda r: (r['symbol'], r['side']))
    print(f"ALL TRADE ACTIONS for {date_str} (including artificial closes={'YES' if include_artificial else 'NO'})")
    print(f"  {'Symbol':<8} {'Side':<6} {'Qty':>8} {'Price':>10} {'On':<5} {'Art':>4}")
    print("  " + '-'*47)
    for r in rows:
        price_fmt = f"{r['price']:.2f}" if isinstance(r['price'], (int,float)) else ''
        print(f"  {r['symbol']:<8} {r['side']:<6} {r['qty']:>8} {price_fmt:>10} {str(r.get('trade_on','')):<5} {r['artificial']:>4}")
    # Summary counts
    from collections import Counter
    c = Counter([r['side'] for r in rows])
    print("Summary:")
    print('  ' + ', '.join([f"{k}={v}" for k,v in sorted(c.items())]))


def all_trades_merged_for_date(date_str: str):
    """Show raw real trade actions (excluding artificial closes) and merged reversal orders + net.
    Uses same gathering logic as list_all_trades_for_date(include_artificial=False)."""
    import glob
    rows = []
    # Reuse logic but inline (avoid refactor churn)
    for long_path in glob.glob('trades_long_*.csv'):
        try:
            df = pd.read_csv(long_path, parse_dates=['buy_date','sell_date'])
        except Exception:
            continue
        symbol = long_path.replace('trades_long_','').replace('.csv','')
        for _, tr in df.iterrows():
            shares = int(tr.get('shares',0) or 0)
            bdt = tr.get('buy_date')
            sdt = tr.get('sell_date')
            bpr = tr.get('buy_price')
            spr = tr.get('sell_price')
            art = bool(tr.get('artificial_close'))
            if pd.notna(bdt) and str(pd.Timestamp(bdt).date()) == date_str:
                rows.append({'symbol':symbol,'side':'BUY','qty':shares,'price':bpr,'trade_on': tr.get('entry_price_col')})
            if pd.notna(sdt) and not art and str(pd.Timestamp(sdt).date()) == date_str:
                rows.append({'symbol':symbol,'side':'SELL','qty':shares,'price':spr,'trade_on': tr.get('exit_price_col')})
    for short_path in glob.glob('trades_short_*.csv'):
        try:
            df = pd.read_csv(short_path, parse_dates=['short_date','cover_date'])
        except Exception:
            continue
        symbol = short_path.replace('trades_short_','').replace('.csv','')
        for _, tr in df.iterrows():
            shares = int(tr.get('shares',0) or 0)
            sdt = tr.get('short_date')
            cdt = tr.get('cover_date')
            spr = tr.get('short_price')
            cpr = tr.get('cover_price')
            art = bool(tr.get('artificial_close'))
            if pd.notna(sdt) and str(pd.Timestamp(sdt).date()) == date_str:
                rows.append({'symbol':symbol,'side':'SHORT','qty':shares,'price':spr,'trade_on': tr.get('entry_price_col')})
            if pd.notna(cdt) and not art and str(pd.Timestamp(cdt).date()) == date_str:
                rows.append({'symbol':symbol,'side':'COVER','qty':shares,'price':cpr,'trade_on': tr.get('exit_price_col')})
    if not rows:
        print(f"No real trade actions on {date_str}.")
        return
    rows.sort(key=lambda r: (r['symbol'], r['side']))
    print(f"RAW REAL TRADE ACTIONS for {date_str} (artificial exits excluded)")
    print(f"  {'Symbol':<8} {'Side':<6} {'Qty':>8} {'Price':>10} {'On':<5}")
    print("  " + '-'*44)
    for r in rows:
        price_fmt = f"{r['price']:.2f}" if isinstance(r['price'], (int,float)) else ''
        print(f"  {r['symbol']:<8} {r['side']:<6} {r['qty']:>8} {price_fmt:>10} {str(r.get('trade_on','')):<5}")
    # Merge reversal orders
    merged = merge_reversal_orders(rows)
    # Annotate trade_on for merged rows
    for m in merged:
        if m.get('merged') and m.get('components'):
            tos = {c.get('trade_on') for c in m['components'] if c.get('trade_on')}
            if len(tos)==1:
                m['trade_on'] = list(tos)[0]
            elif len(tos)>1:
                m['trade_on'] = 'mixed'
        elif 'trade_on' not in m:
            m['trade_on'] = ''
    print(f"\nMERGED REVERSAL ORDERS for {date_str}")
    print(f"  {'Symbol':<8} {'Side':<6} {'Qty':>8} {'Price':>10} {'On':<5} {'Tag':>6}")
    print("  " + '-'*52)
    for m in merged:
        tag = 'M' if m.get('merged') else ''
        price_fmt = f"{m.get('price'):.2f}" if isinstance(m.get('price'), (int,float)) else ''
        print(f"  {m['symbol']:<8} {m['side']:<6} {m['qty']:>8} {price_fmt:>10} {str(m.get('trade_on','')):<5} {tag:>6}")
    # Net summary after merge
    agg = {}
    for o in merged:
        sym = o['symbol']
        side = o['side']
        qty = o['qty']
        agg.setdefault(sym, {'buy':0,'sell':0,'price':o.get('price',0)})
        if side in ('BUY','COVER'):
            agg[sym]['buy'] += qty
        elif side in ('SELL','SHORT'):
            agg[sym]['sell'] += qty
    net_rows = []
    for sym,v in agg.items():
        net = v['buy'] - v['sell']
        if net>0:
            net_rows.append({'symbol':sym,'side':'BUY','qty':net,'price':v['price']})
        elif net<0:
            net_rows.append({'symbol':sym,'side':'SELL','qty':-net,'price':v['price']})
    print(f"\nNET POSITION CHANGES after merge (neutral churn removed)")
    if not net_rows:
        print("  (No net changes)")
    else:
        print(f"  {'Symbol':<8} {'Side':<6} {'Qty':>8} {'Price':>10} {'On':<5}")
        print("  " + '-'*44)
        for r in net_rows:
            price_fmt = f"{r['price']:.2f}" if isinstance(r['price'], (int,float)) else ''
            # Determine trade_on from underlying symbol rows
            tos = {row.get('trade_on') for row in rows if row['symbol']==r['symbol'] and row.get('trade_on')}
            r_on = list(tos)[0] if len(tos)==1 else ('mixed' if len(tos)>1 else '')
            print(f"  {r['symbol']:<8} {r['side']:<6} {r['qty']:>8} {price_fmt:>10} {r_on:<5}")


# ─── 8. Scheduled Execution (Open + Close Windows) ───────────────────────────
def _gather_orders_for_date(date_str: str, merged: bool = True) -> list[dict]:
    """Collect real (non-artificial) trade actions for a date with trade_on info.
    Returns list of {symbol, side, qty, price, trade_on} possibly merged if merged=True.
    """
    import glob
    rows = []
    # Long
    for long_path in glob.glob('trades_long_*.csv'):
        try:
            df = pd.read_csv(long_path, parse_dates=['buy_date','sell_date'])
        except Exception:
            continue
        symbol = long_path.replace('trades_long_','').replace('.csv','')
        for _, tr in df.iterrows():
            art = bool(tr.get('artificial_close'))
            shares = int(tr.get('shares',0) or 0)
            bdt = tr.get('buy_date'); sdt = tr.get('sell_date')
            if pd.notna(bdt) and str(pd.Timestamp(bdt).date())==date_str:
                rows.append({'symbol':symbol,'side':'BUY','qty':shares,'price':tr.get('buy_price'), 'trade_on': tr.get('entry_price_col')})
            if pd.notna(sdt) and not art and str(pd.Timestamp(sdt).date())==date_str:
                rows.append({'symbol':symbol,'side':'SELL','qty':shares,'price':tr.get('sell_price'), 'trade_on': tr.get('exit_price_col')})
    # Short
    for short_path in glob.glob('trades_short_*.csv'):
        try:
            df = pd.read_csv(short_path, parse_dates=['short_date','cover_date'])
        except Exception:
            continue
        symbol = short_path.replace('trades_short_','').replace('.csv','')
        for _, tr in df.iterrows():
            art = bool(tr.get('artificial_close'))
            shares = int(tr.get('shares',0) or 0)
            sdt = tr.get('short_date'); cdt = tr.get('cover_date')
            if pd.notna(sdt) and str(pd.Timestamp(sdt).date())==date_str:
                rows.append({'symbol':symbol,'side':'SHORT','qty':shares,'price':tr.get('short_price'), 'trade_on': tr.get('entry_price_col')})
            if pd.notna(cdt) and not art and str(pd.Timestamp(cdt).date())==date_str:
                rows.append({'symbol':symbol,'side':'COVER','qty':shares,'price':tr.get('cover_price'), 'trade_on': tr.get('exit_price_col')})
    if merged:
        rows = merge_reversal_orders(rows)
    return rows

def schedule_trades_for_date(date_str: str, execute: bool = False, merged: bool = True,
                             open_delay_min: int = 5, close_advance_min: int = 5,
                             force_all: bool = False, limit: bool = False):
    """Schedule submission of trades by trade_on column.
    - trade_on == 'Open': submit at 09:30 ET + open_delay_min
    - trade_on == 'Close': submit at 16:00 ET - close_advance_min
    If execute=False, just prints planned schedule (dry run).
    """
    from datetime import datetime, time as dtime
    try:
        from zoneinfo import ZoneInfo  # py>=3.9
        tz_et = ZoneInfo('US/Eastern')
    except Exception:
        tz_et = None  # fallback naive

    orders = _gather_orders_for_date(date_str, merged=merged)
    if not orders:
        print(f"No real orders for {date_str} to schedule.")
        return
    # Split by trade_on
    open_orders = [o for o in orders if (o.get('trade_on') or '').lower()=='open']
    close_orders = [o for o in orders if (o.get('trade_on') or '').lower()=='close']
    print(f"Scheduling {len(open_orders)} open-session and {len(close_orders)} close-session orders for {date_str} (merged={merged}) force_all={force_all} limit={limit}")
    # Build target datetimes in ET (or naive)
    dt_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    open_target_et = datetime.combine(dt_date, dtime(9,30))
    close_target_et = datetime.combine(dt_date, dtime(16,0))
    if tz_et:
        open_target_et = open_target_et.replace(tzinfo=tz_et)
        close_target_et = close_target_et.replace(tzinfo=tz_et)
    open_target_et = open_target_et.replace(minute=30+open_delay_min)
    close_target_et = close_target_et.replace(minute=60-close_advance_min if close_advance_min<60 else 55)  # guard

    def _sleep_until(target):
        import time
        if tz_et:
            now = datetime.now(tz_et)
        else:
            now = datetime.now()
        if target <= now:
            return
        delta = (target - now).total_seconds()
        if delta > 0:
            time.sleep(delta)

    def _submit_group(label: str, group: list[dict], ib: IB | None):
        if not group:
            print(f"[{label}] No orders")
            return
        print(f"[{label}] Submitting {len(group)} orders:")
        for o in group:
            sym = o['symbol']; side = o['side']; qty = int(o['qty'])
            action = 'BUY' if side in ('BUY','COVER') else 'SELL'
            if not execute:
                print(f"  DRY {action} {qty} {sym} ref={o.get('price')} trade_on={o.get('trade_on')}")
            else:
                try:
                    contract = ib.qualifyContracts(Stock(sym,'SMART','USD'))[0]
                    order = None
                    if limit:
                        # Determine limit price based on trade_on field (Open/Close)
                        price_field = 'Open' if (o.get('trade_on','').lower()=='open') else 'Close'
                        limit_price = get_backtest_price(sym, date_str, price_field)  # fallback historical (same-day) price
                        if not limit_price:
                            print(f"  WARN {sym} missing {price_field} price; falling back to market order")
                            order = MarketOrder(action, qty)
                        else:
                            order = LimitOrder(action, qty, round(float(limit_price),2))
                    if order is None:
                        order = MarketOrder(action, qty)
                    ib.placeOrder(contract, order)
                    lp = getattr(order,'lmtPrice', None)
                    if lp is not None:
                        print(f"  LIVE {action} {qty} {sym} LIMIT {lp} trade_on={o.get('trade_on')}")
                    else:
                        print(f"  LIVE {action} {qty} {sym} MKT trade_on={o.get('trade_on')}")
                except Exception as e:
                    print(f"  ERR {sym} {action} failed: {e}")

    ib = None
    if execute:
        ib = IB()
        try:
            ib.connect('127.0.0.1', 7497, clientId=111)
        except Exception as e:
            print(f"IB connect failed; switching to dry-run: {e}")
            execute = False
            ib = None

    if force_all:
        # Immediate submission of all orders (both Open + Close) regardless of clock/time/day.
        if open_orders:
            _submit_group('FORCE-OPEN', open_orders, ib)
        else:
            print("[FORCE] No Open trades to send.")
        if close_orders:
            _submit_group('FORCE-CLOSE', close_orders, ib)
        else:
            print("[FORCE] No Close trades to send.")
    else:
        # Open-session orders
        if open_orders:
            print(f"Open-session target ET: {open_target_et}")
            _sleep_until(open_target_et)
            _submit_group('OPEN', open_orders, ib)
        else:
            print("No Open trades to send.")
        # Close-session orders
        if close_orders:
            print(f"Close-session target ET: {close_target_et}")
            _sleep_until(close_target_et)
            _submit_group('CLOSE', close_orders, ib)
        else:
            print("No Close trades to send.")

    if ib:
        ib.sleep(1)
        ib.disconnect()
    print("Scheduling complete.")


# ─── 9. Immediate API Transmission Utility ───────────────────────────────────
def transmit_orders_api(date_str: str, *, phase: str = 'both', execute: bool = False,
                        merged: bool = True, limit: bool = False, client_id: int = 777,
                        max_orders: int | None = None, ib: IB | None = None):
    """Immediately transmit orders for a backtest date via IB API.
    Parameters:
      date_str  : YYYY-MM-DD
      phase     : 'open', 'close', or 'both' to filter by trade_on
      execute   : when False -> dry run
      merged    : merge reversal orders first
      limit     : use limit orders at that day's Open/Close price else market
      client_id : IB client id
      max_orders: optional cap on number of orders to submit (after filtering)
    """
    phase_l = phase.lower()
    if phase_l not in ('open','close','both'):
        print(f"Invalid phase {phase}; use open|close|both")
        return
    orders = _gather_orders_for_date(date_str, merged=merged)
    if not orders:
        print(f"No real orders for {date_str} (merged={merged}).")
        return
    if phase_l != 'both':
        orders = [o for o in orders if (o.get('trade_on') or '').lower()==phase_l]
    else:
        # deterministic ordering: Open then Close
        orders.sort(key=lambda o: (0 if (o.get('trade_on') or '').lower()=='open' else 1, o.get('symbol'), o.get('side')))
    if not orders:
        print(f"No {phase_l} orders for {date_str}.")
        return
    if max_orders is not None:
        orders = orders[:max_orders]
    print(f"API TRANSMIT {date_str} phase={phase_l} merged={merged} limit={limit} orders={len(orders)} execute={execute}")
    owned_ib = False
    if execute and ib is None:
        ib = IB()
        try:
            ib.connect('127.0.0.1', 7497, clientId=client_id)
            owned_ib = True
        except Exception as e:
            print(f"IB connect failed: {e}")
            ib = None
            execute = False
    from trade_execution import get_backtest_price  # local import to avoid circular
    sent = 0
    for o in orders:
        sym = o['symbol']; side = o['side']; qty = int(o['qty']); to_col = (o.get('trade_on') or '')
        action = 'BUY' if side in ('BUY','COVER') else 'SELL'
        if not execute:
            print(f"DRY {action} {qty} {sym} trade_on={to_col}")
            continue
        try:
            contract = ib.qualifyContracts(Stock(sym,'SMART','USD'))[0]
            use_limit = False
            limit_price = None
            if limit:
                price_field = 'Open' if to_col.lower()=='open' else 'Close'
                limit_price = get_backtest_price(sym, date_str, price_field)
                if limit_price:
                    use_limit = True
            if use_limit and limit_price:
                order = LimitOrder(action, qty, float(limit_price))
            else:
                order = MarketOrder(action, qty)
            ib.placeOrder(contract, order)
            if isinstance(order, LimitOrder):
                print(f"LIVE {action} {qty} {sym} LIMIT {order.lmtPrice} trade_on={to_col}")
            else:
                print(f"LIVE {action} {qty} {sym} MKT trade_on={to_col}")
            sent += 1
        except Exception as e:
            print(f"ERR {sym} {action} failed: {e}")
    if ib and owned_ib:
        ib.sleep(1)
        ib.disconnect()
    print(f"Done. Sent={sent} (execute={execute}).")


# ─── 10. IB Connection Helper with Retry ─────────────────────────────────────
def connect_ib(client_id: int = 101, retries: int = 3, delay: float = 2.0) -> IB | None:
    """Attempt to connect to IB with limited retries."""
    ib = IB()
    for attempt in range(1, retries+1):
        try:
            ib.connect('127.0.0.1', 7497, clientId=client_id)
            print(f"IB connected (clientId={client_id}) on attempt {attempt}.")
            return ib
        except Exception as e:
            print(f"IB connect attempt {attempt} failed: {e}")
            if attempt < retries:
                import time as _t
                _t.sleep(delay)
    print("Failed to connect to IB after retries.")
    return None


# ─── 11. Run Backtest Then Transmit Immediately ─────────────────────────────
def backtest_and_transmit_date(date_str: str, *, phase: str = 'both', execute: bool = False,
                               merged: bool = True, limit: bool = False, client_id: int = 909,
                               max_orders: int | None = None, reuse_connection: bool = True):
    """Run runner.py fullbacktest, then transmit orders for date_str via API.
    If reuse_connection, keep one IB session for both actions (transmit only)."""
    import subprocess, sys as _sys
    print(f"[BT+TX] Starting fullbacktest prior to transmit date={date_str} phase={phase}")
    res = subprocess.run([_sys.executable, 'runner.py', 'fullbacktest'], capture_output=True, text=True)
    if res.returncode != 0:
        print(f"[BT+TX] Backtest failed: {res.returncode}\n{res.stderr[-500:]}")
        return
    print("[BT+TX] Backtest complete. Tail:")
    tail = '\n'.join(res.stdout.strip().splitlines()[-10:])
    print(tail)
    ib = None
    if execute:
        ib = connect_ib(client_id=client_id) if reuse_connection else None
        if execute and ib is None and reuse_connection:
            print("[BT+TX] Cannot transmit; IB connection failed.")
            return
    transmit_orders_api(date_str, phase=phase, execute=execute, merged=merged, limit=limit,
                        client_id=client_id, max_orders=max_orders, ib=ib)
    if ib and reuse_connection:
        ib.disconnect()


if __name__ == '__main__':
    import sys
    args = sys.argv[1:]
    if not args:
        print("Commands:")
        print("  full_merged_date YYYY-MM-DD")
        print("  all_trades_date YYYY-MM-DD [noart]")
        print("  all_trades_date_no_art YYYY-MM-DD")
        print("  all_trades_merged_date YYYY-MM-DD")
        print("  schedule_date YYYY-MM-DD [execute] [raw] [force]")
        print("  net_date YYYY-MM-DD")
        print("  merged_last_friday")
        print("  merged_date YYYY-MM-DD [execute]")
        sys.exit(0)
    cmd = args[0].lower()
    try:
        if cmd == 'full_merged_date':
            if len(args) < 2:
                raise SystemExit("Provide date YYYY-MM-DD")
            show_full_and_merged_for_date(args[1])
        elif cmd == 'all_trades_date':
            if len(args) < 2:
                raise SystemExit("Provide date YYYY-MM-DD")
            include_art = True
            if len(args) > 2 and args[2].lower() in ('noart','no_art','exclude','real'):
                include_art = False
            list_all_trades_for_date(args[1], include_artificial=include_art)
        elif cmd == 'all_trades_date_no_art':
            if len(args) < 2:
                raise SystemExit("Provide date YYYY-MM-DD")
            list_all_trades_for_date(args[1], include_artificial=False)
        elif cmd == 'all_trades_merged_date':
            if len(args) < 2:
                raise SystemExit("Provide date YYYY-MM-DD")
            all_trades_merged_for_date(args[1])
        elif cmd == 'schedule_date':
            if len(args) < 2:
                raise SystemExit("Provide date YYYY-MM-DD")
            exec_flag = any(a.lower()=='execute' for a in args[2:])
            nomerge = any(a.lower()=='raw' for a in args[2:])
            force_all = any(a.lower() in ('force','force_all','now','immediate') for a in args[2:])
            limit_flag = any(a.lower() in ('limit','limitorder','lmt') for a in args[2:])
            schedule_trades_for_date(args[1], execute=exec_flag, merged=not nomerge, force_all=force_all, limit=limit_flag)
        elif cmd == 'api_transmit_date':
            if len(args) < 2:
                raise SystemExit("Provide date YYYY-MM-DD")
            date_str = args[1]
            exec_flag = any(a.lower()=='execute' for a in args[2:])
            limit_flag = any(a.lower() in ('limit','limitorder','lmt') for a in args[2:])
            merged_flag = not any(a.lower()=='raw' for a in args[2:])
            phase = 'both'
            for a in args[2:]:
                if a.lower() in ('open','close','both'):
                    phase = a.lower()
            max_orders = None
            for a in args[2:]:
                if a.lower().startswith('max='):
                    try:
                        max_orders = int(a.split('=',1)[1])
                    except ValueError:
                        pass
            transmit_orders_api(date_str, phase=phase, execute=exec_flag, merged=merged_flag, limit=limit_flag, max_orders=max_orders)
        elif cmd == 'bt_tx_date':
            if len(args) < 2:
                raise SystemExit("Provide date YYYY-MM-DD")
            date_str = args[1]
            exec_flag = any(a.lower()=='execute' for a in args[2:])
            limit_flag = any(a.lower() in ('limit','limitorder','lmt') for a in args[2:])
            merged_flag = not any(a.lower()=='raw' for a in args[2:])
            phase = 'both'
            reuse = True
            max_orders = None
            for a in args[2:]:
                if a.lower() in ('open','close','both'):
                    phase = a.lower()
                elif a.lower()=='noreuse':
                    reuse = False
                elif a.lower().startswith('max='):
                    try:
                        max_orders = int(a.split('=',1)[1])
                    except ValueError:
                        pass
            backtest_and_transmit_date(date_str, phase=phase, execute=exec_flag, merged=merged_flag,
                                       limit=limit_flag, max_orders=max_orders, reuse_connection=reuse)
        elif cmd == 'net_date':
            if len(args) < 2:
                raise SystemExit("Provide date YYYY-MM-DD")
            summarize_net_trades_for_date(args[1])
        elif cmd == 'merged_last_friday':
            today = date.today()
            offset = (today.weekday() - 4) % 7 or 7
            last_friday = today - timedelta(days=offset)
            test_merged_trades_for_date(last_friday.strftime('%Y-%m-%d'))
        elif cmd == 'merged_date':
            if len(args) < 2:
                raise SystemExit("Provide date YYYY-MM-DD")
            date_str = args[1]
            exec_flag = len(args) > 2 and args[2].lower() == 'execute'
            test_merged_trades_for_date(date_str, execute=exec_flag)
        else:
            raise SystemExit("Unknown command.")
    except SystemExit as e:
        print(e)
        sys.exit(1)
