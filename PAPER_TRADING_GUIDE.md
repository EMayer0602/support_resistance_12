# 📈 PAPER TRADING GUIDE - Support/Resistance Strategy

## 🎯 **TODAY'S PAPER TRADING WORKFLOW**

### **⏰ TIMING IS EVERYTHING**

The system generates signals based on market data that becomes available **after** market open. Here's the proper timing:

#### **🌅 OPEN Trades (trade_on: "OPEN")**
- **Signal Generation**: 10+ minutes after NY market open (9:40 AM ET or later)
- **Execution Window**: 9:40 AM - 12:00 PM ET
- **Why**: Need actual market prices to generate accurate signals

#### **🌙 CLOSE Trades (trade_on: "CLOSE")**
- **Signal Generation**: 15 minutes before NY market close (3:45 PM ET)
- **Execution Window**: 3:45 PM - 4:00 PM ET
- **Why**: Final signals based on near-closing prices

---

## 🚀 **DAILY TRADING PROCESS**

### **Step 1: Morning Preparation (9:00 AM ET)**
```bash
# Check if you have any OPEN trades today (will be empty until 9:40 AM)
python check_todays_signals.py --trade-on OPEN --time-status
```

### **Step 2: OPEN Trading Session (9:40+ AM ET)**
```bash
# Check for OPEN signals (run after 9:40 AM)
python check_todays_signals.py --trade-on OPEN

# Execute OPEN trades (dry run first)
python manual_trading.py --trade-on OPEN

# Execute for real (after verification)
python manual_trading.py --trade-on OPEN --execute
```

### **Step 3: CLOSE Trading Session (3:45 PM ET)**
```bash
# Check for CLOSE signals
python check_todays_signals.py --trade-on CLOSE

# Execute CLOSE trades (dry run first) 
python manual_trading.py --trade-on CLOSE

# Execute for real
python manual_trading.py --trade-on CLOSE --execute
```

---

## 🔧 **COMPLEX ORDER HANDLING**

The system automatically handles complex order combinations to avoid IB rejections:

### **BUY + COVER Combination**
When you have both BUY (long entry) and COVER (short exit) signals:

1. **Limit COVER**: Only covers existing short positions in portfolio
2. **Calculate BUY**: New long position based on capital allocation  
3. **Combine**: Single BUY order for (COVER shares + BUY shares)

**Example:**
- Current position: -50 shares AAPL (short)
- Signals: BUY 100 shares + COVER short
- Result: BUY 150 shares (50 to cover + 100 new long)

### **SELL + SHORT Combination**
When you have both SELL (long exit) and SHORT (short entry) signals:

1. **Get SELL**: Current long position shares
2. **Calculate SHORT**: New short position based on capital allocation
3. **Combine**: Single SELL order for (long shares + short shares)

**Example:**
- Current position: +75 shares GOOGL (long)
- Signals: SELL long + SHORT 80 shares
- Result: SELL 155 shares (75 long + 80 new short)

---

## 💰 **CAPITAL ALLOCATION**

### **Per-Ticker Capital**
- Total capital divided equally among all tickers
- Each ticker gets: `INITIAL_CAPITAL / number_of_tickers`
- Individual allocations can be customized in `tickers_config.py`

### **Position Sizing**
- **Long positions**: `capital / stock_price` shares
- **Short positions**: `capital / stock_price` shares  
- **Rounding**: Down to whole shares

---

## 🛠️ **INTERACTIVE BROKERS SETUP**

### **Requirements**
1. **TWS or IB Gateway** running
2. **Paper Trading Account** enabled
3. **API connections** allowed
4. **Port 7497** for paper trading

### **Connection Test**
```bash
# Test IB connection (dry run)
python manual_trading.py --force

# This will test connection without executing trades
```

### **Real-Time Data**
- System uses IB real-time bid/ask prices
- Fallback to last price if bid/ask unavailable
- Orders placed as LIMIT orders at real-time prices

---

## 📊 **MONITORING & VALIDATION**

### **Before Each Trade Session**
```bash
# 1. Check current portfolio positions
python portfolio_manager.py

# 2. Verify today's signals
python check_todays_signals.py --time-status

# 3. Run comprehensive backtest to ensure data is current
python complete_comprehensive_backtest.py
```

### **Order Validation**
The system automatically validates:
- ✅ Sufficient shares for SELL orders
- ✅ Sufficient short position for COVER orders  
- ✅ Positive share counts
- ✅ Real-time price availability

---

## 📋 **DAILY CHECKLIST**

### **🌅 Morning (9:30-9:45 AM ET)**
- [ ] TWS/IB Gateway running and connected
- [ ] Portfolio positions synced
- [ ] Wait for 9:40 AM before checking OPEN signals

### **🔥 OPEN Session (9:40+ AM ET)**
- [ ] Check signals: `python check_todays_signals.py --trade-on OPEN`
- [ ] Dry run: `python manual_trading.py --trade-on OPEN`
- [ ] Execute: `python manual_trading.py --trade-on OPEN --execute`

### **🌙 CLOSE Session (3:45 PM ET)**
- [ ] Check signals: `python check_todays_signals.py --trade-on CLOSE`  
- [ ] Dry run: `python manual_trading.py --trade-on CLOSE`
- [ ] Execute: `python manual_trading.py --trade-on CLOSE --execute`

### **📊 End of Day**
- [ ] Review executed trades
- [ ] Update portfolio records
- [ ] Prepare for next day

---

## 🚨 **TROUBLESHOOTING**

### **No Signals Found**
- ✅ Make sure backtest results are current
- ✅ Check if running at correct time (after 9:40 AM for OPEN)
- ✅ Verify tickers are configured for trading today

### **IB Connection Issues**
- ✅ TWS/Gateway running on port 7497 (paper) or 7496 (live)
- ✅ API connections enabled in TWS settings
- ✅ Paper trading account selected

### **Order Rejections**
- ✅ Check available buying power
- ✅ Verify stock is tradeable (not halted)
- ✅ Ensure limit price is reasonable

### **Position Sync Issues**
- ✅ Run portfolio sync: `python manual_trading.py --force`
- ✅ Manually check positions in TWS
- ✅ Update `portfolio_positions.json` if needed

---

## 📈 **EXAMPLE TRADING DAY**

### **Monday, August 11, 2025**

**9:00 AM**: Start TWS, connect to paper trading
```bash
python check_todays_signals.py --time-status
# Shows: "Waiting for OPEN trading session..."
```

**9:45 AM**: Check for OPEN signals
```bash
python check_todays_signals.py --trade-on OPEN
# Shows: Found 3 signals for OPEN trades
```

**9:50 AM**: Execute OPEN trades
```bash
python manual_trading.py --trade-on OPEN --execute
# Places: BUY AAPL, SELL+SHORT GOOGL, individual AMD order
```

**3:45 PM**: Check for CLOSE signals
```bash
python check_todays_signals.py --trade-on CLOSE
# Shows: Found 1 signal for CLOSE trades
```

**3:50 PM**: Execute CLOSE trades
```bash
python manual_trading.py --trade-on CLOSE --execute
# Places: SELL META position
```

---

## 💡 **PRO TIPS**

1. **Always dry run first**: Use scripts without `--execute` flag
2. **Monitor real-time**: Watch TWS during execution
3. **Keep records**: Portfolio positions are auto-saved
4. **Stay flexible**: Market conditions can change rapidly
5. **Test thoroughly**: Start with small positions

---

**🎯 Ready for professional paper trading with your support/resistance strategy!** 📈

*Last Updated: August 11, 2025*
