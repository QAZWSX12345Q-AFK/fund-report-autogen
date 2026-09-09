import akshare as ak
import pandas as pd
import json
import os
from datetime import datetime
from config import FUND_CONFIG

STATE_FILE = "state.json"

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    state = {}
    for code, cfg in FUND_CONFIG.items():
        state[code] = {
            "shares": cfg["initial_shares"],
            "last_date": None
        }
    return state

def save_state(state):
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

def get_latest_nav_info(code):
    try:
        df = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
        if df is None or len(df) == 0:
            return None
        latest = df.iloc[-1]
        return {
            "date": str(pd.to_datetime(latest['净值日期']).date()),
            "nav": float(latest['单位净值'])
        }
    except Exception as e:
        print(f"⚠️ 获取 {code} 失败: {e}")
        return None

def get_previous_nav(code):
    try:
        df = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
        if df is None or len(df) < 2:
            return None
        df = df.sort_values('净值日期', ascending=False).head(2)
        return float(df.iloc[1]['单位净值'])
    except Exception as e:
        print(f"⚠️ 获取 {code} 前日净值失败: {e}")
        return None

def update_shares(state, code, cfg, today_info):
    today_date = today_info['date']
    nav = today_info['nav']
    current = state[code]
    last_date = current.get("last_date")
    
    if last_date == today_date:
        return 0
    
    if cfg.get("paused", False):
        print(f"   ⏸️  {cfg['name']} 已暂停申购，今日不加份额")
        current["last_date"] = today_date
        return 0
    
    daily_amount = cfg["daily_invest"]
    added = daily_amount / nav
    current["shares"] += added
    current["last_date"] = today_date
    print(f"   ✅ 定投 {daily_amount}元，净值 {nav:.4f}，购入 {added:.4f} 份")
    return added

def generate_html_report(results, total_profit, total_value):
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>基金收益日报</title>
    <style>
        body {{ font-family: Arial, sans-serif; padding: 20px; background: #f5f5f5; }}
        .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; border-bottom: 3px solid #4CAF50; padding-bottom: 10px; }}
        .fund-item {{ border-bottom: 1px solid #eee; padding: 15px 0; }}
        .fund-name {{ font-size: 18px; font-weight: bold; color: #2196F3; }}
        .profit-positive {{ color: #e53935; }}
        .profit-negative {{ color: #43a047; }}
        .summary {{ background: #e8f5e9; padding: 15px; border-radius: 8px; margin-top: 20px; }}
        .summary h2 {{ margin: 5px 0; }}
        .nav-info {{ color: #666; font-size: 14px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 基金收益日报</h1>
        <p style="color: #888;">更新时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
"""
    for r in results:
        profit_class = "profit-positive" if r['profit'] >= 0 else "profit-negative"
        html += f"""
        <div class="fund-item">
            <div class="fund-name">【{r['name']}】({r['code']})</div>
            <div class="nav-info">持有份额: {r['shares']:.2f} | 最新净值: {r['latest_nav']:.4f} ({r['latest_date']}) | 前日净值: {r['prev_nav']:.4f}</div>
            <div style="margin-top:5px;">
                <span style="font-size:16px; font-weight:bold; class="{profit_class}">📈 今日收益: {r['profit']:+.2f} 元</span>
                <span style="margin-left:20px; color:#333;">💰 持仓市值: {r['market_value']:.2f} 元</span>
            </div>
        </div>
        """
    html += f"""
        <div class="summary">
            <h2>💰 今日总收益: <span class="{"profit-positive" if total_profit >= 0 else "profit-negative"}">{total_profit:+.2f} 元</span></h2>
            <h2>💵 账户总市值: {total_value:.2f} 元</h2>
        </div>
    </div>
</body>
</html>
"""
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

def main():
    print(f"\n{'='*55}")
    print(f"📊 基金收益日报（自动定投推算）")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*55}\n")
    
    state = load_state()
    total_profit = 0.0
    total_value = 0.0
    results = []
    
    for code, cfg in FUND_CONFIG.items():
        print(f"🔍 正在处理 {cfg['name']} ({code})...")
        
        today_info = get_latest_nav_info(code)
        if not today_info:
            print(f"   ❌ 获取净值失败，跳过\n")
            continue
        
        prev_nav = get_previous_nav(code)
        if prev_nav is None:
            print(f"   ❌ 获取前日净值失败，跳过\n")
            continue
        
        update_shares(state, code, cfg, today_info)
        
        shares = state[code]["shares"]
        latest_nav = today_info["nav"]
        daily_profit = (latest_nav - prev_nav) * shares
        market_value = latest_nav * shares
        
        total_profit += daily_profit
        total_value += market_value
        
        print(f"   📊 份额: {shares:.2f} | 净值: {latest_nav:.4f} | 前日: {prev_nav:.4f}")
        print(f"   📈 今日收益: {daily_profit:+.2f} 元 | 市值: {market_value:.2f} 元")
        print("-" * 40)
        
        results.append({
            "code": code,
            "name": cfg['name'],
            "shares": shares,
            "latest_nav": latest_nav,
            "latest_date": today_info['date'],
            "prev_nav": prev_nav,
            "profit": daily_profit,
            "market_value": market_value
        })
    
    print(f"\n{'='*55}")
    print(f"💰 今日账户总收益: {total_profit:+.2f} 元")
    print(f"💵 账户总市值: {total_value:.2f} 元")
    print(f"{'='*55}\n")
    
    save_state(state)
    generate_html_report(results, total_profit, total_value)
    print("✅ 报告已生成: index.html")

if __name__ == "__main__":
    main()
