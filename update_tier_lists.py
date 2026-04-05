import os
import json
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime

# 英中翻譯字典 (只包含高價值或常客)
ALIAS_MAP = {
    # Genshin
    "Furina": "芙寧娜",
    "Neuvillette": "那維萊特",
    "Mavuika": "瑪薇卡",
    "Xilonen": "希諾寧",
    "Ororon": "歐洛倫",
    "Citlali": "茜特菈莉",
    "Columbina": "哥倫比婭",
    "Zibai": "茲白",
    "Ineffa": "伊芙",
    "Kazuha": "楓原萬葉",
    "Zhongli": "鍾離",
    "Yelan": "夜蘭",
    "Nahida": "納西妲",
    "Arlecchino": "阿蕾奇諾",
    "Chasca": "恰斯卡",
    "Skirk": "絲柯克",
    "Kinich": "基尼奇",
    "Raiden Shogun": "雷電將軍",
    "Raiden": "雷電將軍",
    "Alhaitham": "艾爾海森",
    "Flins": "菲林斯",
    # HSR
    "Acheron": "黃泉",
    "Firefly": "流螢",
    "Ruan Mei": "阮•梅",
    "Sparkle": "花火",
    "Robin": "知更鳥",
    "The Herta": "大黑塔",
    "Sunday": "星期日",
    "Tribbie": "緹寶",
    "Mydei": "萬敵",
    "Castorice": "遐蝶",
    "Anaxa": "那刻夏",
    "Phainon": "白厄",
    "Lingsha": "靈砂",
    "Rappa": "亂破",
    "Feixiao": "飛霄",
    "Hyacine": "長夜月",
    "Cipher": "賽飛兒",
    "Yunli": "雲璃",
    "Aventurine": "砂金",
    # WuWa
    "Shorekeeper": "守岸人",
    "Phrolova": "弗洛洛",
    "Augusta": "奧古斯塔",
    "Cartethyia": "卡提希婭",
    "Aemeath": "埃萊特",
    "Ciaccona": "卡羅莎",
    "Phoebe": "菲比",
    "Galbrena": "嘉貝莉娜",
    "Verina": "維里奈",
    "Zani": "贊妮",
    "Sigrika": "西格莉卡",
    "Camellya": "椿",
    "Jinhsi": "今汐",
    "Changli": "長離",
    "Jiyan": "忌炎",
    "Yinlin": "吟霖"
}

def translate_name(eng_name):
    clean_name = eng_name.replace("C0", "").replace("C6", "").strip()
    return ALIAS_MAP.get(clean_name, clean_name)

def update_json_file(filename, ss_names, s_names):
    if not os.path.exists(filename):
        return False
    try:
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # 過濾空值與去重
        ss_names = list(dict.fromkeys([x for x in ss_names if x]))
        s_names = list(dict.fromkeys([x for x in s_names if x]))
        
        # 只在成功抓到名單時才覆寫，避免網路錯誤毀掉 JSON
        if len(ss_names) > 5:
            data["highValueFor8591"] = ss_names + s_names
            data["meta"] = data.get("meta", {})
            data["meta"]["generated_at"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
            data["meta"]["auto_updated"] = True
            
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            print(f"✅ {filename} 更新成功！(SS: {len(ss_names)} / S: {len(s_names)})")
            return True
        else:
            print(f"⚠️ {filename} 抓取數量過少 ({len(ss_names)})，自動放棄更新防呆")
            return False
            
    except Exception as e:
        print(f"❌ {filename} 更新失敗: {e}")
        return False

def scrape_genshin_gg(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # genshin.gg 的 tier list 通常是用某些特定 div
        # 由於網頁結構常常變化，我們做一個簡單的通用擷取:
        # SS / S 會出現在最上面的 list，這裡只做個概念展示
        chars = [a.get('href', '').split('/')[-2].capitalize() for a in soup.find_all('a', href=True) if 'characters/' in a['href']]
        # 因為無法完美拆分 S 跟 SS，這裡假設前 15 名是 SS，16~30 是 S
        chars = list(dict.fromkeys(chars)) # 去重
        
        if len(chars) >= 30:
            ss_names = [translate_name(c) for c in chars[:15]]
            s_names = [translate_name(c) for c in chars[15:30]]
            return ss_names, s_names
    except Exception as e:
        print(f"Scrape error for {url}: {e}")
    return [], []

def run_tier_updates():
    print("🔄 啟動每週 Meta 角色排行榜自動更新（Auto Updater）...")
    
    # 1. 原神
    gs_ss, gs_s = scrape_genshin_gg("https://genshin.gg/tier-list/")
    if gs_ss:
        update_json_file("genshin_tier_list.json", gs_ss, gs_s)
        
    # 2. 崩鐵
    hsr_ss, hsr_s = scrape_genshin_gg("https://genshin.gg/star-rail/tier-list/")
    if hsr_ss:
        update_json_file("hsr_tier_list.json", hsr_ss, hsr_s)
        
    # 3. 鳴潮（暫以寫死或別的爬蟲為準，因為 genshin.gg 沒有鳴潮）
    ww_ss = [translate_name("Shorekeeper"), translate_name("Phrolova"), translate_name("Augusta"), translate_name("Cartethyia"), translate_name("Aemeath"), translate_name("Ciaccona"), translate_name("Phoebe"), translate_name("Galbrena"), translate_name("Zani"), translate_name("Verina"), translate_name("Sigrika"), translate_name("Camellya"), translate_name("Jinhsi")]
    ww_s = [translate_name("Changli"), translate_name("Jiyan"), translate_name("Yinlin"), translate_name("Cartethyia")]
    update_json_file("wutheringwaves_tier_list.json", ww_ss, ww_s)

if __name__ == "__main__":
    run_tier_updates()
