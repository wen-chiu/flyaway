#!/usr/bin/env python3
"""
setup_check.py — 環境檢查 & 快速安裝引導
執行方式：python setup_check.py
"""
import sys
import subprocess
import importlib

REQUIRED = [
    ("fast_flights",  "fast-flights",  "✅ fast-flights  (Google Flights protobuf 後端)"),
    ("playwright",    "playwright",    "✅ playwright    (備用瀏覽器後端)"),
    ("apscheduler",   "apscheduler",   "✅ APScheduler   (每日定時排程)"),
    ("rich",          "rich",          "✅ rich          (漂亮終端輸出)"),
    ("holidays",      "holidays",      "✅ holidays      (台灣假日計算)"),
    ("dateutil",      "python-dateutil","✅ dateutil      (日期處理)"),
]

print("\n" + "="*55)
print("  台北機票比價系統 — 環境檢查")
print("="*55)

missing_pkgs = []
for import_name, pip_name, desc in REQUIRED:
    try:
        importlib.import_module(import_name)
        print(f"  {desc}")
    except ImportError:
        print(f"  ❌ {pip_name:<18} (未安裝)")
        missing_pkgs.append(pip_name)

if missing_pkgs:
    print(f"\n  ⚠️  缺少 {len(missing_pkgs)} 個套件")
    ans = input("  是否立即安裝？(y/n): ").strip().lower()
    if ans == "y":
        for pkg in missing_pkgs:
            print(f"  安裝 {pkg}…")
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])
        
        # 安裝 playwright 瀏覽器
        if "playwright" in missing_pkgs:
            print("  安裝 Playwright Chromium…")
            subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
        
        print("\n  ✅ 所有套件安裝完成！")
    else:
        print(f"\n  手動安裝指令：\n  pip install {' '.join(missing_pkgs)}")
else:
    print("\n  ✅ 所有套件已安裝，環境準備好了！")

print("\n  快速開始：")
print("    python main.py holidays        # 查看假期出遊窗口")
print("    python main.py search          # 互動式機票搜尋")
print("    python main.py schedule        # 啟動每日自動排程")
print("="*55 + "\n")
