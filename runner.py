import sys
from ib_insync import IB
from backtesting_core import (
    run_full_backtest,
    test_trading_for_date,
    trade_trading_for_today,
    preview_trades_for_today,
    test_extended_for_date,
    update_historical_data_csv
)
from simulation_utils import generate_backtest_date_range
from trade_execution import execute_trades, get_backtest_price, plan_trade_qty
from tickers_config import tickers
import json
import os

def load_trades_for_day(date_str, json_path="trades_by_day.json"):
    """
    Lädt die Trades für einen bestimmten Tag aus der Backtest-Datei.
    Gibt (trades, portfolio_snapshot) zurück.
    """
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

def list_trade_days(json_path="trades_by_day.json"):
    """
    Gibt alle Tage zurück, für die in trades_by_day.json aktive Trades vorliegen.
    Nur Tage mit mindestens einem Trade werden angezeigt.
    """
    if not os.path.exists(json_path):
        print(f"⚠️ Datei {json_path} nicht gefunden.")
        return

    try:
        with open(json_path, "r") as f:
            data = json.load(f)
    except Exception as e:
        print(f"⚠️ Fehler beim Laden von {json_path}: {e}")
        return

    active_days = [day for day, trades in data.items() if trades]
    if not active_days:
        print("ℹ️ Keine aktiven Tage mit Trades gefunden.")
        return

    print("\n📅 Tage mit aktiven Trades im Backtest:")
    for day in sorted(active_days):
        print(f"  • {day}")

def print_trade_summary(trades, portfolio_snapshot):
    if not trades:
        print("\nℹ️ Keine Trades generiert.")
        return

    # Einstiegstrades: BUY & SHORT
    entry_trades = [t for t in trades if t["side"] in ("BUY", "SHORT")]

    # Exittrades: SELL & COVER
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
from trade_execution import get_backtest_price, plan_trade_qty
from tickers_config import tickers

def generate_trades_for_day(date_str):
    trades = []
    portfolio = {s: 0 for s in tickers}

    for symbol, cfg in tickers.items():
        field = cfg.get("trade_on", "Close").capitalize()
        price = get_backtest_price(symbol, date_str, field)
        if price is None:
            continue

        for side in ("BUY", "SHORT", "SELL", "COVER"):
            if not cfg.get(side.lower(), False):
                continue

            if side in ("SELL", "COVER"):
                qty = abs(portfolio.get(symbol, 0))
                if qty == 0:
                    continue
            else:
                qty = plan_trade_qty(symbol, side, portfolio, price)
                if qty <= 0:
                    continue

            trades.append({
                "symbol": symbol,
                "side": side,
                "qty": qty,
                "price": round(price, 2)
            })

            delta = qty if side in ("BUY", "COVER") else -qty
            portfolio[symbol] += delta

    return trades

def main():
    if len(sys.argv) < 2:
        print("⚠️ Bitte gib einen Modus an: testdate, tradedate, fullbacktest")
        return

    mode = sys.argv[1].lower()
    ib = IB()
    ib.connect("127.0.0.1", 7497, clientId=1)

    if mode == "testdate":
        date_str = sys.argv[2]
        trades, portfolio = load_trades_for_day(date_str)

        if not trades:
            print(f"\n📅 {date_str}: Keine Trades an diesem Tag.")
            return

        print_trade_summary(trades, portfolio)

    elif mode == "tradedate":
        tradedate = sys.argv[2]
        trades, _ = load_trades_for_day(tradedate)

        if not trades:
            print(f"\n📅 {tradedate}: Kein Trade aus dem Backtest.")
            return

        execute_trades(ib, trades)

    elif mode == "listdays":
        list_trade_days()
        return

    elif mode == "fullbacktest":
        run_full_backtest(ib):
'''        for symbol, cfg in tickers.items():
            fn = f"{symbol}_data.csv"
            contract = cfg["contract"]  # z. B. Stock(symbol, "SMART", "USD")
            df = update_historical_data_csv(ib, contract, fn)
            # Weitere Verarbeitung / Simulationslogik …
            print("✅ Historische Kursdaten aktualisiert – starte Trade-Generierung.")

            # Trade-Erzeugung für jeden Tag im gewünschten Zeitraum
            from datetime import datetime

            backtest_trades = {}
            for date_str in generate_backtest_date_range("2025-07-01", "2025-07-18"):
                trades = generate_trades_for_day(date_str)
                backtest_trades[date_str] = trades
                print(f"📅 {date_str}: {len(trades)} Trades erzeugt.")

            # Exportiere als JSON
            import json
            with open("trades_by_day.json", "w") as f:
                json.dump(backtest_trades, f, indent=2)

            print("✅ Full-Backtest abgeschlossen und Trades exportiert.")

        print("✅ Full-Backtest abgeschlossen.")
        import json

        backtest_trades = {}

        for date_str in generate_backtest_date_range():  # z. B. 2025-07-01 bis 2025-07-18
            trades = generate_trades_for_day(date_str)   # ← deine Strategie
            backtest_trades[date_str] = trades

        # Datei speichern
        with open("trades_by_day.json", "w") as f:
            json.dump(backtest_trades, f, indent=2)

    else:
        print(f"⚠️ Unbekannter Modus: {mode}")
'''
    ib.disconnect()

if __name__ == "__main__":
    main()
