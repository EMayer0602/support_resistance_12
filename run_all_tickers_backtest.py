#!/usr/bin/env python3
"""
Run comprehensive backtest for ALL tickers and save results
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
    """Process a complete backtest for one ticker"""
    print(f"Processing {ticker_name}...")
    
    # Load data from CSV (already downloaded by run_full_backtest)
    filename = f"{ticker_name}_data.csv"
    if not os.path.exists(filename):
        print(f"❌ Data file not found: {filename}")
        return None
    
    try:
        df_full = pd.read_csv(filename, parse_dates=['date'], index_col='date')
        df_full = df_full.dropna()
        
        if df_full.empty:
            print(f"❌ No data for {ticker_name}")
            return None
            
        # Generate backtest date range
        start_date, end_date = generate_backtest_date_range(df_full)
        df_bt = df_full[start_date:end_date].copy()
        
        if df_bt.empty:
            print(f"❌ No backtest data for {ticker_name}")
            return None
            
        print(f"   Data: {df_bt.index[0].date()} to {df_bt.index[-1].date()} ({len(df_bt)} days)")
        
        # Calculate support/resistance
        df_bt = calculate_support_resistance(df_bt, p=3)
        
        results = {
            'data_info': {
                'start_date': df_bt.index[0].strftime('%Y-%m-%d'),
                'end_date': df_bt.index[-1].strftime('%Y-%m-%d'),
                'rows': len(df_bt)
            }
        }
        
        # Long strategy optimization and simulation
        if ticker_config['long']:
            print(f"   Processing Long strategy...")
            best_p_long, best_tw_long, _ = berechne_best_p_tw_long(df_bt, ib, ticker_name)
            
            # Generate extended signals with optimized parameters
            df_bt_long = calculate_support_resistance(df_bt.copy(), p=best_p_long)
            df_bt_long = assign_long_signals_extended(df_bt_long, tw=best_tw_long)
            df_bt_long = update_level_close_long(df_bt_long)
            
            extended_signals = df_bt_long['Signal_Long'].sum()
            
            # Simulate trades
            initial_capital = ticker_config['initialCapitalLong']
            results_long = simulate_trades_compound_extended(
                df_bt_long, initial_capital, ticker_name, 'long', ib
            )
            
            matched_trades = len(results_long['trades'])
            final_capital = results_long['final_capital']
            
            results['long'] = {
                'parameters': {'p': best_p_long, 'tw': best_tw_long},
                'extended_signals': int(extended_signals),
                'matched_trades': matched_trades,
                'initial_capital': initial_capital,
                'final_capital': final_capital
            }
            
        # Short strategy optimization and simulation  
        if ticker_config['short']:
            print(f"   Processing Short strategy...")
            best_p_short, best_tw_short, _ = berechne_best_p_tw_short(df_bt, ib, ticker_name)
            
            # Generate extended signals with optimized parameters
            df_bt_short = calculate_support_resistance(df_bt.copy(), p=best_p_short)
            df_bt_short = assign_short_signals_extended(df_bt_short, tw=best_tw_short)
            df_bt_short = update_level_close_short(df_bt_short)
            
            extended_signals = df_bt_short['Signal_Short'].sum()
            
            # Simulate trades
            initial_capital = ticker_config['initialCapitalShort']
            results_short = simulate_trades_compound_extended(
                df_bt_short, initial_capital, ticker_name, 'short', ib
            )
            
            matched_trades = len(results_short['trades'])
            final_capital = results_short['final_capital']
            
            results['short'] = {
                'parameters': {'p': best_p_short, 'tw': best_tw_short},
                'extended_signals': int(extended_signals),
                'matched_trades': matched_trades,
                'initial_capital': initial_capital,
                'final_capital': final_capital
            }
        
        print(f"   ✅ {ticker_name} completed")
        return results
        
    except Exception as e:
        print(f"❌ Error processing {ticker_name}: {e}")
        return None

def main():
    """Main execution function"""
    print("🚀 STARTING COMPREHENSIVE BACKTEST FOR ALL TICKERS")
    print("="*60)
    
    # Connect to IB
    ib = IB()
    try:
        ib.connect('127.0.0.1', 7497, clientId=1)
        print("✅ Connected to Interactive Brokers")
    except Exception as e:
        print(f"❌ Failed to connect to IB: {e}")
        return
    
    try:
        # First, ensure we have data for all tickers
        print("\n📊 Downloading data for all tickers...")
        run_full_backtest(ib)
        print("✅ Data download completed")
        
        # Process each ticker
        all_results = {}
        total_tickers = len(tickers)
        
        for i, (ticker_name, ticker_config) in enumerate(tickers.items(), 1):
            print(f"\n[{i}/{total_tickers}] {ticker_name}")
            results = process_ticker_backtest(ib, ticker_name, ticker_config)
            if results:
                all_results[ticker_name] = results
        
        # Save results to file
        with open('all_tickers_backtest_results.json', 'w') as f:
            json.dump(all_results, f, indent=2, default=str)
        
        print(f"\n✅ BACKTEST COMPLETED! Results saved to all_tickers_backtest_results.json")
        print(f"📊 Processed {len(all_results)} tickers successfully")
        
    finally:
        ib.disconnect()

if __name__ == "__main__":
    main()
