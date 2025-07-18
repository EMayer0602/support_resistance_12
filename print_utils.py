# print_utils.py

import pandas as pd

def print_matched_long_trades(matched, ticker):
    print(f"\n## Matched Long Trades – {ticker}")
    if not matched:
        print("_Keine Long-Trades gefunden._")
    else:
        df = pd.DataFrame(matched)
        print(df.to_markdown(index=False))

def print_matched_short_trades(matched, ticker):
    print(f"\n## Matched Short Trades – {ticker}")
    if not matched:
        print("_Keine Short-Trades gefunden._")
    else:
        df = pd.DataFrame(matched)
        print(df.to_markdown(index=False))
