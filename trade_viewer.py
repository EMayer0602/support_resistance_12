#!/usr/bin/env python3
"""
Trade List Viewer with Date Range Filtering
Shows detailed trade information for specified date ranges and tickers
"""

import json
import pandas as pd
from datetime import datetime, timedelta
from tickers_config import tickers

def load_trade_data():
    """Load trade data from the comprehensive backtest results"""
    try:
        with open('complete_comprehensive_backtest_results.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("❌ Results file not found. Please run the comprehensive backtest first.")
        return None

def parse_date(date_str):
    """Parse date string to datetime object"""
    if isinstance(date_str, str):
        # Handle both formats: "2023-08-18 00:00:00" and "2023-08-18"
        if " " in date_str:
            return datetime.strptime(date_str.split()[0], "%Y-%m-%d")
        else:
            return datetime.strptime(date_str, "%Y-%m-%d")
    return date_str

def filter_trades_by_date_range(trades, start_date, end_date, date_field='buy_date'):
    """Filter trades by date range"""
    start_dt = parse_date(start_date)
    end_dt = parse_date(end_date)
    
    filtered_trades = []
    for trade in trades:
        trade_date = parse_date(trade[date_field])
        if start_dt <= trade_date <= end_dt:
            filtered_trades.append(trade)
    
    return filtered_trades

def display_trades(ticker, strategy_type, trades, start_date=None, end_date=None):
    """Display trades in a formatted table"""
    if not trades:
        print(f"No {strategy_type} trades found for {ticker}")
        if start_date and end_date:
            print(f"   Date range: {start_date} to {end_date}")
        return
    
    print(f"\n🎯 {ticker} - {strategy_type.upper()} TRADES")
    if start_date and end_date:
        print(f"📅 Date Range: {start_date} to {end_date}")
    print("-" * 90)
    
    # Headers
    if strategy_type == 'long':
        print(f"{'Buy Date':<12} {'Sell Date':<12} {'Buy Price':<10} {'Sell Price':<10} {'Shares':<8} {'Fee':<8} {'P&L':<12}")
    else:  # short
        print(f"{'Short Date':<12} {'Cover Date':<12} {'Short Price':<10} {'Cover Price':<10} {'Shares':<8} {'Fee':<8} {'P&L':<12}")
    
    print("-" * 90)
    
    total_pnl = 0
    total_fees = 0
    winning_trades = 0
    losing_trades = 0
    
    for trade in trades:
        if strategy_type == 'long':
            buy_date = trade['buy_date'].split()[0] if ' ' in trade['buy_date'] else trade['buy_date']
            sell_date = trade['sell_date'].split()[0] if ' ' in trade['sell_date'] else trade['sell_date']
            print(f"{buy_date:<12} {sell_date:<12} {trade['buy_price']:<10.2f} {trade['sell_price']:<10.2f} "
                  f"{trade['shares']:<8} {trade['fee']:<8.2f} {trade['pnl']:<12.2f}")
        else:  # short
            short_date = trade['short_date'].split()[0] if ' ' in trade['short_date'] else trade['short_date']
            cover_date = trade['cover_date'].split()[0] if ' ' in trade['cover_date'] else trade['cover_date']
            print(f"{short_date:<12} {cover_date:<12} {trade['short_price']:<10.2f} {trade['cover_price']:<10.2f} "
                  f"{trade['shares']:<8} {trade['fee']:<8.2f} {trade['pnl']:<12.2f}")
        
        total_pnl += trade['pnl']
        total_fees += trade['fee']
        if trade['pnl'] > 0:
            winning_trades += 1
        else:
            losing_trades += 1
    
    # Summary
    print("-" * 90)
    print(f"📊 SUMMARY: {len(trades)} trades")
    print(f"   Total P&L: ${total_pnl:.2f}")
    print(f"   Total Fees: ${total_fees:.2f}")
    print(f"   Net P&L: ${total_pnl:.2f}")  # P&L already includes fees in your system
    print(f"   Winning Trades: {winning_trades} ({winning_trades/len(trades)*100:.1f}%)")
    print(f"   Losing Trades: {losing_trades} ({losing_trades/len(trades)*100:.1f}%)")
    if len(trades) > 0:
        print(f"   Average P&L per Trade: ${total_pnl/len(trades):.2f}")

def show_trade_list(tickers_to_show=None, start_date=None, end_date=None, strategy_types=None):
    """
    Show trade lists with optional filtering
    
    Parameters:
    - tickers_to_show: list of ticker symbols (e.g., ['AAPL', 'GOOGL']) or None for all
    - start_date: string in format 'YYYY-MM-DD' or None
    - end_date: string in format 'YYYY-MM-DD' or None  
    - strategy_types: list of strategy types ['long', 'short'] or None for both
    """
    
    data = load_trade_data()
    if not data:
        return
    
    # Default parameters
    if tickers_to_show is None:
        tickers_to_show = list(data.keys())
    if strategy_types is None:
        strategy_types = ['long', 'short']
    
    print(f"🚀 TRADE LIST VIEWER")
    print("=" * 70)
    
    if start_date and end_date:
        print(f"📅 Date Filter: {start_date} to {end_date}")
    else:
        print("📅 Date Filter: All dates")
    
    print(f"🎯 Tickers: {', '.join(tickers_to_show)}")
    print(f"📈 Strategies: {', '.join(strategy_types)}")
    print("=" * 70)
    
    for ticker in tickers_to_show:
        if ticker not in data:
            print(f"\n❌ No data found for {ticker}")
            continue
        
        ticker_data = data[ticker]
        
        for strategy_type in strategy_types:
            if strategy_type not in ticker_data:
                continue
            
            strategy_data = ticker_data[strategy_type]
            if 'trades' not in strategy_data:
                continue
            
            trades = strategy_data['trades']
            
            # Filter by date range if specified
            if start_date and end_date:
                if strategy_type == 'long':
                    filtered_trades = filter_trades_by_date_range(trades, start_date, end_date, 'buy_date')
                else:
                    filtered_trades = filter_trades_by_date_range(trades, start_date, end_date, 'short_date')
            else:
                filtered_trades = trades
            
            display_trades(ticker, strategy_type, filtered_trades, start_date, end_date)

def main():
    """Main function with example usage"""
    print("🎯 TRADE LIST VIEWER - EXAMPLES")
    print("=" * 50)
    
    # Example 1: All trades for AAPL
    print("\n1️⃣ Example: All AAPL trades")
    show_trade_list(tickers_to_show=['AAPL'])
    
    # Example 2: All trades for specific date range
    print("\n2️⃣ Example: All trades from 2024-01-01 to 2024-06-30")
    show_trade_list(start_date='2024-01-01', end_date='2024-06-30')
    
    # Example 3: Specific tickers and date range
    print("\n3️⃣ Example: GOOGL and AMD long trades from 2024-01-01 to 2024-12-31")
    show_trade_list(
        tickers_to_show=['GOOGL', 'AMD'], 
        start_date='2024-01-01', 
        end_date='2024-12-31',
        strategy_types=['long']
    )

def interactive_mode():
    """Interactive mode for custom filtering"""
    print("🎮 INTERACTIVE TRADE VIEWER")
    print("=" * 40)
    
    # Get available tickers
    data = load_trade_data()
    if not data:
        return
    
    available_tickers = list(data.keys())
    print(f"Available tickers: {', '.join(available_tickers)}")
    
    # Get user input
    ticker_input = input("\nEnter tickers (comma-separated) or press Enter for all: ").strip()
    if ticker_input:
        selected_tickers = [t.strip().upper() for t in ticker_input.split(',')]
    else:
        selected_tickers = None
    
    strategy_input = input("Enter strategy types (long,short) or press Enter for both: ").strip()
    if strategy_input:
        selected_strategies = [s.strip().lower() for s in strategy_input.split(',')]
    else:
        selected_strategies = None
    
    start_date = input("Enter start date (YYYY-MM-DD) or press Enter for all: ").strip()
    if not start_date:
        start_date = None
    
    end_date = input("Enter end date (YYYY-MM-DD) or press Enter for all: ").strip()
    if not end_date:
        end_date = None
    
    # Show results
    print("\n" + "="*70)
    show_trade_list(
        tickers_to_show=selected_tickers,
        start_date=start_date,
        end_date=end_date,
        strategy_types=selected_strategies
    )

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--interactive':
        interactive_mode()
    else:
        # Show examples or run with command line arguments
        if len(sys.argv) == 1:
            main()
        else:
            # Command line usage: python trade_viewer.py TICKER1,TICKER2 START_DATE END_DATE STRATEGY_TYPE
            tickers_arg = sys.argv[1].split(',') if sys.argv[1] else None
            start_date_arg = sys.argv[2] if len(sys.argv) > 2 else None
            end_date_arg = sys.argv[3] if len(sys.argv) > 3 else None
            strategy_arg = sys.argv[4].split(',') if len(sys.argv) > 4 else None
            
            show_trade_list(
                tickers_to_show=tickers_arg,
                start_date=start_date_arg,
                end_date=end_date_arg,
                strategy_types=strategy_arg
            )
