"""
scheduler.py — 每日定時排程管理
==================================
使用 APScheduler 實現 cron-style 定時任務，
在指定時間自動執行機票抓取。
"""

from __future__ import annotations

import logging
import signal
import sys
from datetime import date, timedelta
from typing import Callable, List, Optional

from config import (
    ALL_DESTINATIONS, DEFAULT_DEPARTURE,
    HOLIDAY_LOOKAHEAD_DAYS, SCHEDULE_TIME,
    MIN_TRIP_DAYS, MAX_TRIP_DAYS, TOP_N_RESULTS,
)

logger = logging.getLogger(__name__)

try:
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger
    _HAS_APScheduler = True
except ImportError:
    _HAS_APScheduler = False
    logger.warning("APScheduler 未安裝，排程功能不可用。")


# ══════════════════════════════════════════════════════════════════════════════
#  排程器主類別
# ══════════════════════════════════════════════════════════════════════════════

class FlightScheduler:
    """
    管理每日機票抓取排程。
    
    用法：
        sched = FlightScheduler(run_time="07:00")
        sched.start()   # 阻塞式，直到按 Ctrl+C 停止
    """

    def __init__(
        self,
        run_time: str = SCHEDULE_TIME,
        from_airport: str = DEFAULT_DEPARTURE,
        destinations: Optional[List[str]] = None,
        departure_dates: Optional[List[date]] = None,
        on_complete: Optional[Callable] = None,
    ):
        if not _HAS_APScheduler:
            raise RuntimeError(
                "APScheduler 未安裝。請執行: pip install apscheduler"
            )

        hour, minute = map(int, run_time.split(":"))
        self.run_time       = run_time
        self.from_airport   = from_airport
        self.destinations   = destinations or ALL_DESTINATIONS
        self.departure_dates = departure_dates  # None = 自動用假期窗口
        self.on_complete    = on_complete

        self._scheduler = BlockingScheduler(timezone="Asia/Taipei")
        self._scheduler.add_job(
            func=self._run_daily_job,
            trigger=CronTrigger(hour=hour, minute=minute, timezone="Asia/Taipei"),
            id="daily_flight_fetch",
            name=f"每日機票抓取 @ {run_time}",
            replace_existing=True,
            misfire_grace_time=600,   # 10分鐘容錯
        )

        # 優雅關機
        signal.signal(signal.SIGINT,  self._graceful_shutdown)
        signal.signal(signal.SIGTERM, self._graceful_shutdown)

    def start(self, run_immediately: bool = False) -> None:
        """啟動排程器。run_immediately=True 時會先立刻執行一次。"""
        try:
            from rich.console import Console
            Console().print(
                f"\n[bold green]🚀 排程器已啟動[/bold green] — "
                f"每天 [yellow]{self.run_time}[/yellow] (台灣時間) 執行\n"
                f"按 [red]Ctrl+C[/red] 停止\n"
            )
        except ImportError:
            print(f"\n排程器已啟動 — 每天 {self.run_time} (台灣時間) 執行")

        if run_immediately:
            logger.info("立即執行一次…")
            self._run_daily_job()

        self._scheduler.start()

    def _run_daily_job(self) -> None:
        """每日執行的任務主體。"""
        from datetime import datetime

        logger.info(f"=== 開始每日機票抓取 {datetime.now().isoformat()} ===")

        # 延遲 import 避免循環依賴
        from flight_scraper import FlightScraper
        from database import Database
        from reporter import print_results, export_csv
        from taiwan_holidays import get_holiday_windows

        db      = Database()
        scraper = FlightScraper()

        # 決定要搜尋的日期
        if self.departure_dates:
            dates_to_search = self.departure_dates
        else:
            # 自動找假期窗口的出發日
            windows = get_holiday_windows(
                lookahead_days=HOLIDAY_LOOKAHEAD_DAYS,
                min_trip_days=MIN_TRIP_DAYS,
                max_trip_days=MAX_TRIP_DAYS,
            )
            # 取前 5 個效率最高的窗口的出發日
            dates_to_search = [w.start_date for w in windows[:5]]
            if not dates_to_search:
                # 備用：搜尋未來 14-90 天
                today = date.today()
                dates_to_search = [today + timedelta(days=d) for d in [14, 30, 60, 90]]

        logger.info(f"搜尋日期：{[str(d) for d in dates_to_search]}")
        logger.info(f"目的地數量：{len(self.destinations)}")

        # 執行搜尋
        all_records = scraper.search_many(
            from_airport=self.from_airport,
            destinations=self.destinations,
            departure_dates=dates_to_search,
        )

        # 存入資料庫
        inserted = db.bulk_insert_flights(all_records)
        logger.info(f"插入 {inserted} 筆記錄")

        # 輸出報告
        if all_records:
            print_results(all_records, title=f"📅 每日機票報告 — {date.today()}", top_n=TOP_N_RESULTS)
            export_csv(all_records)

        if self.on_complete:
            self.on_complete(all_records)

        logger.info("=== 每日抓取完成 ===")

    def _graceful_shutdown(self, signum, frame) -> None:
        logger.info("收到停止信號，正在關閉排程器…")
        self._scheduler.shutdown(wait=False)
        sys.exit(0)

    def list_jobs(self) -> None:
        """列出所有已排程的任務。"""
        for job in self._scheduler.get_jobs():
            next_run = job.next_run_time
            print(f"  [{job.id}] {job.name} — 下次執行: {next_run}")
