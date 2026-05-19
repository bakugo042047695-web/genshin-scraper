# 使用 Microsoft 官方 Playwright Python 映像（已內建 Chromium binary）
FROM mcr.microsoft.com/playwright/python:v1.57.0-noble

WORKDIR /app

# 先安裝依賴（利用 Docker cache 層加速重建）
COPY requirements.txt .
RUN apt-get update && apt-get install -y fonts-noto-cjk && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt

# 複製核心程式
COPY genshin_scraper_original.py .
COPY api_server.py .
COPY discord_bot.py .
COPY daily_maintenance.py .
COPY generate_chart.py .
COPY start.sh .

# 複製 Tier List 與知識庫靜態設定檔
COPY genshin_tier_list.json .
COPY wutheringwaves_tier_list.json .
COPY hsr_tier_list.json .
COPY zzz_tier_list.json .
COPY nte_tier_list.json .
COPY market_knowledge_base.json .

# 確保腳本具備執行權限
RUN chmod +x start.sh

# 確保 Python 輸出不 buffer（log 即時顯示）
ENV PYTHONUNBUFFERED=1

# 設定伺服器時區為台灣時間 (UTC+8)
ENV TZ="Asia/Taipei"

# 入口點：gunicorn 起 api_server，api_server 內部 Popen 啟動爬蟲 + Discord bot
# GCP_KEY_PART_1/2/3 → 拼接後 base64 decode → gcp_key.json（由 api_server._setup_gcp_key 處理）
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT:-31422} --workers 1 --threads 4 --timeout 120 --preload api_server:app"]
