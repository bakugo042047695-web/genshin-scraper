import os
import requests
import json
import gspread
from datetime import datetime
from google.oauth2.service_account import Credentials

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GCP_KEY_FILE = os.path.join(BASE_DIR, "gcp_key.json")
# Try to find Spreadsheet ID from genshin_scraper.py
G_SHEET_KEY = "1W7FjA_Gz9_M5BOS7D2_pDEJ9zO_qgJ6k48iF18Hl4bA"
scraper_path = os.path.join(BASE_DIR, "genshin_scraper.py")
try:
    with open(scraper_path, "r", encoding="utf-8") as f:
        for line in f:
            if "SPREADSHEET_ID" in line and "=" in line:
                import re
                m = re.search(r'SPREADSHEET_ID\s*=\s*["\']([^"\']+)["\']', line)
                if m:
                    G_SHEET_KEY = m.group(1)
                    break
except Exception:
    pass


DISCORD_HOOK = ""
try:
    with open(scraper_path, "r", encoding="utf-8") as f:
        content = f.read()
        m = re.search(r'DISCORD_PRICE_DROP\s*=\s*["']([^"']+)["']', content)
        if m:
            DISCORD_HOOK = m.group(1)
except: pass

def send_discord_webhook(msg):
    if not DISCORD_HOOK: return
    try:
        requests.post(DISCORD_HOOK, json={"content": msg}, timeout=5)
    except: pass

GAMES = ["原神", "鳴潮", "崩鐵", "絕區零"]

def clean_seller_id(raw_seller):
    s = str(raw_seller).replace("🍽️", "").replace("（大盤商）", "").strip()
    return s

def calc_days_on_market(post_time_str, pseudo_seen_map, url, seller_id, title):
    today = datetime.now()
    if post_time_str and post_time_str != "-":
        for fmt in ["%Y-%m-%d", "%Y/%m/%d"]:
            try:
                d = datetime.strptime(post_time_str.strip(), fmt)
                return str((today - d).days)
            except:
                continue
    if title:
        d_str = pseudo_seen_map["__title_idx__"].get(title, "")
        if d_str:
            try:
                days = (today - datetime.strptime(d_str, "%Y-%m-%d")).days
                return f"≥{days}*"
            except: pass
    if seller_id:
        d_str = pseudo_seen_map["__seller_idx__"].get(seller_id, "")
        if d_str:
            try:
                days = (today - datetime.strptime(d_str, "%Y-%m-%d")).days
                return f"≥{days}†"
            except: pass
    return "-"

def get_big_sellers():
    from pymongo import MongoClient
    URI = os.getenv("MONGODB_URI", "mongodb+srv://genshin:genshin123@cluster0.svtlvs0.mongodb.net/scraper_db?appName=Cluster0")
    try:
        client = MongoClient(URI, serverSelectionTimeoutMS=5000)
        db = client.get_default_database()
    except:
        db = client["scraper_db"]
    doc = db["sellers"].find_one({"_id": "global_sellers.json"})
    big_sellers = set()
    if doc:
        for sid, info in doc.items():
            if sid != "_id" and info.get("count", 0) >= 5:
                big_sellers.add(sid)
    return big_sellers

def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 啟動每日自動維護（大盤商回補 + 天數推算）...")
    if not os.path.exists(GCP_KEY_FILE):
        print("找不到 GCP 金鑰", GCP_KEY_FILE)
        return

    scopes = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file(GCP_KEY_FILE, scopes=scopes)
    gc = gspread.authorize(creds)
    try:
        sh = gc.open_by_key(G_SHEET_KEY)
    except Exception as e:
        print("無法開啟 Spreadsheet", e)
        return

    big_sellers = get_big_sellers()
    print(f"目前大盤商名額: {len(big_sellers)} 位")
    report_msg = f"🤖 **【每日維護完成報告】**\n✅ 系統存活且正常運作中！\n- 目前大盤商總數：{len(big_sellers)} 位\n"

    for game_name in GAMES:
        history_sheet_name = f"{game_name}-成交紀錄"
        active_sheet_name = game_name
        
        try:
            ws_history = sh.worksheet(history_sheet_name)
            history_data = ws_history.get_all_values()
        except:
            history_data = []

        try:
            ws_active = sh.worksheet(active_sheet_name)
            active_data = ws_active.get_all_values()
        except:
            active_data = []
            
        print(f"\n--- 處理 {game_name} ---")

        # 重建虛擬 seen_map (用於填補天數)
        pseudo_seen_map = {"__title_idx__": {}, "__seller_idx__": {}}
        def update_idx(date_str, title_str, seller_str):
            if not date_str or not title_str: return
            d = date_str.split(" ")[0].strip()
            t = title_str.strip()
            s = clean_seller_id(seller_str)
            if t:
                ext = pseudo_seen_map["__title_idx__"].get(t, "")
                if not ext or d < ext: pseudo_seen_map["__title_idx__"][t] = d
            if s:
                exs = pseudo_seen_map["__seller_idx__"].get(s, "")
                if not exs or d < exs: pseudo_seen_map["__seller_idx__"][s] = d

        for row in history_data[1:]:
            if len(row) >= 13: update_idx(row[0], row[3], row[12])
        for row in active_data[1:]:
            if len(row) >= 13: update_idx(row[0], row[2], row[12])

        # === 更新成交紀錄 ===
        updates_hist = []
        for i, row in enumerate(history_data[1:], start=2):
            if len(row) < 14: continue
            post_time = row[1]
            days_str = row[2]
            title = row[3]
            raw_seller = row[12]
            url = row[13]
            seller_id = clean_seller_id(raw_seller)

            # 補天數 (Col C)
            if days_str == "-":
                new_days = calc_days_on_market(post_time, pseudo_seen_map, url, seller_id, title)
                if new_days != "-":
                    updates_hist.append({'range': f'C{i}', 'values': [[new_days]]})
            
            # 補大盤商 (Col M)
            expected_seller = f"🍽️{seller_id}（大盤商）" if seller_id in big_sellers else seller_id
            if raw_seller != expected_seller:
                updates_hist.append({'range': f'M{i}', 'values': [[expected_seller]]})
        
        if updates_hist:
            print(f"更新 {history_sheet_name}: {len(updates_hist)} 個儲存格")
            ws_history.batch_update(updates_hist)
            
        # === 更新現行賣場 ===
        updates_active = []
        for i, row in enumerate(active_data[1:], start=2):
            if len(row) < 13: continue
            raw_seller = row[12]
            seller_id = clean_seller_id(raw_seller)
            expected_seller = f"🍽️{seller_id}" if seller_id in big_sellers else seller_id
            if raw_seller != expected_seller:
                updates_active.append({'range': f'M{i}', 'values': [[expected_seller]]})

        if updates_active:
            print(f"更新 {active_sheet_name}: {len(updates_active)} 個儲存格")
            ws_active.batch_update(updates_active)

        report_msg += f"- **{game_name}**: 更新 {len(updates_hist)} 筆歷史、{len(updates_active)} 筆在架\n"

    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 每日自動維護完成！")
    send_discord_webhook(report_msg)

if __name__ == "__main__":
    main()
