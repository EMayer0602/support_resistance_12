#!/usr/bin/env python3
"""
Windows-compatible version of complete_comprehensive_backtest.py
Removes all Unicode emojis that cause encoding errors on Windows
"""

import sys
import os
from typing import Dict, List, Tuple, Optional
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import asyncio
from ib_insync import IB, Stock, util

# Add current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from data_sync import download_ticker_data, process_ticker_data
from tickers_config import TICKERS_CONFIG
from backtesting_core import run_full_backtest, berechne_best_p_tw_long, berechne_best_p_tw_short
from signal_utils import assign_long_signals, assign_short_signals, compute_trend
from simulation_utils import simulate_trades_compound_extended, compute_equity_curve
from stats_tools import stats
from config import DEFAULT_COMMISSION_RATE, MIN_COMMISSION, trade_years
COMMISSION_RATE = DEFAULT_COMMISSION_RATE  # Use the config value
from plotly_utils import create_equity_curve_chart
import json

def load_or_download_data(ib: IB, ticker_name: str) -> Optional[pd.DataFrame]:
    """Load data for ticker, downloading if necessary"""
    csv_file = f"{ticker_name}_data.csv"
    
    try:
        if os.path.exists(csv_file):
            df = pd.read_csv(csv_file)
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
            print(f"[DATA] Loaded {len(df)} rows of cached data for {ticker_name}")
            return df
    except Exception as e:
        print(f"[WARN] Failed to load cached data for {ticker_name}: {e}")
    
    # Download fresh data
    try:
        print(f"[DATA] Downloading fresh data for {ticker_name}...")
        stock_data = download_ticker_data(ib, ticker_name, period_years=trade_years)
        if stock_data is not None and not stock_data.empty:
            df = process_ticker_data(stock_data, ticker_name)
            print(f"[DATA] Downloaded {len(df)} rows for {ticker_name}")
            return df
        else:
            print(f"[FAIL] No data received for {ticker_name}")
            return None
    except Exception as e:
        print(f"[FAIL] Download failed for {ticker_name}: {e}")
        return None

def process_single_ticker(ib: IB, ticker_name: str, ticker_config: Dict) -> Optional[Dict]:
    """Process complete backtest for a single ticker"""
    
    # Load data
    df = load_or_download_data(ib, ticker_name)
    if df is None:
        return None
    
    results = {
        'ticker': ticker_name,
        'data_info': {
            'start_date': str(df['date'].min().date()),
            'end_date': str(df['date'].max().date()),
            'rows': len(df)
        }
    }
    
    # Process Long Strategy
    if ticker_config.get('long_strategy', True):
        try:
            print(f"\n[LONG] Processing Long Strategy for {ticker_name}")
            
            print("   [OPT] Optimizing parameters...")
            best_p_long, best_tw_long, best_return_long, all_results_long = berechne_best_p_tw_long(
                df, ticker_name, 
                commission_rate=COMMISSION_RATE,
                min_commission=MIN_COMMISSION,
                capital=ticker_config.get('capital', 10000),
                round_factor=ticker_config.get('round_factor', 0.01),
                save_results=True
            )
            
            # Generate extended signals
            ext_long = assign_long_signals(df, best_p_long, best_tw_long)
            print(f"   [DATA] Generated {len(ext_long)} extended long signals")
            
            # Save extended signals
            ext_long_file = f"extended_long_{ticker_name}.csv"
            ext_long.to_csv(ext_long_file, index=False)
            
            # Run simulation
            cap_long = ticker_config.get('capital', 10000)
            try:
                equity_curve, cap_long, trades_df = simulate_trades_compound_extended(
                    ext_long, cap_long,
                    commission_rate=COMMISSION_RATE,
                    min_commission=MIN_COMMISSION,
                    round_factor=ticker_config.get('round_factor', 0.01)
                )
                
                # Verify equity curve alignment
                curve_final = equity_curve.iloc[-1] if not equity_curve.empty else cap_long
                print(f"   [PROFIT] Final Capital from simulation: {cap_long:.2f}")
                print(f"   [LONG] Final value from equity curve: {curve_final:.2f}")
                
                # Save trades
                trades_file = f"trades_long_{ticker_name}.csv"
                trades_df.to_csv(trades_file, index=False)
                
                results['long'] = {
                    'parameters': {'p': best_p_long, 'tw': best_tw_long},
                    'final_capital': cap_long,
                    'total_return': best_return_long,
                    'trades_count': len(trades_df),
                    'files': {
                        'extended_signals': ext_long_file,
                        'trades': trades_file
                    }
                }
                
            except Exception as e:
                print(f"   [FAIL] Long simulation failed: {e}")
                results['long'] = {'error': str(e)}
                
        except Exception as e:
            print(f"   [FAIL] Long strategy failed: {e}")
            results['long'] = {'error': str(e)}
    
    # Process Short Strategy  
    if ticker_config.get('short_strategy', True):
        try:
            print(f"\n[SHORT] Processing Short Strategy for {ticker_name}")
            
            print("   [OPT] Optimizing parameters...")
            best_p_short, best_tw_short, best_return_short, all_results_short = berechne_best_p_tw_short(
                df, ticker_name,
                commission_rate=COMMISSION_RATE,
                min_commission=MIN_COMMISSION,
                capital=ticker_config.get('capital', 10000),
                round_factor=ticker_config.get('round_factor', 0.01),
                save_results=True
            )
            
            # Generate extended signals
            ext_short = assign_short_signals(df, best_p_short, best_tw_short)
            print(f"   [DATA] Generated {len(ext_short)} extended short signals")
            
            # Save extended signals
            ext_short_file = f"extended_short_{ticker_name}.csv"
            ext_short.to_csv(ext_short_file, index=False)
            
            # Run simulation
            cap_short = ticker_config.get('capital', 10000)
            try:
                equity_curve, cap_short, trades_df = simulate_trades_compound_extended(
                    ext_short, cap_short,
                    commission_rate=COMMISSION_RATE,
                    min_commission=MIN_COMMISSION,
                    round_factor=ticker_config.get('round_factor', 0.01)
                )
                
                curve_final = equity_curve.iloc[-1] if not equity_curve.empty else cap_short
                print(f"   [PROFIT] Final Capital from simulation: {cap_short:.2f}")
                print(f"   [SHORT] Final value from equity curve: {curve_final:.2f}")
                
                # Save trades
                trades_file = f"trades_short_{ticker_name}.csv"
                trades_df.to_csv(trades_file, index=False)
                
                results['short'] = {
                    'parameters': {'p': best_p_short, 'tw': best_tw_short},
                    'final_capital': cap_short,
                    'total_return': best_return_short,
                    'trades_count': len(trades_df),
                    'files': {
                        'extended_signals': ext_short_file,
                        'trades': trades_file
                    }
                }
                
            except Exception as e:
                print(f"   [FAIL] Short simulation failed: {e}")
                results['short'] = {'error': str(e)}
                
        except Exception as e:
            print(f"   [FAIL] Short strategy failed: {e}")
            results['short'] = {'error': str(e)}
    
    # Create equity curve chart
    try:
        chart_file = f"{ticker_name}_chart.html"
        create_equity_curve_chart(
            df, ticker_name, 
            results.get('long', {}).get('parameters', {}),
            results.get('short', {}).get('parameters', {}),
            output_file=chart_file
        )
        print(f"   [DATA] Chart saved to {chart_file}")
        results['chart_file'] = chart_file
    except Exception as e:
        print(f"   [WARN] Chart creation failed: {e}")
    
    return results

def main():
    """Main function that orchestrates the complete comprehensive backtest."""
    print(">> Starting Complete Comprehensive Backtest System")
    print("=" * 60)
    
    # Connect to Interactive Brokers
    ib = IB()
    try:
        ib.connect('127.0.0.1', 7497, clientId=1)  # Paper trading port
        print("[OK] Connected to IB Paper Trading")
    except Exception as e:
        print(f"[WARN] IB connection failed: {e}")
        print("[INFO] Continuing with cached data only...")
        ib = None
    
    try:
        # Step 1: Download data for all tickers
        print(f"\n[DATA] Step 1: Downloading {trade_years} years of data for all tickers...")
        active_tickers = {name: config for name, config in TICKERS_CONFIG.items() 
                         if config.get('trade_on', True)}
        
        print(f"[INFO] Processing {len(active_tickers)} active tickers")
        
        # Step 2: Process each ticker
        print(f"\n[OPT] Step 2: Processing complete backtest for each ticker...")
        all_results = {}
        
        for ticker_name, ticker_config in active_tickers.items():
            try:
                print(f"\n{'='*40}")
                print(f"Processing {ticker_name}")
                print(f"{'='*40}")
                
                result = process_single_ticker(ib, ticker_name, ticker_config)
                if result:
                    all_results[ticker_name] = result
                    print(f"[OK] Completed {ticker_name}")
                else:
                    print(f"[FAIL] Failed to process {ticker_name}")
                    
            except Exception as e:
                print(f"[FAIL] Error processing {ticker_name}: {e}")
                continue
        
        # Step 3: Generate summary
        print("\n" + "="*60)
        print("[DATA] COMPREHENSIVE BACKTEST SUMMARY")
        print("="*60)
        
        for ticker_name, data in all_results.items():
            print(f"\n[OPT] {ticker_name}:")
            print(f"   [DATE] Data: {data['data_info']['start_date']} to {data['data_info']['end_date']} ({data['data_info']['rows']} days)")
            
            if 'long' in data and 'parameters' in data['long']:
                long_data = data['long']
                print(f"   [LONG] Long: p={long_data['parameters']['p']}, tw={long_data['parameters']['tw']}")
                print(f"        Return: {long_data.get('total_return', 0):.2%}")
                print(f"        Final: ${long_data.get('final_capital', 0):,.2f}")
                print(f"        Trades: {long_data.get('trades_count', 0)}")
            
            if 'short' in data and 'parameters' in data['short']:
                short_data = data['short']
                print(f"   [SHORT] Short: p={short_data['parameters']['p']}, tw={short_data['parameters']['tw']}")
                print(f"        Return: {short_data.get('total_return', 0):.2%}")
                print(f"        Final: ${short_data.get('final_capital', 0):,.2f}")
                print(f"        Trades: {short_data.get('trades_count', 0)}")
        
        # Step 4: Save results
        print(f"\n[SAVE] Step 4: Exporting detailed results...")
        
        # Save comprehensive results
        results_file = f"comprehensive_backtest_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, 'w') as f:
            json.dump(all_results, f, indent=2, default=str)
        
        print(f"[SAVE] Results saved to: {results_file}")
        print(f"[OK] Comprehensive backtest completed successfully!")
        print(f"[INFO] Processed {len(all_results)} tickers")
        
        return True
        
    finally:
        if ib:
            ib.disconnect()
            print("[INFO] Disconnected from IB")

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n[INFO] Backtest interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"[FAIL] Backtest failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
