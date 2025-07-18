import pandas as pd
import numpy as np
import plotly.graph_objs as go
from plotly.subplots import make_subplots

# plot_utils.py
from simulation_utils import compute_equity_curve

import plotly.io as pio
from plotly.subplots import make_subplots
import plotly.graph_objs as go

# Erzwinge Browser-Renderer
pio.renderers.default = "browser"

def plot_combined_chart_and_equity(
    df, ext_long, ext_short, supp, res, trend,
    equity_long, equity_short, equity_combined, buyhold, ticker
):
    df       = df.copy()
    long_df  = ext_long.copy()  if isinstance(ext_long, pd.DataFrame)  else pd.DataFrame()
    short_df = ext_short.copy() if isinstance(ext_short, pd.DataFrame) else pd.DataFrame()

    # feste Spaltennamen laut Debug
    long_date_col   = "Long Date detected"
    long_action_col = "Long Action"
    short_date_col  = "Short Date detected"
    short_action_col= "Short Action"

    # — Candles & Marker-Indizes vorbereiten
    long_df[long_date_col]   = pd.to_datetime(long_df.get(long_date_col),   errors="coerce")
    short_df[short_date_col] = pd.to_datetime(short_df.get(short_date_col), errors="coerce")

    # — Long-Marker nur, wenn Spalten existieren
    if long_date_col in long_df.columns and long_action_col in long_df.columns:
        buy_idx  = long_df.loc[
            long_df[long_action_col].str.lower() == "buy",
            long_date_col
        ].dropna()
        sell_idx = long_df.loc[
            long_df[long_action_col].str.lower() == "sell",
            long_date_col
        ].dropna()
    else:
        buy_idx  = pd.Index([])
        sell_idx = pd.Index([])

    # — Short-Marker nur, wenn Spalten existieren
    if short_date_col in short_df.columns and short_action_col in short_df.columns:
        short_idx = short_df.loc[
            short_df[short_action_col].str.lower() == "short",
            short_date_col
        ].dropna()
        cover_idx = short_df.loc[
            short_df[short_action_col].str.lower() == "cover",
            short_date_col
        ].dropna()
    else:
        short_idx = pd.Index([])
        cover_idx = pd.Index([])

    # — Jetzt sind buy_idx, sell_idx, short_idx, cover_idx garantiert frei von NaT
    print(f"🔧 PLOT: Buy={len(buy_idx)}, Sell={len(sell_idx)}, Short={len(short_idx)}, Cover={len(cover_idx)}")

    # Filter Support/Resistance/Trend auf df-Bereich
    def _filt(s):
        if not isinstance(s, pd.Series): return pd.Series(dtype=float, index=df.index)
        mask = s.index.to_series().between(df.index.min(), df.index.max())
        mask &= s.between(df["Low"].min(), df["High"].max())
        return s[mask]

    supp_filt  = _filt(supp)
    res_filt   = _filt(res)
    trend_filt = trend if isinstance(trend, pd.Series) else pd.Series(dtype=float, index=df.index)

    # Marker-Offset
    off = (df["High"].max() - df["Low"].min()) * 0.02
    print(f"🔧 PLOT: Buy={len(buy_idx)}, Sell={len(sell_idx)}, Short={len(short_idx)}, Cover={len(cover_idx)}")

    # Subplots: 1=Candle+Marker, 2=Equity
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        row_heights=[0.6,0.4], vertical_spacing=0.05,
                        subplot_titles=(f"{ticker} Candles+Marker","Equity-Kurven"))

    # Candlestick
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"], name="Candle"
    ), row=1, col=1)

    # Marker
    for idx, sym, col in [
        (buy_idx,   "triangle-up",   "green"),
        (sell_idx,  "triangle-down", "red"),
        (short_idx, "x",             "blue"),
        (cover_idx, "circle",        "orange")
    ]:
        if not idx.empty:
            y = df.loc[idx, "Close"] + off * (2 if sym in ["triangle-up","triangle-down"] else 1) * (1 if col!="red" else -1)
            fig.add_trace(go.Scatter(
                x=idx, y=y, mode="markers",
                marker=dict(symbol=sym, color=col, size=9),
                name={"triangle-up":"Buy","triangle-down":"Sell","x":"Short","circle":"Cover"}[sym]
            ), row=1, col=1)

    # Supp/Res/Trend
    if not supp_filt.empty:
        fig.add_trace(go.Scatter(x=supp_filt.index, y=supp_filt.values,
                                 mode="markers", marker=dict(symbol="circle-open",color="limegreen",size=7),
                                 name="Support"), row=1, col=1)
    if not res_filt.empty:
        fig.add_trace(go.Scatter(x=res_filt.index, y=res_filt.values,
                                 mode="markers", marker=dict(symbol="x",color="firebrick",size=7),
                                 name="Resistance"), row=1, col=1)
    if not trend_filt.empty:
        fig.add_trace(go.Scatter(x=trend_filt.index, y=trend_filt.values,
                                 mode="lines", line=dict(color="black",width=2), name="Trend"),
                      row=1, col=1)

    # Equity-Kurven
    for series, name in [
        (equity_long,    "Long Equity"),
        (equity_short,   "Short Equity"),
        (equity_combined,"Combined Equity"),
        (buyhold,        "Buy & Hold")
    ]:
        fig.add_trace(go.Scatter(x=df.index, y=series, mode="lines", name=name),
                      row=2, col=1)

    # Layout & Range
    base_height = 800
    fig.update_layout(
        height=int(base_height * 1.2), margin=dict(t=50, b=30),
        xaxis=dict(rangeslider=dict(visible=False), showgrid=True),
        xaxis2=dict(matches="x", rangeslider=dict(visible=False), showgrid=True)
    )
    start, end = df.index.min(), df.index.max()
    fig.update_xaxes(range=[start,end], row=1, col=1)
    fig.update_xaxes(range=[start,end], row=2, col=1)

    # Show & Save
#    fig.show()
    fn = f"{ticker}_chart.html"
    fig.write_html(fn, auto_open=True)
    print(f"🔧 Chart saved to {fn}")

def plot_trades_with_equity(df, trades, equity_curve, ticker="TICKER"):
    fig = go.Figure()

    # 📈 Kursverlauf
    fig.add_trace(go.Scatter(
        x=df.index, y=df["Close"],
        mode="lines", name="Close Price",
        line=dict(color="blue")
    ))

    # 📍 Entry/Exit Marker
    entries_x, entries_y = [], []
    exits_x, exits_y = [], []
    for t in trades:
        entries_x.append(t["entry_date"])
        entries_y.append(t["entry_price"])
        exits_x.append(t["exit_date"])
        exits_y.append(t["exit_price"])

    fig.add_trace(go.Scatter(
        x=entries_x, y=entries_y,
        mode="markers", name="Entry",
        marker=dict(symbol="triangle-up", size=10, color="green")
    ))
    fig.add_trace(go.Scatter(
        x=exits_x, y=exits_y,
        mode="markers", name="Exit",
        marker=dict(symbol="triangle-down", size=10, color="red")
    ))

    # 💰 Equity-Kurve
    fig.add_trace(go.Scatter(
        x=equity_curve.index, y=equity_curve.values,
        mode="lines", name="Equity",
        line=dict(color="black", dash="dash")
    ))

    fig.update_layout(
        title=f"{ticker} – Trade Entries/Exits + Equity",
        xaxis_title="Date",
        yaxis_title="Price / Equity",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=600
    )
    plot_combined_chart_and_equity(
        df, ext_long, ext_short,
        sup_long, res_short,
        compute_trend(df, 20),
        compute_equity_curve(df, trades_long, cfg["initialCapitalLong"], long=True),
        compute_equity_curve(df, trades_short, cfg["initialCapitalShort"], long=False),
        [l + s for l, s in zip(
            compute_equity_curve(df, trades_long, cfg["initialCapitalLong"], long=True),
            compute_equity_curve(df, trades_short, cfg["initialCapitalShort"], long=False)
        )],
        [cfg["initialCapitalLong"] * (p / df["Close"].iloc[0]) for p in df["Close"]],
        ticker
    )

    # Debug: Marker-Zählung
    print(f"🔧 PLOT: Buy={len(buy_idx)}, Sell={len(sell_idx)}, Short={len(short_idx)}, Cover={len(cover_idx)}")

    # Zeige im Browser
#    fig.show()

#    # Speichere zusätzlich als HTML (öffnet automatisch)
#    html_file = f"{ticker}_chart.html"
#    fig.write_html(html_file, auto_open=True)
#    print(f"🔧 Chart gespeichert nach  {html_file}")

import matplotlib.pyplot as plt
import matplotlib.dates as mdates

def debug_plot_extrema(df, support, resistance, ticker=""):
    """
    Visualisiert Candlestick-Chart mit Support (grün) und Resistance (rot).
    
    Parameter:
      df         – DataFrame mit OHLC-Daten (index=date)
      support    – Series mit Support-Preisen (index=date)
      resistance – Series mit Resistance-Preisen (index=date)
      ticker     – optionaler Titel
    """
    plt.figure(figsize=(14, 6))
    
    # Candlestick-ähnlich: High & Low als Linien, Open-Close als Balken
    dates = df.index
    width = 0.6

    for i in range(len(df)):
        color = "green" if df["Close"].iloc[i] >= df["Open"].iloc[i] else "red"
        plt.plot([dates[i], dates[i]], [df["Low"].iloc[i], df["High"].iloc[i]], color="black", linewidth=0.5)
        plt.bar(dates[i], df["Close"].iloc[i] - df["Open"].iloc[i],
                bottom=df["Open"].iloc[i], color=color, width=width, alpha=0.8)

    # Support & Resistance Marker
    plt.scatter(support.index, support.values, label="Support", color="limegreen", s=80, marker="o")
    plt.scatter(resistance.index, resistance.values, label="Resistance", color="red", s=80, marker="x")
    
    plt.title(f"Support & Resistance – Debug Plot {ticker}")
    plt.xlabel("Datum")
    plt.ylabel("Preis")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()

    # Saubere X-Achse mit Datumsformat
    plt.gca().xaxis.set_major_locator(mdates.MonthLocator())
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
    plt.xticks(rotation=45)

    plt.show()
