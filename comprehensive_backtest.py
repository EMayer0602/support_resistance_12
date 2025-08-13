"""
Comprehensive Data Loader and Backtesting System
Loads 2 years of data from Lynx/IB, creates df_bt subset, and runs optimization
"""
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from ib_insync import IB, Stock, util

from tickers_config import tickers
from config import DEFAULT_COMMISSION_RATE, MIN_COMMISSION, backtesting_begin, backtesting_end, trade_years
COMMISSION_RATE = DEFAULT_COMMISSION_RATE  # Use the config value
from signal_utils import (
    calculate_support_resistance,
    assign_long_signals_extended,
    assign_short_signals_extended,
    assign_long_signals,
    assign_short_signals,
    update_level_close_long,
    update_level_close_short,
    compute_trend
)
from backtest_range import restrict_df_for_backtest

from simulation_utils import simulate_trades_compound_extended, compute_equity_curve
from plot_utils import plot_combined_chart_and_equity
from stats_tools import stats

class DataLoader:
    """Loads historical data from Interactive Brokers/Lynx"""
    
    def __init__(self, ib_connection):
        self.ib = ib_connection
        
    def load_historical_data(self, symbol, con_id, years=2, bar_size="1 day"):
        """
        Load historical data for a ticker from IB/Lynx
        
        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            con_id: IB contract ID
            years: Number of years of historical data
            bar_size: Bar size ('1 day', '1 hour', etc.)
        """
        try:
            # Create contract
            contract = Stock(conId=con_id, exchange='SMART', currency='USD')
            
            # Calculate end date (today) and duration
            end_date = datetime.now()
            duration = f"{years} Y"  # Years
            
            print(f"📊 Loading {years} years of data for {symbol}...")
            
            # Request historical data
            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime=end_date,
                durationStr=duration,
                barSizeSetting=bar_size,
                whatToShow='TRADES',
                useRTH=True,  # Regular Trading Hours
                formatDate=1
            )
            
            if not bars:
                print(f"⚠️ No data received for {symbol}")
                return None
                
            # Convert to DataFrame
            df = util.df(bars)
            df.set_index('date', inplace=True)
            df.index = pd.to_datetime(df.index)
            
            # Rename columns to match existing code
            df = df.rename(columns={
                'open': 'Open',
                'high': 'High', 
                'low': 'Low',
                'close': 'Close',
                'volume': 'Volume'
            })
            
            print(f"✅ Loaded {len(df)} bars for {symbol} from {df.index[0].date()} to {df.index[-1].date()}")
            
            # Save to CSV for future use
            csv_path = f"{symbol}_data.csv"
            df.to_csv(csv_path)
            print(f"💾 Saved data to {csv_path}")
            
            return df
            
        except Exception as e:
            print(f"❌ Error loading data for {symbol}: {e}")
            return None

class BacktestOptimizer:
    """Optimizes trading parameters and runs backtests"""
    
    def __init__(self):
        self.results = {}
    
    def create_backtest_subset(self, df, begin_pct=None, end_pct=None):
        """Return percentage slice (df_bt) used ONLY for parameter optimization.

        The full recent trade_years slice should be used for final simulation elsewhere.
        """
        begin_pct = backtesting_begin if begin_pct is None else begin_pct
        end_pct = backtesting_end if end_pct is None else end_pct
        if df is None or df.empty:
            print("⚠️ Empty DataFrame passed to create_backtest_subset")
            return df
        n = len(df)
        start_idx = int(n * begin_pct / 100)
        end_idx = int(n * end_pct / 100)
        df_bt = df.iloc[start_idx:end_idx].copy()
        print(f"📈 Created df_bt optimization subset: {len(df_bt)} bars ({begin_pct}% - {end_pct}%)")
        print(f"   df_bt period: {df_bt.index[0].date()} to {df_bt.index[-1].date()}")
        return df_bt
        
    def optimize_parameters(self, df_bt, symbol, ticker_config, p_range=range(5, 51, 5), tw_range=range(5, 31, 5)):
        """
        Find optimal p (past_window) and tw (trade_window) parameters
        
        Args:
            df_bt: Backtest DataFrame subset
            symbol: Stock symbol
            ticker_config: Configuration for this ticker
            p_range: Range of past_window values to test
            tw_range: Range of trade_window values to test
        """
        print(f"\n🔍 Optimizing parameters for {symbol}...")
        print(f"   Testing p={list(p_range)}, tw={list(tw_range)}")
        
        best_params = {"p": None, "tw": None, "return": -np.inf}
        optimization_results = []
        
        for p in p_range:
            for tw in tw_range:
                try:
                    # Calculate support/resistance
                    price_col = "Open" if ticker_config.get("trade_on", "Close").lower() == "open" else "Close"
                    support, resistance = calculate_support_resistance(df_bt, p, tw, price_col=price_col)
                    
                    # Debug: Check what types we get from calculate_support_resistance
                    if not isinstance(support, pd.Series) or not isinstance(resistance, pd.Series):
                        print(f"      Warning: Support/resistance wrong type: {type(support)}, {type(resistance)}")
                        continue
                    
                    # Generate signals based on trade direction
                    if ticker_config.get("long", False):
                        signals_long = assign_long_signals_extended(support, resistance, df_bt, tw, interval="1D")
                        
                        # Debug: Check the exact type returned
                        print(f"      Debug: signals_long type = {type(signals_long)}")
                        if hasattr(signals_long, 'columns'):
                            print(f"      Debug: signals_long columns = {list(signals_long.columns)}")
                        if hasattr(signals_long, '__len__'):
                            print(f"      Debug: signals_long length = {len(signals_long)}")
                        
                        # Ensure signals_long is a DataFrame
                        if not isinstance(signals_long, pd.DataFrame):
                            print(f"      Warning: Long signals is not DataFrame, got {type(signals_long)}")
                            long_return = 1.0
                        elif signals_long.empty:
                            long_return = 1.0
                        else:
                            signals_long = update_level_close_long(signals_long, df_bt)
                            
                            # Calculate trades and returns
                            trades_long, equity_long = self._backtest_signals(
                                signals_long, df_bt, symbol, ticker_config, "long"
                            )
                            
                            # Calculate return from equity curve
                            if not equity_long.empty and len(equity_long) > 0:
                                # Look for common equity column names
                                equity_cols = [col for col in equity_long.columns if 'equity' in col.lower() or 'capital' in col.lower()]
                                if equity_cols:
                                    final_value = equity_long[equity_cols[0]].iloc[-1]
                                    initial_value = ticker_config.get("initialCapitalLong", 1000)
                                    long_return = final_value / initial_value
                                else:
                                    long_return = 1.0
                            else:
                                long_return = 1.0
                    else:
                        long_return = 1.0
                        
                    if ticker_config.get("short", False):
                        signals_short = assign_short_signals_extended(support, resistance, df_bt, tw, interval="1D")
                        
                        # Ensure signals_short is a DataFrame
                        if not isinstance(signals_short, pd.DataFrame):
                            print(f"      Warning: Short signals is not DataFrame, got {type(signals_short)}")
                            short_return = 1.0
                        elif signals_short.empty:
                            short_return = 1.0
                        else:
                            signals_short = update_level_close_short(signals_short, df_bt)
                            
                            # Calculate trades and returns
                            trades_short, equity_short = self._backtest_signals(
                                signals_short, df_bt, symbol, ticker_config, "short"
                            )
                            
                            # Calculate return from equity curve
                            if not equity_short.empty and len(equity_short) > 0:
                                # Look for common equity column names
                                equity_cols = [col for col in equity_short.columns if 'equity' in col.lower() or 'capital' in col.lower()]
                                if equity_cols:
                                    final_value = equity_short[equity_cols[0]].iloc[-1]
                                    initial_value = ticker_config.get("initialCapitalShort", 1000)
                                    short_return = final_value / initial_value
                                else:
                                    short_return = 1.0
                            else:
                                short_return = 1.0
                    else:
                        short_return = 1.0
                        
                    # Combined return (geometric mean)
                    combined_return = (long_return * short_return) ** 0.5
                    
                    optimization_results.append({
                        "p": p,
                        "tw": tw,
                        "long_return": long_return,
                        "short_return": short_return,
                        "combined_return": combined_return
                    })
                    
                    if combined_return > best_params["return"]:
                        best_params = {"p": p, "tw": tw, "return": combined_return}
                        
                    print(f"   p={p:2d}, tw={tw:2d}: Long={long_return:.4f}, Short={short_return:.4f}, Combined={combined_return:.4f}")
                    
                except Exception as e:
                    print(f"   p={p:2d}, tw={tw:2d}: Error - {e}")
                    continue
                    
        print(f"🎯 Best parameters for {symbol}: p={best_params['p']}, tw={best_params['tw']}, return={best_params['return']:.4f}")
        
        return best_params, optimization_results
        
    def _backtest_signals(self, signals, df_bt, symbol, ticker_config, direction):
        """Helper method to backtest signals and calculate equity curve"""
        try:
            # Handle trade_on setting (open vs close)
            trade_on = ticker_config.get("trade_on", "close").lower()
            
            # Check if signals is a DataFrame and is valid
            if not isinstance(signals, pd.DataFrame):
                print(f"      Signals is not DataFrame, got {type(signals)}")
                return pd.DataFrame(), pd.DataFrame()
                
            # Check if signals DataFrame is valid and not empty
            if signals.empty:
                print(f"      No {direction} signals found")
                return pd.DataFrame(), pd.DataFrame()
            
            # Check for required columns
            if direction == "long":
                required_cols = ["Long Action", "Long Date detected"]
            else:
                required_cols = ["Short Action", "Short Date detected"]
                
            missing_cols = [col for col in required_cols if col not in signals.columns]
            if missing_cols:
                print(f"      Missing columns in {direction} signals: {missing_cols}")
                return pd.DataFrame(), pd.DataFrame()
            
            # Simulate trades using the existing function
            final_capital, trades = simulate_trades_compound_extended(
                signals, df_bt, ticker_config,
                COMMISSION_RATE, MIN_COMMISSION, 
                ticker_config.get("order_round_factor", 1),
                direction=direction
            )
            
            # Compute equity curve
            if trades and len(trades) > 0:
                start_capital = ticker_config["initialCapitalLong"] if direction == "long" else ticker_config["initialCapitalShort"]
                equity = compute_equity_curve(df_bt, trades, start_capital, long=(direction == "long"))
                equity_df = pd.DataFrame({'Equity': equity}, index=df_bt.index)
            else:
                equity_df = pd.DataFrame()
                
            return pd.DataFrame(trades), equity_df
            
        except Exception as e:
            print(f"      Error in backtesting {direction} signals: {e}")
            return pd.DataFrame(), pd.DataFrame()
            
    def run_full_backtest(self, df_bt, symbol, ticker_config, optimal_p, optimal_tw):
        """Run full backtest with optimal parameters and generate outputs."""
        print(f"\n🚀 Running full backtest for {symbol} with p={optimal_p}, tw={optimal_tw}")

        # Support / Resistance using correct price column
        price_col = "Open" if ticker_config.get("trade_on", "Close").lower() == "open" else "Close"
        support, resistance = calculate_support_resistance(df_bt, optimal_p, optimal_tw, price_col=price_col)

        results = {}

        # LONG
        if ticker_config.get("long", False):
            print("   📈 Processing LONG signals...")
            signals_long = assign_long_signals_extended(support, resistance, df_bt, optimal_tw, interval="1D")
            signals_long = update_level_close_long(signals_long, df_bt)
            trades_long, equity_long = self._backtest_signals(signals_long, df_bt, symbol, ticker_config, "long")
            trades_long.to_csv(f"extended_long_{symbol}.csv", index=False)
            matched_trades_long = self._create_matched_trades(trades_long, "long")
            matched_trades_long.to_csv(f"trades_long_{symbol}.csv", index=False)
            equity_list = equity_long['Equity'].tolist() if not equity_long.empty and 'Equity' in equity_long else []
            trades_list = trades_long.to_dict('records') if not trades_long.empty else []
            final_cap_long = equity_list[-1] if equity_list else ticker_config.get('initialCapitalLong')
            long_stats = stats(trades_list, f"{symbol} Long", initial_capital=ticker_config.get('initialCapitalLong'), final_capital=final_cap_long, equity_curve=equity_list) if trades_list else {}
            if long_stats:
                print(f"   🔢 LONG Metrics: Init={long_stats.get('initial_capital'):.2f} Final={long_stats.get('final_capital'):.2f} MaxDD={long_stats.get('max_drawdown_pct'):.2f}%")
            results["long"] = {"signals": signals_long, "trades": trades_long, "matched_trades": matched_trades_long, "equity": equity_long, "stats": long_stats}

        # SHORT
        if ticker_config.get("short", False):
            print("   📉 Processing SHORT signals...")
            signals_short = assign_short_signals_extended(support, resistance, df_bt, optimal_tw, interval="1D")
            signals_short = update_level_close_short(signals_short, df_bt)
            trades_short, equity_short = self._backtest_signals(signals_short, df_bt, symbol, ticker_config, "short")
            trades_short.to_csv(f"extended_short_{symbol}.csv", index=False)
            matched_trades_short = self._create_matched_trades(trades_short, "short")
            matched_trades_short.to_csv(f"trades_short_{symbol}.csv", index=False)
            equity_list_s = equity_short['Equity'].tolist() if not equity_short.empty and 'Equity' in equity_short else []
            trades_list_s = trades_short.to_dict('records') if not trades_short.empty else []
            final_cap_short = equity_list_s[-1] if equity_list_s else ticker_config.get('initialCapitalShort')
            short_stats = stats(trades_list_s, f"{symbol} Short", initial_capital=ticker_config.get('initialCapitalShort'), final_capital=final_cap_short, equity_curve=equity_list_s) if trades_list_s else {}
            if short_stats:
                print(f"   🔢 SHORT Metrics: Init={short_stats.get('initial_capital'):.2f} Final={short_stats.get('final_capital'):.2f} MaxDD={short_stats.get('max_drawdown_pct'):.2f}%")
            results["short"] = {"signals": signals_short, "trades": trades_short, "matched_trades": matched_trades_short, "equity": equity_short, "stats": short_stats}

        # Chart (align with current plot_utils signature)
        try:
            ext_long_df  = results.get("long", {}).get("signals", pd.DataFrame())
            ext_short_df = results.get("short", {}).get("signals", pd.DataFrame())
            eq_long_df   = results.get("long", {}).get("equity", pd.DataFrame())
            eq_short_df  = results.get("short", {}).get("equity", pd.DataFrame())

            # Extract equity series (or empty list) expected by plotter
            equity_long_series  = eq_long_df["Equity"].tolist() if not eq_long_df.empty and "Equity" in eq_long_df else []
            equity_short_series = eq_short_df["Equity"].tolist() if not eq_short_df.empty and "Equity" in eq_short_df else []
            # Combined equity (element-wise sum, fallback to long if short empty)
            if equity_long_series and equity_short_series and len(equity_long_series)==len(equity_short_series):
                equity_combined = [l + s for l, s in zip(equity_long_series, equity_short_series)]
            else:
                equity_combined = equity_long_series or equity_short_series
            # Buy & Hold baseline on Close
            if not df_bt.empty:
                initial_cap = ticker_config.get("initialCapitalLong", 1000)
                first_close = df_bt["Close"].iloc[0]
                buyhold = [initial_cap * (c / first_close) for c in df_bt["Close"]]
            else:
                buyhold = []
            trend_series = compute_trend(df_bt, 20)
            plot_combined_chart_and_equity(
                df_bt,
                ext_long_df,
                ext_short_df,
                support,
                resistance,
                trend_series,
                equity_long_series,
                equity_short_series,
                equity_combined,
                buyhold,
                symbol
            )
            print(f"   📊 Chart saved as {symbol}_chart.html")
        except Exception as e:
            print(f"   ⚠️ Chart generation error: {e}")

        return results
        
    def _create_matched_trades(self, extended_trades, direction):
        """Convert extended trades to matched trades format"""
        matched_trades = []
        
        if direction == "long":
            # Group buy/sell pairs
            buys = extended_trades[extended_trades["Long"] == "buy"].copy()
            sells = extended_trades[extended_trades["Long"] == "sell"].copy()
            
            for _, buy in buys.iterrows():
                # Find corresponding sell
                matching_sells = sells[sells["Long Date"] > buy["Long Date"]]
                if not matching_sells.empty:
                    sell = matching_sells.iloc[0]
                    
                    matched_trades.append({
                        "buy_date": buy["Long Date"],
                        "sell_date": sell["Long Date"],
                        "shares": buy.get("qty", 1),
                        "buy_price": buy.get("Level Close", buy.get("Close", 0)),
                        "sell_price": sell.get("Level Close", sell.get("Close", 0)),
                        "fee": buy.get("fee", 0) + sell.get("fee", 0),
                        "pnl": buy.get("pnl", 0)
                    })
                    
        else:  # short
            # Group short/cover pairs  
            shorts = extended_trades[extended_trades["Short"] == "short"].copy()
            covers = extended_trades[extended_trades["Short"] == "cover"].copy()
            
            for _, short in shorts.iterrows():
                # Find corresponding cover
                matching_covers = covers[covers["Short Date"] > short["Short Date"]]
                if not matching_covers.empty:
                    cover = matching_covers.iloc[0]
                    
                    matched_trades.append({
                        "short_date": short["Short Date"],
                        "cover_date": cover["Short Date"],
                        "shares": short.get("qty", 1),
                        "short_price": short.get("Level Close", short.get("Close", 0)),
                        "cover_price": cover.get("Level Close", cover.get("Close", 0)),
                        "fee": short.get("fee", 0) + cover.get("fee", 0),
                        "pnl": short.get("pnl", 0)
                    })
                    
        return pd.DataFrame(matched_trades)

def run_comprehensive_backtest():
    """Main function to run the complete backtesting workflow"""
    print("🚀 Starting Comprehensive Backtesting System")
    print("=" * 60)
    
    # Connect to IB/Lynx
    ib = IB()
    try:
        # Port 7497 = Paper Trading (SAFE), Port 7496 = Live Trading (REAL MONEY)
        ib.connect("127.0.0.1", 7497, clientId=1)  # Currently: PAPER TRADING
        print("✅ Connected to Interactive Brokers (Paper Trading)")
    except Exception as e:
        print(f"❌ Failed to connect to IB: {e}")
        return
        
    data_loader = DataLoader(ib)
    optimizer = BacktestOptimizer()
    
    all_results = {}
    
    try:
        for symbol, ticker_config in tickers.items():
            print(f"\n{'='*60}")
            print(f"Processing {symbol}")
            print(f"{'='*60}")
            
            # 1. Load 2 years of historical data
            df = data_loader.load_historical_data(
                symbol, 
                ticker_config["conID"], 
                years=2
            )
            
            if df is None or df.empty:
                print(f"⚠️ Skipping {symbol} - no data available")
                continue
                
            # 2. Create df_bt subset based on config percentages
            df_bt = optimizer.create_backtest_subset(df)
            
            if df_bt.empty:
                print(f"⚠️ Skipping {symbol} - empty backtest subset")
                continue
                
            # 3. Optimize parameters
            best_params, optimization_results = optimizer.optimize_parameters(
                df_bt, symbol, ticker_config
            )
            
            if best_params["p"] is None:
                print(f"⚠️ Skipping {symbol} - no valid parameters found")
                continue
                
            # 4. Run full backtest with optimal parameters
            results = optimizer.run_full_backtest(
                df_bt, symbol, ticker_config,
                best_params["p"], best_params["tw"]
            )
            
            # 5. Save optimization results
            opt_df = pd.DataFrame(optimization_results)
            opt_df.to_csv(f"opt_long_{symbol}.csv" if ticker_config.get("long") else f"opt_short_{symbol}.csv", index=False)
            
            all_results[symbol] = {
                "best_params": best_params,
                "optimization": optimization_results,
                "backtest": results
            }
            
            print(f"✅ Completed {symbol}")
            
    except Exception as e:
        print(f"❌ Error in main backtest loop: {e}")
        
    finally:
        ib.disconnect()
        print("📡 Disconnected from Interactive Brokers")
        
    print(f"\n🎉 Comprehensive backtest completed for {len(all_results)} tickers")
    return all_results

if __name__ == "__main__":
    results = run_comprehensive_backtest()
