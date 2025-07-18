import pandas as pd

def stats(trades, name="Trades"):
    if not trades:
        print(f"{name}: Keine Trades vorhanden.")
        return

    pnl_sum = round(sum(t.get("pnl", 0.0) or 0.0 for t in trades), 2)
    pnl_avg = round(pnl_sum / len(trades), 2)
    pnl_max = round(max(t["pnl"] for t in trades), 2)
    pnl_min = round(min(t["pnl"] for t in trades), 2)
    winners = [t for t in trades if t["pnl"] > 0]
    losers = [t for t in trades if t["pnl"] <= 0]
    win_rate = round(len(winners) / len(trades) * 100, 1)

    print(f"\n{name}:")
    print(f"  Anzahl Trades: {len(trades)}")
    print(f"  Summe PnL: {pnl_sum}")
    print(f"  Ø PnL: {pnl_avg}")
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
    print(f"{ticker}: Stats als CSV gespeichert – {filename}")

def write_md_report(ticker, stats_text, matched_long, matched_short, ext_long, ext_short, path):
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# Bericht für {ticker} – {pd.Timestamp.today().date()}\n\n")
        f.write(f"## Statistiken\n{stats_text}\n\n")

        f.write("## Matched Long Trades\n")
        if matched_long:
            f.write(pd.DataFrame(matched_long).to_markdown(index=False) + "\n\n")
        else:
            f.write("_Keine Long-Trades gefunden._\n\n")

        f.write("## Matched Short Trades\n")
        if matched_short:
            f.write(pd.DataFrame(matched_short).to_markdown(index=False) + "\n\n")
        else:
            f.write("_Keine Short-Trades gefunden._\n\n")

        f.write("## Extended Long Signals\n")
        if not ext_long.empty:
            f.write(ext_long.to_markdown(index=False) + "\n\n")
        else:
            f.write("_Keine Extended Long-Signale._\n\n")

        f.write("## Extended Short Signals\n")
        if not ext_short.empty:
            f.write(ext_short.to_markdown(index=False) + "\n\n")
        else:
            f.write("_Keine Extended Short-Signale._\n\n")

import markdown2
import pdfkit

def convert_md_to_html(md_path, html_path):
    with open(md_path, "r", encoding="utf-8") as f:
        html = markdown2.markdown(f.read())
    with open(html_path, "w", encoding="utf-8") as out:
        out.write(html)

def convert_md_to_pdf(md_path, pdf_path):
    html = markdown2.markdown(open(md_path, "r", encoding="utf-8").read())
    config = pdfkit.configuration(wkhtmltopdf=r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe")
    pdfkit.from_string(html, pdf_path, configuration=config)

