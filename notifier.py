"""
notifier.py — 低價通知模組
===========================
支援三種通知管道（依 .env 設定自動啟用）：
  1. LINE Notify
  2. Telegram Bot
  3. Email (SMTP)

使用方式：
    from notifier import notify_cheap_flights
    notify_cheap_flights(cheap_records)
"""

from __future__ import annotations

import logging
import smtplib
from email.mime.text import MIMEText
from typing import List

import requests

from config import (
    LINE_NOTIFY_TOKEN,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    SMTP_HOST,
    SMTP_PORT,
    SMTP_USER,
    SMTP_PASSWORD,
    ALERT_EMAIL_TO,
    PRICE_ALERT_THRESHOLD_TWD,
    DISPLAY_CURRENCY,
)
from database import FlightRecord

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# 公用介面
# ══════════════════════════════════════════════════════════════════════════════

def notify_cheap_flights(records: List[FlightRecord]) -> None:
    """
    篩選低於閾值的票價，若有則透過所有已設定的管道發出通知。
    若未設定任何通知管道則靜默略過。
    """
    cheap = [r for r in records if _to_twd(r) <= PRICE_ALERT_THRESHOLD_TWD]
    if not cheap:
        logger.debug("沒有低於閾值的票價，跳過通知")
        return

    cheap.sort(key=lambda r: _to_twd(r))
    message = _build_message(cheap)
    logger.info(f"發現 {len(cheap)} 筆低價票，準備發送通知...")

    _send_line(message)
    _send_telegram(message)
    _send_email(message)


# ══════════════════════════════════════════════════════════════════════════════
# 訊息格式
# ══════════════════════════════════════════════════════════════════════════════

def _to_twd(record: FlightRecord) -> float:
    """將票價換算為 TWD（若已是 TWD 直接回傳）。"""
    from config import TWD_FALLBACK_RATES
    if record.currency == "TWD":
        return record.price
    rate = TWD_FALLBACK_RATES.get(record.currency.upper(), 1.0)
    return record.price * rate


def _build_message(records: List[FlightRecord]) -> str:
    lines = [
        f"✈️ Flyaway 低價通知（閾值 {PRICE_ALERT_THRESHOLD_TWD:,.0f} TWD）",
        "─" * 40,
    ]
    for r in records[:10]:  # 最多顯示 10 筆避免訊息過長
        twd = int(_to_twd(r))
        rt_tag = "來回" if getattr(r, "is_roundtrip", False) else "單程"
        dep = r.departure_time or "—"
        arr = r.arrival_time or "—"
        lines.append(
            f"• {r.departure_airport}→{r.arrival_airport}  "
            f"{r.departure_date}  {dep}-{arr}\n"
            f"  {r.airline}  {rt_tag}  "
            f"{r.price:,.0f} {r.currency}（≈ {twd:,} TWD）"
        )
    if len(records) > 10:
        lines.append(f"… 還有 {len(records) - 10} 筆，請查看報告。")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# LINE Notify
# ══════════════════════════════════════════════════════════════════════════════

def _send_line(message: str) -> None:
    if not LINE_NOTIFY_TOKEN:
        return
    try:
        resp = requests.post(
            "https://notify-api.line.me/api/notify",
            headers={"Authorization": f"Bearer {LINE_NOTIFY_TOKEN}"},
            data={"message": "\n" + message},
            timeout=10,
        )
        if resp.status_code == 200:
            logger.info("LINE Notify 發送成功 ✓")
        else:
            logger.warning(f"LINE Notify 發送失敗: {resp.status_code} {resp.text}")
    except Exception as e:
        logger.error(f"LINE Notify 例外: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# Telegram
# ══════════════════════════════════════════════════════════════════════════════

def _send_telegram(message: str) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        resp = requests.post(
            url,
            json={"chat_id": TELEGRAM_CHAT_ID, "text": message},
            timeout=10,
        )
        if resp.ok:
            logger.info("Telegram 發送成功 ✓")
        else:
            logger.warning(f"Telegram 發送失敗: {resp.status_code} {resp.text}")
    except Exception as e:
        logger.error(f"Telegram 例外: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# Email
# ══════════════════════════════════════════════════════════════════════════════

def _send_email(message: str) -> None:
    if not all([SMTP_HOST, SMTP_USER, SMTP_PASSWORD, ALERT_EMAIL_TO]):
        return
    try:
        msg = MIMEText(message, "plain", "utf-8")
        msg["Subject"] = f"✈️ Flyaway 低價通知"
        msg["From"] = SMTP_USER
        msg["To"] = ALERT_EMAIL_TO

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, [ALERT_EMAIL_TO], msg.as_string())

        logger.info("Email 發送成功 ✓")
    except Exception as e:
        logger.error(f"Email 發送失敗: {e}")
