import pandas as pd
import numpy as np
import os
from datetime import timedelta

from scipy.signal import argrelextrema
def compute_trend(df, window=20):
    """
    Berechnet den einfachen gleitenden Durchschnitt (SMA) auf Basis der Close‑Preise.
    """
    return df["Close"].rolling(window=window).mean()

def get_next_trading_day(dt):
    """Return the next trading day (Mon-Fri). Does not account for holidays."""
    if pd.isna(dt):
        return pd.NaT
    d = pd.Timestamp(dt).normalize()
    # Move to next day
    d = d + timedelta(days=1)
    # Skip weekends
    while d.weekday() >= 5:
        d = d + timedelta(days=1)
    return d

def get_trade_day_offset(base_date, trade_window, df):
    future_dates = df.index[df.index > base_date]
    if len(future_dates) < trade_window:
        return pd.NaT
    return future_dates[trade_window - 1]
def update_level_close_long(extended_df, market_df):
    closes = []
    for _, row in extended_df.iterrows():
        trade_day = row.get("Long Date detected")
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
        trade_day = row.get("Short Date detected")
        if pd.isna(trade_day):
            closes.append(np.nan)
        elif trade_day in market_df.index:
            closes.append(market_df.loc[trade_day, "Close"])
        else:
            idx = market_df.index.searchsorted(trade_day)
            closes.append(market_df.iloc[idx]["Close"] if idx < len(market_df.index) else np.nan)
    extended_df["Level Close"] = closes
    return extended_df

def calculate_support_resistance(df, past_window, trade_window):
    total_window = int(past_window + trade_window)
    prices = df["Close"].values

    local_min_idx = argrelextrema(prices, np.less, order=total_window)[0]
    support = pd.Series(prices[local_min_idx], index=df.index[local_min_idx])

    local_max_idx = argrelextrema(prices, np.greater, order=total_window)[0]
    resistance = pd.Series(prices[local_max_idx], index=df.index[local_max_idx])

    # Globale Werte ergänzen
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


def assign_long_signals(support, resistance, data, trade_window, interval="1d"):
    data.sort_index(inplace=True)
    sup_df = pd.DataFrame({'Date': support.index, 'Level': support.values, 'Type': 'support'})
    res_df = pd.DataFrame({'Date': resistance.index, 'Level': resistance.values, 'Type': 'resistance'})
    df = pd.concat([sup_df, res_df]).sort_values(by='Date').reset_index(drop=True)

    df['Long'] = None
    df['Long Date'] = pd.NaT
    long_active = False

    for i, row in df.iterrows():
        base_date = row['Date']
        trade_date = get_trade_day_offset(base_date, trade_window, data)

        if row['Type'] == 'support' and not long_active:
            df.at[i, 'Long'] = 'buy'
            df.at[i, 'Long Date'] = trade_date
            long_active = True
        elif row['Type'] == 'resistance' and long_active:
            df.at[i, 'Long'] = 'sell'
            df.at[i, 'Long Date'] = trade_date
            long_active = False

    return df

def assign_short_signals(support, resistance, data, trade_window, interval="1d"):
    data.sort_index(inplace=True)
    sup_df = pd.DataFrame({'Date': support.index, 'Level': support.values, 'Type': 'support'})
    res_df = pd.DataFrame({'Date': resistance.index, 'Level': resistance.values, 'Type': 'resistance'})
    df = pd.concat([res_df, sup_df]).sort_values(by='Date').reset_index(drop=True)

    df['Short'] = None
    df['Short Date'] = pd.NaT
    short_active = False

    for i, row in df.iterrows():
        base_date = row['Date']
        trade_date = get_trade_day_offset(base_date, trade_window, data)

        if row['Type'] == 'resistance' and not short_active:
            df.at[i, 'Short'] = 'short'
            df.at[i, 'Short Date'] = trade_date
            short_active = True
        elif row['Type'] == 'support' and short_active:
            df.at[i, 'Short'] = 'cover'
            df.at[i, 'Short Date'] = trade_date
            short_active = False

    return df

def assign_long_signals_extended(support, resistance, data, trade_window, interval="1d"):
    # Ensure we get a proper DataFrame from assign_long_signals
    try:
        base_signals = assign_long_signals(support, resistance, data, trade_window, interval)
        
        # Check if the result is a DataFrame
        if not isinstance(base_signals, pd.DataFrame):
            print(f"Warning: assign_long_signals returned {type(base_signals)} instead of DataFrame")
            # Return empty DataFrame with expected columns
            return pd.DataFrame(columns=["Date high/low", "Level high/low", "Supp/Resist", "Long Action",
                                       "Long Date detected", "Level Close", "Long Trade Day", "Level trade"])
        
        if base_signals.empty:
            # Return empty DataFrame with expected columns
            return pd.DataFrame(columns=["Date high/low", "Level high/low", "Supp/Resist", "Long Action",
                                       "Long Date detected", "Level Close", "Long Trade Day", "Level trade"])
        
        df = base_signals.copy()
        df["Long Action"] = df["Long"]
        df.rename(columns={"Date": "Date high/low", "Level": "Level high/low", "Type": "Supp/Resist"}, inplace=True)
        df["Long Date detected"] = df["Date high/low"].apply(lambda d: get_trade_day_offset(d, trade_window, data))
        df["Level Close"] = np.nan
        df["Long Trade Day"] = df["Long Date detected"].apply(
            lambda dt: dt.replace(hour=15, minute=50, second=0, microsecond=0) if pd.notna(dt) else pd.NaT
        )
        df["Level trade"] = np.nan
        return df[["Date high/low", "Level high/low", "Supp/Resist", "Long Action",
                   "Long Date detected", "Level Close", "Long Trade Day", "Level trade"]]
        
    except Exception as e:
        print(f"Error in assign_long_signals_extended: {e}")
        # Return empty DataFrame with expected columns
        return pd.DataFrame(columns=["Date high/low", "Level high/low", "Supp/Resist", "Long Action",
                                   "Long Date detected", "Level Close", "Long Trade Day", "Level trade"])

import pandas as pd
from tickers_config import tickers

def extract_trades_by_date(ticker, ext_long, ext_short, cfg, daily_df, current_prices=None):
    """
    Extracts trades from extended signals and groups them by date.
    Uses Open/Close prices from daily_df, or current minute price for today if provided.
    Returns: dict of date -> list of trades
    """
    trades_by_date = {}
    today_str = pd.Timestamp.now().strftime('%Y-%m-%d')

    # LONG trades
    if not ext_long.empty:
        for _, row in ext_long.iterrows():
            action = row.get('Long Action')
            trade_date = str(row.get('Long Date detected'))[:10]  # Format YYYY-MM-DD
            if action in ['buy', 'sell']:
                price_field = cfg.get('trade_on', 'Close').capitalize()
                # Use minute price if today and current_prices given
                if trade_date == today_str and current_prices:
                    price = current_prices.get(ticker)
                else:
                    price = daily_df.loc[trade_date, price_field] if trade_date in daily_df.index else None
                trade = {
                    "symbol": ticker,
                    "side": "BUY" if action == "buy" else "SELL",
                    "date": trade_date,
                    "price": round(float(price), 2) if price is not None else None
                }
                trades_by_date.setdefault(trade_date, []).append(trade)

    # SHORT trades
    if not ext_short.empty:
        for _, row in ext_short.iterrows():
            action = row.get('Short Action')
            trade_date = str(row.get('Short Date detected'))[:10]
            if action in ['short', 'cover']:
                price_field = cfg.get('trade_on', 'Close').capitalize()
                if trade_date == today_str and current_prices:
                    price = current_prices.get(ticker)
                else:
                    price = daily_df.loc[trade_date, price_field] if trade_date in daily_df.index else None
                trade = {
                    "symbol": ticker,
                    "side": "SHORT" if action == "short" else "COVER",
                    "date": trade_date,
                    "price": round(float(price), 2) if price is not None else None
                }
                trades_by_date.setdefault(trade_date, []).append(trade)
    return trades_by_date

def list_all_trades_by_date():
    """
    For all tickers, loads daily data and extended signals, and prints all trades grouped by date.
    """
    all_trades_by_date = {}

    for ticker, cfg in tickers.items():
        # Load daily price data
        fn = f"{ticker}_data.csv"
        daily_df = pd.read_csv(fn, index_col="date", parse_dates=["date"])
        daily_df.rename(columns={"open":"Open","high":"High","low":"Low","close":"Close"}, inplace=True)
        daily_df.index = pd.to_datetime(daily_df.index)

        # Load extended signals
        ext_long_fn = f"extended_long_{ticker}.csv"
        ext_short_fn = f"extended_short_{ticker}.csv"
        ext_long = pd.read_csv(ext_long_fn) if os.path.exists(ext_long_fn) else pd.DataFrame()
        ext_short = pd.read_csv(ext_short_fn) if os.path.exists(ext_short_fn) else pd.DataFrame()

        trades_by_date = extract_trades_by_date(ticker, ext_long, ext_short, cfg, daily_df)
        for date, trades in trades_by_date.items():
            all_trades_by_date.setdefault(date, []).extend(trades)

    # List trades by date
    for date in sorted(all_trades_by_date):
        print(f"📅 {date}:")
        for t in all_trades_by_date[date]:
            print(f"  {t['side']:6} {t['symbol']:6} @ {t['price']}")

# To run:
if __name__ == "__main__":
    list_all_trades_by_date()

def assign_short_signals_extended(support, resistance, data, trade_window, interval="1d"):
    # Ensure we get a proper DataFrame from assign_short_signals
    try:
        base_signals = assign_short_signals(support, resistance, data, trade_window, interval)
        
        # Check if the result is a DataFrame
        if not isinstance(base_signals, pd.DataFrame):
            print(f"Warning: assign_short_signals returned {type(base_signals)} instead of DataFrame")
            # Return empty DataFrame with expected columns
            return pd.DataFrame(columns=["Date high/low", "Level high/low", "Supp/Resist", "Short Action",
                                       "Short Date detected", "Level Close", "Short Trade Day", "Level trade"])
        
        if base_signals.empty:
            # Return empty DataFrame with expected columns
            return pd.DataFrame(columns=["Date high/low", "Level high/low", "Supp/Resist", "Short Action",
                                       "Short Date detected", "Level Close", "Short Trade Day", "Level trade"])
        
        df = base_signals.copy()
        df["Short Action"] = df["Short"]
        df.rename(columns={"Date": "Date high/low", "Level": "Level high/low", "Type": "Supp/Resist"}, inplace=True)
        df["Short Date detected"] = df["Date high/low"].apply(lambda d: get_trade_day_offset(d, trade_window, data))
        df["Level Close"] = np.nan
        df["Short Trade Day"] = df["Short Date detected"].apply(
            lambda dt: dt.replace(hour=15, minute=50, second=0, microsecond=0) if pd.notna(dt) else pd.NaT
        )
        df["Level trade"] = np.nan
        return df[["Date high/low", "Level high/low", "Supp/Resist", "Short Action",
                   "Short Date detected", "Level Close", "Short Trade Day", "Level trade"]]
        
    except Exception as e:
        print(f"Error in assign_short_signals_extended: {e}")
        # Return empty DataFrame with expected columns
        return pd.DataFrame(columns=["Date high/low", "Level high/low", "Supp/Resist", "Short Action",
                                   "Short Date detected", "Level Close", "Short Trade Day", "Level trade"])
