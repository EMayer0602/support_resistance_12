#!/usr/bin/env python3
"""
Portfolio Position Manager
Tracks current positions and calculates proper order sizes for complex trades

This handles the logic for:
- BUY + COVER combinations (limit cover to existing short positions)
- SELL + SHORT combinations (add long + short positions)
- Position tracking and capital allocation
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Tuple, Optional
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
            'symbol': data['symbol'],
            'conID': data.get('conID'),
            'strategies': strategies,
            'trade_on': data.get('trade_on', 'open').upper(),
            'initialCapitalLong': data.get('initialCapitalLong', 1000),
            'initialCapitalShort': data.get('initialCapitalShort', 1000),
            'order_round_factor': data.get('order_round_factor', ORDER_ROUND_FACTOR),
            'long_enabled': data.get('long', True),
            'short_enabled': data.get('short', True)
        }
    return config

# Convert config format
TICKERS_CONFIG = convert_ticker_config()

class PortfolioManager:
    def __init__(self, portfolio_file='portfolio_positions.json'):
        """Initialize portfolio manager"""
        self.portfolio_file = portfolio_file
        self.positions = {}  # ticker -> shares (positive=long, negative=short)
        self.capital_allocation = {}
        self.load_portfolio()
        self.init_capital_allocation()
    
    def init_capital_allocation(self):
        """Initialize capital allocation per ticker using individual settings"""
        for ticker, config in TICKERS_CONFIG.items():
            # Use individual capital allocations from ticker config
            long_capital = config.get('initialCapitalLong', 1000)
            short_capital = config.get('initialCapitalShort', 1000)
            
            # Store both long and short capital for each ticker
            self.capital_allocation[ticker] = {
                'long': long_capital,
                'short': short_capital,
                'total': long_capital + short_capital,
                'round_factor': config.get('order_round_factor', ORDER_ROUND_FACTOR)
            }
    
    def get_capital_for_strategy(self, ticker: str, strategy: str) -> float:
        """Get capital allocation for specific ticker and strategy"""
        ticker_capital = self.capital_allocation.get(ticker, {})
        if strategy.upper() == 'LONG':
            return ticker_capital.get('long', 1000)
        elif strategy.upper() == 'SHORT':
            return ticker_capital.get('short', 1000)
        return 1000  # Default fallback
    
    def load_portfolio(self):
        """Load current portfolio positions from file"""
        if os.path.exists(self.portfolio_file):
            with open(self.portfolio_file, 'r') as f:
                data = json.load(f)
                self.positions = data.get('positions', {})
                # Convert string keys to int values
                for ticker in self.positions:
                    self.positions[ticker] = int(self.positions[ticker])
        else:
            self.positions = {}
    
    def save_portfolio(self):
        """Save current portfolio positions to file"""
        data = {
            'positions': self.positions,
            'last_updated': datetime.now().isoformat(),
            'total_capital': INITIAL_CAPITAL
        }
        with open(self.portfolio_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def get_position(self, ticker: str) -> int:
        """Get current position for ticker (positive=long, negative=short)"""
        return self.positions.get(ticker, 0)
    
    def update_position(self, ticker: str, shares: int, action: str):
        """Update position after trade execution"""
        current = self.get_position(ticker)
        
        if action == 'BUY':
            self.positions[ticker] = current + shares
        elif action == 'SELL':
            self.positions[ticker] = current - shares
        elif action == 'SHORT':
            self.positions[ticker] = current - shares
        elif action == 'COVER':
            self.positions[ticker] = current + shares
        
        # Clean up zero positions
        if self.positions[ticker] == 0:
            del self.positions[ticker]
        
        self.save_portfolio()
    
    def calculate_shares(self, ticker: str, strategy: str, action: str, price: float) -> int:
        """Calculate number of shares for an action using ticker-specific capital"""
        # If we need price for a new position and it's missing, return 0
        if price is None and action in ("BUY", "SHORT"):
            return 0
        # Get the appropriate capital for this strategy
        capital = self.get_capital_for_strategy(ticker, strategy)
        current_position = self.get_position(ticker)
        round_factor = self.capital_allocation[ticker].get('round_factor', ORDER_ROUND_FACTOR)
        
        if strategy == "LONG":
            if action == "BUY":
                # Calculate shares based on long capital allocation
                shares = int(capital / price)
                # Apply rounding factor if needed
                if round_factor > 1:
                    shares = (shares // round_factor) * round_factor
                return shares
            elif action == "SELL":
                # Sell all long positions
                return max(0, current_position)
        
        elif strategy == "SHORT":
            if action == "SHORT":
                # Calculate shares to short based on short capital allocation
                shares = int(capital / price)
                # Apply rounding factor if needed
                if round_factor > 1:
                    shares = (shares // round_factor) * round_factor
                return shares
            elif action == "COVER":
                # Cover all short positions
                return abs(min(0, current_position))
        
        return 0
    
    def create_combined_orders(self, signals: List[Dict]) -> List[Dict]:
        """
        Create combined orders according to your requirements:
        - BUY + COVER: Limit cover to existing short position, then add buy shares
        - SELL + SHORT: Add long position shares + calculated short shares
        """
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
            
            current_position = self.get_position(ticker)
            
            # Handle BUY + COVER combinations
            if buy_signals and cover_signals:
                buy_signal = buy_signals[0]
                cover_signal = cover_signals[0]
                
                # Step 1: Limit COVER to existing short position
                max_cover = abs(min(0, current_position))  # Only negative positions
                cover_shares = min(max_cover, max_cover)  # Limit to existing short
                
                # Step 2: Calculate BUY shares based on capital
                buy_shares = self.calculate_shares(ticker, 'LONG', 'BUY', buy_signal['price'])
                
                # Step 3: Create single BUY order for total shares
                total_buy_shares = buy_shares + cover_shares
                
                if total_buy_shares > 0:
                    combined_orders.append({
                        'ticker': ticker,
                        'action': 'BUY',
                        'shares': total_buy_shares,
                        'price': buy_signal['price'],
                        'trade_on': buy_signal['trade_on'],
                        'description': f"Combined BUY: {buy_shares} new + {cover_shares} cover",
                        'original_signals': [buy_signal, cover_signal]
                    })
            
            # Handle SELL + SHORT combinations  
            elif sell_signals and short_signals:
                sell_signal = sell_signals[0]
                short_signal = short_signals[0]
                
                # Step 1: Get long position to sell
                long_position = max(0, current_position)
                sell_shares = long_position
                
                # Step 2: Calculate SHORT shares based on capital
                short_shares = self.calculate_shares(ticker, 'SHORT', 'SHORT', short_signal['price'])
                
                # Step 3: Create single SELL order for total shares
                total_sell_shares = sell_shares + short_shares
                
                if total_sell_shares > 0:
                    combined_orders.append({
                        'ticker': ticker,
                        'action': 'SELL',
                        'shares': total_sell_shares,
                        'price': sell_signal['price'],
                        'trade_on': sell_signal['trade_on'],
                        'description': f"Combined SELL: {sell_shares} long + {short_shares} short",
                        'original_signals': [sell_signal, short_signal]
                    })
            
            # Handle individual orders
            else:
                for signal in actions:
                    strategy = 'LONG' if signal['action'] in ['BUY', 'SELL'] else 'SHORT'
                    shares = self.calculate_shares(ticker, strategy, signal['action'], signal['price'])
                    
                    if shares > 0:
                        combined_orders.append({
                            'ticker': signal['ticker'],
                            'action': signal['action'],
                            'shares': shares,
                            'price': signal['price'],
                            'trade_on': signal['trade_on'],
                            'description': f"Individual {signal['action']}",
                            'original_signals': [signal]
                        })
        
        return combined_orders
    
    def print_portfolio_summary(self):
        """Print current portfolio status"""
        print("\nCURRENT PORTFOLIO POSITIONS")
        print("=" * 40)

        if not self.positions:
            print("   No open positions")
            return

        total_value = 0
        for ticker, shares in self.positions.items():
            if shares > 0:
                print(f"   {ticker}: +{shares:,} shares (LONG)")
            else:
                print(f"   {ticker}: {shares:,} shares (SHORT)")

        print(f"\nCapital Allocation:")
        for ticker, capital in self.capital_allocation.items():
            try:
                long_cap = capital.get('long', 0)
                short_cap = capital.get('short', 0)
                total_cap = capital.get('total', long_cap + short_cap)
                round_factor = capital.get('round_factor', 1)
                print(
                    f"   {ticker}: long=${long_cap:,.2f}, short=${short_cap:,.2f}, "
                    f"total=${total_cap:,.2f}, round_factor={round_factor}"
                )
            except Exception:
                # Fallback in case structure changes
                print(f"   {ticker}: {capital}")

        print(f"\nTotal Capital: ${INITIAL_CAPITAL:,.2f}")
    
    def validate_order(self, order: Dict) -> Tuple[bool, str]:
        """Validate an order before execution"""
        ticker = order['ticker']
        action = order['action']
        shares = order['shares']
        current_position = self.get_position(ticker)
        original_signals = order.get('original_signals', [])
        
        # Validation rules
        if shares <= 0:
            return False, "Invalid share count"
        
        if action == 'SELL' and shares > max(0, current_position):
            # Allow combined SELL that includes opening a short position
            has_short_component = any(s.get('action') == 'SHORT' for s in original_signals)
            is_combined = isinstance(order.get('description'), str) and order['description'].startswith('Combined SELL')
            if not (has_short_component and is_combined):
                return False, f"Cannot sell {shares} shares, only have {max(0, current_position)} long"
        
        if action == 'COVER' and shares > abs(min(0, current_position)):
            return False, f"Cannot cover {shares} shares, only have {abs(min(0, current_position))} short"
        
        return True, "Order is valid"

def main():
    """Test the portfolio manager"""
    print("PORTFOLIO POSITION MANAGER")
    print("=" * 40)
    
    pm = PortfolioManager()
    pm.print_portfolio_summary()
    
    # Example: Simulate some positions
    print(f"\nTESTING WITH SAMPLE POSITIONS:")
    pm.positions = {
        'AAPL': 100,    # Long 100 shares
        'GOOGL': -50,   # Short 50 shares
        'AMD': 0        # No position
    }
    pm.print_portfolio_summary()
    
    # Test order creation
    sample_signals = [
        {'ticker': 'AAPL', 'action': 'SELL', 'price': 150.0, 'strategy': 'LONG', 'trade_on': 'OPEN'},
        {'ticker': 'AAPL', 'action': 'SHORT', 'price': 150.0, 'strategy': 'SHORT', 'trade_on': 'OPEN'},
        {'ticker': 'GOOGL', 'action': 'BUY', 'price': 100.0, 'strategy': 'LONG', 'trade_on': 'CLOSE'},
        {'ticker': 'GOOGL', 'action': 'COVER', 'price': 100.0, 'strategy': 'SHORT', 'trade_on': 'CLOSE'},
    ]
    
    print(f"\nTESTING ORDER COMBINATIONS:")
    orders = pm.create_combined_orders(sample_signals)
    
    for i, order in enumerate(orders, 1):
        print(f"\n   Order {i}: {order['ticker']} {order['action']} {order['shares']} @ ${order['price']:.2f}")
        print(f"             {order['description']}")
        valid, msg = pm.validate_order(order)
    print(f"             {'OK' if valid else 'FAIL'} {msg}")

if __name__ == "__main__":
    main()
