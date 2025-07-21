# trade_execution.py
# ─── 1. Imports oben im File ────────────────────────────────────────────────────
import sys
import math
from math import floor
import yfinance as yf
from datetime import datetime
from ib_insync import IB, Stock, MarketOrder
from tickers_config import tickers

# ─── 1. IB- & YF-Preise ────────────────────────────────────────────────────────
from ib_insync import Stock

def get_price(ib, symbol: str, fallback: bool = True) -> float | None:
    """
    Holt den aktuellen Preis über IB. Optionaler Fallback auf Yahoo.
    - symbol: z. B. 'AAPL'
    - ib: aktives IB-Objekt
    - fallback: True = Yahoo-Fallback aktiv
    """
    try:
        contract = Stock(symbol, "SMART", "USD")
        ticker   = ib.reqMktData(contract, "", False, False)
        ib.sleep(1.5)  # IB braucht kurz Zeit für Preisdaten

        price = ticker.last if ticker.last else ticker.close
        if price is not None and price > 0:
            return round(price, 2)
    except Exception as e:
        print(f"⚠️ IB-Preisfehler für {symbol}: {e}")

    if fallback:
        try:
            import yfinance as yf
            df = yf.Ticker(symbol).history(period="1d")
            val = df["Close"].iloc[-1]
            return round(val, 2)
        except Exception as e:
            print(f"⚠️ Yahoo-Fallback für {symbol} fehlgeschlagen: {e}")
    
    return None
                                                                                       
# ─── 2. Live-Preis-Getter (unverändert) ────────────────────────────────────────
def get_realtime_price(ib: IB, contract: Stock) -> float:
    ib.qualifyContracts(contract)
    ticker = ib.reqMktData(contract, snapshot=True)
    ib.sleep(2)
    price = ticker.last or ticker.close
    return round(price, 2) if price else None

def get_yf_price(symbol: str, field: str = "Close") -> float:
    try:
        df = yf.Ticker(symbol).history(period="1d")
        price = df[field].iloc[-1]
        return round(price, 2)
    except Exception as e:
        print(f"{symbol}: Yahoo-Preis {field} fehlgeschlagen – {e}")
        return None

# ─── 3. Neuer Backtest-Preis-Getter ────────────────────────────────────────────
def get_backtest_price(symbol: str,
                       date_str: str,
                       field: str = "Close") -> float | None:
    """
    Liefert historischen Preis aus lokalem CSV oder von Yahoo.
    """
    field = field.capitalize()

    # 🔁 CACHE-Versuch über CSV-Datei
    fn = f"{symbol}_data.csv"
    try:
        if os.path.exists(fn):
            df_local = pd.read_csv(fn, parse_dates=["Date"], index_col="Date")
            df_local.sort_index(inplace=True)
            row = df_local.loc[pd.to_datetime(date_str)]
            price = row[field] if field in row else None
            if pd.notna(price):
                return float(price)
    except Exception:
        pass  # Ignorieren, falls Cache nicht greift

    # 🌐 Fallback zu Yahoo Finance
    try:
        start_dt = pd.to_datetime(date_str)
        end_dt = (start_dt + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        df = yf.Ticker(symbol).history(start=date_str, end=end_dt, auto_adjust=False)

        if df.empty:
            print(f"{symbol}: keine Yahoo-Daten für {date_str}")
            return None

        if field not in df.columns or pd.isna(df[field].iloc[0]):
            print(f"{symbol}: kein gültiger {field}-Preis am {date_str}")
            return None

        return round(df[field].iloc[0], 2)
    except Exception as e:
        print(f"{symbol}: Yahoo-Fehler am {date_str} → {e}")
        return None

import pandas as pd
import yfinance as yf

def get_backtest_price(symbol: str,
                       date_str: str,
                       field: str = "Close") -> float | None:
    """
    Liefert historischen Preis (Open/Close) von Yahoo Finance für genau einen Tag.
    Gibt None zurück, wenn keine Daten vorhanden sind.
    - date_str: Format 'YYYY-MM-DD'
    - field: 'Open' oder 'Close'
    """

    try:
        # → end = exklusiv, also +1 Tag für den Tagesbar
        start_dt = pd.to_datetime(date_str)
        end_dt   = (start_dt + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

        df = yf.Ticker(symbol).history(start=date_str, end=end_dt, auto_adjust=False)

        if df.empty:
            print(f"{symbol}: keine Daten für {date_str}")
            return None

        # Fallback von Open auf Close, falls Open fehlt
        field = field.capitalize()
        if field == "Open" and "Open" not in df.columns:
            print(f"{symbol}: kein Open am {date_str}, weiche auf Close aus")
            field = "Close"

        if field not in df.columns or pd.isna(df[field].iloc[0]):
            print(f"{symbol}: kein gültiger {field}-Preis am {date_str}")
            return None

        return round(df[field].iloc[0], 2)

    except Exception as e:
        print(f"{symbol}: Yahoo-Fehler am {date_str} → {e}")
        return None


# ─── 2. Grundlegende Helfer ─────────────────────────────────────────────────────

def calculate_shares(capital: float, price: float, round_factor: int) -> int:
    """
    Berechnet, wie viele Aktien mit 'capital' zum aktuellen 'price' gekauft werden
    können, gerundet auf Vielfache von 'round_factor'.
    """
    if price <= 0 or capital <= 0:
        return 0
    raw_amount = capital / price
    rounded = round(raw_amount / round_factor) * round_factor
    return int(rounded)

# ─── 4. Portfolio/Helfer-Funktionen (unverändert) ─────────────────────────────
def get_portfolio(ib: IB) -> dict:
    return {pos.contract.symbol: pos.position for pos in ib.positions()}

def target_qty(symbol: str, side: str, price: float, cfg: dict) -> int:
    """
    Gibt 0 zurück, wenn 'price' fehlt oder nicht zahlbar ist.
    """
    rnd = cfg['order_round_factor']

    # Preis prüfen
    if price is None or not isinstance(price, (int, float)) or math.isnan(price) or price <= 0:
        return 0

    if side == 'BUY':
        raw = cfg['initialCapitalLong'] / price
    elif side == 'SHORT':
        raw = cfg['initialCapitalShort'] / price
    else:
        return 0

    return int(round(raw / rnd) * rnd)

def plan_trade_qty(symbol, side, portfolio, price):
    cfg = tickers[symbol]
    factor = cfg.get("order_round_factor", 1)

    if side in ("SELL", "COVER"):
        return portfolio.get(symbol, 0)
    
    capital = cfg.get("initialCapitalLong", 0) if side == "BUY" else cfg.get("initialCapitalShort", 0)
    qty_raw = capital / price
    qty_rounded = int(qty_raw // factor * factor)

    return qty_rounded


# ─── 5. Trade-Funktionen (unverändert, nutzen plan_trade_qty) ─────────────────
def preview_trades(ib: IB) -> list:
    portfolio = get_portfolio(ib)
    plan      = []

    for symbol, cfg in tickers.items():
        price = get_price(ib, symbol)
        if not price:
            continue
        for side in ("BUY","SHORT","SELL","COVER"):
            if not cfg.get(side.lower(), False):
                continue
            qty = plan_trade_qty(symbol, side, portfolio, price)
            if qty > 0:
                plan.append({"symbol":symbol, "side":side, "qty":qty, "price":price})
    return plan

def execute_trades(ib: IB):
    portfolio = get_portfolio(ib)
    for symbol, cfg in tickers.items():
        price = get_price(ib, symbol)
        if not price:
            continue
        for side in ("BUY","SHORT","SELL","COVER"):
            if not cfg.get(side.lower(), False):
                continue
            qty = plan_trade_qty(symbol, side, portfolio, price)
            if qty <= 0:
                continue
            action   = "BUY" if side in ("BUY","COVER") else "SELL"
            order    = MarketOrder(action, qty)
            contract = ib.qualifyContracts(Stock(symbol,'SMART','USD'))[0]
            ib.placeOrder(contract, order)
            print(f"{action} {qty}×{symbol} @ {price:.2f} (Ziel={target_qty(symbol,side,price,cfg)})")
