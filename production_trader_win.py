#!/usr/bin/env python3
"""
Production Auto Daily Trader - Windows Compatible Version
Fully automated trading script that can be started anytime and runs continuously.

Features:
- Start at any time of day
- Waits for NY market open + 5 minutes for OPEN trades
- Waits for NY market close - 5 minutes for CLOSE trades
- Runs fresh backtest before each session
- Executes trades only once per session
- Skips weekends and holidays
- Continues until CTRL+C
- Full logging and error handling
- IB Paper Trading integration

Usage:
python production_trader_win.py [options]

Options:
  --dry-run          Show what would be done without executing
  --live-trading     Use live account (default: paper trading)
  --test-mode        Use shorter intervals for testing
  --verbose          Enable verbose logging

Examples:
  python production_trader_win.py                    # Paper trading
  python production_trader_win.py --dry-run          # Test run
  python production_trader_win.py --test-mode        # Quick test
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

try:
    # Python 3.9+
    from zoneinfo import ZoneInfo
except ImportError:  # Fallback (older Python) - use naive times
    ZoneInfo = None

# Default market timezone (override by adding MARKET_TIMEZONE in config.py if desired)
MARKET_TIMEZONE = globals().get('MARKET_TIMEZONE', 'America/New_York')

class ProductionAutoTrader:
    def __init__(self, paper_trading: bool = True, dry_run: bool = False, test_mode: bool = False, verbose: bool = False):
        """Initialize the production auto trader."""
        # Mode flags
        self.paper_trading = paper_trading
        self.dry_run = dry_run
        self.test_mode = test_mode
        self.verbose = verbose
        self.running = True

        # Backtest tracking
        self._last_backtest_run = None
        self._min_backtest_interval_min = 10  # minutes

        # Logging
        self.logger = setup_logging(verbose)

        # Trading times
        self.calculate_trading_times()

        # Session tracking state
        self.sessions_completed = {
            'date': None,
            'open': False,
            'close': False
        }

        # Signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

        # Startup logging
        self.logger.info("PRODUCTION AUTO TRADER INITIALIZED")
        self.logger.info(f"MODE: {'Paper' if paper_trading else 'LIVE'} Trading")
        self.logger.info(f"DRY RUN: {'ON' if dry_run else 'OFF'}")
        self.logger.info(f"TEST MODE: {'ON' if test_mode else 'OFF'}")

        # Heartbeat state
        self._last_ib_heartbeat = None
        self._ib_trader_ref = None  # store a ManualTrader instance when connected

    def signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        if not hasattr(self, '_shutdown_initiated'):
            self._shutdown_initiated = True
            self.logger.info("SHUTDOWN SIGNAL RECEIVED - STOPPING GRACEFULLY...")
            self.running = False
        else:
            self.logger.info("FORCE EXIT...")
            sys.exit(0)

    def get_market_now(self) -> datetime:
        """Return current market timezone-aware datetime (Eastern)"""
        if self.test_mode:
            return datetime.now()
        if ZoneInfo is not None:
            try:
                return datetime.now(ZoneInfo(MARKET_TIMEZONE))
            except Exception:
                return datetime.utcnow()
        # Fallback to naive local time
        return datetime.now()

    def calculate_trading_times(self):
        """Calculate trading times based on config and mode"""
        if self.test_mode:
            # For testing: use current time + small intervals
            now = self.get_market_now()
            self.open_trade_time = (now + timedelta(minutes=1)).time()
            self.close_trade_time = (now + timedelta(minutes=3)).time()
            self.market_close = (now + timedelta(minutes=5)).time()
            self.logger.info("TEST MODE: Using accelerated timing")
        else:
            # Production: use config-driven offsets for open/close sessions
            market_open = datetime.strptime(MARKET_OPEN_TIME, "%H:%M")
            market_close = datetime.strptime(MARKET_CLOSE_TIME, "%H:%M")

            # OPEN session: OPEN_TRADE_DELAY minutes after market open
            open_plus_delay = market_open + timedelta(minutes=OPEN_TRADE_DELAY)
            self.open_trade_time = open_plus_delay.time()

            # CLOSE session: CLOSE_TRADE_ADVANCE minutes before market close
            close_minus_advance = market_close - timedelta(minutes=CLOSE_TRADE_ADVANCE)
            self.close_trade_time = close_minus_advance.time()
            self.market_close = market_close.time()

        self.logger.info(f"TRADING SCHEDULE:")
        self.logger.info(f"  OPEN trades: {self.open_trade_time.strftime('%H:%M')} (open + {OPEN_TRADE_DELAY}m)")
        self.logger.info(f"  CLOSE trades: {self.close_trade_time.strftime('%H:%M')} (close - {CLOSE_TRADE_ADVANCE}m)")
        self.logger.info(f"  Market close: {self.market_close.strftime('%H:%M')}")

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
        """Reset session tracking for a new day. Always allow OPEN session unless already executed earlier today."""
        now = self.get_market_now()
        # Do not pre-skip open; allow it to run immediately if start is after scheduled time
        self.sessions_completed = {
            'date': date,
            'open': False,
            'close': False
        }
        self.logger.info(f"NEW TRADING DAY: {date.strftime('%Y-%m-%d (%A)')}")
        if now.time() > self.open_trade_time:
            self.logger.info(f"NOTE: Current time is past scheduled OPEN trade time ({self.open_trade_time.strftime('%H:%M')}). OPEN session will run now if not yet executed.")

    def run_comprehensive_backtest(self) -> bool:
        """Run the comprehensive backtest to get fresh signals"""
        if self.dry_run:
            self.logger.info("DRY RUN: Would run comprehensive backtest")
            return True
        
        self.logger.info("RUNNING COMPREHENSIVE BACKTEST...")
        
        try:
            # Run the original backtest script
            result = subprocess.run([
                sys.executable, 'complete_comprehensive_backtest.py'
            ], capture_output=True, text=True, timeout=600, encoding='utf-8', errors='ignore')  # Handle Unicode gracefully
            
            if result.returncode == 0:
                self.logger.info("COMPREHENSIVE BACKTEST COMPLETED SUCCESSFULLY")
                if self.verbose:
                    self.logger.debug(f"Backtest output: {result.stdout[:200]}...")
                # After successful backtest, refresh rolling 14-day trade summary
                try:
                    import generate_last14_trades
                    generate_last14_trades.build_last14()
                    self.logger.info("UPDATED trades_last14_days.json (rolling 14 trading days)")
                except Exception as gen_err:
                    self.logger.warning(f"Could not update rolling 14-day trades file: {gen_err}")
                return True
            else:
                self.logger.error(f"BACKTEST FAILED with code {result.returncode}")
                self.logger.error(f"Error: {result.stderr}")
                return False
        
        except subprocess.TimeoutExpired:
            self.logger.error("BACKTEST TIMED OUT after 10 minutes")
            return False
        except Exception as e:
            self.logger.error(f"ERROR running backtest: {e}")
            return False

    def run_backtest_if_needed(self, session_label: str) -> bool:
        """Run backtest unless it was executed very recently to prevent duplicate runs."""
        if self.dry_run:
            self.logger.info("DRY RUN: Skipping real backtest (simulated)")
            return True

        now = datetime.now()
        if self._last_backtest_run is not None:
            delta_min = (now - self._last_backtest_run).total_seconds() / 60.0
            if delta_min < self._min_backtest_interval_min:
                self.logger.info(
                    f"RECENT BACKTEST FOUND ({delta_min:.1f} min ago) - reusing results for {session_label} session"
                )
                return True

        # First attempt + optional retries
        attempts = 0
        ok = False
        max_attempts = 1 + globals().get('BACKTEST_MAX_RETRIES', 0)
        retry_delay = globals().get('BACKTEST_RETRY_DELAY_SEC', 30)
        while attempts < max_attempts and not ok:
            attempts += 1
            if attempts > 1:
                self.logger.info(f"RETRYING BACKTEST (attempt {attempts}/{max_attempts}) after failure...")
            ok = self.run_comprehensive_backtest()
            if not ok and attempts < max_attempts:
                self.logger.info(f"WAITING {retry_delay}s BEFORE BACKTEST RETRY")
                import time as _t
                for _ in range(retry_delay):
                    if not self.running:
                        break
                    _t.sleep(1)
        if ok:
            self._last_backtest_run = now
        return ok

    async def check_portfolio_exits(self) -> List[dict]:
        """Check current portfolio for exit signals - STRATEGY SIGNALS ONLY"""
        try:
            if self.dry_run:
                self.logger.info("DRY RUN: Would check portfolio for STRATEGY-BASED exit signals only")
                # No automatic exits in dry run - only strategy signals
                return []
            
            from manual_trading import ManualTrader
            from check_todays_signals import check_todays_signals
            
            # Create trader instance for portfolio access
            trader = ManualTrader(paper_trading=self.paper_trading)
            
            if not await trader.connect_ib():
                self.logger.error("CANNOT CONNECT TO IB FOR PORTFOLIO CHECK")
                return []
            
            try:
                # Sync portfolio
                await trader.sync_portfolio_with_ib()
                
                # Get current positions
                positions = trader.ib.positions()
                current_tickers = set()
                position_directions = {}
                
                for pos in positions:
                    ticker = pos.contract.symbol
                    shares = int(pos.position)
                    if shares != 0:
                        current_tickers.add(ticker)
                        position_directions[ticker] = "LONG" if shares > 0 else "SHORT"
                
                if not current_tickers:
                    self.logger.info("NO CURRENT POSITIONS - NO EXIT SIGNALS NEEDED")
                    return []
                
                # Get today's strategy signals for ALL sessions (OPEN and CLOSE)
                exit_signals = []
                
                for session in ['OPEN', 'CLOSE']:
                    try:
                        strategy_signals = check_todays_signals(session)
                        if not strategy_signals:
                            continue
                            
                        for signal in strategy_signals:
                            ticker = signal.get('ticker', '')
                            action = signal.get('action', '')
                            strategy = signal.get('strategy', '')
                            
                            if ticker in current_tickers:
                                current_direction = position_directions[ticker]
                                
                                # Check for exit conditions based on STRATEGY SIGNALS ONLY
                                should_exit = False
                                exit_reason = ""
                                
                                # LONG position exits
                                if current_direction == "LONG":
                                    if action == "SELL" and strategy in ["LONG", "SHORT"]:
                                        should_exit = True
                                        exit_reason = f"STRATEGY SIGNAL: {strategy} {action} ({session})"
                                
                                # SHORT position exits  
                                elif current_direction == "SHORT":
                                    if action == "BUY" and strategy in ["LONG", "SHORT"]:
                                        should_exit = True
                                        exit_reason = f"STRATEGY SIGNAL: {strategy} {action} ({session})"
                                
                                if should_exit:
                                    exit_action = "SELL" if current_direction == "LONG" else "COVER"
                                    
                                    exit_signals.append({
                                        'ticker': ticker,
                                        'action': exit_action,
                                        'reason': exit_reason,
                                        'signal_type': 'STRATEGY_EXIT',
                                        'trade_on': 'IMMEDIATE',
                                        'session': session,
                                        'original_signal': signal
                                    })
                                    
                                    self.logger.info(f"STRATEGY EXIT: {ticker} {exit_action} - {exit_reason}")
                                    
                    except Exception as e:
                        self.logger.error(f"ERROR checking {session} signals: {e}")
                
                if not exit_signals:
                    self.logger.info("NO STRATEGY EXIT SIGNALS - POSITIONS MAINTAINED")
                
                return exit_signals
                
            finally:
                if trader.ib:
                    trader.ib.disconnect()
                    
        except Exception as e:
            self.logger.error(f"ERROR checking portfolio exits: {e}")
            return []

    async def get_todays_signals(self, session_type: str) -> List:
        """Get today's trading signals for the specified session type"""
        all_signals = []
        
        # 1. Check for exit signals from existing positions - STRATEGY SIGNALS ONLY
        self.logger.info(f"CHECKING EXISTING PORTFOLIO FOR STRATEGY EXIT SIGNALS...")
        exit_signals = await self.check_portfolio_exits()
        
        if exit_signals:
            self.logger.info(f"FOUND {len(exit_signals)} STRATEGY EXIT SIGNALS FROM PORTFOLIO")
            all_signals.extend(exit_signals)
        else:
            self.logger.info("NO STRATEGY EXIT SIGNALS - POSITIONS MAINTAINED")
        
        # 2. Get regular entry signals
        if self.dry_run:
            # Simulate signals for dry run
            fake_signals = [
                {'ticker': 'AAPL', 'action': 'BUY', 'strategy': 'LONG'},
                {'ticker': 'GOOGL', 'action': 'SELL', 'strategy': 'LONG'}
            ] if session_type == 'OPEN' else []
            
            self.logger.info(f"DRY RUN: Simulated {len(fake_signals)} {session_type} entry signals")
            all_signals.extend(fake_signals)
        else:
            self.logger.info(f"CHECKING FOR {session_type} ENTRY SIGNALS...")
            
            try:
                # Import and use the signal checker
                from check_todays_signals import check_todays_signals
                entry_signals = check_todays_signals(session_type)
                if entry_signals:
                    self.logger.info(f"FOUND {len(entry_signals)} {session_type} entry signals")
                    all_signals.extend(entry_signals)
                else:
                    self.logger.info(f"NO {session_type} entry signals found")
            
            except Exception as e:
                self.logger.error(f"ERROR checking entry signals: {e}")
        
        # 3. Summary
        total_signals = len(all_signals)
        strategy_exit_count = len([s for s in all_signals if s.get('signal_type') == 'STRATEGY_EXIT'])
        entry_count = total_signals - strategy_exit_count
        
        self.logger.info(f"SIGNAL SUMMARY: {total_signals} total ({strategy_exit_count} strategy exits, {entry_count} entries)")
        
        return all_signals

    async def execute_trading_session(self, session_type: str, signals: List) -> bool:
        """Execute a complete trading session"""
        if not signals:
            self.logger.info(f"NO {session_type} SIGNALS TO EXECUTE")
            return True
        
        self.logger.info(f"EXECUTING {session_type} TRADING SESSION with {len(signals)} signals")
        
        if self.dry_run:
            self.logger.info("DRY RUN: Simulating trade execution...")
            for i, signal in enumerate(signals, 1):
                self.logger.info(f"  {i}. Would execute: {signal.get('ticker', 'N/A')} {signal.get('action', 'N/A')}")
                await asyncio.sleep(1)
            self.logger.info(f"DRY RUN: {session_type} session completed")
            return True
        
        try:
            # Import and use manual trader
            from manual_trading import ManualTrader

            trader = ManualTrader(paper_trading=self.paper_trading)
            self._ib_trader_ref = trader  # keep reference for heartbeat checks
            
            # Connect to IB
            if not trader.connect_ib():
                self.logger.error(f"FAILED TO CONNECT to IB for {session_type} session")
                return False
            
            try:
                # Sync portfolio positions
                trader.sync_portfolio_with_ib()
                
                # Create and execute combined orders
                orders = trader.portfolio_manager.create_combined_orders(signals)
                
                if not orders:
                    self.logger.info(f"NO EXECUTABLE ORDERS from {session_type} signals")
                    return True
                
                successful_orders = 0
                for i, order in enumerate(orders, 1):
                    self.logger.info(f"EXECUTING ORDER {i}/{len(orders)}: {order['ticker']} {order['action']} {order['shares']} shares")
                    
                    if trader.place_order(order, execute=True):
                        successful_orders += 1
                    
                    # Brief pause between orders
                    if i < len(orders):
                        await asyncio.sleep(3)
                
                self.logger.info(f"{session_type} SESSION COMPLETED: {successful_orders}/{len(orders)} orders successful")
                
                # Log session results
                self.log_session_results(session_type, len(signals), len(orders), successful_orders)
                
                return successful_orders > 0 or len(orders) == 0
            
            finally:
                # Always disconnect
                if trader.ib:
                    trader.ib.disconnect()
                    self.logger.info("DISCONNECTED FROM IB")
                    self._ib_trader_ref = None
        
        except Exception as e:
            self.logger.error(f"ERROR IN {session_type} SESSION EXECUTION: {e}")
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
            self.logger.error(f"ERROR logging session results: {e}")

    async def wait_for_time(self, target_time: time, session_name: str):
        """Wait until the specified time with periodic updates"""
        while self.running:
            now = self.get_market_now()
            current_time = now.time()
            
            # Check if we've reached the target time
            if current_time >= target_time:
                break
            
            # Check if we should stop
            if not self.running:
                self.logger.info(f"STOPPING WAIT for {session_name} session")
                break
            
            # Calculate wait time
            today = now.date()
            # Build target datetime in market timezone if possible
            if ZoneInfo is not None:
                try:
                    target_datetime = datetime.combine(today, target_time, tzinfo=ZoneInfo(MARKET_TIMEZONE))
                except Exception:
                    target_datetime = datetime.combine(today, target_time)
            else:
                target_datetime = datetime.combine(today, target_time)
            
            # If target time has passed today, it must be for tomorrow
            if target_datetime <= now:
                target_datetime += timedelta(days=1)
            
            wait_seconds = (target_datetime - now).total_seconds()
            
            # Provide appropriate status updates based on wait time
            if wait_seconds > 7200:  # > 2 hours
                self.logger.info(f"WAITING: {wait_seconds/3600:.1f} hours until {session_name} session")
                sleep_time = min(1800, wait_seconds)  # Max 30 minutes
            elif wait_seconds > 600:   # > 10 minutes
                self.logger.info(f"WAITING: {wait_seconds/60:.0f} minutes until {session_name} session")
                sleep_time = min(300, wait_seconds)   # Max 5 minutes
            elif wait_seconds > 60:    # > 1 minute
                self.logger.info(f"WAITING: {wait_seconds/60:.1f} minutes until {session_name} session")
                sleep_time = min(30, wait_seconds)    # Max 30 seconds
            else:
                self.logger.info(f"WAITING: {wait_seconds:.0f} seconds until {session_name} session")
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
        self.logger.info("STARTING CONTINUOUS AUTO TRADING CYCLE")
        self.logger.info(f"TOTAL CAPITAL: ${INITIAL_CAPITAL:,.2f}")
        self.logger.info(f"TRACKING {len(tickers)} tickers")
        
        try:
            while self.running:
                try:
                    now = self.get_market_now()
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
                        self.logger.info(f"{day_name} IS NOT A TRADING DAY - WAITING...")
                        # Sleep in small chunks to be responsive to stop signals
                        for _ in range(60):  # 60 minutes total
                            if not self.running:
                                break
                            await asyncio.sleep(60)  # 1 minute chunks
                        continue
                    
                    # Determine if OPEN session is still within grace window
                    if not self.sessions_completed['open'] and current_time >= self.open_trade_time:
                        # Build scheduled datetime respecting timezone of 'now'
                        if now.tzinfo is not None:
                            scheduled_dt = datetime.combine(now.date(), self.open_trade_time, tzinfo=now.tzinfo)
                        else:
                            scheduled_dt = datetime.combine(now.date(), self.open_trade_time)
                        elapsed_min = max(0.0, (now - scheduled_dt).total_seconds() / 60.0)
                        grace_minutes = globals().get('OPEN_SESSION_GRACE_MIN', 0)
                        within_grace = elapsed_min <= grace_minutes and current_time < self.close_trade_time
                        # If we're past the CLOSE trade time OR grace expired, mark skipped
                        if (current_time >= self.close_trade_time) or (not within_grace):
                            if current_time >= self.close_trade_time:
                                self.logger.warning("OPEN SESSION WINDOW MISSED (past close trade time) - SKIPPING OPEN")
                            else:
                                self.logger.warning(f"OPEN SESSION GRACE EXPIRED ({elapsed_min:.1f} min > {grace_minutes} min) - SKIPPING OPEN")
                            self.sessions_completed['open'] = True

                    # Handle CLOSE trading session FIRST (so we never skip it)
                    # CLOSE session grace handling
                    close_grace_min = globals().get('CLOSE_SESSION_GRACE_MIN', 0)
                    allow_close = False
                    if (not self.sessions_completed['close'] and current_time >= self.close_trade_time and self.running):
                        if current_time <= self.market_close:
                            allow_close = True
                        else:
                            # minutes past close
                            try:
                                past_minutes = (datetime.combine(today, current_time) - datetime.combine(today, self.market_close)).total_seconds()/60.0
                            except Exception:
                                past_minutes = 999
                            if past_minutes <= close_grace_min:
                                allow_close = True
                            else:
                                self.logger.warning(f"CLOSE SESSION GRACE EXPIRED ({past_minutes:.1f} min > {close_grace_min} min) - SKIPPING CLOSE")
                                self.sessions_completed['close'] = True

                    if allow_close:

                        self.logger.info("STARTING CLOSE TRADING SESSION")

                        if self.run_backtest_if_needed('CLOSE') and self.running:
                            signals = await self.get_todays_signals('CLOSE')
                            if self.running:
                                success = await self.execute_trading_session('CLOSE', signals)
                                self.sessions_completed['close'] = True
                                if success:
                                    self.logger.info("CLOSE SESSION COMPLETED SUCCESSFULLY")
                                else:
                                    self.logger.warning("CLOSE SESSION HAD ISSUES")
                        else:
                            self.logger.error("SKIPPING CLOSE SESSION due to backtest failure")
                            self.sessions_completed['close'] = True

                    # Handle OPEN trading session (only if still pending and within window)
                    if (not self.sessions_completed['open'] and 
                        current_time >= self.open_trade_time and 
                        current_time < self.close_trade_time and self.running):

                        self.logger.info("STARTING OPEN TRADING SESSION")

                        if self.run_backtest_if_needed('OPEN') and self.running:
                            signals = await self.get_todays_signals('OPEN')
                            if self.running:
                                success = await self.execute_trading_session('OPEN', signals)
                                self.sessions_completed['open'] = True
                                if success:
                                    self.logger.info("OPEN SESSION COMPLETED SUCCESSFULLY")
                                else:
                                    self.logger.warning("OPEN SESSION HAD ISSUES")
                        else:
                            self.logger.error("SKIPPING OPEN SESSION due to backtest failure")
                            self.sessions_completed['open'] = True

                    # Waiting logic
                    if (not self.sessions_completed['open'] and current_time < self.open_trade_time and self.running):
                        await self.wait_for_time(self.open_trade_time, 'OPEN')
                    elif (self.sessions_completed['open'] and 
                          not self.sessions_completed['close'] and 
                          current_time < self.close_trade_time and self.running):
                        await self.wait_for_time(self.close_trade_time, 'CLOSE')
                    elif (not self.sessions_completed['close'] and current_time > self.market_close and self.running):
                        # If still within grace we handled earlier; here means grace either zero or already expired
                        if globals().get('CLOSE_SESSION_GRACE_MIN', 0) == 0:
                            self.logger.warning("CLOSE SESSION WINDOW MISSED (after market close) - SKIPPING CLOSE")
                            self.sessions_completed['close'] = True
                    elif self.sessions_completed['open'] and self.sessions_completed['close'] and self.running:
                        self.logger.info("ALL TRADING SESSIONS COMPLETED FOR TODAY")
                        self.logger.info("WAITING FOR NEXT TRADING DAY...")
                        for _ in range(60):
                            if not self.running:
                                break
                            await asyncio.sleep(60)
                    
                    # Heartbeat / small delay
                    if self.running:
                        # Perform lightweight heartbeat every IB_HEARTBEAT_SEC seconds if connected
                        if self._ib_trader_ref and getattr(self._ib_trader_ref, 'ib', None) and self._ib_trader_ref.ib.isConnected():
                            now_ts = datetime.utcnow().timestamp()
                            if (self._last_ib_heartbeat is None or 
                                now_ts - self._last_ib_heartbeat > globals().get('IB_HEARTBEAT_SEC', 30)):
                                try:
                                    # Ping by requesting current time
                                    ct = self._ib_trader_ref.ib.reqCurrentTime()
                                    self._last_ib_heartbeat = now_ts
                                    if self.verbose:
                                        self.logger.debug(f"IB HEARTBEAT OK: {ct}")
                                except Exception as hb_err:
                                    self.logger.warning(f"IB HEARTBEAT FAILED: {hb_err}")
                                    if globals().get('IB_RECONNECT_ON_TIMEOUT', True):
                                        try:
                                            self.logger.info("Attempting IB reconnect after heartbeat failure...")
                                            self._ib_trader_ref.ib.disconnect()
                                            # Reconnect using manual trader logic
                                            if not self._ib_trader_ref.connect_ib():
                                                self.logger.error("IB RECONNECT FAILED")
                                            else:
                                                self.logger.info("IB RECONNECTED SUCCESSFULLY")
                                        except Exception as rec_err:
                                            self.logger.error(f"IB RECONNECT ERROR: {rec_err}")
                        await asyncio.sleep(1)
                
                except Exception as e:
                    if self.running:
                        self.logger.error(f"ERROR IN MAIN CYCLE: {e}")
                        self.logger.info("CONTINUING AFTER ERROR...")
                        await asyncio.sleep(60)  # Wait before retrying
                    
        except asyncio.CancelledError:
            self.logger.info("ASYNC TASK CANCELLED")
        except KeyboardInterrupt:
            self.logger.info("KEYBOARD INTERRUPT RECEIVED")
        finally:
            self.running = False
            self.logger.info("CONTINUOUS TRADING CYCLE STOPPED")

        self.logger.info("AUTO TRADER SHUTDOWN COMPLETE")

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Production Auto Daily Trader - Windows Compatible',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python production_trader_win.py                    # Paper trading (recommended)
  python production_trader_win.py --dry-run          # Test what would happen
  python production_trader_win.py --test-mode        # Quick test with short intervals
  python production_trader_win.py --live-trading     # LIVE trading (be careful!)
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
    print("PRODUCTION AUTO DAILY TRADER")
    print("="*50)
    print(f"Trading Mode: {'LIVE' if args.live_trading else 'Paper Trading'}")
    print(f"Dry Run: {'YES' if args.dry_run else 'NO'}")
    print(f"Test Mode: {'YES' if args.test_mode else 'NO'}")
    print(f"Verbose Logging: {'YES' if args.verbose else 'NO'}")
    print(f"Capital: ${INITIAL_CAPITAL:,.2f}")
    print(f"Tickers: {len(tickers)}")
    print()
    print("This script runs continuously until CTRL+C")
    print("It will automatically execute trades at:")
    print("- 5 minutes after market open for OPEN trades")
    print("- 5 minutes before market close for CLOSE trades")
    print("- Skips weekends and major holidays")
    
    # Safety confirmations
    if args.live_trading and not args.dry_run:
        print("\nWARNING: LIVE TRADING MODE ENABLED")
        confirm = input("Type 'LIVE TRADING' to confirm: ")
        if confirm != 'LIVE TRADING':
            print("Cancelled")
            return
    
    if not args.dry_run and not args.test_mode:
        mode_name = 'LIVE' if args.live_trading else 'Paper'
        confirm = input(f"\nStart automated {mode_name} trading? (y/n): ")
        if confirm.lower() != 'y':
            print("Cancelled")
            return
    
    # Create and run the trader
    try:
        trader = ProductionAutoTrader(
            paper_trading=not args.live_trading,
            dry_run=args.dry_run,
            test_mode=args.test_mode,
            verbose=args.verbose
        )
        
        print(f"\nSTARTING AUTO TRADER...")
        print(f"Logs will be saved to: logs/")
        print(f"Press CTRL+C to stop")
        
        # Run the trader with proper signal handling
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(trader.run_continuous_cycle())
        except KeyboardInterrupt:
            print("\nSTOPPING TRADER...")
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
        print("\nSTOPPED BY USER (CTRL+C)")
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        logging.error(f"Fatal error: {e}")
    
    print("AUTO TRADER SHUTDOWN COMPLETE")

if __name__ == "__main__":
    main()
