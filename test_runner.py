#!/usr/bin/env python3
import sys
print("Script started")
print(f"Arguments: {sys.argv}")

if len(sys.argv) < 2:
    print("⚠️ Bitte gib einen Modus an: testdate, tradedate, listdays, fullbacktest")
    print("Beispiele:")
    print("  python runner.py testdate 2025-07-15")
    print("  python runner.py tradedate 2025-07-15")
    print("  python runner.py listdays")
    print("  python runner.py fullbacktest")
else:
    mode = sys.argv[1].lower()
    print(f"Mode: {mode}")
    
    if mode == "testdate":
        if len(sys.argv) < 3:
            print("Need date argument!")
        else:
            print(f"Testing date: {sys.argv[2]}")
            # Check if trades_by_day.json exists
            import os
            if not os.path.exists("trades_by_day.json"):
                print("⚠️ trades_by_day.json not found - run fullbacktest first")
            else:
                print("trades_by_day.json exists")
