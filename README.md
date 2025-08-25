# Support & Resistance Trading Strategy System

A comprehensive automated trading system for support/resistance strategies with full backtesting, paper trading, and Interactive Brokers integration.

Recent Enhancements (August 2025):
- Session grace windows (OPEN_SESSION_GRACE_MIN / CLOSE_SESSION_GRACE_MIN)
- Backtest retry & delay (BACKTEST_MAX_RETRIES / BACKTEST_RETRY_DELAY_SEC)
- IB heartbeat & auto reconnect (IB_HEARTBEAT_SEC / IB_RECONNECT_ON_TIMEOUT)
- Strategy-exit-only mode (USE_STRATEGY_EXITS_ONLY)
- Rolling 14‑day trade list generation
- Prevent same-day exit+reentry (one action per symbol per day)
- Real-time OPEN price usage + end-of-day OHLC reconciliation
- Deduplicated backtest runs & safe session skip logic
- Clear separation of ENTRY vs EXIT signals in execution logs
- Windows-safe console output (ASCII only in runtime scripts)
- Unified backtest engine across `runner.py` & `complete_comprehensive_backtest.py`
- Parameter grid now driven entirely by config (P_RANGE, TW_RANGE, FORCE_TW)
- Data slicing controls (backtesting_begin / backtesting_end / trade_years) with override flags
- Extended signal table + Matched trade table printed with full headers (console & CSV)
- Artificial close handling (forced flatten) with correct commission & PnL attribution
- Equity curve diagnostics (tail(5) + final capital comparison) in console summary
- Strict trade-day logic: trade window (tw) based scheduling, NY trading days only
- Robustness & parsimony scoring (OPT_* flags) to select stable, low-complexity parameter sets
- Distinct marking of artificially closed positions (ArtClose flag) with aggregated summary
 - Signal checker (`check_todays_signals.py`) now enriches runner-derived signals with optimized parameters (p, tw) pulled from `runner_fullbacktest_results.json` so OPEN/CLOSE signal listings display the exact backtest configuration

## QUICK START

### Automated Trading (Recommended)
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

### Manual Analysis
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

## KEY FEATURES

- ✅ **Automated Trading** - Start anytime, runs continuously until stopped
- ✅ **Smart Timing** - Waits for market open/close, executes once per session
- ✅ **Comprehensive Backtesting** - Multi-year historical tests with parameter grid search
- ✅ **Config-Driven Optimization** - P & TW ranges + optional forced TW (FORCE_TW)
- ✅ **Parsimony & Robustness Scoring** - OPT_MIN_TRADES / OPT_TOLERANCE_PCT / OPT_PARSIMONY_TW / OPT_PREFER_MORE_TRADES / OPT_TW_PENALTY
- ✅ **Extended Signals & Matched Trades** - Rich console tables + CSV exports (with ArtClose flag)
- ✅ **Artificial Close Accounting** - Forced flattening applies entry-side commission only & flags trade
- ✅ **Equity Curve Diagnostics** - tail(5) snapshot + final capital match check
- ✅ **Dual Equity Curves** - Close-marked vs Execution-sensitive variants
- ✅ **Strict Trade Day Logic** - tw-based forward validation on NY trading days
- ✅ **Multiple Strategies** - Long & short support/resistance
- ✅ **Interactive Charts** - Plotly HTML with annotated entries/exits & levels
- ✅ **Performance Analytics** - Drawdown, win rate, trade counts, parameter stats
- ✅ **Interactive Brokers** - Live & paper trading integration
- ✅ **Flexible Configuration** - Global + per-ticker (capital, rounding, trade_on)
- ✅ **Safety First** - Paper trading default, dry-run mode, confirmations

## BACKTESTING CONFIG & DATA SLICING

Key controls (see `config_new.py`):

| Setting | Purpose | Typical Use |
|---------|---------|-------------|
| trade_years | Limit lookback to last N years | Faster iteration (e.g. 1 year) |
| backtesting_begin / backtesting_end (%) | Percentage slice of available data | Exclude early noisy data / reserve tail for validation |
| USE_FULL_DATA | Ignore slicing & years entirely | Full-history robustness run |
| SLICE_FOR_OPTIMIZATION_ONLY | Slice only during parameter search; simulate on full set | Avoid biasing final equity |
| FORCE_FLAT_AT_END | Force-close any open positions on final bar | Clean final equity number |
| P_RANGE / TW_RANGE | Parameter grids for level period & trade window | Expand / narrow search space |
| FORCE_TW | Lock trade window to a single value | Sensitivity isolation |
| EXTENDED_VERBOSE | Print extended signals with auto-filled prices | Debug & auditing |

Workflow examples:
1. Tune parameters quickly: set a narrower P_RANGE / TW_RANGE and a smaller `trade_years` (e.g. 0.5) with SLICE_FOR_OPTIMIZATION_ONLY=True.
2. Final validation: set USE_FULL_DATA=True and FORCE_FLAT_AT_END=True to verify robustness & clean equity end-state.

## OPTIMIZATION PARSIMONY & SELECTION
Candidate scoring applies filters & preferences:
1. Discard if trades < OPT_MIN_TRADES.
2. Compute baseline performance metric (final_capital).
3. Retain alternatives within OPT_TOLERANCE_PCT of best.
4. Prefer lower TW if OPT_PARSIMONY_TW=True.
5. Break ties by higher trade count if OPT_PREFER_MORE_TRADES=True.
6. Optional complexity penalty: final_cap - (OPT_TW_PENALTY * tw).

This yields stable, minimally complex parameter sets resistant to overfitting.

## EXTENDED & MATCHED TRADE OUTPUTS
Two complementary views are produced per ticker:
1. Extended Signals: Every qualifying raw signal (including those not forming a completed trade yet) with levels, timestamps, and auto-filled price columns.
2. Matched Trades: Executed entry/exit pairs, PnL, fees, holding period, parameter context, plus ArtClose flag when forced closed.

Console prints nicely formatted tables (headers once, wide columns trimmed) and CSV/JSON outputs retain full precision. Artificially closed trades are aggregated into a summary (count, gross PnL, commission) for transparency.

## ARTIFICIAL CLOSE TRADES
When FORCE_FLAT_AT_END=True or a controlled flatten is required (e.g. slicing cut-off), any still-open position is closed using an "artificial" exit:
- Marked with ArtClose=True
- Charged entry-side commission only (no exit commission double-count)
- PnL computed vs last available mark price
- Aggregated summary printed per ticker and globally

Use this to ensure final equity reflects only realized + marked value without lingering positions.

## EQUITY CURVE DIAGNOSTICS
Backtests print the final 5 equity points (tail(5)) alongside final_capital to visually confirm monotonicity / anomalies and verify FORCE_FLAT_AT_END alignment (equity[-1] == final_capital when True).

## STRICT TRADE DAY LOGIC
Trade execution days are derived using the trade window (tw) applied over valid NYSE trading days only (skips weekends/market holidays). This ensures realistic delay between level identification and actionable entry.

## CORE FILES

### Automated Trading
- `production_auto_trader.py` - **Production automated trading system**
- `auto_daily_trader.py` - Full-featured daily automation
- `simple_auto_trader.py` - Lightweight auto trader for testing

### Main Execution
- `complete_comprehensive_backtest.py` - **Full system backtest with optimization**
- `runner.py` - Single ticker backtesting (proven reliable)
- `single_trades.py` - **Generate paper trading lists**
- `show_summary.py` - Display comprehensive results

### Manual Trading
- `manual_trading.py` - Manual trade execution with IB
- `portfolio_manager.py` - Position and order management
- `check_todays_signals.py` - Check current trading signals

#### Signal Parameter Enrichment
`check_todays_signals.py` merges two sources:
1. Comprehensive backtest export (`complete_comprehensive_backtest_results.json`) – already contains p & tw.
2. Runner backtest daily trade ledger (`trades_by_day.json`).

Previously runner-derived signals (those only present in `trades_by_day.json`) lacked parameter context and showed `p=None, tw=None`. They are now enriched by loading `runner_fullbacktest_results.json` (generated via `python runner.py fullbacktest`). If that file is missing or stale, these parameters will revert to `None` until you regenerate it. Workflow to guarantee populated parameters:
```bash
python runner.py fullbacktest   # builds runner_fullbacktest_results.json with selected p, tw
python check_todays_signals.py  # now shows p=.. tw=.. for all sources
```
This ensures OPEN/CLOSE execution plans reflect the exact optimized configuration used for the latest runner backtest.

### Core Logic
- `backtesting_core.py` - Core backtesting functions
- `signal_utils.py` - Support/resistance signal generation
- `simulation_utils.py` - Trade simulation and matching
- `stats_tools.py` - Performance statistics

### Configuration & Data
- `config.py` - **System parameters and timing settings**
- `tickers_config.py` - **Per-ticker trading configuration**
- `*_data.csv` - Historical price data
- `complete_comprehensive_backtest_results.json` - Full results

### Analysis & Tools
- `comprehensive_trade_summary.py` - Detailed trade analysis
- `paper_trading_list.py` - Interactive paper trading tool
- `plot_utils.py` / `plotly_utils.py` - Chart generation
- `verify_price_column_usage.py` - Asserts price column (Open/Close) mapping correctness
- `test_config.py` - Validate configuration integration

## AUTOMATED TRADING SYSTEM

### Which Script To Run For OPEN & CLOSE Paper Trading
Use `production_trader_win.py` for continuous paper (or live) trading that handles both the OPEN and CLOSE sessions automatically. Typical sequence:
1. (Optional but recommended) Update data: `python data_sync.py`
2. Run a full backtest once to warm up: `python complete_comprehensive_backtest.py`
3. Start the continuous paper trader: `python production_trader_win.py`

Behavior:
- Before each session (OPEN or CLOSE) it ensures a recent successful full backtest exists; if stale or missing it runs `complete_comprehensive_backtest.py` (with retries per config) before executing orders.
- OPEN session: waits for configured open + delay (plus grace) then executes all qualifying OPEN entry signals plus any strategy-based exits.
- CLOSE session: revalidates / refreshes backtest if needed, then executes CLOSE signals plus exits.
- Disconnects from IB between sessions, reconnects ahead of next session (with heartbeat & auto-reconnect logic).
- Paper trading is default; for live trading add `--live-trading` (will prompt for confirmation).

Alternatives:
- `production_auto_trader.py` is a cross-platform variant (use only if you need non-Windows terminal features).
- Manual one-off execution: run full backtest, then `check_todays_signals.py`, then `manual_trading.py` at the desired session time.

If you only want to simulate without sending orders, add `--dry-run` (optionally `--test-mode` to accelerate timing windows for QA).

### Production Auto Trader
The `production_auto_trader.py` (cross-platform) and `production_trader_win.py` (Windows-focused) are fully automated trading systems that:

- **Can start anytime** - Automatically waits for next trading session
- **Morning (OPEN) Session**: Waits for market open (09:30 ET) + OPEN_TRADE_DELAY (config, default 10 min => 09:40). Runs fresh backtest (if not recently done), gathers signals whose `trade_on` is `OPEN`, merges any strategy-based exit signals for existing positions, then executes orders.
- **Afternoon (CLOSE) Session**: Waits for market close (16:00 ET) - CLOSE_TRADE_ADVANCE (config, default 15 min => 15:45). Runs backtest (if needed), collects `CLOSE` signals + strategy exits, then executes.
- **Runs continuously** until stopped with CTRL+C
- **Skips weekends** and major holidays automatically
- **Paper trading by default** - Safe for testing and learning

### Auto Trading Options
```bash
# Windows continuous auto trader (recommended on Windows)
python production_trader_win.py            # Paper trading (real orders, paper account)
python production_trader_win.py --dry-run  # Simulate signals & sessions only
python production_trader_win.py --test-mode --dry-run  # Fast cycle for QA
python production_trader_win.py --verbose  # More logging detail
python production_trader_win.py --live-trading  # Live acct (prompts + risk!)

# Cross-platform legacy variant
python production_auto_trader.py --dry-run
```

### Session Timing & Config Mapping
| Purpose | Config Keys | Default | Effective / Behavior |
|---------|-------------|---------|----------------------|
| Market Open | MARKET_OPEN_TIME | 09:30 | Baseline market open |
| OPEN Execution Delay | OPEN_TRADE_DELAY | 10 min | Execution target (e.g. 09:40) |
| OPEN Grace Window | OPEN_SESSION_GRACE_MIN | 7 min | Extra window if backtest/signals delayed |
| CLOSE Advance | CLOSE_TRADE_ADVANCE | 15 min | Minutes before 16:00 to execute (15:45) |
| CLOSE Grace Window | CLOSE_SESSION_GRACE_MIN | 5 min | Extra window if retry needed |
| Backtest Retries | BACKTEST_MAX_RETRIES | 2 | Additional attempts on failure |
| Retry Delay | BACKTEST_RETRY_DELAY_SEC | 90 | Seconds between retry attempts |
| IB Heartbeat | IB_HEARTBEAT_SEC | 45 | Interval to ping & ensure connectivity |
| Auto Reconnect | IB_RECONNECT_ON_TIMEOUT | True | Reconnect on inactivity/timeouts |
| Strategy Exit Mode | USE_STRATEGY_EXITS_ONLY | True | Only close via opposing strategy signal |

Change timings in `config.py` (OPEN_TRADE_DELAY / CLOSE_TRADE_ADVANCE) then restart the auto trader.

### Daily Cycle (production_trader_win.py)
1. Startup: Loads config, determines next pending session (OPEN or CLOSE) based on time.
2. Pre-Session Wait: Sleeps until scheduled execution window; skips weekends & holiday list.
3. Backtest Gate: Runs `complete_comprehensive_backtest.py` unless a recent run (< min interval) exists; retries if fails (config governed). Ensures only one successful run per needed window (dedup).
4. Signal Aggregation:
   - Entry signals from `check_todays_signals.py` for session type.
   - Strategy-based exit signals for currently held positions (no stop-loss / take-profit; strategy exits only when `USE_STRATEGY_EXITS_ONLY=True`).
   - Deduplicates and tags counts (exits vs entries).
5. Order Construction: Combines complementary actions (e.g., SELL + SHORT) where possible via portfolio manager; enforces one action per symbol per day (prevents same-day exit then re-entry churn).
6. Execution: Places LIMIT or MARKET orders as implemented (dry-run prints only).
7. Logging: Session result appended to `logs/sessions_YYYYMMDD.json` and detailed log file.
8. Between Sessions: Disconnects IB during waits; loops until both sessions complete, then idles until next trading day; real-time prices captured at OPEN, later reconciled with official OHLC after close for accurate historical alignment.

### Strategy Exit Logic
With `USE_STRATEGY_EXITS_ONLY=True` (default) the system will NOT exit via stop loss / profit target. Positions close only when an opposing strategy signal appears (e.g., LONG SELL or SHORT COVER) during either session. This minimizes premature exits and matches the core support/resistance methodology.

### Test Mode Behavior
`--test-mode` compresses wait intervals for rapid QA (session windows fire quickly). Use together with `--dry-run` to validate scheduling & logging without contacting IB excessively.

### Quick Start (Windows)
```bash
# One-time prep
python complete_comprehensive_backtest.py

# Start continuous paper automation (runs until CTRL+C)
python production_trader_win.py

# View live logs in another PowerShell
Get-Content logs\auto_trader_*.log -Tail 30 -Wait
```

### Troubleshooting
| Symptom | Cause | Action |
|---------|-------|--------|
| No OPEN trades executed | No qualifying signals; backtest failed; outside window | Check log, rerun backtest, verify config times |
| Duplicate session run | Restarted mid-session | Safe: system marks session complete; will not re-run |
| Missing exit order | No opposing strategy signal generated | Confirm `complete_comprehensive_backtest_results.json` includes expected SELL/COVER signal |
| IB disconnects mid-wait | Intentional idle disconnect | Normal; reconnect occurs before next session |


### Safety Features
- ✅ **Paper trading default** - No real money at risk
- ✅ **Dry run mode** - Test everything without executing
- ✅ **Confirmation prompts** for live trading
- ✅ **Fresh backtests** before each session
- ✅ **One-time execution** per session (no duplicate trades)
- ✅ **Comprehensive logging** with daily log files
- ✅ **Graceful shutdown** on CTRL+C

## USAGE COMMANDS

### Backtesting
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

### Paper Trading
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

### Manual Trading
```bash
# Execute manual trades with IB
python manual_trading.py

# Check today's signals
python check_todays_signals.py

# Test configuration integration
python test_config.py
```

### Data Management
```bash
# Update price data
python data_sync.py

# Today's signals
python signal_alert_today.py
```

## CONFIGURATION

The system uses two main configuration files:

### `config.py` - System Settings
```python
INITIAL_CAPITAL = 50000           # Total trading capital
MARKET_OPEN_TIME = "09:30"        # NY market open
MARKET_CLOSE_TIME = "16:00"       # NY market close
IB_PAPER_PORT = 7497              # Paper trading port
IB_LIVE_PORT = 7496               # Live trading port
# ... and more timing/execution parameters
```

### `tickers_config.py` - Per-Ticker Settings
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

## OUTPUT FORMATS

### Console Output
- Entry/Exit signals with prices (ENTRY vs EXIT tagged)
- Performance metrics (return, win rate, drawdown)
- Best performing tickers and strategies
- Capital curves and equity progression
- Backtest retry & session timing diagnostics (when verbose)

## ORDER TRANSMISSION UTILITIES (IB API)

The system now provides focused utilities to extract backtest-derived signals and submit orders to Interactive Brokers with precise session control, merging, limit pricing, and safety caps.

### Key Concepts
| Concept | Meaning |
|---------|---------|
| trade_on | Column indicating whether a signal executes at session OPEN or CLOSE |
| Merged orders | SELL+SHORT or BUY+COVER reversal pairs collapsed into a single net order |
| Artificial closes | Forced flatten exits (not transmitted) are excluded from live order sets |
| Phase | OPEN, CLOSE, or BOTH (controls which trade_on signals are acted upon) |
| Force | Immediate submission bypassing scheduled wait times (testing / weekend QA) |
| Limit mode | Use day's historical Open (for OPEN trades) or Close (for CLOSE trades) as limit price |
| Raw mode | Disable reversal merging (submit each leg independently) |
| Cap fraction | Fraction of AvailableFunds (or NetLiquidation fallback) to cap per-symbol notional |
| Max notional | Absolute USD cap per order after merging / sizing adjustments |

### Core Transmission Scripts / Commands

1. `schedule_date` (inside `trade_execution.py`)
    - Schedules (and optionally executes) OPEN (09:30 + delay) and CLOSE (16:00 - advance) batches for a specific historical date.
    - Can force immediate submission of both groups.
    - Example (dry run):
       ```bash
       python trade_execution.py schedule_date 2025-08-22
       ```
    - Execute merged market orders at proper session times:
       ```bash
       python trade_execution.py schedule_date 2025-08-22 execute
       ```
    - Force immediate (no waiting) and use limit orders:
       ```bash
       python trade_execution.py schedule_date 2025-08-22 execute force limit
       ```

2. `api_transmit_date` (immediate transmit without re-running backtest)
    - Pulls existing per-symbol trade CSVs, filters real (non-artificial) actions, merges if enabled, and sends immediately.
    - Phase filter + limit order + raw + max cap control.
    - Examples:
       ```bash
       # Dry run both phases merged
       python trade_execution.py api_transmit_date 2025-08-22

       # Execute OPEN only, raw legs, market orders
       python trade_execution.py api_transmit_date 2025-08-22 execute open raw

       # Execute CLOSE only, limit orders, cap to first 5 orders
       python trade_execution.py api_transmit_date 2025-08-22 execute close limit max=5
       ```

3. `bt_tx_date` (run backtest first, then transmit)
    - Ensures a fresh `runner.py fullbacktest` run before building the order set.
    - Reuses a single IB connection unless `noreuse` specified.
    - Examples:
       ```bash
       # Backtest + transmit both phases (dry run)
       python trade_execution.py bt_tx_date 2025-08-22

       # Backtest + execute CLOSE only, limit orders
       python trade_execution.py bt_tx_date 2025-08-22 execute close limit

       # Backtest + execute OPEN only, raw legs, no merge reuse
       python trade_execution.py bt_tx_date 2025-08-22 execute open raw noreuse
       ```

4. `daily_trading_scheduler.py`
    - Continuous loop (weekdays) performing:
       - OPEN: 09:30 ET + configurable delay -> run backtest -> transmit OPEN orders.
       - CLOSE: 16:00 ET - configurable advance -> (optionally rerun backtest) -> transmit CLOSE orders.
       - Disconnects IB between sessions.
    - Options:
       ```bash
       python daily_trading_scheduler.py --force-now --date 2025-08-22 --limit --max-notional 15000 --cap-fraction 0.15
       ```
       Flags:
       - `--force-now` : Immediate backtest + transmit (bypass schedule; useful weekends)
       - `--date`      : Override trade date
       - `--limit`     : Use limit orders at day Open/Close
       - `--raw` / `--merged` : Disable / enable reversal merging
       - `--max-notional` : Absolute USD per-order cap
       - `--cap-fraction` : Fraction of available funds per symbol (post-merge)
       - `--no-backtest-close` : Reuse morning backtest for afternoon
       - `--once` : Single-day run then exit

### Limit Orders (Open/Close Anchoring)
- OPEN trades: limit price = historical day Open.
- CLOSE trades: limit price = historical day Close.
- If price unavailable (data gap), system falls back to MarketOrder (logged warning).

### Reversal Order Merging
| Pattern | Result | Rationale |
|---------|--------|-----------|
| SELL then SHORT (same symbol, session) | Single SELL with combined qty | Flat long + establish short in one action |
| BUY then COVER | Single BUY with combined qty | Flat short + establish long in one action |
- Reduces order count & commissions; set `raw` to inspect unmerged internal legs.

### Artificial Close Exclusion
Forced flatten exit legs (ArtClose) are filtered out; real strategy exits only are transmitted to prevent sending synthetic bookkeeping actions.

### Risk & Sizing Controls
| Mechanism | Description |
|-----------|-------------|
| cap_fraction | Per-symbol notional <= AvailableFunds * fraction (fallback NetLiquidation) |
| max_notional | Hard USD ceiling (applied after cap_fraction) |
| Dynamic resize | Quantity reduced to fit within active cap; skipped if new qty <= 0 |
| max= argument | CLI cap on number of orders submitted in a batch |

### Connection Handling
- `connect_ib()` helper with retry used in combined backtest+transmit flow.
- Reused IB connection (bt_tx_date) avoids reconnect overhead.
- Standalone API transmit commands create & close their own session unless an IB instance passed internally.

### Phases & Forcing
| Phase Arg | Effect |
|-----------|--------|
| open | Only trade_on == Open actions |
| close | Only trade_on == Close actions |
| both (default) | All actions (Open first, then Close) |
| force / --force-now | Immediate submission ignoring session clocks |

### Example End-to-End Weekend Test
```bash
# 1. Run full backtest to ensure trade CSVs are fresh
python runner.py fullbacktest

# 2. Force immediate transmit of both Open & Close (limit orders, merged)
python trade_execution.py api_transmit_date 2025-08-22 execute limit

# 3. Cap risk: backtest + transmit with max $10k notional per order, only OPEN trades
python trade_execution.py bt_tx_date 2025-08-22 execute open limit max=10

# 4. Scheduler dry run (no orders executed) with caps
python daily_trading_scheduler.py --force-now --date 2025-08-22 --cap-fraction 0.1 --max-notional 12000 --raw
```

### Troubleshooting Transmission
| Symptom | Likely Cause | Resolution |
|---------|--------------|-----------|
| Rejected order (Error 201) | Insufficient margin / notional too large | Use `--cap-fraction`, `--max-notional`, or reduce per-ticker capital in config |
| No orders found | Backtest did not produce signals; date mismatch; artificial-only trades | Re-run `runner.py fullbacktest`; confirm date; check CSV contents |
| Limit orders never fill (historical price unrealistic) | Using historical Open/Close outside current market | Switch to market or implement real-time price fetch adaptation |
| Duplicate orders expected but missing | Reversal merge collapsed pairs | Add `raw` flag to inspect underlying legs |
| CLOSE orders missing after morning | `--no-backtest-close` reused morning output lacking new exits | Omit `--no-backtest-close` to refresh mid-day |

### Extending Further
Potential next enhancements (not yet implemented):
- Bracket orders (attach stop/target) after core fill
- Partial fill monitoring & adaptive re-price
- Holiday calendar auto-skip (currently weekend only in some scripts)
- Persistent JSON order ledger with fill & PnL trails
- Slack / email notifications on execution batches

---
This section documents all current automated & on-demand trading transmission pathways. Keep it updated when adding new execution flags or sizing logic.

### CSV Exports
- **Single Trades**: `trade_date,ticker,strategy,action,price,shares`
- **Matched Trades**: Entry/exit pairs with P&L
- **Extended Signals**: All signals with support/resistance levels
- **Optimization Results**: Best parameters per ticker

### HTML Charts
- Interactive Plotly charts with price action
- Support/resistance level visualization
- Entry/exit point markers

## STRATEGY OVERVIEW

### Support/Resistance Logic
1. **Identify Levels**: Uses period `p` to find local highs/lows
2. **Signal Confirmation**: Requires `tw` time windows for validation
3. **Entry Rules**: BUY at support, SELL at resistance
4. **Risk Management**: Automatic stop losses and profit targets

### Trading Strategies
### Equity Curves (Two Variants)
The system now produces two conceptual equity representations:
1. Close-Marked Equity (default): Marks open positions each day using the session Close. Provides a smooth, comparable baseline across tickers.
2. Execution Equity (optional): Uses actual execution price on entry and exit days (Open if trade_on=Open) and Close on intervening days, highlighting intraday gap effects.

When trade_on == Open, execution equity can differ notably from close equity if large opening gaps occur; use it to assess slippage/gap sensitivity.

### Price Column Verification
Run the quick audit script to confirm all tickers use the intended price column for both level detection and execution:
```bash
python verify_price_column_usage.py
```
Outputs [OK]/[FAIL] lines per ticker plus sampled comparisons.

### Trade Audit Metadata
Each simulated trade now stores `entry_price_col` and `exit_price_col` ("Open" or "Close") so downstream analytics or compliance reviews can confirm execution basis.

- **LONG**: Buy at support levels, sell at resistance
- **SHORT**: Short at resistance levels, cover at support
- **Execution**: Market OPEN or CLOSE based on configuration
- **Orders**: LIMIT orders at calculated levels

## REQUIREMENTS

```bash
pip install pandas numpy matplotlib yfinance scipy plotly ib_insync markdown2
```

### Python Packages
- `pandas` - Data manipulation
- `numpy` - Numerical computations
- `matplotlib` - Basic plotting
- `plotly` - Interactive charts
- `yfinance` - Price data download
- `scipy` - Statistical analysis
- `ib_insync` - Interactive Brokers API
- `markdown2` - Report generation

## TYPICAL WORKFLOW

### Automated Trading (Recommended)
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

### Manual Analysis & Trading
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

## LOG FILES & MONITORING

### Automated Trading Logs
- `logs/auto_trader_YYYYMMDD.log` - Daily operation logs
- `logs/sessions_YYYYMMDD.json` - Session results and statistics
- `logs/` directory created automatically

### Monitoring Commands
```bash
# View real-time logs
Get-Content logs\auto_trader_*.log -Tail 20 -Wait

# Check session results
python -c "import json; print(json.dumps(json.load(open('logs/sessions_$(Get-Date -Format "yyyyMMdd").json')), indent=2))"

# Validate configuration
python test_config.py
```

## DOCUMENTATION & HELP

- **`HELP.md`** - Comprehensive help guide with all commands
- **`README.md`** - This overview file  
- **`test_config.py`** - Validate system configuration
- **Inline Comments** - Detailed code documentation
- **Error Messages** - Descriptive error handling

## GETTING STARTED CHECKLIST

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

## IMPORTANT NOTES

### Trading Safety
- ✅ **Default to paper trading** - Real money requires explicit confirmation
- ✅ **Start with dry runs** to understand the system
- ✅ **Test thoroughly** with recent data before live trading
- ✅ **Monitor continuously** - Check logs regularly
- ✅ **Use CTRL+C** to stop automated trading gracefully

### Interactive Brokers Setup
- Paper Trading Account: Port 7497 (default)
- Live Trading Account: Port 7496 (requires --live-trading flag)
- TWS or IB Gateway must be running
- Contract IDs configured in `tickers_config.py`

### Data Requirements
- Historical data updated via `data_sync.py`
- Minimum 1+ years of data for reliable backtesting
- Fresh backtests run automatically before each trading session
- ✅ Use proper risk management and position sizing
- ✅ Monitor support/resistance level confirmations

### Additional Data Notes
- Minimum 2 years of historical data
- Daily OHLCV format
- Regular updates via `data_sync.py`

## TROUBLESHOOTING

| Issue | Solution |
|-------|----------|
| No data found | Run `python data_sync.py` |
| No signals generated | Check date range, ticker config, ensure backtest success |
| CSV export fails | Verify write permissions |
| Performance slow | Reduce date range or ticker count |
| Session skipped | Review logs: may be outside grace window or backtest failed after retries |
| Missing exit order | Strategy exit not generated yet (strategy-exit-only mode) |
| Same-day churn | Prevented by design; verify signals file integrity |

## SUPPORT

- Run any script without arguments for usage examples
- Check `HELP.md` for comprehensive documentation
- Review error messages for specific guidance
- Validate ticker symbols in `tickers_config.py`

---

**🎯 Ready to trade support and resistance levels like a pro!** 📈

Last Updated: August 24, 2025 - Support/Resistance Trading System v1.2