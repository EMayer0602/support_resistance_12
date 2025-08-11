#!/usr/bin/env python3
"""
Display comprehensive backtest summary for ALL tickers
"""
import json
from tickers_config import tickers

def main():
    try:
        with open('all_tickers_backtest_results.json', 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print("❌ Results file not found. Please run the backtest first.")
        return

    print('📊 COMPREHENSIVE BACKTEST SUMMARY FOR ALL TICKERS')
    print('=' * 70)

    # Calculate totals
    total_tickers = len(data)
    total_long_return = 0
    total_short_return = 0
    total_long_capital = 0
    total_short_capital = 0
    total_long_initial = 0
    total_short_initial = 0

    for ticker, results in data.items():
        print(f'\n🎯 {ticker}:')
        data_info = results.get('data_info', {})
        print(f'   📅 Data: {data_info.get("start_date", "N/A")} to {data_info.get("end_date", "N/A")} ({data_info.get("rows", 0)} days)')
        
        # Get trade_on from tickers config
        trade_on = tickers.get(ticker, {}).get('trade_on', 'close')
        print(f'   📈 Trade On: {trade_on.upper()}')
        
        if 'long' in results:
            long = results['long']
            params = long.get('parameters', {})
            initial = long.get('initial_capital', 0)
            final = long.get('final_capital', 0)
            return_pct = ((final - initial) / initial * 100) if initial > 0 else 0
            
            total_long_initial += initial
            total_long_capital += final
            
            print(f'   🟢 Long: p={params.get("p", "N/A")}, tw={params.get("tw", "N/A")}')
            print(f'       📡 Extended Signals: {long.get("extended_signals", 0)}')
            print(f'       🎯 Matched Trades: {long.get("matched_trades", 0)}')
            print(f'       💰 Initial Capital: ${initial:,.2f}')
            print(f'       💎 Final Capital: ${final:,.2f}')
            print(f'       📊 Return: {return_pct:+.2f}%')
        
        if 'short' in results:
            short = results['short']
            params = short.get('parameters', {})
            initial = short.get('initial_capital', 0)
            final = short.get('final_capital', 0)
            return_pct = ((final - initial) / initial * 100) if initial > 0 else 0
            
            total_short_initial += initial
            total_short_capital += final
            
            print(f'   🔴 Short: p={params.get("p", "N/A")}, tw={params.get("tw", "N/A")}')
            print(f'       📡 Extended Signals: {short.get("extended_signals", 0)}')
            print(f'       🎯 Matched Trades: {short.get("matched_trades", 0)}')
            print(f'       💰 Initial Capital: ${initial:,.2f}')
            print(f'       💎 Final Capital: ${final:,.2f}')
            print(f'       📊 Return: {return_pct:+.2f}%')

    # Print totals
    print(f'\n🏆 PORTFOLIO SUMMARY:')
    print('=' * 70)
    print(f'📊 Total Tickers Processed: {total_tickers}')
    
    if total_long_initial > 0:
        total_long_return = ((total_long_capital - total_long_initial) / total_long_initial * 100)
        print(f'🟢 Long Portfolio:')
        print(f'   💰 Total Initial Capital: ${total_long_initial:,.2f}')
        print(f'   💎 Total Final Capital: ${total_long_capital:,.2f}')
        print(f'   📊 Total Long Return: {total_long_return:+.2f}%')
    
    if total_short_initial > 0:
        total_short_return = ((total_short_capital - total_short_initial) / total_short_initial * 100)
        print(f'🔴 Short Portfolio:')
        print(f'   💰 Total Initial Capital: ${total_short_initial:,.2f}')
        print(f'   💎 Total Final Capital: ${total_short_capital:,.2f}')
        print(f'   📊 Total Short Return: {total_short_return:+.2f}%')
    
    if total_long_initial > 0 and total_short_initial > 0:
        combined_initial = total_long_initial + total_short_initial
        combined_final = total_long_capital + total_short_capital
        combined_return = ((combined_final - combined_initial) / combined_initial * 100)
        print(f'🎯 Combined Portfolio:')
        print(f'   💰 Total Initial Capital: ${combined_initial:,.2f}')
        print(f'   💎 Total Final Capital: ${combined_final:,.2f}')
        print(f'   📊 Combined Return: {combined_return:+.2f}%')

    print('\n' + '=' * 70)

if __name__ == "__main__":
    main()
