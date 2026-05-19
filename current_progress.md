# genshin-auto-scraper 專案進度與架構交接文件
**最後更新：2026-04-18**
**Repository：** `https://github.com/tya85364-ops/genshin-auto-scraper`
**部署平台：** Railway（後端爬蟲與API）與 GitHub Pages（前端 PWA 看盤雷達）

---

## 一、專案概覽

這是一個自動爬取 [8591 賣場](https://www.8591.com.tw/) 的市場分析爬蟲，並配有一套輔助估價的 PWA 介面（8591 看盤雷達），監控四款遊戲的帳號買賣：

| 遊戲 | 前綴 | Emoji |
|------|------|-------|
| 原神 | `gs` | ⚙️ |
| 鳴潮 | `ww` | 🌊 |
| 崩鐵 | `sr` | 🚂 |
| 絕區零 | `zzz` | ⚡（已加入爬取迴圈，但 `genshin_scraper_original.py` 內的 config 設定檔字典還待補齊） |

---

## 二、關鍵系統與檔案

| 檔案/模組 | 用途 |
|------|------|
| `genshin_scraper_original.py` | **主爬蟲程式**，每 30 分鐘執行一輪抓取，計算各種 CP 值並推播降價通知。 |
| `docs/index.html` | **前端 PWA 程式**，部署於 Github Pages 上。可直接從前端讀取 Google Sheets csv，進行關鍵字或條件篩選（支援金角/金武數量過濾）。 |
| `api_server.py` | **輕量後端 API (Flask)**，處理 PWA 發來的自訂降價目標（GET/POST/DELETE），並存入 MongoDB `custom_targets`。 |
| `daily_maintenance.py` | 每日自動維護腳本，跑整併大盤商資料、補齊 Google Sheets 天數等維護工作。 |
| `global_sellers.json` | **全遊戲共用大盤商名單**，累計交易次數超過 5 次即視為「大盤商 `🍽️`」。 |

---

## 三、最新完成功能（2026-04-17 / 18 更新）

1. **自訂降價通知 (PWA + API + Railway + Discord)**
   - 前端 PWA `docs/index.html` 加入「🔔 (鈴鐺)」按鈕，使用者能打入目標金額（ex: 降到 3500 就通知）。
   - 前端透過 AJAX 呼叫部署在 Railway 上的 `api_server.py`，寫入 MongoDB。
   - `genshin_scraper_original.py` 主爬蟲抓取時會比對這些設定，只要現行價 <= 目標價，立刻發 Discord Webhook 通知並標記為已達成免得重複發送。

2. **金角與金武數量篩選過濾器 (PWA 前端)**
   - 在前端介面上方加入「金數」輸入格。
   - 使用者可以打入 **金角（例如：50）** 或 **金武（例如：10）**。
   - 搜尋時系統會進行 **正負 10 本地誤差搜尋**（找 `abs(金數 - 目標輸入) <= 10` 的帳號）。
   - 卡片上會精準顯示：`⭐ 50 金角 / 20 金武` 的標記。

3. **Chart.js 趨勢報表 (PWA 前端)**
   - 在前端左上方實作了 `📊 切換走勢圖` 按鈕，系統會將掃描出的行情報表依據日期分組，渲染成雙 Y 軸折線圖 (價格與 CP 值)。

4. **修復全域大盤商與 MongoDB 記憶丟失問題**
   - 過去 Railway 容器如果休眠重啟，會在本地 JSON 遺失狀態。現改為「MongoDB 優先，本地 JSON 備援」雙軌讀寫模式。
   - 解決了商品降價邏輯（`check_price_drop`）判斷過於敏感，改成只在累計跌幅達 15% 才會觸發跌價重置。

---

## 四、環境變數與部署設定 (Railway 必設)

| 變數名 | 說明 |
|--------|------|
| `MONGODB_URI` | 核心！爬蟲記憶體。包含 `scraper_db` 資料庫。 |
| `GCP_KEY_JSON` | Google Service Account JSON 字串，提供 Google Sheets 寫入權限。 |
| `TZ` | 值設為 `Asia/Taipei`，確保存檔時間戳顯示正確。 |

---

## 五、目前已知的待辦事項 (TODOs)

1. **絕區零的 Configuration 不完整**：
   目前雖然已經將「絕區零」加進了迴圈 `for game_key in [...]` 中，但在 `build_games_config()` 函數的 `games = {...}` 字典結構內仍缺乏「絕區零」相關的完整設定（Webhook 網址、Excel 命名等），若直接執行可能會噴 `KeyError` 使爬蟲停止。

2. **`TIER_LIST_FILES` 的本地硬編碼**：
   某些路徑（特別 Excel 檔）原本寫死為 `C:\Users\toge\...`，這導致在雲端部署時只能吃相對路徑的 JSON，部分邏輯若想輸出完整備份可能會有 IO 錯誤。

---
`這份文件可以隨時丟給 Claude 提供背景知識，讓它幫忙接手處理接下來的開發工作。`
