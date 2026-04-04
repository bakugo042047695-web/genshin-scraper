import os
import json
import gspread
from datetime import datetime
from google.oauth2.service_account import Credentials

games = {
    "原神": {"listing_file": "gs_listing_seen.json", "sheet": "原神-成交紀錄"},
    "鳴潮": {"listing_file": "ww_listing_seen.json", "sheet": "鳴潮-成交紀錄"},
    "崩鐵": {"listing_file": "sr_listing_seen.json", "sheet": "崩鐵-成交紀錄"},
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GCP_KEY_FILE = os.path.join(BASE_DIR, "gcp_key.json")
G_SHEET_KEY = "1SOt-2DwJVEcEgvuvQfAvW6ue6WcrnvywxPbKIJFEcYI"

def load_listing_seen(filepath):
    # 此腳本目前在本地端，如果沒有 MONGO_URI 就讀取本地 JSON
    full_path = os.path.join(BASE_DIR, filepath)
    if os.path.exists(full_path):
        with open(full_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        seen_map = data.get("seen_map", {})
        # 相容舊版
        for url in data.get("urls", []):
            if url not in seen_map:
                seen_map[url] = ""
        return seen_map
    return {}

def calc_days_on_market(post_time_str, seen_map, url, seller_id="", title=""):
    today = datetime.now()

    # A
    if post_time_str and post_time_str != "-":
        for fmt in ["%Y-%m-%d", "%Y/%m/%d"]:
            try:
                d = datetime.strptime(post_time_str.strip(), fmt)
                days = (today - d).days
                return str(days)
            except:
                continue

    # B
    first_seen = seen_map.get(url, "")
    if isinstance(first_seen, dict):
        first_seen = first_seen.get("date", "")
    if first_seen:
        try:
            d = datetime.strptime(first_seen, "%Y-%m-%d")
            days = (today - d).days
            return f"≥{days}"
        except:
            pass

    # C
    if title:
        title_idx = seen_map.get("__title_idx__", {})
        ebt = title_idx.get(title, "")
        if ebt:
            try:
                d = datetime.strptime(ebt, "%Y-%m-%d")
                days = (today - d).days
                return f"≥{days}*"
            except:
                pass

    # D
    if seller_id: # (簡易版不排除大盤商了，只是盡量補)
        sidx = seen_map.get("__seller_idx__", {})
        e = sidx.get(seller_id, "")
        if e:
            try:
                d = datetime.strptime(e, "%Y-%m-%d")
                days = (today - d).days
                return f"≥{days}†"
            except:
                pass

    return "-"

def clean_seller_id(raw_seller):
    s = str(raw_seller).replace("🍽️", "").replace("（大盤商）", "").strip()
    return s

def main():
    print("啟動舊資料「售出天數」回補腳本...")
    scopes = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    if os.path.exists(GCP_KEY_FILE):
        creds = Credentials.from_service_account_file(GCP_KEY_FILE, scopes=scopes)
    else:
        print("找不到 GCP 金鑰", GCP_KEY_FILE)
        return

    gc = gspread.authorize(creds)
    try:
        sh = gc.open_by_key(G_SHEET_KEY)
    except Exception as e:
        print("無法開啟 Spreadsheet", e)
        return

    for game_name, info in games.items():
        print(f"\n處理 {game_name} ...")

            
        # ====== 第一階段：從 Google Sheets 的兩個分頁萃取歷史日期 ======
        active_sheet_name = game_name
        history_sheet_name = info["sheet"]
        
        # 讀取「成交紀錄」與「現行賣場」
        try:
            ws_history = sh.worksheet(history_sheet_name)
            history_data = ws_history.get_all_values()
        except:
            print(f"找不到工作表 {history_sheet_name}")
            continue

        try:
            ws_active = sh.worksheet(active_sheet_name)
            active_data = ws_active.get_all_values()
        except:
            active_data = []

        if len(history_data) <= 1:
            continue

        # 重建虛擬 seen_map
        pseudo_seen_map = {
            "__title_idx__": {},
            "__seller_idx__": {}
        }
        
        # Helper: 更新索引
        def update_idx(date_str, title_str, seller_str):
            if not date_str or not title_str: return
            # 確保 date_str 只有 YYYY-MM-DD
            d = date_str.split(" ")[0].strip()
            t = title_str.strip()
            s = clean_seller_id(seller_str)
            
            # 更新 title_idx
            if t:
                ext = pseudo_seen_map["__title_idx__"].get(t, "")
                if not ext or d < ext:
                    pseudo_seen_map["__title_idx__"][t] = d
                    
            # 更新 seller_idx (只記錄小賣家的，這邊簡單全記，因爲腳本的 calc_days_on_market 不再區分)
            if s:
                exs = pseudo_seen_map["__seller_idx__"].get(s, "")
                if not exs or d < exs:
                    pseudo_seen_map["__seller_idx__"][s] = d

        # 從「成交紀錄」萃取 (A=0: 發現日, D=3: 標題, M=12: 賣家)
        for row in history_data[1:]:
            if len(row) >= 13:
                update_idx(row[0], row[3], row[12])

        # 從「現行賣場」萃取 (A=0: 發現日, C=2: 標題, M=12: 賣家)
        for row in active_data[1:]:
            if len(row) >= 13:
                update_idx(row[0], row[2], row[12])

        # ====== 第二階段：進行回補 ======
        updates = []
        for i, row in enumerate(history_data[1:], start=2):
            if len(row) < 14: continue
            
            post_time = row[1]
            days_str = row[2]
            title = row[3]
            seller_str = row[12]
            url = row[13]
            seller_id = clean_seller_id(seller_str)

            if days_str == "-":
                new_days = calc_days_on_market(post_time, pseudo_seen_map, url, seller_id, title)
                if new_days != "-":
                    updates.append({'range': f'C{i}', 'values': [[new_days]]})

        if updates:
            print(f"  找到 {len(updates)} 筆可回補的紀錄，寫入中...")
            ws_history.batch_update(updates)
            print("  寫入完成！")
        else:
            print("  沒有需要回補的紀錄（或皆無法推算）。")

if __name__ == "__main__":
    main()
