import os
import pandas as pd
import numpy as np
from ib_insync import Stock

from plot_utils import plot_combined_chart_and_equity
from tickers_config import tickers
from signal_utils import (
    calculate_support_resistance,
    assign_long_signals_extended,
    assign_short_signals_extended,
    update_level_close_long,
    update_level_close_short,
    assign_long_signals,
    assign_short_signals,
    compute_trend
)
from simulation_utils import debug_equity_alignment
from simulation_utils import simulate_trades_compound_extended, compute_equity_curve
from stats_tools import stats
from plot_utils import plot_combined_chart_and_equity
from config import ORDER_ROUND_FACTOR, COMMISSION_RATE, MIN_COMMISSION, ORDER_SIZE, backtesting_begin, backtesting_end
COMMISSION_RATE = 0.0018
MIN_COMMISSION = 1.0

import os
import pandas as pd
from pandas.errors import EmptyDataError

import pandas as pd
from pandas.errors import EmptyDataError
from tickers_config import tickers

# backtesting_utils.py

def get_backtesting_slice(df, begin_pct=0, end_pct=20):
    """
    Gibt einen Teil-DataFrame zurück von begin_pct % bis end_pct % der Gesamtlänge.
    """
    n = len(df)
    start = int(n * begin_pct / 100)
    end   = int(n * end_pct   / 100)
    return df.iloc[start:end]


def test_trading_for_date(ib, date_str):
    """
    Gibt alle simulierten Trades für ein gegebenes Datum testweise aus.
    Sucht in trades_long_<ticker>.csv und trades_short_<ticker>.csv.
    """
    today = pd.to_datetime(date_str).date()
    print(f"\n=== TESTMODE TRADES für {today} ===")

    for ticker, cfg in tickers.items():
        # 1) CSV einlesen (oder leere DF mit den Spalten):
        try:
            trades_l = pd.read_csv(
                f"trades_long_{ticker}.csv",
                parse_dates=["buy_date", "sell_date"]
            )
        except (FileNotFoundError, EmptyDataError):
            trades_l = pd.DataFrame(
                columns=["buy_date","sell_date","shares","buy_price","sell_price","fee","pnl"]
            )

        try:
            trades_s = pd.read_csv(
                f"trades_short_{ticker}.csv",
                parse_dates=["short_date", "cover_date"]
            )
        except (FileNotFoundError, EmptyDataError):
            trades_s = pd.DataFrame(
                columns=["short_date","cover_date","shares","short_price","cover_price","fee","pnl"]
            )

        # 2) Erzwungene Umwandlung in datetime64 (verhindert .dt-Accessor-Fehler)
        for col in ["buy_date","sell_date"]:
            if col in trades_l.columns:
                trades_l[col] = pd.to_datetime(trades_l[col], errors="coerce")
        for col in ["short_date","cover_date"]:
            if col in trades_s.columns:
                trades_s[col] = pd.to_datetime(trades_s[col], errors="coerce")

        # 3) Filtern nach dem Datum
        buys   = trades_l.loc[trades_l["buy_date"].dt.date   == today]
        sells  = trades_l.loc[trades_l["sell_date"].dt.date  == today]
        shorts = trades_s.loc[trades_s["short_date"].dt.date == today]
        covers = trades_s.loc[trades_s["cover_date"].dt.date == today]

        if buys.empty and sells.empty and shorts.empty and covers.empty:
            continue

        print(f"\n📦 Trades für {ticker}:")
        used = set()

        # paired + einzelne Orders ausgeben
        def show(df, label, price_field, offset):
            for _, r in df.iterrows():
                price = r[price_field]
                qty   = int(r["shares"])
                print(f" {label:<6} {qty}@{price:.2f}")
                # Market
                print(f"   → MARKET {label}  {qty} @ {price:.2f}")
                # Limit
                lim = price * offset
                print(f"   → LIMIT  {label}  {qty} @ {lim:.2f}")

        # Paired LONG: buy_date + cover_date am selben Tag
        for _, b in buys.iterrows():
            match = covers[covers["cover_date"].dt.date == b["buy_date"].date()]
            if not match.empty and b["buy_date"] not in used:
                c = match.iloc[0]
                qty   = int(b["shares"] + c["shares"])
                price = b["buy_price"]
                print(f" PAIRED LONG {qty}@{price:.2f}")
                show(pd.DataFrame([b]), "BUY",  "buy_price",  1.002)
                show(pd.DataFrame([c]), "COVER","cover_price", 1.002)
                used.add(b["buy_date"])

        # Paired SHORT: sell_date + short_date
        for _, s in sells.iterrows():
            match = shorts[shorts["short_date"].dt.date == s["sell_date"].date()]
            if not match.empty and s["sell_date"] not in used:
                sh = match.iloc[0]
                qty   = int(s["shares"] + sh["shares"])
                price = sh["short_price"]
                print(f" PAIRED SHORT {qty}@{price:.2f}")
                show(pd.DataFrame([s]),   "SELL", "sell_price", 0.998)
                show(pd.DataFrame([sh]),  "SHORT","short_price",0.998)
                used.add(s["sell_date"])

        # Einzelorders Long/Short/Cover
        show(buys.loc[~buys["buy_date"].isin(used)],   "BUY",   "buy_price",   1.002)
        show(sells.loc[~sells["sell_date"].isin(used)],"SELL",  "sell_price",  0.998)
        show(covers.loc[~covers["cover_date"].isin(used)],"COVER","cover_price",1.002)
        show(shorts.loc[~shorts["short_date"].isin(used)],"SHORT","short_price",0.998)


def trade_trading_for_today(ib, date_str=None):
    """
    Wrapper, um test_trading_for_date mit einem Datum (oder heute) zu
    starten. Wird von runner.py aufgerufen.
    """
    from datetime import date
    ds = date_str if date_str else str(date.today())
    print(f"\n📆 trade_trading_for_today() für {ds}")
    test_trading_for_date(ib, ds)

import os
import pandas as pd
from ib_insync import util


def update_historical_data_csv(ib, contract, fn):
    """
    Holt fehlende Tagesdaten über IB, bereinigt und speichert sie.
    - Duplikate & kaputte Zeilen werden rausgefiltert
    - Nur neue Daten werden ergänzt
    - Rückgabe: bereinigtes DataFrame mit DatetimeIndex
    """
    # 1) Alte Daten einlesen
    if os.path.exists(fn):
        df_old = pd.read_csv(fn)
        # Nur erste 6 Spalten behalten, falls andere dazugemischt wurden
        df_old = df_old.iloc[:, :6]
        df_old.columns = ["Date", "Open", "High", "Low", "Close", "Volume"]

        df_old["Date"] = pd.to_datetime(df_old["Date"], errors="coerce")
        df_old.dropna(subset=["Date", "Open"], inplace=True)
        df_old.drop_duplicates(subset="Date", keep="last", inplace=True)
        df_old.set_index("Date", inplace=True)
        df_old.sort_index(inplace=True)
    else:
        df_old = pd.DataFrame()

    # 2) Dauer berechnen
    today = pd.Timestamp.now().normalize()
    if df_old.empty:
        duration = "10 Y"
    else:
        last_date = df_old.index.max()
        days = (today - last_date).days
        if days <= 0:
            print(f"✅ {contract.symbol} bereits aktuell bis {last_date.date()}")
            return df_old
        duration = f"{days} D" if days <= 365 else f"{(days // 365) + 1} Y"

    print(f"🔄 Lade historische Daten für {contract.symbol}: durationStr={duration}")

    # 3) IB-Anfrage
    bars = ib.reqHistoricalData(
        contract,
        endDateTime="",
        durationStr=duration,
        barSizeSetting="1 day",
        whatToShow="TRADES",
        useRTH=True,
        formatDate=1
    )
    if not bars:
        print(f"⚠️ Keine neuen Daten für {contract.symbol}")
        return df_old

    df_new = util.df(bars)
    df_new = df_new[["date", "open", "high", "low", "close", "volume"]]
    df_new.columns = ["Date", "Open", "High", "Low", "Close", "Volume"]
    df_new["Date"] = pd.to_datetime(df_new["Date"], errors="coerce")
    df_new.dropna(subset=["Date", "Open"], inplace=True)
    df_new.drop_duplicates(subset="Date", keep="last", inplace=True)
    df_new.set_index("Date", inplace=True)
    df_new.sort_index(inplace=True)

    # 4) Kombinieren
    df_all = pd.concat([df_old, df_new])
    df_all = df_all[~df_all.index.duplicated(keep="last")]
    df_all.sort_index(inplace=True)

    # 5) Speichern
    df_all.to_csv(fn)
    print(f"✅ CSV aktualisiert: {fn} mit {len(df_all)} Zeilen")

    return df_all

def get_trade_day_offset(base_date, trade_window, df):
    future_dates = df.index[df.index > base_date]
    if len(future_dates) < trade_window:
        return pd.NaT
    return future_dates[trade_window - 1]

def berechne_best_p_tw_long(df, config, begin=0, end=20, verbose=True, ticker=""):
    df_opt = get_backtesting_slice(df, begin, end)
    results = []

    for p in range(3, 10):
        for tw in range(1, 6):
            sup, res = calculate_support_resistance(df_opt, p, tw)
            ext_df = assign_long_signals_extended(sup, res, df_opt, tw, "1d")
            ext_df = update_level_close_long(ext_df, df_opt)

            cap, _ = simulate_trades_compound_extended(
                ext_df, df_opt, config,
                commission_rate=COMMISSION_RATE,
                min_commission=MIN_COMMISSION,
                round_factor=config.get("order_round_factor", ORDER_ROUND_FACTOR),
                artificial_close_price=None,
                artificial_close_date=None,
                direction="long"
            )
            results.append({"past_window": p, "trade_window": tw, "final_cap": cap})

    df_result = pd.DataFrame(results).sort_values("final_cap", ascending=False)
    if verbose:
        print(f"\n--- Long-Optimierung für {ticker} ---")
        print(df_result.head(5).to_string(index=False))
        print(f"🔍 Beste Kombination: {df_result.iloc[0].to_dict()}")

    df_result.to_csv(f"opt_long_{ticker}.csv", index=False)
    best = df_result.iloc[0]
    return int(best["past_window"]), int(best["trade_window"])


def berechne_best_p_tw_short(df, config, begin=0, end=20, verbose=True, ticker=""):
    df_opt = get_backtesting_slice(df, begin, end)
    results = []

    for p in range(3, 10):
        for tw in range(1, 4):
            sup, res = calculate_support_resistance(df_opt, p, tw)
            ext_df = assign_short_signals_extended(sup, res, df_opt, tw, "1d")
            ext_df = update_level_close_short(ext_df, df_opt)

            cap, _ = simulate_trades_compound_extended(
                ext_df, df_opt, config,
                commission_rate=COMMISSION_RATE,
                min_commission=MIN_COMMISSION,
                round_factor=config.get("order_round_factor", ORDER_ROUND_FACTOR),
                artificial_close_price=None,
                artificial_close_date=None,
                direction="short"
            )
            results.append({"past_window": p, "trade_window": tw, "final_cap": cap})

    df_result = pd.DataFrame(results).sort_values("final_cap", ascending=False)
    if verbose:
        print(f"\n--- Short-Optimierung für {ticker} ---")
        print(df_result.head(5).to_string(index=False))
        print(f"🔍 Beste Kombination: {df_result.iloc[0].to_dict()}")

    df_result.to_csv(f"opt_short_{ticker}.csv", index=False)
    best = df_result.iloc[0]
    return int(best["past_window"]), int(best["trade_window"])

def get_last_price(df: pd.DataFrame, cfg: dict, ticker: str) -> float | None:
    price_col = "Open" if cfg.get("trade_on", "close").lower() == "open" else "Close"
    if price_col not in df:
        print(f"⚠️ Spalte {price_col} fehlt für {ticker}")
        return None
    val = df[price_col].iloc[-1]
    try:
        return float(val)
    except Exception:
        print(f"⚠️ Ungültiger Preiswert: '{val}' für {ticker}")
        return None


def run_full_backtest(ib):
    show_chart = True

    for ticker, cfg in tickers.items():
        print(f"\n=== Backtest für {ticker} ===")

        # 1) Daten laden
        fn = f"{ticker}_data.csv"
        contract = Stock(cfg["symbol"], "SMART", "USD")
        # 1) Tagesdaten updaten und einlesen
        df = update_historical_data_csv(ib, contract, fn)
        df.index = pd.to_datetime(df.index)                # einheitliche Zeitstempel
        df = df[~df.index.duplicated(keep="last")]         # doppelte entfernen

        df.rename(columns={"open":"Open","high":"High","low":"Low","close":"Close"}, inplace=True)
        df.sort_index(inplace=True)
        # ✅ Preis holen & absichern
        last_price = get_last_price(df, cfg, ticker)
        if last_price is None:
            print(f"{ticker}: letzter Preis nicht verfügbar – Backtest übersprungen.")
            continue

        # Datum der letzten Zeile (brauchst du später)
        last_date = df.index[-1]
        price_col = "Open" if cfg.get("trade_on", "close").lower() == "open" else "Close"

        # Hole den letzten Wert aus der Spalte
        val = df[price_col].iloc[-1]

        # Versuche, float daraus zu machen – nur wenn gültig
        try:
            last_price = float(val)
        except (TypeError, ValueError):
            print(f"⚠️ Ungültiger Wert für {ticker} in Spalte {price_col}: '{val}'")
            continue  # Ticker überspringen

        # 2) Initialisieren (verhindert UnboundLocalError)
        ext_long, ext_short = pd.DataFrame(), pd.DataFrame()
        trades_long, trades_short = [], []
        sup_long = res_long = pd.Series(dtype=float)
        sup_short = res_short = pd.Series(dtype=float)

        # 3) Long-Optimierung & Simulation
        if cfg.get("long", False):
            p_long, tw_long = berechne_best_p_tw_long(df, cfg, verbose=True, ticker=ticker)
            sup_long, res_long = calculate_support_resistance(df, p_long, tw_long)

            ext_long = assign_long_signals_extended(sup_long, res_long, df, tw_long, "1d")
            ext_long = update_level_close_long(ext_long, df)

            # ─── DEBUG EXTENDED LONG SIGNALS
            print(f"\n🔍 EXT_LONG for {ticker} ({len(ext_long)} Rows):")
            print(ext_long)     # alle Spalten + Zeilen
 
            cap_long, trades_long = simulate_trades_compound_extended(
                ext_long, df, cfg,
                COMMISSION_RATE, MIN_COMMISSION,
                cfg.get("order_round_factor",1),
                artificial_close_price=last_price,
                artificial_close_date=last_date,
                direction="long"
            )

          # ─── DEBUG MATCHED LONG TRADES ─────────────────────────────────────────
            # ─── DEBUG MATCHED TRADES_LONG als Tabelle ────────────────────────────────
            if trades_long:
                df_trades_long = pd.DataFrame(trades_long)
                print(f"\n🗒️ MATCHED TRADES_LONG ({len(df_trades_long)})")
                print(df_trades_long.to_string(index=False))
            else:
                print("\n🗒️ MATCHED TRADES_LONG: Keine Trades")

        else:
            cap_long, trades_long = 0, []

        # 4) Short-Optimierung & Simulation
        if cfg.get("short", False):
            p_short, tw_short = berechne_best_p_tw_short(df, cfg, verbose=True, ticker=ticker)
            sup_short, res_short = calculate_support_resistance(df, p_short, tw_short)

            ext_short = assign_short_signals_extended(sup_short, res_short, df, tw_short, "1d")
            ext_short = update_level_close_short(ext_short, df)

            print(f"\n🔍 EXT_SHORT for {ticker}, cols={ext_short.columns.tolist()}")
            if {"Short Date detected","Short Action"}.issubset(ext_short.columns):
                print(ext_short[["Short Date detected","Short Action"]].dropna().head(5))
            else:
                print("→ EXT_SHORT enthält keine Spalten Short Date detected/Short Action")

            cap_short, trades_short = simulate_trades_compound_extended(
                ext_short, df, cfg,
                COMMISSION_RATE, MIN_COMMISSION,
                cfg.get("order_round_factor",1),
                artificial_close_price=last_price,
                artificial_close_date=last_date,
                direction="short"
            )
            if trades_short:
                df_trades_short = pd.DataFrame(trades_short)
                print(f"\n🗒️ MATCHED TRADES_SHORT ({len(df_trades_short)})")
                print(df_trades_short.to_string(index=False))
            else:
                print("\n🗒️ MATCHED TRADES_SHPRT: Keine Trades")

        else:
            cap_short = 0

        # 5) Stats ausgeben
        print(f"{ticker} Final Capital: Long={cap_long:.2f}  Short={cap_short:.2f}")
        stats(trades_long,  f"{ticker} Long")
        stats(trades_short, f"{ticker} Short")

        # 6) Equity-Kurven bauen & debug-print
        eq_long  = compute_equity_curve(df, trades_long,  cfg["initialCapitalLong"],  long=True)
        eq_short = compute_equity_curve(df, trades_short, cfg["initialCapitalShort"], long=False)
#        print("🔍 DEBUG eq_long head:", eq_long, "tail:", eq_long[-5:])
#        print("🔍 DEBUG eq_short head:", eq_short, "tail:", eq_short[-5:])

        eq_combined = [l+s for l,s in zip(eq_long, eq_short)]
        buyhold     = [cfg["initialCapitalLong"] * (p/df["Close"].iloc[0]) for p in df["Close"]]

        # 7) Plot
        if show_chart:
            try:
                trend = compute_trend(df, 20)
                plot_combined_chart_and_equity(
                    df, ext_long, ext_short,
                    sup_long, res_long, trend,
                    eq_long, eq_short, eq_combined, buyhold,
                    ticker
                )
            except Exception:
                import traceback
                print(f"⚠️ Plot für {ticker} fehlgeschlagen:")
                traceback.print_exc()

        # 8) CSV speichern
        pd.DataFrame(trades_long).to_csv(f"trades_long_{ticker}.csv", index=False)
        pd.DataFrame(trades_short).to_csv(f"trades_short_{ticker}.csv", index=False)
        ext_long.to_csv(f"extended_long_{ticker}.csv", index=False)
        ext_short.to_csv(f"extended_short_{ticker}.csv", index=False)


def test_trading_for_date(ib, date_str):
    """
    Gibt alle Trades für ein gegebenes Datum testweise aus, inkl. Market- & Limit-Orders.
    Sucht in trades_long_<ticker>.csv und trades_short_<ticker>.csv
    """
    today = pd.to_datetime(date_str).date()
    print(f"\n=== TESTMODE TRADES für {today} ===")

    for ticker, cfg in tickers.items():
        # Trades laden
        try:
            trades_l = pd.read_csv(f"trades_long_{ticker}.csv", parse_dates=["buy_date", "sell_date"])
        except (FileNotFoundError, EmptyDataError):
            trades_l = pd.DataFrame(columns=["buy_date", "sell_date", "shares", "buy_price", "sell_price", "fee", "pnl"])
        try:
            trades_s = pd.read_csv(f"trades_short_{ticker}.csv", parse_dates=["short_date", "cover_date"])
        except (FileNotFoundError, EmptyDataError):
            trades_s = pd.DataFrame(columns=["short_date", "cover_date", "shares", "short_price", "cover_price", "fee", "pnl"])

        # Filter
        buys   = trades_l[trades_l["buy_date"].dt.date == today]
        sells  = trades_l[trades_l["sell_date"].dt.date == today]
        shorts = trades_s[trades_s["short_date"].dt.date == today]
        covers = trades_s[trades_s["cover_date"].dt.date == today]

        if buys.empty and sells.empty and shorts.empty and covers.empty:
            continue

        print(f"\n{ticker}:")
        used = set()

        # Paired LONG (buy + cover am selben Tag)
        for _, b in buys.iterrows():
            cov = covers[covers["cover_date"].dt.date == b["buy_date"].date()]
            if not cov.empty and b["buy_date"] not in used:
                c = cov.iloc[0]
                qty = int(b["shares"] + c["shares"])
                price = b["buy_price"]
                print(f" PAIRED LONG {qty}@{price:.2f}")
                print(f"   → Market Buy  {qty} @ {price:.2f}")
                print(f"   → Limit Buy   {qty} @ {price * 1.002:.2f}")
                used.add(b["buy_date"])

        # Paired SHORT (sell + short am selben Tag)
        for _, s in sells.iterrows():
            sho = shorts[shorts["short_date"].dt.date == s["sell_date"].date()]
            if not sho.empty and s["sell_date"] not in used:
                sh = sho.iloc[0]
                qty = int(s["shares"] + sh["shares"])
                price = sh["short_price"]
                print(f" PAIRED SHORT {qty}@{price:.2f}")
                print(f"   → Market Sell {qty} @ {price:.2f}")
                print(f"   → Limit Sell  {qty} @ {price * 0.998:.2f}")
                used.add(s["sell_date"])

        # Einzelorders BUY
        for _, b in buys.iterrows():
            if b["buy_date"] in used: continue
            qty = int(b["shares"]); price = b["buy_price"]
            print(f" BUY   {qty}@{price:.2f}")
            print(f"   → Market Buy  {qty} @ {price:.2f}")
            print(f"   → Limit Buy   {qty} @ {price * 1.002:.2f}")
            used.add(b["buy_date"])

        # Einzelorders SELL
        for _, s in sells.iterrows():
            if s["sell_date"] in used: continue
            qty = int(s["shares"]); price = s["sell_price"]
            print(f" SELL  {qty}@{price:.2f}")
            print(f"   → Market Sell {qty} @ {price:.2f}")
            print(f"   → Limit Sell  {qty} @ {price * 0.998:.2f}")
            used.add(s["sell_date"])

        # Einzelorders COVER
        for _, c in covers.iterrows():
            if c["cover_date"] in used: continue
            qty = int(c["shares"]); price = c["cover_price"]
            print(f" COVER {qty}@{price:.2f}")
            print(f"   → Market Buy  {qty} @ {price:.2f}")
            print(f"   → Limit Buy   {qty} @ {price * 1.002:.2f}")
            used.add(c["cover_date"])

        # Einzelorders SHORT
        for _, sh in shorts.iterrows():
            if sh["short_date"] in used: continue
            qty = int(sh["shares"]); price = sh["short_price"]
            print(f" SHORT {qty}@{price:.2f}")
            print(f"   → Market Sell {qty} @ {price:.2f}")
            print(f"   → Limit Sell  {qty} @ {price * 0.998:.2f}")
            used.add(sh["short_date"])

import os
import pandas as pd
from pandas.errors import EmptyDataError
from tickers_config import tickers  # falls nicht schon oben importiert

def test_extended_for_date(date_str, report_dir="reports"):
    """
    Zeigt Extended-Signale für ein Datum an.
    Liest CSVs aus report_dir und filtert nach Spalte 'date'.
    """
    today = pd.to_datetime(date_str).date()
    print(f"\n=== EXTENDED SIGNALS für {today} ===")

    for ticker, cfg in tickers.items():
        # Pfade zusammenbauen
        path_l = os.path.join(report_dir, f"extended_Long_signals_{ticker}.csv")
        path_s = os.path.join(report_dir, f"extended_Short_signals_{ticker}.csv")

        # Long-CSV einlesen
        try:
            ext_l = pd.read_csv(path_l)
            if "date" not in ext_l.columns:
                ext_l = ext_l.reset_index().rename(columns={"index":"date"})
            ext_l["date"] = pd.to_datetime(ext_l["date"], errors="coerce")
        except (FileNotFoundError, EmptyDataError, ValueError):
            ext_l = pd.DataFrame()

        # Short-CSV einlesen
        try:
            ext_s = pd.read_csv(path_s)
            if "date" not in ext_s.columns:
                ext_s = ext_s.reset_index().rename(columns={"index":"date"})
            ext_s["date"] = pd.to_datetime(ext_s["date"], errors="coerce")
        except (FileNotFoundError, EmptyDataError, ValueError):
            ext_s = pd.DataFrame()

        # Filtern und Ausgeben
        sel_l = ext_l.loc[ext_l["date"].dt.date == today]
        sel_s = ext_s.loc[ext_s["date"].dt.date == today]

        if not sel_l.empty:
            print(f"\n{ticker} EXT LONG:")
            print(sel_l.to_string(index=False))
        if not sel_s.empty:
            print(f"\n{ticker} EXT SHORT:")
            print(sel_s.to_string(index=False))

def test_trading_for_date(ib, date_str, report_dir="reports"):
    import pandas as pd
    from pandas.errors import EmptyDataError
    from tickers_config import tickers

    today = pd.to_datetime(date_str).date()
    print(f"\n=== TESTMODE TRADES für {today} ===")

    for ticker, cfg in tickers.items():
        # 1) Tabellen einlesen
        def load(fname, date_cols, cols):
            try:
                df = pd.read_csv(f"{report_dir}/{fname}", parse_dates=date_cols)
            except (FileNotFoundError, EmptyDataError):
                df = pd.DataFrame(columns=cols)
            for c in date_cols:
                if c in df.columns:
                    df[c] = pd.to_datetime(df[c], errors="coerce")
            return df

        trades_l = load(f"trades_long_{ticker}.csv",
                        ["buy_date","sell_date"],
                        ["buy_date","sell_date","shares","buy_price","sell_price"])
        trades_s = load(f"trades_short_{ticker}.csv",
                        ["short_date","cover_date"],
                        ["short_date","cover_date","shares","short_price","cover_price"])

        # 2) Heute gefilterte Einträge
        buys   = trades_l.loc[trades_l["buy_date"].dt.date   == today]
        covers = trades_s.loc[trades_s["cover_date"].dt.date == today]
        sells  = trades_l.loc[trades_l["sell_date"].dt.date  == today]
        shorts = trades_s.loc[trades_s["short_date"].dt.date == today]

        # 3) Netto-Buy = alle Käufe + alle Cover (alles Käufe von heute)
        buy_qty   = buys["shares"].sum()
        cover_qty = covers["shares"].sum()
        net_buy   = buy_qty + cover_qty

        if net_buy > 0:
            # gewichteter Durchschnittspreis
            cost_buy   = (buys["shares"]   * buys["buy_price"]).sum()
            cost_cover = (covers["shares"] * covers["cover_price"]).sum()
            avg_price  = (cost_buy + cost_cover) / net_buy

            print(f"\n📦 NET TOP-LONG für {ticker}:")
            print(f" NET BUY {net_buy}@{avg_price:.2f}")
            print(f"   → MARKET BUY {net_buy}@{avg_price:.2f}")
            print(f"   → LIMIT  BUY {net_buy}@{avg_price * 1.002:.2f}")

        # 4) Netto-Short = alle Shorts + alle Sells (alles Verkäufe/Shorts von heute)
        sell_qty  = sells["shares"].sum()
        short_qty = shorts["shares"].sum()
        net_short = sell_qty + short_qty

        if net_short > 0:
            cost_sell  = (sells["shares"]  * sells["sell_price"]).sum()
            cost_short = (shorts["shares"] * shorts["short_price"]).sum()
            avg_price  = (cost_sell + cost_short) / net_short

            print(f"\n📦 NET TOP-SHORT für {ticker}:")
            print(f" NET SELL {net_short}@{avg_price:.2f}")
            print(f"   → MARKET SELL {net_short}@{avg_price:.2f}")
            print(f"   → LIMIT  SELL {net_short}@{avg_price * 0.998:.2f}")

import os
import pandas as pd
from pandas.errors import EmptyDataError
from tickers_config import tickers

def test_extended_for_date(date_str, report_dir="reports"):
    """
    Zeigt Extended-Signale für ein Datum an.
    Liest CSVs aus report_dir und filtert nach Spalte 'date'.
    """
    today = pd.to_datetime(date_str).date()
    print(f"\n=== EXTENDED SIGNALS für {today} ===")

    for ticker, cfg in tickers.items():
        path_l = os.path.join(report_dir, f"extended_Long_signals_{ticker}.csv")
        path_s = os.path.join(report_dir, f"extended_Short_signals_{ticker}.csv")

        try:
            ext_l = pd.read_csv(path_l)
            if "date" not in ext_l.columns:
                ext_l = ext_l.reset_index().rename(columns={"index":"date"})
            ext_l["date"] = pd.to_datetime(ext_l["date"], errors="coerce")
        except (FileNotFoundError, EmptyDataError, ValueError):
            ext_l = pd.DataFrame()

        try:
            ext_s = pd.read_csv(path_s)
            if "date" not in ext_s.columns:
                ext_s = ext_s.reset_index().rename(columns={"index":"date"})
            ext_s["date"] = pd.to_datetime(ext_s["date"], errors="coerce")
        except (FileNotFoundError, EmptyDataError, ValueError):
            ext_s = pd.DataFrame()

        sel_l = ext_l.loc[ext_l["date"].dt.date == today]
        sel_s = ext_s.loc[ext_s["date"].dt.date == today]

        if not sel_l.empty:
            print(f"\n{ticker} EXT LONG:")
            print(sel_l.to_string(index=False))
        if not sel_s.empty:
            print(f"\n{ticker} EXT SHORT:")
            print(sel_s.to_string(index=False))

def preview_trades_for_today(ib, date_str=None, report_dir="reports"):
    from datetime import date
    ds = date_str or str(date.today())
    print(f"\n🔍 PREVIEW TRADES für {ds}")
    test_trading_for_date(ib, ds)
    test_extended_for_date(ds, report_dir=report_dir)


# ————————————————————————————————————————————————
def trade_trading_for_today(ib, date_str=None):
    """
    Wrapper: ruft test_trading_for_date mit heutigem Datum (oder date_str) auf.
    """
    ds = date_str or str(date.today())
    print(f"\n📆 TRADE FOR {ds}")
    test_trading_for_date(ib, ds)
