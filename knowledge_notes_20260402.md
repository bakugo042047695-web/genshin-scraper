# 8591 爬蟲自動化維護日誌 (2026-04-02 起)

這份文件記錄了針對 `genshin-scraper` 所做的最佳化與維護經驗，作為未來修復、換雲端帳號或新功能開發的**最重要防呆參考**。請在處理問題前優先閱讀此檔案。

## 1. 「售出所需天數」四層推算法改良
為解決賣家經常「改價格重新拋售」導致原網址失效、無法推算真實上架天數的問題，我們在 `genshin_scraper_original.py` 實作了多維度比對系統：
* **Method A (網頁直抓)**：精確的上架時間。
* **Method B (網址追蹤)**：比對歷史 `urls` 發現日。
* **Method C (標題追蹤)**：新建 `__title_idx__` 字典，紀錄該標題最早出現日。完美破解改價重拋，找回過去紀錄。
* **Method D (賣家追蹤)**：新建 `__seller_idx__` 字典，用賣家最早活躍日估計。
  * **⚠️ 大盤商豁免條款**：透過引入 `is_big_seller` 參數，如果賣場商品大於 `BIG_SELLER_THRESHOLD` (大盤商)，**強制略過 Method D**，避免其底下所有新商品的上架天數都被無限放大。

## 2. 舊資料暴力回補腳本 (`backfill_days.py`)
由於舊版 JSON 尚未紀錄 `__title_idx__`，傳統方法無法回推。我們採用了直接爬取 Google Sheets 歷史的手法：
1. 一次性讀取「現行賣場(Active)」與「成交紀錄(History)」兩個 Sheet。
2. 以「發現日期」作為依據，在本地建立一份虛擬的 `pseudo_seen_map`。
3. 批次將舊資料中售出所需天數為 `-` 的欄位（超過數千筆資料）改寫為推算天數。
* **未來運用**：若之後因任何原因又遺失了 JSON 記憶，可隨時復用此腳本從 Google Sheets 重建記憶索引並自動回補。

## 3. 歷史核心最佳化紀錄 (資料精確度 & 效能)
除了售出天數推算外，我們也對爬蟲的效能與資料評估準確度做過幾次關鍵升級：
1. **極端值剔除系統 (`get_trimmed_mean`)**：
   * 過去經常有賣家亂標價（例如隨便填個 $999999）導致整個遊戲的 CP 均值被無限拉高。
   * 現在採用了 Trimmed Mean 演算法，在計算 `cp1`、`cp2`、`cpw` 和 `price` 的歷史均值時，會**自動剔除最高與最低的 15% 紀錄**，確保算出來的門檻不受極端值影響。
2. **雙軌掃描機制 (`fast_track_scan`)**：
   * 為了克服 Playwright 爬取詳情頁極度耗時的問題，我們導入了「主爬蟲 + 輕量掃描」雙軌機制。
   * `fast_track_scan` 只掃描首頁清單，搭配極為嚴苛的防守條件（例如只過濾絕對超值品），一旦發現獵物不進詳情頁直接推送 Discord，大幅提升警報的即時性。

## 4. Railway 資源限制排查與應對
* **現象**：程式運行幾日後無預警停止，且無程式錯誤日誌。
* **原因**：Railway Free Trial 提供 500小時 或 $5 的資源。因為程式設計為 `while True:` 常駐運行，大約 20 天會耗盡免費開機額度。
* **應對方案 (無縫接軌)**：
  * 修改 Python 內的排程從 10 分鐘降為 **30 分鐘** (降低運算負載)。
  * **定期轉移帳號**：若不升級付費，只要準備新的 GitHub 與 Railway 帳號，並完美設置環境變數，即能無縫轉移。

---

## 5. Railway 新帳號與環境變數轉移 防呆指南 (部署踩坑全紀錄)
經過 2026/04 的換號踩坑經驗，下次更換 Railway 帳號時，**請務必確實執行以下所有步驟，漏一個都會導致災難**：

### 🚨 災難重現與原因分析
1. **Google Sheets 連線失敗 （缺少或破損 `GCP_KEY_JSON`）**
   * **現象**：爬蟲有抓資料，卻無權限印進 Google 表單 (log 會報 `'NoneType' object has no attribute 'open_by_key'`)，原神/崩鐵/鳴潮皆無法更新。
   * **解法**：從本機 `gcp_key.json` 全選複製，在 Railway 設定為 `GCP_KEY_JSON`。
   * **⚠️ 踩坑提示**：Railway 的「Raw Editor」介面對包含換行符 (`\n`) 的 JSON 解析有 Bug！**絕對不要透過 Raw Editor 貼上 JSON**，必須點選該變數的單獨 `Edit`，或是在創立新變數的獨立欄位中貼上。

2. **Discord 瘋狂洗版、什麼都被當成「優質商品」 （缺少 `MONGODB_URI`）**
   * **現象**：Discord 推播暴增，且系統不認得大盤商、所有的 CP 門檻都降低為預設值。
   * **原因**：程式讀不到 MongoDB 裡累積的「已見過網址 (`seen_urls`)」、「歷史 CP 統計」與「大盤商名單」。程式徹底失憶，把 8591 上一堆早就盤踞的商品當成「剛上架的超棒商品」推播！
   * **解法**：貼上 `mongodb+srv://genshin:genshin123@cluster0.svtlvs0.mongodb.net/?appName=Cluster0`。MongoDB 是系統的「大腦」，就算換了 Railway，只要有這把鑰匙，所有的學習模型都會接續運作。

### 📌 完美搬家 SOP (請照做！)
1. 申請新 GitHub / Railway 帳號，將本地最新程式碼推上。
2. 在 Railway 綁定該 GitHub Repo 開始部署。
3. **[最關鍵] 到 Railway / 專案 / Variables 手動並仔細地建立這 3 個變數**：
   - `TZ` = `Asia/Taipei`
   - `MONGODB_URI` = `mongodb+srv://genshin:genshin123@cluster0.svtlvs0.mongodb.net/?appName=Cluster0`
   - `GCP_KEY_JSON` = `(完整貼上本地金鑰)`
4. 確認儲存並等到 Deploy 結束。觀察接下來一兩梯次的 Discord 發送，如果不小心中斷或漏資料了：
   * -> 執行一次 `sync_missing_completed.py` 把空窗期那些只進了 MongoDB 卻沒上 Google Sheets 的已完成交易拿回來。
   * -> 再執行一次 `backfill_days.py` 給補回來的資料算一算「售出所需天數」。
