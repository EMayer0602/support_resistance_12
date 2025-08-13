from ib_insync import IB, Contract
from tickers_config import tickers
from trade_execution import execute_trades, get_backtest_price, plan_trade_qty
from simulation_utils import generate_backtest_date_range
from backtesting_core import run_full_backtest
from stats_tools import stats
from simulation_utils import compute_equity_curve
from plot_utils import plot_combined_chart_and_equity
import json
import os
import sys
from datetime import datetime
import pandas as pd

def load_trades_for_day(date_str, json_path="trades_by_day.json"):
    if not os.path.exists(json_path):
        print(f"⚠️ Datei {json_path} nicht gefunden.")
        return [], {}
    try:
        with open(json_path, "r") as f:
            all_trades = json.load(f)
    except Exception as e:
        print(f"⚠️ Fehler beim Laden von {json_path}: {e}")
        return [], {}
    trades = all_trades.get(date_str, [])
    portfolio = {}
    for t in trades:
        delta = t["qty"] if t["side"] in ("BUY", "COVER") else -t["qty"]
        portfolio[t["symbol"]] = portfolio.get(t["symbol"], 0) + delta
    return trades, portfolio

def print_trade_summary(trades, portfolio_snapshot):
    if not trades:
        print("\nℹ️ Keine Trades generiert.")
        return
    entry_trades = [t for t in trades if t["side"] in ("BUY", "SHORT")]
    exit_trades = [t for t in trades if t["side"] in ("SELL", "COVER")]
    print("\n📈 Einstiegstrades (neu investiert / leerverkauft)")
    if entry_trades:
        print(f"{'Symbol':<8} {'Aktion':<7} {'Stück':>5} {'Preis':>10}")
        print("-" * 36)
        for t in entry_trades:
            print(f"{t['symbol']:<8} {t['side']:<7} {t['qty']:>5} {t['price']:>10.2f}")
    else:
        print("Keine Einstiegstrades.")
    print("\n📉 Exit-Trades (verkaufte / gedeckte Bestände)")
    if exit_trades:
        print(f"{'Symbol':<8} {'Aktion':<7} {'Stück':>5} {'Preis':>10} {'Bestand':>10}")
        print("-" * 50)
        for t in exit_trades:
            owned = portfolio_snapshot.get(t['symbol'], 0)
            print(f"{t['symbol']:<8} {t['side']:<7} {t['qty']:>5} {t['price']:>10.2f} {owned:>10}")
    else:
        print("Keine Exit-Trades.")

def main():
    if len(sys.argv) < 2:
        print("⚠️ Bitte gib einen Modus an: testdate, tradedate, listdays, fullbacktest")
        print("Beispiele:")
        print("  python runner.py testdate 2025-07-15")
        print("  python runner.py tradedate 2025-07-15")
        print("  python runner.py listdays")
        print("  python runner.py fullbacktest")
        return

    mode = sys.argv[1].lower()
    
    # Validate arguments based on mode
    if mode in ["testdate", "tradedate"] and len(sys.argv) < 3:
        print(f"⚠️ Der Modus '{mode}' benötigt ein Datum als zweiten Parameter.")
        print(f"Beispiel: python runner.py {mode} 2025-07-15")
        return
    
    # Only connect to IB for tradedate and fullbacktest modes
    ib = None
    if mode in ["tradedate", "fullbacktest"]:
        ib = IB()
        try:
            ib.connect("127.0.0.1", 7497, clientId=1)
        except Exception as e:
            print(f"⚠️ Fehler bei IB-Verbindung: {e}")
            print("Für 'testdate' und 'listdays' ist keine IB-Verbindung erforderlich.")
            return
    
    if mode == "testdate":
        date_str = sys.argv[2]
        trades, portfolio = load_trades_for_day(date_str)
        if not trades:
            print(f"\n📅 {date_str}: Keine Trades an diesem Tag.")
            print("💡 Tipp: Führe zuerst 'python runner.py fullbacktest' aus, um Trades zu generieren.")
            return
        print_trade_summary(trades, portfolio)

    elif mode == "tradedate":
        tradedate = sys.argv[2]
        trades, _ = load_trades_for_day(tradedate)
        if not trades:
            print(f"\n📅 {tradedate}: Kein Trade aus dem Backtest.")
            return
        # When executing trades, you can use conID to build IB contracts
        for t in trades:
            cfg = tickers[t['symbol']]
            contract = Contract(conId=cfg["conID"], exchange="SMART", currency="USD")
            # Pass contract to your execute_trades logic as needed
            # execute_trades(ib, t, contract)
        # If execute_trades expects only the trade dict, and handles contract creation, update it accordingly

    elif mode == "listdays":
        json_path = "trades_by_day.json"
        if not os.path.exists(json_path):
            print(f"⚠️ Datei {json_path} nicht gefunden.")
            return
        with open(json_path, "r") as f:
            data = json.load(f)
        active_days = [day for day, trades in data.items() if trades]
        if not active_days:
            print("ℹ️ Keine aktiven Tage mit Trades gefunden.")
            return
        print("\n📅 Tage mit aktiven Trades im Backtest:")
        for day in sorted(active_days):
            print(f"  • {day}")

    elif mode == "fullbacktest":
        # 1) Run core backtest (creates trades_long_*.csv / trades_short_*.csv)
        run_full_backtest(ib)

        # 2) Build daily trade ledger from MATCHED trade CSVs (entry/exit pairs)
        backtest_trades: dict[str, list] = {}
        for symbol, cfg in tickers.items():
            # LONG matched trades
            long_path = f"trades_long_{symbol}.csv"
            if cfg.get("long", False) and os.path.exists(long_path):
                try:
                    df_long = pd.read_csv(long_path, parse_dates=["buy_date","sell_date"])
                except Exception as e:
                    print(f"WARN cannot read {long_path}: {e}")
                    df_long = pd.DataFrame()
                for _, row in df_long.iterrows():
                    b = row.get("buy_date")
                    s = row.get("sell_date")
                    shares = int(row.get("shares", 0) or 0)
                    b_price = row.get("buy_price")
                    s_price = row.get("sell_price")
                    if pd.notna(b):
                        ds = pd.Timestamp(b).strftime('%Y-%m-%d')
                        backtest_trades.setdefault(ds, []).append({
                            "symbol": symbol, "side": "BUY", "qty": shares,
                            "price": None if pd.isna(b_price) else float(b_price),
                            "source": "LONG"
                        })
                    if pd.notna(s):
                        ds = pd.Timestamp(s).strftime('%Y-%m-%d')
                        backtest_trades.setdefault(ds, []).append({
                            "symbol": symbol, "side": "SELL", "qty": shares,
                            "price": None if pd.isna(s_price) else float(s_price),
                            "source": "LONG"
                        })
            # SHORT matched trades
            short_path = f"trades_short_{symbol}.csv"
            if cfg.get("short", False) and os.path.exists(short_path):
                try:
                    df_short = pd.read_csv(short_path, parse_dates=["short_date","cover_date"])
                except Exception as e:
                    print(f"WARN cannot read {short_path}: {e}")
                    df_short = pd.DataFrame()
                for _, row in df_short.iterrows():
                    sh = row.get("short_date")
                    cv = row.get("cover_date")
                    shares = int(row.get("shares", 0) or 0)
                    sh_price = row.get("short_price")
                    cv_price = row.get("cover_price")
                    if pd.notna(sh):
                        ds = pd.Timestamp(sh).strftime('%Y-%m-%d')
                        backtest_trades.setdefault(ds, []).append({
                            "symbol": symbol, "side": "SHORT", "qty": shares,
                            "price": None if pd.isna(sh_price) else float(sh_price),
                            "source": "SHORT"
                        })
                    if pd.notna(cv):
                        ds = pd.Timestamp(cv).strftime('%Y-%m-%d')
                        backtest_trades.setdefault(ds, []).append({
                            "symbol": symbol, "side": "COVER", "qty": shares,
                            "price": None if pd.isna(cv_price) else float(cv_price),
                            "source": "SHORT"
                        })

        # 3) Sort dates and trades for stable output
        ordered = {d: backtest_trades[d] for d in sorted(backtest_trades.keys())}
        with open("trades_by_day.json", "w") as f:
            json.dump(ordered, f, indent=2)
        print("✅ Full-Backtest abgeschlossen und Trades exportiert (matched trades basis).")

        # 4) Standardisierte Statistik-Ausgabe (gleiche Formatierung für alle Ticker)
        print("\n📊 Zusammenfassung je Ticker (Long/Short):")
        for symbol, cfg in tickers.items():
            data_path = f"{symbol}_data.csv"
            if not os.path.exists(data_path):
                continue
            try:
                df_price = pd.read_csv(data_path, parse_dates=["date"], index_col="date")
            except Exception:
                continue

            # LONG
            if cfg.get("long", False) and os.path.exists(f"trades_long_{symbol}.csv"):
                df_long = pd.read_csv(f"trades_long_{symbol}.csv", parse_dates=["buy_date", "sell_date"])
                trades_long = df_long.to_dict("records")
                eq_long = compute_equity_curve(df_price, trades_long, cfg.get("initialCapitalLong", 0), long=True) if trades_long else []
                final_cap_long = eq_long[-1] if eq_long else cfg.get("initialCapitalLong", 0)
                stats(trades_long, f"{symbol} LONG", initial_capital=cfg.get("initialCapitalLong"), final_capital=final_cap_long, equity_curve=eq_long)
            else:
                print(f"\n{symbol} LONG: Keine Trades oder deaktiviert")

            # SHORT
            if cfg.get("short", False) and os.path.exists(f"trades_short_{symbol}.csv"):
                df_short = pd.read_csv(f"trades_short_{symbol}.csv", parse_dates=["short_date", "cover_date"])
                trades_short = df_short.to_dict("records")
                eq_short = compute_equity_curve(df_price, trades_short, cfg.get("initialCapitalShort", 0), long=False) if trades_short else []
                final_cap_short = eq_short[-1] if eq_short else cfg.get("initialCapitalShort", 0)
                stats(trades_short, f"{symbol} SHORT", initial_capital=cfg.get("initialCapitalShort"), final_capital=final_cap_short, equity_curve=eq_short)
            else:
                print(f"\n{symbol} SHORT: Keine Trades oder deaktiviert")

    else:
        print(f"⚠️ Unbekannter Modus: {mode}")

    if ib is not None:
        ib.disconnect()

if __name__ == "__main__":
    main()
