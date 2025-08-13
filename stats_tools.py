import pandas as pd

def _max_drawdown(equity_list):
    if not equity_list:
        return 0.0
    peak = equity_list[0]
    max_dd = 0.0
    for v in equity_list:
        if v > peak:
            peak = v
        dd = (peak - v) / peak if peak else 0.0
        if dd > max_dd:
            max_dd = dd
    return round(max_dd * 100, 2)  # percentage

def stats(trades, name="Trades", initial_capital=None, final_capital=None, equity_curve=None):
    """Print trade statistics plus capital & max drawdown.

    Parameters:
        trades (list[dict]): matched trades
        name (str): label
        initial_capital (float|None): starting capital (optional)
        final_capital (float|None): final capital (optional)
        equity_curve (list|None): equity values over time for drawdown calc
    """
    if not trades:
        print(f"{name}: No trades")
        return {
            "trades": 0,
            "sum_pnl": 0.0,
            "avg_pnl": 0.0,
            "win_rate": 0.0,
            "max_drawdown_pct": _max_drawdown(equity_curve or [])
        }

    pnl_values = [t.get("pnl", 0.0) or 0.0 for t in trades]
    pnl_sum = round(sum(pnl_values), 2)
    pnl_avg = round(pnl_sum / len(trades), 2)
    pnl_max = round(max(pnl_values), 2)
    pnl_min = round(min(pnl_values), 2)
    winners = [p for p in pnl_values if p > 0]
    losers = [p for p in pnl_values if p <= 0]
    win_rate = round(len(winners) / len(trades) * 100, 1)
    max_dd_pct = _max_drawdown(equity_curve or [])

    print(f"\n{name}:")
    print(f"  Trades: {len(trades)}")
    if initial_capital is not None:
        print(f"  Initial Capital: {initial_capital:.2f}")
    if final_capital is not None:
        print(f"  Final Capital:   {final_capital:.2f}")
    if initial_capital is not None and final_capital is not None:
        roi = (final_capital / initial_capital - 1) * 100 if initial_capital else 0
        print(f"  Return:          {roi:.2f}%")
    print(f"  Sum PnL: {pnl_sum}")
    print(f"  Avg PnL: {pnl_avg}")
    print(f"  Max PnL: {pnl_max}")
    print(f"  Min PnL: {pnl_min}")
    print(f"  Winning Trades: {len(winners)} ({win_rate}%)")
    print(f"  Losing  Trades: {len(losers)} ({round(100 - win_rate, 1)}%)")
    print(f"  Max Drawdown:   {max_dd_pct:.2f}%")

    return {
        "trades": len(trades),
        "sum_pnl": pnl_sum,
        "avg_pnl": pnl_avg,
        "pnl_max": pnl_max,
        "pnl_min": pnl_min,
        "win_rate": win_rate,
        "max_drawdown_pct": max_dd_pct,
        "initial_capital": initial_capital,
        "final_capital": final_capital
    }


def generate_trade_report(trades, side="long"):
    if side == "long":
        cols = ["buy_date", "sell_date", "shares", "buy_price", "sell_price", "fee", "pnl"]
    else:
        cols = ["short_date", "cover_date", "shares", "short_price", "cover_price", "fee", "pnl"]
    df = pd.DataFrame(trades)
    return df[cols] if not df.empty else pd.DataFrame()

def export_stats_csv(trades, ticker, side):
    filename = f"stats_{side}_{ticker}.csv"
    df = generate_trade_report(trades, side=side)
    df.to_csv(filename, index=False)
    print(f"{ticker}: Stats saved to CSV - {filename}")

def write_md_report(ticker, stats_text, matched_long, matched_short, ext_long, ext_short, path):
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# Report for {ticker} - {pd.Timestamp.today().date()}\n\n")
        f.write(f"## Stats\n{stats_text}\n\n")

        f.write("## Matched Long Trades\n")
        if matched_long:
            f.write(pd.DataFrame(matched_long).to_markdown(index=False) + "\n\n")
        else:
            f.write("_No long trades found._\n\n")

        f.write("## Matched Short Trades\n")
        if matched_short:
            f.write(pd.DataFrame(matched_short).to_markdown(index=False) + "\n\n")
        else:
            f.write("_No short trades found._\n\n")

        f.write("## Extended Long Signals\n")
        if ext_long is not None and not ext_long.empty:
            f.write(ext_long.to_markdown(index=False) + "\n\n")
        else:
            f.write("_No extended long signals._\n\n")

        f.write("## Extended Short Signals\n")
        if ext_short is not None and not ext_short.empty:
            f.write(ext_short.to_markdown(index=False) + "\n\n")
        else:
            f.write("_No extended short signals._\n\n")

# Optional dependencies for HTML/PDF export
try:
    import markdown2  # type: ignore
except Exception:  # pragma: no cover
    markdown2 = None

try:
    import pdfkit  # type: ignore
except Exception:  # pragma: no cover
    pdfkit = None

def convert_md_to_html(md_path, html_path):
    if markdown2 is None:
        print("HTML export skipped: markdown2 not installed")
        return
    with open(md_path, "r", encoding="utf-8") as f:
        html = markdown2.markdown(f.read())
    with open(html_path, "w", encoding="utf-8") as out:
        out.write(html)

def convert_md_to_pdf(md_path, pdf_path, wkhtmltopdf_path=r"C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe"):
    if markdown2 is None or pdfkit is None:
        print("PDF export skipped: markdown2/pdfkit not installed")
        return
    html = markdown2.markdown(open(md_path, "r", encoding="utf-8").read())
    try:
        config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)
        pdfkit.from_string(html, pdf_path, configuration=config)
    except Exception as e:
        print(f"PDF export failed: {e}")

