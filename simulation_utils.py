# simulation_utils.py

import pandas as pd
from trade_execution import calculate_shares
from tickers_config import tickers
from datetime import datetime, timedelta


def generate_backtest_date_range(start="2025-07-01", end="2025-07-18"):
    """
    Gibt eine Liste von Datum-Strings im Format 'YYYY-MM-DD' zurück
    zwischen Start und End (beide inklusive).
    """
    from datetime import datetime, timedelta
    start_date = datetime.strptime(start, "%Y-%m-%d")
    end_date   = datetime.strptime(end, "%Y-%m-%d")
    days = []

    while start_date <= end_date:
        days.append(start_date.strftime("%Y-%m-%d"))
        start_date += timedelta(days=1)

    return days

def get_trade_price(df, cfg, date):
    '''
    Gibt den Preis für einen Tag laut trade_on-Vorgabe zurück ('open' oder 'close').
    '''
    col = "Open" if cfg.get("trade_on", "close").lower() == "open" else "Close"
    if date in df.index:
        return float(df.at[date, col])
    idx = df.index.searchsorted(date)
    if idx < len(df.index):
        return float(df.iloc[idx][col])
    return None

def compute_equity_curve(df, trades, start_capital, long=True):
    '''
    Berechnet die Equity-Kurve exakt entlang df.index.
    Nutzt reale Entry/Exit und täglich aktuelle Close-Preise.
    '''
    equity = []
    cap = start_capital
    pos = 0
    entry_price = 0
    trade_idx = 0

    for date in df.index:
        # Entry?
        if trade_idx < len(trades):
            entry_key = "buy_date" if long else "short_date"
            entry_price_key = "buy_price" if long else "short_price"
            if pd.Timestamp(trades[trade_idx].get(entry_key)) == date:
                pos = trades[trade_idx]["shares"]
                entry_price = trades[trade_idx][entry_price_key]

        # Exit?
        if trade_idx < len(trades):
            exit_key = "sell_date" if long else "cover_date"
            if pd.Timestamp(trades[trade_idx].get(exit_key)) == date:
                cap += trades[trade_idx]["pnl"]
                pos = 0
                entry_price = 0
                trade_idx += 1

        # Kapitalwert berechnen
        if pos > 0:
            current_price = df.loc[date, "Close"]
            delta = (current_price - entry_price) if long else (entry_price - current_price)
            value = cap + pos * delta
        else:
            value = cap

        equity.append(value)

    return equity  # ← exakt gleich lang wie df.index

def debug_equity_alignment(df, equity_curve):
    '''
    Prüft, ob die Equity-Kurve exakt die gleiche Länge und Zeitachse wie df.index hat.
    Gibt Warnungen bei Diskrepanzen.
    '''
    n_df = len(df.index)
    n_eq = len(equity_curve)
    print(f"✅ Candlestick-Zeilen: {n_df}")
    print(f"✅ Equity-Zeilen:      {n_eq}")

    if n_df != n_eq:
        print(f"❌ Unterschiedliche Länge! Equity-Kurve hat {n_eq - n_df:+d} Zeilen Abweichung.")
        return

    mismatches = []
    for i, (dt, eq_dt) in enumerate(zip(df.index, df.index)):
        if pd.isna(dt) or not isinstance(dt, pd.Timestamp):
            mismatches.append((i, "NaT oder kein Timestamp in df.index"))
        # Equity verwendet denselben Index — falls dort später z. B. eigene Zeitachse kommt, kann man auch gegen eq_index prüfen

    if mismatches:
        print(f"⚠️ {len(mismatches)} problematische Zeilen:")
        for i, reason in mismatches[:5]:
            print(f"  Zeile {i}: {reason}")
    else:
        print("✅ Alles ok. Index ist zeilensynchron und verwendbar für Plotly.")

def simulate_trades_compound_extended(
    extended_df, market_df, config,
    commission_rate=0.0018, min_commission=1.0,
    round_factor=1, artificial_close_price=None,
    artificial_close_date=None, direction="long"
):
    sort_col = "Long Date detected" if direction == "long" else "Short Date detected"
    action_col = "Long Action" if direction == "long" else "Short Action"

    extended_df = extended_df.sort_values(by=sort_col)
    capital = config["initialCapitalLong"] if direction == "long" else config["initialCapitalShort"]

    trades = []
    position_active = False
    entry_price = entry_date = prev_cap = shares = None

    for _, row in extended_df.iterrows():
        action = row.get(action_col)
        exec_date = row.get(sort_col)
        if pd.isna(exec_date):
            continue

        price = get_trade_price(market_df, config, exec_date)
        if price is None:
            continue

        if action in ["buy", "short"] and not position_active:
            shares = int(capital / price)
            shares = max((shares // round_factor) * round_factor, round_factor)
            if shares <= 0:
                continue
            entry_price = price
            entry_date = exec_date
            prev_cap = capital
            position_active = True

        elif action in ["sell", "cover"] and position_active:
            profit = (price - entry_price) * shares if direction == "long" else (entry_price - price) * shares
            turnover = shares * (entry_price + price)
            fee = max(min_commission, turnover * commission_rate)
            capital += profit - fee
            trades.append({
                ("buy_date" if direction == "long" else "short_date"): entry_date,
                ("sell_date" if direction == "long" else "cover_date"): exec_date,
                ("buy_price" if direction == "long" else "short_price"): round(entry_price, 2),
                ("sell_price" if direction == "long" else "cover_price"): round(price, 2),
                "shares": shares,
                "fee": round(fee, 2),
                "pnl": round(capital - prev_cap, 3)
            })
            position_active = False

    if position_active and artificial_close_price is not None and artificial_close_date is not None:
        profit = (artificial_close_price - entry_price) * shares if direction == "long" else (entry_price - artificial_close_price) * shares
        turnover = shares * (entry_price + artificial_close_price)
        fee = max(min_commission, turnover * commission_rate)
        capital += profit - fee
        trades.append({
            ("buy_date" if direction == "long" else "short_date"): entry_date,
            ("sell_date" if direction == "long" else "cover_date"): artificial_close_date,
            ("buy_price" if direction == "long" else "short_price"): round(entry_price, 2),
            ("sell_price" if direction == "long" else "cover_price"): round(artificial_close_price, 2),
            "shares": shares,
            "fee": round(fee, 2),
            "pnl": round(capital - prev_cap, 3)
        })

    return capital, trades


def calculate_shares_from_df(cfg, df, date, direction="long"):
    if pd.isna(date) or date not in df.index:
        return 0

    col = "Open" if cfg.get("trade_on", "close").lower() == "open" else "Close"
    price = df.at[date, col]
    if not isinstance(price, (int, float)) or price <= 0:
        return 0

    capital_key = "initialCapitalLong" if direction == "long" else "initialCapitalShort"
    capital = cfg.get(capital_key, 0)
    round_factor = cfg.get("order_round_factor", 1)

    raw_shares = capital / price
    shares = int(raw_shares)
    shares = max((shares // round_factor) * round_factor, round_factor)

    return shares


