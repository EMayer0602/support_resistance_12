#!/usr/bin/env python3
"""
Single Trade List Generator for Paper Trading
Command line usage: python single_trades.py START_DATE END_DATE [STRATEGY]
Example: python single_trades.py 2025-07-01 2025-08-01 long
"""

import json
import sys
import argparse
import os
from datetime import datetime
import pandas as pd
from tickers_config import tickers

def load_trade_data():
    """Load trade data from the comprehensive backtest results"""
    try:
        with open('complete_comprehensive_backtest_results.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("❌ Results file not found. Please run the comprehensive backtest first.")
        return None

def _parse_date_flexible(val: str) -> datetime:
    """Try multiple date formats (with or without time)"""
    if not val:
        return None
    formats = ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d']
    for fmt in formats:
        try:
            return datetime.strptime(val, fmt)
        except ValueError:
            continue
    # Fallback: pandas parser
    try:
        return pd.to_datetime(val).to_pydatetime()
    except Exception:
        return None

def extract_single_trades(data, start_date, end_date, strategy_filter=None):
    """Extract individual trade entries (JSON structure or fallback CSV)"""
    single_trades = []

    # Map possible key variants: 'long' or 'long_strategy'
    key_variants = {
        'long': ['long', 'long_strategy'],
        'short': ['short', 'short_strategy']
    }

    for ticker, ticker_data in data.items():
        ticker_config = tickers.get(ticker, {})
        trade_on = ticker_config.get('trade_on', 'close').upper()

        strategies = ['long', 'short']
        if strategy_filter:
            strategies = [strategy_filter]

        for strategy in strategies:
            # Find existing key variant
            strat_dict = None
            for k in key_variants[strategy]:
                if k in ticker_data and isinstance(ticker_data[k], dict):
                    strat_dict = ticker_data[k]
                    break
            if not strat_dict:
                continue

            trades = strat_dict.get('trades', [])
            params = strat_dict.get('parameters', {})
            p_param = params.get('p', 'N/A')
            tw_param = params.get('tw', 'N/A')

            for tr in trades:
                is_long = 'buy_date' in tr
                if is_long:
                    entry_date = _parse_date_flexible(tr.get('buy_date'))
                    exit_date = _parse_date_flexible(tr.get('sell_date'))
                    entry_price = tr.get('buy_price')
                    exit_price = tr.get('sell_price')
                    entry_action, exit_action = 'BUY', 'SELL'
                else:
                    entry_date = _parse_date_flexible(tr.get('short_date'))
                    exit_date = _parse_date_flexible(tr.get('cover_date'))
                    entry_price = tr.get('short_price')
                    exit_price = tr.get('cover_price')
                    entry_action, exit_action = 'SHORT', 'COVER'

                # Entry
                if entry_date and start_date <= entry_date <= end_date:
                    single_trades.append({
                        'ticker': ticker,
                        'strategy': strategy.upper(),
                        'trade_date': entry_date.strftime('%Y-%m-%d'),
                        'action': entry_action,
                        'order_type': 'LIMIT',
                        'price': entry_price,
                        'shares': tr.get('shares'),
                        'trade_on': trade_on,
                        'signal_type': 'ENTRY',
                        'p_param': p_param,
                        'tw_param': tw_param
                    })
                # Exit
                if exit_date and start_date <= exit_date <= end_date:
                    single_trades.append({
                        'ticker': ticker,
                        'strategy': strategy.upper(),
                        'trade_date': exit_date.strftime('%Y-%m-%d'),
                        'action': exit_action,
                        'order_type': 'LIMIT',
                        'price': exit_price,
                        'shares': tr.get('shares'),
                        'trade_on': trade_on,
                        'signal_type': 'EXIT',
                        'p_param': p_param,
                        'tw_param': tw_param
                    })

    # Fallback: if JSON produced no trades, read per-ticker CSVs
    if not single_trades:
        for ticker, cfg in tickers.items():
            if strategy_filter in (None, 'long'):
                long_csv = f'trades_long_{ticker}.csv'
                if pd.errors.EmptyDataError:
                    pass
                if os.path.exists(long_csv):
                    try:
                        df_l = pd.read_csv(long_csv)
                    except Exception:
                        df_l = None
                    if df_l is not None and not df_l.empty:
                        for _, row in df_l.iterrows():
                            entry_date = _parse_date_flexible(str(row.get('buy_date')))
                            exit_date = _parse_date_flexible(str(row.get('sell_date')))
                            if entry_date and start_date <= entry_date <= end_date:
                                single_trades.append({
                                    'ticker': ticker,
                                    'strategy': 'LONG',
                                    'trade_date': entry_date.strftime('%Y-%m-%d'),
                                    'action': 'BUY',
                                    'order_type': 'LIMIT',
                                    'price': row.get('buy_price'),
                                    'shares': row.get('shares'),
                                    'trade_on': cfg.get('trade_on','OPEN').upper(),
                                    'signal_type': 'ENTRY',
                                    'p_param': 'NA','tw_param': 'NA'
                                })
                            if exit_date and start_date <= exit_date <= end_date:
                                single_trades.append({
                                    'ticker': ticker,
                                    'strategy': 'LONG',
                                    'trade_date': exit_date.strftime('%Y-%m-%d'),
                                    'action': 'SELL',
                                    'order_type': 'LIMIT',
                                    'price': row.get('sell_price'),
                                    'shares': row.get('shares'),
                                    'trade_on': cfg.get('trade_on','OPEN').upper(),
                                    'signal_type': 'EXIT',
                                    'p_param': 'NA','tw_param': 'NA'
                                })
            if strategy_filter in (None, 'short'):
                short_csv = f'trades_short_{ticker}.csv'
                if os.path.exists(short_csv):
                    try:
                        df_s = pd.read_csv(short_csv)
                    except Exception:
                        df_s = None
                    if df_s is not None and not df_s.empty:
                        for _, row in df_s.iterrows():
                            entry_date = _parse_date_flexible(str(row.get('short_date')))
                            exit_date = _parse_date_flexible(str(row.get('cover_date')))
                            if entry_date and start_date <= entry_date <= end_date:
                                single_trades.append({
                                    'ticker': ticker,
                                    'strategy': 'SHORT',
                                    'trade_date': entry_date.strftime('%Y-%m-%d'),
                                    'action': 'SHORT',
                                    'order_type': 'LIMIT',
                                    'price': row.get('short_price'),
                                    'shares': row.get('shares'),
                                    'trade_on': cfg.get('trade_on','OPEN').upper(),
                                    'signal_type': 'ENTRY',
                                    'p_param': 'NA','tw_param': 'NA'
                                })
                            if exit_date and start_date <= exit_date <= end_date:
                                single_trades.append({
                                    'ticker': ticker,
                                    'strategy': 'SHORT',
                                    'trade_date': exit_date.strftime('%Y-%m-%d'),
                                    'action': 'COVER',
                                    'order_type': 'LIMIT',
                                    'price': row.get('cover_price'),
                                    'shares': row.get('shares'),
                                    'trade_on': cfg.get('trade_on','OPEN').upper(),
                                    'signal_type': 'EXIT',
                                    'p_param': 'NA','tw_param': 'NA'
                                })

    return single_trades

def print_single_trades(trades, start_date_str, end_date_str, strategy_filter=None):
    """Print formatted single trade list for paper trading"""
    
    if not trades:
        filter_text = f" ({strategy_filter} only)" if strategy_filter else ""
        print(f"❌ No trades found for the period {start_date_str} to {end_date_str}{filter_text}")
        return
    
    filter_text = f" - {strategy_filter.upper()} ONLY" if strategy_filter else ""
    print(f"\n📋 SINGLE TRADE LIST FOR PAPER TRADING{filter_text}")
    print(f"📅 Period: {start_date_str} to {end_date_str}")
    print(f"🎯 Total Trade Actions: {len(trades)}")
    print("="*100)
    
    # Sort trades by date
    trades_sorted = sorted(trades, key=lambda x: x['trade_date'])
    
    # Print header
    print(f"{'#':<3} {'Date':<12} {'Ticker':<6} {'Strategy':<8} {'Action':<6} "
          f"{'Type':<6} {'Price $':<9} {'Shares':<6} {'On':<5} {'Signal':<6} {'P/TW':<6}")
    print("-" * 100)
    
    entry_count = 0
    exit_count = 0
    
    for i, trade in enumerate(trades_sorted, 1):
        if trade['signal_type'] == 'ENTRY':
            entry_count += 1
        else:
            exit_count += 1
        
        params = f"{trade['p_param']}/{trade['tw_param']}"
        
        print(f"{i:<3} {trade['trade_date']:<12} {trade['ticker']:<6} {trade['strategy']:<8} "
              f"{trade['action']:<6} {trade['order_type']:<6} {trade['price']:<9.2f} "
              f"{trade['shares']:<6} {trade['trade_on']:<5} {trade['signal_type']:<6} {params:<6}")
    
    # Print summary
    print("-" * 100)
    print(f"📊 SUMMARY:")
    print(f"   🟢 Entry Signals: {entry_count}")
    print(f"   🔴 Exit Signals: {exit_count}")
    print(f"   📈 Total Actions: {len(trades_sorted)}")
    
    # Show ticker breakdown
    ticker_summary = {}
    for trade in trades_sorted:
        ticker = trade['ticker']
        if ticker not in ticker_summary:
            ticker_summary[ticker] = {'entry': 0, 'exit': 0}
        ticker_summary[ticker][trade['signal_type'].lower()] += 1
    
    print(f"\n🎯 TICKER BREAKDOWN:")
    for ticker, counts in sorted(ticker_summary.items()):
        print(f"   {ticker}: {counts['entry']} entries, {counts['exit']} exits")
    
    print(f"\n💡 PAPER TRADING INSTRUCTIONS:")
    print(f"   📝 Use LIMIT orders at the specified prices")
    print(f"   ⏰ Execute trades at market {trades_sorted[0]['trade_on'] if trades_sorted else 'OPEN'}")
    print(f"   🎯 Monitor support/resistance levels for signal confirmation")

def save_trades_csv(trades, filename):
    """Save single trades to CSV for trading platforms"""
    if not trades:
        print("❌ No trades to save")
        return
    
    import pandas as pd
    df = pd.DataFrame(trades)
    # Reorder columns for trading platform compatibility
    column_order = ['trade_date', 'ticker', 'strategy', 'action', 'order_type', 
                   'price', 'shares', 'trade_on', 'signal_type', 'p_param', 'tw_param']
    df = df[column_order]
    df.to_csv(filename, index=False)
    print(f"✅ Single trades saved to {filename}")

def main():
    """Main function with command line arguments"""
    parser = argparse.ArgumentParser(description='Generate single trade list for paper trading')
    parser.add_argument('start_date', help='Start date (YYYY-MM-DD)')
    parser.add_argument('end_date', help='End date (YYYY-MM-DD)')
    parser.add_argument('strategy', nargs='?', choices=['long', 'short'], 
                       help='Strategy filter (optional): long or short')
    parser.add_argument('--csv', action='store_true', 
                       help='Save results to CSV file')
    
    args = parser.parse_args()
    
    # Validate dates
    try:
        start_date = datetime.strptime(args.start_date, '%Y-%m-%d')
        end_date = datetime.strptime(args.end_date, '%Y-%m-%d')
    except ValueError:
        print("❌ Invalid date format. Use YYYY-MM-DD")
        return
    
    if start_date > end_date:
        print("❌ Start date must be before end date")
        return
    
    # Load data
    data = load_trade_data()
    if not data:
        return
    
    print(f"🚀 SINGLE TRADE LIST GENERATOR")
    print(f"📊 Loaded data for {len(data)} tickers")
    
    # Extract single trades
    single_trades = extract_single_trades(data, start_date, end_date, args.strategy)
    
    # Display results
    print_single_trades(single_trades, args.start_date, args.end_date, args.strategy)
    
    # Save to CSV if requested
    if args.csv and single_trades:
        filename = f"single_trades_{args.start_date}_to_{args.end_date}"
        if args.strategy:
            filename += f"_{args.strategy}"
        filename += ".csv"
        save_trades_csv(single_trades, filename)

if __name__ == "__main__":
    if len(sys.argv) == 1:
        # Show usage examples if no arguments provided
        print("🚀 SINGLE TRADE LIST GENERATOR")
        print("="*50)
        print("\nUsage examples:")
        print("  python single_trades.py 2025-07-01 2025-08-01")
        print("  python single_trades.py 2025-07-15 2025-08-08 long")
        print("  python single_trades.py 2025-06-01 2025-07-31 short --csv")
        print("\nArguments:")
        print("  START_DATE    Start date (YYYY-MM-DD)")
        print("  END_DATE      End date (YYYY-MM-DD)")
        print("  STRATEGY      Optional: 'long' or 'short'")
        print("  --csv         Save to CSV file")
        print("\nExamples:")
        print("  📈 All trades in July 2025:")
        print("     python single_trades.py 2025-07-01 2025-07-31")
        print("  🟢 Long trades only in recent period:")
        print("     python single_trades.py 2025-07-15 2025-08-08 long")
        print("  💾 Save short trades to CSV:")
        print("     python single_trades.py 2025-06-01 2025-08-01 short --csv")
    else:
        main()
