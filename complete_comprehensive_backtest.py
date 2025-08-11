#!/usr/bin/env python3
"""
Complete Comprehensive Backtest System
Shows extended signals, matched trades, and capital curves
Uses the proven data download mechanism from runner.py fullbacktest
"""

import os
import sys
import pandas as pd
from datetime import datetime, timedelta
import json

# Add the current directory to Python path to import local modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from tickers_config import tickers
from backtesting_core import berechne_best_p_tw_long, berechne_best_p_tw_short
from simulation_utils import simulate_trades_compound_extended, compute_equity_curve
from config import DEFAULT_COMMISSION_RATE, MIN_COMMISSION, trade_years
COMMISSION_RATE = DEFAULT_COMMISSION_RATE  # Use the config value
from signal_utils import (
    calculate_support_resistance,
    assign_long_signals_extended,
    assign_short_signals_extended,
    update_level_close_long,
    update_level_close_short
)
from stats_tools import stats
from plot_utils import plot_combined_chart_and_equity

def process_ticker_backtest(ib, ticker_name, ticker_config):
    """
    Process a complete backtest for one ticker including:
    - Parameter optimization
    - Extended signal generation 
    - Matched trade simulation
    - Capital curve calculation
    """
    print(f"\n{'='*20} Processing {ticker_name} {'='*20}")
    
    # Load data from CSV (already downloaded by run_full_backtest)
    filename = f"{ticker_name}_data.csv"
    if not os.path.exists(filename):
        print(f"[FAIL] Data file not found: {filename}")
        return None

    try:
        df = pd.read_csv(filename, index_col=0, parse_dates=True)
        df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close"}, inplace=True)
        df.sort_index(inplace=True)

        print(f"[DATA] Loaded {len(df)} rows of data for {ticker_name}")
        print(f"   Date range: {df.index[0].date()} to {df.index[-1].date()}")
        
        # Get last price and date for artificial close
        last_price = df["Close"].iloc[-1]
        last_date = df.index[-1]
        
        results = {
            "ticker": ticker_name,
            "config": ticker_config,
            "data_info": {
                "rows": len(df),
                "start_date": str(df.index[0].date()),
                "end_date": str(df.index[-1].date()),
                "last_price": last_price
            }
        }
        
        # Process Long strategy if enabled
        if ticker_config.get("long", False):
            print(f"\n[LONG] Processing Long Strategy for {ticker_name}")
            
            # Optimize parameters
            print("   Optimizing parameters...")
            p_long, tw_long = berechne_best_p_tw_long(df, ticker_config, verbose=False, ticker=ticker_name)
            print(f"   OK Best Long Parameters: p={p_long}, tw={tw_long}")
            
            # Calculate support/resistance
            sup_long, res_long = calculate_support_resistance(df, p_long, tw_long)
            
            # Generate extended signals
            ext_long = assign_long_signals_extended(sup_long, res_long, df, tw_long, "1d")
            ext_long = update_level_close_long(ext_long, df)
            
            print(f"   Generated {len(ext_long)} extended long signals")
            
            # Simulate matched trades
            cap_long, trades_long = simulate_trades_compound_extended(
                ext_long, df, ticker_config,
                COMMISSION_RATE, MIN_COMMISSION,
                ticker_config.get("order_round_factor", 1),
                artificial_close_price=last_price,
                artificial_close_date=last_date,
                direction="long"
            )
            
            # Calculate equity curve
            initial_capital = ticker_config.get("initialCapitalLong", 1000)
            equity_curve_long = compute_equity_curve(df, trades_long, initial_capital, long=True)
            
            # Verify capital curve final value matches final capital
            if equity_curve_long:
                curve_final = equity_curve_long[-1]
                print(f"   Final Capital from simulation: {cap_long:.2f}")
                print(f"   Final value from equity curve: {curve_final:.2f}")
                print(f"   Match: {'YES' if abs(cap_long - curve_final) < 0.01 else 'NO'}")
            
            results["long"] = {
                "parameters": {"p": p_long, "tw": tw_long},
                "extended_signals": len(ext_long),
                "matched_trades": len(trades_long),
                "final_capital": cap_long,
                "initial_capital": initial_capital,
                "equity_curve": equity_curve_long,
                "trades": trades_long,
                "extended_signals_data": ext_long.to_dict('records') if not ext_long.empty else []
            }
            
            # Print trade statistics
            stats(trades_long, f"{ticker_name} Long")
        
        # Process Short strategy if enabled
        if ticker_config.get("short", False):
            print(f"\n[SHORT] Processing Short Strategy for {ticker_name}")
            
            # Optimize parameters
            print("   Optimizing parameters...")
            p_short, tw_short = berechne_best_p_tw_short(df, ticker_config, verbose=False, ticker=ticker_name)
            print(f"   OK Best Short Parameters: p={p_short}, tw={tw_short}")
            
            # Calculate support/resistance
            sup_short, res_short = calculate_support_resistance(df, p_short, tw_short)
            
            # Generate extended signals
            ext_short = assign_short_signals_extended(sup_short, res_short, df, tw_short, "1d")
            ext_short = update_level_close_short(ext_short, df)
            
            print(f"   Generated {len(ext_short)} extended short signals")
            
            # Simulate matched trades
            cap_short, trades_short = simulate_trades_compound_extended(
                ext_short, df, ticker_config,
                COMMISSION_RATE, MIN_COMMISSION,
                ticker_config.get("order_round_factor", 1),
                artificial_close_price=last_price,
                artificial_close_date=last_date,
                direction="short"
            )
            
            # Calculate equity curve
            initial_capital = ticker_config.get("initialCapitalShort", 1000)
            equity_curve_short = compute_equity_curve(df, trades_short, initial_capital, long=False)
            
            # Verify capital curve final value matches final capital
            if equity_curve_short:
                curve_final = equity_curve_short[-1]
                print(f"   Final Capital from simulation: {cap_short:.2f}")
                print(f"   Final value from equity curve: {curve_final:.2f}")
                print(f"   Match: {'YES' if abs(cap_short - curve_final) < 0.01 else 'NO'}")
            
            results["short"] = {
                "parameters": {"p": p_short, "tw": tw_short},
                "extended_signals": len(ext_short),
                "matched_trades": len(trades_short),
                "final_capital": cap_short,
                "initial_capital": initial_capital,
                "equity_curve": equity_curve_short,
                "trades": trades_short,
                "extended_signals_data": ext_short.to_dict('records') if not ext_short.empty else []
            }
            
            # Print trade statistics
            stats(trades_short, f"{ticker_name} Short")
        
        # Generate combined chart
        try:
            plot_combined_chart_and_equity(
                df, 
                results.get("long", {}).get("trades", []),
                results.get("short", {}).get("trades", []),
                ticker_name
            )
            print(f"   Chart saved to {ticker_name}_chart.html")
        except Exception as e:
            print(f"   WARN Chart generation failed: {e}")
        
        return results
        
    except Exception as e:
        print(f"[FAIL] Error processing {ticker_name}: {e}")
        import traceback
        traceback.print_exc()
    return None

def update_yesterday_ohlc_in_results():
    """Update yesterday's artificial prices in the backtest results file with true OHLC from CSV."""
    import json
    from datetime import datetime, timedelta
    results_file = 'complete_comprehensive_backtest_results.json'
    if not os.path.exists(results_file):
        return
    try:
        with open(results_file, 'r') as f:
            results = json.load(f)
    except Exception:
        return
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    changed = False
    for ticker, ticker_data in results.items():
        csv_file = f"{ticker}_data.csv"
        if not os.path.exists(csv_file):
            continue
        try:
            import pandas as pd
            df = pd.read_csv(csv_file, index_col=0, parse_dates=True)
            if yesterday not in df.index.strftime('%Y-%m-%d'):
                continue
            row = df.loc[df.index.strftime('%Y-%m-%d') == yesterday].iloc[0]
            ohlc = {
                'open': float(row['Open']) if 'Open' in row else None,
                'high': float(row['High']) if 'High' in row else None,
                'low': float(row['Low']) if 'Low' in row else None,
                'close': float(row['Close']) if 'Close' in row else None
            }
        except Exception:
            continue
        # Update long/short extended_signals for yesterday
        for strat in ['long_strategy', 'short_strategy']:
            if strat in ticker_data and 'extended_signals' in ticker_data[strat]:
                for sig in ticker_data[strat]['extended_signals']:
                    if sig.get('date') == yesterday:
                        # Only update if price is None or marked as artificial
                        if sig.get('price') is None or sig.get('price') == 'artificial':
                            # Use close for now (can be changed to open/close as needed)
                            sig['price'] = ohlc['close']
                            sig['open'] = ohlc['open']
                            sig['high'] = ohlc['high']
                            sig['low'] = ohlc['low']
                            sig['close'] = ohlc['close']
                            changed = True
    if changed:
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"[INFO] Updated OHLC prices for {yesterday} in {results_file}")

if __name__ == "__main__":
    print("[START] Starting Complete Comprehensive Backtest System")
    print("=" * 60)

    # Update yesterday's OHLC in prior results (if any)
    try:
        update_yesterday_ohlc_in_results()
    except Exception as _e:
        # Non-fatal
        print(f"[WARN] Could not update yesterday OHLC in prior results: {_e}")

    # Connect to Interactive Brokers (optional)
    ib = None
    try:
        from ib_insync import IB
        ib = IB()
        ib.connect('127.0.0.1', 7497, clientId=1)  # Paper trading port
        print("[OK] Connected to Interactive Brokers (Paper Trading)")
    except Exception as e:
        print(f"[WARN] Could not connect to Interactive Brokers: {e}")
        print("[INFO] Continuing using existing cached CSV data only...")

    import argparse
    parser = argparse.ArgumentParser(description='Run the complete comprehensive backtest for all tickers')
    parser.add_argument('--tickers', nargs='*', help='List of tickers to process (default: all)')
    args = parser.parse_args()

    # Run for all tickers or a subset
    tickers_to_run = args.tickers if args.tickers else list(tickers.keys())
    all_results = {}

    for ticker in tickers_to_run:
        ticker_config = tickers[ticker]
        # Skip if no strategies are enabled for this ticker
        if not any([ticker_config.get("long", False), ticker_config.get("short", False)]):
            print(f"Skipping {ticker}: No strategies enabled")
            continue

        result = process_ticker_backtest(ib, ticker, ticker_config)
        if result:
            all_results[ticker] = result

    # Export results in structure consumable by check_todays_signals.py
    export_data = {}
    for ticker_name, data in all_results.items():
        export_entry = {
            "data_info": data.get("data_info", {}),
        }
        # Map long strategy if present
        if "long" in data:
            long_info = data["long"]
            p_param = long_info.get("parameters", {}).get("p")
            tw_param = long_info.get("parameters", {}).get("tw")
            ext_rows = long_info.get("extended_signals_data", [])
            long_ext = []
            for row in ext_rows:
                action = row.get("Long Action")
                date_str = str(row.get("Long Date detected"))[:10]
                if action in ("buy", "sell") and date_str and date_str != "nan":
                    price = row.get("Level trade") or row.get("Level Close")
                    try:
                        price_val = float(price) if price is not None and price == price else None
                    except Exception:
                        price_val = None
                    long_ext.append({
                        "date": date_str,
                        "action": action.upper(),
                        "price": price_val,
                        "signal_type": row.get("Supp/Resist"),
                        "p_param": p_param,
                        "tw_param": tw_param,
                    })
            export_entry["long_strategy"] = {
                "parameters": long_info.get("parameters", {}),
                "extended_signals": long_ext,
            }
        # Map short strategy if present
        if "short" in data:
            short_info = data["short"]
            p_param = short_info.get("parameters", {}).get("p")
            tw_param = short_info.get("parameters", {}).get("tw")
            ext_rows = short_info.get("extended_signals_data", [])
            short_ext = []
            for row in ext_rows:
                action = row.get("Short Action")
                date_str = str(row.get("Short Date detected"))[:10]
                if action in ("short", "cover") and date_str and date_str != "nan":
                    price = row.get("Level trade") or row.get("Level Close")
                    try:
                        price_val = float(price) if price is not None and price == price else None
                    except Exception:
                        price_val = None
                    short_ext.append({
                        "date": date_str,
                        "action": ("SHORT" if action == "short" else "COVER"),
                        "price": price_val,
                        "signal_type": row.get("Supp/Resist"),
                        "p_param": p_param,
                        "tw_param": tw_param,
                    })
            export_entry["short_strategy"] = {
                "parameters": short_info.get("parameters", {}),
                "extended_signals": short_ext,
            }

        export_data[ticker_name] = export_entry

    with open("complete_comprehensive_backtest_results.json", "w") as f:
        json.dump(export_data, f, indent=2, default=str)

    print("[DONE] All results saved to complete_comprehensive_backtest_results.json")
    print("[OK] Individual charts saved as: [TICKER]_chart.html")
    print("[OK] Complete comprehensive backtest finished!")

    # Clean up IB connection if open
    if ib is not None:
        try:
            ib.disconnect()
        except Exception:
            pass
