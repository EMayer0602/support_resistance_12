from ib_insync import IB, Contract
from tickers_config import tickers
from trade_execution import execute_trades, get_backtest_price, plan_trade_qty
from simulation_utils import generate_backtest_date_range
from backtesting_core import run_full_backtest
from stats_tools import stats
from simulation_utils import compute_equity_curve
from plot_utils import plot_combined_chart_and_equity
import json
import os
import sys
from datetime import datetime
import pandas as pd

def load_trades_for_day(date_str, json_path="trades_by_day.json"):
    if not os.path.exists(json_path):
        print(f"⚠️ Datei {json_path} nicht gefunden.")
        return [], {}
    try:
        with open(json_path, "r") as f:
            all_trades = json.load(f)
    except Exception as e:
        print(f"⚠️ Fehler beim Laden von {json_path}: {e}")
        return [], {}
    trades = all_trades.get(date_str, [])
    portfolio = {}
    for t in trades:
        delta = t["qty"] if t["side"] in ("BUY", "COVER") else -t["qty"]
        portfolio[t["symbol"]] = portfolio.get(t["symbol"], 0) + delta
    return trades, portfolio

def print_trade_summary(trades, portfolio_snapshot):
    if not trades:
        print("\nℹ️ Keine Trades generiert.")
        return
    entry_trades = [t for t in trades if t["side"] in ("BUY", "SHORT")]
    exit_trades = [t for t in trades if t["side"] in ("SELL", "COVER")]
    print("\n📈 Einstiegstrades (neu investiert / leerverkauft)")
    if entry_trades:
        print(f"{'Symbol':<8} {'Aktion':<7} {'Stück':>5} {'Preis':>10}")
        print("-" * 36)
        for t in entry_trades:
            print(f"{t['symbol']:<8} {t['side']:<7} {t['qty']:>5} {t['price']:>10.2f}")
    else:
        print("Keine Einstiegstrades.")
    print("\n📉 Exit-Trades (verkaufte / gedeckte Bestände)")
    if exit_trades:
        print(f"{'Symbol':<8} {'Aktion':<7} {'Stück':>5} {'Preis':>10} {'Bestand':>10}")
        print("-" * 50)
        for t in exit_trades:
            owned = portfolio_snapshot.get(t['symbol'], 0)
            print(f"{t['symbol']:<8} {t['side']:<7} {t['qty']:>5} {t['price']:>10.2f} {owned:>10}")
    else:
        print("Keine Exit-Trades.")

def main():
    if len(sys.argv) < 2:
        print("⚠️ Bitte gib einen Modus an: testdate, tradedate, listdays, fullbacktest")
        print("Beispiele:")
        print("  python runner.py testdate 2025-07-15")
        print("  python runner.py tradedate 2025-07-15")
        print("  python runner.py listdays")
        print("  python runner.py fullbacktest")
        return

    mode = sys.argv[1].lower()
    
    # Validate arguments based on mode
    if mode in ["testdate", "tradedate"] and len(sys.argv) < 3:
        print(f"⚠️ Der Modus '{mode}' benötigt ein Datum als zweiten Parameter.")
        print(f"Beispiel: python runner.py {mode} 2025-07-15")
        return
    
    # Only connect to IB for tradedate and fullbacktest modes
    ib = None
    if mode in ["tradedate", "fullbacktest"]:
        ib = IB()
        try:
            ib.connect("127.0.0.1", 7497, clientId=1)
        except Exception as e:
            print(f"⚠️ Fehler bei IB-Verbindung: {e}")
            print("Für 'testdate' und 'listdays' ist keine IB-Verbindung erforderlich.")
            return
    
    if mode == "testdate":
        date_str = sys.argv[2]
        trades, portfolio = load_trades_for_day(date_str)
        if not trades:
            print(f"\n📅 {date_str}: Keine Trades an diesem Tag.")
            print("💡 Tipp: Führe zuerst 'python runner.py fullbacktest' aus, um Trades zu generieren.")
            return
        print_trade_summary(trades, portfolio)

    elif mode == "tradedate":
        tradedate = sys.argv[2]
        trades, _ = load_trades_for_day(tradedate)
        if not trades:
            print(f"\n📅 {tradedate}: Kein Trade aus dem Backtest.")
            return
        # When executing trades, you can use conID to build IB contracts
        for t in trades:
            cfg = tickers[t['symbol']]
            contract = Contract(conId=cfg["conID"], exchange="SMART", currency="USD")
            # Pass contract to your execute_trades logic as needed
            # execute_trades(ib, t, contract)
        # If execute_trades expects only the trade dict, and handles contract creation, update it accordingly

    elif mode == "listdays":
        json_path = "trades_by_day.json"
        if not os.path.exists(json_path):
            print(f"⚠️ Datei {json_path} nicht gefunden.")
            return
        with open(json_path, "r") as f:
            data = json.load(f)
        active_days = [day for day, trades in data.items() if trades]
        if not active_days:
            print("ℹ️ Keine aktiven Tage mit Trades gefunden.")
            return
        print("\n📅 Tage mit aktiven Trades im Backtest:")
        for day in sorted(active_days):
            print(f"  • {day}")

    elif mode == "fullbacktest":
        # 1) Run core backtest and capture structured results
        results = run_full_backtest(ib)

        # 2) Build daily trade ledger from MATCHED trade CSVs (entry/exit pairs)
        backtest_trades: dict[str, list] = {}
        for symbol, cfg in tickers.items():
            # LONG matched trades
            long_path = f"trades_long_{symbol}.csv"
            if cfg.get("long", False) and os.path.exists(long_path):
                try:
                    df_long = pd.read_csv(long_path, parse_dates=["buy_date","sell_date"])
                except Exception as e:
                    print(f"WARN cannot read {long_path}: {e}")
                    df_long = pd.DataFrame()
                for _, row in df_long.iterrows():
                    b = row.get("buy_date")
                    s = row.get("sell_date")
                    shares = int(row.get("shares", 0) or 0)
                    b_price = row.get("buy_price")
                    s_price = row.get("sell_price")
                    is_artificial = bool(row.get("artificial_close"))
                    if pd.notna(b):
                        ds = pd.Timestamp(b).strftime('%Y-%m-%d')
                        backtest_trades.setdefault(ds, []).append({
                            "symbol": symbol, "side": "BUY", "qty": shares,
                            "price": None if pd.isna(b_price) else float(b_price),
                            "source": "LONG"
                        })
                    # For artificial close trades we suppress the forced SELL leg (not a real signal-based exit)
                    if pd.notna(s) and not is_artificial:
                        ds = pd.Timestamp(s).strftime('%Y-%m-%d')
                        backtest_trades.setdefault(ds, []).append({
                            "symbol": symbol, "side": "SELL", "qty": shares,
                            "price": None if pd.isna(s_price) else float(s_price),
                            "source": "LONG"
                        })
            # SHORT matched trades
            short_path = f"trades_short_{symbol}.csv"
            if cfg.get("short", False) and os.path.exists(short_path):
                try:
                    df_short = pd.read_csv(short_path, parse_dates=["short_date","cover_date"])
                except Exception as e:
                    print(f"WARN cannot read {short_path}: {e}")
                    df_short = pd.DataFrame()
                for _, row in df_short.iterrows():
                    sh = row.get("short_date")
                    cv = row.get("cover_date")
                    shares = int(row.get("shares", 0) or 0)
                    sh_price = row.get("short_price")
                    cv_price = row.get("cover_price")
                    is_artificial = bool(row.get("artificial_close"))
                    if pd.notna(sh):
                        ds = pd.Timestamp(sh).strftime('%Y-%m-%d')
                        backtest_trades.setdefault(ds, []).append({
                            "symbol": symbol, "side": "SHORT", "qty": shares,
                            "price": None if pd.isna(sh_price) else float(sh_price),
                            "source": "SHORT"
                        })
                    # Suppress artificial forced COVER legs
                    if pd.notna(cv) and not is_artificial:
                        ds = pd.Timestamp(cv).strftime('%Y-%m-%d')
                        backtest_trades.setdefault(ds, []).append({
                            "symbol": symbol, "side": "COVER", "qty": shares,
                            "price": None if pd.isna(cv_price) else float(cv_price),
                            "source": "SHORT"
                        })

        # 3) Sort dates and trades for stable output
        ordered = {d: backtest_trades[d] for d in sorted(backtest_trades.keys())}
        with open("trades_by_day.json", "w") as f:
            json.dump(ordered, f, indent=2)
        print("[DONE] Full-Backtest abgeschlossen und Trades exportiert (matched trades basis).")

        # 2b) Export unified JSON schema (aligned with comprehensive script)
        export_data = {}
        for tkr, data in (results or {}).items():
            t_entry = { 'data_info': data.get('data_info', {}) }
            for side in ['long','short']:
                if side not in data:
                    continue
                sd = data[side]
                # Map signals (extended) similar to comprehensive export
                mapped_signals = []
                for row in sd.get('extended_signals_data', []):
                    if side=='long':
                        action = row.get('Long Action')
                        date_raw = row.get('Long Date detected')
                    else:
                        action = row.get('Short Action')
                        date_raw = row.get('Short Date detected')
                    date_str = str(date_raw)[:10]
                    if not action or not date_str or date_str=='nan':
                        continue
                    price = row.get('Level trade') or row.get('Level Close')
                    try:
                        price_val = float(price) if price is not None and price==price else None
                    except Exception:
                        price_val = None
                    mapped_signals.append({
                        'date': date_str,
                        'action': action.upper(),
                        'price': price_val,
                        'signal_type': row.get('Supp/Resist'),
                        'p_param': sd.get('parameters',{}).get('p'),
                        'tw_param': sd.get('parameters',{}).get('tw')
                    })
                t_entry[side] = {
                    'parameters': sd.get('parameters', {}),
                    'signals': mapped_signals,
                    'trades': sd.get('trades', []),
                    'stats': sd.get('stats', {}),
                    'equity_curve': sd.get('equity_curve', [])
                }
            export_data[tkr] = t_entry
        with open('runner_fullbacktest_results.json','w') as jf:
            json.dump(export_data, jf, indent=2, default=str)
        print("[SAVE] JSON export -> runner_fullbacktest_results.json")

        # 2c) Build aggregated HTML report
        try:
            html = [
                "<html><head><meta charset='utf-8'><title>Runner Backtest Report</title>",
                "<style>body{font-family:Arial;background:#111;color:#eee;margin:20px;}table{border-collapse:collapse;width:100%;margin-bottom:30px;}th,td{border:1px solid #444;padding:4px 6px;font-size:12px;}th{background:#222;}tr:nth-child(even){background:#1d1d1d;}h1,h2,h3{color:#fff;} .pos{color:#4caf50;} .neg{color:#ff5252;} details{margin:12px 0;} summary{cursor:pointer;font-weight:bold;} .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;} .card{background:#1c1c1c;padding:8px 10px;border:1px solid #333;border-radius:6px;} a{color:#64b5f6;text-decoration:none;} a:hover{text-decoration:underline;}</style></head><body>",
                f"<h1>Runner Full Backtest Report - {datetime.now().strftime('%Y-%m-%d %H:%M')}</h1>"
            ]
            # Summary table
            html.append("<h2>Summary</h2><table><tr><th>Ticker</th><th>Side</th><th>p</th><th>tw</th><th>Trades</th><th>Win%</th><th>Sum PnL</th><th>Avg PnL</th><th>MaxDD%</th><th>Init</th><th>Final</th><th>ROI%</th></tr>")
            for tkr, data in (results or {}).items():
                for side in ['long','short']:
                    if side not in data: continue
                    st = data[side].get('stats', {})
                    p = data[side].get('parameters',{}).get('p')
                    tw = data[side].get('parameters',{}).get('tw')
                    trades_ct = st.get('trades',0)
                    win_rate = st.get('win_rate',0)
                    sum_pnl = st.get('sum_pnl',0)
                    avg_pnl = st.get('avg_pnl',0)
                    maxdd = st.get('max_drawdown_pct',0)
                    init_cap = st.get('initial_capital',0) or 0
                    final_cap = st.get('final_capital',0) or 0
                    roi = (final_cap/init_cap -1)*100 if init_cap else 0
                    html.append(
                        f"<tr><td>{tkr}</td><td>{side.upper()}</td><td>{p}</td><td>{tw}</td><td>{trades_ct}</td><td>{win_rate:.1f}</td><td class='{'pos' if sum_pnl>=0 else 'neg'}'>{sum_pnl:.2f}</td><td>{avg_pnl:.2f}</td><td>{maxdd:.2f}</td><td>{init_cap:.2f}</td><td>{final_cap:.2f}</td><td class='{'pos' if roi>=0 else 'neg'}'>{roi:.2f}</td></tr>"
                    )
            html.append("</table>")
            # Per ticker detail
            for tkr, data in (results or {}).items():
                html.append(f"<h2>{tkr}</h2>")
                for side in ['long','short']:
                    if side not in data: continue
                    sd = data[side]
                    st = sd.get('stats', {})
                    html.append(f"<h3>{side.upper()} Strategy</h3>")
                    html.append("<div class='grid'>")
                    for label,val in [
                        ("p", sd.get('parameters',{}).get('p')),
                        ("tw", sd.get('parameters',{}).get('tw')),
                        ("Trades", st.get('trades')),
                        ("Win%", st.get('win_rate')),
                        ("SumPnL", st.get('sum_pnl')),
                        ("AvgPnL", st.get('avg_pnl')),
                        ("MaxDD%", st.get('max_drawdown_pct')),
                        ("InitCap", st.get('initial_capital')),
                        ("FinalCap", st.get('final_capital'))
                    ]:
                        html.append(f"<div class='card'><b>{label}</b><br>{val}</div>")
                    html.append("</div>")
                    # Extended signals
                    ext_rows = sd.get('extended_signals_data', [])
                    html.append(f"<details><summary>Extended Signals ({len(ext_rows)})</summary>")
                    if ext_rows:
                        keep_cols = [c for c in ["Long Date detected","Long Action","Short Date detected","Short Action","Supp/Resist","Level trade","Level Close","p_param","tw_param"] if any(c in r for r in ext_rows)]
                        html.append("<table><tr>" + ''.join(f"<th>{c}</th>" for c in keep_cols) + "</tr>")
                        for r in ext_rows[:400]:
                            html.append("<tr>" + ''.join(f"<td>{r.get(c,'')}</td>" for c in keep_cols) + "</tr>")
                        if len(ext_rows) > 400:
                            html.append(f"<tr><td colspan='{len(keep_cols)}'>... {len(ext_rows)-400} more rows truncated ...</td></tr>")
                        html.append("</table>")
                    else:
                        html.append("<p>No signals</p>")
                    html.append("</details>")
                    # Matched trades
                    trades_rows = sd.get('trades', [])
                    html.append(f"<details><summary>Matched Trades ({len(trades_rows)})</summary>")
                    if trades_rows:
                        cols = list({k for trd in trades_rows for k in trd.keys()})
                        html.append("<table><tr>" + ''.join(f"<th>{c}</th>" for c in cols) + "</tr>")
                        for trd in trades_rows[:400]:
                            html.append("<tr>" + ''.join(f"<td>{trd.get(c,'')}</td>" for c in cols) + "</tr>")
                        if len(trades_rows) > 400:
                            html.append(f"<tr><td colspan='{len(cols)}'>... {len(trades_rows)-400} more rows truncated ...</td></tr>")
                        html.append("</table>")
                    else:
                        html.append("<p>No trades</p>")
                    html.append("</details>")
            html.append("</body></html>")
            with open('runner_fullbacktest_report.html','w', encoding='utf-8') as hf:
                hf.write('\n'.join(html))
            print("[SAVE] HTML report -> runner_fullbacktest_report.html")
        except Exception as rep_e:
            print(f"[WARN] Could not create runner HTML report: {rep_e}")

        # 4) Standardisierte Statistik-Ausgabe (gleiche Formatierung für alle Ticker)
        print("\n[SUMMARY] Zusammenfassung je Ticker (Long/Short):")
        for symbol, cfg in tickers.items():
            data_path = f"{symbol}_data.csv"
            if not os.path.exists(data_path):
                continue
            try:
                df_price = pd.read_csv(data_path, parse_dates=["date"], index_col="date")
            except Exception:
                continue

            # LONG
            if cfg.get("long", False) and os.path.exists(f"trades_long_{symbol}.csv"):
                df_long = pd.read_csv(f"trades_long_{symbol}.csv", parse_dates=["buy_date", "sell_date"])
                trades_long = df_long.to_dict("records")
                eq_long = compute_equity_curve(df_price, trades_long, cfg.get("initialCapitalLong", 0), long=True) if trades_long else []
                final_cap_long = eq_long[-1] if eq_long else cfg.get("initialCapitalLong", 0)
                stats(trades_long, f"{symbol} LONG", initial_capital=cfg.get("initialCapitalLong"), final_capital=final_cap_long, equity_curve=eq_long)
                # Equity tail diagnostics (LONG)
                if eq_long:
                    tail5 = eq_long[-5:] if len(eq_long) >= 5 else eq_long
                    diff = final_cap_long - eq_long[-1]
                    print(f"[LONG EQUITY] {symbol} tail5={[round(v,2) for v in tail5]} final_cap={final_cap_long:.2f} eq_last={eq_long[-1]:.2f} diff={diff:.4f}")
                # Console matched trade table (LONG)
                if trades_long:
                    print(f"[MATCHED LONG TABLE] {symbol} trades={len(trades_long)} (showing up to 50)")
                    sample_long = trades_long[:50]
                    core_cols = ["buy_date","buy_price","sell_date","sell_price","shares","pnl"]
                    extra_keys = []
                    for tr in sample_long:
                        for k in tr.keys():
                            if k == 'artificial_close':
                                continue
                            if k not in core_cols and k not in extra_keys and not k.startswith('_'):
                                extra_keys.append(k)
                    add_artificial_col = any(tr.get('artificial_close') for tr in sample_long)
                    cols = core_cols + extra_keys
                    if add_artificial_col and "artificial_close" not in cols:
                        cols.append("artificial_close")
                    rows_fmt = []
                    for i, tr in enumerate(sample_long, start=1):
                        artificial = 'Y' if tr.get('artificial_close') else ''
                        row = {
                            'idx': i,
                            'buy_date': tr.get('buy_date'),
                            'buy_price': tr.get('buy_price'),
                            'sell_date': tr.get('sell_date'),
                            'sell_price': tr.get('sell_price'),
                            'shares': tr.get('shares'),
                            'pnl': tr.get('pnl'),
                        }
                        if add_artificial_col:
                            row['artificial_close'] = artificial
                        for ek in extra_keys:
                            row[ek] = tr.get(ek)
                        rows_fmt.append(row)
                    def fmt(v):
                        if isinstance(v, float):
                            return f"{v:.6g}" if abs(v) >= 1e-3 else f"{v:.4g}"
                        return '' if v is None else str(v)
                    headers = ["#"] + cols
                    widths = {h: len(h) for h in headers}
                    for r in rows_fmt:
                        widths['#'] = max(widths['#'], len(str(r['idx'])))
                        for c in cols:
                            widths[c] = max(widths[c], len(fmt(r.get(c))))
                    for k in widths:
                        widths[k] = min(widths[k], 36)
                    def header_label(name: str) -> str:
                        if name == 'artificial_close':
                            return 'ArtClose'
                        return name.replace('_',' ').title()
                    header_line = ' | '.join([
                        f"#".ljust(widths['#'])
                    ] + [header_label(c).ljust(widths[c]) for c in cols])
                    print(header_line)
                    print('-' * len(header_line))
                    for r in rows_fmt:
                        line = ' | '.join([
                            str(r['idx']).ljust(widths['#'])
                        ] + [fmt(r.get(c)).ljust(widths[c]) for c in cols])
                        print(line)
                    if add_artificial_col:
                        art_pnl = sum(tr.get('pnl',0) for tr in trades_long if tr.get('artificial_close'))
                        art_ct = sum(1 for tr in trades_long if tr.get('artificial_close'))
                        print(f"[LONG ARTIFICIAL SUMMARY] {symbol} artificial_trades={art_ct} sum_pnl={art_pnl:.2f}")
            else:
                print(f"\n{symbol} LONG: Keine Trades oder deaktiviert")

            # SHORT
            if cfg.get("short", False) and os.path.exists(f"trades_short_{symbol}.csv"):
                df_short = pd.read_csv(f"trades_short_{symbol}.csv", parse_dates=["short_date", "cover_date"])
                trades_short = df_short.to_dict("records")
                eq_short = compute_equity_curve(df_price, trades_short, cfg.get("initialCapitalShort", 0), long=False) if trades_short else []
                final_cap_short = eq_short[-1] if eq_short else cfg.get("initialCapitalShort", 0)
                stats(trades_short, f"{symbol} SHORT", initial_capital=cfg.get("initialCapitalShort"), final_capital=final_cap_short, equity_curve=eq_short)
                if eq_short:
                    tail5s = eq_short[-5:] if len(eq_short) >= 5 else eq_short
                    diff_s = final_cap_short - eq_short[-1]
                    print(f"[SHORT EQUITY] {symbol} tail5={[round(v,2) for v in tail5s]} final_cap={final_cap_short:.2f} eq_last={eq_short[-1]:.2f} diff={diff_s:.4f}")
                if trades_short:
                    print(f"[MATCHED SHORT TABLE] {symbol} trades={len(trades_short)} (showing up to 50)")
                    sample_short = trades_short[:50]
                    core_cols_s = ["short_date","short_price","cover_date","cover_price","shares","pnl"]
                    extra_keys_s = []
                    for tr in sample_short:
                        for k in tr.keys():
                            if k == 'artificial_close':
                                continue
                            if k not in core_cols_s and k not in extra_keys_s and not k.startswith('_'):
                                extra_keys_s.append(k)
                    add_artificial_col_s = any(tr.get('artificial_close') for tr in sample_short)
                    cols_s = core_cols_s + extra_keys_s
                    if add_artificial_col_s and "artificial_close" not in cols_s:
                        cols_s.append("artificial_close")
                    rows_fmt_s = []
                    for i, tr in enumerate(sample_short, start=1):
                        artificial = 'Y' if tr.get('artificial_close') else ''
                        row = {
                            'idx': i,
                            'short_date': tr.get('short_date'),
                            'short_price': tr.get('short_price'),
                            'cover_date': tr.get('cover_date'),
                            'cover_price': tr.get('cover_price'),
                            'shares': tr.get('shares'),
                            'pnl': tr.get('pnl'),
                        }
                        if add_artificial_col_s:
                            row['artificial_close'] = artificial
                        for ek in extra_keys_s:
                            row[ek] = tr.get(ek)
                        rows_fmt_s.append(row)
                    def fmt_s(v):
                        if isinstance(v, float):
                            return f"{v:.6g}" if abs(v) >= 1e-3 else f"{v:.4g}"
                        return '' if v is None else str(v)
                    headers_s = ["#"] + cols_s
                    widths_s = {h: len(h) for h in headers_s}
                    for r in rows_fmt_s:
                        widths_s['#'] = max(widths_s['#'], len(str(r['idx'])))
                        for c in cols_s:
                            widths_s[c] = max(widths_s[c], len(fmt_s(r.get(c))))
                    for k in widths_s:
                        widths_s[k] = min(widths_s[k], 36)
                    def header_label_s(name: str) -> str:
                        if name == 'artificial_close':
                            return 'ArtClose'
                        return name.replace('_',' ').title()
                    header_line_s = ' | '.join([
                        f"#".ljust(widths_s['#'])
                    ] + [header_label_s(c).ljust(widths_s[c]) for c in cols_s])
                    print(header_line_s)
                    print('-' * len(header_line_s))
                    for r in rows_fmt_s:
                        line_s = ' | '.join([
                            str(r['idx']).ljust(widths_s['#'])
                        ] + [fmt_s(r.get(c)).ljust(widths_s[c]) for c in cols_s])
                        print(line_s)
                    if add_artificial_col_s:
                        art_pnl_s = sum(tr.get('pnl',0) for tr in trades_short if tr.get('artificial_close'))
                        art_ct_s = sum(1 for tr in trades_short if tr.get('artificial_close'))
                        print(f"[SHORT ARTIFICIAL SUMMARY] {symbol} artificial_trades={art_ct_s} sum_pnl={art_pnl_s:.2f}")
            else:
                print(f"\n{symbol} SHORT: Keine Trades oder deaktiviert")

    else:
        print(f"⚠️ Unbekannter Modus: {mode}")

    if ib is not None:
        ib.disconnect()

if __name__ == "__main__":
    main()
