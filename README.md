# ✈ 台北機票比價系統

從台北出發，每日自動爬取 Google Flights 最便宜機票，  
並根據台灣國定假日找出「最少請假、最多出遊」的黃金時間窗口。

---

## 功能特色

| 功能 | 說明 |
|------|------|
| 🌍 全球比價 | 台北 (TPE/TSA) → 全球 80+ 城市，可自訂目的地 |
| ⏱️ 飛行限制 | 最多轉機 2 次、單程不超過 26 小時（可調整） |
| 📅 假期規劃 | 自動分析台灣國定假日，找出最少請假的出遊窗口 |
| 🤖 每日排程 | APScheduler cron 排程，固定時間自動抓取 |
| 💾 歷史紀錄 | SQLite 儲存所有結果，支援價格歷史查詢 |
| 📊 報告輸出 | Rich 終端彩色表格 + CSV 匯出 |

---

## 安裝

```bash
# 1. 建立虛擬環境（建議）
python -m venv .venv
source .venv/bin/activate          # macOS/Linux
.venv\Scripts\activate             # Windows

# 2. 安裝套件
pip install -r requirements.txt

# 3. 安裝 Playwright 瀏覽器（備用方案）
playwright install chromium
```

---

## 使用方式

### ① 互動式搜尋（最簡單）
```bash
python main.py
# 或
python main.py search
```
程式會逐步詢問：出發機場、目的地地區、出發日期等。

---

### ② 指定參數搜尋

```bash
# 搜尋東京航班，明後天出發
python main.py search --dest NRT,KIX --date 2025-10-10,2025-10-11

# 搜尋所有目的地，使用假期最佳日期
python main.py search --dest ALL --use-holidays

# 搜尋東南亞地區，最多轉機 1 次
python main.py search --dest "東南亞 SE Asia" --use-holidays --max-stops 1

# 搜尋並匯出 CSV
python main.py search --dest NRT --date 2025-12-20 --export-csv
```

---

### ③ 查看台灣假期出遊窗口

```bash
python main.py holidays                # 未來一年
python main.py holidays --days 180     # 未來半年
python main.py holidays --min-days 5   # 至少 5 天的假期
```

**輸出範例：**
```
┌─────────────────────────────────────────────────────────────┐
│             最佳出遊時間窗口（最少請假原則）                │
├────────────────┬────────────────┬──────┬──────┬──────┬──────┤
│ 出發日         │ 回程日         │ 總天 │ 請假 │ 效率 │ 包含假日 │
├────────────────┼────────────────┼──────┼──────┼──────┼──────┤
│ 2025-10-09 Thu │ 2025-10-13 Mon │ 5    │  0   │ 5.0  │ 國慶日  │
│ 2025-01-25 Sat │ 2025-02-02 Sun │ 9    │  0   │ 9.0  │ 農曆春節 │
│ 2025-02-27 Thu │ 2025-03-02 Sun │ 4    │  1   │ 2.0  │ 和平紀念日 │
└────────────────┴────────────────┴──────┴──────┴──────┴──────┘
```

---

### ④ 啟動每日自動排程

```bash
# 每天早上 07:00 執行（台灣時間）
python main.py schedule

# 自訂時間，並立即先跑一次
python main.py schedule --time 08:30 --run-now

# 只搜尋特定目的地
python main.py schedule --time 06:00 --dest NRT,SIN,BKK,CDG,LAX
```

---

### ⑤ 查詢歷史最低票價

```bash
# 資料庫中所有目的地最低價
python main.py history

# 特定航線最近 30 天價格走勢
python main.py history --to NRT --days 30
python main.py history --to LAX --days 60
```

---

## 設定調整

所有參數集中在 `config.py`：

```python
# 每日排程時間（台灣時間）
SCHEDULE_TIME = "07:00"

# 飛行限制
MAX_STOPS          = 2    # 最多轉機次數
MAX_DURATION_HOURS = 26   # 單程最長時數

# 假期搜尋範圍
HOLIDAY_LOOKAHEAD_DAYS = 180
MIN_TRIP_DAYS = 3
MAX_TRIP_DAYS = 14

# 顯示結果數量
TOP_N_RESULTS = 20
```

---

## 目的地地區代碼

| 地區參數 | 包含城市 |
|---------|---------|
| `東北亞 NE Asia` | 東京、大阪、首爾、香港… |
| `東南亞 SE Asia` | 曼谷、新加坡、吉隆坡、巴里島… |
| `歐洲 Europe` | 倫敦、巴黎、法蘭克福、羅馬… |
| `北美 N America` | 紐約、洛杉磯、舊金山… |
| `大洋洲 Oceania` | 雪梨、墨爾本、奧克蘭… |
| `ALL` | 全部 80+ 目的地 |

---

## 架構說明

```
flight_tracker/
├── main.py            # 入口點，CLI 命令定義
├── config.py          # 全域設定（機場、目的地、限制條件）
├── taiwan_holidays.py # 台灣假日解析 & 最少請假規劃算法
├── flight_scraper.py  # Google Flights 爬取引擎
│                      #   Backend 1: fast-flights (protobuf API)
│                      #   Backend 2: Playwright (瀏覽器備用)
├── database.py        # SQLite 資料儲存與查詢
├── scheduler.py       # APScheduler 每日定時任務
├── reporter.py        # Rich 表格顯示 & CSV 匯出
├── requirements.txt
├── flights.db         # 資料庫（自動建立）
└── reports/           # CSV 報告輸出目錄
```

---

## 重要注意事項

> **Google Flights 爬取限制**  
> Google Flights 沒有公開 API。本系統使用 `fast-flights` 套件透過 protobuf 協議存取，  
> 或使用 Playwright 模擬瀏覽器行為。請遵守 Google 服務條款，避免過於頻繁的請求。  
> 建議請求間隔 ≥ 2-3 秒（已內建 `REQUEST_DELAY_SEC = 2.5`）。

---

## 常見問題

**Q: fast-flights 找不到結果？**  
A: Google Flights 的 protobuf API 格式偶爾會更新，可切換至 Playwright 後端：  
在 `flight_scraper.py` 的 `FlightScraper.__init__` 中設定 `self._backend = "playwright"`

**Q: 如何新增目的地？**  
A: 編輯 `config.py` 中的 `WORLD_DESTINATIONS` 字典，加入 IATA 機場代碼即可。

**Q: 如何設定系統服務（開機自啟）？**  
A: 在 Linux 上可建立 systemd service；在 macOS 上可使用 launchd；  
Windows 可使用工作排程器。也可使用 Docker 部署。
