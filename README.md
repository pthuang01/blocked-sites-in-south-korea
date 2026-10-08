# blocked-sites-in-south-korea

南韓網路審查阻擋之網站清單與檢測工具。

## 檔案說明
- `list.txt`: 原始阻擋網站清單（1,119 筆）
- `kr.list`: 擴充阻擋網站清單（2,056 筆）
- `merged.txt`: 合併 `list.txt` 與 `kr.list` 並去重排序之完整清單（共 2,805 筆）
- `check.py`: 非同步檢測網站是否遭到封鎖的 Python 腳本
- `dedup.py`: 清單重複項目檢查與去重工具
- `run_dedup.bat`: Windows 一鍵執行去重檢查腳本