# signal_alert_today.py

import yfinance as yf
import pandas as pd

from config import backtesting_begin, backtesting_end
from crypto_tickers import crypto_tickers
from crypto_backtesting_module import load_crypto_data_yf, berechne_best_p_tw_long
from signal_utils import calculate_support_resistance, assign_long_signals
from tickers_config import tickers

def get_today_signal(symbol: str, p: int, tw: int):
    """
    Lädt die 1-Min-Daten von heute und bestimmt das letzte Long-Signal.
    """
    # heute ab Mitternacht
    df1m = yf.download(
        symbol,
        period="1d",
        interval="1m",
        progress=False,
        auto_adjust=True
    )
    if df1m is None or df1m.empty:
        return None

    # sicherstellen, dass Close numerisch ist
    df1m["Close"] = pd.to_numeric(df1m["Close"], errors="coerce")
    df1m.dropna(subset=["Close"], inplace=True)
    if df1m.empty:
        return None

    # Support/Resistance auf Minute anwenden
    supp, res = calculate_support_resistance(df1m, p, tw)
    sig = assign_long_signals(supp, res, df1m, tw, interval="1m")
    sig = sig.dropna(subset=["Long"])  # nur die echten Signale

    # schau dir das letzte Signal an
    if sig.empty:
        return None
    last = sig.iloc[-1]
    return {
        "symbol": symbol,
        "action": last["Long"],          # 'buy' oder 'sell'
        "time":    last["Long Date"]     # Timestamp (Minute)
    }

if __name__ == "__main__":
    alerts = []
    for sym, cfg in crypto_tickers.items():
        # 1) Parameter p,tw aus Jahres-Historie bestimmen
        df = load_crypto_data_yf(cfg["symbol"], days=365)
        if df is None:
            continue
        p, tw = berechne_best_p_tw_long(df, cfg, backtesting_begin, backtesting_end)

        # 2) Heutiges Signal basierend auf 1-Min-Daten
        res = get_today_signal(cfg["symbol"], p, tw)
        if res:
            alerts.append(res)

    # 3) Ausgabe
    if not alerts:
        print("Heute keine neuen Signale.")
    else:
        for a in alerts:
            t = a["time"].strftime("%H:%M")
            act = "KAUFEN" if a["action"]=="buy" else "VERKAUFEN"
            print(f"Heute um {t}: {act} bei {a['symbol']}")
