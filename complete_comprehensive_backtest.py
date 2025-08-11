#!/usr/bin/env python3
"""
Complete Comprehensive Backtest System
Shows extended signals, matched trades, and capital curves
Uses the proven data download mechanism from runner.py fullbacktest
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json

# Add the current directory to Python path to import local modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ib_insync import IB
from tickers_config import tickers
from backtesting_core import run_full_backtest, berechne_best_p_tw_long, berechne_best_p_tw_short
from trade_execution import get_backtest_price
from simulation_utils import generate_backtest_date_range, simulate_trades_compound_extended, compute_equity_curve
from config import COMMISSION_RATE, MIN_COMMISSION, trade_years
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
        print(f"❌ Data file not found: {filename}")
        return None
    
    try:
        df = pd.read_csv(filename, index_col=0, parse_dates=True)
        df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close"}, inplace=True)
        df.sort_index(inplace=True)
        
        print(f"📊 Loaded {len(df)} rows of data for {ticker_name}")
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
            print(f"\n📈 Processing Long Strategy for {ticker_name}")
            
            # Optimize parameters
            print("   🎯 Optimizing parameters...")
            p_long, tw_long = berechne_best_p_tw_long(df, ticker_config, verbose=False, ticker=ticker_name)
            print(f"   ✅ Best Long Parameters: p={p_long}, tw={tw_long}")
            
            # Calculate support/resistance
            sup_long, res_long = calculate_support_resistance(df, p_long, tw_long)
            
            # Generate extended signals
            ext_long = assign_long_signals_extended(sup_long, res_long, df, tw_long, "1d")
            ext_long = update_level_close_long(ext_long, df)
            
            print(f"   📊 Generated {len(ext_long)} extended long signals")
            
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
                print(f"   💰 Final Capital from simulation: {cap_long:.2f}")
                print(f"   📈 Final value from equity curve: {curve_final:.2f}")
                print(f"   ✅ Match: {'YES' if abs(cap_long - curve_final) < 0.01 else 'NO'}")
            
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
            print(f"\n📉 Processing Short Strategy for {ticker_name}")
            
            # Optimize parameters
            print("   🎯 Optimizing parameters...")
            p_short, tw_short = berechne_best_p_tw_short(df, ticker_config, verbose=False, ticker=ticker_name)
            print(f"   ✅ Best Short Parameters: p={p_short}, tw={tw_short}")
            
            # Calculate support/resistance
            sup_short, res_short = calculate_support_resistance(df, p_short, tw_short)
            
            # Generate extended signals
            ext_short = assign_short_signals_extended(sup_short, res_short, df, tw_short, "1d")
            ext_short = update_level_close_short(ext_short, df)
            
            print(f"   📊 Generated {len(ext_short)} extended short signals")
            
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
                print(f"   💰 Final Capital from simulation: {cap_short:.2f}")
                print(f"   📈 Final value from equity curve: {curve_final:.2f}")
                print(f"   ✅ Match: {'YES' if abs(cap_short - curve_final) < 0.01 else 'NO'}")
            
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
            print(f"   📊 Chart saved to {ticker_name}_chart.html")
        except Exception as e:
            print(f"   ⚠️ Chart generation failed: {e}")
        
        return results
        
    except Exception as e:
        print(f"❌ Error processing {ticker_name}: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    """
    Main function that orchestrates the complete comprehensive backtest.
    """
    print("🚀 Starting Complete Comprehensive Backtest System")
    print("=" * 60)
    
    # Connect to Interactive Brokers
    ib = IB()
    try:
        ib.connect('127.0.0.1', 7497, clientId=1)  # Paper trading port
        print("✅ Connected to Interactive Brokers (Paper Trading)")
    except Exception as e:
        print(f"❌ Failed to connect to Interactive Brokers: {e}")
        print("Make sure TWS/IB Gateway is running on port 7497 (Paper Trading)")
        return
    
    try:
        # Step 1: Download all data using the proven method
        print(f"\n📊 Step 1: Downloading {trade_years} years of data for all tickers...")
        print("Using proven data download from runner.py fullbacktest...")
        
        run_full_backtest(ib)
        print("✅ Data download and optimization completed")
        
        # Step 2: Process each ticker for complete backtest
        print(f"\n🎯 Step 2: Processing complete backtest for each ticker...")
        
        all_results = {}
        
        # Process only a few tickers first to test
        test_tickers = ["AAPL", "GOOGL", "AMD"]  # Start with just 3 tickers
        
        for ticker_name, ticker_config in tickers.items():
            if ticker_name not in test_tickers:
                continue
                
            # Skip if no strategies are enabled for this ticker
            if not any([ticker_config.get("long", False), ticker_config.get("short", False)]):
                print(f"⏭️ Skipping {ticker_name}: No strategies enabled")
                continue
            
            result = process_ticker_backtest(ib, ticker_name, ticker_config)
            if result:
                all_results[ticker_name] = result
        
        # Step 3: Generate comprehensive summary
        print(f"\n{'='*60}")
        print("📊 COMPREHENSIVE BACKTEST SUMMARY")
        print(f"{'='*60}")
        
        for ticker_name, data in all_results.items():
            ticker_config = tickers[ticker_name]  # Get ticker config for trade_on info
            print(f"\n🎯 {ticker_name}:")
            print(f"   📅 Data: {data['data_info']['start_date']} to {data['data_info']['end_date']} ({data['data_info']['rows']} days)")
            print(f"   ⚙️  Trade On: {ticker_config.get('trade_on', 'close').upper()}")
            
            if "long" in data:
                long_data = data["long"]
                print(f"   📈 Long: p={long_data['parameters']['p']}, tw={long_data['parameters']['tw']}")
                print(f"       Extended Signals: {long_data['extended_signals']}")
                print(f"       Matched Trades: {long_data['matched_trades']}")
                print(f"       Initial Capital: ${long_data['initial_capital']:.2f}")
                print(f"       Final Capital: ${long_data['final_capital']:.2f}")
                if long_data['equity_curve']:
                    print(f"       Equity Curve Final: ${long_data['equity_curve'][-1]:.2f}")
                    print(f"       Return: {((long_data['final_capital'] / long_data['initial_capital']) - 1) * 100:.2f}%")
            
            if "short" in data:
                short_data = data["short"]
                print(f"   📉 Short: p={short_data['parameters']['p']}, tw={short_data['parameters']['tw']}")
                print(f"       Extended Signals: {short_data['extended_signals']}")
                print(f"       Matched Trades: {short_data['matched_trades']}")
                print(f"       Initial Capital: ${short_data['initial_capital']:.2f}")
                print(f"       Final Capital: ${short_data['final_capital']:.2f}")
                if short_data['equity_curve']:
                    print(f"       Equity Curve Final: ${short_data['equity_curve'][-1]:.2f}")
                    print(f"       Return: {((short_data['final_capital'] / short_data['initial_capital']) - 1) * 100:.2f}%")
        
        # Step 4: Export detailed results
        print(f"\n💾 Step 4: Exporting detailed results...")
        
        # Save complete results to JSON
        export_data = {}
        for ticker_name, data in all_results.items():
            export_data[ticker_name] = {
                "data_info": data["data_info"],
                "long": data.get("long", {}),
                "short": data.get("short", {})
            }
        
        with open("complete_comprehensive_backtest_results.json", "w") as f:
            json.dump(export_data, f, indent=2, default=str)
        
        print(f"✅ Complete results exported to: complete_comprehensive_backtest_results.json")
        print(f"✅ Individual charts saved as: [TICKER]_chart.html")
        print(f"✅ Complete comprehensive backtest finished!")
        
    except Exception as e:
        print(f"❌ Error during backtest: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Always disconnect from IB
        if ib.isConnected():
            ib.disconnect()
            print("🔌 Disconnected from Interactive Brokers")

if __name__ == "__main__":
    main()
