# 📊 Support & Resistance Trading Strategy System

A comprehensive automated trading system for support/resistance strategies with full backtesting, paper trading, and Interactive Brokers integration.

## 🚀 **QUICK START**

### 🎯 **Automated Trading (Recommended)**
Start the production auto trader that runs continuously:

**Windows Compatible Version (Recommended):**
```bash
# Test mode without executing trades (recommended first)
python production_trader_win.py --dry-run --test-mode

# Paper trading (safe - recommended for production)
python production_trader_win.py

# Test what would happen without executing
python production_trader_win.py --dry-run

# LIVE trading (requires confirmation)
python production_trader_win.py --live-trading
```

**Full-Featured Version (requires UTF-8 terminal):**
```bash
# Paper trading (safe - recommended for first runs)
python production_auto_trader.py

# Test mode without executing trades
python production_auto_trader.py --dry-run

# Quick test with accelerated timing
python production_auto_trader.py --test-mode

# LIVE trading (requires confirmation)
python production_auto_trader.py --live-trading
```

### 📊 **Manual Analysis**
1. **Run Full Backtest**
```bash
# Complete system backtest (all tickers, optimization)
python complete_comprehensive_backtest.py

# Interactive single ticker backtest with full analysis
python runner.py fullbacktest
```

2. **View Results**
```bash
python show_summary.py
```

3. **Generate Paper Trading List**
```bash
python single_trades.py 2025-08-01 2025-08-15 --csv
```

## 🎯 **KEY FEATURES**

- ✅ **Automated Trading** - Start anytime, runs continuously until stopped
- ✅ **Smart Timing** - Waits for market open/close, executes once per session
- ✅ **Comprehensive Backtesting** - 2+ years of data with parameter optimization
- ✅ **Multiple Strategies** - Long and short support/resistance trading
- ✅ **Paper Trading Lists** - Single trades ready for execution
- ✅ **Interactive Charts** - HTML charts with signals and levels
- ✅ **Performance Analytics** - Detailed statistics and trade analysis
- ✅ **Interactive Brokers** - Full live and paper trading integration
- ✅ **Flexible Configuration** - Per-ticker strategy and timing settings
- ✅ **Safety First** - Paper trading default, dry-run mode, confirmations

## 📁 **CORE FILES**

### **🤖 Automated Trading**
- `production_auto_trader.py` - **Production automated trading system**
- `auto_daily_trader.py` - Full-featured daily automation
- `simple_auto_trader.py` - Lightweight auto trader for testing

### **🔧 Main Execution**
- `complete_comprehensive_backtest.py` - **Full system backtest with optimization**
- `runner.py` - Single ticker backtesting (proven reliable)
- `single_trades.py` - **Generate paper trading lists**
- `show_summary.py` - Display comprehensive results

### **📋 Manual Trading**
- `manual_trading.py` - Manual trade execution with IB
- `portfolio_manager.py` - Position and order management
- `check_todays_signals.py` - Check current trading signals

### **⚙️ Core Logic**
- `backtesting_core.py` - Core backtesting functions
- `signal_utils.py` - Support/resistance signal generation
- `simulation_utils.py` - Trade simulation and matching
- `stats_tools.py` - Performance statistics

### **📊 Configuration & Data**
- `config.py` - **System parameters and timing settings**
- `tickers_config.py` - **Per-ticker trading configuration**
- `*_data.csv` - Historical price data
- `complete_comprehensive_backtest_results.json` - Full results

### **📈 Analysis & Tools**
- `comprehensive_trade_summary.py` - Detailed trade analysis
- `paper_trading_list.py` - Interactive paper trading tool
- `plot_utils.py` / `plotly_utils.py` - Chart generation
- `test_config.py` - Validate configuration integration

## 🤖 **AUTOMATED TRADING SYSTEM**

### **🚀 Production Auto Trader**
The `production_auto_trader.py` is a fully automated trading system that:

- **Can start anytime** - Automatically waits for next trading session
- **Morning Session**: Waits for 9:35 AM ET, runs backtest, executes OPEN trades
- **Evening Session**: Waits for 3:55 PM ET, runs backtest, executes CLOSE trades
- **Runs continuously** until stopped with CTRL+C
- **Skips weekends** and major holidays automatically
- **Paper trading by default** - Safe for testing and learning

### **📋 Auto Trading Options**
```bash
# Start paper trading (recommended)
python production_auto_trader.py

# Test without executing trades
python production_auto_trader.py --dry-run

# Quick test with accelerated timing
python production_auto_trader.py --test-mode --dry-run

# Enable detailed logging
python production_auto_trader.py --verbose

# LIVE trading (requires confirmation)
python production_auto_trader.py --live-trading
```

### **🛡️ Safety Features**
- ✅ **Paper trading default** - No real money at risk
- ✅ **Dry run mode** - Test everything without executing
- ✅ **Confirmation prompts** for live trading
- ✅ **Fresh backtests** before each session
- ✅ **One-time execution** per session (no duplicate trades)
- ✅ **Comprehensive logging** with daily log files
- ✅ **Graceful shutdown** on CTRL+C

## 🎮 **USAGE COMMANDS**

### **📊 Backtesting**
```bash
# Full system backtest (all tickers, optimization)
python complete_comprehensive_backtest.py

# Interactive single ticker backtest with full analysis
python runner.py fullbacktest

# Single ticker interactive backtest (basic)
python runner.py

# View comprehensive summary
python show_summary.py

# Detailed trade analysis
python comprehensive_trade_summary.py
```

### **📋 Paper Trading**
```bash
# All trades for date range
python single_trades.py 2025-07-01 2025-08-15

# Long trades only
python single_trades.py 2025-07-01 2025-08-15 long

# Short trades with CSV export
python single_trades.py 2025-07-01 2025-08-15 short --csv

# Interactive paper trading tool
python paper_trading_list.py

# Quick predefined lists
python quick_paper_trading.py
```

### **🤖 Manual Trading**
```bash
# Execute manual trades with IB
python manual_trading.py

# Check today's signals
python check_todays_signals.py

# Test configuration integration
python test_config.py
```

### **🔄 Data Management**
```bash
# Update price data
python data_sync.py

# Today's signals
python signal_alert_today.py
```

## ⚙️ **CONFIGURATION**

The system uses two main configuration files:

### **📊 `config.py` - System Settings**
```python
INITIAL_CAPITAL = 50000           # Total trading capital
MARKET_OPEN_TIME = "09:30"        # NY market open
MARKET_CLOSE_TIME = "16:00"       # NY market close
IB_PAPER_PORT = 7497              # Paper trading port
IB_LIVE_PORT = 7496               # Live trading port
# ... and more timing/execution parameters
```

### **🎯 `tickers_config.py` - Per-Ticker Settings**
```python
tickers = {
    'AAPL': {
        'strategies': ['LONG', 'SHORT'],  # Enable both strategies
        'trade_on': 'OPEN',              # Trade at market open
        'capital': 5000,                 # Dedicated capital
        'conID': 265598,                 # IB contract ID
        'rounding': 0.01,                # Price rounding
    },
    'GOOGL': {
        'strategies': ['LONG'],          # Long only
        'trade_on': 'CLOSE',            # Trade at market close
        'capital': 8000,
        'conID': 208813720,
        'rounding': 0.01,
    },
    # ... add more tickers as needed
}
```

## 📊 **OUTPUT FORMATS**

### **Console Output**
- 🎯 Entry/Exit signals with prices
- 📈 Performance metrics (return, win rate, drawdown)
- 🏆 Best performing tickers and strategies
- 💰 Capital curves and equity progression

### **CSV Exports**
- **Single Trades**: `trade_date,ticker,strategy,action,price,shares`
- **Matched Trades**: Entry/exit pairs with P&L
- **Extended Signals**: All signals with support/resistance levels
- **Optimization Results**: Best parameters per ticker

### **HTML Charts**
- Interactive Plotly charts with price action
- Support/resistance level visualization
- Entry/exit point markers

## 🎯 **STRATEGY OVERVIEW**

### **Support/Resistance Logic**
1. **Identify Levels**: Uses period `p` to find local highs/lows
2. **Signal Confirmation**: Requires `tw` time windows for validation
3. **Entry Rules**: BUY at support, SELL at resistance
4. **Risk Management**: Automatic stop losses and profit targets

### **Trading Strategies**
- **LONG**: Buy at support levels, sell at resistance
- **SHORT**: Short at resistance levels, cover at support
- **Execution**: Market OPEN or CLOSE based on configuration
- **Orders**: LIMIT orders at calculated levels

## 🛠️ **REQUIREMENTS**

```bash
pip install pandas numpy matplotlib yfinance scipy plotly ib_insync markdown2
```

### **Python Packages**
- `pandas` - Data manipulation
- `numpy` - Numerical computations
- `matplotlib` - Basic plotting
- `plotly` - Interactive charts
- `yfinance` - Price data download
- `scipy` - Statistical analysis
- `ib_insync` - Interactive Brokers API
- `markdown2` - Report generation

## 📈 **TYPICAL WORKFLOW**

### **🎯 Automated Trading (Recommended)**
```bash
# 1. Update data and test the system
python data_sync.py
python complete_comprehensive_backtest.py
python show_summary.py

# 2. Test automated trading (dry run) - Windows Compatible
python production_trader_win.py --dry-run --test-mode

# 3. Start paper trading automation - Windows Compatible
python production_trader_win.py

# 4. Monitor logs and performance (Windows)
Get-Content logs\auto_trader_*.log -Tail 20 -Wait
```

### **📊 Manual Analysis & Trading**
```bash
# 1. Initial setup & backtest
python data_sync.py                          # Update data
python complete_comprehensive_backtest.py   # Run full backtest
python runner.py fullbacktest               # Interactive single ticker analysis
python show_summary.py                      # View results

# 2. Generate paper trading lists
python single_trades.py 2025-08-01 2025-08-15 --csv

# 3. Manual execution (optional)
python check_todays_signals.py             # Check signals
python manual_trading.py                   # Execute trades
```

## 🗂️ **LOG FILES & MONITORING**

### **📁 Automated Trading Logs**
- `logs/auto_trader_YYYYMMDD.log` - Daily operation logs
- `logs/sessions_YYYYMMDD.json` - Session results and statistics
- `logs/` directory created automatically

### **📊 Monitoring Commands**
```bash
# View real-time logs
Get-Content logs\auto_trader_*.log -Tail 20 -Wait

# Check session results
python -c "import json; print(json.dumps(json.load(open('logs/sessions_$(Get-Date -Format "yyyyMMdd").json')), indent=2))"

# Validate configuration
python test_config.py
```

## 📚 **DOCUMENTATION & HELP**

- **`HELP.md`** - Comprehensive help guide with all commands
- **`README.md`** - This overview file  
- **`test_config.py`** - Validate system configuration
- **Inline Comments** - Detailed code documentation
- **Error Messages** - Descriptive error handling

## 🚀 **GETTING STARTED CHECKLIST**

1. **📦 Install Requirements**
   ```bash
   pip install pandas numpy matplotlib yfinance scipy plotly ib_insync markdown2
   ```

2. **⚙️ Configure System**
   - Edit `config.py` for capital and timing settings
   - Edit `tickers_config.py` for ticker-specific settings
   - Run `python test_config.py` to validate

3. **📊 Run Initial Backtest**
   ```bash
   python complete_comprehensive_backtest.py
   python runner.py fullbacktest
   python show_summary.py
   ```

4. **🧪 Test Automated Trading (Windows Compatible)**
   ```bash
   python production_trader_win.py --dry-run --test-mode
   ```

5. **🎯 Start Paper Trading (Windows Compatible)**
   ```bash
   python production_trader_win.py
   ```

6. **📈 Monitor & Optimize**
   - Check logs in `logs/` directory
   - Review session results
   - Adjust configuration as needed

---
**💡 Pro Tip**: Always start with `--dry-run` to understand what the system will do before executing real trades!

## 🚨 **IMPORTANT NOTES**

### **🛡️ Trading Safety**
- ✅ **Default to paper trading** - Real money requires explicit confirmation
- ✅ **Start with dry runs** to understand the system
- ✅ **Test thoroughly** with recent data before live trading
- ✅ **Monitor continuously** - Check logs regularly
- ✅ **Use CTRL+C** to stop automated trading gracefully

### **⚙️ Interactive Brokers Setup**
- Paper Trading Account: Port 7497 (default)
- Live Trading Account: Port 7496 (requires --live-trading flag)
- TWS or IB Gateway must be running
- Contract IDs configured in `tickers_config.py`

### **📊 Data Requirements**
- Historical data updated via `data_sync.py`
- Minimum 1+ years of data for reliable backtesting
- Fresh backtests run automatically before each trading session
- ✅ Use proper risk management and position sizing
- ✅ Monitor support/resistance level confirmations

### **Data Requirements**
- Minimum 2 years of historical data
- Daily OHLCV format
- Regular updates via `data_sync.py`

## 🔧 **TROUBLESHOOTING**

| Issue | Solution |
|-------|----------|
| No data found | Run `python data_sync.py` |
| No signals generated | Check date range and ticker config |
| CSV export fails | Verify write permissions |
| Performance slow | Reduce date range or ticker count |

## 📞 **SUPPORT**

- Run any script without arguments for usage examples
- Check `HELP.md` for comprehensive documentation
- Review error messages for specific guidance
- Validate ticker symbols in `tickers_config.py`

---

**🎯 Ready to trade support and resistance levels like a pro!** 📈

*Last Updated: August 11, 2025 - Support/Resistance Trading System v1.0*