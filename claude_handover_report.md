# 🤖 給 Claude 的專案交接與背景知識設定檔
*(嗨，Claude！當你收到這份文件時，請將其作為本專案系統架構與業務邏輯的基礎上下文，後續的對話與除錯請依據此份文件發展。)*

---

## 🎯 一、專案概述 (Project Overview)
**專案名稱**：8591 市場看盤雷達與降價通報自動化系統 (genshin-auto-scraper)
**GitHub Repository**：`https://github.com/tya85364-ops/genshin-auto-scraper`
**專案核心目標**：自動爬取 8591 網站上四大遊戲（原神、鳴潮、崩鐵、絕區零）的帳號交易市場，利用加權算法（CPW）估算帳號真實價值，將資料推送到 Google Sheets 作為資料庫，並提供一個 PWA 前端介面供使用者動態篩選、追蹤，以及利用 Discord webhook 進行特定條件的斷崖式降價通報。

**部署環境**：
- **後端 API 與爬蟲本體**：託管於 Railway 平台 (Dockerized)，具備背景定時執行能力。
- **前端 Web APP**：PWA (Progressive Web App)，透過 Github Pages 靜態託管 (`/docs/index.html`)。

---

## ⚙️ 二、系統架構與技術棧 (Tech Stack)

### 1. 後端 (Backend & Scraper)
- **語言**：Python 3
- **核心爬蟲工具**：Playwright (負責模擬瀏覽器抓取 8591 的 JS 渲染內容與商品內文)。
- **輕量 API 伺服器**：Flask + flask-cors (負責接收使用者 PWA 發送的自訂通知目標)。
- **排程機制**：透過 `start.sh` 背景起 Flask API，並用 Python `schedule` 模組或無窮迴圈執行爬蟲 (預設每 30 分鐘一輪) 與每日維護腳本 (`daily_maintenance.py` UTC 18:00 執行)。

### 2. 資料庫 (Database & Storage)
- **記憶體狀態儲存**：MongoDB (雲端連線 `MONGODB_URI`)。為了防止 Railway 容器重啟遺失配置（如歷史紀錄、已處理清單、賣家累計），系統實作了**「MongoDB 優先，本地 JSON 備援」**的雙軌模式。
- **大數據展示與圖表資料來源**：Google Sheets API (`gcp_key.json` Auth)。爬蟲會將每輪的結果推上雲端 Sheet，前端 PWA 再藉由 Google Sheets 的 CSV export URL 直接將資料拉到前端渲染，實現**零後端資料庫負載**的強大架構。

### 3. 前端 (Frontend PWA)
- **技術**：原生 HTML / Vanilla CSS / Vanilla JS (無框架負擔) + Chart.js
- **特色**：支援安裝為桌面/手機 App，提供「關鍵字智能模糊配對」、「金角/金武容錯區間篩選」、「動態折線圖」、「一鍵複製估價 Prompt」與「追蹤清單設定」。

---

## 🗂️ 三、核心模組與檔案結構

| 檔案名稱 | 核心職責與功能說明 |
|----------|------------------|
| `genshin_scraper_original.py` | 整個專案的**大腦**。負責主爬蟲迴圈、讀取不同遊戲配置、計算 CP 值、過濾大盤商、向 Discord 發送最新報表與降價通知，最後再把結果寫入 Google Sheets。 |
| `api_server.py` | 以 Flask 運行的輕量服務，開出 GET/POST/DELETE `/api/targets` 介面。接收 PWA 端設定的自訂降價目標並存進 MongoDB，供爬蟲本體調用比對。 |
| `daily_maintenance.py` | **每日維護腳本**。處理跨遊戲的大盤商整合邏輯 (`global_sellers.json` 滿 5 次視為大盤商)，並負責補齊 Google Sheets 內遺漏的「售出天數」。 |
| `gen_tier_list / rules` | 存放於原始環境的各遊戲權重評分表 (JSON)，定義例如 6命火神加權等邏輯。 |
| `docs/index.html` | 前端 PWA 的本體。內部包含了 `smartMatch` (角色與命座智能解析系統)、Google Sheets CSV 串接解析器，以及最新的圖表渲染引擎。 |

---

## 📊 四、核心估算邏輯：CPW 系統 (Cost-Performance Weights)

為防止帳號數量暴漲導致價格失真，本系統定義了獨家的 **CP 判斷演算法**，讓真正有價值的滿命滿精帳號浮現：
1. **基礎分計算**：每 1 個 5 星角色 = 1 分（6命則為 7 分）；每 1 個 5 星專武 = 1 分（滿精為 5 分）。
2. **Meta 加權系數**：T0 幻神級角色（如原神火神、崩鐵黃泉、絕區零雅）權重 = `2.5`，T1 級 = `1.5`，常駐老角 = `1.0`。
3. **最終得分**：`(金角總數 * 權重 * 10) + (金武總數 * 權重 * 5)`。
4. **CP1 / CP2 / CPW 定義**：
   - `純角CP (CP1)` = 價格 / (金角數 * 10)
   - `帶武CP (CP2)` = 價格 / (總金角 + 總金武分數)
   - `加權CP (CPW)` = 價格 / 最終加權得分

---

## 🚀 五、最新實作與功能更新 (2026-04 最新里程碑)

5. **降價通知統一頻道化與雜訊過濾**
   新增 DISCORD_PRICE_DROP_WEBHOOK 環境變數，將四大遊戲的降價通報統一集中至單一「降價專區」頻道。並實作 cp1 <= threshold * 3 的動態雜訊過濾機制，避免被錯誤命座估值的極端防守價格洗版。
6. **智慧標題解析與別名庫 (Knowledge Base) 更新**
   修復 N-M（如 6-2夜闌）與 N+M（如 原神 6+1）的解析錯誤，將別名對應（例如水神→芙寧娜）改為從 market_knowledge_base.json 動態載入，大幅提升金角數量與命座抓取的準確度。
7. **全網賣家跨遊戲查水表功能修復**
   於 PWA 新增 🕵️ 賣家查水表 分頁，支援一鍵同時搜尋全網 8 份 (在架+成交) Google Sheets。已修復因短資料列 (short rows) 造成的 Cannot read properties of undefined 當機 Bug，以及無在架但有歷史紀錄時被誤判為空的錯誤渲染。

為了因應商務需求，系統剛完成以下幾個重大改版，請 Claude 特別留意這些新架構：

1. **自訂目標價追蹤 (Webhook Push)**
   前端加入 `🔔` 按鈕可輸入目標價 -> `api_server.py` 存入 Mongo 的 `custom_targets` -> `genshin_scraper_original.py` 掃描到現價 <= 目標價時 -> 觸發專用 Discord 頻道通知，解除監聽。
2. **前端金角 / 金武 ±10 誤差搜查**
   在 `docs/index.html` 的 `applyFilter()` 裡加入了「金角」與「金武」的獨立輸入框。當有輸入此條件時，只會顯示 `abs(目標金數 - 實際金數) <= 10` 範圍內的精準結果。
3. **PWA 整合 Chart.js 動態走勢圖**
   可直接於網頁抓取到的資料中依「日期」分組，渲染出近期均價與 CP 值的雙連動圖表。
4. **跨四合一大盤商追蹤 (Cross-Game Sellers)**
   廢棄舊版單兵作戰，轉為維護一份 `global_sellers.json`，四款遊戲交易次數直接加總，觸發門檻（>=5）後上 `🍽️` 標記。

---

## ⚠️ 六、目前已知 Bug 與待辦事項 (重點交接)

Claude，當你開始撰寫新代碼或修復問題時，可以優先思考以下幾點：

1. **絕區零 (ZZZ) 爬蟲設定檔殘缺 (KeyError 隱患)**
   目前的程式中，已經將 `'絕區零'` 這個字串加入了主執行的 `for game_key in [...]` 迴圈中，但在 `build_games_config()` 的設定字典裡並沒有相對應的「絕區零 URL、webhook 網址、JSON 檔名」紀錄。這會導致輪到絕區零時引發 KeyError 崩潰。**必須緊急補上配置！**
2. **硬編碼與路徑清理**
   歷史程式碼中有著大量的 `C:\Users\toge\...` 絕對路徑痕跡（如 `TIER_LIST_FILES`），雖不影響 Railway 環境（因 Railway 用的是 MongoDB 存取與相對路徑），但有時候在做 CSV 導出時，檔案 IO 會因此報錯，建議找機會拔除。
3. **PWA 金武顯示問題優化**
   現在的 `index.html` 雖然可以搜「金武」，但 `COLS` 的 Google Sheets CSV index 可能因為 `completed` (成交紀錄) 多塞了時間欄位而位移，導致金武的數字在特定狀態下可能抓到別的欄外資料，需要驗證 `COLS` 的欄位 mapping 是否精準對齊。

---
`End of Document. Please acknowledge your understanding before proceeding with further operations.`
