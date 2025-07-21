import os
import sys
import datetime
import time
import logging
import builtins
from datetime import date as date_class

from scipy import stats
print = builtins.print
from builtins import AttributeError
import pandas as pd
import pandas_market_calendars as mcal
from ib_insync import Stock, MarketOrder, LimitOrder, StopOrder
from collections import namedtuple

# Definiere eine Struktur für gepaarte Trades
PairedTrade = namedtuple("PairedTrade",
    ["ticker","date","side","qty","entry_mkt","entry_lim","exit_sl","exit_tp","exit_mkt"]
)
# Handelskalender initialisieren (z.B. NYSE)
nyse = mcal.get_calendar("NYSE")
import numpy as np
from scipy.signal import argrelextrema
import mplfinance as mpf
from ib_insync import IB, Stock, LimitOrder
import time
import logging
from ib_insync import IB
import datetime
from zoneinfo import ZoneInfo
import plotly.graph_objs as go
from plotly.subplots import make_subplots
import pandas_market_calendars as mcal  # Am Anfang des Skripts einfügen
import yfinance as yf
import threading
price_event = threading.Event()
shared_price = {"price": None, "bid": None, "ask": None}
import plotly.io as pio
pio.renderers.default = "browser"
# Globale Parameter
ORDER_ROUND_FACTOR = 1
COMMISSION_RATE = 0.0018  # 0,18% des Umsatzes
MIN_COMMISSION = 1.0      # Mindestprovision
ORDER_SIZE = 100          # Standard-Ordergröße
backtesting_begin = 25      # z.B. 0 für Start bei 0%
backtesting_end = 98       # z.B. 50 für Ende bei 50%
# Logging konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
SIMULATE = False
TESTMODE = False
# =============================================================================
# 1. Historische Daten laden/aktualisieren (mindestens 365 Tage)
# =============================================================================
import os
import pandas as pd
from ib_insync import Stock

def update_historical_data_csv(ib, contract, fn):
    """
    Lädt oder aktualisiert die Tages-CSV (OHLCV).  
    Aktualisiert die heutige Zeile mit Realtime-/Minutedaten, falls bereits vorhanden.
    """
    import pandas as pd
    import os

    today = pd.Timestamp.now(tz=ZoneInfo("America/New_York")).normalize().tz_localize(None)

    # 1) CSV laden oder leeres Gerüst
    if os.path.exists(fn):
        df = pd.read_csv(fn, parse_dates=["date"], index_col="date")
    else:
        df = pd.DataFrame(columns=["Open","High","Low","Close","Volume"])

    # 2) Letzte Minute-Daten abrufen
    minute_df = get_today_minute_data(ib, contract)
    if minute_df is None or minute_df.empty:
        print(f"{contract.symbol}: Keine Minutedaten für heute.")
        return df

    o = minute_df["Open"].iloc[0]
    h = minute_df["High"].max()
    l = minute_df["Low"].min()
    c = minute_df["Close"].iloc[-1]
    v = minute_df["Volume"].sum()

    # 3) Heute existiert bereits → Überschreiben
    if today in df.index:
        print(f"{contract.symbol}: Ersetze Tagesdaten vom {today.date()} durch Minutedaten.")
    else:
        print(f"{contract.symbol}: Füge neuen Tag {today.date()} aus Minutedaten hinzu.")

    df.loc[today, ["Open","High","Low","Close","Volume"]] = [o, h, l, c, v]
    df.sort_index(inplace=True)
    df.to_csv(fn)

    return df


# =============================================================================
# 2. Support/Resistance und Trend
# =============================================================================
def calculate_support_resistance(df, past_window, trade_window):
    """
    Berechnet Support/Resistance basierend auf Close-Preisen.
    Ein Fenster von (past_window+trade_window) wird genutzt; zusätzlich werden das absolute Minimum und Maximum hinzugefügt.
    """
    total_window = int(past_window + trade_window)
    prices = df["Close"].values
    local_min_idx = argrelextrema(prices, np.less, order=total_window)[0]
    support = pd.Series(prices[local_min_idx], index=df.index[local_min_idx])
    local_max_idx = argrelextrema(prices, np.greater, order=total_window)[0]
    resistance = pd.Series(prices[local_max_idx], index=df.index[local_max_idx])
    absolute_low_date = df["Close"].idxmin()
    absolute_low = df["Close"].min()
    if absolute_low_date not in support.index:
        support = pd.concat([support, pd.Series([absolute_low], index=[absolute_low_date])])
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

# =============================================================================
# 3. Helper: Berechnung der Ordergröße (Shares)
# =============================================================================
def calculate_shares(capital, price, round_factor):
    """
    Berechnet die Anzahl der Shares als (Kapital / Preis)
    und rundet das Ergebnis auf das nächstgelegene Vielfache des round_factor.
    """
    raw = capital / price
    shares = round(raw / round_factor) * round_factor
    return shares

# =============================================================================
# 4. Standard-Signale zuordnen (Long und Short)
# =============================================================================
def assign_long_signals(support, resistance, data, trade_window, interval):
    """
    Ermittelt Standard-Long-Signale.
    Gibt ein DataFrame mit Spalten "Long" und "Long Date" zurück.
    """
    data.sort_index(inplace=True)
    sup_df = pd.DataFrame({'Date': support.index, 'Level': support.values, 'Type': 'support'})
    res_df = pd.DataFrame({'Date': resistance.index, 'Level': resistance.values, 'Type': 'resistance'})
    df = pd.concat([sup_df, res_df]).sort_values(by='Date').reset_index(drop=True)
    df['Long'] = None
    df['Long Date'] = pd.NaT
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
            raise ValueError(f"Unsupported interval: {interval}")
        if trade_date not in data.index:
            idx = data.index.searchsorted(trade_date)
            trade_date = data.index[idx] if idx < len(data.index) else pd.NaT
        # ...restlicher Code...
# ...existing code...
        if row['Type'] == 'support' and not long_active:
            df.at[i, 'Long'] = 'buy'
            # Cast auf tz-naive:
            try:
                trade_date = trade_date.tz_localize(None)
            except AttributeError:
                pass
            df.at[i, 'Long Date'] = trade_date
            long_active = True
        elif row['Type'] == 'resistance' and long_active:
            df.at[i, 'Long'] = 'sell'
            if hasattr(trade_date, 'tz_localize'):
                trade_date = trade_date.tz_localize(None)
            df.at[i, 'Long Date'] = trade_date
            long_active = False

    df['Date'] = pd.to_datetime(df['Date']).dt.tz_localize(None)
    df['Long Date'] = pd.to_datetime(df['Long Date'], errors='coerce').dt.tz_localize(None)
    return df

def assign_short_signals(support, resistance, data, trade_window, interval):
    data.sort_index(inplace=True)
    sup_df = pd.DataFrame({'Date': support.index, 'Level': support.values, 'Type': 'support'})
    res_df = pd.DataFrame({'Date': resistance.index, 'Level': resistance.values, 'Type': 'resistance'})
    df = pd.concat([sup_df, res_df]).sort_values(by='Date').reset_index(drop=True)
    df['Short'] = None
    df['Short Date'] = pd.NaT
    short_active = False
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
            raise ValueError(f"Unsupported interval: {interval}")
        if trade_date not in data.index:
            idx = data.index.searchsorted(trade_date)
            trade_date = data.index[idx] if idx < len(data.index) else pd.NaT
        # ...restlicher Code...
        if row['Type'] == 'resistance' and not short_active:
            df.at[i, 'Short'] = 'short'
            if hasattr(trade_date, 'tz_localize'):
                trade_date = trade_date.tz_localize(None)
            df.at[i, 'Short Date'] = trade_date
            short_active = True
        elif row['Type'] == 'support' and short_active:
            df.at[i, 'Short'] = 'cover'
            if hasattr(trade_date, 'tz_localize'):
                trade_date = trade_date.tz_localize(None)
            df.at[i, 'Short Date'] = trade_date
            short_active = False
    df['Date'] = pd.to_datetime(df['Date']).dt.tz_localize(None)
    df['Short Date'] = pd.to_datetime(df['Short Date'], errors='coerce').dt.tz_localize(None)
    return df

def is_trading_day(date):
    """
    Prüft, ob das gegebene Datum ein US-Handelstag ist (NYSE).
    date: pd.Timestamp (tz-naiv, Datumsteil)
    """
    schedule = nyse.schedule(start_date=date, end_date=date)
    return not schedule.empty

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


def assign_long_signals_extended(support, resistance, data, trade_window, interval):
    df = assign_long_signals(support, resistance, data, trade_window, interval).copy()
    df["Long Action"] = df["Long"]
    df.rename(columns={"Date": "Date high/low", "Level": "Level high/low", "Type": "Supp/Resist"}, inplace=True)
    df["Long Date detected"] = df["Date high/low"] + pd.Timedelta(days=trade_window)
    # Hier: Nur wenn der Wert vorhanden ist, wird get_next_trading_day aufgerufen
    df["Long Date detected"] = df["Long Date detected"].apply(
        lambda dt: get_next_trading_day(dt, data) if pd.notna(dt) else pd.NaT
    )
    df["Level Close"] = np.nan
    df["Long Trade Day"] = df["Long Date detected"].apply(
        lambda dt: dt.replace(hour=15, minute=50, second=0, microsecond=0) if pd.notna(dt) else pd.NaT
    )
    df["Level trade"] = np.nan
    df = df[["Date high/low", "Level high/low", "Supp/Resist", "Long Action",
             "Long Date detected", "Level Close", "Long Trade Day", "Level trade"]]
    return df


def assign_short_signals_extended(support, resistance, data, trade_window, interval):
    df = assign_short_signals(support, resistance, data, trade_window, interval).copy()
    df["Short Action"] = df["Short"]
    df.rename(columns={"Date": "Date high/low", "Level": "Level high/low", "Type": "Supp/Resist"}, inplace=True)
    df["Short Date detected"] = df["Date high/low"] + pd.Timedelta(days=trade_window)
    df["Short Date detected"] = df["Short Date detected"].apply(lambda dt: get_next_trading_day(dt, data))
    df["Level Close"] = np.nan
    df["Short Trade Day"] = df["Short Date detected"].apply(lambda dt: dt.replace(hour=15, minute=50, second=0, microsecond=0) if pd.notna(dt) else pd.NaT)
    df["Level trade"] = np.nan
    df = df[["Date high/low", "Level high/low", "Supp/Resist", "Short Action",
             "Short Date detected", "Level Close", "Short Trade Day", "Level trade"]]
    return df

def update_level_close_long(extended_df, market_df):
    closes = []
    for _, row in extended_df.iterrows():
        if pd.notna(row["Long Date detected"]):
            trade_day = row["Long Date detected"].normalize()
        else:
            trade_day = pd.NaT
        if pd.isna(trade_day):
            closes.append(np.nan)
        elif trade_day in market_df.index:
            closes.append(market_df.loc[trade_day, "Close"])
        else:
            idx = market_df.index.searchsorted(trade_day)
            closes.append(market_df.iloc[idx]["Close"] if idx < len(market_df.index) else np.nan)
    extended_df["Level Close"] = closes
    return extended_df

def update_level_close_short(extended_df, market_df):
    closes = []
    for _, row in extended_df.iterrows():
        if pd.notna(row["Short Date detected"]):
            trade_day = row["Short Date detected"].normalize()
        else:
            trade_day = pd.NaT
        if pd.isna(trade_day):
            closes.append(np.nan)
        elif trade_day in market_df.index:
            closes.append(market_df.loc[trade_day, "Close"])
        else:
            idx = market_df.index.searchsorted(trade_day)
            closes.append(market_df.iloc[idx]["Close"] if idx < len(market_df.index) else np.nan)
    extended_df["Level Close"] = closes
    return extended_df

# =============================================================================
# 7. Tradesimulation (Long und Short) mit dynamischer Ordergröße
# =============================================================================

def simulate_trades_compound_extended(extended_df, market_df, starting_capital=10000,
                                        commission_rate=COMMISSION_RATE, min_commission=MIN_COMMISSION,
                                        round_factor=ORDER_ROUND_FACTOR,
                                        artificial_close_price=None, artificial_close_date=None):
    """
    Simuliert Long‑Trades basierend auf den Extended-Long-Signalen.
    Ergänzt offene Trades mit künstlichem Close (z.B. 15:50).
    """
    extended_df = extended_df.sort_values(by="Long Date detected")
    capital = starting_capital
    position_active = False
    trades = []
    buy_price = buy_date = prev_cap = None
    for _, row in extended_df.iterrows():
        action = row.get('Long Action')
        exec_date = row.get('Long Date detected')
        if pd.isna(exec_date):
            continue
        if exec_date in market_df.index:
            price = float(market_df.loc[exec_date, "Close"])
        else:
            idx = market_df.index.searchsorted(exec_date)
            price = float(market_df.iloc[idx]["Close"]) if idx < len(market_df.index) else None
        if price is None:
            continue
        if action == 'buy' and not position_active:
            shares = calculate_shares(capital, price, round_factor)
            if shares < 1e-6:
                continue
            buy_price = price
            buy_date = exec_date
            position_active = True
            prev_cap = capital
        elif action == 'sell' and position_active:
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
    # Falls noch Position offen, mit künstlichem Close abschließen
    if position_active and artificial_close_price is not None and artificial_close_date is not None:
        sell_price = artificial_close_price
        sell_date = artificial_close_date
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
    return capital, trades
def simulate_short_trades_compound_extended(extended_df, market_df, starting_capital=10000,
                                             commission_rate=COMMISSION_RATE, min_commission=MIN_COMMISSION,
                                             round_factor=ORDER_ROUND_FACTOR,
                                             artificial_close_price=None, artificial_close_date=None):
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
    # Falls noch Position offen, mit künstlichem Close abschließen
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
                             commission_rate=COMMISSION_RATE, min_commission=MIN_COMMISSION,
                             round_factor=ORDER_ROUND_FACTOR):
    """
    Simuliert Long‑Trades mit dynamischer Ordergröße.
    
    Für jede Zeile des Signal-DataFrames:
      - Es wird der Preis zum Ausführungstermin ermittelt (als float).
      - Es werden Shares berechnet (Kapital/Preis) und auf den nächstgelegenen Wert gerundet.
      - Falls dabei 0 (oder ein vernachlässigbarer Wert) herauskommt, wird der Trade übersprungen.
      - Beim 'buy' wird eine Position eröffnet und beim 'sell' wieder geschlossen,
        wobei Gewinn, Turnover, Provision (fee) und pnl berechnet werden.
      
    Gibt das finale Kapital sowie eine Liste der Trades zurück.
    """
    capital = starting_capital
    position_active = False
    trades = []
    for _, row in signals_df.iterrows():
        signal = row.get('Long')
        exec_date = row.get('Long Date')
        if pd.isna(exec_date):
            continue
        # Preis ermitteln und als float interpretieren:
        if exec_date in market_df.index:
            price = float(market_df.loc[exec_date, "Close"])
        else:
            idx = market_df.index.searchsorted(exec_date)
            price = float(market_df.iloc[idx]["Close"]) if idx < len(market_df.index) else None
        if price is None:
            continue
        if signal == 'buy' and not position_active:
            shares = calculate_shares(capital, price, round_factor)
            # Falls shares (oder ein kleiner Schwellenwert) nicht signifikant > 0 sind, überspringen.
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
                                  commission_rate=COMMISSION_RATE, min_commission=MIN_COMMISSION,
                                  round_factor=ORDER_ROUND_FACTOR):
    """
    Simuliert Short‑Trades mit dynamischer Ordergröße.
    
    Für jede Zeile des Signal-DataFrames:
      - Ermittelt den Preis zum Ausführungstermin (als float).
      - Berechnet die zu handelnden Shares (Kapital / Preis) anhand eines Rundungsfaktors.  
      - Falls das Ergebnis vernachlässigbar (also 0) ist, wird der Trade übersprungen.
      - Beim 'short' wird die Short-Position eröffnet und beim 'cover' geschlossen.
      - Es werden Gewinn, Turnover, Provision (fee) und pnl berechnet.
      
    Gibt das finale Kapital und eine Liste der durchgeführten Short-Trades zurück.
    """
    capital = starting_capital
    position_active = False
    trades = []
    for _, row in signals_df.iterrows():
        signal = row.get('Short')
        exec_date = row.get('Short Date')
        if pd.isna(exec_date):
            continue
        # Preis ermitteln als float:
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
                continue  # Überspringe Trade, falls keine signifikante Anzahl an Shares berechnet wurde
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






# =============================================================================
# 8. Plotten des Candlestick-Charts
# =============================================================================
def plot_chart(csv_filename, past_window=5, trade_window=1, trend_window=20):
    df = pd.read_csv(csv_filename, parse_dates=['date'], index_col='date')
    df.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close'}, inplace=True)
    if 'Volume' not in df.columns:
        df['Volume'] = 0
    supp, res = calculate_support_resistance(df, past_window, trade_window)
    trend = compute_trend(df, window=trend_window)
    supp = supp.reindex(df.index)
    res = res.reindex(df.index)
    ap_support = mpf.make_addplot(supp, type='scatter', markersize=30, marker='o', color='green')
    ap_resistance = mpf.make_addplot(res, type='scatter', markersize=30, marker='o', color='red')
    ap_trend = mpf.make_addplot(trend, type='line', color='blue')
    add_plots = [ap_support, ap_resistance, ap_trend]
    mpf.plot(df, type='candle', style='charles', volume=True, addplot=add_plots,
             title='Candlestick Chart mit Support/Resistance und Trend')

# =============================================================================
# 10. Multi-Ticker Modi
# =============================================================================
# Hier haben wir die Ticker-Konfiguration überarbeitet.
# Jeder Ticker ist nun ein Dictionary, das Flags und separate Anfangskapitalwerte für Long und Short enthält.
tickers = {
    "AAPL": {"symbol": "AAPL", "long": True, "short": True, "initialCapitalLong": 1000, "initialCapitalShort": 1000, "order_round_factor":1},
    "GOOGL": {"symbol": "GOOGL", "long": True, "short": False, "initialCapitalLong": 1200, "initialCapitalShort": 0, "order_round_factor":1},
    "NVDA": {"symbol": "NVDA", "long": True, "short": True, "initialCapitalLong": 1800, "initialCapitalShort": 1500, "order_round_factor":1},
    "MSFT": {"symbol": "MSFT", "long": True, "short": True, "initialCapitalLong": 1100, "initialCapitalShort": 1100, "order_round_factor":1},
    "META":  {"symbol": "META",  "long": True, "short": True, "initialCapitalLong": 1000,  "initialCapitalShort": 1000, "order_round_factor":1},
    "AMD": {"symbol": "AMD",  "long": True, "short": True, "initialCapitalLong": 1000,  "initialCapitalShort": 1000, "order_round_factor":1},
    "AMD": {"symbol": "AMD",  "long": True, "short": True, "initialCapitalLong": 1000,  "initialCapitalShort": 1000, "order_round_factor":1},
    "QBTS": {"symbol": "QBTS",  "long": True, "short": True, "initialCapitalLong": 1000,  "initialCapitalShort": 1000, "order_round_factor":1},
    "TSLA": {"symbol": "TSLA",  "long": True, "short": True, "initialCapitalLong": 1000,  "initialCapitalShort": 1000, "order_round_factor":1},
    "MRNA": {"symbol": "MRNA",  "long": True, "short": True, "initialCapitalLong": 1000,  "initialCapitalShort": 1000, "order_round_factor":1},
    "NFLX": {"symbol": "NFLX",  "long": True, "short": True, "initialCapitalLong": 1500,  "initialCapitalShort": 1500, "order_round_factor":1},
    "AMZN": {"symbol": "AMZN",  "long": True, "short": True, "initialCapitalLong": 1000,  "initialCapitalShort": 1000, "order_round_factor":1},
    "INTC": {"symbol": "INTC",  "long": True, "short": True, "initialCapitalLong": 1000,  "initialCapitalShort": 1000, "order_round_factor":1},
    "BRRR": {"symbol": "BRRR",  "long": True, "short": True, "initialCapitalLong": 1000,  "initialCapitalShort": 1000, "order_round_factor":1},
    "QUBT": {"symbol": "QUBT", "long": True, "short": True, "initialCapitalLong": 2000,  "initialCapitalShort": 2000, "order_round_factor":10}
}

def plot_optimal_trades_multi(ticker, ib):
    # Ticker-Konfiguration abrufen
    config = tickers[ticker]  # z. B. config = tickers["AAPL"]

    csv_filename = f"{ticker}_data.csv"
    contract = Stock(config["symbol"], "SMART", "USD")
    
    # Lese oder lade Daten
    if os.path.exists(csv_filename):
        df = pd.read_csv(csv_filename, parse_dates=["date"], index_col="date")
        df.sort_index(inplace=True)
        df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close"}, inplace=True)
    else:
        df = update_historical_data_csv(ib, contract, csv_filename)
        df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close"}, inplace=True)
    
    if "Volume" not in df.columns:
        df["Volume"] = 0

    # ----------------------------
    # Backtesting Long-Trades
        # ----------------------------
    best_p_long, best_tw_long = berechne_best_p_tw_long(df, config, backtesting_begin, backtesting_end)
    best_sup_long, best_res_long = calculate_support_resistance(df, best_p_long, best_tw_long)
    standard_long = assign_long_signals(best_sup_long, best_res_long, df, best_tw_long, "1d")
    
    # Extended Long-Signale nutzen und aktualisieren
    extended_long = assign_long_signals_extended(best_sup_long, best_res_long, df, best_tw_long, "1d")
    extended_long = update_level_close_long(extended_long, df)
    round_factor_long = config.get("order_round_factor", ORDER_ROUND_FACTOR)
    long_cap, long_trades = simulate_trades_compound_extended(
        extended_long, df,
        starting_capital=config["initialCapitalLong"],
        commission_rate=COMMISSION_RATE,
        min_commission=MIN_COMMISSION,
        round_factor=round_factor_long
    )
    
    print(f"\nBeste Parameter (Long) für {config['symbol']}: past_window={best_p_long}, trade_window={best_tw_long}, Final Capital (Long)={long_cap:.2f}")
    
    # ----------------------------
    # Backtesting Short-Trades
    # ----------------------------
    best_p_short, best_tw_short = berechne_best_p_tw_short(df, config, backtesting_begin, backtesting_end)
    best_sup_short, best_res_short = calculate_support_resistance(df, best_p_short, best_tw_short)
    standard_short = assign_short_signals(best_sup_short, best_res_short, df, best_tw_short, "1d")
    
    # Extended Short-Signale nutzen und aktualisieren
    extended_short = assign_short_signals_extended(best_sup_short, best_res_short, df, best_tw_short, "1d")
    extended_short = update_level_close_short(extended_short, df)
    round_factor_short = config.get("order_round_factor", ORDER_ROUND_FACTOR)
    short_cap, short_trades = simulate_short_trades_compound_extended(
        extended_short, df,
        starting_capital=config["initialCapitalShort"],
        commission_rate=COMMISSION_RATE,
        min_commission=MIN_COMMISSION,
        round_factor=round_factor_short
    )
    
    print(f"Beste Parameter (Short) für {config['symbol']}: past_window={best_p_short}, trade_window={best_tw_short}, Final Capital (Short)={short_cap:.2f}")
    
    # ----------------------------
    # Zusätzliche Marker: 4 Arten (Buy, Sell, Short, Cover) mit vertikalen Offsets
    # ----------------------------
    # Definiere einen generellen Offset aufgrund der Preisspanne:
    offset = 0.02 * (df["Close"].max() - df["Close"].min())
    # Wir definieren separate Offsets für die Marker:
    buy_offset = 2*offset      # Buy-Marker sollen nach oben verschoben werden
    sell_offset = -2*offset    # Sell-Marker sollen nach unten verschoben werden
    short_offset = -offset   # Short-Marker sollen nach unten verschoben werden
    cover_offset = offset    # Cover-Marker sollen nach oben verschoben werden

    # Erstelle separate leere Serien für die Marker
    buy_marker = pd.Series(np.nan, index=df.index)
    sell_marker = pd.Series(np.nan, index=df.index)
    short_marker = pd.Series(np.nan, index=df.index)
    cover_marker = pd.Series(np.nan, index=df.index)
    
    # Für Long-Trades: Buy und Sell
    for _, row in standard_long.iterrows():
        if row["Long"] == "buy" and pd.notna(row["Long Date"]):
            buy_marker.loc[row["Long Date"]] = df.loc[row["Long Date"], "Close"] + buy_offset
        elif row["Long"] == "sell" and pd.notna(row["Long Date"]):
            sell_marker.loc[row["Long Date"]] = df.loc[row["Long Date"], "Close"] + sell_offset
    
    # Für Short-Trades: Short und Cover
    for _, row in standard_short.iterrows():
        if row.get("Short") == "short" and pd.notna(row["Short Date"]):
            short_marker.loc[row["Short Date"]] = df.loc[row["Short Date"], "Close"] + short_offset
        elif row.get("Short") == "cover" and pd.notna(row["Short Date"]):
            cover_marker.loc[row["Short Date"]] = df.loc[row["Short Date"], "Close"] + cover_offset
    
    # Definiere Add-Plots für die 4 Trade-Marker
    ap_buy = mpf.make_addplot(buy_marker, type="scatter", markersize=30, marker="^", color="red")
    ap_sell = mpf.make_addplot(sell_marker, type="scatter", markersize=30, marker="v", color="red")
    ap_short = mpf.make_addplot(short_marker, type="scatter", markersize=30, marker="v", color="blue")
    ap_cover = mpf.make_addplot(cover_marker, type="scatter", markersize=30, marker="^", color="blue")
    
    # Zusätzliche Marker: Support/Resistance und Trend
    best_p_long, best_tw_long =     (df, config, backtesting_begin, backtesting_end)
    best_sup_long, best_res_long = calculate_support_resistance(df, best_p_long, best_tw_long)
    ap_support = mpf.make_addplot(best_sup_long.reindex(df.index), type="scatter", markersize=30, marker="o", color="green")

    best_p_short, best_tw_short = berechne_best_p_tw_short(df, config, backtesting_begin, backtesting_end)
    best_sup_short, best_res_short = calculate_support_resistance(df, best_p_short, best_tw_short)
    ap_resistance = mpf.make_addplot(best_res_short.reindex(df.index), type="scatter", markersize=30, marker="o", color="red")
    ap_trend = mpf.make_addplot(compute_trend(df, 20), type="line", color="blue")
    
    # Alle Add-Plots zusammenführen
    add_plots = [ap_buy, ap_sell, ap_short, ap_cover, ap_support, ap_resistance, ap_trend]
    
    # Titel des Plots
    title_str = (f"{config['symbol']} Optimal Long: past_window={best_p_long}, trade_window={best_tw_long} "
                 f"(Cap={long_cap:.2f})\nOptimal Short: past_window={best_p_short}, trade_window={best_tw_short} "
                 f"(Cap={short_cap:.2f})")
    
    mpf.plot(df, type="candle", style="charles", volume=True, addplot=add_plots, title=title_str)
    
    # Konsolenausgabe
    print(f"\nTicker: {config['symbol']}")
    print("Matched Long Trades:")
    print(pd.DataFrame(long_trades).to_string(index=False))
    # Statistik-Printout einfügen:
    if isinstance(long_trades, pd.DataFrame):
        stats(long_trades.to_dict("records"), "Long")
    else:
        stats(long_trades, "Long")
    print(stats(long_trades, "Long Trades"))
    print("Matched Short Trades:")
    print(pd.DataFrame(short_trades).to_string(index=False))
  # Statistik-Printout einfügen:
    if isinstance(short_trades, pd.DataFrame):
        stats(short_trades.to_dict("records"), "Short")
    else:
        stats(short_trades, "Short")
    print(stats(short_trades, "Short Trades"))#.to_string())
    print("Extended Long Signals:")
    print(extended_long.to_string(index=False))
    print("Extended Short Signals:")
    print(extended_short.to_string(index=False))
def match_trades(raw_trades, side="long"):
    """
    Paart Entry- und Exit-​Trades FIFO-mäßig.
    side = "long" für buy→sell, "short" für short→cover.
    Erwartet:
      raw_trades: Liste von dicts mit
        - bei long:  buy_date, buy_price  und sell_date, sell_price
        - bei short: short_date, short_price und cover_date, cover_price
    Liefert: Liste gepaarter Trades als dict.
    """
    paired = []
    buffer = []

    if side == "long":
        entry_key, exit_key = "buy_date", "sell_date"
        entry_pr, exit_pr = "buy_price", "sell_price"
    else:
        entry_key, exit_key = "short_date", "cover_date"
        entry_pr, exit_pr = "short_price", "cover_price"

    # FIFO nach Entry-Datum sortieren
    raw_trades = sorted(
        raw_trades,
        key=lambda t: t.get(entry_key) or t.get(exit_key)
    )

    for tr in raw_trades:
        # Wenn ein Entry-Trade
        if tr.get(entry_key) is not None and tr.get(entry_pr) is not None:
            buffer.append(tr)
        # Wenn ein Exit-Trade
        elif tr.get(exit_key) is not None and tr.get(exit_pr) is not None:
            if buffer:
                op = buffer.pop(0)
                paired.append({
                    entry_key:    op[entry_key],
                    exit_key:     tr[exit_key],
                    "shares":     op["shares"],
                    entry_pr:     op[entry_pr],
                    exit_pr:      tr[exit_pr],
                    "fee_entry":  op.get("fee", 0),
                    "fee_exit":   tr.get("fee", 0),
                    "pnl":        tr.get("pnl", op.get("pnl"))
                })
    return paired

import sys
import os
import pandas as pd
import matplotlib.pyplot as plt
from ib_insync import IB, Stock, MarketOrder, LimitOrder
from datetime import datetime, date

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


# ──────────────────────────────────────────────────────────────────────────────
# 1) Dein unverändertes both_backtesting_multi-Modul mit Speicher-Endstück
# ──────────────────────────────────────────────────────────────────────────────
def both_backtesting_multi(ib):
    for ticker, config in tickers.items():
        print(f"\n=================== Backtesting für {ticker} ===================")

        # CSV laden oder aktualisieren
        filename = f"{ticker}_data.csv"
        contract = Stock(config["symbol"], "SMART", "USD")
        df = update_historical_data_csv(ib, contract, filename)
        df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close"}, inplace=True)
        df.sort_index(inplace=True)

        # Letzter Preis für künstlichen Close
        artificial_close_date  = df.index[-1]
        artificial_close_price = df.loc[artificial_close_date, "Close"]

        # Long-Trading
        if config.get("long", False):
            best_p_long, best_tw_long = berechne_best_p_tw_long(df, config, backtesting_begin, backtesting_end)
            sup_long, res_long = calculate_support_resistance(df, best_p_long, best_tw_long)
            std_long = assign_long_signals(sup_long, res_long, df, best_tw_long, "1d")
            ext_long = assign_long_signals_extended(sup_long, res_long, df, best_tw_long, "1d")
            ext_long = update_level_close_long(ext_long, df)

            rf_long = config.get("order_round_factor", ORDER_ROUND_FACTOR)
            long_cap, long_trades = simulate_trades_compound_extended(
                ext_long, df,
                config["initialCapitalLong"], COMMISSION_RATE, MIN_COMMISSION,
                rf_long,
                artificial_close_price, artificial_close_date
            )
            equity_long = compute_equity_curve(df, long_trades, config["initialCapitalLong"], long=True)
        else:
            ext_long = pd.DataFrame()
            std_long = pd.DataFrame()
            long_trades = []
            long_cap = config["initialCapitalLong"]
            equity_long = [long_cap] * len(df)

        # Short-Trading
        if config.get("short", False):
            best_p_short, best_tw_short = berechne_best_p_tw_short(df, config, backtesting_begin, backtesting_end)
            sup_short, res_short = calculate_support_resistance(df, best_p_short, best_tw_short)
            std_short = assign_short_signals(sup_short, res_short, df, best_tw_short, "1d")
            ext_short = assign_short_signals_extended(sup_short, res_short, df, best_tw_short, "1d")
            ext_short = update_level_close_short(ext_short, df)

            rf_short = config.get("order_round_factor", ORDER_ROUND_FACTOR)
            short_cap, short_trades = simulate_short_trades_compound_extended(
                ext_short, df,
                config["initialCapitalShort"], COMMISSION_RATE, MIN_COMMISSION,
                rf_short,
                artificial_close_price, artificial_close_date
            )
            equity_short = compute_equity_curve(df, short_trades, config["initialCapitalShort"], long=False)
        else:
            ext_short = pd.DataFrame()
            std_short = pd.DataFrame()
            short_trades = []
            short_cap = config["initialCapitalShort"]
            equity_short = [short_cap] * len(df)

        # Equity-Kombi + Buy & Hold
        equity_combined = [l + s for l, s in zip(equity_long, equity_short)]
        buyhold = [config["initialCapitalLong"] * (p / df["Close"].iloc[0]) for p in df["Close"]]

        # Speicherung
        if not ext_long.empty:
            ext_long.to_csv(f"extended_Long_signals_{ticker}.csv", index=False)
        if not ext_short.empty and "Short Action" in ext_short.columns:
            ext_short.to_csv(f"extended_Short_signals_{ticker}.csv", index=False)
        pd.DataFrame(long_trades).to_csv(f"trades_long_{ticker}.csv", index=False)
        pd.DataFrame(short_trades).to_csv(f"trades_short_{ticker}.csv", index=False)

        print(f"{ticker}: Extended-Signale & Trades gespeichert.")

        # 📊 Stats + Matched + Extended-Ausgabe
        print(f"\n📊 Trade-Statistiken für {ticker}")
        stats(long_trades, f"{ticker} – Long")
        stats(short_trades, f"{ticker} – Short")

        matched_long = match_trades(long_trades, side="long")
        matched_short = match_trades(short_trades, side="short")
        print("\nMatched Long Trades:")
        print(pd.DataFrame(matched_long).to_string(index=False))
        print("\nMatched Short Trades:")
        print(pd.DataFrame(matched_short).to_string(index=False))

        print("\nExtended Long Signals:")
        print(ext_long.to_string(index=False))
        print("\nExtended Short Signals:")
        print(ext_short.to_string(index=False))

        # 📈 Visualisierung
        plot_combined_chart_and_equity(
            df, std_long, std_short,
            sup_long, res_short,
            compute_trend(df, 20),
            equity_long, equity_short,
            equity_combined, buyhold,
            ticker
        )
        plt.show()


import plotly.graph_objs as go
def plot_equity_curves_and_stats(df, long_trades, short_trades, ticker, start_capital_long, start_capital_short):
    import plotly.graph_objs as go
    import numpy as np

    df = df.sort_index()
    dates = df.index

    # --- Long Equity-Kurve: folgt Ticker nur wenn investiert ---
    equity_long = []
    cap = start_capital_long
    pos = 0
    entry_price = 0
    trade_idx = 0
    trades = long_trades
    equity_val = cap
    for date in dates:
        # Einstieg?
        if trade_idx < len(trades) and 'buy_date' in trades[trade_idx] and trades[trade_idx]['buy_date'] == date:
            pos = trades[trade_idx]['shares']
            entry_price = trades[trade_idx]['buy_price']
        # Ausstieg?
        if trade_idx < len(trades) and 'sell_date' in trades[trade_idx] and trades[trade_idx]['sell_date'] == date:
            cap += trades[trade_idx]['pnl']
            pos = 0
            entry_price = 0
            trade_idx += 1
        # Equity-Berechnung
        if pos > 0:
            equity_val = cap + pos * (df.loc[date, "Close"] - entry_price)
        else:
            equity_val = cap
        equity_long.append(equity_val)

    # --- Short Equity-Kurve: folgt Ticker nur wenn investiert ---
    equity_short = []
    cap = start_capital_short
    pos = 0
    entry_price = 0
    trade_idx = 0
    trades = short_trades
    equity_val = cap
    for date in dates:
        # Einstieg?
        if trade_idx < len(trades) and 'short_date' in trades[trade_idx] and trades[trade_idx]['short_date'] == date:
            pos = trades[trade_idx]['shares']
            entry_price = trades[trade_idx]['short_price']
        # Ausstieg?
        if trade_idx < len(trades) and 'cover_date' in trades[trade_idx] and trades[trade_idx]['cover_date'] == date:
            cap += trades[trade_idx]['pnl']
            pos = 0
            entry_price = 0
            trade_idx += 1
        # Equity-Berechnung
        if pos > 0:
            equity_val = cap + pos * (entry_price - df.loc[date, "Close"])
        else:
            equity_val = cap
        equity_short.append(equity_val)

    # --- Combined Equity-Kurve ---
    equity_combined = [l + s for l, s in zip(equity_long, equity_short)]

    # --- Buy & Hold ---
    buyhold = [start_capital_long * (p / df["Close"].iloc[0]) for p in df["Close"]]

    # --- Plotly-Chart ---
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dates, y=equity_long, mode='lines', name='Long Equity'))
    fig.add_trace(go.Scatter(x=dates, y=equity_short, mode='lines', name='Short Equity'))
    fig.add_trace(go.Scatter(x=dates, y=equity_combined, mode='lines', name='Combined'))
    fig.add_trace(go.Scatter(x=dates, y=buyhold, mode='lines', name='Buy & Hold'))

    fig.update_layout(title=f"Equity Curves für {ticker}",
                     xaxis_title="Datum",
                     yaxis_title="Kapital",
                     legend=dict(x=0, y=1.1, orientation="h"))
    print(f"\n📊 Trade-Statistiken für {ticker}")
    stats(long_trades, f"{ticker} – Long Trades")
    stats(short_trades, f"{ticker} – Short Trades")

    matched_long  = match_trades(long_trades, side="long")
    matched_short = match_trades(short_trades, side="short")
    print("\nMatched Long Trades:")
    print(pd.DataFrame(matched_long).to_string(index=False))
    print("Matched Short Trades:")
    print(pd.DataFrame(matched_short).to_string(index=False))

    # CSV-Export optional
    pd.DataFrame(matched_long).to_csv(f"matched_trades_long_{ticker}.csv", index=False)
    pd.DataFrame(matched_short).to_csv(f"matched_trades_short_{ticker}.csv", index=False)

    # Heutige Extended-Signale direkt sichten
    today = pd.Timestamp.today().date()
    extended_signals = _get_extended_signals(ticker)
    today_ext = extended_signals[extended_signals["DateDetected"].dt.date == today]
    if not today_ext.empty:
        print(f"\n📈 EXTENDED TRADES heute ({ticker}):")
        print(today_ext.to_string(index=False))
    else:
        print(f"\n— Keine Extended Trades heute für {ticker}")

    fig.show()

def stats(trades, name):
    # Akzeptiere DataFrame oder Liste von Dicts
    if isinstance(trades, pd.DataFrame):
        if trades.empty or 'pnl' not in trades.columns:
            print(f"\n{name}: Keine Trades.")
            return
        pnls = trades['pnl'].values
    elif isinstance(trades, list):
        if not trades or 'pnl' not in trades[0]:
            print(f"\n{name}: Keine Trades.")
            return
        pnls = [t['pnl'] for t in trades]
    else:
        print(f"\n{name}: Keine Trades.")
        return

    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    print(f"\n{name}:")
    print(f"  Anzahl Trades: {len(pnls)}")
    print(f"  Summe PnL: {sum(pnls):.2f}")
    print(f"  Ø PnL: {np.mean(pnls):.2f}")
    print(f"  Max PnL: {np.max(pnls):.2f}")
    print(f"  Min PnL: {np.min(pnls):.2f}")
    print(f"  Winning Trades: {len(wins)} ({len(wins)/len(pnls)*100:.1f}%)")
    print(f"  Losing Trades: {len(losses)} ({len(losses)/len(pnls)*100:.1f}%)")



#   print(f"\nBuy & Hold: Start={buyhold[0]:.2f}, Ende={buyhold[-1]:.2f}, Rendite={(buyhold[-1]/buyhold[0]-1)*100:.2f}%")
#    print(f"Combined: Start={equity_combined[0]:.2f}, Ende={equity_combined[-1]:.2f}, Rendite={(equity_combined[-1]/equity_combined[0]-1)*100:.2f}%")


import matplotlib.pyplot as plt

def plot_equity_curve_and_stats(df, trades, ticker, start_capital=10000):
    # Equity-Kurve berechnen
    equity = [start_capital]
    for trade in trades:
        equity.append(equity[-1] + trade['pnl'])
    equity = equity[1:]  # Erste Zeile ist Startkapital
    trade_dates = [trade['sell_date'] if 'sell_date' in trade else trade['cover_date'] for trade in trades]
    # Plot
    plt.figure(figsize=(10, 5))
    plt.plot(trade_dates, equity, marker='o', label=f'Equity {ticker}')
    plt.title(f'Equity Curve {ticker}')
    plt.xlabel('Datum')
    plt.ylabel('Kapital')
    plt.legend()
    plt.grid()
    plt.show()
    # Statistiken
    print(f"\n=== Trade-Statistiken für {ticker} ===")
    pnls = [t['pnl'] for t in trades]
    print(f"Anzahl Trades: {len(trades)}")
    print(f"Summe PnL: {sum(pnls):.2f}")
    print(f"Ø PnL: {np.mean(pnls):.2f}")
    print(f"Max PnL: {np.max(pnls):.2f}")
    print(f"Min PnL: {np.min(pnls):.2f}")

# Beispiel: Nach dem Backtesting für alle Ticker
def show_all_equity_curves_and_stats():
    for ticker, config in tickers.items():
        csv_filename = f"{ticker}_data.csv"
        if os.path.exists(csv_filename):
            df = pd.read_csv(csv_filename, parse_dates=["date"], index_col="date")
            df.sort_index(inplace=True)
            df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close"}, inplace=True)
            # Beispiel: Long-Trades simulieren
            best_p_long, best_tw_long = berechne_best_p_tw_long(df, config, backtesting_begin, backtesting_end)
            best_sup_long, best_res_long = calculate_support_resistance(df, best_p_long, best_tw_long)
            sig = assign_long_signals(best_sup_long, best_res_long, df, best_tw_long, "1d")
            cap, trades = simulate_trades_compound(sig, df, starting_capital=config["initialCapitalLong"])
            #plot_equity_curve_and_stats(df, trades, ticker, start_capital=config["initialCapitalLong"])

# Am Ende von both_backtesting_multi(ib) oder als eigenen Modus aufrufen:
# show_all_equity_curves_and_stats()
def get_today_minute_data(ib, contract):
    """
    Holt die Minutendaten für den aktuellen Tag von IB.
    Gibt ein DataFrame mit Spalten open, high, low, close, volume zurück.
    """
    now = datetime.datetime.now(ZoneInfo("America/New_York"))
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_time = now.replace(hour=15, minute=45, second=0, microsecond=0)
    # Beide tz-naiv machen:
    today = today.replace(tzinfo=None)
    end_time = end_time.replace(tzinfo=None)
    bars = ib.reqHistoricalData(
        contract,
        endDateTime=end_time,
        durationStr="1 D",
        barSizeSetting="1 min",
        whatToShow="TRADES",
        useRTH=True
    )
    df = pd.DataFrame(bars)
    if df.empty:
        return None
    df['date'] = pd.to_datetime(df['date'])
    # Entferne Zeitzone (macht alles tz-naive)
    df['date'] = df['date'].dt.tz_localize(None)
    df.set_index('date', inplace=True)
    df = df[(df.index >= today) & (df.index <= end_time)]
    return df

def trading_multi(ib):
    print("=== Trading-Testlauf für Datum:", pd.Timestamp.now(tz=ZoneInfo("America/New_York")).normalize())
    for ticker, config in tickers.items():
        print(f"\n--- {ticker}: Starte Trading-Check ---")
        csv_filename = f"{ticker}_data.csv"
        contract = Stock(config["symbol"], "SMART", "USD")
        # Lade Tagesdaten
        if os.path.exists(csv_filename):
            daily_df = pd.read_csv(csv_filename, parse_dates=["date"], index_col="date")
            daily_df.sort_index(inplace=True)
            daily_df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close"}, inplace=True)
        else:
            print(f"{ticker}: Keine Tagesdaten gefunden, lade neu ...")
            daily_df = update_historical_data_csv(ib, contract, csv_filename)
            daily_df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close"}, inplace=True)

        # --- NEU: Fehlt ein Tag? Dann aktualisiere bis gestern ---
        today = pd.Timestamp.now(tz=ZoneInfo("America/New_York")).normalize().tz_localize(None)
        if not is_trading_day(today):
            print(f"{ticker}: {today.date()} ist kein Handelstag. Kein Update/Trade.")
            continue        
        yesterday = today - pd.Timedelta(days=1)
        last_daily = daily_df.index.max()
        if last_daily < yesterday:
            print(f"{ticker}: Aktualisiere Tagesdaten bis {yesterday.date()} ...")
            daily_df = update_historical_data_csv(ib, contract, csv_filename)
            daily_df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close"}, inplace=True)

        # Realtime-Kurs von IB holen (mit Fallback auf Yahoo)
        print(f"{ticker}: Fordere Realtime-Kurs an ...")
        last_price, bid, ask = get_realtime_price(ticker, contract, ib)
        print(f"{ticker}: Realtime-Kurse (inkl. Fallback): Last={last_price}, Bid={bid}, Ask={ask}")

        if last_price is None or last_price <= 0 or (hasattr(last_price, 'isnan') and last_price.isnan()):
            print(f"{ticker}: Kein Kurs verfügbar. Kein Trade.")
            continue

        # --- NEU: Füge Realtime-Kurs als neuen Tagesabschluss hinzu (nur wenn noch nicht vorhanden) ---
        if today not in daily_df.index:
            new_row = pd.DataFrame({
                "Open": last_price,
                "High": last_price,
                "Low": last_price,
                "Close": last_price,
                "Volume": 0
            }, index=[today])
            daily_df = pd.concat([daily_df, new_row])
            daily_df.sort_index(inplace=True)
            daily_df.to_csv(csv_filename, index_label="date")
            print(f"{ticker}: Realtime-Kurs als neuen Tagesabschluss für {today.date()} hinzugefügt.")

        # Support/Resistance berechnen (Debug)
        print(f"{ticker}: Berechne Support/Resistance ...")
        long_df = pd.DataFrame(daily_df)
        best_p_long, best_tw_long = berechne_best_p_tw_long(daily_df, config, backtesting_begin, backtesting_end)
        long_support, long_resistance = calculate_support_resistance(daily_df, best_p_long, best_tw_long)
        long_signals_df = assign_long_signals(long_support, long_resistance, daily_df, best_tw_long, "1d")

        # Prüfe, ob heute ein neues Signal entstanden ist
        long_today = long_signals_df[long_signals_df["Long Date"] == today]
        print(f"{ticker}: Long-Signale heute: {len(long_today)}")
        if not long_today.empty:
            last_long = long_today.iloc[-1]
            pos_long = sum(pos.position for pos in ib.positions() if pos.contract.symbol == ticker and pos.position > 0)
            shares = calculate_shares(config["initialCapitalLong"], last_price, config.get("order_round_factor", ORDER_ROUND_FACTOR))
            print(f"{ticker}: Signal={last_long['Long']}, Shares={shares}, Position={pos_long}")
            if last_long["Long"] == "buy" and pos_long == 0 and shares > 0:
                # Limit-Buy leicht über dem aktuellen Kurs
                limit_price = round(last_price * 1.001, 2)
                print(f"{ticker}: LIMIT BUY {shares} @ {limit_price}")
                order = LimitOrder("BUY", int(shares), limit_price, outsideRth=True)
                ib.placeOrder(contract, order)
            elif last_long["Long"] == "sell" and pos_long > 0 and shares > 0:
                # Limit-Sell leicht unter dem aktuellen Kurs
                limit_price = round(last_price * 0.999, 2)
                print(f"{ticker}: LIMIT SELL {shares} @ {limit_price}")
                order = LimitOrder("SELL", int(shares), limit_price, outsideRth=True)
                ib.placeOrder(contract, order)
        else:
            print(f"{ticker}: Kein Long-Trade heute.")

        # Gleiches für Short (optional)
        best_p_short, best_tw_short = berechne_best_p_tw_short(daily_df, config, backtesting_begin, backtesting_end)
        short_support, short_resistance = calculate_support_resistance(daily_df, best_p_short, best_tw_short)
        short_signals_df = assign_short_signals(short_support, short_resistance, daily_df, best_tw_short, "1d")

        short_today = short_signals_df[short_signals_df["Short Date"] == today]
        print(f"{ticker}: Short-Signale heute: {len(short_today)}")
        if not short_today.empty:
            last_short = short_today.iloc[-1]
            pos_short = sum(pos.position for pos in ib.positions() if pos.contract.symbol == ticker and pos.position < 0)
            shares = calculate_shares(config["initialCapitalShort"], last_price, config.get("order_round_factor", ORDER_ROUND_FACTOR))
            print(f"{ticker}: Signal={last_short['Short']}, Shares={shares}, Position={pos_short}")
            if last_short["Short"] == "short" and pos_short == 0 and shares > 0:
                # Limit-Short leicht unter dem aktuellen Kurs
                limit_price = round(last_price * 0.999, 2)
                print(f"{ticker}: LIMIT SHORT {shares} @ {limit_price}")
                order = LimitOrder("SELL", int(shares), limit_price, outsideRth=True)
                ib.placeOrder(contract, order)
            elif last_short["Short"] == "cover" and pos_short < 0 and shares > 0:
                # Limit-Cover leicht über dem aktuellen Kurs
                limit_price = round(last_price * 1.001, 2)
                print(f"{ticker}: LIMIT COVER {shares} @ {limit_price}")
                order = LimitOrder("BUY", int(shares), limit_price, outsideRth=True)
                ib.placeOrder(contract, order)
        else:
            print(f"{ticker}: Kein Short-Trade heute.")
            

    print("=== Trading-Testlauf für Datum:", pd.Timestamp.now(tz=ZoneInfo("America/New_York")).normalize())
    for ticker, config in tickers.items():
        print(f"\n--- {ticker}: Starte Trading-Check ---")
        csv_filename = f"{ticker}_data.csv"
        contract = Stock(config["symbol"], "SMART", "USD")
        # Lade Tagesdaten
        if os.path.exists(csv_filename):
            daily_df = pd.read_csv(csv_filename, parse_dates=["date"], index_col="date")
            daily_df.sort_index(inplace=True)
            daily_df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close"}, inplace=True)
        else:
            print(f"{ticker}: Keine Tagesdaten gefunden, lade neu ...")
            daily_df = update_historical_data_csv(ib, contract, csv_filename)
            daily_df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close"}, inplace=True)

        # --- NEU: Fehlt ein Tag? Dann aktualisiere bis gestern ---
        today = pd.Timestamp.now(tz=ZoneInfo("America/New_York")).normalize().tz_localize(None)
        if not is_trading_day(today):
            print(f"{ticker}: {today.date()} ist kein Handelstag. Kein Update/Trade.")
            continue        
        yesterday = today - pd.Timedelta(days=1)
        last_daily = daily_df.index.max()
        if last_daily < yesterday:
            print(f"{ticker}: Aktualisiere Tagesdaten bis {yesterday.date()} ...")
            daily_df = update_historical_data_csv(ib, contract, csv_filename)
            daily_df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close"}, inplace=True)

        # Realtime-Kurs von IB holen (mit Fallback auf Yahoo)
        print(f"{ticker}: Fordere Realtime-Kurs an ...")
        last_price, bid, ask = get_realtime_price(ticker, contract, ib)
        print(f"{ticker}: Realtime-Kurse (inkl. Fallback): Last={last_price}, Bid={bid}, Ask={ask}")

        if last_price is None or last_price <= 0 or (hasattr(last_price, 'isnan') and last_price.isnan()):
            print(f"{ticker}: Kein Kurs verfügbar. Kein Trade.")
            continue

        # --- NEU: Füge Realtime-Kurs als neuen Tagesabschluss hinzu (nur wenn noch nicht vorhanden) ---
        if today not in daily_df.index:
            new_row = pd.DataFrame({
                "Open": last_price,
                "High": last_price,
                "Low": last_price,
                "Close": last_price,
                "Volume": 0
            }, index=[today])
            daily_df = pd.concat([daily_df, new_row])
            daily_df.sort_index(inplace=True)
            daily_df.to_csv(csv_filename, index_label="date")
            print(f"{ticker}: Realtime-Kurs als neuen Tagesabschluss für {today.date()} hinzugefügt.")

        # Support/Resistance berechnen (Debug)
        print(f"{ticker}: Berechne Support/Resistance ...")
        best_p_long, best_tw_long = berechne_best_p_tw_long(daily_df, config, backtesting_begin, backtesting_end)
        long_support, long_resistance = calculate_support_resistance(daily_df, best_p_long, best_tw_long)
        long_signals_df = assign_long_signals(long_support, long_resistance, daily_df, best_tw_long, "1d")

        # Prüfe, ob heute ein neues Signal entstanden ist
        long_today = long_signals_df[long_signals_df["Long Date"] == today]
        print(f"{ticker}: Long-Signale heute: {len(long_today)}")
        if not long_today.empty:
            last_long = long_today.iloc[-1]
            pos_long = sum(pos.position for pos in ib.positions() if pos.contract.symbol == ticker and pos.position > 0)
            shares = calculate_shares(config["initialCapitalLong"], last_price, config.get("order_round_factor", ORDER_ROUND_FACTOR))
            print(f"{ticker}: Signal={last_long['Long']}, Shares={shares}, Position={pos_long}")
            if last_long["Long"] == "buy" and pos_long == 0 and shares > 0:
                print(f"{ticker}: MARKET BUY {shares} @ {last_price}")
                order1 = MarketOrder("BUY", int(shares))
                ib.placeOrder(contract, order1)
                time.sleep(2)  # Warte, damit Market Order ausgeführt wird
                # Limit-Order absichtlich NICHT im Spread, damit sie sichtbar bleibt
                limit_price = round(last_price * 0.995, 2)  # 0.5% unter Market
                print(f"{ticker}: LIMIT BUY {shares} @ {limit_price}")
                order2 = LimitOrder("BUY", int(shares), limit_price, tif="DAY")
                ib.placeOrder(contract, order2)
            elif last_long["Long"] == "sell" and pos_long > 0 and shares > 0:
                print(f"{ticker}: MARKET SELL {shares} @ {last_price}")
                order1 = MarketOrder("SELL", int(shares))
                ib.placeOrder(contract, order1)
                time.sleep(2)
                limit_price = round(last_price * 1.005, 2)  # 0.5% über Market
                print(f"{ticker}: LIMIT SELL {shares} @ {limit_price}")
                order2 = LimitOrder("SELL", int(shares), limit_price, tif="DAY")
                ib.placeOrder(contract, order2)
        else:
            print(f"{ticker}: Kein Long-Trade heute.")

        # Gleiches für Short (optional)
        best_p_short, best_tw_short = berechne_best_p_tw_short(daily_df, config, backtesting_begin, backtesting_end)
        short_support, short_resistance = calculate_support_resistance(daily_df, best_p_short, best_tw_short)
        short_signals_df = assign_short_signals(short_support, short_resistance, daily_df, best_tw_short, "1d")

        short_today = short_signals_df[short_signals_df["Short Date"] == today]
        print(f"{ticker}: Short-Signale heute: {len(short_today)}")
        if not short_today.empty:
            last_short = short_today.iloc[-1]
            pos_short = sum(pos.position for pos in ib.positions() if pos.contract.symbol == ticker and pos.position < 0)
            shares = calculate_shares(config["initialCapitalShort"], last_price, config.get("order_round_factor", ORDER_ROUND_FACTOR))
            print(f"{ticker}: Signal={last_short['Short']}, Shares={shares}, Position={pos_short}")
            if last_short["Short"] == "short" and pos_short == 0 and shares > 0:
                print(f"{ticker}: MARKET SHORT {shares} @ {last_price}")
                order1 = MarketOrder("SELL", int(shares))
                ib.placeOrder(contract, order1)
                time.sleep(2)
                limit_price = round(last_price * 1.005, 2)  # 0.5% über Market
                print(f"{ticker}: LIMIT SHORT {shares} @ {limit_price}")
                order2 = LimitOrder("SELL", int(shares), limit_price, tif="DAY")
                ib.placeOrder(contract, order2)
            elif last_short["Short"] == "cover" and pos_short < 0 and shares > 0:
                print(f"{ticker}: MARKET COVER {shares} @ {last_price}")
                order1 = MarketOrder("BUY", int(shares))
                ib.placeOrder(contract, order1)
                time.sleep(2)
                limit_price = round(last_price * 0.995, 2)  # 0.5% unter Market
                print(f"{ticker}: LIMIT COVER {shares} @ {limit_price}")
                order2 = LimitOrder("BUY", int(shares), limit_price, tif="DAY")
                ib.placeOrder(contract, order2)
        else:
            print(f"{ticker}: Kein Short-Trade heute.")

def daytrading_multi(ib, intervals=["5 mins", "15 mins", "30 mins", "1 hour"], days_back=10):
    """
    Lädt und speichert OHLCV-Daten für verschiedene Zeitintervalle für alle Ticker.
    Nutzt für das letzte Intervall den aktuellen Realtime-Kurs von IB (mit YF-Fallback).
    """
    for ticker, config in tickers.items():
        contract = Stock(config["symbol"], "SMART", "USD")
        for interval in intervals:
            # IB-Parameter
            bar_size = interval
            duration = f"{days_back} D"
            print(f"\n[{ticker}] Lade {bar_size} Daten für {duration} ...")
            bars = ib.reqHistoricalData(
                contract,
                endDateTime="",
                durationStr=duration,
                barSizeSetting=bar_size,
                whatToShow="TRADES",
                useRTH=True
            )
            df = pd.DataFrame(bars)
            if df.empty:
                print(f"Keine Daten für {ticker} ({bar_size}) erhalten.")
                continue
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            # Einheitliche Spaltennamen
            df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}, inplace=True)
            # Speichern
            fname = f"{ticker}_{bar_size.replace(' ', '').replace('hour','h').replace('min','m')}.csv"
            df.to_csv(fname)
            print(f"Gespeichert: {fname} ({len(df)} Zeilen)")

            # --- NEU: Realtime-Kurs für das aktuelle Intervall holen ---
            last_price, bid, ask = get_realtime_price(ticker, contract, ib)
            print(f"{ticker} ({interval}): Realtime-Kurse: Last={last_price}, Bid={bid}, Ask={ask}")

            # Intervall-String für Signalzuordnung anpassen
            interval_str = (
                bar_size.replace(" ", "")
                        .replace("mins", "min")
                        .replace("min", "min")
                        .replace("hour", "h")
            )
            # Beispiel: Berechne Support/Resistance und Signale
            if len(df) > 10:
                best_p_long, best_tw_long = berechne_best_p_tw_long(df, config, backtesting_begin, backtesting_end)
                best_sup_long, best_res_long = calculate_support_resistance(df, best_p_long, best_tw_long)
                sig_long = assign_long_signals(best_sup_long, best_res_long, df, best_tw_long, interval_str)
                best_p_short, best_tw_short = berechne_best_p_tw_short(df, config, backtesting_begin, backtesting_end)
                best_sup_short, best_res_short = calculate_support_resistance(df, best_p_short, best_tw_short)
                sig_short = assign_short_signals(best_sup_short, best_res_short, df, best_tw_short, interval_str)

                print(f"Long-Signale ({bar_size}):\n", sig_long.tail(3))
                print(f"Short-Signale ({bar_size}):\n", sig_short.tail(3))
                

def wait_and_trade_at_1540(ib):
    print("Warte auf 15:45 New York Zeit für Trading ... (Beenden mit STRG+C)")
    while True:
        now = datetime.datetime.now(ZoneInfo("America/New_York"))
        # Prüfe, ob es 15:40 <= jetzt < 15:50 ist (Trading-Fenster)
        if now.hour == 15 and 45 <= now.minute < 50 :
            print(f"{now.strftime('%Y-%m-%d %H:%M:%S')} NY: Starte Trading!")
            trading_multi(ib)
            # Warte bis nach 15:45, damit nicht mehrfach getradet wird
            while True:
                now2 = datetime.datetime.now(ZoneInfo("America/New_York"))
                if now2.minute >= 49 or now2.hour > 15:
                    break
                time.sleep(10)
            print("Trading abgeschlossen, warte auf nächsten Tag ...")
        else:
            # Noch nicht im Trading-Fenster, warte 30 Sekunden
            time.sleep(30)

def live_trading_loop(ib, intervals=["5 mins", "15 mins", "30 mins", "1 hour"], order_time="15:45"):
    """
    Hält die IB-Verbindung offen und prüft regelmäßig, ob ein neues Intervall abgeschlossen ist
    oder ob es Zeit für die End-of-Day-Order ist. Holt dann Daten und platziert ggf. Orders.
    """
    print("Starte Live-Trading-Loop. Beende mit STRG+C.")
    last_checked = {ticker: {iv: None for iv in intervals} for ticker in tickers}
    try:
        while True:
            now = datetime.datetime.now(ZoneInfo("America/New_York"))
            # --- End-of-Day-Trading um 15:50 ---
            if now.strftime("%H:%M") == order_time:
                print(f"\n[{now.strftime('%H:%M')}] Prüfe End-of-Day-Trading ...")
                trading_multi(ib)
                time.sleep(60)  # Warte eine Minute, um Doppel-Orders zu vermeiden

            # --- Daytrading für alle Intervalle ---
            for ticker, config in tickers.items():
                contract = Stock(config["symbol"], "SMART", "USD")
                for interval in intervals:
                    # Prüfe, ob ein neues Intervall abgeschlossen ist
                    if interval.endswith("mins"):
                        interv_min = int(interval.split()[0])
                        if now.minute % interv_min == 0 and (last_checked[ticker][interval] != now.replace(second=0, microsecond=0)):
                            print(f"\n[{now.strftime('%H:%M')}] {ticker}: Prüfe {interval} Intervall ...")
                            bars = ib.reqHistoricalData(
                                contract,
                                endDateTime="",
                                durationStr="2 D",
                                barSizeSetting=interval,
                                whatToShow="TRADES",
                                useRTH=True
                            )
                            df = pd.DataFrame(bars)
                            if not df.empty:
                                df['date'] = pd.to_datetime(df['date'])
                                df.set_index('date', inplace=True)
                                df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}, inplace=True)
                                best_p_long, best_tw_long = berechne_best_p_tw_long(df, config, backtesting_begin, backtesting_end)
                                best_sup_long, best_res_long = calculate_support_resistance(df, best_p_long, best_tw_long)
                                sig_long = assign_long_signals(best_sup_long, best_res_long, df, best_tw_long, replace(" ", ""))
                                best_p_short, best_tw_short = berechne_best_p_tw_short(df, config, backtesting_begin, backtesting_end)
                                best_sup_short, best_res_short = calculate_support_resistance(df, best_p_short, best_tw_short)
                                sig_short = assign_short_signals(best_sup_short, best_res_short, df, best_tw_short, replace(" ", ""))

                                print(f"Long-Signale ({interval}):\n", sig_long.tail(1))
                                print(f"Short-Signale ({interval}):\n", sig_short.tail(1))
                            last_checked[ticker][interval] = now.replace(second=0, microsecond=0)
                    elif interval.endswith("hour"):
                        if now.minute == 0 and (last_checked[ticker][interval] != now.replace(second=0, microsecond=0)):
                            print(f"\n[{now.strftime('%H:%M')}] {ticker}: Prüfe {interval} Intervall ...")
                            bars = ib.reqHistoricalData(
                                contract,
                                endDateTime="",
                                durationStr="2 D",
                                barSizeSetting=interval,
                                whatToShow="TRADES",
                                useRTH=True
                            )
                            df = pd.DataFrame(bars)
                            if not df.empty:
                                df['date'] = pd.to_datetime(df['date'])
                                df.set_index('date', inplace=True)
                                df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}, inplace=True)
                                best_p_long, best_tw_long = berechne_best_p_tw_long(df, config, backtesting_begin, backtesting_end)
                                best_sup_long, best_res_long = calculate_support_resistance(df, best_p_long, best_tw_long)
                                sig_long = assign_long_signals(best_sup_long, best_res_long, df, best_tw_long, replace(" ", ""))
                                best_p_short, best_tw_short = berechne_best_p_tw_short(df, config, backtesting_begin, backtesting_end)
                                best_sup_short, best_res_short = calculate_support_resistance(df, best_p_short, best_tw_short)
                                sig_short = assign_short_signals(best_sup_short, best_res_short, df, best_tw_short, replace(" ", ""))
                                print(f"Long-Signale ({interval}):\n", sig_long.tail(1))
                                print(f"Short-Signale ({interval}):\n", sig_short.tail(1))
                            last_checked[ticker][interval] = now.replace(second=0, microsecond=0)
            time.sleep(30)  # Prüfe alle 30 Sekunden
    except KeyboardInterrupt:
        print("Live-Trading-Loop beendet.")
        ib.disconnect()

def download_ib_minute_data(ib, symbol, exchange, currency, date, end_time="15:45:00", n_bars=100, filename=None):
    """
    Lädt n_bars Minutendaten für ein Symbol bis zu einer bestimmten Uhrzeit an einem Tag.
    Speichert als CSV, falls filename angegeben.
    Gibt ein DataFrame zurück oder None bei Fehler.
    """
    from ib_insync import Stock
    import pandas as pd
    import datetime

    contract = Stock(symbol, exchange, currency)
    if isinstance(date, str):
        date = datetime.datetime.strptime(date, "%Y-%m-%d").date()
    date_str = date.strftime("%Y%m%d")
    end_datetime = f"{date_str} {end_time}"

    # IB verlangt durationStr in Sekunden (z.B. "1200 S" für 20 Minuten)
    duration_seconds = n_bars * 60
    durationStr = f"{duration_seconds} S"

    print(f"Lade {n_bars} Minutendaten für {symbol} bis {end_time} am {date_str} ...")
    bars = ib.reqHistoricalData(
        contract,
        endDateTime=end_datetime,
        durationStr=durationStr,
        barSizeSetting="1 min",
        whatToShow="TRADES",
        useRTH=True
    )
    if not bars:
        print("Keine Daten erhalten. Prüfe Marktdaten-Abo und Datum.")
        return None

    df = pd.DataFrame(bars)
    if df.empty:
        print("Leeres DataFrame erhalten.")
        return None

    df['date'] = pd.to_datetime(df['date'])
    df['date'] = df['date'].dt.tz_localize(None)
    df.set_index('date', inplace=True)
    if filename:
        df.to_csv(filename)
        print(f"Gespeichert: {filename} ({len(df)} Zeilen)")
    return df

def get_minute_data_for_date(ib, contract, target_date):
    """
    Holt Minutendaten für einen bestimmten Tag.
    target_date: entweder ein datetime.date-Objekt oder ein String 'YYYYMMDD'.
    """
    # Wenn wir wirklich ein date-Objekt bekommen, formatiere es:
    if isinstance(target_date, date_class):
        date_str = target_date.strftime("%Y%m%d")
    else:
        date_str = str(target_date)

    end_time = f"{date_str} 15:45:00"
    bars = ib.reqHistoricalData(
        contract,
        endDateTime=end_time,
        durationStr="1 D",
        barSizeSetting="1 min",
        whatToShow="TRADES",
        useRTH=True
    )
    if not bars:
        logging.warning(f"Keine Minutendaten von IB für {contract.symbol} am {date_str}")
        return None

    df = pd.DataFrame(bars)
    df['date'] = pd.to_datetime(df['date']).dt.tz_localize(None)
    df.set_index('date', inplace=True)
    return df


def plot_combined_chart_and_equity(df, standard_long, standard_short, supp, res, trend, equity_long, equity_short, equity_combined, buyhold, ticker):
    # Marker-Serien erzeugen (wie in plot_optimal_trades_multi)
    offset = 0.02 * (df["Close"].max() - df["Close"].min())
    buy_offset = 2*offset
    sell_offset = -2*offset
    short_offset = -offset
    cover_offset = offset

    buy_marker = pd.Series(np.nan, index=df.index)
    sell_marker = pd.Series(np.nan, index=df.index)
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

    # Subplots: 2 rows, shared x
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05,
                        row_heights=[0.6, 0.4],
                        subplot_titles=(f"{ticker} Candlestick mit Markern", "Equity-Kurven"))

    # Candlestick
    fig.add_trace(go.Candlestick(
        x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
        name="Candlestick"
    ), row=1, col=1)

    # Marker als Scatter
    fig.add_trace(go.Scatter(x=buy_marker.index, y=buy_marker.values, mode='markers',
                             marker=dict(symbol='triangle-up', color='red', size=12), name='Buy'), row=1, col=1)
    fig.add_trace(go.Scatter(x=sell_marker.index, y=sell_marker.values, mode='markers',
                             marker=dict(symbol='triangle-down', color='red', size=12), name='Sell'), row=1, col=1)
    fig.add_trace(go.Scatter(x=short_marker.index, y=short_marker.values, mode='markers',
                             marker=dict(symbol='triangle-down', color='blue', size=12), name='Short'), row=1, col=1)
    fig.add_trace(go.Scatter(x=cover_marker.index, y=cover_marker.values, mode='markers',
                             marker=dict(symbol='triangle-up', color='blue', size=12), name='Cover'), row=1, col=1)
    # Support/Resistance
    # Saubere Marker für Support & Resistance (mit Reindexing & klarem Symbol)
    supp = supp.reindex(df.index)
    res  = res.reindex(df.index)

    fig.add_trace(go.Scatter(
        x=supp.dropna().index,
        y=supp.dropna().values,
        mode="markers",
        marker=dict(symbol="circle", color="limegreen", size=12, line=dict(width=1)),
        name="Support"
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=res.dropna().index,
        y=res.dropna().values,
        mode="markers",
        marker=dict(symbol="x", color="red", size=12, line=dict(width=1)),
        name="Resistance"
    ), row=1, col=1)

    # Trend
    fig.add_trace(go.Scatter(x=trend.index, y=trend.values, mode='lines', line=dict(color='black', width=2), name='Trend'), row=1, col=1)

    # Equity-Kurven
    fig.add_trace(go.Scatter(x=df.index, y=equity_long, mode='lines', name='Long Equity'), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=equity_short, mode='lines', name='Short Equity'), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=equity_combined, mode='lines', name='Combined'), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=buyhold, mode='lines', name='Buy & Hold'), row=2, col=1)

    #fig.update_layout(height=900, title=f"{ticker}: Candlestick & Equity-Kurven")
    fig.update_layout(
    height=900,
    title=f"{ticker}: Candlestick & Equity-Kurven",
        xaxis=dict(
            rangeslider=dict(visible=False)  # Kein Slider unter Chart 1
        ),
    xaxis2=dict(
        rangeslider=dict(
            visible=True,
            thickness=0.03,  # sehr dünn
            bgcolor="#eee"
        ),
        rangeselector=dict(
            buttons=[
                dict(count=1, label="1m", step="month", stepmode="backward"),
                dict(count=3, label="3m", step="month", stepmode="backward"),
                dict(count=6, label="6m", step="month", stepmode="backward"),
                dict(step="all")
            ]
        ),
        showline=True,
        showgrid=True,
    ),
    margin=dict(b=30, t=60),  # wenig Platz unten
)                                          
    fig.show()
# Beispiel-Funktion für deinen Preis-Thread
def yahoo_price_thread(symbol):
    import time
    while not price_event.is_set():
        # ...hole Preis von Yahoo...
        last_price, bid, ask = get_yf_price(symbol)
        if last_price is not None and last_price > 0:
            shared_price["price"] = last_price
            shared_price["bid"] = bid
            shared_price["ask"] = ask
            price_event.set()  # Thread kann jetzt stoppen!
            break
        time.sleep(1)

def get_yf_price(symbol):
    ticker = yf.Ticker(symbol)
    data = ticker.history(period="1d", interval="1m")
    if not data.empty:
        last_row = data.iloc[-1]
        last_price = last_row['Close']
        bid = last_price  # YF liefert kein Bid/Ask, nur Close
        ask = last_price
        return float(last_price), float(bid), float(ask)
    else:
        return None, None, None
def get_realtime_price(ticker, ib_contract, ib):
    # Versuche Preis von IB zu holen
    try:
        ticker_data = ib.reqMktData(ib_contract, '', False, False)
        ib.sleep(1)  # kurze Wartezeit für Daten
        last = ticker_data.last
        bid = ticker_data.bid
        ask = ticker_data.ask
        if last is not None:
            return float(last), float(bid), float(ask)
    except Exception as e:
        print(f"IB Preisfehler für {ticker}: {e}")
    # Fallback: Yahoo Finance
    last, bid, ask = get_yf_price(ticker)
    return last, bid, ask
def get_backtesting_slice(df, backtesting_begin=0, backtesting_end=50):
    n = len(df)
    start_idx = int(n * backtesting_begin / 100)
    end_idx = int(n * backtesting_end / 100)
    return df.iloc[start_idx:end_idx]

def berechne_best_p_tw_long(df, config, backtesting_begin=0, backtesting_end=20):
    df_opt = get_backtesting_slice(df, backtesting_begin, backtesting_end)
    #print(f"Optimierung Long von {df_opt.index.min().date()} bis {df_opt.index.max().date()} "      
    print(f"({len(df_opt)} Zeilen, {backtesting_begin}% bis {backtesting_end}% der Daten)")
    long_results = []
    for p in range(3, 10):
        for tw in range(1, 6):
            supp_temp, res_temp = calculate_support_resistance(df_opt, p, tw)
            sig = assign_long_signals(supp_temp, res_temp, df_opt, tw, "1d")
            cap, _ = simulate_trades_compound(
                sig, df_opt,
                starting_capital=config["initialCapitalLong"],
                commission_rate=COMMISSION_RATE,
                min_commission=MIN_COMMISSION,
                round_factor=config.get("order_round_factor", ORDER_ROUND_FACTOR)
            )
            long_results.append({"past_window": p, "trade_window": tw, "final_cap": cap})
    long_df = pd.DataFrame(long_results)
    best_long = long_df.loc[long_df["final_cap"].idxmax()]
    best_p_long = int(best_long["past_window"])
    best_tw_long = int(best_long["trade_window"])
    return best_p_long, best_tw_long

def berechne_best_p_tw_short(df, config, backtesting_begin=0, backtesting_end=20):
    df_opt = get_backtesting_slice(df, backtesting_begin, backtesting_end)
    #print(f"Optimierung Short von {df_opt.index.min().date()} bis {df_opt.index.max().date()} "
    print(f"({len(df_opt)} Zeilen, {backtesting_begin}% bis {backtesting_end}% der Daten)")
    short_results = []
    for p in range(3, 10):
        for tw in range(1, 4):
            supp_temp, res_temp = calculate_support_resistance(df_opt, p, tw)
            sig = assign_short_signals(supp_temp, res_temp, df_opt, tw, "1d")
            cap, _ = simulate_short_trades_compound(
                sig, df_opt,
                starting_capital=config["initialCapitalShort"],
                commission_rate=COMMISSION_RATE,
                min_commission=MIN_COMMISSION,
                round_factor=config.get("order_round_factor", ORDER_ROUND_FACTOR)
            )
            short_results.append({"past_window": p, "trade_window": tw, "final_cap": cap})
    short_df = pd.DataFrame(short_results)
    best_short = short_df.loc[short_df["final_cap"].idxmax()]
    best_p_short = int(best_short["past_window"])
    best_tw_short = int(best_short["trade_window"])
    return best_p_short, best_tw_short

import sys
import pandas as pd
from contextlib import contextmanager
from ib_insync import IB, Stock, MarketOrder, LimitOrder

@contextmanager
def _mute():
    import sys, os
    old = sys.stdout
    sys.stdout = open(os.devnull, 'w')
    try:
        yield
    finally:
        sys.stdout.close()
        sys.stdout = old


def _print(o, sym):
    tag = "Market" if isinstance(o, MarketOrder) else f"LMT@{o.lmtPrice:.2f}"
    print(f"   → {o.action:5} {o.totalQuantity:4d} of {sym} @ {tag}")

# ---------------------------------------------
# 1) Helfer: Alle Backtest-Trades einsammeln
# ---------------------------------------------
def collect_backtest_trades():
    """
    Führt both_backtesting_multi (ohne Prints) durch
    und gibt ein Dict zurück:
      { 'AAPL': { 'long': [trade_dicts], 'short': [trade_dicts] }, ... }
    """
    from collections import defaultdict
    trades_by_ticker = defaultdict(lambda: {"long": [], "short": []})

    for ticker, cfg in tickers.items():
        # Tages-CSV laden
        df = pd.read_csv(f"{ticker}_data.csv", parse_dates=["date"], index_col="date")
        df.rename(columns={"open":"Open","high":"High","low":"Low","close":"Close"}, inplace=True)
        df.sort_index(inplace=True)

        # Silent Optimization & Signals
        with _mute():
            p_l, tw_l = berechne_best_p_tw_long(df, cfg, backtesting_begin, backtesting_end)
            p_s, tw_s = berechne_best_p_tw_short(df, cfg, backtesting_begin, backtesting_end)
            sup, res  = calculate_support_resistance(df, p_l, tw_l)
            long_df   = assign_long_signals (sup, res, df, tw_l, "1d")
            short_df  = assign_short_signals(sup, res, df, tw_s, "1d")

            # Trades simulieren
            _, trades_l = simulate_trades_compound(long_df, df,
                                starting_capital=cfg["initialCapitalLong"],
                                commission_rate=COMMISSION_RATE,
                                min_commission=MIN_COMMISSION,
                                round_factor=cfg.get("order_round_factor",1))
            _, trades_s = simulate_short_trades_compound(short_df, df,
                                starting_capital=cfg["initialCapitalShort"],
                                commission_rate=COMMISSION_RATE,
                                min_commission=MIN_COMMISSION,
                                round_factor=cfg.get("order_round_factor",1))

        trades_by_ticker[ticker]["long"]  = trades_l
        trades_by_ticker[ticker]["short"] = trades_s

    return trades_by_ticker
def _print_order(order, symbol):
    """
    Gibt eine Order als lesbare Zeile aus.
    MarketOrder → Market, LimitOrder → LMT@xxx.xx
    """
    tag = "Market" if isinstance(order, MarketOrder) else f"LMT@{order.lmtPrice:.2f}"
    print(f"   → {order.action:5} {order.totalQuantity:4d} of {symbol} @ {tag}")

import os

def is_valid_csv(path):
    return os.path.exists(path) and os.path.getsize(path) > 50



# ---------------------------------------------
# 2) Test-Modus: Ausgeben dieser echten Trades
# ---------------------------------------------
import sys

# ──────────────────────────────────────────────────────────────────────────────
# TESTMODE: Nur printen der Trades für ein gegebenes Datum
# ──────────────────────────────────────────────────────────────────────────────
from pandas.errors import EmptyDataError
import pandas as pd

def test_trading_for_date(ib, date_str):
    today = pd.to_datetime(date_str).date()
    print(f"\n=== TESTMODE TRADES für {today} ===")

    for ticker, cfg in tickers.items():
        # 1) Trades laden
        try:
            trades_l = pd.read_csv(f"trades_long_{ticker}.csv",
                                   parse_dates=["buy_date","sell_date"])
        except (FileNotFoundError, EmptyDataError):
            trades_l = pd.DataFrame(columns=[
                "buy_date","sell_date","shares","buy_price","sell_price","fee","pnl"
            ])
        trades_l["buy_date"]  = pd.to_datetime(trades_l["buy_date"], errors="coerce")
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

        # 2) Filter auf heute
        buys   = trades_l[trades_l["buy_date"].dt.date  == today]
        sells  = trades_l[trades_l["sell_date"].dt.date == today]
        shorts = trades_s[trades_s["short_date"].dt.date == today]
        covers = trades_s[trades_s["cover_date"].dt.date == today]

        if buys.empty and sells.empty and shorts.empty and covers.empty:
            continue

        print(f"\n{ticker}:")
        used = set()

        # 3) PAIRED LONG: Buy + Cover zusammenlegen
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

        # 4) PAIRED SHORT: Sell + Short zusammenlegen
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

        # 5) Einzelorders BUY
        for _, b in buys.iterrows():
            if b["buy_date"] not in used:
                qty = int(b["shares"])
                price = b["buy_price"]
                print(f" BUY   {qty}@{price:.2f}")
                print(f"   → Market Buy  {qty} @ {price:.2f}")
                print(f"   → Limit Buy   {qty} @ {price * 1.002:.2f}")
                used.add(b["buy_date"])

        # 6) Einzelorders SELL
        for _, s in sells.iterrows():
            if s["sell_date"] not in used:
                qty = int(s["shares"])
                price = s["sell_price"]
                print(f" SELL  {qty}@{price:.2f}")
                print(f"   → Market Sell {qty} @ {price:.2f}")
                print(f"   → Limit Sell  {qty} @ {price * 0.998:.2f}")
                used.add(s["sell_date"])

        # 7) Einzelorders COVER
        for _, c in covers.iterrows():
            if c["cover_date"] not in used:
                qty = int(c["shares"])
                price = c["cover_price"]
                print(f" COVER {qty}@{price:.2f}")
                print(f"   → Market Buy  {qty} @ {price:.2f}")
                print(f"   → Limit Buy   {qty} @ {price * 1.002:.2f}")
                used.add(c["cover_date"])

        # 8) Einzelorders SHORT
        for _, sh in shorts.iterrows():
            if sh["short_date"] not in used:
                qty = int(sh["shares"])
                price = sh["short_price"]
                print(f" SHORT {qty}@{price:.2f}")
                print(f"   → Market Sell {qty} @ {price:.2f}")
                print(f"   → Limit Sell  {qty} @ {price * 0.998:.2f}")
                used.add(sh["short_date"])

# ──────────────────────────────────────────────────────────────────────────────
# 2) Testmodus: nur printen aus Extended-Signalen
# ──────────────────────────────────────────────────────────────────────────────
def test_from_extended_signals(date_str):
    today = pd.to_datetime(date_str).date()
    print(f"\n=== TESTMODE EXTENDED {today} ===")
    for ticker, cfg in tickers.items():
        long_csv  = f"extended_long_signals_{ticker}.csv"
        short_csv = f"extended_short_signals_{ticker}.csv"
        if not os.path.exists(long_csv) or not os.path.exists(short_csv):
            continue

        long_df  = pd.read_csv(long_csv,  parse_dates=["Long Date"])
        short_df = pd.read_csv(short_csv, parse_dates=["Short Date"])
        l = long_df [ long_df["Long Date"].dt.date  == today ]
        s = short_df[ short_df["Short Date"].dt.date == today ]
        if l.empty and s.empty:
            continue

        print(f"\n{ticker} → Signale für {today}:")
        paired = set()

        # PAIRED LONG
        for _, buy in l[l["Long Action"]=="buy"].iterrows():
            cov = s[(s["Short Action"]=="cover") & (s["Short Date"]==buy["Long Date"])]
            if not cov.empty:
                cov = cov.iloc[0]
                qty = int(cfg["initialCapitalLong"] // buy["Close"])
                print(f" PAIRED LONG {qty}@{buy['Close']:.2f} → {cov['Close']:.2f}")
                print(f"   → BUY   {qty} @ Market")
                print(f"   → BUY   {qty} @ LMT@{round(buy['Close']*1.002,2)}")
                print(f"   → SELL  {qty} @ Market")
                print(f"   → SELL  {qty} @ LMT@{round(cov['Close']*0.998,2)}")
                paired.add(buy["Long Date"])

        # PAIRED SHORT
        for _, sell in l[l["Long Action"]=="sell"].iterrows():
            sh = s[(s["Short Action"]=="short") & (s["Short Date"]==sell["Long Date"])]
            if not sh.empty:
                sh = sh.iloc[0]
                qty = int(cfg["initialCapitalShort"] // sh["Close"])
                print(f" PAIRED SHORT {qty}@{sh['Close']:.2f} → {sell['Close']:.2f}")
                print(f"   → SELL  {qty} @ Market")
                print(f"   → SELL  {qty} @ LMT@{round(sh['Close']*0.998,2)}")
                print(f"   → BUY   {qty} @ Market")
                print(f"   → BUY   {qty} @ LMT@{round(sell['Close']*1.002,2)}")
                paired.add(sell["Long Date"])

        # Einzelorders Long
        for _, row in l.iterrows():
            d = row["Long Date"]
            if d in paired: continue
            qty  = int(cfg["initialCapitalLong"]  // row["Close"])
            side = "BUY" if row["Long Action"]=="buy" else "SELL"
            lvl  = round(row["Close"] * (1.002 if side=="BUY" else 0.998), 2)
            print(f" {side:<5}{qty}@{row['Close']:.2f}")
            print(f"   → {side}   {qty} @ Market")
            print(f"   → {side}   {qty} @ LMT@{lvl}")

        # Einzelorders Short
        for _, row in s.iterrows():
            d = row["Short Date"]
            if d in paired: continue
            qty  = int(cfg["initialCapitalShort"] // row["Close"])
            side = "SELL" if row["Short Action"]=="short" else "BUY"
            lvl  = round(row["Close"] * (0.998 if side=="SELL" else 1.002), 2)
            print(f" {side:<5}{qty}@{row['Close']:.2f}")
            print(f"   → {side}   {qty} @ Market")
            print(f"   → {side}   {qty} @ LMT@{lvl}")



# ──────────────────────────────────────────────────────────────────────────────
# 3) Live-Trades: heute an IB, kein Datum-Parameter
# ──────────────────────────────────────────────────────────────────────────────
def trade_from_extended_signals(ib):
    today = date.today()
    print(f"\n=== TRADEMODE EXTENDED {today} ===")
    for ticker, cfg in tickers.items():
        contract = Stock(cfg["symbol"], cfg.get("exchange","SMART"), cfg.get("currency","USD"))
        long_csv  = f"extended_long_signals_{ticker}.csv"
        short_csv = f"extended_short_signals_{ticker}.csv"
        if not os.path.exists(long_csv) or not os.path.exists(short_csv):
            continue

        long_df  = pd.read_csv(long_csv,  parse_dates=["Long Date"])
        short_df = pd.read_csv(short_csv, parse_dates=["Short Date"])
        l = long_df [ long_df["Long Date"].dt.date  == today ]
        s = short_df[ short_df["Short Date"].dt.date == today ]
        if l.empty and s.empty:
            continue

        paired = set()
        def send(side, qty, price):
            ib.placeOrder(contract, MarketOrder(side, qty))
            lvl = round(price * (1.002 if side=="BUY" else 0.998), 2)
            ib.placeOrder(contract, LimitOrder(side, qty, lvl))

        # PAIRED LONG
        for _, buy in l[l["Long Action"]=="buy"].iterrows():
            cov = s[(s["Short Action"]=="cover") & (s["Short Date"]==buy["Long Date"])]
            if not cov.empty:
                cov = cov.iloc[0]
                qty = int(cfg["initialCapitalLong"] // buy["Close"])
                send("BUY",  qty, buy["Close"])
                send("SELL", qty, cov["Close"])
                paired.add(buy["Long Date"])

        # PAIRED SHORT
        for _, sell in l[l["Long Action"]=="sell"].iterrows():
            sh = s[(s["Short Action"]=="short") & (s["Short Date"]==sell["Long Date"])]
            if not sh.empty:
                sh  = sh.iloc[0]
                qty = int(cfg["initialCapitalShort"] // sh["Close"])
                send("SELL", qty, sh["Close"])
                send("BUY",  qty, sell["Close"])
                paired.add(sell["Long Date"])

        # Einzelorders Long & Short (wie oben) …
        for _, row in l.iterrows():
            d = row["Long Date"]
            if d in paired: continue
            side = "BUY" if row["Long Action"]=="buy" else "SELL"
            qty  = int(cfg["initialCapitalLong"]  // row["Close"])
            send(side, qty, row["Close"])
        for _, row in s.iterrows():
            d = row["Short Date"]
            if d in paired: continue
            side = "SELL" if row["Short Action"]=="short" else "BUY"
            qty  = int(cfg["initialCapitalShort"] // row["Close"])
            send(side, qty, row["Close"])

def process_trades(ib, date_str=None, live=False):
    """
    Wenn date_str=True: Testmodus für ein beliebiges Datum (print).
    Wenn date_str=None & live=True: Livemodus für HEUTE (order to IB).
    """
    # Datum bestimmen
    if date_str:
        today = pd.to_datetime(date_str).date()
        mode  = "TESTMODE"
    else:
        today = date.today()
        mode  = "TRADEMODE"

    print(f"\n=== {mode} TRADES für {today} ===")

    for ticker, cfg in tickers.items():
        # CSV-Dateinamen
        long_csv  = f"trades_long_{ticker}.csv"
        short_csv = f"trades_short_{ticker}.csv"
        # lade CSVs, wenn vorhanden
        trades_l = pd.read_csv(long_csv)  if os.path.exists(long_csv)  else pd.DataFrame()
        trades_s = pd.read_csv(short_csv) if os.path.exists(short_csv) else pd.DataFrame()
        if trades_l.empty and trades_s.empty:
            continue

        # Datumsspalten parsen
        for col in ["buy_date","sell_date"]:
            if col in trades_l: trades_l[col] = pd.to_datetime(trades_l[col], errors="coerce")
        for col in ["short_date","cover_date"]:
            if col in trades_s: trades_s[col] = pd.to_datetime(trades_s[col], errors="coerce")

        # Filter
        buys   = trades_l[ trades_l["buy_date"].dt.date  == today ]
        sells  = trades_l[ trades_l["sell_date"].dt.date == today ]
        shorts = trades_s[ trades_s["short_date"].dt.date== today ]
        covers = trades_s[ trades_s["cover_date"].dt.date== today ]

        if buys.empty and sells.empty and shorts.empty and covers.empty:
            continue

        print(f"\n{ticker}:")
        used = set()

        # Pair Long: buy + cover
        for _, b in buys.iterrows():
            c = covers[ covers["cover_date"].dt.date == b["buy_date"].date() ]
            if not c.empty and b["buy_date"] not in used:
                cov = c.iloc[0]
                qty = int(b["shares"])
                _do("BUY",  qty, b["buy_price"])
                _do("SELL", qty, cov["cover_price"])
                used.add(b["buy_date"])

        # Pair Short: sell + short
        for _, s in sells.iterrows():
            sh = shorts[ shorts["short_date"].dt.date == s["sell_date"].date() ]
            if not sh.empty and s["sell_date"] not in used:
                sho = sh.iloc[0]
                qty = int(s["shares"])
                _do("SELL", qty, sho["short_price"])
                _do("BUY",  qty, s["sell_price"])
                used.add(s["sell_date"])

        # Einzelorders Long
        for _, b in buys.iterrows():
            if b["buy_date"] in used: continue
            _do("BUY", int(b["shares"]), b["buy_price"])
            used.add(b["buy_date"])
        for _, s in sells.iterrows():
            if s["sell_date"] in used: continue
            _do("SELL", int(s["shares"]), s["sell_price"])
            used.add(s["sell_date"])
        # Einzelorders Short
        for _, c in covers.iterrows():
            if c["cover_date"] in used: continue
            _do("BUY",  int(c["shares"]), c["cover_price"])
            used.add(c["cover_date"])
        for _, sh in shorts.iterrows():
            if sh["short_date"] in used: continue
            _do("SELL", int(sh["shares"]), sh["short_price"])
            used.add(sh["short_date"])

    # Abschluss
    if live:
        print("\nAlle Orders an IB gesendet.")
    else:
        print("\nFertig gedruckt.")

# ──────────────────────────────────────────────────────────────────────────────
# TRADEMODE: Live senden aller Trades für HEUTE
# ──────────────────────────────────────────────────────────────────────────────
from pandas.errors import EmptyDataError
import pandas as pd
import datetime
from ib_insync import Stock, MarketOrder, LimitOrder

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

# Hilfsfunktion: print vs. IB
def _do(side, qty, price):
    if live_flag:
        contract = Stock(curr_ticker_symbol, "SMART", "USD")
        ib_global.placeOrder(contract, MarketOrder(side, qty))
        lvl = round(price * (1.002 if side=="BUY" else 0.998), 2)
        ib_global.placeOrder(contract, LimitOrder(side, qty, lvl))
    else:
        print(f" {side:<4}{qty}@{price:.2f}")

# Globale Container
extended_trades_long  = {}
extended_trades_short = {}

def preview_trades_for_today(ib):
    """
    Kombiniert both_backtesting_multi() und test_trading_for_date() für HEUTE.
    - Backtest schreibt trades_long_...csv & trades_short_...csv
    - Testmodus druckt alle Trades für heute
    """
    today_str = pd.Timestamp.today().strftime("%Y-%m-%d")
    # 1) Backtest für alle Ticker (schreibt die CSVs)
    both_backtesting_multi(ib)
    print("\n--- Vorschau der heutigen Trades (kein Live-Trade) ---")
    # 2) Test-Ausgabe für heute
    test_trading_for_date(ib, today_str)

import os
import pandas as pd
import numpy as np

def _load_extended(ticker, side):
    """
    Lädt extended_Long_signals_<ticker>.csv oder extended_Short_signals_<ticker>.csv 
    und liefert immer ein DataFrame mit genau diesen Spalten:
      - DateDetected (dtype datetime64[ns])
      - Action       (dtype object)
      - LevelClose   (dtype float64)
    """
    fn = f"extended_{side.lower()}_signals_{ticker}.csv"
    # 1) Leeres Grundgerüst
    out = pd.DataFrame({
        "DateDetected": pd.Series(dtype="datetime64[ns]"),
        "Action":       pd.Series(dtype="object"),
        "LevelClose":   pd.Series(dtype="float64")
    })

    if not os.path.exists(fn):
        return out

    try:
        df = pd.read_csv(fn)
    except Exception:
        return out

    # 2) Erkennen der richtigen Spaltennamen
    date_col   = next((c for c in df.columns if "date" in c.lower() and "detect" in c.lower()), None)
    action_col = next((c for c in df.columns if c.lower().endswith("action")), None)
    level_col  = next((c for c in df.columns if "level" in c.lower() and "close" in c.lower()), None)

    # 3) Spalten parsen
    if date_col:
        out["DateDetected"] = pd.to_datetime(df[date_col], errors="coerce")
    if action_col:
        # force string, fill NaN mit empty
        out["Action"] = df[action_col].fillna("").astype(str)
    if level_col:
        out["LevelClose"] = pd.to_numeric(df[level_col], errors="coerce")

    return out

# ──────────────────────────────────────────────────────────────────────────────
# 2) Pairing-Funktion
# ──────────────────────────────────────────────────────────────────────────────
def _pair_signals(df_long, df_short):
    """
    Paart Buy+Cover und Sell+Short nach gleichem DateDetected.
    Liefert vier Objekte:
      paired_long:  Liste von (b_row, c_row)
      paired_short: Liste von (s_row, sh_row)
      single_long:  DataFrame aller verbleibenden long-Signale
      single_short: DataFrame aller verbleibenden short-Signale
    """
    # Filter nach Aktion
    buys   = df_long [df_long["Action"]=="buy"]
    sells  = df_long [df_long["Action"]=="sell"]
    covers = df_short[df_short["Action"]=="cover"]
    shorts = df_short[df_short["Action"]=="short"]
    
    # Pair Buy+Cover
    paired_long, used_b, used_c = [], set(), set()
    for bi, b in buys.iterrows():
        match = covers[covers["DateDetected"]==b["DateDetected"]]
        if not match.empty:
            ci = match.index[0]
            paired_long.append((b, covers.loc[ci]))
            used_b.add(bi); used_c.add(ci)
    
    # Pair Sell+Short
    paired_short, used_s, used_sh = [], set(), set()
    for si, s in sells.iterrows():
        match = shorts[shorts["DateDetected"]==s["DateDetected"]]
        if not match.empty:
            shi = match.index[0]
            paired_short.append((s, shorts.loc[shi]))
            used_s.add(si); used_sh.add(shi)
    
    # Singles: alle ohne used-Indizes
    single_long  = df_long .drop(index=list(used_b|used_s), errors="ignore")
    single_short = df_short.drop(index=list(used_c|used_sh), errors="ignore")
    
    return paired_long, paired_short, single_long, single_short

import os, pandas as pd, datetime
from ib_insync import Stock, MarketOrder, LimitOrder

def _get_extended_signals(ticker):
    import pandas as pd
    import numpy as np
    import os

    records = []
    empty_df = pd.DataFrame(columns=["DateDetected", "Action", "LevelClose"])

    fn_long = f"extended_Long_signals_{ticker}.csv"
    if os.path.exists(fn_long) and os.path.getsize(fn_long) > 50:
        try:
            df_long = pd.read_csv(fn_long, parse_dates=["Long Date detected"])
            for _, row in df_long.iterrows():
                records.append({
                    "DateDetected": pd.to_datetime(row.get("Long Date detected"), errors="coerce"),
                    "Action": str(row.get("Long Action", "")).strip().lower() if pd.notna(row.get("Long Action")) else "",
                    "LevelClose": pd.to_numeric(row.get("Level Close", np.nan), errors="coerce")
                })
        except Exception as e:
            print(f"{ticker}: Fehler beim Laden von Long-Signalen – {e}")

    fn_short = f"extended_Short_signals_{ticker}.csv"
    if os.path.exists(fn_short) and os.path.getsize(fn_short) > 50:
        try:
            df_short = pd.read_csv(fn_short, parse_dates=["Short Date detected"])
            for _, row in df_short.iterrows():
                records.append({
                    "DateDetected": pd.to_datetime(row.get("Short Date detected"), errors="coerce"),
                    "Action": str(row.get("Short Action", "")).strip().lower() if pd.notna(row.get("Short Action")) else "",
                    "LevelClose": pd.to_numeric(row.get("Level Close", np.nan), errors="coerce")
                })
        except Exception as e:
            print(f"{ticker}: Fehler beim Laden von Short-Signalen – {e}")

    return pd.DataFrame(records, columns=["DateDetected", "Action", "LevelClose"]) if records else empty_df


def _fallback_price(ticker, date, price):
    if not pd.isna(price):
        return price
    df = pd.read_csv(f"{ticker}_data.csv", parse_dates=["date"], index_col="date")
    return float(df.loc[date, "Close"])

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
                price = _fallback_price(ticker, date, b["LevelClose"] if pd.notna(b["LevelClose"]) else c["LevelClose"])
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
                price = _fallback_price(ticker, date, sh["LevelClose"] if pd.notna(sh["LevelClose"]) else s["LevelClose"])
                qty_s  = calculate_shares(cfg["initialCapitalLong"],  price, cfg["order_round_factor"])
                qty_sh = calculate_shares(cfg["initialCapitalShort"], price, cfg["order_round_factor"])
                qty = qty_s + qty_sh
                print(f" SELL  {qty}@{price:.2f}")
                print(f"   → MARKET SELL {qty} @ {price:.2f}")
                print(f"   → LIMIT SELL  {qty} @ {price*0.998:.2f}")
                used_dates.add(date)

        # Einzelorders (nicht gematcht)
        singles = df[df["DateDetected"].dt.date.isin([today]) & ~df["DateDetected"].dt.date.isin(used_dates)]
        for _, row in singles.iterrows():
            action = row["Action"]; price = _fallback_price(ticker, today, row["LevelClose"])
            if action == "buy":
                cap = cfg["initialCapitalLong"]; factor = 1.002; side = "BUY"
            elif action == "sell":
                cap = cfg["initialCapitalLong"]; factor = 0.998; side = "SELL"
            elif action == "short":
                cap = cfg["initialCapitalShort"]; factor = 0.998; side = "SELL"
            elif action == "cover":
                cap = cfg["initialCapitalShort"]; factor = 1.002; side = "BUY"
            else:
                continue
            qty = calculate_shares(cap, price, cfg["order_round_factor"])
            print(f" {side:<5} {qty}@{price:.2f}")
            print(f"   → MARKET {side} {qty} @ {price:.2f}")
            print(f"   → LIMIT  {side} {qty} @ {price*factor:.2f}")

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
                price = _fallback_price(ticker, date, b["LevelClose"] if pd.notna(b["LevelClose"]) else c["LevelClose"])
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
                price = _fallback_price(ticker, date, sh["LevelClose"] if pd.notna(sh["LevelClose"]) else s["LevelClose"])
                qty_s  = calculate_shares(cfg["initialCapitalLong"],  price, cfg["order_round_factor"])
                qty_sh = calculate_shares(cfg["initialCapitalShort"], price, cfg["order_round_factor"])
                qty = qty_s + qty_sh
                print(f" SELL  {qty}@{price:.2f}")
                print(f"   → MARKET SELL {qty} @ {price:.2f}")
                print(f"   → LIMIT SELL  {qty} @ {price*0.998:.2f}")
                used_dates.add(date)

        # Einzelorders (nicht gematcht)
        singles = df[df["DateDetected"].dt.date.isin([today]) & ~df["DateDetected"].dt.date.isin(used_dates)]
        for _, row in singles.iterrows():
            action = row["Action"]; price = _fallback_price(ticker, today, row["LevelClose"])
            if action == "buy":
                cap = cfg["initialCapitalLong"]; factor = 1.002; side = "BUY"
            elif action == "sell":
                cap = cfg["initialCapitalLong"]; factor = 0.998; side = "SELL"
            elif action == "short":
                cap = cfg["initialCapitalShort"]; factor = 0.998; side = "SELL"
            elif action == "cover":
                cap = cfg["initialCapitalShort"]; factor = 1.002; side = "BUY"
            else:
                continue
            qty = calculate_shares(cap, price, cfg["order_round_factor"])
            print(f" {side:<5} {qty}@{price:.2f}")
            print(f"   → MARKET {side} {qty} @ {price:.2f}")
            print(f"   → LIMIT  {side} {qty} @ {price*factor:.2f}")
                                                                                         




import matplotlib.pyplot as plt
import matplotlib.dates as mdates

def debug_plot_extrema(df, support, resistance, ticker=""):
    """
    Visualisiert Candlestick-Chart mit Support (grün) und Resistance (rot).
    
    Parameter:
      df         – DataFrame mit OHLC-Daten (index=date)
      support    – Series mit Support-Preisen (index=date)
      resistance – Series mit Resistance-Preisen (index=date)
      ticker     – optionaler Titel
    """
    plt.figure(figsize=(14, 6))
    
    # Candlestick-ähnlich: High & Low als Linien, Open-Close als Balken
    dates = df.index
    width = 0.6

    for i in range(len(df)):
        color = "green" if df["Close"].iloc[i] >= df["Open"].iloc[i] else "red"
        plt.plot([dates[i], dates[i]], [df["Low"].iloc[i], df["High"].iloc[i]], color="black", linewidth=0.5)
        plt.bar(dates[i], df["Close"].iloc[i] - df["Open"].iloc[i],
                bottom=df["Open"].iloc[i], color=color, width=width, alpha=0.8)

    # Support & Resistance Marker
    plt.scatter(support.index, support.values, label="Support", color="limegreen", s=80, marker="o")
    plt.scatter(resistance.index, resistance.values, label="Resistance", color="red", s=80, marker="x")
    
    plt.title(f"Support & Resistance – Debug Plot {ticker}")
    plt.xlabel("Datum")
    plt.ylabel("Preis")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()

    # Saubere X-Achse mit Datumsformat
    plt.gca().xaxis.set_major_locator(mdates.MonthLocator())
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
    plt.xticks(rotation=45)

    plt.show()
def run_daily_trading_cycle(ib):
    today = pd.Timestamp.today().strftime("%Y-%m-%d")
    print(f"\n=== DAILY TRADING CYCLE für {today} gestartet ===")

    # Schritt 1: Backtesting für alle Ticker
    print("\n→ Starte Backtesting für alle Ticker …")
    both_backtesting_multi(ib)

    # Schritt 2: Signale für heute sichten
    print("\n→ Prüfe Extended-Signale für heute …")
    test_extended_for_date(today)

    # Schritt 3: Warte auf Handelszeit & starte Trades
    print("\n→ Warte auf 15:45 NY-Zeit für automatische Orders …")
    wait_and_trade_at_1540(ib)

def repair_missing_days(ib):
    from ib_insync import Stock

    today = pd.Timestamp.today().normalize().tz_localize(None)
    print(f"\n🔧 Repariere fehlende Tagesdaten bis {today.date()}")

    for ticker, cfg in tickers.items():
        csv_fn = f"{ticker}_data.csv"
        contract = Stock(cfg["symbol"], "SMART", "USD")

        if not os.path.exists(csv_fn):
            print(f"{ticker}: Datei fehlt – lade neu …")
            update_historical_data_csv(ib, contract, csv_fn)
            continue

        try:
            df = pd.read_csv(csv_fn, parse_dates=["date"], index_col="date")
        except Exception as e:
            print(f"{ticker}: Fehler beim Laden – {e}")
            continue

        last_date = df.index.max()
        if pd.isna(last_date) or last_date < today - pd.Timedelta(days=1):
            print(f"{ticker}: Letzter Tag = {last_date.date()}, aktualisiere …")
            update_historical_data_csv(ib, contract, csv_fn)
        else:
            print(f"{ticker}: OK, letzte Zeile ist aktuell ({last_date.date()})")


# ──────────────────────────────────────────────────────────────────────────────
# 4) Main-Block mit allen Modi
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # DEBUG-VISUALISIERUNG FÜR GOOGL
    ticker = "GOOGL"
    df = pd.read_csv(f"{ticker}_data.csv", parse_dates=["date"], index_col="date")
    df.rename(columns={"open":"Open", "high":"High", "low":"Low", "close":"Close"}, inplace=True)

    support, resistance = calculate_support_resistance(df, past_window=3, trade_window=1)
    debug_plot_extrema(df, support, resistance, ticker=ticker)

    # Rest deiner Modi
    mode = sys.argv[1].lower()

    if len(sys.argv) < 2:
        print("Modi: optimalplot, bothbacktesting, trading, daytrading, live, testdate, exttestdate, tradedate")
        sys.exit(1)

    mode = sys.argv[1].lower()

    ib = IB()
    ib.connect("127.0.0.1", 7497, clientId=10)

    if mode == "optimalplot":
        for ticker in tickers:
            plot_optimal_trades_multi(ticker, ib)

    elif mode == "bothbacktesting":
        # ← Hier bleibt alles genau so, wie dein Modul es vorschreibt
        repair_missing_days(ib)
        both_backtesting_multi(ib)
        show_all_equity_curves_and_stats()
    elif mode == "exttestdate":
        test_extended_for_date(sys.argv[2])

    elif mode == "autotrade":
        run_daily_trading_cycle(ib)

    elif mode == "exttradedate":
        trade_extended_for_today(ib)

    elif mode == "preview":
        preview_trades_for_today(ib)

    elif mode == "trading":
        trading_multi(ib)

    elif mode == "daytrading":
        daytrading_multi(ib, intervals=intervals)
        print("Daytrading läuft… Beenden mit STRG+C.")
        while True:
            time.sleep(60)

    elif mode == "live":
        live_trading_loop(ib, intervals=intervals)
        # kein disconnect hier

    elif mode == "testdate":
        test_tradcing_for_date(ib, sys.argv[2])

    elif mode == "tradedate":
        trade_trading_for_today(ib)


    elif mode == "tradedate":
        trade_trading_for_today(ib)

    else:
        print(f"Unbekannter Modus '{mode}'")

    # Disconnect in allen Modi außer 'live'
    if mode != "live":
        ib.disconnect()
