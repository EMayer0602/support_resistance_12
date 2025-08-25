#!/usr/bin/env python3
"""
Today's Trading Signals Checker
Checks for support/resistance signals for today's trading

Usage:
python check_todays_signals.py [--trade-on OPEN|CLOSE]
"""

import json
import os
import sys
from datetime import datetime, timedelta
import argparse
from functools import lru_cache
from tickers_config import tickers
from config import *

def convert_ticker_config():
    """Convert the existing ticker config to our expected format"""
    config = {}
    for symbol, data in tickers.items():
        strategies = []
        if data.get('long', False):
            strategies.append('LONG')
        if data.get('short', False):
            strategies.append('SHORT')
        
        config[symbol] = {
            'strategies': strategies,
            'trade_on': data.get('trade_on', 'open').upper(),
            'initialCapitalLong': data.get('initialCapitalLong', 1000),
            'initialCapitalShort': data.get('initialCapitalShort', 1000),
            'conID': data.get('conID'),
            'order_round_factor': data.get('order_round_factor', ORDER_ROUND_FACTOR)
        }
    return config

# Convert config format
TICKERS_CONFIG = convert_ticker_config()

def load_backtest_results():
    """Load the comprehensive backtest results"""
    results_file = 'complete_comprehensive_backtest_results.json'
    
    if not os.path.exists(results_file):
        print("[FAIL] No backtest results found!")
        print("   Run: python complete_comprehensive_backtest.py")
        return None
    
    with open(results_file, 'r') as f:
        return json.load(f)

def load_runner_trades_today(trade_on_filter=None):
    """Load today's trades from trades_by_day.json (runner.py output) and convert to signal format."""
    file_path = 'trades_by_day.json'
    if not os.path.exists(file_path):
        return []

    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
    except Exception:
        return []

    today_str = datetime.now().strftime('%Y-%m-%d')
    trades = data.get(today_str, []) or []
    if not trades:
        return []

    # Load parameter mapping from runner fullbacktest export (if available)
    runner_params = load_runner_parameters()

    signals = []
    for t in trades:
        ticker = t.get('symbol')
        side = t.get('side')
        if not ticker or not side:
            continue

        if ticker not in TICKERS_CONFIG:
            continue

        trade_on = TICKERS_CONFIG[ticker]['trade_on']
        if trade_on_filter and trade_on != trade_on_filter:
            continue

        # Map sides to strategy/action
        if side in ('BUY', 'SELL'):
            strategy = 'LONG'
            action = side  # BUY or SELL
        elif side in ('SHORT', 'COVER'):
            strategy = 'SHORT'
            action = 'SHORT' if side == 'SHORT' else 'COVER'
        else:
            continue

        # Pull p, tw from runner parameters if present
        p_param = None
        tw_param = None
        rp = runner_params.get(ticker)
        if rp:
            strat_params = rp.get(strategy)
            if strat_params:
                p_param = strat_params.get('p')
                tw_param = strat_params.get('tw')

        signals.append({
            'ticker': ticker,
            'strategy': strategy,
            'date': today_str,
            'action': action,
            'price': t.get('price'),
            'signal_type': 'runner_backtest',
            'p_param': p_param,
            'tw_param': tw_param,
            'trade_on': trade_on
        })

    return signals

@lru_cache(maxsize=1)
def load_runner_parameters():
    """Load per-symbol strategy parameters (p, tw) from runner_fullbacktest_results.json.
    Returns mapping like { 'AAPL': { 'LONG': {'p':3,'tw':2}, 'SHORT': {'p':4,'tw':1} } }
    """
    path = 'runner_fullbacktest_results.json'
    if not os.path.exists(path):
        return {}
    try:
        with open(path, 'r') as f:
            data = json.load(f)
    except Exception:
        return {}
    out = {}
    for symbol, sym_data in data.items():
        sym_map = {}
        for side_key, side_name in (('long','LONG'), ('short','SHORT')):
            if side_key in sym_data:
                params = sym_data[side_key].get('parameters', {}) or {}
                p = params.get('p')
                tw = params.get('tw')
                if p is not None or tw is not None:
                    sym_map[side_name] = {'p': p, 'tw': tw}
        if sym_map:
            out[symbol] = sym_map
    return out

def check_todays_signals(trade_on_filter=None):
    """Check for signals today"""
    backtest_data = load_backtest_results()
    
    today_str = datetime.now().strftime('%Y-%m-%d')
    print(f"[CHECK] CHECKING SIGNALS FOR: {today_str}")
    print("="*50)
    
    found_signals = []
    printed_keys = set()  # track which (ticker, action, strategy, date) were already printed
    
    # If we have comprehensive backtest results, prefer them
    if backtest_data:
        for ticker, ticker_data in backtest_data.items():
            if ticker not in TICKERS_CONFIG:
                continue
            
            ticker_config = TICKERS_CONFIG[ticker]
            
            # Filter by trade timing if specified
            if trade_on_filter and ticker_config['trade_on'] != trade_on_filter:
                continue
            
            print(f"\n[TICKER] {ticker} ({ticker_config['trade_on']} trades)")
            print("-" * 30)
            
            ticker_signals = []
            
            # Check both long and short strategies
            for strategy in ['LONG', 'SHORT']:
                if strategy not in ticker_config['strategies']:
                    continue
                    
                strategy_key = f"{strategy.lower()}_strategy"
                if strategy_key not in ticker_data:
                    continue
                    
                extended_signals = ticker_data[strategy_key].get('extended_signals', [])
                
                # Look for today's signals
                for signal in extended_signals:
                    if signal.get('date') == today_str:
                        ticker_signals.append({
                            'ticker': ticker,
                            'strategy': strategy,
                            'date': signal.get('date'),
                            'action': signal.get('action'),
                            'price': signal.get('price'),
                            'signal_type': signal.get('signal_type'),
                            'p_param': signal.get('p_param'),
                            'tw_param': signal.get('tw_param'),
                            'trade_on': ticker_config['trade_on']
                        })
            
            if ticker_signals:
                for signal in ticker_signals:
                    action_tag = "[BUY]" if signal['action'] in ['BUY', 'COVER'] else "[SELL]"
                    print(f"  {action_tag} {signal['strategy']} {signal['action']}")
                    price_val = signal['price']
                    if price_val is not None:
                        print(f"     Price: ${price_val:.2f}")
                    else:
                        print(f"     Price: N/A")
                    print(f"     Signal: {signal['signal_type']}")
                    print(f"     Params: p={signal['p_param']}, tw={signal['tw_param']}")
                    print(f"     Execute: {signal['trade_on']}")
                    
                for sig in ticker_signals:
                    key = (sig['ticker'], sig['action'], sig['strategy'], sig['date'])
                    printed_keys.add(key)
                found_signals.extend(ticker_signals)
            else:
                print("  [NONE] No signals today")

    # Also include runner.py trades as a fallback/augment for today
    runner_signals = load_runner_trades_today(trade_on_filter)
    if runner_signals:
        print(f"\n[INFO] Adding {len(runner_signals)} signals from trades_by_day.json (runner backtest)")
        # Deduplicate & collect those not previously printed
        existing = {(s['ticker'], s['action'], s['strategy'], s['date']) for s in found_signals}
        newly_added = []
        for s in runner_signals:
            key = (s['ticker'], s['action'], s['strategy'], s['date'])
            if key not in existing:
                found_signals.append(s)
                newly_added.append(s)
        # Print details for newly added runner signals (grouped by ticker)
        if newly_added:
            by_ticker = {}
            for s in newly_added:
                by_ticker.setdefault(s['ticker'], []).append(s)
            print("\n[DETAIL] Runner-derived signals (not present in comprehensive backtest):")
            for ticker in sorted(by_ticker.keys()):
                print(f"  {ticker} ({by_ticker[ticker][0]['trade_on']} trades)")
                for sig in by_ticker[ticker]:
                    action_tag = "[BUY]" if sig['action'] in ['BUY', 'COVER'] else "[SELL]"
                    price_val = sig.get('price')
                    price_str = f"${price_val:.2f}" if price_val is not None else "N/A"
                    print(f"     {action_tag} {sig['strategy']} {sig['action']} @ {price_str} (source={sig.get('signal_type','runner')})")
                    print(f"        Params: p={sig.get('p_param')}, tw={sig.get('tw_param')} Execute={sig['trade_on']}")
    
    print("\n" + "="*50)
    print(f"[SUMMARY] {len(found_signals)} signals found for today")
    
    if found_signals:
        # Group by trade timing
        open_signals = [s for s in found_signals if s['trade_on'] == 'OPEN']
        close_signals = [s for s in found_signals if s['trade_on'] == 'CLOSE']

        # Dynamically compute execution times from config
        try:
            market_open_dt = datetime.strptime(MARKET_OPEN_TIME, "%H:%M")
            market_close_dt = datetime.strptime(MARKET_CLOSE_TIME, "%H:%M")
            open_exec_dt = (market_open_dt + timedelta(minutes=OPEN_TRADE_DELAY)).strftime('%H:%M')
            close_exec_dt = (market_close_dt - timedelta(minutes=CLOSE_TRADE_ADVANCE)).strftime('%H:%M')
        except Exception:
            open_exec_dt = "(config error)"
            close_exec_dt = "(config error)"

        if open_signals:
            print(f"   OPEN trades: {len(open_signals)} signals")
            print(f"      Execute at: {open_exec_dt} ET ({OPEN_TRADE_DELAY} min after market open)")

        if close_signals:
            print(f"   CLOSE trades: {len(close_signals)} signals")
            print(f"      Execute at: {close_exec_dt} ET ({CLOSE_TRADE_ADVANCE} min before market close)")
        
        print(f"\nINSTRUCTIONS:")
        print(f"   - Use LIMIT orders at the specified prices")
        print(f"   - Check portfolio positions before execution")
        print(f"   - Use real-time IB prices at execution time")
        print(f"   - Combine BUY+COVER and SELL+SHORT orders as needed")
    
    return found_signals

def print_current_time_status():
    """Show current time and trading windows using config parameters"""
    now = datetime.now()
    current_time = now.time()
    
    print(f"TIME: {now.strftime('%H:%M:%S ET')}")
    print(f"DATE: {now.strftime('%A, %B %d, %Y')}")
    
    from datetime import time
    
    # Define trading windows using config parameters
    market_open = datetime.strptime(MARKET_OPEN_TIME, "%H:%M").time()
    market_close = datetime.strptime(MARKET_CLOSE_TIME, "%H:%M").time()
    
    # Calculate trading windows
    open_start_minutes = market_open.hour * 60 + market_open.minute + OPEN_TRADE_DELAY
    open_trade_time = time(open_start_minutes // 60, open_start_minutes % 60)
    
    close_start_minutes = market_close.hour * 60 + market_close.minute - CLOSE_TRADE_ADVANCE
    close_trade_time = time(close_start_minutes // 60, close_start_minutes % 60)
    
    print(f"\nTRADING WINDOWS TODAY:")
    
    if current_time < open_trade_time:
        print(f"   Waiting for OPEN session (starts at {open_trade_time.strftime('%H:%M')} ET)")
    elif current_time < close_trade_time:
        print(f"   OPEN session completed")
        print(f"   Waiting for CLOSE session (starts at {close_trade_time.strftime('%H:%M')} ET)")
    elif current_time < market_close:
        print(f"   CLOSE session active NOW!")
    else:
        print(f"   Market closed for today")
    
    print(f"\nSCHEDULE (from config.py):")
    print(f"   Market Opens: {MARKET_OPEN_TIME} ET")
    print(f"   OPEN Trades: {open_trade_time.strftime('%H:%M')} ET ({OPEN_TRADE_DELAY} min after open)")
    print(f"   CLOSE Trades: {close_trade_time.strftime('%H:%M')} ET ({CLOSE_TRADE_ADVANCE} min before close)")
    print(f"   Market Closes: {MARKET_CLOSE_TIME} ET")
    
    print(f"\nCAPITAL SETTINGS:")
    print(f"   Total Capital: ${INITIAL_CAPITAL:,.2f}")
    print(f"   Commission Rate: {DEFAULT_COMMISSION_RATE*100:.2f}%")
    print(f"   Min Commission: ${MIN_COMMISSION:.2f}")
    print(f"   Limit Offset: ${LIMIT_ORDER_OFFSET:.2f}")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Check today\'s trading signals')
    parser.add_argument('--trade-on', choices=['OPEN', 'CLOSE'], 
                       help='Filter by trade timing (OPEN or CLOSE)')
    parser.add_argument('--time-status', action='store_true',
                       help='Show current time and trading windows')
    
    args = parser.parse_args()
    
    print("TODAY'S TRADING SIGNALS CHECKER")
    print("="*40)
    
    if args.time_status:
        print_current_time_status()
        print("\n" + "="*40)
    
    # Check signals
    signals = check_todays_signals(args.trade_on)
    
    if not signals:
        print(f"\nNo trading signals for today")
        if not args.trade_on:
            print(f"   Try: --trade-on OPEN  or  --trade-on CLOSE")
    
    print(f"\nNEXT STEPS:")
    print(f"   1. Wait for appropriate trading window")
    print(f"   2. Connect to IB Paper Trading (port 7497)")
    print(f"   3. Use real-time prices for LIMIT orders")
    print(f"   4. Monitor portfolio positions before trading")

if __name__ == "__main__":
    main()
