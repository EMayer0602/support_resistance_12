#!/usr/bin/env python3
"""
Simple Auto Trader - Start Anytime
Lightweight version for easy testing and monitoring

Usage:
python simple_auto_trader.py [--dry-run] [--test-mode]

Test mode: Uses 1-minute intervals for quick testing
"""

import asyncio
import sys
from datetime import datetime, time, timedelta
import signal
import logging
from config import *

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

class SimpleAutoTrader:
    def __init__(self, dry_run=False, test_mode=False):
        self.dry_run = dry_run
        self.test_mode = test_mode
        self.running = True
        
        # Setup signal handler for CTRL+C
        signal.signal(signal.SIGINT, self.signal_handler)
        
        # Calculate trading times
        if test_mode:
            # For testing: use current time + small intervals
            now = datetime.now()
            self.open_time = (now + timedelta(minutes=1)).time()
            self.close_time = (now + timedelta(minutes=3)).time()
        else:
            # Real times: 5 minutes after open, 5 minutes before close
            market_open = datetime.strptime(MARKET_OPEN_TIME, "%H:%M")
            market_close = datetime.strptime(MARKET_CLOSE_TIME, "%H:%M")
            
            open_plus_5 = market_open + timedelta(minutes=5)
            close_minus_5 = market_close - timedelta(minutes=5)
            
            self.open_time = open_plus_5.time()
            self.close_time = close_minus_5.time()
        
        logger.info(f"🕐 OPEN trades at: {self.open_time.strftime('%H:%M')}")
        logger.info(f"🕐 CLOSE trades at: {self.close_time.strftime('%H:%M')}")

    def signal_handler(self, signum, frame):
        """Handle CTRL+C"""
        logger.info("🛑 Stopping trader...")
        self.running = False

    def is_trading_day(self):
        """Check if today is a trading day"""
        today = datetime.now()
        if today.weekday() in [5, 6]:  # Weekend
            return False
        return True

    async def run_backtest_and_check_signals(self, session_type):
        """Run backtest and check for signals"""
        logger.info(f"🔄 Running backtest for {session_type} session...")
        
        if self.dry_run:
            logger.info("🔍 DRY RUN: Would run backtest and check signals")
            return ["fake_signal_1", "fake_signal_2"] if session_type == "OPEN" else []
        
        try:
            # Import and run signal checker
            from check_todays_signals import check_todays_signals
            signals = check_todays_signals(session_type)
            logger.info(f"📊 Found {len(signals)} {session_type} signals")
            return signals
        except Exception as e:
            logger.error(f"❌ Error checking signals: {e}")
            return []

    async def execute_trades(self, signals, session_type):
        """Execute the trading session"""
        if not signals:
            logger.info(f"📭 No {session_type} trades to execute")
            return
        
        logger.info(f"🚀 Executing {len(signals)} {session_type} trades...")
        
        if self.dry_run:
            logger.info("🔍 DRY RUN: Would execute trades via IB")
            for i, signal in enumerate(signals, 1):
                logger.info(f"   {i}. Would trade: {signal}")
                await asyncio.sleep(0.5)
        else:
            # Import and use manual trader
            from manual_trading import ManualTrader
            trader = ManualTrader(paper_trading=True)
            
            if await trader.connect_ib():
                try:
                    orders = trader.portfolio_manager.create_combined_orders(signals)
                    for order in orders:
                        await trader.place_order(order, execute=True)
                        await asyncio.sleep(2)
                finally:
                    if trader.ib:
                        trader.ib.disconnect()

    async def wait_until_time(self, target_time, session_name):
        """Wait until the target time"""
        while self.running:
            now = datetime.now()
            current_time = now.time()
            
            if current_time >= target_time:
                break
            
            # Calculate wait time
            today = now.date()
            target_datetime = datetime.combine(today, target_time)
            if target_datetime <= now:
                target_datetime += timedelta(days=1)
            
            wait_seconds = (target_datetime - now).total_seconds()
            
            if wait_seconds > 3600:  # More than 1 hour
                logger.info(f"⏳ {wait_seconds/3600:.1f} hours until {session_name} session")
                await asyncio.sleep(1800)  # Check every 30 minutes
            elif wait_seconds > 300:  # More than 5 minutes
                logger.info(f"⏳ {wait_seconds/60:.0f} minutes until {session_name} session")
                await asyncio.sleep(60)  # Check every minute
            else:
                logger.info(f"⏳ {wait_seconds:.0f} seconds until {session_name} session")
                await asyncio.sleep(min(wait_seconds, 10))

    async def run_daily_cycle(self):
        """Main daily cycle"""
        logger.info("🚀 Simple Auto Trader Started")
        logger.info(f"🔍 Dry Run: {'ON' if self.dry_run else 'OFF'}")
        logger.info(f"🧪 Test Mode: {'ON' if self.test_mode else 'OFF'}")
        
        daily_open_done = False
        daily_close_done = False
        
        while self.running:
            try:
                current_date = datetime.now().date()
                current_time = datetime.now().time()
                
                # Check if we're on a new day
                if not hasattr(self, 'last_date') or self.last_date != current_date:
                    logger.info(f"📅 New day: {current_date}")
                    daily_open_done = False
                    daily_close_done = False
                    self.last_date = current_date
                
                # Skip weekends
                if not self.is_trading_day():
                    logger.info("😴 Weekend - waiting for next trading day")
                    await asyncio.sleep(3600)  # Check every hour
                    continue
                
                # Handle OPEN session
                if not daily_open_done and current_time >= self.open_time:
                    logger.info("🌅 Starting OPEN trading session")
                    signals = await self.run_backtest_and_check_signals("OPEN")
                    await self.execute_trades(signals, "OPEN")
                    daily_open_done = True
                    logger.info("✅ OPEN session completed")
                
                # Handle CLOSE session
                elif not daily_close_done and current_time >= self.close_time:
                    logger.info("🌙 Starting CLOSE trading session")
                    signals = await self.run_backtest_and_check_signals("CLOSE")
                    await self.execute_trades(signals, "CLOSE")
                    daily_close_done = True
                    logger.info("✅ CLOSE session completed")
                
                # Wait for next session
                elif not daily_open_done:
                    await self.wait_until_time(self.open_time, "OPEN")
                elif not daily_close_done:
                    await self.wait_until_time(self.close_time, "CLOSE")
                else:
                    # Both sessions done, wait for next day
                    logger.info("😴 All sessions done for today, waiting for next day")
                    await asyncio.sleep(3600)  # Check every hour
                
            except Exception as e:
                logger.error(f"❌ Error in daily cycle: {e}")
                await asyncio.sleep(60)
        
        logger.info("🛑 Simple Auto Trader Stopped")

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Simple Auto Trader')
    parser.add_argument('--dry-run', action='store_true', help='Dry run mode')
    parser.add_argument('--test-mode', action='store_true', help='Test mode with 1-minute intervals')
    
    args = parser.parse_args()
    
    print("🎯 SIMPLE AUTO TRADER")
    print("="*30)
    print(f"🔍 Dry Run: {'YES' if args.dry_run else 'NO'}")
    print(f"🧪 Test Mode: {'YES' if args.test_mode else 'NO'}")
    
    if args.test_mode:
        print("\n⚠️  TEST MODE: Will use 1-minute intervals for quick testing")
    
    print("\n⚠️  Press CTRL+C to stop")
    
    if not args.dry_run and not args.test_mode:
        confirm = input("\n▶️  Start automated trading? (y/n): ")
        if confirm.lower() != 'y':
            return
    
    trader = SimpleAutoTrader(dry_run=args.dry_run, test_mode=args.test_mode)
    
    try:
        asyncio.run(trader.run_daily_cycle())
    except KeyboardInterrupt:
        print("\n🛑 Stopped by user")

if __name__ == "__main__":
    main()
