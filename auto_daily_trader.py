#!/usr/bin/env python3
"""
Automated Daily Trading Script
Runs continuously, executing trades at the appropriate times each trading day.

Features:
- Can be started at any time of day
- Waits for NY market open + 5 minutes for OPEN trades
- Waits for NY market close - 5 minutes for CLOSE trades
- Runs fresh backtest before each trading session
- Skips weekends and holidays
- Continues until CTRL+C

Usage:
python auto_daily_trader.py [--paper-trading] [--dry-run]
"""

import asyncio
import sys
import os
import signal
from datetime import datetime, time, timedelta
from typing import Optional, Tuple
import logging
from ib_insync import *
import json

# Import our modules
from config import *
from check_todays_signals import check_todays_signals, TICKERS_CONFIG
from portfolio_manager import PortfolioManager
from manual_trading import ManualTrader
import subprocess

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('auto_trader.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AutoDailyTrader:
    def __init__(self, paper_trading=True, dry_run=False):
        """Initialize the automated daily trader"""
        self.paper_trading = paper_trading
        self.dry_run = dry_run
        self.running = True
        self.manual_trader = ManualTrader(paper_trading)
        self.portfolio_manager = PortfolioManager()
        
        # Trading windows (will be calculated from config)
        self.open_trading_time = None
        self.close_trading_time = None
        self.market_close_time = None
        self.calculate_trading_times()
        
        # Track what we've done today
        self.today_open_executed = False
        self.today_close_executed = False
        self.current_date = None
        
        # Setup signal handler for CTRL+C
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def signal_handler(self, signum, frame):
        """Handle CTRL+C gracefully"""
        logger.info("🛑 Received shutdown signal (CTRL+C)")
        self.running = False

    def calculate_trading_times(self):
        """Calculate trading times from config parameters"""
        try:
            # Parse market times
            market_open = datetime.strptime(MARKET_OPEN_TIME, "%H:%M").time()
            market_close = datetime.strptime(MARKET_CLOSE_TIME, "%H:%M").time()
            
            # Calculate OPEN trading time (5 minutes after market open)
            open_minutes = market_open.hour * 60 + market_open.minute + 5  # 5 min after open
            self.open_trading_time = time(open_minutes // 60, open_minutes % 60)
            
            # Calculate CLOSE trading time (5 minutes before market close)  
            close_minutes = market_close.hour * 60 + market_close.minute - 5  # 5 min before close
            self.close_trading_time = time(close_minutes // 60, close_minutes % 60)
            
            self.market_close_time = market_close
            
            logger.info(f"🕐 Trading Schedule:")
            logger.info(f"   Market Open: {MARKET_OPEN_TIME}")
            logger.info(f"   OPEN Trades: {self.open_trading_time.strftime('%H:%M')} (5 min after open)")
            logger.info(f"   CLOSE Trades: {self.close_trading_time.strftime('%H:%M')} (5 min before close)")
            logger.info(f"   Market Close: {MARKET_CLOSE_TIME}")
            
        except Exception as e:
            logger.error(f"Error calculating trading times: {e}")
            # Fallback to defaults
            self.open_trading_time = time(9, 35)   # 9:35 AM
            self.close_trading_time = time(15, 55)  # 3:55 PM
            self.market_close_time = time(16, 0)   # 4:00 PM

    def is_trading_day(self, check_date: datetime) -> bool:
        """Check if the given date is a trading day (not weekend/holiday)"""
        # Skip weekends
        if check_date.weekday() in [5, 6]:  # Saturday = 5, Sunday = 6
            return False
        
        # Basic US market holidays (you can expand this list)
        us_holidays_2025 = [
            # New Year's Day
            datetime(2025, 1, 1).date(),
            # Martin Luther King Jr. Day (3rd Monday in January)
            datetime(2025, 1, 20).date(),
            # Presidents' Day (3rd Monday in February)
            datetime(2025, 2, 17).date(),
            # Good Friday (varies each year)
            datetime(2025, 4, 18).date(),
            # Memorial Day (last Monday in May)
            datetime(2025, 5, 26).date(),
            # Juneteenth
            datetime(2025, 6, 19).date(),
            # Independence Day
            datetime(2025, 7, 4).date(),
            # Labor Day (1st Monday in September)
            datetime(2025, 9, 1).date(),
            # Thanksgiving Day (4th Thursday in November)
            datetime(2025, 11, 27).date(),
            # Christmas Day
            datetime(2025, 12, 25).date(),
        ]
        
        return check_date.date() not in us_holidays_2025

    def get_next_trading_session(self) -> Tuple[datetime, str]:
        """Get the next trading session (OPEN or CLOSE) and its datetime"""
        now = datetime.now()
        current_time = now.time()
        current_date = now.date()
        
        # Check if today is a trading day
        if self.is_trading_day(now):
            # Check for today's sessions
            if not self.today_open_executed and current_time < self.open_trading_time:
                # Next session is today's OPEN
                next_session = datetime.combine(current_date, self.open_trading_time)
                return next_session, "OPEN"
            
            elif not self.today_close_executed and current_time < self.close_trading_time:
                # Next session is today's CLOSE
                next_session = datetime.combine(current_date, self.close_trading_time)
                return next_session, "CLOSE"
        
        # Need to find next trading day
        next_date = now + timedelta(days=1)
        while not self.is_trading_day(next_date):
            next_date += timedelta(days=1)
        
        # Reset daily flags for new day
        if next_date.date() != current_date:
            self.today_open_executed = False
            self.today_close_executed = False
            self.current_date = next_date.date()
        
        # Next session is OPEN of next trading day
        next_session = datetime.combine(next_date.date(), self.open_trading_time)
        return next_session, "OPEN"

    def run_fresh_backtest(self) -> bool:
        """Run a fresh backtest to get latest signals"""
        logger.info("🔄 Running fresh backtest to get latest signals...")
        try:
            # Run the comprehensive backtest
            result = subprocess.run([
                sys.executable, 
                'complete_comprehensive_backtest.py'
            ], capture_output=True, text=True, timeout=300)  # 5 minute timeout
            
            if result.returncode == 0:
                logger.info("✅ Backtest completed successfully")
                return True
            else:
                logger.error(f"❌ Backtest failed: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("❌ Backtest timed out after 5 minutes")
            return False
        except Exception as e:
            logger.error(f"❌ Error running backtest: {e}")
            return False

    async def execute_trading_session(self, session_type: str) -> bool:
        """Execute a trading session (OPEN or CLOSE)"""
        logger.info(f"🚀 Starting {session_type} trading session")
        
        try:
            # Run fresh backtest first
            if not self.run_fresh_backtest():
                logger.error(f"❌ Skipping {session_type} session due to backtest failure")
                return False
            
            # Check for today's signals for this session
            logger.info(f"🔍 Checking for {session_type} signals...")
            signals = check_todays_signals(session_type)
            
            if not signals:
                logger.info(f"📭 No {session_type} signals found for today")
                return True
            
            logger.info(f"📊 Found {len(signals)} {session_type} signals")
            
            # Connect to IB
            if not await self.manual_trader.connect_ib():
                logger.error(f"❌ Failed to connect to IB for {session_type} session")
                return False
            
            try:
                # Update portfolio positions
                await self.manual_trader.sync_portfolio_with_ib()
                
                # Create combined orders
                orders = self.manual_trader.portfolio_manager.create_combined_orders(signals)
                
                if not orders:
                    logger.info(f"📭 No executable orders for {session_type} session")
                    return True
                
                logger.info(f"📈 Executing {len(orders)} {session_type} orders...")
                
                # Execute each order
                successful_orders = 0
                for i, order in enumerate(orders, 1):
                    logger.info(f"📋 Processing order {i}/{len(orders)}: {order['ticker']} {order['action']}")
                    
                    if await self.manual_trader.place_order(order, not self.dry_run):
                        successful_orders += 1
                    
                    # Wait between orders
                    if i < len(orders):
                        await asyncio.sleep(2)
                
                logger.info(f"✅ {session_type} session completed: {successful_orders}/{len(orders)} orders successful")
                
                # Log session summary
                session_summary = {
                    'timestamp': datetime.now().isoformat(),
                    'session_type': session_type,
                    'signals_found': len(signals),
                    'orders_executed': len(orders),
                    'successful_orders': successful_orders,
                    'dry_run': self.dry_run
                }
                
                # Save session log
                log_file = f'trading_sessions_{datetime.now().strftime("%Y%m%d")}.json'
                if os.path.exists(log_file):
                    with open(log_file, 'r') as f:
                        sessions = json.load(f)
                else:
                    sessions = []
                
                sessions.append(session_summary)
                with open(log_file, 'w') as f:
                    json.dump(sessions, f, indent=2)
                
                return True
                
            finally:
                # Always disconnect from IB
                if self.manual_trader.ib:
                    self.manual_trader.ib.disconnect()
                    logger.info("🔌 Disconnected from IB")
        
        except Exception as e:
            logger.error(f"❌ Error in {session_type} trading session: {e}")
            return False

    async def wait_for_next_session(self, next_session: datetime, session_type: str):
        """Wait for the next trading session with status updates"""
        now = datetime.now()
        wait_seconds = (next_session - now).total_seconds()
        
        if wait_seconds <= 0:
            return  # Already time for the session
        
        logger.info(f"⏳ Waiting for {session_type} session at {next_session.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"   Time until session: {wait_seconds/3600:.1f} hours")
        
        # Wait with periodic status updates
        update_interval = min(300, wait_seconds / 10)  # Update every 5 minutes or 1/10 of wait time
        
        while wait_seconds > 0 and self.running:
            sleep_time = min(update_interval, wait_seconds)
            await asyncio.sleep(sleep_time)
            wait_seconds -= sleep_time
            
            if wait_seconds > 60 and self.running:
                logger.info(f"⏱️  {wait_seconds/60:.0f} minutes until {session_type} session...")

    async def run_daily_cycle(self):
        """Run the main daily trading cycle"""
        logger.info("🚀 AUTOMATED DAILY TRADER STARTED")
        logger.info(f"📊 Paper Trading: {'ON' if self.paper_trading else 'OFF'}")
        logger.info(f"🔍 Dry Run: {'ON' if self.dry_run else 'OFF'}")
        
        # Initialize current date tracking
        self.current_date = datetime.now().date()
        
        while self.running:
            try:
                # Get next trading session
                next_session, session_type = self.get_next_trading_session()
                
                # Check if we moved to a new day
                if next_session.date() != self.current_date:
                    logger.info(f"📅 New trading day: {next_session.date().strftime('%Y-%m-%d')}")
                    self.current_date = next_session.date()
                    self.today_open_executed = False
                    self.today_close_executed = False
                
                # Wait for the next session
                await self.wait_for_next_session(next_session, session_type)
                
                if not self.running:
                    break
                
                # Execute the trading session
                success = await self.execute_trading_session(session_type)
                
                # Mark this session as completed
                if session_type == "OPEN":
                    self.today_open_executed = True
                elif session_type == "CLOSE":
                    self.today_close_executed = True
                
                if not success:
                    logger.warning(f"⚠️  {session_type} session had issues, but continuing...")
                
                # Brief pause before checking for next session
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"❌ Error in daily cycle: {e}")
                logger.info("🔄 Continuing after error...")
                await asyncio.sleep(60)
        
        logger.info("🛑 Automated daily trader stopped")

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Automated Daily Trading Script')
    parser.add_argument('--live-trading', action='store_true',
                       help='Use live trading account (default: paper trading)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Dry run mode - no actual orders placed')
    
    args = parser.parse_args()
    
    paper_trading = not args.live_trading
    
    print("🎯 AUTOMATED DAILY TRADER")
    print("="*50)
    print(f"📊 Mode: {'Paper Trading' if paper_trading else 'LIVE TRADING'}")
    print(f"🔍 Dry Run: {'YES' if args.dry_run else 'NO'}")
    print(f"💰 Capital: ${INITIAL_CAPITAL:,.2f}")
    print(f"📈 Tickers: {len(TICKERS_CONFIG)}")
    print("\n⚠️  This script will run continuously until CTRL+C")
    print("   It will execute trades automatically at market open/close times")
    
    if not paper_trading:
        confirm = input("\n🚨 LIVE TRADING MODE - Are you sure? (type 'YES' to continue): ")
        if confirm != 'YES':
            print("❌ Cancelled")
            return
    
    if not args.dry_run:
        confirm = input(f"\n▶️  Start automated {'paper' if paper_trading else 'LIVE'} trading? (y/n): ")
        if confirm.lower() != 'y':
            print("❌ Cancelled")
            return
    
    # Create and run the trader
    trader = AutoDailyTrader(paper_trading=paper_trading, dry_run=args.dry_run)
    
    try:
        asyncio.run(trader.run_daily_cycle())
    except KeyboardInterrupt:
        print("\n🛑 Stopped by user (CTRL+C)")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        logger.error(f"Fatal error: {e}")

if __name__ == "__main__":
    main()
