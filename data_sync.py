# backtesting_core.py

import os
import pandas as pd
from ib_insync import Stock

from tickers_config      import tickers
from trade_execution     import get_realtime_price, get_yf_price, calculate_shares
from signal_utils        import (
    calculate_support_resistance, get_next_trading_day,
    assign_long_signals_extended, assign_short_signals_extended,
    update_level_close_long,  update_level_close_short
)
from simulation_utils    import simulate_trades_compound_extended
from matching_utils      import match_trades
from print_utils         import print_matched_long_trades, print_matched_short_trades
from backtesting_core    import berechne_best_p_tw_long, berechne_best_p_tw_short
from backtesting_core import update_historical_data_csv
 
COMMISSION_RATE    = 0.0018
MIN_COMMISSION     = 1.0
ORDER_ROUND_FACTOR = 1
backtesting_begin  = 0
backtesting_end    = 100

from ib_insync import IB, Stock
import pandas as pd
import os

def update_historical_data_minute(ib, contract, fn, duration="1 D", bar_size="1 min", what_to_show="TRADES"):
    """
    Holt historische Intraday-Daten (z. B. Minutenkerzen) von IB und speichert als CSV.
    """
    if os.path.exists(fn):
        df_existing = pd.read_csv(fn, parse_dates=["date"], index_col="date")
    else:
        df_existing = pd.DataFrame()

    # 📡 Request vom IB
    bars = ib.reqHistoricalData(
        contract,
        endDateTime="",                  # Jetzt
        durationStr=duration,           # z. B. "1 D" für 1 Handelstag
        barSizeSetting=bar_size,        # z. B. "1 min"
        whatToShow=what_to_show,        # "TRADES", "MIDPOINT", etc.
        useRTH=True,                    # Nur Regular Trading Hours
        formatDate=1
    )

    # 📦 In DataFrame
    df_new = pd.DataFrame([{
        "date": pd.to_datetime(bar.date),
        "Open": bar.open,
        "High": bar.high,
        "Low": bar.low,
        "Close": bar.close,
        "Volume": bar.volume
    } for bar in bars]).set_index("date")

    # 🔁 Zusammenführen
    df_combined = pd.concat([df_existing, df_new])
    df_combined = df_combined[~df_combined.index.duplicated()].sort_index()

    # 💾 Speichern
    df_combined.to_csv(fn)
    return df_combined


def update_today_row(ticker, df_daily, df_minute, ib, contract):
    today = pd.Timestamp.today().normalize()

    if is_ny_trading_time():
        today_row = construct_today_from_minute_data(df_minute, today)
        print(f"{ticker}: NY offen → Tageszeile aus Minutedaten aktualisiert.")
    else:
        csv_fn = f"{ticker}_data.csv"
        df_updated = update_historical_data_csv(ib, contract, csv_fn)
        if today in df_updated.index:
            today_row = df_updated.loc[today]
            print(f"{ticker}: NY geschlossen → Echte Tageszeile aus CSV geladen.")
        else:
            print(f"{ticker}: Keine finale Tageszeile gefunden – heute wird übersprungen.")
            return df_daily

    df_daily.loc[today] = today_row
    return df_daily



def run_full_backtest(ib, report_dir):
    os.makedirs(report_dir, exist_ok=True)

    for ticker, cfg in tickers.items():
        print(f"\n=== Backtest für {ticker} ===")

        # Daten laden/aktualisieren
        fn = f"{ticker}_data.csv"
        c  = Stock(cfg["symbol"], "SMART", "USD")
        if os.path.exists(fn):
            df = pd.read_csv(fn, parse_dates=["date"], index_col="date")
        else:
            df = update_historical_data_csv(ib, c, fn)
        df.sort_index(inplace=True)
        df.rename(columns={"open":"Open","high":"High","low":"Low","close":"Close"}, inplace=True)

        artificial_close_price = df["Close"].iloc[-1]
        artificial_close_date  = df.index[-1]

        # Long optimieren + simulieren
        p_long, tw_long = berechne_best_p_tw_long(df, cfg, backtesting_begin, backtesting_end)
        sup_long, res_long = calculate_support_resistance(df, p_long, tw_long)
        ext_long = assign_long_signals_extended(sup_long, res_long, df, tw_long, "1d")
        ext_long = update_level_close_long(ext_long, df)
        p_long, tw_long = berechne_best_p_tw_long(df, cfg)
        sup_long, res_long = calculate_support_resistance(df, p_long, tw_long)
        ext_long = assign_long_signals_extended(sup_long, res_long, df, tw_long, "1d")
        ext_long = update_level_close_long(ext_long, df)
        cap_long, trades_long = simulate_trades_compound_extended(
            ext_long, df, cfg,
            commission_rate=COMMISSION_RATE,
            min_commission=MIN_COMMISSION,
            round_factor=cfg.get("order_round_factor", ORDER_ROUND_FACTOR),
            artificial_close_price=close_price,
            artificial_close_date=close_date,
            direction="long"
        )

        # Short optimieren + simulieren
        p_short, tw_short = berechne_best_p_tw_short(df, cfg, backtesting_begin, backtesting_end)
        sup_short, res_short = calculate_support_resistance(df, p_short, tw_short)
        ext_short = assign_short_signals_extended(sup_short, res_short, df, tw_short, "1d")
        ext_short = update_level_close_short(ext_short, df)
        cap_short, trades_short = simulate_trades_compound_extended(
            ext_short, df, cfg,
            commission_rate=COMMISSION_RATE,
            min_commission=MIN_COMMISSION,
            round_factor=cfg.get("order_round_factor", ORDER_ROUND_FACTOR),
            artificial_close_price=close_price,
            artificial_close_date=close_date,
            direction="short"
        )

        # CSV export
        pd.DataFrame(trades_long ).to_csv(f"{report_dir}/trades_long_{ticker}.csv",  index=False)
        pd.DataFrame(trades_short).to_csv(f"{report_dir}/trades_short_{ticker}.csv", index=False)
        print(f"{ticker}: Trades gespeichert.")

        # Ausgabe
        matched_long  = match_trades(trades_long,  side="long")
        matched_short = match_trades(trades_short, side="short")
        print_matched_long_trades(matched_long,  ticker)
        print_matched_short_trades(matched_short, ticker)

    print("\nBacktest abgeschlossen.")
