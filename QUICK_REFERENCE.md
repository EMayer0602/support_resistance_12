# 🚀 QUICK REFERENCE - Support/Resistance Trading System

## 📋 **MOST COMMON COMMANDS**

### **🎯 Essential Commands (Start Here)**
```bash
# 1. Run full backtest system
python complete_comprehensive_backtest.py

# 2. View all results summary  
python show_summary.py

# 3. Generate paper trading list for recent period
python single_trades.py 2025-08-01 2025-08-15 --csv
```

### **📊 Backtesting & Analysis**
```bash
python runner.py                           # Single ticker backtest (interactive)
python show_summary.py                     # View comprehensive summary
python comprehensive_trade_summary.py      # Detailed trade breakdown
```

### **📋 Paper Trading Lists**
```bash
# Generate trade lists for specific date ranges
python single_trades.py 2025-07-01 2025-08-15              # All trades
python single_trades.py 2025-07-01 2025-08-15 long         # Long only
python single_trades.py 2025-07-01 2025-08-15 short --csv  # Short to CSV

# Interactive tools
python paper_trading_list.py               # Interactive date/filter selection
python quick_paper_trading.py              # Quick predefined lists
```

### **🔄 Data & Maintenance**
```bash
python data_sync.py                        # Update price data
python signal_alert_today.py               # Check today's signals
```

---

## 📊 **OUTPUT EXAMPLES**

### **Console Summary Output**
```
📊 COMPREHENSIVE BACKTEST SUMMARY
==================================
🎯 Total Tickers: 14
📅 Period: 2023-01-01 to 2025-08-11

🏆 TOP PERFORMERS:
   1. NVDA LONG  - 284.5% return (8.2% win rate)
   2. TSLA SHORT - 156.3% return (12.4% win rate)
   3. AAPL LONG  - 89.7% return (15.6% win rate)
```

### **Paper Trading List Output**
```
📋 SINGLE TRADE LIST FOR PAPER TRADING
📅 Period: 2025-08-01 to 2025-08-15
🎯 Total Trade Actions: 12

#   Date         Ticker Strategy Action Type   Price $   Shares
1   2025-08-04   AAPL   LONG     BUY    LIMIT  204.46    23
2   2025-08-07   AMD    LONG     BUY    LIMIT  166.84    146
3   2025-08-08   GOOGL  LONG     SELL   LIMIT  201.42    36
```

### **CSV Export Format**
```csv
trade_date,ticker,strategy,action,order_type,price,shares,trade_on
2025-08-04,AAPL,LONG,BUY,LIMIT,204.46,23,OPEN
2025-08-07,AMD,LONG,BUY,LIMIT,166.84,146,OPEN
2025-08-08,GOOGL,LONG,SELL,LIMIT,201.42,36,OPEN
```

---

## ⚙️ **KEY CONFIGURATION**

### **Main Config File: `tickers_config.py`**
```python
TICKERS_CONFIG = {
    'AAPL': {
        'strategies': ['LONG', 'SHORT'],  # Which strategies to run
        'trade_on': 'OPEN',              # OPEN or CLOSE execution
    },
    'GOOGL': {
        'strategies': ['LONG'],          # Long only
        'trade_on': 'CLOSE',            # Close execution
    },
}
```

### **Add New Tickers**
1. Add to `tickers_config.py`
2. Run `python data_sync.py` to download data
3. Run `python complete_comprehensive_backtest.py` to analyze

---

## 🎯 **QUICK WORKFLOW**

### **New User Setup (First Time)**
```bash
# 1. Download data
python data_sync.py

# 2. Run full backtest  
python complete_comprehensive_backtest.py

# 3. View results
python show_summary.py
```

### **Daily Paper Trading**
```bash
# Generate today's trade list
python single_trades.py 2025-08-11 2025-08-16 --csv

# Check signals
python signal_alert_today.py
```

### **Weekly Review**
```bash
# Check recent performance
python single_trades.py 2025-08-04 2025-08-11

# Detailed analysis
python comprehensive_trade_summary.py
```

---

## 🚨 **TROUBLESHOOTING**

| Problem | Quick Fix |
|---------|-----------|
| "No data found" | `python data_sync.py` |
| "No trades in period" | Try wider date range |
| CSV won't save | Check file permissions |
| Slow performance | Use shorter date ranges |

---

## 📱 **COMMAND SHORTCUTS**

Save these as batch files (.bat) for Windows:

**`run_backtest.bat`**
```batch
python complete_comprehensive_backtest.py
python show_summary.py
pause
```

**`paper_trades.bat`**
```batch
python single_trades.py 2025-08-01 2025-08-15 --csv
pause
```

**`update_data.bat`**
```batch
python data_sync.py
pause
```

---

## 📞 **HELP**

- 📖 **Full Documentation**: See `HELP.md`
- 🎮 **Command Help**: Run any script without arguments
- 🔧 **Examples**: `python single_trades.py` shows usage examples

---

*🎯 Keep this reference handy for quick access to all commands!*
