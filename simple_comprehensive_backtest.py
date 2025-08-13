#!/usr/bin/env python3
"""
Simple Comprehensive Backtest System
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
from backtesting_core import run_full_backtest
from trade_execution import get_backtest_price
from simulation_utils import generate_backtest_date_range
from config import trade_years
from plot_utils import plot_combined_chart_and_equity

def main():
    """
    Main function that orchestrates the comprehensive backtest.
    Uses the same proven data download approach as runner.py fullbacktest.
    """
    print("🚀 Starting Simple Comprehensive Backtest System")
    print("=" * 50)
    
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
        # Step 1: Download 2 years of data using the proven method from runner.py
        print("\n📊 Step 1: Downloading 2 years of data for all tickers...")
        print("Using proven data download from runner.py fullbacktest...")
        
        # Use the proven run_full_backtest to download data
        run_full_backtest(ib)
        print("✅ Data download completed")
        
        # Step 2: Generate backtest trades for a specific date range
        print(f"\n🎯 Step 2: Generating backtest trades...")
        
        # Build recent trade_years dynamic date range
        # Determine min start based on longest available series
        all_dates = []
        for symbol in tickers:
            fn = f"{symbol}_data.csv"
            if os.path.exists(fn):
                try:
                    df_tmp = pd.read_csv(fn, parse_dates=[0])
                    df_tmp.set_index(df_tmp.columns[0], inplace=True)
                    all_dates.extend(df_tmp.index.tolist())
                except Exception:
                    pass
        if not all_dates:
            print("❌ No price data available after download step.")
            return
        max_date = max(all_dates)
        min_allowed = max_date - pd.Timedelta(days=int(trade_years * 365)) if trade_years else min(all_dates)
        start_date = min_allowed.strftime('%Y-%m-%d')
        end_date = max_date.strftime('%Y-%m-%d')
        print(f"Date range (trade_years subset): {start_date} to {end_date}")
        
        max_missing_days = 1
        missing_days = {symbol: 0 for symbol in tickers}
        skip_tickers = set()
        backtest_trades = {}
        
        # Generate trades for each day in the backtest range
        for date_str in generate_backtest_date_range(start_date, end_date):
            trades = []
            portfolio = {s: 0 for s in tickers}
            
            for symbol, cfg in tickers.items():
                if symbol in skip_tickers:
                    continue
                    
                # Skip if this ticker doesn't support any trading direction
                if not any([cfg.get("long", False), cfg.get("short", False), 
                           cfg.get("buy", False), cfg.get("sell", False), cfg.get("cover", False)]):
                    continue
                
                field = cfg.get("trade_on", "Close").capitalize()
                price = get_backtest_price(symbol, date_str, field)
                
                if price is None:
                    missing_days[symbol] += 1
                    if missing_days[symbol] >= max_missing_days:
                        print(f"⚠️ Skipping {symbol}: {missing_days[symbol]} consecutive days without data")
                        skip_tickers.add(symbol)
                    continue
                else:
                    missing_days[symbol] = 0
                
                # Generate trades based on ticker configuration
                for side in ("BUY", "SHORT", "SELL", "COVER"):
                    side_key = side.lower()
                    
                    # Check if this side is enabled for this ticker
                    if not cfg.get(side_key, False):
                        continue
                    
                    if side in ("SELL", "COVER"):
                        qty = abs(portfolio.get(symbol, 0))
                        if qty == 0:
                            continue
                    else:
                        # Simple position sizing - can be enhanced later
                        qty = 100  # Fixed size for now
                        if qty <= 0:
                            continue
                    
                    trades.append({
                        "symbol": symbol,
                        "side": side,
                        "qty": qty,
                        "price": round(price, 2)
                    })
                    
                    # Update portfolio
                    delta = qty if side in ("BUY", "COVER") else -qty
                    portfolio[symbol] += delta
            
            backtest_trades[date_str] = trades
            
            if trades:
                print(f"📅 {date_str}: {len(trades)} trades generated")
            
        # Step 3: Export results
        print(f"\n💾 Step 3: Exporting results...")
        
        # Save trades by day
        with open("simple_comprehensive_backtest_trades.json", "w") as f:
            json.dump(backtest_trades, f, indent=2)
        
        # Generate summary statistics
        total_trades = sum(len(trades) for trades in backtest_trades.values())
        active_days = len([trades for trades in backtest_trades.values() if trades])
        
        print(f"\n📊 Backtest Summary:")
        print(f"   • Total trading days: {len(backtest_trades)}")
        print(f"   • Days with trades: {active_days}")
        print(f"   • Total trades generated: {total_trades}")
        print(f"   • Results saved to: simple_comprehensive_backtest_trades.json")
        
        # Step 4: Analyze ticker performance
        ticker_stats = {}
        for symbol in tickers:
            if symbol in skip_tickers:
                continue
                
            symbol_trades = []
            for trades in backtest_trades.values():
                symbol_trades.extend([t for t in trades if t["symbol"] == symbol])
            
            if symbol_trades:
                ticker_stats[symbol] = {
                    "total_trades": len(symbol_trades),
                    "buy_trades": len([t for t in symbol_trades if t["side"] == "BUY"]),
                    "sell_trades": len([t for t in symbol_trades if t["side"] == "SELL"]),
                    "short_trades": len([t for t in symbol_trades if t["side"] == "SHORT"]),
                    "cover_trades": len([t for t in symbol_trades if t["side"] == "COVER"]),
                }
        
        print(f"\n📈 Ticker Performance:")
        print(f"{'Ticker':<8} {'Total':<8} {'Buy':<6} {'Sell':<6} {'Short':<6} {'Cover':<6}")
        print("-" * 50)
        for symbol, stats in ticker_stats.items():
            print(f"{symbol:<8} {stats['total_trades']:<8} {stats['buy_trades']:<6} "
                  f"{stats['sell_trades']:<6} {stats['short_trades']:<6} {stats['cover_trades']:<6}")
        
        print(f"\n✅ Simple comprehensive backtest completed successfully!")
        
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
