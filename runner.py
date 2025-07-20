from ib_insync import IB, Contract
from tickers_config import tickers
from trade_execution import execute_trades, get_backtest_price, plan_trade_qty
from simulation_utils import generate_backtest_date_range
from backtesting_core import run_full_backtest
import json
import os
import sys

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
        # Example: get live prices using conID (if you want to show live info)
        # for t in trades:
        #     cfg = tickers[t['symbol']]
        #     contract = Contract(conId=cfg["conID"], exchange="SMART", currency="USD")
        #     # ticker = ib.reqMktData(contract, '', False, False)
        #     # print(f"{t['symbol']}: {ticker.marketPrice()}")

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
        max_missing_days = 3
        missing_days = {symbol: 0 for symbol in tickers}
        skip_tickers = set()
        backtest_trades = {}
        for date_str in generate_backtest_date_range("2025-07-01", "2025-07-18"):
            trades = []
            portfolio = {s: 0 for s in tickers}
            for symbol, cfg in tickers.items():
                if symbol in skip_tickers:
                    continue
                field = cfg.get("trade_on", "Close").capitalize()
                price = get_backtest_price(symbol, date_str, field)
                if price is None:
                    missing_days[symbol] += 1
                    print(f"{symbol}: keine Daten für {date_str}")
                    if missing_days[symbol] >= max_missing_days:
                        print(f"\nAborting for {symbol}: {missing_days[symbol]} consecutive days without price data. Skipping this ticker for the rest of the backtest.")
                        skip_tickers.add(symbol)
                    continue
                else:
                    missing_days[symbol] = 0
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
            backtest_trades[date_str] = trades
            print(f"📅 {date_str}:")
            if trades:
                for t in trades:
                    print(f"  {t['symbol']}: {t['side']} {t['qty']} @ {t['price']}")
            else:
                print("  Keine Trades erzeugt.")
        # Exportiere als JSON
        with open("trades_by_day.json", "w") as f:
            json.dump(backtest_trades, f, indent=2)
        print("✅ Full-Backtest abgeschlossen und Trades exportiert.")

    else:
        print(f"⚠️ Unbekannter Modus: {mode}")

    ib.disconnect()

if __name__ == "__main__":
    main()