#!/usr/bin/env python3
"""
Quick Paper Trading List - Predefined Date Ranges
Example usage for common date ranges
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from paper_trading_list import load_trade_data, extract_trades_for_paper_trading, print_paper_trading_list, save_to_csv
from datetime import datetime, timedelta

def show_recent_trades(days_back=30):
    """Show trades from the last N days"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    
    data = load_trade_data()
    if not data:
        return
    
    trades = extract_trades_for_paper_trading(data, start_date, end_date)
    print_paper_trading_list(trades, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
    
    return trades

def show_trades_for_month(year, month):
    """Show trades for a specific month"""
    start_date = datetime(year, month, 1)
    if month == 12:
        end_date = datetime(year + 1, 1, 1) - timedelta(days=1)
    else:
        end_date = datetime(year, month + 1, 1) - timedelta(days=1)
    
    data = load_trade_data()
    if not data:
        return
    
    trades = extract_trades_for_paper_trading(data, start_date, end_date)
    print_paper_trading_list(trades, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
    
    return trades

def show_profitable_trades_only(start_date_str, end_date_str):
    """Show only profitable trades in date range"""
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
    
    data = load_trade_data()
    if not data:
        return
    
    trades = extract_trades_for_paper_trading(data, start_date, end_date, min_pnl=0.01)
    print_paper_trading_list(trades, start_date_str, end_date_str)
    
    return trades

if __name__ == "__main__":
    print("🚀 QUICK PAPER TRADING EXAMPLES")
    print("="*50)
    
    print("\n1️⃣ RECENT TRADES (Last 30 days):")
    show_recent_trades(30)
    
    print("\n2️⃣ JULY 2025 TRADES:")
    show_trades_for_month(2025, 7)
    
    print("\n3️⃣ PROFITABLE TRADES ONLY (2025-06-01 to 2025-08-08):")
    show_profitable_trades_only('2025-06-01', '2025-08-08')
