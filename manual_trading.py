#!/usr/bin/env python3
"""
Manual Paper Trading Execution
Simple script to execute today's trades manually at the right time

Usage:
python manual_trading.py [--execute] [--trade-on OPEN|CLOSE]

This script:
1. Checks for today's signals
2. Gets real-time IB prices
3. Creates combined orders (BUY+COVER, SELL+SHORT)
4. Executes trades if --execute flag is used
"""

from ib_insync import *
import sys
import os
from datetime import datetime, time
import argparse
import json
from typing import Dict, Tuple

# Import our modules
from check_todays_signals import check_todays_signals, TICKERS_CONFIG
from portfolio_manager import PortfolioManager
from config import *

class ManualTrader:
    def __init__(self, paper_trading=True):
        self.paper_trading = paper_trading
        self.ib = IB()
        self.portfolio_manager = PortfolioManager()

    def connect_ib(self):
        try:
            port = IB_PAPER_PORT if self.paper_trading else IB_LIVE_PORT
            self.ib.connect(IB_HOST, port, clientId=IB_CLIENT_ID)
            print(f"Connected to IB {'Paper' if self.paper_trading else 'Live'} Trading")
            print(f"Host: {IB_HOST}:{port}, Client ID: {IB_CLIENT_ID}")
            self.sync_portfolio_with_ib()
            return True
        except Exception as e:
            print(f"ERROR: Failed to connect to IB: {e}")
            return False

    def sync_portfolio_with_ib(self):
        try:
            positions = self.ib.positions()
            ib_positions = {}
            for pos in positions:
                ticker = pos.contract.symbol
                shares = int(pos.position)
                if shares != 0:
                    ib_positions[ticker] = shares
            self.portfolio_manager.positions = ib_positions
            self.portfolio_manager.save_portfolio()
            print("Portfolio synced with IB:")
            if ib_positions:
                for t, sh in ib_positions.items():
                    pos_type = 'LONG' if sh > 0 else 'SHORT'
                    print(f"{t}: {sh:+d} shares ({pos_type})")
            else:
                print("No open positions")
        except Exception as e:
            print(f"ERROR: syncing portfolio failed: {e}")

    def get_realtime_price(self, ticker: str) -> float | None:
        try:
            contract = Stock(ticker, 'SMART', 'USD')
            self.ib.qualifyContracts(contract)
            tickers = self.ib.reqTickers(contract)
            self.ib.sleep(1.0)
            if not tickers:
                return None
            t0 = tickers[0]
            candidates = []
            if getattr(t0, 'bid', None) and getattr(t0, 'ask', None) and t0.bid > 0 and t0.ask > 0:
                candidates.append((t0.bid + t0.ask) / 2)
            if getattr(t0, 'last', None) and t0.last and t0.last > 0:
                candidates.append(t0.last)
            if getattr(t0, 'close', None) and t0.close and t0.close > 0:
                candidates.append(t0.close)
            price = next((p for p in candidates if p and p > 0), None)
            if price:
                price = float(price)
                print(f"{ticker} real-time price: ${price:.2f}")
                return price
            return None
        except Exception as e:
            print(f"ERROR: getting price for {ticker}: {e}")
            # Fallback
            try:
                import yfinance as yf
                df = yf.Ticker(ticker).history(period='1d')
                if not df.empty:
                    close_price = float(df['Close'].iloc[-1])
                    print(f"{ticker} fallback close price: ${close_price:.2f}")
                    return close_price
            except Exception:
                pass
            return None

    def place_order(self, order: Dict, execute: bool = False) -> bool:
        try:
            ticker = order['ticker']
            action = order['action']
            shares = order['shares']
            current_pos = self.portfolio_manager.get_position(ticker)
            closing = (action == 'SELL' and current_pos > 0) or (action == 'COVER' and current_pos < 0)
            real_price = None
            limit_price = None
            if not closing:
                real_price = self.get_realtime_price(ticker)
                if not real_price:
                    print(f"Cannot obtain price for opening order {action} {ticker}")
                    return False
                if action in ['BUY', 'COVER']:
                    limit_price = real_price + LIMIT_ORDER_OFFSET
                else:
                    limit_price = real_price - LIMIT_ORDER_OFFSET
            commission = max(MIN_COMMISSION, shares * (real_price or 0) * DEFAULT_COMMISSION_RATE)
            print("\nORDER DETAILS:")
            print(f"Ticker: {ticker}")
            print(f"Action: {action}")
            print(f"Shares: {shares:,}")
            if real_price:
                print(f"Real-time Price: ${real_price:.2f}")
                print(f"Limit Price: ${limit_price:.2f} (offset {LIMIT_ORDER_OFFSET})")
            else:
                print("Real-time Price: N/A (market close fallback)")
            print(f"Est. Commission: ${commission:.2f}")
            print(f"Description: {order['description']}")
            valid, msg = self.portfolio_manager.validate_order({**order, 'price': real_price})
            if not valid:
                print(f"ERROR: Order validation failed: {msg}")
                return False
            print(f"OK: Order validation: {msg}")
            if not execute:
                print("DRY RUN - Order not executed (use --execute to place)")
                return True
            contract = Stock(ticker, 'SMART', 'USD')
            self.ib.qualifyContracts(contract)
            if limit_price is not None:
                ib_order = LimitOrder(action, shares, limit_price)
            else:
                ib_order = MarketOrder(action, shares)
            trade = self.ib.placeOrder(contract, ib_order)
            print(f"ORDER PLACED: {action} {shares:,} {ticker} @ {('%.2f' % limit_price) if limit_price else 'MKT'}")
            print(f"Order ID: {trade.order.orderId if hasattr(trade, 'order') else 'N/A'}")
            self.portfolio_manager.update_position(ticker, shares, action)
            return True
        except Exception as e:
            print(f"ERROR: placing order failed: {e}")
            return False
    
    def check_trading_time(self, trade_on: str = None) -> Tuple[bool, str]:
        """Check if it's appropriate trading time using config parameters"""
        now = datetime.now()
        current_time = now.time()
        
        # Parse config times and add delays/advance
        market_open = datetime.strptime(MARKET_OPEN_TIME, "%H:%M").time()
        market_close = datetime.strptime(MARKET_CLOSE_TIME, "%H:%M").time()
        
        # Calculate trading windows using config parameters
        open_start_minutes = market_open.hour * 60 + market_open.minute + OPEN_TRADE_DELAY
        open_start = time(open_start_minutes // 60, open_start_minutes % 60)
        open_end = time(12, 0)  # Noon cutoff for open trades
        
        close_start_minutes = market_close.hour * 60 + market_close.minute - CLOSE_TRADE_ADVANCE
        close_start = time(close_start_minutes // 60, close_start_minutes % 60)
        close_end = market_close
        
        if trade_on == "OPEN":
            if current_time >= open_start and current_time < open_end:
                return True, f"OPEN trading window is active ({open_start.strftime('%H:%M')}-{open_end.strftime('%H:%M')} ET)"
            else:
                return False, f"OPEN trading window is {open_start.strftime('%H:%M')}-{open_end.strftime('%H:%M')} ET (current: {current_time.strftime('%H:%M')})"
        
        elif trade_on == "CLOSE":
            if current_time >= close_start and current_time < close_end:
                return True, f"CLOSE trading window is active ({close_start.strftime('%H:%M')}-{close_end.strftime('%H:%M')} ET)"
            else:
                return False, f"CLOSE trading window is {close_start.strftime('%H:%M')}-{close_end.strftime('%H:%M')} ET (current: {current_time.strftime('%H:%M')})"
        
        else:
            # Check both windows
            if (current_time >= open_start and current_time < open_end):
                return True, f"OPEN trading window is active ({open_start.strftime('%H:%M')}-{open_end.strftime('%H:%M')} ET)"
            elif (current_time >= close_start and current_time < close_end):
                return True, f"CLOSE trading window is active ({close_start.strftime('%H:%M')}-{close_end.strftime('%H:%M')} ET)"
            else:
                return False, f"Outside trading windows ({open_start.strftime('%H:%M')}-{open_end.strftime('%H:%M')} or {close_start.strftime('%H:%M')}-{close_end.strftime('%H:%M')} ET)"

def main():
    """Main execution function (synchronous)"""
    parser = argparse.ArgumentParser(description='Manual Paper Trading Execution')
    parser.add_argument('--execute', action='store_true', 
                       help='Actually place orders (default is dry run)')
    parser.add_argument('--trade-on', choices=['OPEN', 'CLOSE'],
                       help='Filter by trade timing')
    parser.add_argument('--force', action='store_true',
                       help='Force execution outside trading windows')
    parser.add_argument('--yes', action='store_true',
                       help='Auto-confirm order execution (non-interactive)')
    
    args = parser.parse_args()
    
    print("MANUAL PAPER TRADING EXECUTION")
    print("="*50)
    
    # Check trading time
    trader = ManualTrader(paper_trading=True)
    can_trade, time_msg = trader.check_trading_time(args.trade_on)
    
    print(f"Trading Time Check: {time_msg}")
    
    if not can_trade and not args.force:
        print(f"Not in trading window. Use --force to override.")
        return
    
    # Get today's signals
    print(f"\nChecking today's signals...")
    signals = check_todays_signals(args.trade_on)
    
    if not signals:
        print(f"No signals found for today")
        return
    
    # Connect to IB
    print(f"\nConnecting to Interactive Brokers...")
    if not trader.connect_ib():
        return
    
    try:
        # Show current portfolio
        trader.portfolio_manager.print_portfolio_summary()

        # Enrich signals with prices for new positions
        print("\nFetching real-time prices for signals...")
        new_signals = []
        for s in signals:
            s2 = dict(s)
            if s2.get('price') is None and s2.get('action') in ('BUY','SHORT'):
                p = trader.get_realtime_price(s2['ticker'])
                if p is not None:
                    s2['price'] = p
            new_signals.append(s2)
        signals = new_signals

        # Fallback: ensure we have COVER signals for any open shorts if previous day's cover missed
        try:
            from datetime import datetime, timedelta
            today_str = datetime.now().strftime('%Y-%m-%d')
            yday_str = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            with open('complete_comprehensive_backtest_results.json','r') as f:
                bt = json.load(f)
            tickers_with_signals = {s['ticker'] for s in signals}
            added = 0
            for tkr, pos in trader.portfolio_manager.positions.items():
                if pos < 0 and tkr not in tickers_with_signals:
                    # look for latest COVER in backtest
                    short_data = bt.get(tkr,{}).get('short_strategy',{}).get('extended_signals',[])
                    latest_cover = None
                    for sig in reversed(short_data):
                        if sig.get('action') == 'COVER':
                            latest_cover = sig
                            break
                    if latest_cover and latest_cover.get('date') == yday_str:
                        signals.append({
                            'ticker': tkr,
                            'strategy': 'SHORT',
                            'date': today_str,
                            'action': 'COVER',
                            'price': None,
                            'signal_type': 'stale_cover_recovery',
                            'p_param': latest_cover.get('p_param'),
                            'tw_param': latest_cover.get('tw_param'),
                            'trade_on': 'CLOSE'
                        })
                        added += 1
            if added:
                print(f"Added {added} stale COVER recovery signal(s) for open shorts")
        except Exception:
            pass

        # Create combined orders
        print(f"\nCreating combined orders...")
        orders = trader.portfolio_manager.create_combined_orders(signals)

        if not orders:
            print(f"No orders to execute")
            return

        print(f"\nORDERS TO EXECUTE:")
        print("="*40)

        # Show all orders first
        for i, order in enumerate(orders, 1):
            print(f"\n{i}. {order['ticker']} - {order['description']}")
            print(f"   Action: {order['action']} {order['shares']:,} shares")
            print(f"   Timing: {order['trade_on']} trades")

        # Execute orders
        if args.execute and not args.yes:
            print(f"\nEXECUTING ORDERS...")
            confirm = input(f"\nExecute {len(orders)} orders? (y/n): ")
            if confirm.lower() != 'y':
                print("Execution cancelled")
                return

        successful = 0
        for i, order in enumerate(orders, 1):
            print(f"\n--- ORDER {i}/{len(orders)} ---")
            success = trader.place_order(order, args.execute)
            if success:
                successful += 1
            if i < len(orders):
                trader.ib.sleep(1.5)

        print(f"\nEXECUTION SUMMARY:")
        print(f"Successful: {successful}/{len(orders)}")
        print(f"{'Orders executed!' if args.execute else 'Dry run completed'}")

    finally:
        if trader.ib:
            trader.ib.disconnect()
            print(f"\nDisconnected from IB")

if __name__ == "__main__":
    main()
