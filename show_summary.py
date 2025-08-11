#!/usr/bin/env python3
import json
from tickers_config import tickers

with open('complete_comprehensive_backtest_results.json', 'r') as f:
    data = json.load(f)

print('COMPREHENSIVE BACKTEST SUMMARY FOR ALL TICKERS')
print('=' * 60)

for ticker, results in data.items():
    print(f'\n{ticker}:')
    data_info = results.get('data_info', {})
    print(f'   Data: {data_info.get("start_date", "N/A")} to {data_info.get("end_date", "N/A")} ({data_info.get("rows", 0)} days)')
    
    # Get trade_on from tickers config
    trade_on = tickers.get(ticker, {}).get('trade_on', 'close')
    print(f'   Trade On: {trade_on.upper()}')
    
    if 'long' in results:
        long = results['long']
        params = long.get('parameters', {})
        initial = long.get('initial_capital', 0)
        final = long.get('final_capital', 0)
        return_pct = ((final - initial) / initial * 100) if initial > 0 else 0
        print(f'   Long: p={params.get("p", "N/A")}, tw={params.get("tw", "N/A")}')
        print(f'       Extended Signals: {long.get("extended_signals", 0)}')
        print(f'       Matched Trades: {long.get("matched_trades", 0)}')
        print(f'       Initial Capital: ${initial:.2f}')
        print(f'       Final Capital: ${final:.2f}')
        print(f'       Return: {return_pct:.2f}%')
    
    if 'short' in results:
        short = results['short']
        params = short.get('parameters', {})
        initial = short.get('initial_capital', 0)
        final = short.get('final_capital', 0)
        return_pct = ((final - initial) / initial * 100) if initial > 0 else 0
        print(f'   Short: p={params.get("p", "N/A")}, tw={params.get("tw", "N/A")}')
        print(f'       Extended Signals: {short.get("extended_signals", 0)}')
        print(f'       Matched Trades: {short.get("matched_trades", 0)}')
        print(f'       Initial Capital: ${initial:.2f}')
        print(f'       Final Capital: ${final:.2f}')
        print(f'       Return: {return_pct:.2f}%')
