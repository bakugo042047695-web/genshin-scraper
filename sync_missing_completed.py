from genshin_scraper_original import (
    get_gsheet, build_games_config, get_mongo_db, scrape_pages,
    load_sellers, load_listing_seen, init_gsheet_completed, update_gsheet_completed
)
from playwright.sync_api import sync_playwright

def sync_missing():
    print("啟動補齊手續...")
    try:
        gc = get_gsheet()
        if not gc: 
            print("Google Sheet 無法連線")
            return
    except Exception as e:
        print("Google Sheet 連線錯誤", e)
        return
        
    GAMES = build_games_config()
    db = get_mongo_db()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        main_page = browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        
        for game_key in ["原神", "崩鐵"]:
            print(f"\n檢查 {game_key} 缺漏資料...")
            g = GAMES[game_key]
            ws_completed = init_gsheet_completed(gc, game_key)
            if not ws_completed: continue
            
            # 從 Google Sheet 獲取已經存在的 URL (通常在 Column N, index 13)
            all_records = ws_completed.get_all_values()
            gsheet_urls = set()
            for row in all_records[1:]:
                if len(row) >= 14:
                    gsheet_urls.add(row[13])
            print(f"  Google Sheet 現有 {len(gsheet_urls)} 筆紀錄")
            
            # 抓取最新的 3 頁歷史成交 (強制不使用 stop_at_seen，因為我們需要補上之前漏掉的)
            # scrape_pages signature requires detail_page as well
            latest_completed = scrape_pages(
                main_page,
                g["completed_url"],
                3,
                "已完成",
                stop_at_seen=None, # 強制抓取
                do_detail=False,
                char_weights=g["char_weights"],
                alias_map=g["alias_map"]
            )
            
            missing_completed = [r for r in latest_completed if r["url"] not in gsheet_urls]
            print(f"  從最新 3 頁找到 {len(missing_completed)} 筆 Google Sheet 缺漏資料")
            
            if missing_completed:
                sellers = load_sellers(g["seller_file"])
                seen_map = load_listing_seen(g["listing_seen_file"])
                high_tier_chars = g.get("high_tier_chars", set())
                try:
                    update_gsheet_completed(ws_completed, missing_completed, sellers, seen_map, high_tier_chars)
                    print(f"  成功補上 {len(missing_completed)} 筆！")
                except Exception as e:
                    print(f"  補入資料時出錯：{e}")
                
        browser.close()

if __name__ == "__main__":
    sync_missing()
