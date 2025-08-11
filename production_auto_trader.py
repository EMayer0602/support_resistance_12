#!/usr/bin/env python3
"""
Production Auto Daily Trader
Fully automated trading script that can be started anytime and runs continuously.

Features:
✅ Start at any time of day
✅ Waits for NY market open + 5 minutes for OPEN trades
✅ Waits for NY market close - 5 minutes for CLOSE trades
✅ Runs fresh backtest before each session
✅ Executes trades only once per session
✅ Skips weekends and holidays
✅ Continues until CTRL+C
✅ Full logging and error handling
✅ IB Paper Trading integration

Usage:
python production_auto_trader.py [options]

Options:
  --dry-run          Show what would be done without executing
  --live-trading     Use live account (default: paper trading)
  --test-mode        Use shorter intervals for testing
  --verbose          Enable verbose logging

Examples:
  python production_auto_trader.py                    # Paper trading
  python production_auto_trader.py --dry-run          # Test run
  python production_auto_trader.py --test-mode        # Quick test
"""

import asyncio
import sys
import os
import signal
import json
import subprocess
import logging
from datetime import datetime, time, timedelta
from typing import List, Tuple, Optional
from pathlib import Path

# Import our modules
from config import *
from tickers_config import tickers
import importlib

# Configure logging
def setup_logging(verbose=False):
    """Setup comprehensive logging"""
    log_level = logging.DEBUG if verbose else logging.INFO
    
    # Create logs directory
    Path('logs').mkdir(exist_ok=True)
    
    # Setup formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(message)s'
    )
    
    # Setup handlers
    handlers = []
    
    # File handler for all logs
    file_handler = logging.FileHandler(f'logs/auto_trader_{datetime.now().strftime("%Y%m%d")}.log')
    file_handler.setFormatter(detailed_formatter)
    file_handler.setLevel(log_level)
    handlers.append(file_handler)
    
    # Console handler for important messages
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(simple_formatter)
    console_handler.setLevel(logging.INFO)
    handlers.append(console_handler)
    
    # Configure root logger
    logging.basicConfig(
        level=log_level,
        handlers=handlers
    )
    
    return logging.getLogger(__name__)

class ProductionAutoTrader:
    def __init__(self, paper_trading=True, dry_run=False, test_mode=False, verbose=False):
        """Initialize the production auto trader"""
        self.paper_trading = paper_trading
        self.dry_run = dry_run
        self.test_mode = test_mode
        self.verbose = verbose
        self.running = True
        
        # Setup logging
        self.logger = setup_logging(verbose)
        
        # Calculate trading times
        self.calculate_trading_times()
        
        # Session tracking
        self.sessions_completed = {
            'date': None,
            'open': False,
            'close': False
        }
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        self.logger.info("🚀 Production Auto Trader Initialized")
        self.logger.info(f"📊 Mode: {'Paper' if paper_trading else 'LIVE'} Trading")
        self.logger.info(f"🔍 Dry Run: {'ON' if dry_run else 'OFF'}")
        self.logger.info(f"🧪 Test Mode: {'ON' if test_mode else 'OFF'}")

    def signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        if not hasattr(self, '_shutdown_initiated'):
            self._shutdown_initiated = True
            self.logger.info("🛑 Shutdown signal received - stopping gracefully...")
            self.running = False
            # Force exit if called multiple times
        else:
            self.logger.info("🛑 Force exit...")
            sys.exit(0)

    def calculate_trading_times(self):
        """Calculate trading times based on config and mode"""
        if self.test_mode:
            # For testing: use current time + small intervals
            now = datetime.now()
            self.open_trade_time = (now + timedelta(minutes=1)).time()
            self.close_trade_time = (now + timedelta(minutes=3)).time()
            self.market_close = (now + timedelta(minutes=5)).time()
            self.logger.info("🧪 Test mode: Using accelerated timing")
        else:
            # Production: 5 minutes after open, 5 minutes before close
            market_open = datetime.strptime(MARKET_OPEN_TIME, "%H:%M")
            market_close = datetime.strptime(MARKET_CLOSE_TIME, "%H:%M")
            
            # OPEN session: 5 minutes after market open
            open_plus_5 = market_open + timedelta(minutes=5)
            self.open_trade_time = open_plus_5.time()
            
            # CLOSE session: 5 minutes before market close
            close_minus_5 = market_close - timedelta(minutes=5)
            self.close_trade_time = close_minus_5.time()
            self.market_close = market_close.time()
        
        self.logger.info(f"⏰ Trading Schedule:")
        self.logger.info(f"   📈 OPEN trades: {self.open_trade_time.strftime('%H:%M')}")
        self.logger.info(f"   📉 CLOSE trades: {self.close_trade_time.strftime('%H:%M')}")
        self.logger.info(f"   🔔 Market close: {self.market_close.strftime('%H:%M')}")

    def is_trading_day(self, check_date: datetime = None) -> bool:
        """Check if date is a trading day (excludes weekends and major holidays)"""
        if check_date is None:
            check_date = datetime.now()
        
        # Skip weekends
        if check_date.weekday() in [5, 6]:  # Saturday=5, Sunday=6
            return False
        
        # US market holidays for 2025 (basic list - can be expanded)
        holidays_2025 = [
            datetime(2025, 1, 1).date(),   # New Year's Day
            datetime(2025, 1, 20).date(),  # MLK Day
            datetime(2025, 2, 17).date(),  # Presidents' Day
            datetime(2025, 4, 18).date(),  # Good Friday
            datetime(2025, 5, 26).date(),  # Memorial Day
            datetime(2025, 6, 19).date(),  # Juneteenth
            datetime(2025, 7, 4).date(),   # Independence Day
            datetime(2025, 9, 1).date(),   # Labor Day
            datetime(2025, 11, 27).date(), # Thanksgiving
            datetime(2025, 12, 25).date(), # Christmas
        ]
        
        return check_date.date() not in holidays_2025

    def reset_daily_sessions(self, date):
        """Reset session tracking for a new day"""
        self.sessions_completed = {
            'date': date,
            'open': False,
            'close': False
        }
        self.logger.info(f"📅 New trading day: {date.strftime('%Y-%m-%d (%A)')}")

    def run_comprehensive_backtest(self) -> bool:
        """Run the comprehensive backtest to get fresh signals"""
        if self.dry_run:
            self.logger.info("� DRY RUN: Would run comprehensive backtest")
            return True
        
        self.logger.info("� Running comprehensive backtest...")
        
        try:
            # Run the backtest script
            result = subprocess.run([
                sys.executable, 'complete_comprehensive_backtest.py'
            ], capture_output=True, text=True, timeout=600)  # 10 minute timeout
            
            if result.returncode == 0:
                self.logger.info("✅ Comprehensive backtest completed successfully")
                if self.verbose:
                    self.logger.debug(f"Backtest output: {result.stdout[:200]}...")
                return True
            else:
                self.logger.error(f"❌ Backtest failed with code {result.returncode}")
                self.logger.error(f"Error: {result.stderr}")
                return False
        
        except subprocess.TimeoutExpired:
            self.logger.error("❌ Backtest timed out after 10 minutes")
            return False
        except Exception as e:
            self.logger.error(f"❌ Error running backtest: {e}")
            return False

    def get_todays_signals(self, session_type: str) -> List:
        """Get today's trading signals for the specified session type"""
        if self.dry_run:
            # Simulate signals for dry run
            fake_signals = [
                {'ticker': 'AAPL', 'action': 'BUY', 'strategy': 'LONG'},
                {'ticker': 'GOOGL', 'action': 'SELL', 'strategy': 'LONG'}
            ] if session_type == 'OPEN' else []
            
            self.logger.info(f"🔍 DRY RUN: Simulated {len(fake_signals)} {session_type} signals")
            return fake_signals
        
        self.logger.info(f"🔍 Checking for {session_type} signals...")
        
        try:
            # Import and use the signal checker
            from check_todays_signals import check_todays_signals
            signals = check_todays_signals(session_type)
            self.logger.info(f"📊 Found {len(signals)} {session_type} signals")
            return signals or []
        
        except Exception as e:
            self.logger.error(f"❌ Error checking signals: {e}")
            return []

    async def execute_trading_session(self, session_type: str, signals: List) -> bool:
        """Execute a complete trading session"""
        if not signals:
            self.logger.info(f"📭 No {session_type} signals to execute")
            return True
        
        self.logger.info(f"🚀 Executing {session_type} trading session with {len(signals)} signals")
        
        if self.dry_run:
            self.logger.info("🔍 DRY RUN: Simulating trade execution...")
            for i, signal in enumerate(signals, 1):
                self.logger.info(f"   {i}. Would execute: {signal.get('ticker', 'N/A')} {signal.get('action', 'N/A')}")
                await asyncio.sleep(1)
            self.logger.info(f"✅ DRY RUN: {session_type} session completed")
            return True
        
        try:
            # Import and use manual trader
            from manual_trading import ManualTrader
            
            trader = ManualTrader(paper_trading=self.paper_trading)
            
            # Connect to IB
            if not await trader.connect_ib():
                self.logger.error(f"❌ Failed to connect to IB for {session_type} session")
                return False
            
            try:
                # Sync portfolio positions
                await trader.sync_portfolio_with_ib()
                
                # Create and execute combined orders
                orders = trader.portfolio_manager.create_combined_orders(signals)
                
                if not orders:
                    self.logger.info(f"📭 No executable orders from {session_type} signals")
                    return True
                
                successful_orders = 0
                for i, order in enumerate(orders, 1):
                    self.logger.info(f"📋 Executing order {i}/{len(orders)}: {order['ticker']} {order['action']} {order['shares']} shares")
                    
                    if await trader.place_order(order, execute=True):
                        successful_orders += 1
                    
                    # Brief pause between orders
                    if i < len(orders):
                        await asyncio.sleep(3)
                
                self.logger.info(f"✅ {session_type} session completed: {successful_orders}/{len(orders)} orders successful")
                
                # Log session results
                self.log_session_results(session_type, len(signals), len(orders), successful_orders)
                
                return successful_orders > 0 or len(orders) == 0
            
            finally:
                # Always disconnect
                if trader.ib:
                    trader.ib.disconnect()
                    self.logger.info("🔌 Disconnected from IB")
        
        except Exception as e:
            self.logger.error(f"❌ Error in {session_type} session execution: {e}")
            return False

    def log_session_results(self, session_type: str, signals_count: int, orders_count: int, successful_orders: int):
        """Log session results to file"""
        try:
            session_log = {
                'timestamp': datetime.now().isoformat(),
                'session_type': session_type,
                'signals_found': signals_count,
                'orders_created': orders_count,
                'orders_successful': successful_orders,
                'success_rate': successful_orders / orders_count if orders_count > 0 else 1.0,
                'paper_trading': self.paper_trading,
                'dry_run': self.dry_run
            }
            
            # Append to daily session log
            log_file = f'logs/sessions_{datetime.now().strftime("%Y%m%d")}.json'
            
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    sessions = json.load(f)
            else:
                sessions = []
            
            sessions.append(session_log)
            
            with open(log_file, 'w') as f:
                json.dump(sessions, f, indent=2)
        
        except Exception as e:
            self.logger.error(f"❌ Error logging session results: {e}")

    async def wait_for_time(self, target_time: time, session_name: str):
        """Wait until the specified time with periodic updates"""
        while self.running:
            now = datetime.now()
            current_time = now.time()
            
            # Check if we've reached the target time
            if current_time >= target_time:
                break
            
            # Check if we should stop
            if not self.running:
                self.logger.info(f"🛑 Stopping wait for {session_name} session")
                break
            
            # Calculate wait time
            today = now.date()
            target_datetime = datetime.combine(today, target_time)
            
            # If target time has passed today, it must be for tomorrow
            if target_datetime <= now:
                target_datetime += timedelta(days=1)
            
            wait_seconds = (target_datetime - now).total_seconds()
            
            # Provide appropriate status updates based on wait time
            if wait_seconds > 7200:  # > 2 hours
                self.logger.info(f"⏳ {wait_seconds/3600:.1f} hours until {session_name} session")
                sleep_time = min(1800, wait_seconds)  # Max 30 minutes
            elif wait_seconds > 600:   # > 10 minutes
                self.logger.info(f"⏳ {wait_seconds/60:.0f} minutes until {session_name} session")
                sleep_time = min(300, wait_seconds)   # Max 5 minutes
            elif wait_seconds > 60:    # > 1 minute
                self.logger.info(f"⏳ {wait_seconds/60:.1f} minutes until {session_name} session")
                sleep_time = min(30, wait_seconds)    # Max 30 seconds
            else:
                self.logger.info(f"⏳ {wait_seconds:.0f} seconds until {session_name} session")
                sleep_time = min(wait_seconds, 10)
            
            # Sleep in small chunks to be responsive to stop signals
            sleep_chunks = max(1, int(sleep_time / 5))  # Sleep in 5 chunks
            chunk_time = sleep_time / sleep_chunks
            
            for _ in range(sleep_chunks):
                if not self.running:
                    break
                await asyncio.sleep(chunk_time)
            
            if not self.running:
                break

    async def run_continuous_cycle(self):
        """Main continuous trading cycle"""
        self.logger.info("🎯 Starting continuous auto trading cycle")
        self.logger.info(f"💰 Total Capital: ${INITIAL_CAPITAL:,.2f}")
        self.logger.info(f"📊 Tracking {len(tickers)} tickers")
        
        try:
            while self.running:
                try:
                    now = datetime.now()
                    today = now.date()
                    current_time = now.time()
                    
                    # Check if we should stop
                    if not self.running:
                        break
                    
                    # Reset sessions for new day
                    if self.sessions_completed['date'] != today:
                        self.reset_daily_sessions(today)
                    
                    # Skip non-trading days
                    if not self.is_trading_day(now):
                        day_name = now.strftime('%A')
                        self.logger.info(f"😴 {day_name} is not a trading day - waiting...")
                        # Sleep in small chunks to be responsive to stop signals
                        for _ in range(60):  # 60 minutes total
                            if not self.running:
                                break
                            await asyncio.sleep(60)  # 1 minute chunks
                        continue
                    
                    # Handle OPEN trading session
                    if (not self.sessions_completed['open'] and 
                        current_time >= self.open_trade_time and self.running):
                        
                        self.logger.info("🌅 Starting OPEN trading session")
                        
                        # Run backtest first
                        if self.run_comprehensive_backtest() and self.running:
                            # Get signals and execute
                            signals = self.get_todays_signals('OPEN')
                            if self.running:
                                success = await self.execute_trading_session('OPEN', signals)
                                self.sessions_completed['open'] = True
                                
                                if success:
                                    self.logger.info("✅ OPEN session completed successfully")
                                else:
                                    self.logger.warning("⚠️  OPEN session had issues")
                        else:
                            self.logger.error("❌ Skipping OPEN session due to backtest failure")
                            self.sessions_completed['open'] = True  # Mark as done to avoid retry
                    
                    # Handle CLOSE trading session
                    elif (not self.sessions_completed['close'] and 
                          current_time >= self.close_trade_time and self.running):
                        
                        self.logger.info("🌙 Starting CLOSE trading session")
                        
                        # Run backtest first
                        if self.run_comprehensive_backtest() and self.running:
                            # Get signals and execute
                            signals = self.get_todays_signals('CLOSE')
                            if self.running:
                                success = await self.execute_trading_session('CLOSE', signals)
                                self.sessions_completed['close'] = True
                                
                                if success:
                                    self.logger.info("✅ CLOSE session completed successfully")
                                else:
                                    self.logger.warning("⚠️  CLOSE session had issues")
                        else:
                            self.logger.error("❌ Skipping CLOSE session due to backtest failure")
                            self.sessions_completed['close'] = True  # Mark as done to avoid retry
                    
                    # Wait for next session
                    elif not self.sessions_completed['open'] and self.running:
                        await self.wait_for_time(self.open_trade_time, 'OPEN')
                    elif not self.sessions_completed['close'] and self.running:
                        await self.wait_for_time(self.close_trade_time, 'CLOSE')
                    else:
                        # Both sessions done for today
                        if self.running:
                            self.logger.info("✅ All trading sessions completed for today")
                            self.logger.info("😴 Waiting for next trading day...")
                            # Sleep in small chunks to be responsive to stop signals
                            for _ in range(60):  # 60 minutes total
                                if not self.running:
                                    break
                                await asyncio.sleep(60)  # 1 minute chunks
                    
                    # Small delay to prevent tight loops
                    if self.running:
                        await asyncio.sleep(1)
                
                except Exception as e:
                    if self.running:
                        self.logger.error(f"❌ Error in main cycle: {e}")
                        self.logger.info("🔄 Continuing after error...")
                        await asyncio.sleep(60)  # Wait before retrying
                    
        except asyncio.CancelledError:
            self.logger.info("🛑 Async task cancelled")
        except KeyboardInterrupt:
            self.logger.info("🛑 Keyboard interrupt received")
        finally:
            self.running = False
            self.logger.info("🛑 Continuous trading cycle stopped")

        self.logger.info("🏁 Auto trader shutdown complete")

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Production Auto Daily Trader',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python production_auto_trader.py                    # Paper trading (recommended)
  python production_auto_trader.py --dry-run          # Test what would happen
  python production_auto_trader.py --test-mode        # Quick test with short intervals
  python production_auto_trader.py --live-trading     # LIVE trading (be careful!)
        """
    )
    
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without executing trades')
    parser.add_argument('--live-trading', action='store_true',
                       help='Use live trading account (default: paper trading)')
    parser.add_argument('--test-mode', action='store_true',
                       help='Use accelerated timing for testing')
    parser.add_argument('--verbose', action='store_true',
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Display startup information
    print("🎯 PRODUCTION AUTO DAILY TRADER")
    print("="*50)
    print(f"📊 Trading Mode: {'LIVE' if args.live_trading else 'Paper Trading'}")
    print(f"🔍 Dry Run: {'YES' if args.dry_run else 'NO'}")
    print(f"🧪 Test Mode: {'YES' if args.test_mode else 'NO'}")
    print(f"📝 Verbose Logging: {'YES' if args.verbose else 'NO'}")
    print(f"💰 Capital: ${INITIAL_CAPITAL:,.2f}")
    print(f"📈 Tickers: {len(tickers)}")
    print()
    print("⚠️  This script runs continuously until CTRL+C")
    print("   It will automatically execute trades at:")
    print("   • 5 minutes after market open for OPEN trades")
    print("   • 5 minutes before market close for CLOSE trades")
    print("   • Skips weekends and major holidays")
    
    # Safety confirmations
    if args.live_trading and not args.dry_run:
        print("\n🚨 WARNING: LIVE TRADING MODE ENABLED")
        confirm = input("   Type 'LIVE TRADING' to confirm: ")
        if confirm != 'LIVE TRADING':
            print("❌ Cancelled")
            return
    
    if not args.dry_run and not args.test_mode:
        mode_name = 'LIVE' if args.live_trading else 'Paper'
        confirm = input(f"\n▶️  Start automated {mode_name} trading? (y/n): ")
        if confirm.lower() != 'y':
            print("❌ Cancelled")
            return
    
    # Create and run the trader
    try:
        trader = ProductionAutoTrader(
            paper_trading=not args.live_trading,
            dry_run=args.dry_run,
            test_mode=args.test_mode,
            verbose=args.verbose
        )
        
        print(f"\n🚀 Starting auto trader...")
        print(f"📁 Logs will be saved to: logs/")
        print(f"🛑 Press CTRL+C to stop")
        
        # Run the trader with proper signal handling
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(trader.run_continuous_cycle())
        except KeyboardInterrupt:
            print("\n🛑 Stopping trader...")
            trader.running = False
            # Give it a moment to clean up
            try:
                loop.run_until_complete(asyncio.sleep(1))
            except:
                pass
        finally:
            # Cancel any pending tasks
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            # Wait for tasks to complete cancellation
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.close()
        
    except KeyboardInterrupt:
        print("\n🛑 Stopped by user (CTRL+C)")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        logging.error(f"Fatal error: {e}")
    
    print("🏁 Auto trader shutdown complete")

if __name__ == "__main__":
    main()
