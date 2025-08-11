#!/usr/bin/env python3
"""
Live Trading Manager for Support/Resistance Strategy
Handles paper trading execution with Interactive Brokers

Key Features:
- Timing-based execution (10 min after open, 15 min before close)
- Portfolio position management for complex orders
- Real-time IB price integration
- Signal validation before trade execution
"""

import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta
from ib_insync import *
import json
import sys
import os
from typing import Dict, List, Tuple, Optional
import logging

# Import our modules
from tickers_config import TICKERS_CONFIG
from config import *
import backtesting_core
import signal_utils

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LiveTradingManager:
    def __init__(self, paper_trading=True):
        """Initialize the live trading manager"""
        self.paper_trading = paper_trading
        self.ib = None
        self.portfolio = {}  # Current positions
        self.capital_allocation = {}  # Capital per ticker
        self.market_data = {}  # Real-time market data
        
        # Trading times (Eastern Time)
        self.market_open = time(9, 30)  # 9:30 AM ET
        self.open_trade_time = time(9, 40)  # 10 minutes after open
        self.market_close = time(16, 0)  # 4:00 PM ET
        self.close_trade_time = time(15, 45)  # 15 minutes before close
        
        # Initialize capital allocation from config
        self.init_capital_allocation()
        
    def init_capital_allocation(self):
        """Initialize capital allocation per ticker"""
        total_tickers = len(TICKERS_CONFIG)
        capital_per_ticker = INITIAL_CAPITAL / total_tickers
        
        for ticker in TICKERS_CONFIG:
            self.capital_allocation[ticker] = capital_per_ticker
            logger.info(f"Allocated ${capital_per_ticker:,.2f} to {ticker}")

    async def connect_ib(self):
        """Connect to Interactive Brokers"""
        try:
            self.ib = IB()
            port = 7497 if self.paper_trading else 7496
            await self.ib.connectAsync('127.0.0.1', port, clientId=1)
            logger.info(f"Connected to IB {'Paper' if self.paper_trading else 'Live'} Trading")
            
            # Get current portfolio positions
            await self.update_portfolio()
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to IB: {e}")
            return False

    async def update_portfolio(self):
        """Update current portfolio positions"""
        try:
            positions = self.ib.positions()
            self.portfolio = {}
            
            for pos in positions:
                ticker = pos.contract.symbol
                shares = int(pos.position)
                if shares != 0:
                    self.portfolio[ticker] = shares
                    logger.info(f"Current position: {ticker} = {shares} shares")
                    
        except Exception as e:
            logger.error(f"Error updating portfolio: {e}")

    async def get_realtime_price(self, ticker: str) -> Optional[float]:
        """Get real-time market price from IB"""
        try:
            contract = Stock(ticker, 'SMART', 'USD')
            self.ib.qualifyContracts(contract)
            
            # Request market data
            ticker_data = self.ib.reqMktData(contract, '', False, False)
            await asyncio.sleep(1)  # Wait for data
            
            # Get bid/ask midpoint
            if ticker_data.bid and ticker_data.ask:
                price = (ticker_data.bid + ticker_data.ask) / 2
                self.market_data[ticker] = price
                logger.info(f"{ticker} real-time price: ${price:.2f}")
                return price
            else:
                logger.warning(f"No market data available for {ticker}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting price for {ticker}: {e}")
            return None

    def check_trading_time(self) -> Tuple[bool, str]:
        """Check if it's time to trade and return trade type"""
        now = datetime.now().time()
        
        # Check if it's time for OPEN trades (10 minutes after market open)
        if now >= self.open_trade_time and now < time(12, 0):  # Morning window
            return True, "OPEN"
            
        # Check if it's time for CLOSE trades (15 minutes before market close)
        elif now >= self.close_trade_time and now < self.market_close:
            return True, "CLOSE"
            
        else:
            return False, "NONE"

    def generate_today_signals(self, trade_on: str) -> List[Dict]:
        """Generate signals for today using backtesting system"""
        try:
            logger.info(f"Generating signals for {trade_on} trades...")
            
            # Run backtesting to get signals for today
            today_str = datetime.now().strftime('%Y-%m-%d')
            
            # Load the backtest results
            results_file = 'complete_comprehensive_backtest_results.json'
            if not os.path.exists(results_file):
                logger.error("No backtest results found. Run complete_comprehensive_backtest.py first")
                return []
                
            with open(results_file, 'r') as f:
                backtest_data = json.load(f)
            
            today_signals = []
            
            for ticker, ticker_data in backtest_data.items():
                if ticker not in TICKERS_CONFIG:
                    continue
                    
                ticker_config = TICKERS_CONFIG[ticker]
                if ticker_config['trade_on'] != trade_on:
                    continue  # Skip if not trading on this timing
                
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
                            today_signals.append({
                                'ticker': ticker,
                                'strategy': strategy,
                                'action': signal.get('action'),
                                'price': signal.get('price'),
                                'signal_type': signal.get('signal_type'),
                                'trade_on': trade_on
                            })
            
            logger.info(f"Found {len(today_signals)} signals for {trade_on} trades")
            return today_signals
            
        except Exception as e:
            logger.error(f"Error generating signals: {e}")
            return []

    def calculate_shares(self, ticker: str, strategy: str, action: str, price: float) -> int:
        """Calculate number of shares based on capital allocation and current positions"""
        try:
            capital = self.capital_allocation[ticker]
            current_position = self.portfolio.get(ticker, 0)
            
            if strategy == "LONG":
                if action == "BUY":
                    # Calculate shares based on available capital
                    shares = int(capital / price)
                elif action == "SELL":
                    # Sell all long positions
                    shares = max(0, current_position)  # Only positive positions
            
            elif strategy == "SHORT":
                if action == "SHORT":
                    # Calculate shares to short based on capital
                    shares = int(capital / price)
                elif action == "COVER":
                    # Cover all short positions
                    shares = abs(min(0, current_position))  # Only negative positions
            
            logger.info(f"{ticker} {strategy} {action}: {shares} shares at ${price:.2f}")
            return shares
            
        except Exception as e:
            logger.error(f"Error calculating shares for {ticker}: {e}")
            return 0

    def combine_orders(self, signals: List[Dict]) -> List[Dict]:
        """Combine BUY+COVER and SELL+SHORT orders per your requirements"""
        combined_orders = []
        ticker_actions = {}
        
        # Group signals by ticker
        for signal in signals:
            ticker = signal['ticker']
            if ticker not in ticker_actions:
                ticker_actions[ticker] = []
            ticker_actions[ticker].append(signal)
        
        for ticker, actions in ticker_actions.items():
            buy_signals = [s for s in actions if s['action'] == 'BUY']
            cover_signals = [s for s in actions if s['action'] == 'COVER']
            sell_signals = [s for s in actions if s['action'] == 'SELL']
            short_signals = [s for s in actions if s['action'] == 'SHORT']
            
            current_position = self.portfolio.get(ticker, 0)
            
            # Handle BUY + COVER combinations
            if buy_signals and cover_signals:
                buy_signal = buy_signals[0]
                cover_signal = cover_signals[0]
                
                # First limit COVER to existing short position
                max_cover = abs(min(0, current_position))
                cover_shares = min(cover_signal.get('shares', max_cover), max_cover)
                
                # Calculate BUY shares
                buy_shares = self.calculate_shares(ticker, 'LONG', 'BUY', buy_signal['price'])
                
                # Create combined BUY order (net position)
                total_buy_shares = buy_shares + cover_shares
                
                combined_orders.append({
                    'ticker': ticker,
                    'action': 'BUY',
                    'shares': total_buy_shares,
                    'price': buy_signal['price'],  # Use real-time price
                    'trade_on': buy_signal['trade_on'],
                    'combined': f"BUY {buy_shares} + COVER {cover_shares}"
                })
            
            # Handle SELL + SHORT combinations
            elif sell_signals and short_signals:
                sell_signal = sell_signals[0]
                short_signal = short_signals[0]
                
                # Get long position to sell
                max_sell = max(0, current_position)
                sell_shares = min(sell_signal.get('shares', max_sell), max_sell)
                
                # Calculate SHORT shares
                short_shares = self.calculate_shares(ticker, 'SHORT', 'SHORT', short_signal['price'])
                
                # Create combined SELL order (net position)
                total_sell_shares = sell_shares + short_shares
                
                combined_orders.append({
                    'ticker': ticker,
                    'action': 'SELL',
                    'shares': total_sell_shares,
                    'price': sell_signal['price'],  # Use real-time price
                    'trade_on': sell_signal['trade_on'],
                    'combined': f"SELL {sell_shares} + SHORT {short_shares}"
                })
            
            # Handle individual orders
            else:
                for signal in actions:
                    shares = self.calculate_shares(ticker, 
                                                 'LONG' if signal['action'] in ['BUY', 'SELL'] else 'SHORT',
                                                 signal['action'], 
                                                 signal['price'])
                    if shares > 0:
                        combined_orders.append({
                            'ticker': signal['ticker'],
                            'action': signal['action'],
                            'shares': shares,
                            'price': signal['price'],
                            'trade_on': signal['trade_on'],
                            'combined': 'Individual'
                        })
        
        return combined_orders

    async def place_order(self, order: Dict) -> bool:
        """Place order with Interactive Brokers"""
        try:
            ticker = order['ticker']
            action = order['action']
            shares = order['shares']
            
            # Get real-time price at execution
            real_price = await self.get_realtime_price(ticker)
            if not real_price:
                logger.error(f"Cannot get real-time price for {ticker}")
                return False
            
            # Create contract
            contract = Stock(ticker, 'SMART', 'USD')
            self.ib.qualifyContracts(contract)
            
            # Create order
            ib_order = LimitOrder(action, shares, real_price)
            
            # Place order
            trade = self.ib.placeOrder(contract, ib_order)
            
            logger.info(f"✅ Order placed: {action} {shares} {ticker} @ ${real_price:.2f}")
            logger.info(f"   Combined: {order.get('combined', 'Individual')}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error placing order for {order['ticker']}: {e}")
            return False

    async def execute_trading_session(self):
        """Main trading execution loop"""
        logger.info("🚀 Starting Live Trading Session")
        
        # Connect to IB
        if not await self.connect_ib():
            return
        
        try:
            while True:
                # Check if it's trading time
                should_trade, trade_type = self.check_trading_time()
                
                if should_trade:
                    logger.info(f"⏰ Trading time for {trade_type} trades!")
                    
                    # Generate today's signals
                    signals = self.generate_today_signals(trade_type)
                    
                    if not signals:
                        logger.info("📋 No signals found for today")
                    else:
                        # Update portfolio positions
                        await self.update_portfolio()
                        
                        # Combine orders according to your requirements
                        orders = self.combine_orders(signals)
                        
                        if orders:
                            logger.info(f"📊 Executing {len(orders)} orders:")
                            
                            # Execute orders
                            for order in orders:
                                await self.place_order(order)
                                await asyncio.sleep(2)  # Wait between orders
                        
                        # Wait until next trading session
                        if trade_type == "OPEN":
                            logger.info("✅ OPEN trades completed. Waiting for CLOSE session...")
                            await asyncio.sleep(3600)  # Wait 1 hour
                        else:
                            logger.info("✅ CLOSE trades completed. Session finished.")
                            break
                else:
                    # Wait and check again
                    await asyncio.sleep(60)  # Check every minute
                    
        except KeyboardInterrupt:
            logger.info("Trading session interrupted by user")
        except Exception as e:
            logger.error(f"Error in trading session: {e}")
        finally:
            if self.ib:
                self.ib.disconnect()
                logger.info("Disconnected from IB")

def print_trading_status():
    """Print current trading status and schedule"""
    now = datetime.now()
    print(f"\n🕐 Current Time: {now.strftime('%H:%M:%S ET')}")
    print(f"📅 Date: {now.strftime('%Y-%m-%d')}")
    
    print(f"\n📊 TRADING SCHEDULE:")
    print(f"   🌅 Market Open: 09:30 ET")
    print(f"   🔹 OPEN Trades: 09:40 ET (10 min after open)")
    print(f"   🔸 CLOSE Trades: 15:45 ET (15 min before close)")
    print(f"   🌙 Market Close: 16:00 ET")
    
    # Check current status
    current_time = now.time()
    if current_time < time(9, 40):
        print(f"   ⏳ Waiting for OPEN trading session...")
    elif current_time < time(15, 45):
        print(f"   ✅ OPEN session completed, waiting for CLOSE session...")
    elif current_time < time(16, 0):
        print(f"   🔥 CLOSE trading session active!")
    else:
        print(f"   😴 Market closed, waiting for next day...")

async def main():
    """Main entry point"""
    print("🎯 LIVE TRADING MANAGER - Support/Resistance Strategy")
    print("="*60)
    
    print_trading_status()
    
    # Check if backtest data exists
    if not os.path.exists('complete_comprehensive_backtest_results.json'):
        print("\n❌ No backtest results found!")
        print("   Run: python complete_comprehensive_backtest.py")
        return
    
    # Initialize trading manager
    manager = LiveTradingManager(paper_trading=True)
    
    print(f"\n🎮 Paper Trading Mode: {'ON' if manager.paper_trading else 'OFF'}")
    print(f"💰 Total Capital: ${INITIAL_CAPITAL:,.2f}")
    print(f"📊 Tickers: {list(TICKERS_CONFIG.keys())}")
    
    # Wait for user confirmation
    response = input("\n▶️  Start live trading session? (y/n): ")
    if response.lower() != 'y':
        print("Trading session cancelled.")
        return
    
    # Start trading
    await manager.execute_trading_session()

if __name__ == "__main__":
    asyncio.run(main())
