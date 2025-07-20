from ib_insync import Stock
import yfinance as yf
def get_realtime_price(ib, contract):
    ib.qualifyContracts(contract)
    ticker = ib.reqMktData(contract, snapshot=True)
    ib.sleep(2)
    price = ticker.last if ticker.last else ticker.close
    return round(price, 2) if price else None

def get_yf_price(symbol):
    data = yf.Ticker(symbol)
    try:
        price = data.history(period="1d")["Close"].iloc[-1]
        return round(price, 2)
    except Exception as e:
        print(f"{symbol}: Preisabruf fehlgeschlagen – {e}")
        return None

def calculate_shares(capital: float, price: float, round_factor: int) -> int:
    """
    Berechnet die Stückzahl als (capital / price) und rundet
    auf das nächstliegende Vielfache von round_factor.
    """
    if price <= 0 or capital <= 0:
        return 0
    raw = capital / price
    shares = round(raw / round_factor) * round_factor
    return int(shares)

from tickers_config import tickers
from scipy.signal import argrelextrema
import numpy as np
import pandas as pd
from backtesting_core import assign_long_signals_extended, assign_short_signals_extended
from signal_utils import update_level_close_long, update_level_close_short
from backtesting_core import simulate_trades_compound_extended

def get_next_trading_day(current_date, market_df):
    """Findet den nächsten verfügbaren Handelstag.
       Falls current_date NaT ist oder über den maximalen Handelstag hinausgeht, wird NaT zurückgegeben.
    """
    if pd.isna(current_date):
        return pd.NaT
    max_date = market_df.index.max()
    if current_date > max_date:
        return pd.NaT
    while current_date not in market_df.index:
        current_date += pd.Timedelta(days=1)
        if current_date > max_date:
            return pd.NaT
    return current_date

def trade_trading_for_today(ib):
    today = datetime.date.today()
    print(f"\n=== TRADEMODE TRADES für {today} ===")

    for ticker, cfg in tickers.items():
        # 1) Trades laden
        try:
            trades_l = pd.read_csv(f"trades_long_{ticker}.csv",
                                   parse_dates=["buy_date","sell_date"])
        except (FileNotFoundError, EmptyDataError):
            trades_l = pd.DataFrame(columns=[
                "buy_date","sell_date","shares","buy_price","sell_price","fee","pnl"
            ])
        trades_l["buy_date"]  = pd.to_datetime(trades_l["buy_date"],  errors="coerce")
        trades_l["sell_date"] = pd.to_datetime(trades_l["sell_date"], errors="coerce")

        try:
            trades_s = pd.read_csv(f"trades_short_{ticker}.csv",
                                   parse_dates=["short_date","cover_date"])
        except (FileNotFoundError, EmptyDataError):
            trades_s = pd.DataFrame(columns=[
                "short_date","cover_date","shares","short_price","cover_price","fee","pnl"
            ])
        trades_s["short_date"] = pd.to_datetime(trades_s["short_date"], errors="coerce")
        trades_s["cover_date"] = pd.to_datetime(trades_s["cover_date"], errors="coerce")

        # 2) Filtern auf heute
        buys   = trades_l[ trades_l["buy_date"].dt.date  == today ]
        sells  = trades_l[ trades_l["sell_date"].dt.date == today ]
        shorts = trades_s[ trades_s["short_date"].dt.date == today ]
        covers = trades_s[ trades_s["cover_date"].dt.date== today ]

        if buys.empty and sells.empty and shorts.empty and covers.empty:
            continue

        contract = Stock(cfg["symbol"], cfg.get("exchange","SMART"), cfg.get("currency","USD"))
        used = set()

        # 3) PAIRED LONG: buy_date + cover_date
        for _, b in buys.iterrows():
            cov = covers[covers["cover_date"].dt.date == b["buy_date"].date()]
            if cov.empty or b["buy_date"] in used:
                continue
            cov = cov.iloc[0]
            qty = int(b["shares"] + cov["shares"])
            price = b["buy_price"]
            # Market Buy
            ib.placeOrder(contract, MarketOrder("BUY", qty))
            # Limit Buy
            lvl = round(price * 1.002, 2)
            ib.placeOrder(contract, LimitOrder("BUY", qty, lvl))
            used.add(b["buy_date"])

        # 4) PAIRED SHORT: sell_date + short_date
        for _, s in sells.iterrows():
            sho = shorts[shorts["short_date"].dt.date == s["sell_date"].date()]
            if sho.empty or s["sell_date"] in used:
                continue
            sho = sho.iloc[0]
            qty = int(s["shares"] + sho["shares"])
            price = sho["short_price"]
            # Market Sell
            ib.placeOrder(contract, MarketOrder("SELL", qty))
            # Limit Sell
            lvl = round(price * 0.998, 2)
            ib.placeOrder(contract, LimitOrder("SELL", qty, lvl))
            used.add(s["sell_date"])

        # 5) Einzelorders BUY
        for _, b in buys.iterrows():
            if b["buy_date"] in used: continue
            qty = int(b["shares"])
            price = b["buy_price"]
            ib.placeOrder(contract, MarketOrder("BUY", qty))
            lvl = round(price * 1.002, 2)
            ib.placeOrder(contract, LimitOrder("BUY", qty, lvl))
            used.add(b["buy_date"])

        # 6) Einzelorders SELL
        for _, s in sells.iterrows():
            if s["sell_date"] in used: continue
            qty = int(s["shares"])
            price = s["sell_price"]
            ib.placeOrder(contract, MarketOrder("SELL", qty))
            lvl = round(price * 0.998, 2)
            ib.placeOrder(contract, LimitOrder("SELL", qty, lvl))
            used.add(s["sell_date"])

        # 7) Einzelorders COVER
        for _, c in covers.iterrows():
            if c["cover_date"] in used: continue
            qty = int(c["shares"])
            price = c["cover_price"]
            ib.placeOrder(contract, MarketOrder("BUY", qty))
            lvl = round(price * 1.002, 2)
            ib.placeOrder(contract, LimitOrder("BUY", qty, lvl))
            used.add(c["cover_date"])

        # 8) Einzelorders SHORT
        for _, sh in shorts.iterrows():
            if sh["short_date"] in used: continue
            qty = int(sh["shares"])
            price = sh["short_price"]
            ib.placeOrder(contract, MarketOrder("SELL", qty))
            lvl = round(price * 0.998, 2)
            ib.placeOrder(contract, LimitOrder("SELL", qty, lvl))
            used.add(sh["short_date"])

    print("\nAlle Trades für heute wurden an IB gesendet.")

    today = datetime.date.today()
    print(f"\n=== TRADEMODE TRADES für {today} ===")

    for ticker, cfg in tickers.items():
        # Trades laden
        try:
            trades_l = pd.read_csv(f"trades_long_{ticker}.csv",
                                   parse_dates=["buy_date","sell_date"])
        except (FileNotFoundError, EmptyDataError):
            trades_l = pd.DataFrame()
        trades_l["buy_date"]  = pd.to_datetime(trades_l.get("buy_date"),  errors="coerce")
        trades_l["sell_date"] = pd.to_datetime(trades_l.get("sell_date"), errors="coerce")

        try:
            trades_s = pd.read_csv(f"trades_short_{ticker}.csv",
                                   parse_dates=["short_date","cover_date"])
        except (FileNotFoundError, EmptyDataError):
            trades_s = pd.DataFrame()
        trades_s["short_date"] = pd.to_datetime(trades_s.get("short_date"), errors="coerce")
        trades_s["cover_date"] = pd.to_datetime(trades_s.get("cover_date"), errors="coerce")

        # Filtern
        buys   = trades_l[ trades_l["buy_date"].dt.date  == today ]
        sells  = trades_l[ trades_l["sell_date"].dt.date == today ]
        shorts = trades_s[ trades_s["short_date"].dt.date == today ]
        covers = trades_s[ trades_s["cover_date"].dt.date == today ]

        if buys.empty and sells.empty and shorts.empty and covers.empty:
            continue

        contract = Stock(cfg["symbol"], cfg.get("exchange","SMART"), cfg.get("currency","USD"))
        for side_df, entry_col, qty_col, price_col, mkt_side, lim_side, lim_factor in [
            (buys,  "buy_date",   "shares", "buy_price",  "BUY",  "BUY", 1.002),
            (sells, "sell_date",  "shares", "sell_price", "SELL", "SELL",0.998),
            (covers,"cover_date","shares","cover_price","BUY","BUY",1.002),
            (shorts,"short_date","shares","short_price","SELL","SELL",0.998),
        ]:
            for _, row in side_df.iterrows():
                qty   = int(row[qty_col])
                price = float(row[price_col])
                # Market
                ib.placeOrder(contract, MarketOrder(mkt_side, qty))
                # Limit
                lvl = round(price * lim_factor, 2)
                ib.placeOrder(contract, LimitOrder(lim_side, qty, lvl))

    print("\nAlle Trades für heute wurden an IB gesendet.")


def calculate_support_resistance(df, past_window, trade_window):
    """
    Berechnet Support/Resistance basierend auf Close-Preisen.
    Ein Fenster von (past_window + trade_window) wird genutzt; 
    zusätzlich werden das absolute Minimum und Maximum hinzugefügt.
    """
    total_window = int(past_window + trade_window)
    prices = df["Close"].values

    local_min_idx = argrelextrema(prices, np.less, order=total_window)[0]
    support = pd.Series(prices[local_min_idx], index=df.index[local_min_idx])

    local_max_idx = argrelextrema(prices, np.greater, order=total_window)[0]
    resistance = pd.Series(prices[local_max_idx], index=df.index[local_max_idx])

    # Absolutes Minimum ergänzen
    absolute_low_date = df["Close"].idxmin()
    absolute_low = df["Close"].min()
    if absolute_low_date not in support.index:
        support = pd.concat([support, pd.Series([absolute_low], index=[absolute_low_date])])

    # Absolutes Maximum ergänzen
    absolute_high_date = df["Close"].idxmax()
    absolute_high = df["Close"].max()
    if absolute_high_date not in resistance.index:
        resistance = pd.concat([resistance, pd.Series([absolute_high], index=[absolute_high_date])])

    support.sort_index(inplace=True)
    resistance.sort_index(inplace=True)

    return support, resistance

def compute_trend(df, window=20):
    """Berechnet den einfachen gleitenden Durchschnitt (SMA)."""
    return df["Close"].rolling(window=window).mean()

def calculate_shares(capital, price, round_factor):
    """
    Berechnet die Anzahl der Shares als (Kapital / Preis)
    und rundet das Ergebnis auf das nächstgelegene Vielfache des round_factor.
    """
    raw = capital / price
    shares = round(raw / round_factor) * round_factor
    return shares

def assign_long_signals(support, resistance, data, trade_window, interval):
    data.sort_index(inplace=True)

    sup_df = pd.DataFrame({'Date': support.index, 'Level': support.values, 'Type': 'support'})
    res_df = pd.DataFrame({'Date': resistance.index, 'Level': resistance.values, 'Type': 'resistance'})
    df = pd.concat([sup_df, res_df]).sort_values(by='Date').reset_index(drop=True)

    df['Long'] = None
    df['Long Date'] = pd.NaT
    df['Valid Signal'] = True
    long_active = False

    for i, row in df.iterrows():
        base_date = row['Date']
        interval_clean = interval.replace(" ", "").lower()

        if interval_clean in ["1d", "1day"]:
            trade_date = base_date + pd.Timedelta(days=trade_window)
        elif interval_clean.endswith("min"):
            minutes = int(interval_clean.replace("min", ""))
            trade_date = base_date + pd.Timedelta(minutes=trade_window * minutes)
        elif interval_clean in ["1h", "1hour"]:
            trade_date = base_date + pd.Timedelta(hours=trade_window)
        else:
            df.at[i, "Valid Signal"] = False
            continue

        if trade_date not in data.index:
            idx = data.index.searchsorted(trade_date)
            trade_date = data.index[idx] if idx < len(data.index) else pd.NaT

        if pd.isna(trade_date) or trade_date not in data.index or pd.isna(data.loc[trade_date, "Close"]):
            df.at[i, "Valid Signal"] = False

        if row['Type'] == 'support' and not long_active:
            df.at[i, 'Long'] = 'buy'
            df.at[i, 'Long Date'] = trade_date
            long_active = True
        elif row['Type'] == 'resistance' and long_active:
            df.at[i, 'Long'] = 'sell'
            df.at[i, 'Long Date'] = trade_date
            long_active = False

    df['Date'] = pd.to_datetime(df['Date']).dt.tz_localize(None)
    df['Long Date'] = pd.to_datetime(df['Long Date'], errors='coerce').dt.tz_localize(None)
    return df

def assign_long_signals(support, resistance, data, trade_window, interval):
    data.sort_index(inplace=True)

    sup_df = pd.DataFrame({'Date': support.index, 'Level': support.values, 'Type': 'support'})
    res_df = pd.DataFrame({'Date': resistance.index, 'Level': resistance.values, 'Type': 'resistance'})
    df = pd.concat([sup_df, res_df]).sort_values(by='Date').reset_index(drop=True)

    df['Long'] = None
    df['Long Date'] = pd.NaT
    df['Valid Signal'] = True
    long_active = False

    for i, row in df.iterrows():
        base_date = row['Date']
        interval_clean = interval.replace(" ", "").lower()

        if interval_clean in ["1d", "1day"]:
            trade_date = base_date + pd.Timedelta(days=trade_window)
        elif interval_clean.endswith("min"):
            minutes = int(interval_clean.replace("min", ""))
            trade_date = base_date + pd.Timedelta(minutes=trade_window * minutes)
        elif interval_clean in ["1h", "1hour"]:
            trade_date = base_date + pd.Timedelta(hours=trade_window)
        else:
            df.at[i, "Valid Signal"] = False
            continue

        if trade_date not in data.index:
            idx = data.index.searchsorted(trade_date)
            trade_date = data.index[idx] if idx < len(data.index) else pd.NaT

        if pd.isna(trade_date) or trade_date not in data.index or pd.isna(data.loc[trade_date, "Close"]):
            df.at[i, "Valid Signal"] = False

        if row['Type'] == 'support' and not long_active:
            df.at[i, 'Long'] = 'buy'
            df.at[i, 'Long Date'] = trade_date
            long_active = True
        elif row['Type'] == 'resistance' and long_active:
            df.at[i, 'Long'] = 'sell'
            df.at[i, 'Long Date'] = trade_date
            long_active = False

    df['Date'] = pd.to_datetime(df['Date']).dt.tz_localize(None)
    df['Long Date'] = pd.to_datetime(df['Long Date'], errors='coerce').dt.tz_localize(None)
    return df

def simulate_short_trades_compound_extended(extended_df, market_df, starting_capital=10000,
                                            commission_rate=0.0018, min_commission=1.0,
                                            round_factor=1,
                                            artificial_close_price=None,
                                            artificial_close_date=None):
    """
    Simuliert Short‑Trades basierend auf den Extended-Short-Signalen.
    Ergänzt offene Trades mit künstlichem Close (z.B. 15:50).
    """
    extended_df = extended_df.sort_values(by="Short Date detected")
    capital = starting_capital
    position_active = False
    trades = []
    short_price = short_date = prev_cap = None

    for _, row in extended_df.iterrows():
        action = row.get('Short Action')
        exec_date = row.get('Short Date detected')
        if pd.isna(exec_date):
            continue

        if exec_date in market_df.index:
            price = float(market_df.loc[exec_date, "Close"])
        else:
            idx = market_df.index.searchsorted(exec_date)
            price = float(market_df.iloc[idx]["Close"]) if idx < len(market_df.index) else None

        if price is None:
            continue

        if action == 'short' and not position_active:
            shares = calculate_shares(capital, price, round_factor)
            if shares < 1e-6:
                continue
            short_price = price
            short_date = exec_date
            position_active = True
            prev_cap = capital

        elif action == 'cover' and position_active:
            cover_price = price
            cover_date = exec_date
            profit = (short_price - cover_price) * shares
            turnover = shares * (short_price + cover_price)
            fee = max(min_commission, turnover * commission_rate)
            new_cap = prev_cap + profit - fee
            trades.append({
                'short_date': short_date,
                'cover_date': cover_date,
                'shares': shares,
                'short_price': round(short_price, 2),
                'cover_price': round(cover_price, 2),
                'fee': round(fee, 2),
                'pnl': round(new_cap - prev_cap, 3)
            })
            capital = new_cap
            position_active = False

    # Falls Position offen: mit künstlichem Close abschließen
    if position_active and artificial_close_price is not None and artificial_close_date is not None:
        cover_price = artificial_close_price
        cover_date = artificial_close_date
        profit = (short_price - cover_price) * shares
        turnover = shares * (short_price + cover_price)
        fee = max(min_commission, turnover * commission_rate)
        new_cap = prev_cap + profit - fee
        trades.append({
            'short_date': short_date,
            'cover_date': cover_date,
            'shares': shares,
            'short_price': round(short_price, 2),
            'cover_price': round(cover_price, 2),
            'fee': round(fee, 2),
            'pnl': round(new_cap - prev_cap, 3)
        })
        capital = new_cap

    return capital, trades

def simulate_trades_compound(signals_df, market_df, starting_capital=10000,
                             commission_rate=0.0018, min_commission=1.0,
                             round_factor=1):
    """
    Simuliert Long‑Trades mit dynamischer Ordergröße.
    """
    capital = starting_capital
    position_active = False
    trades = []

    for _, row in signals_df.iterrows():
        signal = row.get('Long')
        exec_date = row.get('Long Date')
        if pd.isna(exec_date):
            continue

        if exec_date in market_df.index:
            price = float(market_df.loc[exec_date, "Close"])
        else:
            idx = market_df.index.searchsorted(exec_date)
            price = float(market_df.iloc[idx]["Close"]) if idx < len(market_df.index) else None

        if price is None:
            continue

        if signal == 'buy' and not position_active:
            shares = calculate_shares(capital, price, round_factor)
            if shares < 1e-6:
                continue
            buy_price = price
            buy_date = exec_date
            position_active = True
            prev_cap = capital

        elif signal == 'sell' and position_active:
            sell_price = price
            sell_date = exec_date
            profit = (sell_price - buy_price) * shares
            turnover = shares * (buy_price + sell_price)
            fee = max(min_commission, turnover * commission_rate)
            new_cap = prev_cap + profit - fee
            trades.append({
                'buy_date': buy_date,
                'sell_date': sell_date,
                'shares': shares,
                'buy_price': round(buy_price, 2),
                'sell_price': round(sell_price, 2),
                'fee': round(fee, 2),
                'pnl': round(new_cap - prev_cap, 3)
            })
            capital = new_cap
            position_active = False

    return capital, trades

def simulate_short_trades_compound(signals_df, market_df, starting_capital=10000,
                                   commission_rate=0.0018, min_commission=1.0,
                                   round_factor=1):
    """
    Simuliert Short‑Trades mit dynamischer Ordergröße.
    """
    capital = starting_capital
    position_active = False
    trades = []

    for _, row in signals_df.iterrows():
        signal = row.get('Short')
        exec_date = row.get('Short Date')
        if pd.isna(exec_date):
            continue

        if exec_date in market_df.index:
            price = float(market_df.loc[exec_date, "Close"])
        else:
            idx = market_df.index.searchsorted(exec_date)
            price = float(market_df.iloc[idx]["Close"]) if idx < len(market_df.index) else None

        if price is None:
            continue

        if signal == 'short' and not position_active:
            shares = calculate_shares(capital, price, round_factor)
            if shares < 1e-6:
                continue
            short_price = price
            short_date = exec_date
            position_active = True
            prev_cap = capital

        elif signal == 'cover' and position_active:
            cover_price = price
            cover_date = exec_date
            profit = (short_price - cover_price) * shares
            turnover = shares * (short_price + cover_price)
            fee = max(min_commission, turnover * commission_rate)
            new_cap = prev_cap + profit - fee
            trades.append({
                'short_date': short_date,
                'cover_date': cover_date,
                'shares': shares,
                'short_price': round(short_price, 2),
                'cover_price': round(cover_price, 2),
                'fee': round(fee, 2),
                'pnl': round(new_cap - prev_cap, 3)
            })
            capital = new_cap
            position_active = False

    return capital, trades

def compute_equity_curve(df, trades, start_capital, long=True):
    equity = []
    cap = start_capital
    pos = 0
    entry_price = 0
    trade_idx = 0

    for date in df.index:
        # Einstieg
        if trade_idx < len(trades):
            entry_key = "buy_date" if long else "short_date"
            entry_price_key = "buy_price" if long else "short_price"
            if trades[trade_idx].get(entry_key) == date:
                pos = trades[trade_idx]["shares"]
                entry_price = trades[trade_idx][entry_price_key]

        # Ausstieg
        if trade_idx < len(trades):
            exit_key = "sell_date" if long else "cover_date"
            if trades[trade_idx].get(exit_key) == date:
                cap += trades[trade_idx]["pnl"]
                pos = 0
                entry_price = 0
                trade_idx += 1

        # Equity berechnen
        if pos > 0:
            current_price = df.loc[date, "Close"]
            delta = (current_price - entry_price) if long else (entry_price - current_price)
            value = cap + pos * delta
        else:
            value = cap

        equity.append(value)

    return equity

import plotly.graph_objs as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

def plot_combined_chart_and_equity(df, standard_long, standard_short, support, resistance, trend,
                                   equity_long, equity_short, equity_combined, buyhold, ticker):
    offset = 0.02 * (df["Close"].max() - df["Close"].min())
    buy_offset   = 2 * offset
    sell_offset  = -2 * offset
    short_offset = -offset
    cover_offset = offset

    buy_marker   = pd.Series(np.nan, index=df.index)
    sell_marker  = pd.Series(np.nan, index=df.index)
    short_marker = pd.Series(np.nan, index=df.index)
    cover_marker = pd.Series(np.nan, index=df.index)

    for _, row in standard_long.iterrows():
        if row["Long"] == "buy" and pd.notna(row["Long Date"]):
            buy_marker.loc[row["Long Date"]] = df.loc[row["Long Date"], "Close"] + buy_offset
        elif row["Long"] == "sell" and pd.notna(row["Long Date"]):
            sell_marker.loc[row["Long Date"]] = df.loc[row["Long Date"], "Close"] + sell_offset

    for _, row in standard_short.iterrows():
        if row.get("Short") == "short" and pd.notna(row["Short Date"]):
            short_marker.loc[row["Short Date"]] = df.loc[row["Short Date"], "Close"] + short_offset
        elif row.get("Short") == "cover" and pd.notna(row["Short Date"]):
            cover_marker.loc[row["Short Date"]] = df.loc[row["Short Date"], "Close"] + cover_offset

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05,
                        row_heights=[0.6, 0.4],
                        subplot_titles=(f"{ticker} Candlestick mit Markern", "Equity-Kurven"))

    # Candlestick
    fig.add_trace(go.Candlestick(
        x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
        name="Candlestick"
    ), row=1, col=1)

    # Trade-Marker
    fig.add_trace(go.Scatter(x=buy_marker.index, y=buy_marker.values, mode='markers',
                             marker=dict(symbol='triangle-up', color='red', size=10), name='Buy'), row=1, col=1)
    fig.add_trace(go.Scatter(x=sell_marker.index, y=sell_marker.values, mode='markers',
                             marker=dict(symbol='triangle-down', color='red', size=10), name='Sell'), row=1, col=1)
    fig.add_trace(go.Scatter(x=short_marker.index, y=short_marker.values, mode='markers',
                             marker=dict(symbol='triangle-down', color='blue', size=10), name='Short'), row=1, col=1)
    fig.add_trace(go.Scatter(x=cover_marker.index, y=cover_marker.values, mode='markers',
                             marker=dict(symbol='triangle-up', color='blue', size=10), name='Cover'), row=1, col=1)

    # Support / Resistance / Trend
    support = support.reindex(df.index)
    resistance = resistance.reindex(df.index)

    fig.add_trace(go.Scatter(x=support.dropna().index, y=support.dropna().values,
                             mode="markers", marker=dict(symbol="circle", color="green", size=6), name="Support"), row=1, col=1)
    fig.add_trace(go.Scatter(x=resistance.dropna().index, y=resistance.dropna().values,
                             mode="markers", marker=dict(symbol="x", color="orange", size=6), name="Resistance"), row=1, col=1)
    fig.add_trace(go.Scatter(x=trend.index, y=trend.values, mode='lines',
                             line=dict(color='black', width=1), name='Trend'), row=1, col=1)

    # Equity-Kurven
    fig.add_trace(go.Scatter(x=df.index, y=equity_long, mode='lines', name='Long Equity'), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=equity_short, mode='lines', name='Short Equity'), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=equity_combined, mode='lines', name='Combined'), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=buyhold, mode='lines', name='Buy & Hold'), row=2, col=1)

    fig.update_layout(
        height=900,
        title=f"{ticker}: Chart mit Support, Trades & Equity",
        xaxis=dict(rangeslider=dict(visible=False)),
        xaxis2=dict(rangeslider=dict(visible=True, thickness=0.03)),
        margin=dict(b=30, t=60)
    )
    fig.show()

def print_matched_long_trades(trades, ticker=None):
    """
    Gibt Long-Trades als Markdown-Tabelle aus.
    Struktur: buy_date, buy_price, sell_date, sell_price, shares, fee, pnl
    """
    print(f"\n## Matched Long Trades – {ticker or 'Unnamed'}")

    if not trades:
        print("_Keine Long-Trades gefunden._")
        return

    df = pd.DataFrame(trades)
    df["pnl"] = df["pnl"].round(2)
    cols = ["buy_date", "buy_price", "sell_date", "sell_price", "shares", "fee", "pnl"]
    if all(col in df.columns for col in cols):
        print(df[cols].to_markdown(index=False))
    else:
        print("_Ungültiges Long-Trade-Format._")

def print_matched_short_trades(trades, ticker=None):
    """
    Gibt Short-Trades als Markdown-Tabelle aus.
    Struktur: short_date, short_price, cover_date, cover_price, shares, fee, pnl
    """
    print(f"\n## Matched Short Trades – {ticker or 'Unnamed'}")

    if not trades:
        print("_Keine Short-Trades gefunden._")
        return

    df = pd.DataFrame(trades)
    df["pnl"] = df["pnl"].round(2)
    cols = ["short_date", "short_price", "cover_date", "cover_price", "shares", "fee", "pnl"]
    if all(col in df.columns for col in cols):
        print(df[cols].to_markdown(index=False))
    else:
        print("_Ungültiges Short-Trade-Format._")


def both_backtesting_multi(ib):
    import os
    import pandas as pd
    from ib_insync import Stock

    # Holt deine Ticker-Konfiguration
    from tickers_config import tickers

    # Für die Equity-Kurven und das Chart
    from your_plot_module import plot_combined_chart_and_equity  # passe den Importpfad an
    from your_utils_module import compute_equity_curve, compute_trend  # passe an

    for ticker, config in tickers.items():
        print(f"\n=================== Backtesting für {ticker} ===================")

        # 1) CSV laden oder aktualisieren
        csv_fn  = f"{ticker}_data.csv"
        contract = Stock(config["symbol"], "SMART", "USD")
        if os.path.exists(csv_fn):
            df = pd.read_csv(csv_fn, parse_dates=["date"], index_col="date")
        else:
            df = update_historical_data_csv(ib, contract, csv_fn)
        df.sort_index(inplace=True)
        df.rename(columns={"open":"Open","high":"High","low":"Low","close":"Close"}, inplace=True)

        # künstlicher Schlusskurs für offene Positionen
        artificial_close_date  = df.index[-1]
        artificial_close_price = df.loc[artificial_close_date, "Close"]

        # 2) LONG backtesten
        if config.get("long", False):
            p_long, tw_long = berechne_best_p_tw_long(df, config, backtesting_begin, backtesting_end)
            sup_long, res_long = calculate_support_resistance(df, p_long, tw_long)
            standard_long = assign_long_signals(sup_long, res_long, df, tw_long, "1d")
            ext_long      = assign_long_signals_extended(sup_long, res_long, df, tw_long, "1d")
            ext_long      = update_level_close_long(ext_long, df)
            cap_long, long_trades = simulate_trades_compound_extended(
                ext_long, df,
                starting_capital       = config["initialCapitalLong"],
                commission_rate        = COMMISSION_RATE,
                min_commission         = MIN_COMMISSION,
                round_factor           = config["order_round_factor"],
                artificial_close_price = artificial_close_price,
                artificial_close_date  = artificial_close_date,
                direction              = "long"
            )
            equity_long = compute_equity_curve(df, long_trades, config["initialCapitalLong"], long=True)
        else:
            standard_long = ext_long = pd.DataFrame()
            long_trades   = []
            equity_long   = [0] * len(df)
            cap_long      = config["initialCapitalLong"]

        # 3) SHORT backtesten
        if config.get("short", False):
            p_short, tw_short = berechne_best_p_tw_short(df, config, backtesting_begin, backtesting_end)
            sup_short, res_short = calculate_support_resistance(df, p_short, tw_short)
            standard_short = assign_short_signals(sup_short, res_short, df, tw_short, "1d")
            ext_short      = assign_short_signals_extended(sup_short, res_short, df, tw_short, "1d")
            ext_short      = update_level_close_short(ext_short, df)
            cap_short, short_trades = simulate_trades_compound_extended(
                ext_short, df,
                starting_capital       = config["initialCapitalShort"],
                commission_rate        = COMMISSION_RATE,
                min_commission         = MIN_COMMISSION,
                round_factor           = config["order_round_factor"],
                artificial_close_price = artificial_close_price,
                artificial_close_date  = artificial_close_date,
                direction              = "short"
            )
            equity_short = compute_equity_curve(df, short_trades, config["initialCapitalShort"], long=False)
        else:
            standard_short = ext_short = pd.DataFrame()
            short_trades   = []
            equity_short   = [0] * len(df)
            cap_short      = config["initialCapitalShort"]

        # 4) CSVs schreiben
        if not ext_long.empty:
            ext_long.to_csv(f"extended_Long_signals_{ticker}.csv", index=False)
        if not ext_short.empty:
            ext_short.to_csv(f"extended_Short_signals_{ticker}.csv", index=False)
        pd.DataFrame(long_trades ).to_csv(f"trades_long_{ticker}.csv",  index=False)
        pd.DataFrame(short_trades).to_csv(f"trades_short_{ticker}.csv", index=False)
        print(f"{ticker}: Extended-Signale & Trades gespeichert.")

        # 5) Markdown-Output
        print(f"\n=== Backtest für {ticker} ===\n")

        print(f"## Matched Long Trades – {ticker}")
        if long_trades:
            df_ml = pd.DataFrame(long_trades)
            print(df_ml.to_markdown(index=False))
        else:
            print("_Keine Long-Trades gefunden._")
        print()

        print(f"## Matched Short Trades – {ticker}")
        if short_trades:
            df_ms = pd.DataFrame(short_trades)
            print(df_ms.to_markdown(index=False))
        else:
            print("_Keine Short-Trades gefunden._")
        print("-" * 60)

        # 6) Chart & Equity-Kurven plotten
        equity_combined = [l + s for l, s in zip(equity_long, equity_short)]
        buyhold = [config["initialCapitalLong"] * (p / df["Close"].iloc[0]) for p in df["Close"]]
        plot_combined_chart_and_equity(
            df, standard_long, standard_short,
            sup_long if config.get("long",False) else sup_short,
            res_short if config.get("short",False) else res_long,
            compute_trend(df, window=20),
            equity_long, equity_short,
            equity_combined, buyhold,
            ticker
        )


from pandas.errors import EmptyDataError
import pandas as pd
import datetime

def test_trading_for_date(ib, date_str):
    today = pd.to_datetime(date_str).date()
    print(f"\n=== TESTMODE TRADES für {today} ===")

    for ticker, cfg in tickers.items():
        try:
            trades_l = pd.read_csv(f"trades_long_{ticker}.csv", parse_dates=["buy_date", "sell_date"])
        except (FileNotFoundError, EmptyDataError):
            trades_l = pd.DataFrame(columns=["buy_date", "sell_date", "shares", "buy_price", "sell_price", "fee", "pnl"])

        try:
            trades_s = pd.read_csv(f"trades_short_{ticker}.csv", parse_dates=["short_date", "cover_date"])
        except (FileNotFoundError, EmptyDataError):
            trades_s = pd.DataFrame(columns=["short_date", "cover_date", "shares", "short_price", "cover_price", "fee", "pnl"])

        trades_l["buy_date"]  = pd.to_datetime(trades_l["buy_date"],  errors="coerce")
        trades_l["sell_date"] = pd.to_datetime(trades_l["sell_date"], errors="coerce")
        trades_s["short_date"] = pd.to_datetime(trades_s["short_date"], errors="coerce")
        trades_s["cover_date"] = pd.to_datetime(trades_s["cover_date"], errors="coerce")

        buys   = trades_l[trades_l["buy_date"].dt.date  == today]
        sells  = trades_l[trades_l["sell_date"].dt.date == today]
        shorts = trades_s[trades_s["short_date"].dt.date == today]
        covers = trades_s[trades_s["cover_date"].dt.date == today]

        if buys.empty and sells.empty and shorts.empty and covers.empty:
            continue

        print(f"\n{ticker}:")
        used = set()

        for _, b in buys.iterrows():
            cov = covers[covers["cover_date"].dt.date == b["buy_date"].date()]
            if cov.empty or b["buy_date"] in used:
                continue
            cov = cov.iloc[0]
            qty = int(b["shares"] + cov["shares"])
            price = b["buy_price"]
            print(f" PAIRED LONG {qty}@{price:.2f}")
            print(f"   → Market Buy  {qty} @ {price:.2f}")
            print(f"   → Limit Buy   {qty} @ {price * 1.002:.2f}")
            used.add(b["buy_date"])

        for _, s in sells.iterrows():
            sho = shorts[shorts["short_date"].dt.date == s["sell_date"].date()]
            if sho.empty or s["sell_date"] in used:
                continue
            sho = sho.iloc[0]
            qty = int(s["shares"] + sho["shares"])
            price = sho["short_price"]
            print(f" PAIRED SHORT {qty}@{price:.2f}")
            print(f"   → Market Sell {qty} @ {price:.2f}")
            print(f"   → Limit Sell  {qty} @ {price * 0.998:.2f}")
            used.add(s["sell_date"])

        for _, b in buys.iterrows():
            if b["buy_date"] not in used:
                qty = int(b["shares"])
                price = b["buy_price"]
                print(f" BUY   {qty}@{price:.2f}")
                print(f"   → Market Buy  {qty} @ {price:.2f}")
                print(f"   → Limit Buy   {qty} @ {price * 1.002:.2f}")
                used.add(b["buy_date"])

        for _, s in sells.iterrows():
            if s["sell_date"] not in used:
                qty = int(s["shares"])
                price = s["sell_price"]
                print(f" SELL  {qty}@{price:.2f}")
                print(f"   → Market Sell {qty} @ {price:.2f}")
                print(f"   → Limit Sell  {qty} @ {price * 0.998:.2f}")
                used.add(s["sell_date"])

        for _, c in covers.iterrows():
            if c["cover_date"] not in used:
                qty = int(c["shares"])
                price = c["cover_price"]
                print(f" COVER {qty}@{price:.2f}")
                print(f"   → Market Buy  {qty} @ {price:.2f}")
                print(f"   → Limit Buy   {qty} @ {price * 1.002:.2f}")
                used.add(c["cover_date"])

        for _, sh in shorts.iterrows():
            if sh["short_date"] not in used:
                qty = int(sh["shares"])
                price = sh["short_price"]
                print(f" SHORT {qty}@{price:.2f}")
                print(f"   → Market Sell {qty} @ {price:.2f}")
                print(f"   → Limit Sell  {qty} @ {price * 0.998:.2f}")
                used.add(sh["short_date"])

def test_extended_for_date(date_str):
    today = pd.to_datetime(date_str).date()
    print(f"\n=== TESTMODE EXTENDED TRADES für {today} ===")

    for ticker, cfg in tickers.items():
        df = _get_extended_signals(ticker)
        df = df[df["DateDetected"].dt.date == today]
        if df.empty:
            continue

        print(f"\n{ticker}:")
        used_dates = set()

        # Paired Buy + Cover
        buys   = df[df["Action"] == "buy"]
        covers = df[df["Action"] == "cover"]
        for _, b in buys.iterrows():
            date = b["DateDetected"].date()
            if date in used_dates: continue
            match = covers[covers["DateDetected"].dt.date == date]
            if not match.empty:
                c = match.iloc[0]
                price = _fallback_price(ticker, date, b["LevelClose"] or c["LevelClose"])
                qty_b = calculate_shares(cfg["initialCapitalLong"],  price, cfg["order_round_factor"])
                qty_c = calculate_shares(cfg["initialCapitalShort"], price, cfg["order_round_factor"])
                qty = qty_b + qty_c
                print(f" BUY   {qty}@{price:.2f}")
                print(f"   → MARKET BUY {qty} @ {price:.2f}")
                print(f"   → LIMIT BUY  {qty} @ {price*1.002:.2f}")
                used_dates.add(date)


        # Paired Sell + Short
        sells  = df[df["Action"] == "sell"]
        shorts = df[df["Action"] == "short"]
        for _, s in sells.iterrows():
            date = s["DateDetected"].date()
            if date in used_dates: continue
            match = shorts[shorts["DateDetected"].dt.date == date]
            if not match.empty:
                sh = match.iloc[0]
                price = _fallback_price(ticker, date, sh["LevelClose"] or s["LevelClose"])
                qty_s  = calculate_shares(cfg["initialCapitalLong"],  price, cfg["order_round_factor"])
                qty_sh = calculate_shares(cfg["initialCapitalShort"], price, cfg["order_round_factor"])
                qty = qty_s + qty_sh
                print(f" SELL  {qty}@{price:.2f}")
                print(f"   → MARKET SELL {qty} @ {price:.2f}")
                print(f"   → LIMIT SELL  {qty} @ {price*0.998:.2f}")
                used_dates.add(date)

        # Einzelorders
        singles = df[df["DateDetected"].dt.date.isin([today]) & ~df["DateDetected"].dt.date.isin(used_dates)]
        for _, row in singles.iterrows():
            action = row["Action"]
            price = _fallback_price(ticker, today, row["LevelClose"])
            if action in ["buy", "sell"]:
                cap = cfg["initialCapitalLong"]
                factor = 1.002 if action == "buy" else 0.998
                side = "BUY" if action == "buy" else "SELL"
            elif action in ["short", "cover"]:
                cap = cfg["initialCapitalShort"]
                factor = 0.998 if action == "short" else 1.002
                side = "SELL" if action == "short" else "BUY"
            else:
                continue
            qty = calculate_shares(cap, price, cfg["order_round_factor"])
            print(f" {side:<5} {qty}@{price:.2f}")
            print(f"   → MARKET {side} {qty} @ {price:.2f}")
            print(f"   → LIMIT  {side} {qty} @ {price*factor:.2f}")

def run_daily_trading_cycle(ib):
    today = pd.Timestamp.today().strftime("%Y-%m-%d")
    print(f"\n=== DAILY TRADING CYCLE für {today} gestartet ===")

    print("\n→ Starte Backtesting für alle Ticker …")
    both_backtesting_multi(ib)

    print("\n→ Prüfe Extended-Signale für heute …")
    test_extended_for_date(today)

    print("\n→ Warte auf 15:45 NY-Zeit für automatische Orders …")
    wait_and_trade_at_1540(ib)

