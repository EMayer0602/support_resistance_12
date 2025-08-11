#!/usr/bin/env python3
"""
Portfolio Exit Signal Checker
Checks existing positions and generates exit signals when appropriate

This script:
1. Downloads current IB portfolio positions
2. Checks if any existing positions should be closed
3. Generates SELL/COVER signals for positions at profit/loss targets
4. Integrates with existing signal system

Usage:
python check_portfolio_exits.py [--execute-exits]
"""

import asyncio
from ib_insync import *
import json
import os
from datetime import datetime, timedelta
import sys
from typing import Dict, List, Tuple, Optional

# Import our modules
from config import *
from tickers_config import tickers
from portfolio_manager import PortfolioManager
import yfinance as yf

class PortfolioExitChecker:
    def __init__(self, paper_trading=True):
        """Initialize the portfolio exit checker"""
        self.paper_trading = paper_trading
        self.ib = None
        self.portfolio_manager = PortfolioManager()
        
    async def connect_ib(self):
        """Connect to Interactive Brokers"""
        try:
            self.ib = IB()
            port = IB_PAPER_PORT if self.paper_trading else IB_LIVE_PORT
            await self.ib.connectAsync(IB_HOST, port, clientId=IB_CLIENT_ID)
            print(f"✅ Connected to IB {'Paper' if self.paper_trading else 'Live'} Trading")
            return True
            
        except Exception as e:
            print(f"❌ Failed to connect to IB: {e}")
            print(f"   Make sure TWS/IB Gateway is running on port {port}")
            return False
    
    async def download_portfolio_positions(self) -> Dict[str, Dict]:
        """Download current portfolio positions from IB"""
        if not self.ib:
            print("❌ Not connected to IB")
            return {}
        
        try:
            positions = self.ib.positions()
            portfolio_data = {}
            
            print("📊 CURRENT PORTFOLIO POSITIONS")
            print("=" * 50)
            
            if not positions:
                print("📭 No open positions")
                return {}
            
            for pos in positions:
                ticker = pos.contract.symbol
                shares = int(pos.position)
                avg_cost = float(pos.avgCost) if pos.avgCost else 0
                market_price = float(pos.marketPrice) if pos.marketPrice else 0
                market_value = float(pos.marketValue) if pos.marketValue else 0
                unrealized_pnl = float(pos.unrealizedPNL) if pos.unrealizedPNL else 0
                
                if shares != 0:  # Only track non-zero positions
                    position_type = "LONG" if shares > 0 else "SHORT"
                    pnl_percent = (unrealized_pnl / abs(market_value)) * 100 if market_value != 0 else 0
                    
                    portfolio_data[ticker] = {
                        'shares': shares,
                        'avg_cost': avg_cost,
                        'market_price': market_price,
                        'market_value': market_value,
                        'unrealized_pnl': unrealized_pnl,
                        'pnl_percent': pnl_percent,
                        'position_type': position_type
                    }
                    
                    pnl_emoji = "🟢" if unrealized_pnl >= 0 else "🔴"
                    print(f"{pnl_emoji} {ticker}: {shares:+d} shares ({position_type})")
                    print(f"   Cost: ${avg_cost:.2f} | Current: ${market_price:.2f}")
                    print(f"   P&L: ${unrealized_pnl:+.2f} ({pnl_percent:+.1f}%)")
            
            # Update portfolio manager with current positions
            ib_positions = {ticker: data['shares'] for ticker, data in portfolio_data.items()}
            self.portfolio_manager.positions = ib_positions
            self.portfolio_manager.save_portfolio()
            
            return portfolio_data
            
        except Exception as e:
            print(f"❌ Error downloading portfolio: {e}")
            return {}
    
    def check_exit_conditions(self, portfolio_data: Dict[str, Dict]) -> List[Dict]:
        """Check if any positions meet STRATEGY-BASED exit conditions ONLY"""
        exit_signals = []
        
        print(f"\n📈 STRATEGY EXIT SIGNAL ANALYSIS")
        print("=" * 50)
        print("🚨 NO STOP LOSS OR PROFIT TARGETS - STRATEGY SIGNALS ONLY!")
        print("=" * 50)
        
        if not portfolio_data:
            print("📊 NO POSITIONS TO CHECK")
            return exit_signals
        
        try:
            # Get today's strategy signals for both sessions
            from check_todays_signals import check_todays_signals
            
            # Check both OPEN and CLOSE session signals
            for session in ['OPEN', 'CLOSE']:
                try:
                    strategy_signals = check_todays_signals(session)
                    if not strategy_signals:
                        print(f"   📅 No {session} strategy signals today")
                        continue
                    
                    print(f"\n📊 CHECKING {session} SESSION STRATEGY SIGNALS:")
                    
                    for signal in strategy_signals:
                        ticker = signal.get('ticker', '')
                        action = signal.get('action', '')
                        strategy = signal.get('strategy', '')
                        
                        if ticker in portfolio_data:
                            position = portfolio_data[ticker]
                            shares = position['shares']
                            current_price = position['market_price']
                            position_type = position['position_type']
                            pnl_percent = position['pnl_percent']
                            
                            should_exit = False
                            exit_reason = ""
                            
                            # Check for strategy-based exits only
                            if position_type == "LONG":
                                if action == "SELL" and strategy in ["LONG", "SHORT"]:
                                    should_exit = True
                                    exit_reason = f"STRATEGY EXIT: {strategy} {action} ({session})"
                            
                            elif position_type == "SHORT":
                                if action == "BUY" and strategy in ["LONG", "SHORT"]:
                                    should_exit = True
                                    exit_reason = f"STRATEGY EXIT: {strategy} {action} ({session})"
                            
                            if should_exit:
                                # Determine exit action
                                exit_action = "SELL" if position_type == "LONG" else "COVER"
                                
                                exit_signal = {
                                    'ticker': ticker,
                                    'action': exit_action,
                                    'shares': abs(shares),
                                    'price': current_price,
                                    'reason': exit_reason,
                                    'current_pnl': position['unrealized_pnl'],
                                    'pnl_percent': pnl_percent,
                                    'position_type': position_type,
                                    'trade_on': 'IMMEDIATE',
                                    'signal_type': 'STRATEGY_EXIT',
                                    'session': session,
                                    'strategy_signal': signal
                                }
                                
                                exit_signals.append(exit_signal)
                                
                                print(f"🎯 {ticker}: {exit_action} {abs(shares)} shares")
                                print(f"   💡 {exit_reason}")
                                print(f"   💰 Price: ${current_price:.2f}")
                                print(f"   📊 Current P&L: ${position['unrealized_pnl']:+.2f} ({pnl_percent:+.1f}%)")
                            else:
                                print(f"⏳ {ticker}: No strategy exit signal (P&L: {pnl_percent:+.1f}%)")
                        else:
                            print(f"   📈 {ticker}: No current position for {action} signal")
                            
                except Exception as e:
                    print(f"   ❌ ERROR checking {session} signals: {e}")
            
            if not exit_signals:
                print("\n✅ NO STRATEGY EXIT SIGNALS FOUND")
                print("📈 All positions will be maintained until strategy signals exit")
                print("💡 Remember: No stop losses or profit targets - pure strategy trading!")
                
                # Show current positions for reference
                print(f"\n📊 CURRENT POSITIONS (maintained):")
                for ticker, position in portfolio_data.items():
                    shares = position['shares']
                    pnl_percent = position['pnl_percent']
                    position_type = position['position_type']
                    pnl_emoji = "🟢" if position['unrealized_pnl'] >= 0 else "🔴"
                    print(f"{pnl_emoji} {ticker}: {position_type} {abs(shares)} shares ({pnl_percent:+.1f}%)")
            
        except Exception as e:
            print(f"❌ ERROR checking strategy exit conditions: {e}")
        
        return exit_signals
    
    def save_exit_signals(self, exit_signals: List[Dict]):
        """Save exit signals to file for integration with other systems"""
        if exit_signals:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"exit_signals_{timestamp}.json"
            
            with open(filename, 'w') as f:
                json.dump(exit_signals, f, indent=2)
            
            print(f"\n💾 Exit signals saved to: {filename}")
        
        # Also save to standard location for integration
        with open('todays_exit_signals.json', 'w') as f:
            json.dump(exit_signals, f, indent=2)
    
    async def execute_exit_signals(self, exit_signals: List[Dict]) -> bool:
        """Execute exit signals immediately (if requested)"""
        if not exit_signals:
            print("📭 No exit signals to execute")
            return True
        
        print(f"\n🚀 EXECUTING {len(exit_signals)} EXIT SIGNALS")
        print("=" * 50)
        
        try:
            from manual_trading import ManualTrader
            
            # Use manual trader to execute
            trader = ManualTrader(paper_trading=self.paper_trading)
            if not await trader.connect_ib():
                return False
            
            successful = 0
            for signal in exit_signals:
                print(f"📋 Executing: {signal['action']} {signal['shares']} {signal['ticker']}")
                print(f"   Reason: {signal['reason']}")
                
                # Create order format expected by manual trader
                order = {
                    'ticker': signal['ticker'],
                    'action': signal['action'],
                    'shares': signal['shares'],
                    'price': signal['price'],
                    'description': f"EXIT: {signal['reason']}"
                }
                
                if await trader.place_order(order, execute=True):
                    successful += 1
                    print(f"✅ {signal['ticker']} {signal['action']} executed")
                else:
                    print(f"❌ {signal['ticker']} {signal['action']} failed")
                
                # Brief pause between orders
                await asyncio.sleep(3)
            
            print(f"\n📊 Exit Results: {successful}/{len(exit_signals)} orders executed")
            return successful > 0
            
        except Exception as e:
            print(f"❌ Error executing exit signals: {e}")
            return False
    
    async def run_exit_check(self, execute_exits=False):
        """Main function to check for portfolio exits"""
        print("🎯 PORTFOLIO EXIT SIGNAL CHECKER")
        print("=" * 50)
        print(f"Mode: {'Paper' if self.paper_trading else 'LIVE'} Trading")
        print(f"Execute: {'YES' if execute_exits else 'DRY RUN'}")
        
        # Connect to IB
        if not await self.connect_ib():
            return
        
        try:
            # Download current positions
            portfolio_data = await self.download_portfolio_positions()
            
            if not portfolio_data:
                print("📭 No positions to analyze")
                return
            
            # Check for exit conditions
            exit_signals = self.check_exit_conditions(portfolio_data)
            
            # Save signals
            self.save_exit_signals(exit_signals)
            
            if exit_signals:
                print(f"\n📈 FOUND {len(exit_signals)} EXIT SIGNALS")
                
                if execute_exits:
                    await self.execute_exit_signals(exit_signals)
                else:
                    print("🔍 DRY RUN: Use --execute-exits to place orders")
                    print("\nExit signals saved for manual review or integration")
            else:
                print("✅ No exit signals generated - all positions within targets")
        
        finally:
            if self.ib:
                self.ib.disconnect()
                print("🔌 Disconnected from IB")

async def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Check portfolio for exit signals')
    parser.add_argument('--execute-exits', action='store_true',
                       help='Execute exit orders immediately')
    parser.add_argument('--live-trading', action='store_true',
                       help='Use live trading account (default: paper)')
    
    args = parser.parse_args()
    
    # Safety check for live trading
    if args.live_trading and args.execute_exits:
        print("⚠️  WARNING: LIVE TRADING WITH EXECUTION ENABLED")
        confirm = input("Type 'LIVE EXIT TRADES' to confirm: ")
        if confirm != 'LIVE EXIT TRADES':
            print("❌ Cancelled")
            return
    
    checker = PortfolioExitChecker(paper_trading=not args.live_trading)
    await checker.run_exit_check(execute_exits=args.execute_exits)

if __name__ == "__main__":
    asyncio.run(main())
