import os
import json
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta

def load_json(filepath):
    # 此處可能需要考慮 MongoDB！
    # 但因為這個腳本是跟著主程式運作的，我們可以讓主程式傳入 stats dict 而不是走 filepath
    pass

def generate_trend_chart(game_name, stats, output_path="trend_chart.png"):
    records = stats.get("records", [])
    if not records:
        return None
        
    df = pd.DataFrame(records)
    if 'date' not in df.columns or 'price' not in df.columns:
        return None
        
    # 過濾近30天
    thirty_days_ago = datetime.now() - timedelta(days=30)
    df['date'] = pd.to_datetime(df['date'])
    df = df[df['date'] >= thirty_days_ago]
    
    if df.empty:
        return None
        
    # Group by date
    daily = df.groupby('date').agg({
        'price': 'mean',
        'cp1': 'mean',
        'gold_char': 'mean'
    }).reset_index()
    
    # 決定字體，避免亂碼
    plt.rcParams['font.sans-serif'] = ['Noto Sans CJK JP', 'Noto Sans TC', 'Microsoft JhengHei', 'SimHei', 'Arial']
    plt.rcParams['axes.unicode_minus'] = False
    
    fig, ax1 = plt.subplots(figsize=(10, 6))
    
    # Plot Price on ax1
    color = 'tab:blue'
    ax1.set_xlabel('日期')
    ax1.set_ylabel('日均價 (TWD)', color=color)
    ax1.plot(daily['date'], daily['price'], color=color, marker='o', linewidth=2, label='均價')
    ax1.tick_params(axis='y', labelcolor=color)
    
    # Plot CP1 on ax2
    ax2 = ax1.twinx()
    color = 'tab:orange'
    ax2.set_ylabel('純角CP均值', color=color)
    ax2.plot(daily['date'], daily['cp1'], color=color, marker='s', linestyle='--', linewidth=2, label='純角CP')
    ax2.tick_params(axis='y', labelcolor=color)
    
    # Title and format
    plt.title(f"{game_name} - 近30天市場走勢圖", fontsize=16, fontweight='bold')
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    fig.autofmt_xdate()
    
    plt.grid(True, alpha=0.3)
    fig.tight_layout()
    plt.savefig(output_path, dpi=120)
    plt.close()
    
    return output_path
