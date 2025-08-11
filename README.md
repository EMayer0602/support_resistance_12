# 📊 Support & Resistance Trading Strategy System

A comprehensive backtesting and paper trading system for support/resistance trading strategies with Interactive Brokers integration.

## 🚀 **QUICK START**

### 1. **Run Full Backtest**
```bash
python complete_comprehensive_backtest.py
```

### 2. **View Results**
```bash
python show_summary.py
```

### 3. **Generate Paper Trading List**
```bash
python single_trades.py 2025-08-01 2025-08-15 --csv
```

## 🎯 **KEY FEATURES**

- ✅ **Comprehensive Backtesting** - 2+ years of data with parameter optimization
- ✅ **Multiple Strategies** - Long and short support/resistance trading
- ✅ **Paper Trading Lists** - Single trades ready for execution
- ✅ **Interactive Charts** - HTML charts with signals and levels
- ✅ **Performance Analytics** - Detailed statistics and trade analysis
- ✅ **Interactive Brokers** - Ready for live trading integration
- ✅ **Flexible Configuration** - Per-ticker strategy and timing settings

## 📁 **CORE FILES**

### **🔧 Main Execution**
- `complete_comprehensive_backtest.py` - **Full system backtest with optimization**
- `runner.py` - Single ticker backtesting (proven reliable)
- `single_trades.py` - **Generate paper trading lists**
- `show_summary.py` - Display comprehensive results

### **⚙️ Core Logic**
- `backtesting_core.py` - Core backtesting functions
- `signal_utils.py` - Support/resistance signal generation
- `simulation_utils.py` - Trade simulation and matching
- `stats_tools.py` - Performance statistics

### **📊 Configuration & Data**
- `tickers_config.py` - **Trading configuration (strategies, timing)**
- `config.py` - System parameters
- `*_data.csv` - Historical price data
- `complete_comprehensive_backtest_results.json` - Full results

### **📈 Analysis & Tools**
- `comprehensive_trade_summary.py` - Detailed trade analysis
- `paper_trading_list.py` - Interactive paper trading tool
- `plot_utils.py` / `plotly_utils.py` - Chart generation
- `MultiTradingIB25_ID_E.py` - Interactive Brokers integration

## 🎮 **USAGE COMMANDS**

### **📊 Backtesting**
```bash
# Full system backtest (all tickers, optimization)
python complete_comprehensive_backtest.py

# Single ticker interactive backtest
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

### **🔄 Data Management**
```bash
# Update price data
python data_sync.py

# Today's signals
python signal_alert_today.py
```

## ⚙️ **CONFIGURATION**

Edit `tickers_config.py` to configure trading:

```python
TICKERS_CONFIG = {
    'AAPL': {
        'strategies': ['LONG', 'SHORT'],  # Enable strategies
        'trade_on': 'OPEN',              # OPEN or CLOSE
    },
    'GOOGL': {
        'strategies': ['LONG'],          # Long only
        'trade_on': 'CLOSE',
    },
    # Add more tickers...
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

### **1. Initial Setup & Backtest**
```bash
python data_sync.py                          # Update data
python complete_comprehensive_backtest.py   # Run full backtest
python show_summary.py                      # View results
```

### **2. Paper Trading**
```bash
python single_trades.py 2025-08-01 2025-08-15 --csv  # Generate trade list
# Import CSV into paper trading platform
```

### **3. Live Trading** (Optional)
```bash
python signal_alert_today.py               # Check today's signals
python MultiTradingIB25_ID_E.py           # Execute via IB
```

## 📚 **DOCUMENTATION**

- **`HELP.md`** - Comprehensive help guide with all commands
- **`README.md`** - This overview file
- **Inline Comments** - Detailed code documentation
- **Error Messages** - Descriptive error handling

## 🚨 **IMPORTANT NOTES**

### **Before Trading**
- ✅ Backtest thoroughly with recent data
- ✅ Start with paper trading to validate signals
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