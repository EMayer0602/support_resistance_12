#!/usr/bin/env python3
"""
Extract comprehensive performance data from terminal output
and create a complete summary
"""

import json
import re
from tickers_config import tickers

# Data extracted from terminal output
terminal_results = {
    "AAPL": {
        "data_info": {"start_date": "2023-08-10", "end_date": "2025-08-08", "rows": 501},
        "long": {"parameters": {"p": 3, "tw": 1}, "extended_signals": 65, "matched_trades": 28, "initial_capital": 1000, "final_capital": 25367.67},
        "short": {"parameters": {"p": 3, "tw": 1}, "extended_signals": 65, "matched_trades": 28, "initial_capital": 1000, "final_capital": 10453.98}
    },
    "GOOGL": {
        "data_info": {"start_date": "2023-08-10", "end_date": "2025-08-08", "rows": 501},
        "long": {"parameters": {"p": 4, "tw": 1}, "extended_signals": 61, "matched_trades": 28, "initial_capital": 1200, "final_capital": 60745.82},
        "short": {"parameters": {"p": 4, "tw": 1}, "extended_signals": 61, "matched_trades": 28, "initial_capital": 1200, "final_capital": 11737.15}
    },
    "NVDA": {
        "data_info": {"start_date": "2023-08-10", "end_date": "2025-08-08", "rows": 501},
        "long": {"parameters": {"p": 3, "tw": 1}, "extended_signals": 74, "matched_trades": 30, "initial_capital": 1800, "final_capital": 47712.36},
        "short": "disabled"
    },
    "MSFT": {
        "data_info": {"start_date": "2023-08-10", "end_date": "2025-08-08", "rows": 501},
        "long": {"parameters": {"p": 3, "tw": 1}, "extended_signals": 69, "matched_trades": 29, "initial_capital": 1100, "final_capital": 6842.28},
        "short": {"parameters": {"p": 3, "tw": 1}, "extended_signals": 69, "matched_trades": 29, "initial_capital": 1100, "final_capital": 4190.35}
    },
    "META": {
        "data_info": {"start_date": "2023-08-10", "end_date": "2025-08-08", "rows": 501},
        "long": {"parameters": {"p": 3, "tw": 1}, "extended_signals": 65, "matched_trades": 28, "initial_capital": 1000, "final_capital": 13085.01},
        "short": {"parameters": {"p": 3, "tw": 1}, "extended_signals": 65, "matched_trades": 28, "initial_capital": 1000, "final_capital": 4950.36}
    },
    "AMD": {
        "data_info": {"start_date": "2023-08-10", "end_date": "2025-08-08", "rows": 501},
        "long": {"parameters": {"p": 3, "tw": 1}, "extended_signals": 78, "matched_trades": 34, "initial_capital": 1000, "final_capital": 25367.67},
        "short": {"parameters": {"p": 3, "tw": 1}, "extended_signals": 78, "matched_trades": 34, "initial_capital": 1000, "final_capital": 11107.27}
    },
    "QBTS": {
        "data_info": {"start_date": "2024-07-22", "end_date": "2025-08-08", "rows": 264},
        "long": {"parameters": {"p": 3, "tw": 1}, "extended_signals": 47, "matched_trades": 19, "initial_capital": 1000, "final_capital": 976927.90},
        "short": "disabled"
    },
    "TSLA": {
        "data_info": {"start_date": "2023-08-10", "end_date": "2025-08-08", "rows": 501},
        "long": {"parameters": {"p": 3, "tw": 1}, "extended_signals": 79, "matched_trades": 30, "initial_capital": 1000, "final_capital": 28897.51},
        "short": {"parameters": {"p": 9, "tw": 1}, "extended_signals": 79, "matched_trades": 14, "initial_capital": 1000, "final_capital": 9316.81}
    },
    "MRNA": {
        "data_info": {"start_date": "2024-07-22", "end_date": "2025-08-08", "rows": 264},
        "long": {"parameters": {"p": 3, "tw": 1}, "extended_signals": 40, "matched_trades": 18, "initial_capital": 1000, "final_capital": 5797.51},
        "short": {"parameters": {"p": 3, "tw": 1}, "extended_signals": 40, "matched_trades": 19, "initial_capital": 1000, "final_capital": 13490.49}
    },
    "NFLX": {
        "data_info": {"start_date": "2024-08-05", "end_date": "2025-08-08", "rows": 264},
        "long": {"parameters": {"p": 7, "tw": 1}, "extended_signals": 20, "matched_trades": 9, "initial_capital": 1500, "final_capital": 3901.07},
        "short": "disabled"
    },
    "AMZN": {
        "data_info": {"start_date": "2023-08-10", "end_date": "2025-08-08", "rows": 501},
        "long": {"parameters": {"p": 3, "tw": 1}, "extended_signals": 69, "matched_trades": 28, "initial_capital": 1000, "final_capital": 5205.25},
        "short": {"parameters": {"p": 3, "tw": 1}, "extended_signals": 69, "matched_trades": 29, "initial_capital": 1000, "final_capital": 2843.57}
    },
    "INTC": {
        "data_info": {"start_date": "2024-07-22", "end_date": "2025-08-08", "rows": 264},
        "long": {"parameters": {"p": 9, "tw": 1}, "extended_signals": 19, "matched_trades": 9, "initial_capital": 1000, "final_capital": 4418.62},
        "short": {"parameters": {"p": 9, "tw": 1}, "extended_signals": 19, "matched_trades": 9, "initial_capital": 1000, "final_capital": 4586.15}
    },
    "BRRR": {
        "data_info": {"start_date": "2024-08-05", "end_date": "2025-08-08", "rows": 264},
        "long": {"parameters": {"p": 4, "tw": 1}, "extended_signals": 34, "matched_trades": 15, "initial_capital": 1000, "final_capital": 5556.38},
        "short": {"parameters": {"p": 4, "tw": 1}, "extended_signals": 34, "matched_trades": 15, "initial_capital": 1000, "final_capital": 2359.36}
    },
    "QUBT": {
        "data_info": {"start_date": "2024-07-24", "end_date": "2025-08-08", "rows": 264},
        "long": {"parameters": {"p": 3, "tw": 1}, "extended_signals": 43, "matched_trades": 17, "initial_capital": 2000, "final_capital": 665197.89},
        "short": "disabled"
    }
}

def main():
    print('🚀 COMPREHENSIVE BACKTEST SUMMARY FOR ALL TICKERS')
    print('=' * 70)

    # Calculate totals
    total_tickers = len(terminal_results)
    total_long_return = 0
    total_short_return = 0
    total_long_capital = 0
    total_short_capital = 0
    total_long_initial = 0
    total_short_initial = 0
    
    # Best performers tracking
    best_long_return = 0
    best_short_return = 0
    best_long_ticker = ""
    best_short_ticker = ""

    for ticker, results in terminal_results.items():
        print(f'\n🎯 {ticker}:')
        data_info = results.get('data_info', {})
        print(f'   📅 Data: {data_info.get("start_date", "N/A")} to {data_info.get("end_date", "N/A")} ({data_info.get("rows", 0)} days)')
        
        # Get trade_on from tickers config
        trade_on = tickers.get(ticker, {}).get('trade_on', 'open')
        print(f'   📈 Trade On: {trade_on.upper()}')
        
        if 'long' in results and results['long'] != 'disabled':
            long = results['long']
            params = long.get('parameters', {})
            initial = long.get('initial_capital', 0)
            final = long.get('final_capital', 0)
            return_pct = ((final - initial) / initial * 100) if initial > 0 else 0
            
            total_long_initial += initial
            total_long_capital += final
            
            if return_pct > best_long_return:
                best_long_return = return_pct
                best_long_ticker = ticker
            
            print(f'   🟢 Long: p={params.get("p", "N/A")}, tw={params.get("tw", "N/A")}')
            print(f'       📡 Extended Signals: {long.get("extended_signals", 0)}')
            print(f'       🎯 Matched Trades: {long.get("matched_trades", 0)}')
            print(f'       💰 Initial Capital: ${initial:,.2f}')
            print(f'       💎 Final Capital: ${final:,.2f}')
            print(f'       📊 Return: {return_pct:+.2f}%')
        
        if 'short' in results and results['short'] != 'disabled':
            short = results['short']
            params = short.get('parameters', {})
            initial = short.get('initial_capital', 0)
            final = short.get('final_capital', 0)
            return_pct = ((final - initial) / initial * 100) if initial > 0 else 0
            
            total_short_initial += initial
            total_short_capital += final
            
            if return_pct > best_short_return:
                best_short_return = return_pct
                best_short_ticker = ticker
            
            print(f'   🔴 Short: p={params.get("p", "N/A")}, tw={params.get("tw", "N/A")}')
            print(f'       📡 Extended Signals: {short.get("extended_signals", 0)}')
            print(f'       🎯 Matched Trades: {short.get("matched_trades", 0)}')
            print(f'       💰 Initial Capital: ${initial:,.2f}')
            print(f'       💎 Final Capital: ${final:,.2f}')
            print(f'       📊 Return: {return_pct:+.2f}%')
        
        if results.get('short') == 'disabled':
            print(f'   🔴 Short: DISABLED')

    # Print totals and best performers
    print(f'\n🏆 PORTFOLIO SUMMARY:')
    print('=' * 70)
    print(f'📊 Total Tickers Processed: {total_tickers}')
    
    if total_long_initial > 0:
        total_long_return = ((total_long_capital - total_long_initial) / total_long_initial * 100)
        print(f'🟢 Long Portfolio:')
        print(f'   💰 Total Initial Capital: ${total_long_initial:,.2f}')
        print(f'   💎 Total Final Capital: ${total_long_capital:,.2f}')
        print(f'   📊 Total Long Return: {total_long_return:+.2f}%')
        print(f'   🏅 Best Long Performer: {best_long_ticker} ({best_long_return:+.2f}%)')
    
    if total_short_initial > 0:
        total_short_return = ((total_short_capital - total_short_initial) / total_short_initial * 100)
        print(f'🔴 Short Portfolio:')
        print(f'   💰 Total Initial Capital: ${total_short_initial:,.2f}')
        print(f'   💎 Total Final Capital: ${total_short_capital:,.2f}')
        print(f'   📊 Total Short Return: {total_short_return:+.2f}%')
        print(f'   🏅 Best Short Performer: {best_short_ticker} ({best_short_return:+.2f}%)')
    
    if total_long_initial > 0 and total_short_initial > 0:
        combined_initial = total_long_initial + total_short_initial
        combined_final = total_long_capital + total_short_capital
        combined_return = ((combined_final - combined_initial) / combined_initial * 100)
        print(f'🎯 Combined Portfolio:')
        print(f'   💰 Total Initial Capital: ${combined_initial:,.2f}')
        print(f'   💎 Total Final Capital: ${combined_final:,.2f}')
        print(f'   📊 Combined Return: {combined_return:+.2f}%')

    print('\n🎉 TOP PERFORMERS:')
    print('=' * 70)
    
    # Sort by returns for top performers
    long_performers = []
    short_performers = []
    
    for ticker, results in terminal_results.items():
        if 'long' in results and results['long'] != 'disabled':
            long = results['long']
            initial = long.get('initial_capital', 0)
            final = long.get('final_capital', 0)
            return_pct = ((final - initial) / initial * 100) if initial > 0 else 0
            long_performers.append((ticker, return_pct, final))
        
        if 'short' in results and results['short'] != 'disabled':
            short = results['short']
            initial = short.get('initial_capital', 0)
            final = short.get('final_capital', 0)
            return_pct = ((final - initial) / initial * 100) if initial > 0 else 0
            short_performers.append((ticker, return_pct, final))
    
    # Sort and display top 3
    long_performers.sort(key=lambda x: x[1], reverse=True)
    short_performers.sort(key=lambda x: x[1], reverse=True)
    
    print('🟢 TOP LONG PERFORMERS:')
    for i, (ticker, return_pct, final_capital) in enumerate(long_performers[:3], 1):
        print(f'   {i}. {ticker}: {return_pct:+.2f}% (${final_capital:,.2f})')
    
    print('🔴 TOP SHORT PERFORMERS:')
    for i, (ticker, return_pct, final_capital) in enumerate(short_performers[:3], 1):
        print(f'   {i}. {ticker}: {return_pct:+.2f}% (${final_capital:,.2f})')

    print('\n' + '=' * 70)

if __name__ == "__main__":
    main()
