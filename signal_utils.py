import pandas as pd
import numpy as np

from scipy.signal import argrelextrema
def compute_trend(df, window=20):
    """
    Berechnet den einfachen gleitenden Durchschnitt (SMA) auf Basis der Close‑Preise.
    """
    return df["Close"].rolling(window=window).mean()

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
    df = assign_long_signals(support, resistance, data, trade_window, interval).copy()
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

def assign_short_signals_extended(support, resistance, data, trade_window, interval="1d"):
    df = assign_short_signals(support, resistance, data, trade_window, interval).copy()
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
