#!/usr/bin/env python3
"""
Configuration Validation Script
Tests that all parameters from config.py and tickers_config.py are properly loaded and used

Usage: python test_config.py
"""

import sys
from datetime import datetime, time
from config import *
from tickers_config import tickers
from portfolio_manager import PortfolioManager, TICKERS_CONFIG

def test_config_loading():
    """Test that all config parameters are loaded correctly"""
    print("🔧 CONFIGURATION VALIDATION TEST")
    print("="*50)
    
    print(f"\n💰 CAPITAL SETTINGS:")
    print(f"   INITIAL_CAPITAL: ${INITIAL_CAPITAL:,.2f}")
    print(f"   DEFAULT_COMMISSION_RATE: {DEFAULT_COMMISSION_RATE*100:.3f}%")
    print(f"   MIN_COMMISSION: ${MIN_COMMISSION:.2f}")
    print(f"   ORDER_SIZE: {ORDER_SIZE}")
    print(f"   ORDER_ROUND_FACTOR: {ORDER_ROUND_FACTOR}")
    
    print(f"\n📅 TIME SETTINGS:")
    print(f"   trade_years: {trade_years}")
    print(f"   backtesting_begin: {backtesting_begin}%")
    print(f"   backtesting_end: {backtesting_end}%")
    
    print(f"\n📈 SIGNAL PARAMETERS:")
    print(f"   P_RANGE: {P_RANGE}")
    print(f"   TW_RANGE: {TW_RANGE}")
    
    print(f"\n🎯 TRADING EXECUTION:")
    print(f"   LIMIT_ORDER_OFFSET: ${LIMIT_ORDER_OFFSET:.2f}")
    print(f"   MAX_POSITION_SIZE: {MAX_POSITION_SIZE*100:.1f}%")
    print(f"   STOP_LOSS_PCT: {STOP_LOSS_PCT*100:.1f}%")
    print(f"   TAKE_PROFIT_PCT: {TAKE_PROFIT_PCT*100:.1f}%")
    
    print(f"\n⏰ TRADING TIMING:")
    print(f"   MARKET_OPEN_TIME: {MARKET_OPEN_TIME}")
    print(f"   MARKET_CLOSE_TIME: {MARKET_CLOSE_TIME}")
    print(f"   OPEN_TRADE_DELAY: {OPEN_TRADE_DELAY} minutes")
    print(f"   CLOSE_TRADE_ADVANCE: {CLOSE_TRADE_ADVANCE} minutes")
    
    # Calculate actual trading times
    market_open = datetime.strptime(MARKET_OPEN_TIME, "%H:%M").time()
    market_close = datetime.strptime(MARKET_CLOSE_TIME, "%H:%M").time()
    open_start_minutes = market_open.hour * 60 + market_open.minute + OPEN_TRADE_DELAY
    open_trade_time = time(open_start_minutes // 60, open_start_minutes % 60)
    close_start_minutes = market_close.hour * 60 + market_close.minute - CLOSE_TRADE_ADVANCE
    close_trade_time = time(close_start_minutes // 60, close_start_minutes % 60)
    
    print(f"   ➡️  Calculated OPEN trading time: {open_trade_time.strftime('%H:%M')}")
    print(f"   ➡️  Calculated CLOSE trading time: {close_trade_time.strftime('%H:%M')}")
    
    print(f"\n📊 IB CONNECTION:")
    print(f"   IB_PAPER_PORT: {IB_PAPER_PORT}")
    print(f"   IB_LIVE_PORT: {IB_LIVE_PORT}")
    print(f"   IB_HOST: {IB_HOST}")
    print(f"   IB_CLIENT_ID: {IB_CLIENT_ID}")
    
    print(f"\n🔧 PERFORMANCE:")
    print(f"   MAX_WORKERS: {MAX_WORKERS}")
    print(f"   CACHE_RESULTS: {CACHE_RESULTS}")
    print(f"   VERBOSE_LOGGING: {VERBOSE_LOGGING}")
    
    print(f"\n📁 FILE PATHS:")
    print(f"   RESULTS_DIR: {RESULTS_DIR}")
    print(f"   CHARTS_DIR: {CHARTS_DIR}")
    print(f"   DATA_DIR: {DATA_DIR}")
    print(f"   PORTFOLIO_FILE: {PORTFOLIO_FILE}")

def test_ticker_config():
    """Test ticker-specific configuration"""
    print(f"\n📊 TICKER CONFIGURATION:")
    print("="*50)
    
    total_long_capital = 0
    total_short_capital = 0
    
    for symbol, config in tickers.items():
        print(f"\n🎯 {symbol}:")
        print(f"   conID: {config.get('conID', 'N/A')}")
        print(f"   Long enabled: {config.get('long', False)}")
        print(f"   Short enabled: {config.get('short', False)}")
        print(f"   Long capital: ${config.get('initialCapitalLong', 0):,.2f}")
        print(f"   Short capital: ${config.get('initialCapitalShort', 0):,.2f}")
        print(f"   Trade on: {config.get('trade_on', 'open').upper()}")
        print(f"   Round factor: {config.get('order_round_factor', 1)}")
        
        # Calculate totals
        total_long_capital += config.get('initialCapitalLong', 0)
        total_short_capital += config.get('initialCapitalShort', 0)
    
    print(f"\n📈 CAPITAL SUMMARY:")
    print(f"   Total tickers: {len(tickers)}")
    print(f"   Total long capital: ${total_long_capital:,.2f}")
    print(f"   Total short capital: ${total_short_capital:,.2f}")
    print(f"   Combined capital: ${total_long_capital + total_short_capital:,.2f}")
    print(f"   Config INITIAL_CAPITAL: ${INITIAL_CAPITAL:,.2f}")
    
    if total_long_capital + total_short_capital != INITIAL_CAPITAL:
        print(f"   ⚠️  Warning: Combined ticker capital doesn't match INITIAL_CAPITAL")
    else:
        print(f"   ✅ Capital allocation matches INITIAL_CAPITAL")

def test_converted_config():
    """Test the converted ticker configuration used by trading scripts"""
    print(f"\n🔄 CONVERTED TICKER CONFIG:")
    print("="*50)
    
    pm = PortfolioManager()
    
    for symbol, config in TICKERS_CONFIG.items():
        print(f"\n📊 {symbol}:")
        print(f"   Strategies: {config['strategies']}")
        print(f"   Trade on: {config['trade_on']}")
        print(f"   Long capital: ${config['initialCapitalLong']:,.2f}")
        print(f"   Short capital: ${config['initialCapitalShort']:,.2f}")
        print(f"   ConID: {config['conID']}")
        print(f"   Round factor: {config['order_round_factor']}")
        
        # Test portfolio manager capital allocation
        capital_info = pm.capital_allocation.get(symbol, {})
        print(f"   PM Long capital: ${capital_info.get('long', 0):,.2f}")
        print(f"   PM Short capital: ${capital_info.get('short', 0):,.2f}")
        print(f"   PM Round factor: {capital_info.get('round_factor', 'N/A')}")

def test_sample_calculations():
    """Test sample share calculations using config parameters"""
    print(f"\n🧮 SAMPLE CALCULATIONS:")
    print("="*50)
    
    pm = PortfolioManager()
    
    # Test with sample prices
    test_prices = {'AAPL': 150.0, 'GOOGL': 100.0, 'NVDA': 400.0, 'AMD': 80.0}
    
    for ticker, price in test_prices.items():
        if ticker in TICKERS_CONFIG:
            print(f"\n📊 {ticker} @ ${price:.2f}:")
            
            # Test long calculation
            long_shares = pm.calculate_shares(ticker, 'LONG', 'BUY', price)
            long_capital = pm.get_capital_for_strategy(ticker, 'LONG')
            print(f"   Long BUY: {long_shares} shares (${long_capital:,.2f} capital)")
            
            # Test short calculation
            if 'SHORT' in TICKERS_CONFIG[ticker]['strategies']:
                short_shares = pm.calculate_shares(ticker, 'SHORT', 'SHORT', price)
                short_capital = pm.get_capital_for_strategy(ticker, 'SHORT')
                print(f"   Short SELL: {short_shares} shares (${short_capital:,.2f} capital)")
            
            # Test commission calculation
            commission = max(MIN_COMMISSION, long_shares * price * DEFAULT_COMMISSION_RATE)
            print(f"   Est. commission: ${commission:.2f}")

def main():
    """Main test function"""
    try:
        test_config_loading()
        test_ticker_config()
        test_converted_config()
        test_sample_calculations()
        
        print(f"\n✅ CONFIGURATION VALIDATION COMPLETE")
        print(f"="*50)
        print(f"All parameters from config.py and tickers_config.py are loaded and accessible.")
        
    except Exception as e:
        print(f"\n❌ Configuration validation failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
