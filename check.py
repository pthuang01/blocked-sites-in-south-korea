"""
南韓網站封鎖檢測工具 (check.py)

此程式使用非同步 I/O (asyncio 與 aiohttp) 批次檢測目標網址是否遭到南韓網路審查阻擋。
判定原理：
  當使用者在南韓網路環境下訪問被封鎖的網站時，南韓官方（放送通信審議委員會 KCSC）
  通常會將連線攔截並重導向或回傳包含特定特徵網址（warning.or.kr/i1.html）的警告頁面。
  若回應內容中包含此字串，即判定該網站已被南韓官方封鎖。

注意：
  本程式需在南韓本地網路環境或透過南韓 Proxy / VPN 執行，才能發揮實際檢測效果。
"""

import asyncio
import aiohttp
import time
import logging
from aiohttp import TCPConnector

# ==================== 全域常數設定 ====================
# 最大並發請求數（透過 Semaphore 控制同時發出的請求數量）
CONCURRENT_REQUESTS = 50

# TCP 連線池大小（限制 aiohttp 連線池所能維持的最大連線數）
CONNECTION_LIMIT = 100

# 每批次處理的 URL 數量（分批載入並發送，避免一次載入過多網址佔用過大記憶體）
BATCH_SIZE = 1000

# ==================== 日誌記錄配置 ====================
# 設定日誌格式並同時輸出至檔案 (log.log) 與終端機 (StreamHandler)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("log.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

async def fetch_url(session: aiohttp.ClientSession, url: str, output_file: str):
    """
    發送 HTTP GET 請求檢測單一網址是否被南韓官方封鎖。

    參數:
        session (aiohttp.ClientSession): 共享的 aiohttp 用戶端連線 Session。
        url (str): 待檢測的完整目標網址。
        output_file (str): 檢測到被封鎖時，記錄該網址的目的檔案路徑。
    """
    start_time = time.time()
    try:
        # 設定單次請求超時為 5 秒；allow_redirects=False 代表不自動跟隨 HTTP 重導向
        async with session.get(url, timeout=5, allow_redirects=False) as response:
            end_time = time.time()
            duration = end_time - start_time

            # 若伺服器成功回應 HTTP 200，讀取 HTML 內容以比對審查特徵字串
            if response.status == 200:
                text = await response.text()
                # 檢測回應內文是否包含南韓官方阻擋頁面標記
                if "warning.or.kr/i1.html" in text:
                    logging.info(f"在 {url} 中發現阻擋關鍵字（耗時 {duration:.2f} 秒）")
                    # 以附加模式寫入輸出結果檔案
                    with open(output_file, 'a', encoding='utf-8') as f:
                        f.write(f"{url} (took {duration:.2f} seconds)\n")

            # 若遇到 30x 重導向狀態碼，記錄目標轉址位置
            elif response.status in (301, 302, 303, 307, 308):
                location = response.headers.get('Location')
                logging.info(f"偵測到 {url} 轉址至 {location}（耗時 {duration:.2f} 秒）")

            # 其餘非 200 狀態碼（例如 403, 404, 500 等）
            else:
                logging.info(f"{url} 回傳非 200 狀態碼 {response.status}（耗時 {duration:.2f} 秒）")

    except Exception as e:
        # 捕捉連線超時、DNS 解析失敗或連線拒絕等例外狀況
        logging.error(f"存取 {url} 時發生錯誤: {e}")

async def bound_fetch(sem: asyncio.Semaphore, session: aiohttp.ClientSession, url: str, output_file: str):
    """
    利用信號量 (Semaphore) 包裝請求函式，確保同時連線數不超過 CONCURRENT_REQUESTS 上限。

    參數:
        sem (asyncio.Semaphore): 並發控制信號量。
        session (aiohttp.ClientSession): 用戶端連線 Session。
        url (str): 目標網址。
        output_file (str): 輸出檔案路徑。
    """
    async with sem:
        await fetch_url(session, url, output_file)

def clean_url(url: str) -> str:
    """
    標準化並整理網址字串。
    若網址開頭未包含 http:// 或 https://，則預設補上 http://。

    參數:
        url (str): 原始網域名稱或網址。

    回傳:
        str: 補全協定前綴後的完整網址。
    """
    if not url.startswith(('http://', 'https://')):
        url = 'http://' + url
    return url

async def process_urls(urls: list, output_file: str):
    """
    建立並發任務群組，非同步批次處理指定的 URL 清單。

    參數:
        urls (list): 該批次要處理的網址字串清單。
        output_file (str): 命中封鎖時的輸出檔案路徑。
    """
    # 建立並發信號量與 TCP 連線池控制器
    sem = asyncio.Semaphore(CONCURRENT_REQUESTS)
    connector = TCPConnector(limit=CONNECTION_LIMIT)

    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = []
        for url in urls:
            cleaned_url = clean_url(url.strip())
            if cleaned_url:
                # 建立受信號量保護的非同步工作
                task = bound_fetch(sem, session, cleaned_url, output_file)
                tasks.append(task)
        try:
            # 並行發起該批次的所有非同步請求並等待全部完成
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            # 若工作被取消，依序取消所有尚未完成的任務
            logging.error("工作因 asyncio.CancelledError 而被取消")
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

async def process_file_in_batches(input_file: str, output_file: str):
    """
    分批讀取輸入檔案中的網址清單，每滿 BATCH_SIZE 筆即執行一次非同步批次處理。

    參數:
        input_file (str): 包含網域/網址清單的來源檔案路徑。
        output_file (str): 命中封鎖結果的輸出檔案路徑。
    """
    with open(input_file, 'r', encoding='utf-8') as file:
        batch = []
        for line in file:
            batch.append(line.strip())
            # 累積滿一個批次大小時即觸發處理，並重置暫存緩衝區
            if len(batch) >= BATCH_SIZE:
                await process_urls(batch, output_file)
                batch = []
        # 處理剩餘不足一個批次的網址
        if batch:
            await process_urls(batch, output_file)

def main():
    """
    程式主要入口函式：
    定義輸入與輸出檔案名稱、初始化輸出檔案，並建立執行事件迴圈。
    """
    # 預設輸入檔案名稱（可依需求調整為 merged.txt、list.txt 或 kr.list）
    input_file = 'domains.txt'
    # 檢測結果輸出檔案名稱
    output_file = 'output.txt'

    # 執行前先清空輸出檔案內容
    open(output_file, 'w', encoding='utf-8').close()

    # 取得 asyncio 事件迴圈並啟動分批處理
    loop = asyncio.get_event_loop()
    loop.run_until_complete(process_file_in_batches(input_file, output_file))

if __name__ == '__main__':
    start_time = time.time()
    main()
    logging.info(f"檢測完成！總共耗時 {time.time() - start_time:.2f} 秒")
