# signal_alert_today.py

import yfinance as yf
import pandas as pd

from config import backtesting_begin, backtesting_end
# Optional crypto modules (may not exist in this workspace)
try:
    from crypto_tickers import crypto_tickers  # type: ignore
    from crypto_backtesting_module import load_crypto_data_yf, berechne_best_p_tw_long  # type: ignore
except Exception:  # fallback to equities config
    crypto_tickers = {}
    def load_crypto_data_yf(symbol, days=365):
        return yf.download(symbol, period=f"{days}d", interval="1d", auto_adjust=True, progress=False)
    def berechne_best_p_tw_long(df, cfg, backtesting_begin, backtesting_end):
        # Simple placeholder: pick small defaults
        return 5, 5
from signal_utils import calculate_support_resistance, assign_long_signals
from tickers_config import tickers

def get_today_signal(symbol: str, p: int, tw: int, cfg: dict):
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
    price_col = "Open" if cfg.get("trade_on","Close").lower()=="open" else "Close"
    supp, res = calculate_support_resistance(df1m, p, tw, price_col=price_col)
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
    # If no crypto tickers, optionally loop over equity tickers as demo
    source_dict = crypto_tickers if crypto_tickers else {k: {"symbol": v["symbol"], "trade_on": v.get("trade_on", "Close")} for k, v in tickers.items()}
    for sym, cfg in source_dict.items():
        # 1) Parameter p,tw aus Jahres-Historie bestimmen
        df = load_crypto_data_yf(cfg["symbol"], days=365)
        if df is None:
            continue
        p, tw = berechne_best_p_tw_long(df, cfg, backtesting_begin, backtesting_end)

        # 2) Heutiges Signal basierend auf 1-Min-Daten
        res = get_today_signal(cfg["symbol"], p, tw, cfg)
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
