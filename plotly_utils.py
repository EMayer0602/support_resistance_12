# plotly_utils.py
import plotly.graph_objects as go
from plotly.subplots import make_subplots

def plotly_combined_chart_and_equity(
    df, standard_signals, support, resistance, trend,
    equity_curve, buyhold_curve, ticker
):
    """
    Erstellt ein interaktives Plotly-Chart mit:
      - Candlestick inkl. Support/Resistance + Buy/Sell-Marker
      - Equity-Kurve vs. Buy&Hold (Unterplot)
    """

    # 1) Figure mit 2 Zeilen
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        row_heights=[0.7, 0.3]
    )

    # 2) Candlestick-Chart
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["Open"], high=df["High"],
            low=df["Low"], close=df["Close"],
            name="Candlestick"
        ),
        row=1, col=1
    )

    # 3) Trendline
    fig.add_trace(
        go.Scatter(
            x=trend.index, y=trend.values,
            mode="lines", line=dict(color="blue", width=2),
            name="Trend (MA)"
        ),
        row=1, col=1
    )

    # 4) Support/Resistance
    fig.add_trace(
        go.Scatter(
            x=support.index, y=support.values,
            mode="markers", marker=dict(symbol="circle", color="green", size=8),
            name="Support"
        ),
        row=1, col=1
    )
    fig.add_trace(
        go.Scatter(
            x=resistance.index, y=resistance.values,
            mode="markers", marker=dict(symbol="x", color="red", size=8),
            name="Resistance"
        ),
        row=1, col=1
    )

    # 5) Buy/Sell Marker aus standard_signals
    buys = standard_signals[standard_signals["Long"]=="buy"]
    sells= standard_signals[standard_signals["Long"]=="sell"]
    if not buys.empty:
        fig.add_trace(
            go.Scatter(
                x=buys["Long Date"], 
                y=df.loc[buys["Long Date"],"Close"],
                mode="markers", marker=dict(symbol="triangle-up", color="blue", size=12),
                name="Buy"
            ), row=1, col=1
        )
    if not sells.empty:
        fig.add_trace(
            go.Scatter(
                x=sells["Long Date"], 
                y=df.loc[sells["Long Date"],"Close"],
                mode="markers", marker=dict(symbol="triangle-down", color="orange", size=12),
                name="Sell"
            ), row=1, col=1
        )

    # 6) Equity vs. Buy&Hold (Unterplot)
    fig.add_trace(
        go.Scatter(
            x=df.index, y=equity_curve,
            mode="lines", line=dict(color="blue"), name="Strategie (Equity)"
        ), row=2, col=1
    )
    fig.add_trace(
        go.Scatter(
            x=df.index, y=buyhold_curve,
            mode="lines", line=dict(color="gray", dash="dash"),
            name="Buy & Hold"
        ), row=2, col=1
    )

    # 7) Layout anpassen
    fig.update_layout(
        title=f"{ticker} – Candlestick mit Signalen & Equity",
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", y=-0.1, font=dict(color="white")),
        margin=dict(l=50, r=50, t=50, b=50),
        template="plotly_white",
        paper_bgcolor="midnightblue",
        plot_bgcolor="midnightblue",
        font=dict(color="white")
    )

    fig.update_xaxes(
        showspikes=True, spikecolor="grey", spikesnap="cursor", spikemode="across"
    )
    fig.update_yaxes(title_text="Price", row=1, col=1)
    fig.update_yaxes(title_text="Kapital (€)", row=2, col=1)

    fig.show()
