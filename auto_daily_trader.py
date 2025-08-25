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
from typing import Tuple
import logging
try:  # Python 3.9+
    from zoneinfo import ZoneInfo  # type: ignore
except Exception:  # pragma: no cover
    ZoneInfo = None  # fallback handled later
from ib_insync import *  # noqa: F401,F403 (assumed needed by ManualTrader)
import json
import subprocess

# Import project modules
from config import *  # noqa: F401,F403
from check_todays_signals import check_todays_signals, TICKERS_CONFIG
from portfolio_manager import PortfolioManager
from manual_trading import ManualTrader

# Logging setup (ASCII only for Windows console compatibility)
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
    def __init__(self, paper_trading: bool = True, dry_run: bool = False):
        # Basic config
        self.paper_trading = paper_trading
        self.dry_run = dry_run
        self.running = True
        self.stop_event = asyncio.Event()
        self._sigint_count = 0

        # Timezone (market time in US/Eastern)
        self.market_tz_name = 'US/Eastern'
        if ZoneInfo is not None:
            try:
                self.market_tz = ZoneInfo(self.market_tz_name)
            except Exception:  # pragma: no cover
                self.market_tz = None
        else:  # pragma: no cover
            self.market_tz = None

        # Core components
        self.manual_trader = ManualTrader(paper_trading)
        self.portfolio_manager = PortfolioManager()

        # Trading time placeholders
        self.open_trading_time = None
        self.close_trading_time = None
        self.market_close_time = None
        self.calculate_trading_times()

        # Daily session flags
        self.today_open_executed = False
        self.today_close_executed = False
        self.current_date = None

        # Persistent state / idempotency tracking
        self.state_file = 'auto_daily_state.json'
        self.executed_orders_file = 'executed_orders.json'
        self._load_persistent_state()

        # OS signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def signal_handler(self, signum, frame):  # noqa: D401, unused-arguments
        """Handle CTRL+C gracefully"""
        self._sigint_count += 1
        if self._sigint_count == 1:
            logger.info("Received shutdown signal (CTRL+C) -> initiating graceful stop")
            self.running = False
            try:
                self.stop_event.set()
            except Exception:
                pass
        else:
            logger.info("Additional CTRL+C received -> forcing faster exit")
            self.running = False
            try:
                self.stop_event.set()
            except Exception:
                pass

    def calculate_trading_times(self):
        try:
            market_open = datetime.strptime(MARKET_OPEN_TIME, "%H:%M").time()
            market_close = datetime.strptime(MARKET_CLOSE_TIME, "%H:%M").time()

            open_minutes = market_open.hour * 60 + market_open.minute + 5
            self.open_trading_time = time(open_minutes // 60, open_minutes % 60)

            close_minutes = market_close.hour * 60 + market_close.minute - 5
            self.close_trading_time = time(close_minutes // 60, close_minutes % 60)

            self.market_close_time = market_close

            logger.info("Trading Schedule:")
            logger.info(f"   Market Open: {MARKET_OPEN_TIME}")
            logger.info(f"   OPEN Trades: {self.open_trading_time.strftime('%H:%M')} (5 min after open)")
            logger.info(f"   CLOSE Trades: {self.close_trading_time.strftime('%H:%M')} (5 min before close)")
            logger.info(f"   Market Close: {MARKET_CLOSE_TIME}")
        except Exception as e:  # pragma: no cover
            logger.error(f"Error calculating trading times: {e}")
            self.open_trading_time = time(9, 35)
            self.close_trading_time = time(15, 55)
            self.market_close_time = time(16, 0)

    def _market_now(self) -> datetime:
        """Return current market timezone-aware datetime (falls back to local)."""
        if getattr(self, 'market_tz', None):
            return datetime.now(self.market_tz)
        return datetime.now()

    def is_trading_day(self, check_date: datetime) -> bool:
        if check_date.weekday() in [5, 6]:  # Saturday, Sunday
            return False
        us_holidays_2025 = [
            datetime(2025, 1, 1).date(),
            datetime(2025, 1, 20).date(),
            datetime(2025, 2, 17).date(),
            datetime(2025, 4, 18).date(),
            datetime(2025, 5, 26).date(),
            datetime(2025, 6, 19).date(),
            datetime(2025, 7, 4).date(),
            datetime(2025, 9, 1).date(),
            datetime(2025, 11, 27).date(),
            datetime(2025, 12, 25).date(),
        ]
        return check_date.date() not in us_holidays_2025

    def get_next_trading_session(self) -> Tuple[datetime, str]:
        """Return the next session (OPEN or CLOSE) purely by NY time.

        Logic:
          - If today is not trading day, advance to next trading day OPEN.
          - If before OPEN window -> schedule OPEN.
          - If between OPEN and CLOSE windows -> schedule CLOSE.
          - If after CLOSE window -> advance to next trading day OPEN.
        Session flags are not used to decide scheduling (idempotency handled elsewhere).
        """
        now = self._market_now()
        while True:
            if not self.is_trading_day(now):
                # Move to next day at midnight NY and continue
                next_day = (now + timedelta(days=1)).date()
                base = datetime.combine(next_day, time(0, 0))
                if getattr(self, 'market_tz', None):
                    now = base.replace(tzinfo=self.market_tz)
                else:
                    now = base
                continue

            date = now.date()
            open_dt = datetime.combine(date, self.open_trading_time)
            close_dt = datetime.combine(date, self.close_trading_time)
            if getattr(self, 'market_tz', None):
                open_dt = open_dt.replace(tzinfo=self.market_tz)
                close_dt = close_dt.replace(tzinfo=self.market_tz)

            if now < open_dt:
                return open_dt, "OPEN"
            if now < close_dt:
                return close_dt, "CLOSE"

            # After today's close: advance one day and loop
            next_day = (now + timedelta(days=1)).date()
            base = datetime.combine(next_day, time(0, 0))
            if getattr(self, 'market_tz', None):
                now = base.replace(tzinfo=self.market_tz)
            else:
                now = base

    # ------------------ PERSISTENT STATE ------------------
    def _load_persistent_state(self):
        """Load previous day's session completion to avoid duplicate runs on restart."""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                saved_date = data.get('date')
                today_str = self._market_now().strftime('%Y-%m-%d')
                if saved_date == today_str:
                    self.today_open_executed = data.get('open_executed', False)
                    self.today_close_executed = data.get('close_executed', False)
                    logger.info(f"Restored session state for {today_str}: OPEN={self.today_open_executed} CLOSE={self.today_close_executed}")
        except Exception as e:  # pragma: no cover
            logger.warning(f"Could not load state file: {e}")

    def _save_persistent_state(self):
        """Persist today's session completion flags."""
        try:
            data = {
                'date': self._market_now().strftime('%Y-%m-%d'),
                'open_executed': self.today_open_executed,
                'close_executed': self.today_close_executed
            }
            with open(self.state_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:  # pragma: no cover
            logger.warning(f"Could not save state file: {e}")

    def _load_executed_orders(self):
        try:
            if os.path.exists(self.executed_orders_file):
                with open(self.executed_orders_file, 'r') as f:
                    return set(json.load(f))
        except Exception as e:  # pragma: no cover
            logger.warning(f"Could not load executed orders file: {e}")
        return set()

    def _save_executed_orders(self, executed_keys: set):
        try:
            with open(self.executed_orders_file, 'w') as f:
                json.dump(sorted(list(executed_keys)), f, indent=2)
        except Exception as e:  # pragma: no cover
            logger.warning(f"Could not save executed orders file: {e}")

    def run_fresh_backtest(self) -> bool:
        logger.info("Running fresh backtest to get latest signals...")
        try:
            result = subprocess.run([
                sys.executable,
                'complete_comprehensive_backtest.py'
            ], capture_output=True, text=True, timeout=300)
            if result.returncode == 0:
                logger.info("Backtest completed successfully")
                return True
            logger.error(f"Backtest failed: {result.stderr}")
            return False
        except subprocess.TimeoutExpired:
            logger.error("Backtest timed out after 5 minutes")
            return False
        except Exception as e:  # pragma: no cover
            logger.error(f"Error running backtest: {e}")
            return False

    async def execute_trading_session(self, session_type: str) -> bool:
        logger.info(f"Starting {session_type} trading session")
        try:
            if not self.run_fresh_backtest():
                logger.error(f"Skipping {session_type} session due to backtest failure")
                return False

            logger.info(f"Checking for {session_type} signals...")
            signals = check_todays_signals(session_type)
            if not signals:
                logger.info(f"No {session_type} signals found for today")
                return True
            logger.info(f"Found {len(signals)} {session_type} signals")

            if not await self.manual_trader.connect_ib_async():
                logger.error(f"Failed to connect to IB for {session_type} session")
                return False
            try:
                await self.manual_trader.async_sync_portfolio_with_ib()
                orders = self.manual_trader.portfolio_manager.create_combined_orders(signals)
                if not orders:
                    logger.info(f"No executable orders for {session_type} session")
                    return True
                # Idempotent order execution (per date+session+ticker+action)
                today_str = self._market_now().strftime('%Y-%m-%d')
                executed_keys = self._load_executed_orders()
                session_prefix = f"{today_str}|{session_type}"
                filtered_orders = []
                skipped = 0
                for o in orders:
                    key = f"{session_prefix}|{o['ticker']}|{o['action']}"
                    if key in executed_keys:
                        skipped += 1
                        continue
                    filtered_orders.append((o, key))

                logger.info(f"Prepared {len(filtered_orders)} orders (skipped {skipped} already executed duplicates)")
                successful_orders = 0
                for i, (order, key) in enumerate(filtered_orders, 1):
                    logger.info(f"Processing order {i}/{len(filtered_orders)}: {order['ticker']} {order['action']}")
                    if await self.manual_trader.place_order(order, not self.dry_run):
                        successful_orders += 1
                        executed_keys.add(key)
                        self._save_executed_orders(executed_keys)
                    if i < len(filtered_orders):
                        await asyncio.sleep(2)
                logger.info(f"{session_type} session completed: {successful_orders}/{len(filtered_orders)} orders successful (duplicates skipped: {skipped})")
                logger.info(f"{session_type} session completed: {successful_orders}/{len(orders)} orders successful")
                session_summary = {
                    'timestamp': self._market_now().isoformat(),
                    'session_type': session_type,
                    'signals_found': len(signals),
                    'orders_executed': len(orders),
                    'successful_orders': successful_orders,
                    'dry_run': self.dry_run
                }
                log_file = f'trading_sessions_{self._market_now().strftime("%Y%m%d")}.json'
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
                if self.manual_trader.ib:
                    self.manual_trader.ib.disconnect()
                    logger.info("Disconnected from IB")
        except Exception as e:  # pragma: no cover
            logger.error(f"Error in {session_type} trading session: {e}")
            return False

    async def wait_for_next_session(self, next_session: datetime, session_type: str):
        now = self._market_now()
        # Ensure both datetimes are comparable (make next_session aware if needed)
        if getattr(self, 'market_tz', None) and next_session.tzinfo is None:
            next_session = next_session.replace(tzinfo=self.market_tz)
        wait_seconds = (next_session - now).total_seconds()
        if wait_seconds <= 0:
            return
        logger.info(f"Waiting for {session_type} session at {next_session.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"   Time until session: {wait_seconds/3600:.1f} hours")
        update_interval = min(300, wait_seconds / 10)
        # Cap individual sleep slices so shutdown is responsive (max 5s)
        while wait_seconds > 0 and self.running and not self.stop_event.is_set():
            slice_len = min(update_interval, wait_seconds, 5)
            try:
                await asyncio.wait_for(self.stop_event.wait(), timeout=slice_len)
                break  # stop_event set
            except asyncio.TimeoutError:
                wait_seconds -= slice_len
                if wait_seconds > 60 and self.running:
                    logger.info(f"{wait_seconds/60:.0f} minutes until {session_type} session...")

    async def run_daily_cycle(self):
        logger.info("AUTOMATED DAILY TRADER STARTED")
        logger.info(f"Paper Trading: {'ON' if self.paper_trading else 'OFF'}")
        logger.info(f"Dry Run: {'ON' if self.dry_run else 'OFF'}")
        self.current_date = self._market_now().date()
        while self.running:
            try:
                next_session, session_type = self.get_next_trading_session()
                if next_session.date() != self.current_date:
                    logger.info(f"New trading day: {next_session.date().strftime('%Y-%m-%d')}")
                    self.current_date = next_session.date()
                await self.wait_for_next_session(next_session, session_type)
                if not self.running or self.stop_event.is_set():
                    break
                success = await self.execute_trading_session(session_type)
                if session_type == "OPEN":
                    self.today_open_executed = True
                elif session_type == "CLOSE":
                    self.today_close_executed = True
                self._save_persistent_state()
                if not success:
                    logger.warning(f"{session_type} session had issues, but continuing...")
                for _ in range(12):  # up to 60s, responsive to stop
                    if not self.running or self.stop_event.is_set():
                        break
                    try:
                        await asyncio.wait_for(self.stop_event.wait(), timeout=5)
                        break
                    except asyncio.TimeoutError:
                        continue
            except Exception as e:  # pragma: no cover
                logger.error(f"Error in daily cycle: {e}")
                logger.info("Continuing after error...")
                for _ in range(12):
                    if not self.running or self.stop_event.is_set():
                        break
                    try:
                        await asyncio.wait_for(self.stop_event.wait(), timeout=5)
                        break
                    except asyncio.TimeoutError:
                        continue
        logger.info("Automated daily trader stopped")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Automated Daily Trading Script')
    parser.add_argument('--live-trading', action='store_true', help='Use live trading account (default: paper)')
    parser.add_argument('--dry-run', action='store_true', help='Dry run mode - no actual orders placed')
    args = parser.parse_args()
    paper_trading = not args.live_trading
    print("AUTOMATED DAILY TRADER")
    print("=" * 50)
    print(f"Mode: {'Paper Trading' if paper_trading else 'LIVE TRADING'}")
    print(f"Dry Run: {'YES' if args.dry_run else 'NO'}")
    print(f"Capital: ${INITIAL_CAPITAL:,.2f}")  # from config
    print(f"Tickers: {len(TICKERS_CONFIG)}")
    print("\nWARNING: This script will run continuously until CTRL+C")
    print("   It will execute trades automatically at market open/close times")
    if not paper_trading:
        confirm = input("\nLIVE TRADING MODE - Are you sure? (type 'YES' to continue): ")
        if confirm != 'YES':
            print("Cancelled")
            return
    if not args.dry_run:
        confirm = input(f"\nStart automated {'paper' if paper_trading else 'LIVE'} trading? (y/n): ")
        if confirm.lower() != 'y':
            print("Cancelled")
            return
    trader = AutoDailyTrader(paper_trading=paper_trading, dry_run=args.dry_run)
    try:
        asyncio.run(trader.run_daily_cycle())
    except KeyboardInterrupt:
        print("\nStopped by user (CTRL+C)")
    except Exception as e:  # pragma: no cover
        print(f"\nFatal error: {e}")
        logger.error(f"Fatal error: {e}")


if __name__ == "__main__":
    main()
