# 📊 Support/Resistance Trading Strategy System - HELP GUIDE

## 🎯 **OVERVIEW**

This is a comprehensive backtesting and paper trading system for support/resistance trading strategies. The system analyzes stock price data, identifies support and resistance levels, generates trading signals, and provides detailed performance analytics.

---

## 🏗️ **PROGRAM STRUCTURE**

### **Core Components**

#### 📈 **Data & Configuration Files**
- `tickers_config.py` - Trading configuration (tickers, strategies, trade timing)
- `config.py` - System configuration and parameters
- `*_data.csv` - Historical price data for each ticker
- `*_chart.html` - Interactive price charts with signals

#### 🔧 **Core Trading Logic**
- `runner.py` - Main backtesting engine (proven, reliable)
- `backtesting_core.py` - Core backtesting functions
- `signal_utils.py` - Support/resistance signal generation
- `simulation_utils.py` - Trade simulation and matching
- `stats_tools.py` - Performance statistics calculations

#### 📊 **Analysis & Visualization**
- `plot_utils.py` - Chart generation and visualization
- `plotly_utils.py` - Interactive Plotly charts
- `print_utils.py` - Formatted output utilities

#### 🚀 **Execution Scripts**
- `complete_comprehensive_backtest.py` - Full system backtest with optimization
- `show_summary.py` - Display backtest summaries
- `comprehensive_trade_summary.py` - Detailed trade analysis
- `single_trades.py` - Generate paper trading lists
- `paper_trading_list.py` - Interactive paper trading tool
- `quick_paper_trading.py` - Quick predefined trade lists

#### 📁 **Output Files**
- `opt_long_*.csv` / `opt_short_*.csv` - Optimal parameters per ticker
- `extended_long_*.csv` / `extended_short_*.csv` - Extended signals with parameters
- `trades_long_*.csv` / `trades_short_*.csv` - Matched trade pairs
- `complete_comprehensive_backtest_results.json` - Full backtest results

---

## 🎮 **USAGE COMMANDS**

### **1. 🔍 Basic Backtesting**

#### Run Single Ticker Backtest
```bash
python runner.py
# Interactive: Select ticker and strategy
```

#### Run All Tickers Comprehensive Backtest
```bash
python complete_comprehensive_backtest.py
# Runs full optimization and analysis for all configured tickers
```

### **2. 📊 View Results & Analytics**

#### Show Summary for All Tickers
```bash
python show_summary.py
# Displays comprehensive backtest summary with key metrics
```

#### Detailed Trade Analysis
```bash
python comprehensive_trade_summary.py
# Shows detailed trade breakdown by ticker and strategy
```

### **3. 📋 Paper Trading Lists**

#### Generate Single Trades (Recommended for Paper Trading)
```bash
# All trades for date range
python single_trades.py 2025-07-01 2025-08-15

# Long trades only
python single_trades.py 2025-07-01 2025-08-15 long

# Short trades only with CSV export
python single_trades.py 2025-07-01 2025-08-15 short --csv

# Show help and examples
python single_trades.py
```

#### Interactive Paper Trading Tool
```bash
python paper_trading_list.py
# Interactive date range selection and filtering
```

#### Quick Predefined Lists
```bash
python quick_paper_trading.py
# Generates common date range trade lists
```

### **4. 🛠️ Data Management**

#### Download/Update Data
```bash
python data_sync.py
# Downloads latest price data for all tickers
```

#### Signal Generation
```bash
python signal_utils.py
# Standalone signal generation and testing
```

---

## 📊 **OUTPUT FORMATS**

### **Console Output**
- 🎯 **Entry/Exit Signals**: BUY/SELL/SHORT/COVER with prices
- 📈 **Performance Metrics**: Total return, win rate, max drawdown
- 🏆 **Rankings**: Best performing tickers and strategies
- 💰 **Capital Curves**: Equity progression over time

### **CSV Exports**
- **Single Trades**: `trade_date,ticker,strategy,action,order_type,price,shares`
- **Matched Trades**: Entry/exit pairs with P&L calculations
- **Extended Signals**: All signals with support/resistance levels
- **Optimization Results**: Best parameters per ticker/strategy

### **HTML Charts**
- Interactive Plotly charts with price action
- Support/resistance level visualization
- Entry/exit point markers
- Technical indicators overlay

---

## ⚙️ **CONFIGURATION**

### **Ticker Configuration (`tickers_config.py`)**
```python
TICKERS_CONFIG = {
    'AAPL': {
        'strategies': ['LONG', 'SHORT'],  # Enabled strategies
        'trade_on': 'OPEN',              # OPEN or CLOSE execution
    },
    # ... more tickers
}
```

### **Strategy Parameters**
- **p**: Support/resistance period (3-5 typical)
- **tw**: Time window for signal confirmation (1-3 typical)
- **capital**: Starting capital allocation per ticker
- **commission**: Trading costs per transaction

---

## 🎯 **TYPICAL WORKFLOW**

### **1. Initial Setup**
```bash
# Update data
python data_sync.py

# Run full backtest
python complete_comprehensive_backtest.py

# View results
python show_summary.py
```

### **2. Paper Trading Preparation**
```bash
# Generate recent trades for paper trading
python single_trades.py 2025-08-01 2025-08-15 --csv

# Or use interactive tool
python paper_trading_list.py
```

### **3. Live Trading Integration**
```bash
# Check today's signals
python signal_alert_today.py

# Execute via Interactive Brokers
python MultiTradingIB25_ID_E.py
```

---

## 📈 **STRATEGY LOGIC**

### **Support/Resistance Detection**
1. **Period Analysis**: Uses `p` periods to identify local highs/lows
2. **Level Confirmation**: Requires `tw` time windows for signal validation
3. **Signal Generation**: BUY at support, SELL at resistance
4. **Risk Management**: Stop losses and profit targets

### **Entry/Exit Rules**
- **LONG Strategy**: BUY at support levels, SELL at resistance
- **SHORT Strategy**: SHORT at resistance levels, COVER at support
- **Execution Timing**: Market OPEN or CLOSE based on configuration
- **Order Types**: LIMIT orders at calculated levels

---

## 🚨 **IMPORTANT NOTES**

### **Data Requirements**
- Minimum 2 years of historical data recommended
- Daily OHLCV format required
- Automatic data updates via `data_sync.py`

### **Paper Trading**
- Use `single_trades.py` for paper trading platforms
- LIMIT orders recommended at support/resistance levels
- Monitor signal confirmation before execution

### **Live Trading**
- Backtest thoroughly before live implementation
- Start with paper trading to validate signals
- Use proper risk management and position sizing

---

## 🔧 **TROUBLESHOOTING**

### **Common Issues**
1. **No Data**: Run `python data_sync.py` first
2. **No Signals**: Check ticker configuration and date ranges
3. **Performance Issues**: Reduce date range or ticker count
4. **CSV Export**: Ensure write permissions in directory

### **Getting Help**
- Run any script without arguments for usage examples
- Check error messages for specific issues
- Verify ticker symbols in `tickers_config.py`

---

## 📋 **QUICK REFERENCE**

| Task | Command |
|------|---------|
| Full Backtest | `python complete_comprehensive_backtest.py` |
| View Summary | `python show_summary.py` |
| Paper Trading List | `python single_trades.py START END [long\|short] [--csv]` |
| Update Data | `python data_sync.py` |
| Interactive Trading | `python paper_trading_list.py` |
| Today's Signals | `python signal_alert_today.py` |

---

*Last Updated: August 11, 2025*
*Support/Resistance Trading Strategy System v1.0*
