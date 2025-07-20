from backtesting_core import *
from stats_tools import stats, export_stats_csv
from trade_execution import get_realtime_price
from data_sync import update_historical_data_csv, berechne_best_p_tw_long

import os
from datetime import date
from tickers_config import tickers

today = date.today().isoformat()
report_dir = f"reports/{today}"
os.makedirs(report_dir, exist_ok=True)

pd.DataFrame(matched_long).to_csv(f"{report_dir}/matched_long_{ticker}.csv", index=False)
pd.DataFrame(matched_short).to_csv(f"{report_dir}/matched_short_{ticker}.csv", index=False)
pd.DataFrame(long_trades).to_csv(f"{report_dir}/trades_long_{ticker}.csv", index=False)
pd.DataFrame(short_trades).to_csv(f"{report_dir}/trades_short_{ticker}.csv", index=False)
ext_long.to_csv(f"{report_dir}/extended_long_{ticker}.csv", index=False)
ext_short.to_csv(f"{report_dir}/extended_short_{ticker}.csv", index=False)

def write_md_report(ticker, stats_text, matched_long, matched_short, ext_long, ext_short, path):
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# Bericht für {ticker} – {date.today().isoformat()}\n\n")
        f.write(f"## Statistiken\n{stats_text}\n\n")
        f.write("## Matched Long Trades\n")
        f.write(pd.DataFrame(matched_long).to_markdown(index=False))
        f.write("\n\n## Matched Short Trades\n")
        f.write(pd.DataFrame(matched_short).to_markdown(index=False))
        f.write("\n\n## Extended Long Signals\n")
        f.write(pd.DataFrame(ext_long).to_markdown(index=False))
        f.write("\n\n## Extended Short Signals\n")
        f.write(pd.DataFrame(ext_short).to_markdown(index=False))

def run_full_backtest(
    ib, tickers, report_dir,
    backtesting_begin=25, backtesting_end=98,
    commission_rate=COMMISSION_RATE,
    min_commission=MIN_COMMISSION,
    round_factor=ORDER_ROUND_FACTOR
):
    for ticker, config in tickers.items():
        print(f"\n=================== Backtesting für {ticker} ===================")

        contract = Stock(config["symbol"], "SMART", "USD")
        csv_fn = f"{ticker}_data.csv"
        df = update_historical_data_csv(ib, contract, csv_fn)
        df.rename(columns={"open":"Open","high":"High","low":"Low","close":"Close"}, inplace=True)
        df.sort_index(inplace=True)

        last_date = df.index[-1]
        last_price = df.loc[last_date, "Close"]

        # Long
        if config.get("long", False):
            p_long, tw_long = berechne_best_p_tw_long(df, config, backtesting_begin, backtesting_end)
            sup_long, res_long = calculate_support_resistance(df, p_long, tw_long)
            ext_long = assign_signals_extended(sup_long, res_long, df, tw_long, "1d", "long")
            ext_long = update_level_close(ext_long, df, "long")
            cap_long, trades_long = simulate_trades_compound_extended(
                ext_long, df, config["initialCapitalLong"],
                commission_rate, min_commission, round_factor,
                last_price, last_date, direction="long"
            )
            equity_long = compute_equity_curve(df, trades_long, config["initialCapitalLong"], long=True)
            matched_long = match_trades(trades_long, "long")
        else:
            ext_long, trades_long, matched_long = pd.DataFrame(), [], []
            equity_long = [config["initialCapitalLong"]] * len(df)

        # Short
        if config.get("short", False):
            p_short, tw_short = berechne_best_p_tw_short(df, config, backtesting_begin, backtesting_end)
            sup_short, res_short = calculate_support_resistance(df, p_short, tw_short)
            ext_short = assign_signals_extended(sup_short, res_short, df, tw_short, "1d", "short")
            ext_short = update_level_close(ext_short, df, "short")
            cap_short, trades_short = simulate_trades_compound_extended(
                ext_short, df, config["initialCapitalShort"],
                commission_rate, min_commission, round_factor,
                last_price, last_date, direction="short"
            )
            equity_short = compute_equity_curve(df, trades_short, config["initialCapitalShort"], long=False)
            matched_short = match_trades(trades_short, "short")
        else:
            ext_short, trades_short, matched_short = pd.DataFrame(), [], []
            equity_short = [config["initialCapitalShort"]] * len(df)

        equity_combined = [l + s for l, s in zip(equity_long, equity_short)]

        # 📁 Report-Speicherung
        pd.DataFrame(trades_long).to_csv(f"{report_dir}/trades_long_{ticker}.csv", index=False)
        pd.DataFrame(trades_short).to_csv(f"{report_dir}/trades_short_{ticker}.csv", index=False)
        pd.DataFrame(matched_long).to_csv(f"{report_dir}/matched_long_{ticker}.csv", index=False)
        pd.DataFrame(matched_short).to_csv(f"{report_dir}/matched_short_{ticker}.csv", index=False)
        ext_long.to_csv(f"{report_dir}/extended_long_{ticker}.csv", index=False)
        ext_short.to_csv(f"{report_dir}/extended_short_{ticker}.csv", index=False)

        print(f"{ticker}: Alle Dateien gespeichert unter {report_dir}/")

        # 📊 Konsole-Statistik + Markdown-Report
        stats(trades_long, f"{ticker} – Long")
        stats(trades_short, f"{ticker} – Short")
        stats_txt = (
            f"- Long Trades: {len(trades_long)}\n"
            f"- Short Trades: {len(trades_short)}\n"
        )
        write_md_report(ticker, stats_txt, matched_long, matched_short, ext_long, ext_short,
                        f"{report_dir}/report_{ticker}.md")
from backtesting_core import *
from stats_tools import stats, write_md_report
from data_sync import update_historical_data_csv, berechne_best_p_tw_long, berechne_best_p_tw_short
from trade_execution import get_realtime_price

from run_full_backtest import run_full_backtest  # oder direkt dort definieren

# Konfiguration laden (z. B. Ticker & Kapital)
tickers = {...}  # dein Dictionary
report_dir = f"reports/{pd.Timestamp.today().date()}"

run_full_backtest(ib, tickers, report_dir)

from runner import run_full_backtest

report_dir = f"reports/{pd.Timestamp.today().date().isoformat()}"
run_full_backtest(ib, tickers, report_dir)

