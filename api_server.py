import os
import json
import base64
import subprocess
import sys
from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient

app = Flask(__name__)
CORS(app)

MONGO_URI = os.environ.get("MONGODB_URI", "mongodb+srv://genshin:genshin123@cluster0.svtlvs0.mongodb.net/scraper_db?appName=Cluster0")

# ─── 啟動時解碼 GCP Key ───────────────────────────────────────────────────────
def _setup_gcp_key():
    """將 GCP_KEY_B64 env var 解碼成 gcp_key.json，讓爬蟲直接讀檔案（最穩定）"""
    b64 = os.environ.get("GCP_KEY_B64", "").strip()
    if not b64:
        print("[API] GCP_KEY_B64 not set, skipping gcp_key.json write")
        return
    # 補回 Railway 可能截掉的 base64 padding
    b64 += "=" * ((-len(b64)) % 4)
    key_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gcp_key.json")
    try:
        decoded = base64.b64decode(b64).decode("utf-8")
        json.loads(decoded)  # 驗證 JSON 格式正確
        with open(key_path, "w", encoding="utf-8") as f:
            f.write(decoded)
        print(f"[API] gcp_key.json written OK ({len(decoded)} chars)")
    except Exception as e:
        print(f"[API] ERROR writing gcp_key.json: {e}")

_setup_gcp_key()

def get_db():
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    return client["scraper_db"]

# ─── Start background workers ───────────────────────────────────────────────
BASE = os.path.dirname(os.path.abspath(__file__))

def start_workers():
    """Start scraper and Discord bot as background subprocesses."""
    procs = []
    
    discord_path = os.path.join(BASE, "discord_bot.py")
    if os.path.exists(discord_path):
        p = subprocess.Popen([sys.executable, discord_path],
                             stdout=sys.stdout, stderr=sys.stderr)
        procs.append(("discord_bot", p))
        print(f"[API] Discord bot started (pid={p.pid})")
    
    scraper_path = os.path.join(BASE, "genshin_scraper_original.py")
    if os.path.exists(scraper_path):
        p = subprocess.Popen([sys.executable, scraper_path],
                             stdout=sys.stdout, stderr=sys.stderr)
        procs.append(("scraper", p))
        print(f"[API] Scraper started (pid={p.pid})")
    
    return procs

# ─── API routes ─────────────────────────────────────────────────────────────
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "alive"}), 200

@app.route('/api/targets', methods=['GET'])
def get_targets():
    try:
        db = get_db()
        targets = list(db["custom_targets"].find({}))
        # _id is the URL string, already serializable
        return jsonify({"status": "ok", "data": targets}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/targets', methods=['POST'])
def add_target():
    data = request.json
    if not data or 'url' not in data or 'target_price' not in data:
        return jsonify({"status": "error", "message": "Missing url or target_price"}), 400
    
    url = data['url']
    try:
        target_price = int(data['target_price'])
    except (ValueError, TypeError):
        return jsonify({"status": "error", "message": "target_price must be integer"}), 400
    
    title = data.get('title', 'Unknown Item')
    
    db = get_db()
    db["custom_targets"].update_one(
        {"_id": url},
        {"$set": {"target_price": target_price, "title": title, "alerted": False}},
        upsert=True
    )
    return jsonify({"status": "ok", "message": "Target saved"}), 200

@app.route('/api/targets/<path:url>', methods=['DELETE'])
def delete_target(url):
    db = get_db()
    db["custom_targets"].delete_one({"_id": url})
    return jsonify({"status": "ok"}), 200

# ─── Entry point ────────────────────────────────────────────────────────────
# Called at module level so gunicorn --preload also triggers it
_workers_started = False
def _ensure_workers():
    global _workers_started
    if not _workers_started:
        start_workers()
        _workers_started = True

_ensure_workers()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 31422))
    print(f"[API] Flask dev server on 0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, threaded=True)
