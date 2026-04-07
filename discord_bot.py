import os
import discord
from discord import app_commands
from dotenv import load_dotenv
from typing import Optional

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
SPREADSHEET_ID = "1SOt-2DwJVEcEgvuvQfAvW6ue6WcrnvywxPbKIJFEcYI"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GCP_KEY_FILE = os.path.join(BASE_DIR, "gcp_key.json")

# 工作表名稱對照
GAME_SHEETS = {
    "崩鐵 (在架)":  ("崩鐵",          "in_progress"),
    "崩鐵 (成交)":  ("崩鐵-成交紀錄", "completed"),
    "原神 (在架)":  ("原神",          "in_progress"),
    "原神 (成交)":  ("原神-成交紀錄", "completed"),
    "鳴潮 (在架)":  ("鳴潮",          "in_progress"),
    "鳴潮 (成交)":  ("鳴潮-成交紀錄", "completed"),
    "絕區零 (在架)":  ("絕區零",          "in_progress"),
    "絕區零 (成交)":  ("絕區零-成交紀錄", "completed"),
}

# 欄位索引
COLS = {
    "in_progress": {"date": 0, "title": 2, "price": 3, "gold": 4, "cp1": 6, "seller": 12, "url": 13},
    "completed":   {"date": 0, "title": 3, "price": 4, "gold": 5, "cp1": 9, "seller": 12, "url": 13},
}

def get_gc():
    import gspread
    from google.oauth2.service_account import Credentials
    import json

    # Railway 環境：GCP_KEY_JSON 環境變數優先
    key_json = os.getenv("GCP_KEY_JSON", "")
    if key_json:
        info = json.loads(key_json)
        creds = Credentials.from_service_account_info(
            info, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])
    else:
        creds = Credentials.from_service_account_file(
            GCP_KEY_FILE, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])
    return gspread.authorize(creds)

def fetch_and_filter(sheet_name, sheet_type, p_min, p_max, kw):
    gc = get_gc()
    sh = gc.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet(sheet_name)
    rows = ws.get_all_values()[1:]  # 跳標題
    c = COLS[sheet_type]

    results = []
    for row in rows:
        def g(i): return row[i] if len(row) > i else ""
        title  = g(c["title"])
        price_s= g(c["price"])
        cp1_s  = g(c["cp1"])
        seller = g(c["seller"])
        url    = g(c["url"])
        date_s = g(c["date"])
        gold_s = g(c["gold"])

        try: price = float(price_s.replace(",","").replace("$",""))
        except: price = 0
        if price == 0: continue
        if not (p_min <= price <= p_max): continue
        if kw and kw.lower() not in title.lower(): continue

        results.append({
            "title": title, "price": price, "cp1": cp1_s,
            "gold": gold_s, "seller": seller, "url": url, "date": date_s
        })
    return results


class RadarBot(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        print(f"[OK] Discord Bot online: {self.user}")

bot = RadarBot()

@bot.tree.command(name="search", description="8591 市場快速盤查（讀取 Google Sheets 歷史資料）")
@app_commands.describe(
    game="選擇遊戲與類型（在架/成交）",
    min_price="最低價（選填，預設不限）",
    max_price="最高價（選填，預設不限）",
    keyword="標題必須包含的關鍵字（選填）",
    limit="顯示幾筆（選填，預設 10，最多 25）"
)
@app_commands.choices(game=[
    app_commands.Choice(name=k, value=k) for k in GAME_SHEETS.keys()
])
async def search_cmd(
    interaction: discord.Interaction,
    game: app_commands.Choice[str],
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    keyword: Optional[str] = None,
    limit: Optional[int] = 10
):
    await interaction.response.defer(thinking=True)

    sheet_name, sheet_type = GAME_SHEETS[game.value]
    p_min = min_price if min_price is not None else 0
    p_max = max_price if max_price is not None else 999999
    kw    = keyword.strip() if keyword else ""
    n     = max(1, min(limit or 10, 25))  # 夾在 1~25 之間

    try:
        results = await bot.loop.run_in_executor(
            None, fetch_and_filter, sheet_name, sheet_type, p_min, p_max, kw)
    except Exception as e:
        await interaction.followup.send(f"? Google Sheets ??: {e}")
        return

    if not results:
        cond = f"${p_min:,}~${p_max:,}" + (f" ?:{kw}" if kw else "")
        await interaction.followup.send(f"?? ????({cond})??{game.value}???!")
        return

    # ? CP1 ??? top5
    try:
        results.sort(key=lambda r: float(r["cp1"]) if r["cp1"] else 9999)
    except: pass

    cond_str = f"${p_min:,}~${p_max:,}" + (f" | {kw}" if kw else "")
    embed = discord.Embed(
        title=f"[{game.value}] 共 {len(results)} 筆",
        description=f"條件: {cond_str} | 顯示前 {n} 筆（依 CP 由低到高）",
        color=0x00BFFF
    )

    for r in results[:n]:
        try: price_fmt = f"${float(r['price']):,.0f}"
        except: price_fmt = r['price']
        field_name  = f"{price_fmt} | CP: {r['cp1']} | 金角: {r['gold']} | {r['date']}"
        field_value = f"[{r['title'][:60]}]({r['url']})" if r["url"] else r["title"][:80]
        embed.add_field(name=field_name, value=field_value, inline=False)

    await interaction.followup.send(embed=embed)


@bot.tree.command(name="trend", description="顯示特定角色的歷史成交價格走勢圖")
@app_commands.describe(
    game="選擇遊戲",
    keyword="角色名稱或配置關鍵字（必填，例如：流螢、6+1黃泉）"
)
@app_commands.choices(game=[
    app_commands.Choice(name=k, value=k) for k in ["崩鐵", "原神", "鳴潮", "絕區零"]
])
async def trend_cmd(
    interaction: discord.Interaction,
    game: app_commands.Choice[str],
    keyword: str
):
    await interaction.response.defer(thinking=True)
    sheet_name = f"{game.value}-成交紀錄"

    try:
        results = await bot.loop.run_in_executor(
            None, fetch_and_filter, sheet_name, "completed", 0, 999999, keyword.strip())
    except Exception as e:
        await interaction.followup.send(f"❌ Google Sheets 讀取失敗：{e}")
        return

    if not results:
        await interaction.followup.send(f"找不到包含「{keyword}」的 {game.value} 成交紀錄！")
        return

    # Prepare data for plotting
    # Import locally to save memory if not used
    import io
    from datetime import datetime
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    dates = []
    prices = []
    
    for r in results:
        # Extract date (assume format is YYYY-MM-DD or starts with it)
        date_str = str(r.get("date", "")).strip().split(' ')[0]
        price = r.get("price", 0)
        
        try:
            # Handle relative times fallback
            if "前" in date_str:
                dt = datetime.now()
            else:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
            dates.append(dt)
            prices.append(float(price))
        except:
            continue

    if not dates:
        await interaction.followup.send(f"無法解析日期，走勢圖產生失敗。")
        return

    # Sort chronologically
    sorted_pairs = sorted(zip(dates, prices), key=lambda x: x[0])
    dates, prices = zip(*sorted_pairs)

    # Plot
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(8, 4))
    
    # Scatter points for individual trades
    ax.scatter(dates, prices, color='#00D4FF', alpha=0.6, s=50, label='Trades')
    
    # Try to add a moving average line if enough points
    if len(prices) >= 3:
        import pandas as pd
        df = pd.DataFrame({'date': dates, 'price': prices})
        # Group by date to average if multiple on same day, then rolling
        daily = df.groupby('date')['price'].mean().reset_index()
        ax.plot(daily['date'], daily['price'], color='#6C63FF', linewidth=2, label='Daily Avg')

    ax.set_title(f"Market Trend: {keyword} ({game.value})", fontsize=14, color='white')
    ax.set_ylabel("Price (TWD)", fontsize=12)
    ax.set_xlabel("Date", fontsize=12)
    ax.grid(True, linestyle='--', alpha=0.3)
    ax.legend()
    
    # Format x-axis dates
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    fig.autofmt_xdate()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=150)
    buf.seek(0)
    plt.close(fig)

    file = discord.File(buf, filename="trend.png")
    
    # Calculate some stats
    median_price = sorted(prices)[len(prices)//2]
    latest_price = prices[-1]
    diff = latest_price - median_price
    diff_str = f"{'+' if diff > 0 else ''}{diff:,.0f}" if diff != 0 else "="
    
    embed = discord.Embed(
        title=f"📈 {game.value} - 【{keyword}】成交走勢",
        description=f"總計 {len(prices)} 筆成交紀錄\n中位數: **${median_price:,.0f}** | 最新價: **${latest_price:,.0f}** ({diff_str})",
        color=0x6C63FF
    )
    embed.set_image(url="attachment://trend.png")

    await interaction.followup.send(embed=embed, file=file)


if __name__ == "__main__":
    if not TOKEN:
        print("?? DISCORD_BOT_TOKEN ????")
    else:
        bot.run(TOKEN)
