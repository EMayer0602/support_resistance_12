"""Quick assertions to verify each ticker uses the intended price column (Open vs Close)
for support/resistance detection and trade execution.

Run:
    python verify_price_column_usage.py

Outputs PASS/FAIL per ticker and example sampled levels & trade prices.
"""
import pandas as pd
from tickers_config import tickers
from signal_utils import calculate_support_resistance
from simulation_utils import get_trade_price

SAMPLE_POINTS = 3

def main():
    all_pass = True
    for sym, cfg in tickers.items():
        price_col_expected = 'Open' if cfg.get('trade_on','close').lower()=='open' else 'Close'
        data_file = f"{sym}_data.csv"
        try:
            df = pd.read_csv(data_file, index_col=0, parse_dates=True)
        except Exception as e:
            print(f"[FAIL] {sym}: cannot read {data_file}: {e}")
            all_pass = False
            continue
        sup, res = calculate_support_resistance(df, past_window=5, trade_window=5, price_col=price_col_expected)
        # Verify sampled support points equal original df values from expected column
        sample_support = sup.sort_index().head(SAMPLE_POINTS)
        mismatches = []
        for dt, level in sample_support.items():
            orig = df.loc[dt, price_col_expected] if dt in df.index else None
            if orig is None or abs(orig - level) > 1e-6:
                mismatches.append((dt, level, orig))
        if mismatches:
            print(f"[FAIL] {sym}: Support levels mismatch expected column {price_col_expected}: {mismatches[:2]}")
            all_pass = False
        else:
            print(f"[OK]   {sym}: Support derives from {price_col_expected} (checked {len(sample_support)} points)")
        # Spot-check a future trade date price
        if not df.empty:
            mid_date = df.index[len(df)//2]
            trade_price = get_trade_price(df, cfg, mid_date)
            orig = df.loc[mid_date, price_col_expected]
            if abs(trade_price - orig) > 1e-9:
                print(f"[FAIL] {sym}: Trade price {trade_price} != {price_col_expected} {orig}")
                all_pass = False
            else:
                print(f"       {sym}: Execution price uses {price_col_expected}")
    print("\nRESULT:", "ALL PASS" if all_pass else "CHECK FAILURES ABOVE")

if __name__ == '__main__':
    main()
