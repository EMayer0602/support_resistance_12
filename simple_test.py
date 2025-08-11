import json
import os

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

# Test for July 1st (should have trades)
print("=== Testing 2025-07-01 ===")
trades, portfolio = load_trades_for_day("2025-07-01")
if trades:
    print(f"Found {len(trades)} trades:")
    for t in trades:
        print(f"  {t['symbol']}: {t['side']} {t['qty']} @ ${t['price']}")
else:
    print("No trades found")

print("\n=== Testing 2025-08-06 ===")
trades, portfolio = load_trades_for_day("2025-08-06")
if trades:
    print(f"Found {len(trades)} trades")
else:
    print("No trades found for this date - it's outside the backtest range")
    
print("\n=== Available dates ===")
with open("trades_by_day.json", "r") as f:
    all_data = json.load(f)
    
dates_with_trades = []
for date, trades in all_data.items():
    if trades:  # Only dates with actual trades
        dates_with_trades.append(date)

print(f"Dates with trades: {dates_with_trades}")
