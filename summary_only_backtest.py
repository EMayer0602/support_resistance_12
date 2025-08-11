#!/usr/bin/env python3
"""
Quick Summary-Only Backtest for All Tickers
Shows comprehensive results without detailed output
"""

import sys
import asyncio
from pathlib import Path
import pandas as pd
import json

# Import our modules
from runner import connect_ib, disconnect_ib, download_and_save_data
from signal_utils import assign_long_signals_extended, assign_short_signals_extended, update_level_close_long, update_level_close_short
from simulation_utils import simulate_trades_compound_extended, compute_equity_curve
from tickers_config import tickers
from config import BACKTEST_CONFIG

# Configuration
COMMISSION_RATE = 0.0018
MIN_COMMISSION = 1.0

def optimize_parameters(df, ticker_config, direction="long"):
    """Quick parameter optimization"""
    best_result = {"p": 3, "tw": 1, "final_cap": 1000}
    
    for p in [3, 4, 5, 6, 7]:
        for tw in [1]:
            try:
                if direction == "long":
                    ext_df = assign_long_signals_extended(df, p, tw)
                    ext_df = update_level_close_long(ext_df, df)
                else:
                    ext_df = assign_short_signals_extended(df, p, tw)
                    ext_df = update_level_close_short(ext_df, df)
                
                if ext_df.empty:
                    continue
                
                last_price = df.iloc[-1]['Close']
                last_date = df.index[-1].strftime('%Y-%m-%d')
                
                cap, trades = simulate_trades_compound_extended(
                    ext_df, df, ticker_config,
                    COMMISSION_RATE, MIN_COMMISSION,
                    ticker_config.get("order_round_factor", 1),
                    artificial_close_price=last_price,
                    artificial_close_date=last_date,
                    direction=direction
                )
                
                if cap > best_result["final_cap"]:
                    best_result = {"p": p, "tw": tw, "final_cap": cap}
                    
            except Exception:
                continue
    
    return best_result

def process_ticker_summary(ticker):
    """Process single ticker and return summary"""
    try:
        ticker_config = tickers[ticker]
        
        # Load data
        csv_path = f"{ticker}_data.csv"
        if not Path(csv_path).exists():
            return None
        
        df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
        if df.empty:
            return None
        
        results = {
            "ticker": ticker,
            "trade_on": ticker_config.get("trade_on", "close"),
            "data_range": f"{df.index[0].strftime('%Y-%m-%d')} to {df.index[-1].strftime('%Y-%m-%d')}",
            "data_days": len(df)
        }
        
        # Process Long Strategy if enabled
        if ticker_config.get("long", False):
            best_long = optimize_parameters(df, ticker_config, "long")
            
            # Generate final results with best parameters
            ext_long = assign_long_signals_extended(df, best_long["p"], best_long["tw"])
            ext_long = update_level_close_long(ext_long, df)
            
            last_price = df.iloc[-1]['Close']
            last_date = df.index[-1].strftime('%Y-%m-%d')
            
            cap_long, trades_long = simulate_trades_compound_extended(
                ext_long, df, ticker_config,
                COMMISSION_RATE, MIN_COMMISSION,
                ticker_config.get("order_round_factor", 1),
                artificial_close_price=last_price,
                artificial_close_date=last_date,
                direction="long"
            )
            
            initial_cap_long = ticker_config.get("initialCapitalLong", 1000)
            return_pct_long = ((cap_long - initial_cap_long) / initial_cap_long) * 100
            
            results["long"] = {
                "parameters": f"p={best_long['p']}, tw={best_long['tw']}",
                "extended_signals": len(ext_long),
                "matched_trades": len(trades_long),
                "initial_capital": initial_cap_long,
                "final_capital": cap_long,
                "return_pct": return_pct_long
            }
        
        # Process Short Strategy if enabled
        if ticker_config.get("short", False):
            best_short = optimize_parameters(df, ticker_config, "short")
            
            # Generate final results with best parameters
            ext_short = assign_short_signals_extended(df, best_short["p"], best_short["tw"])
            ext_short = update_level_close_short(ext_short, df)
            
            last_price = df.iloc[-1]['Close']
            last_date = df.index[-1].strftime('%Y-%m-%d')
            
            cap_short, trades_short = simulate_trades_compound_extended(
                ext_short, df, ticker_config,
                COMMISSION_RATE, MIN_COMMISSION,
                ticker_config.get("order_round_factor", 1),
                artificial_close_price=last_price,
                artificial_close_date=last_date,
                direction="short"
            )
            
            initial_cap_short = ticker_config.get("initialCapitalShort", 1000)
            return_pct_short = ((cap_short - initial_cap_short) / initial_cap_short) * 100
            
            results["short"] = {
                "parameters": f"p={best_short['p']}, tw={best_short['tw']}",
                "extended_signals": len(ext_short),
                "matched_trades": len(trades_short),
                "initial_capital": initial_cap_short,
                "final_capital": cap_short,
                "return_pct": return_pct_short
            }
        
        return results
        
    except Exception as e:
        print(f"❌ Error processing {ticker}: {e}")
        return None

def main():
    print("🎯 COMPREHENSIVE BACKTEST SUMMARY FOR ALL TICKERS")
    print("=" * 60)
    
    all_results = []
    
    for ticker in tickers.keys():
        print(f"\n🔄 Processing {ticker}...")
        result = process_ticker_summary(ticker)
        if result:
            all_results.append(result)
            
            # Print summary
            print(f"🎯 {ticker}:")
            print(f"   📅 Data: {result['data_range']} ({result['data_days']} days)")
            print(f"   ⚙️  Trade On: {result['trade_on'].upper()}")
            
            if "long" in result:
                long = result["long"]
                print(f"   📈 Long: {long['parameters']}")
                print(f"       Extended Signals: {long['extended_signals']}")
                print(f"       Matched Trades: {long['matched_trades']}")
                print(f"       Initial Capital: ${long['initial_capital']:.2f}")
                print(f"       Final Capital: ${long['final_capital']:.2f}")
                print(f"       Return: {long['return_pct']:.2f}%")
            
            if "short" in result:
                short = result["short"]
                print(f"   📉 Short: {short['parameters']}")
                print(f"       Extended Signals: {short['extended_signals']}")
                print(f"       Matched Trades: {short['matched_trades']}")
                print(f"       Initial Capital: ${short['initial_capital']:.2f}")
                print(f"       Final Capital: ${short['final_capital']:.2f}")
                print(f"       Return: {short['return_pct']:.2f}%")
    
    # Save results
    with open("all_tickers_summary.json", "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    
    print(f"\n✅ Summary completed for {len(all_results)} tickers!")
    print("💾 Results saved to: all_tickers_summary.json")

if __name__ == "__main__":
    main()
