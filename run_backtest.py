#!/usr/bin/env python3
"""
Simple runner for the comprehensive backtest system
"""
from comprehensive_backtest import run_comprehensive_backtest

if __name__ == "__main__":
    print("🎯 Starting Comprehensive Backtest Runner")
    print("This will:")
    print("1. Load 2 years of data from Lynx/IB for all tickers")
    print("2. Create df_bt subset (25%-95% of data)")
    print("3. Optimize p and tw parameters")
    print("4. Generate extended trades, matched trades, and equity curves")
    print("5. Create charts and statistics")
    print()
    
    input("Press Enter to continue or Ctrl+C to cancel...")
    
    try:
        results = run_comprehensive_backtest()
        
        if results:
            print("\n📊 SUMMARY")
            print("=" * 50)
            for symbol, data in results.items():
                best = data["best_params"]
                print(f"{symbol:6s}: p={best['p']:2d}, tw={best['tw']:2d}, return={best['return']:.4f}")
                
        print("\n✅ Backtest completed successfully!")
        
    except KeyboardInterrupt:
        print("\n⚠️ Backtest cancelled by user")
    except Exception as e:
        print(f"\n❌ Backtest failed: {e}")
        raise
