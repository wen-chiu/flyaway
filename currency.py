"""
currency.py — TWD 匯率轉換
============================
嘗試從免費 API 取得即時匯率，若失敗則使用 config.py 的備用固定匯率。
"""
from __future__ import annotations

import json
import logging
import urllib.request
from functools import lru_cache
from typing import Optional

from config import TWD_FALLBACK_RATES

logger = logging.getLogger(__name__)

_LIVE_RATES: Optional[dict[str, float]] = None   # 快取

def _fetch_live_rates() -> Optional[dict[str, float]]:
    """
    嘗試從 open.er-api.com 取得 TWD 為基準的匯率。
    免費方案，無需 API key。
    """
    try:
        url = "https://open.er-api.com/v6/latest/TWD"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        if data.get("result") == "success":
            # API 回傳 1 TWD = X 外幣，我們需要反轉：1 外幣 = N TWD
            rates_from_twd: dict[str, float] = data["rates"]  # e.g. "USD": 0.0308
            twd_rates = {}
            for cur, rate in rates_from_twd.items():
                if rate and rate > 0:
                    twd_rates[cur] = round(1.0 / rate, 6)
            twd_rates["TWD"] = 1.0
            logger.info(f"✅ 取得即時匯率 {len(twd_rates)} 種幣別")
            return twd_rates
    except Exception as e:
        logger.debug(f"即時匯率取得失敗（將使用備用匯率）: {e}")
    return None


def get_twd_rate(currency: str) -> float:
    """
    取得 1 單位外幣 = N 台幣的匯率。
    優先使用即時匯率，若失敗則用備用固定匯率。
    """
    global _LIVE_RATES
    if _LIVE_RATES is None:
        _LIVE_RATES = _fetch_live_rates() or {}

    cur = currency.upper().strip()
    rate = _LIVE_RATES.get(cur) or TWD_FALLBACK_RATES.get(cur)
    if rate:
        return rate

    logger.warning(f"找不到 {cur} 的匯率，預設 1:1")
    return 1.0


def to_twd(amount: float, currency: str) -> float:
    """將金額從 currency 換算成 TWD。"""
    if currency.upper() == "TWD":
        return amount
    return round(amount * get_twd_rate(currency), 0)


def format_twd(amount: float) -> str:
    return f"NT${int(amount):,}"
