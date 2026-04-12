"""
scheduler.py — 每日定時排程管理
==================================
使用 APScheduler 實現 cron-style 定時任務，
在指定時間自動執行來回票抓取並輸出報告。

資料庫策略：
  每次排程執行前先清除所有舊資料（clear_all_flights），
  確保資料庫只保留最新一批搜尋結果。
  票價每天都在變動，累積舊資料沒有意義。
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
    ASIA_DEFAULT_TRIP_DAYS,
)

logger = logging.getLogger(__name__)

try:
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger
    _HAS_APScheduler = True
except ImportError:
    _HAS_APScheduler = False
    logger.warning("APScheduler 未安裝，排程功能不可用。請執行: pip install apscheduler")


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
        on_complete: Optional[Callable] = None,
    ):
        if not _HAS_APScheduler:
            raise RuntimeError(
                "APScheduler 未安裝。請執行: pip install apscheduler"
            )

        hour, minute      = map(int, run_time.split(":"))
        self.run_time     = run_time
        self.from_airport = from_airport
        self.destinations = destinations or ALL_DESTINATIONS
        self.on_complete  = on_complete

        self._scheduler = BlockingScheduler(timezone="Asia/Taipei")
        self._scheduler.add_job(
            func=self._run_daily_job,
            trigger=CronTrigger(hour=hour, minute=minute, timezone="Asia/Taipei"),
            id="daily_flight_fetch",
            name=f"每日機票抓取 @ {run_time}",
            replace_existing=True,
            misfire_grace_time=600,  # 10 分鐘容錯
        )

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
        """
        每日執行的任務主體。

        流程：
        1. 清除資料庫所有舊資料（完整刷新，確保只保留最新票價）
        2. 從台灣假日窗口計算出發/回程日期對
        3. 執行來回票搜尋
        4. 存入資料庫
        5. 輸出報告（按出發日期分組，傳統/廉航分表）
        """
        from datetime import datetime as _dt

        logger.info(f"=== 開始每日機票抓取 {_dt.now().isoformat()} ===")

        from flight_scraper import FlightScraper
        from database import Database
        from reporter import print_results, export_csv
        from taiwan_holidays import get_holiday_windows

        db      = Database()
        scraper = FlightScraper()

        # Step 1: 清除所有舊資料，確保 DB 只保留本次最新搜尋結果
        deleted = db.clear_all_flights()
        if deleted:
            logger.info(f"已清除 {deleted} 筆舊資料")

        # Step 2: 從假日窗口決定搜尋日期
        windows = get_holiday_windows(
            lookahead_days=HOLIDAY_LOOKAHEAD_DAYS,
            min_trip_days=MIN_TRIP_DAYS,
            max_trip_days=MAX_TRIP_DAYS,
        )
        top_windows = windows[:5]  # 最多 5 個最高效益假期窗口

        if top_windows:
            out_dates = [w.start_date for w in top_windows]
            ret_dates = [w.end_date   for w in top_windows]
        else:
            # 備用：搜尋未來 14、30、60、90 天
            today     = date.today()
            out_dates = [today + timedelta(days=d) for d in [14, 30, 60, 90]]
            ret_dates = [d + timedelta(days=ASIA_DEFAULT_TRIP_DAYS - 1) for d in out_dates]

        logger.info(f"搜尋出發日期：{[str(d) for d in out_dates]}")
        logger.info(f"目的地數量：{len(self.destinations)}")

        # Step 3: 來回票搜尋
        all_records = scraper.search_roundtrip_many(
            from_airport=self.from_airport,
            destinations=self.destinations,
            outbound_dates=out_dates,
            return_dates=ret_dates,
        )

        # Step 4: 存入資料庫
        inserted = db.bulk_insert_flights(all_records)
        logger.info(f"插入 {inserted} 筆最新記錄")

        # Step 5: 輸出報告
        if all_records:
            print_results(
                all_records,
                title=f"📅 每日機票報告 — {date.today()}",
                top_n=TOP_N_RESULTS,
                split_lcc=True,
                group_by_date=True,  # 按出發日期分組，方便閱讀
            )
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
            print(f"  [{job.id}] {job.name} — 下次執行: {job.next_run_time}")
