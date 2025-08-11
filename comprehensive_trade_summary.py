#!/usr/bin/env python3
"""
Comprehensive Trade Summary for All Tickers
Shows detailed trade information for both long and short positions
"""

import json
import pandas as pd
from datetime import datetime
from tickers_config import tickers

def load_trade_data():
    """Load trade data from the comprehensive backtest results"""
    try:
        with open('complete_comprehensive_backtest_results.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("❌ Results file not found. Please run the comprehensive backtest first.")
        return None

def format_currency(value):
    """Format currency values"""
    return f"${value:,.2f}"

def format_percentage(value):
    """Format percentage values"""
    return f"{value:+.2f}%"

def analyze_trades(trades, strategy_type, ticker):
    """Analyze trade performance"""
    if not trades:
        return {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0,
            'total_pnl': 0,
            'avg_pnl': 0,
            'max_profit': 0,
            'max_loss': 0,
            'avg_hold_days': 0
        }
    
    winning_trades = [t for t in trades if t['pnl'] > 0]
    losing_trades = [t for t in trades if t['pnl'] < 0]
    
    # Calculate holding periods
    hold_days = []
    for trade in trades:
        # Handle different trade formats (long vs short)
        if 'buy_date' in trade:
            # Long trades
            buy_date = datetime.strptime(trade['buy_date'], '%Y-%m-%d %H:%M:%S')
            sell_date = datetime.strptime(trade['sell_date'], '%Y-%m-%d %H:%M:%S')
        else:
            # Short trades
            buy_date = datetime.strptime(trade['short_date'], '%Y-%m-%d %H:%M:%S')
            sell_date = datetime.strptime(trade['cover_date'], '%Y-%m-%d %H:%M:%S')
        days = (sell_date - buy_date).days
        hold_days.append(days)
    
    return {
        'total_trades': len(trades),
        'winning_trades': len(winning_trades),
        'losing_trades': len(losing_trades),
        'win_rate': (len(winning_trades) / len(trades) * 100) if trades else 0,
        'total_pnl': sum(t['pnl'] for t in trades),
        'avg_pnl': sum(t['pnl'] for t in trades) / len(trades),
        'max_profit': max(t['pnl'] for t in trades),
        'max_loss': min(t['pnl'] for t in trades),
        'avg_hold_days': sum(hold_days) / len(hold_days) if hold_days else 0
    }

def print_ticker_trades(ticker, data, date_filter=None, min_pnl=None, strategy_filter=None):
    """Print detailed trades for a ticker"""
    print(f"\n{'='*80}")
    print(f"🎯 {ticker} - DETAILED TRADE ANALYSIS")
    print(f"{'='*80}")
    
    # Data info
    data_info = data.get('data_info', {})
    print(f"📅 Data Period: {data_info.get('start_date', 'N/A')} to {data_info.get('end_date', 'N/A')}")
    print(f"📊 Total Days: {data_info.get('rows', 0)}")
    
    # Get trade_on setting
    trade_on = tickers.get(ticker, {}).get('trade_on', 'close')
    print(f"📈 Trade Execution: {trade_on.upper()}")
    
    strategies = ['long', 'short']
    total_trades_shown = 0
    
    for strategy in strategies:
        if strategy_filter and strategy != strategy_filter:
            continue
            
        if strategy not in data or not isinstance(data[strategy], dict):
            continue
            
        strategy_data = data[strategy]
        trades = strategy_data.get('trades', [])
        
        if not trades:
            print(f"\n🔴 No {strategy.upper()} trades found")
            continue
        
        # Filter trades if needed
        filtered_trades = []
        for trade in trades:
            # Date filter - handle different trade formats
            if date_filter:
                if 'buy_date' in trade:
                    trade_date = datetime.strptime(trade['buy_date'], '%Y-%m-%d %H:%M:%S')
                else:
                    trade_date = datetime.strptime(trade['short_date'], '%Y-%m-%d %H:%M:%S')
                if not (date_filter['start'] <= trade_date <= date_filter['end']):
                    continue
            
            # PnL filter
            if min_pnl is not None and trade['pnl'] < min_pnl:
                continue
                
            filtered_trades.append(trade)
        
        if not filtered_trades:
            print(f"\n🔴 No {strategy.upper()} trades match the filters")
            continue
        
        # Analyze trades
        analysis = analyze_trades(filtered_trades, strategy, ticker)
        
        print(f"\n🟢 {strategy.upper()} STRATEGY SUMMARY:")
        print(f"   Parameters: p={strategy_data.get('parameters', {}).get('p', 'N/A')}, tw={strategy_data.get('parameters', {}).get('tw', 'N/A')}")
        print(f"   📊 Total Trades: {analysis['total_trades']}")
        print(f"   ✅ Winning Trades: {analysis['winning_trades']} ({analysis['win_rate']:.1f}%)")
        print(f"   ❌ Losing Trades: {analysis['losing_trades']} ({100-analysis['win_rate']:.1f}%)")
        print(f"   💰 Total PnL: {format_currency(analysis['total_pnl'])}")
        print(f"   📈 Average PnL: {format_currency(analysis['avg_pnl'])}")
        print(f"   🏆 Best Trade: {format_currency(analysis['max_profit'])}")
        print(f"   📉 Worst Trade: {format_currency(analysis['max_loss'])}")
        print(f"   ⏱️  Avg Hold Days: {analysis['avg_hold_days']:.1f}")
        print(f"   💎 Initial Capital: {format_currency(strategy_data.get('initial_capital', 0))}")
        print(f"   🎯 Final Capital: {format_currency(strategy_data.get('final_capital', 0))}")
        
        return_pct = 0
        initial = strategy_data.get('initial_capital', 0)
        final = strategy_data.get('final_capital', 0)
        if initial > 0:
            return_pct = ((final - initial) / initial * 100)
        print(f"   📊 Total Return: {format_percentage(return_pct)}")
        
        # Show individual trades
        print(f"\n📋 {strategy.upper()} TRADES DETAIL:")
        if strategy == 'long':
            print(f"{'#':<3} {'Buy Date':<12} {'Sell Date':<12} {'Buy $':<8} {'Sell $':<8} {'Shares':<6} {'Fee $':<7} {'PnL $':<10} {'Days':<4}")
        else:
            print(f"{'#':<3} {'Short Date':<12} {'Cover Date':<12} {'Short $':<8} {'Cover $':<8} {'Shares':<6} {'Fee $':<7} {'PnL $':<10} {'Days':<4}")
        print("-" * 85)
        
        for i, trade in enumerate(filtered_trades, 1):
            if 'buy_date' in trade:
                # Long trades
                entry_date = datetime.strptime(trade['buy_date'], '%Y-%m-%d %H:%M:%S')
                exit_date = datetime.strptime(trade['sell_date'], '%Y-%m-%d %H:%M:%S')
                entry_price = trade['buy_price']
                exit_price = trade['sell_price']
            else:
                # Short trades
                entry_date = datetime.strptime(trade['short_date'], '%Y-%m-%d %H:%M:%S')
                exit_date = datetime.strptime(trade['cover_date'], '%Y-%m-%d %H:%M:%S')
                entry_price = trade['short_price']
                exit_price = trade['cover_price']
            
            hold_days = (exit_date - entry_date).days
            pnl_color = "🟢" if trade['pnl'] > 0 else "🔴"
            
            print(f"{i:<3} {entry_date.strftime('%Y-%m-%d'):<12} {exit_date.strftime('%Y-%m-%d'):<12} "
                  f"{entry_price:<8.2f} {exit_price:<8.2f} {trade['shares']:<6} "
                  f"{trade['fee']:<7.2f} {pnl_color}{trade['pnl']:<9.2f} {hold_days:<4}")
        
        total_trades_shown += len(filtered_trades)
    
    if total_trades_shown == 0:
        print(f"\n🔴 No trades found for {ticker} matching the specified filters")

def print_portfolio_summary(data):
    """Print overall portfolio summary"""
    print(f"\n{'='*80}")
    print(f"🏆 PORTFOLIO SUMMARY - ALL TICKERS")
    print(f"{'='*80}")
    
    portfolio_stats = {
        'long': {'tickers': 0, 'total_trades': 0, 'winning_trades': 0, 'total_pnl': 0, 'initial_capital': 0, 'final_capital': 0},
        'short': {'tickers': 0, 'total_trades': 0, 'winning_trades': 0, 'total_pnl': 0, 'initial_capital': 0, 'final_capital': 0}
    }
    
    best_performers = {'long': [], 'short': []}
    
    for ticker, ticker_data in data.items():
        for strategy in ['long', 'short']:
            if strategy not in ticker_data or not isinstance(ticker_data[strategy], dict):
                continue
                
            strategy_data = ticker_data[strategy]
            trades = strategy_data.get('trades', [])
            
            if not trades:
                continue
            
            stats = portfolio_stats[strategy]
            stats['tickers'] += 1
            stats['total_trades'] += len(trades)
            stats['winning_trades'] += len([t for t in trades if t['pnl'] > 0])
            stats['total_pnl'] += sum(t['pnl'] for t in trades)
            stats['initial_capital'] += strategy_data.get('initial_capital', 0)
            stats['final_capital'] += strategy_data.get('final_capital', 0)
            
            # Track best performers
            initial = strategy_data.get('initial_capital', 0)
            final = strategy_data.get('final_capital', 0)
            if initial > 0:
                return_pct = ((final - initial) / initial * 100)
                best_performers[strategy].append((ticker, return_pct, len(trades), sum(t['pnl'] for t in trades)))
    
    # Print summary for each strategy
    for strategy in ['long', 'short']:
        stats = portfolio_stats[strategy]
        if stats['tickers'] == 0:
            continue
            
        strategy_emoji = "🟢" if strategy == 'long' else "🔴"
        print(f"\n{strategy_emoji} {strategy.upper()} PORTFOLIO:")
        print(f"   📊 Active Tickers: {stats['tickers']}")
        print(f"   🎯 Total Trades: {stats['total_trades']}")
        print(f"   ✅ Winning Trades: {stats['winning_trades']} ({stats['winning_trades']/stats['total_trades']*100:.1f}%)")
        print(f"   💰 Total PnL: {format_currency(stats['total_pnl'])}")
        print(f"   💎 Initial Capital: {format_currency(stats['initial_capital'])}")
        print(f"   🎯 Final Capital: {format_currency(stats['final_capital'])}")
        
        if stats['initial_capital'] > 0:
            portfolio_return = ((stats['final_capital'] - stats['initial_capital']) / stats['initial_capital'] * 100)
            print(f"   📊 Portfolio Return: {format_percentage(portfolio_return)}")
        
        # Show top performers
        best_performers[strategy].sort(key=lambda x: x[1], reverse=True)
        print(f"   🏅 Top Performers:")
        for i, (ticker, return_pct, trades_count, total_pnl) in enumerate(best_performers[strategy][:3], 1):
            print(f"      {i}. {ticker}: {format_percentage(return_pct)} ({trades_count} trades, {format_currency(total_pnl)} PnL)")

def main():
    """Main function"""
    print("🚀 COMPREHENSIVE TRADE SUMMARY FOR ALL TICKERS")
    print("="*80)
    
    # Load data
    data = load_trade_data()
    if not data:
        return
    
    print(f"📊 Loaded data for {len(data)} tickers")
    
    # Print portfolio summary first
    print_portfolio_summary(data)
    
    # Print detailed trades for each ticker
    for ticker in sorted(data.keys()):
        print_ticker_trades(ticker, data[ticker])
    
    print(f"\n{'='*80}")
    print("🎉 TRADE ANALYSIS COMPLETE!")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()
