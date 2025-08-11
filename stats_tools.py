import pandas as pd

def stats(trades, name="Trades"):
    if not trades:
        print(f"{name}: No trades")
        return

    pnl_sum = round(sum(t.get("pnl", 0.0) or 0.0 for t in trades), 2)
    pnl_avg = round(pnl_sum / len(trades), 2)
    pnl_max = round(max(t["pnl"] for t in trades), 2)
    pnl_min = round(min(t["pnl"] for t in trades), 2)
    winners = [t for t in trades if t["pnl"] > 0]
    losers = [t for t in trades if t["pnl"] <= 0]
    win_rate = round(len(winners) / len(trades) * 100, 1)

    print(f"\n{name}:")
    print(f"  Trades: {len(trades)}")
    print(f"  Sum PnL: {pnl_sum}")
    print(f"  Avg PnL: {pnl_avg}")
    print(f"  Max PnL: {pnl_max}")
    print(f"  Min PnL: {pnl_min}")
    print(f"  Winning Trades: {len(winners)} ({win_rate}%)")
    print(f"  Losing Trades: {len(losers)} ({round(100 - win_rate, 1)}%)")


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

