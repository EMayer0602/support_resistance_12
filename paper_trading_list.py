#!/usr/bin/env python3
"""
Paper Trading Trade List Generator
Creates a filtered trade list for a specific date range with ticker symbols
Perfect for paper trading preparation and execution
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

def parse_date_range(start_date_str, end_date_str):
    """Parse date range strings into datetime objects"""
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        return start_date, end_date
    except ValueError:
        print("❌ Invalid date format. Use YYYY-MM-DD format.")
        return None, None

def extract_trades_for_paper_trading(data, start_date, end_date, strategy_filter=None, min_pnl=None):
    """Extract trades for paper trading with ticker information"""
    
    paper_trades = []
    
    for ticker, ticker_data in data.items():
        # Get ticker config
        ticker_config = tickers.get(ticker, {})
        trade_on = ticker_config.get('trade_on', 'close')
        
        strategies = ['long', 'short']
        if strategy_filter:
            strategies = [strategy_filter]
        
        for strategy in strategies:
            if strategy not in ticker_data or not isinstance(ticker_data[strategy], dict):
                continue
            
            strategy_data = ticker_data[strategy]
            trades = strategy_data.get('trades', [])
            
            if not trades:
                continue
            
            # Get strategy parameters
            params = strategy_data.get('parameters', {})
            p_param = params.get('p', 'N/A')
            tw_param = params.get('tw', 'N/A')
            
            for trade in trades:
                # Handle different trade formats (long vs short)
                if 'buy_date' in trade:
                    # Long trades
                    entry_date = datetime.strptime(trade['buy_date'], '%Y-%m-%d %H:%M:%S')
                    exit_date = datetime.strptime(trade['sell_date'], '%Y-%m-%d %H:%M:%S')
                    entry_price = trade['buy_price']
                    exit_price = trade['sell_price']
                    entry_action = 'BUY'
                    exit_action = 'SELL'
                else:
                    # Short trades
                    entry_date = datetime.strptime(trade['short_date'], '%Y-%m-%d %H:%M:%S')
                    exit_date = datetime.strptime(trade['cover_date'], '%Y-%m-%d %H:%M:%S')
                    entry_price = trade['short_price']
                    exit_price = trade['cover_price']
                    entry_action = 'SHORT'
                    exit_action = 'COVER'
                
                # Apply date filter
                if not (start_date <= entry_date <= end_date):
                    continue
                
                # Apply PnL filter
                if min_pnl is not None and trade['pnl'] < min_pnl:
                    continue
                
                hold_days = (exit_date - entry_date).days
                
                # Create paper trading record
                paper_trade = {
                    'ticker': ticker,
                    'strategy': strategy.upper(),
                    'entry_date': entry_date.strftime('%Y-%m-%d'),
                    'exit_date': exit_date.strftime('%Y-%m-%d'),
                    'entry_action': entry_action,
                    'exit_action': exit_action,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'shares': trade['shares'],
                    'fee': trade['fee'],
                    'pnl': trade['pnl'],
                    'hold_days': hold_days,
                    'trade_on': trade_on.upper(),
                    'p_param': p_param,
                    'tw_param': tw_param,
                    'return_pct': ((exit_price - entry_price) / entry_price * 100) if strategy == 'long' else ((entry_price - exit_price) / entry_price * 100)
                }
                
                paper_trades.append(paper_trade)
    
    return paper_trades

def print_paper_trading_list(trades, start_date_str, end_date_str):
    """Print formatted trade list for paper trading"""
    
    if not trades:
        print(f"❌ No trades found for the period {start_date_str} to {end_date_str}")
        return
    
    print(f"\n📋 PAPER TRADING TRADE LIST")
    print(f"📅 Period: {start_date_str} to {end_date_str}")
    print(f"🎯 Total Trades: {len(trades)}")
    print("="*120)
    
    # Sort trades by entry date
    trades_sorted = sorted(trades, key=lambda x: x['entry_date'])
    
    # Print header
    print(f"{'#':<3} {'Ticker':<6} {'Strategy':<8} {'Entry Date':<12} {'Exit Date':<12} {'Action':<6} "
          f"{'Entry $':<8} {'Exit $':<8} {'Shares':<6} {'PnL $':<9} {'Return%':<8} {'Days':<4} {'On':<5}")
    print("-" * 120)
    
    total_pnl = 0
    winning_trades = 0
    
    for i, trade in enumerate(trades_sorted, 1):
        pnl_color = "🟢" if trade['pnl'] > 0 else "🔴"
        if trade['pnl'] > 0:
            winning_trades += 1
        total_pnl += trade['pnl']
        
        print(f"{i:<3} {trade['ticker']:<6} {trade['strategy']:<8} {trade['entry_date']:<12} "
              f"{trade['exit_date']:<12} {trade['entry_action']:<6} {trade['entry_price']:<8.2f} "
              f"{trade['exit_price']:<8.2f} {trade['shares']:<6} {pnl_color}{trade['pnl']:<8.2f} "
              f"{trade['return_pct']:<7.1f}% {trade['hold_days']:<4} {trade['trade_on']:<5}")
    
    # Print summary
    print("-" * 120)
    win_rate = (winning_trades / len(trades_sorted) * 100) if trades_sorted else 0
    avg_pnl = total_pnl / len(trades_sorted) if trades_sorted else 0
    
    print(f"📊 SUMMARY:")
    print(f"   ✅ Winning Trades: {winning_trades}/{len(trades_sorted)} ({win_rate:.1f}%)")
    print(f"   💰 Total PnL: ${total_pnl:.2f}")
    print(f"   📈 Average PnL: ${avg_pnl:.2f}")
    print(f"   🏆 Best Trade: ${max(trade['pnl'] for trade in trades_sorted):.2f}")
    if len(trades_sorted) > 0:
        print(f"   📉 Worst Trade: ${min(trade['pnl'] for trade in trades_sorted):.2f}")
    
    # Show ticker breakdown
    ticker_summary = {}
    for trade in trades_sorted:
        ticker = trade['ticker']
        if ticker not in ticker_summary:
            ticker_summary[ticker] = {'count': 0, 'pnl': 0}
        ticker_summary[ticker]['count'] += 1
        ticker_summary[ticker]['pnl'] += trade['pnl']
    
    print(f"\n🎯 TICKER BREAKDOWN:")
    for ticker, stats in sorted(ticker_summary.items()):
        print(f"   {ticker}: {stats['count']} trades, ${stats['pnl']:.2f} PnL")

def save_to_csv(trades, filename):
    """Save trades to CSV for paper trading platforms"""
    if not trades:
        print("❌ No trades to save")
        return
    
    df = pd.DataFrame(trades)
    df.to_csv(filename, index=False)
    print(f"✅ Trades saved to {filename}")

def main():
    """Main function with interactive date range input"""
    print("🚀 PAPER TRADING TRADE LIST GENERATOR")
    print("="*60)
    
    # Load data
    data = load_trade_data()
    if not data:
        return
    
    print(f"📊 Loaded data for {len(data)} tickers")
    
    # Get date range from user
    print("\n📅 Enter date range for trade list:")
    start_date_str = input("Start date (YYYY-MM-DD): ").strip()
    end_date_str = input("End date (YYYY-MM-DD): ").strip()
    
    start_date, end_date = parse_date_range(start_date_str, end_date_str)
    if not start_date or not end_date:
        return
    
    # Optional filters
    print("\n🔍 Optional filters:")
    strategy_filter = input("Strategy (long/short/all) [all]: ").strip().lower()
    if strategy_filter not in ['long', 'short']:
        strategy_filter = None
    
    min_pnl_input = input("Minimum PnL (leave empty for no filter): ").strip()
    min_pnl = None
    if min_pnl_input:
        try:
            min_pnl = float(min_pnl_input)
        except ValueError:
            print("Invalid PnL filter, ignoring...")
    
    # Extract trades
    paper_trades = extract_trades_for_paper_trading(
        data, start_date, end_date, strategy_filter, min_pnl
    )
    
    # Display results
    print_paper_trading_list(paper_trades, start_date_str, end_date_str)
    
    # Option to save to CSV
    if paper_trades:
        save_csv = input("\n💾 Save to CSV? (y/n) [n]: ").strip().lower()
        if save_csv in ['y', 'yes']:
            filename = f"paper_trading_trades_{start_date_str}_to_{end_date_str}.csv"
            save_to_csv(paper_trades, filename)

if __name__ == "__main__":
    main()
