"""Minimal Bitpanda-like exchange client abstraction.
Currently a placeholder using ccxt if available. Fallback to dummy data.
"""
from __future__ import annotations
import time
import json
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

try:
    import ccxt  # type: ignore
except ImportError:  # pragma: no cover
    ccxt = None

from .crypto_config import PAIRS, TIMEFRAME, FETCH_LIMIT

@dataclass
class TickerPrice:
    symbol: str
    bid: Optional[float]
    ask: Optional[float]
    last: Optional[float]
    timestamp: float

class ExchangeClient:
    def __init__(self, api_key: str | None = None, secret: str | None = None, exchange: str = "bitpanda"):
        self.exchange_name = exchange
        self.api_key = api_key
        self.secret = secret
        if ccxt:
            try:
                cls = getattr(ccxt, exchange)
                self.client = cls({"apiKey": api_key, "secret": secret, "enableRateLimit": True})
            except Exception:
                self.client = None
        else:
            self.client = None

    def fetch_ohlcv(self, pair: str, limit: int = FETCH_LIMIT, timeframe: str = TIMEFRAME) -> List[Dict[str, Any]]:
        if self.client:
            raw = self.client.fetch_ohlcv(pair, timeframe=timeframe, limit=limit)
            return [
                {"timestamp": r[0], "open": r[1], "high": r[2], "low": r[3], "close": r[4], "volume": r[5]} for r in raw
            ]
        # fallback dummy
        now = int(time.time()*1000)
        return [
            {"timestamp": now - i*60_000, "open": 100+i, "high": 101+i, "low": 99+i, "close": 100+i, "volume": 1.0}
            for i in range(limit)
        ][::-1]

    def fetch_ticker(self, pair: str) -> TickerPrice:
        if self.client:
            t = self.client.fetch_ticker(pair)
            return TickerPrice(symbol=pair, bid=t.get("bid"), ask=t.get("ask"), last=t.get("last"), timestamp=t.get("timestamp", time.time()*1000))
        return TickerPrice(symbol=pair, bid=100.0, ask=100.5, last=100.2, timestamp=time.time()*1000)

    def create_order(self, pair: str, side: str, order_type: str, amount: float, price: Optional[float] = None) -> Dict[str, Any]:
        if self.client:
            return self.client.create_order(pair, order_type, side.lower(), amount, price)
        return {"id": f"demo-{int(time.time())}", "symbol": pair, "side": side, "type": order_type, "amount": amount, "price": price}

    def fetch_balance(self) -> Dict[str, Any]:
        if self.client:
            return self.client.fetch_balance()
        # demo balance
        return {"total": {"EUR": 5000, "BTC": 0.5, "ETH": 5}}

    def close(self):
        pass
