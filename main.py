import akshare as ak
import pandas as pd
import json
import os
from datetime import datetime
from config import FUND_CONFIG

STATE_FILE = "state.json"

# ---------- 工具函数：使用 akshare 获取净值 ----------
def fetch_fund_nav_from_api(fund_code):
    """
    使用 akshare 库获取基金历史净值
    """
    try:
        df = ak.fund_open_fund_info_em(symbol=fund_code, indicator="单位净值走势")
        if df is None or df.empty:
            print(f"   ⚠️ 返回数据为空")
            return None
        
        # 按日期降序排列，取最新两条
        df = df.sort_values('净值日期', ascending=False)
        if len(df) < 2:
            print(f"   ⚠️ 数据不足，仅获取到 {len(df)} 条")
            return None
        
        nav_list = []
        for _, row in df.iterrows():
            nav_list.append({
                "date": row['净值日期'].strftime('%Y-%m-%d'),
                "nav": float(row['单位净值'])
            })
        return nav_list
    except Exception as e:
        print(f"   ⚠️ 使用 akshare 获取 {fund_code} 数据失败: {e}")
        return None

# ---------- 状态管理 ----------
def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    state = {}
    for code, cfg in FUND_CONFIG.items():
        state[code] = {
            "shares": cfg["initial_shares"],
            "last_date": None,
            "total_cost": cfg.get("initial_cost", 0.0)
        }
    return state

def save_state(state):
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

# ---------- 核心逻辑 ----------
def update_shares(state, code, cfg, latest_nav_info):
    today_date = latest_nav_info['date']
    nav = latest_nav_info['nav']
    current = state[code]
    last_date = current.get("last_date")

    if last_date == today_date:
        print(f"   ℹ️ 净值日期 {today_date} 未更新，今日不加份额")
        return 0

    if cfg.get("paused", False):
        print(f"   ⏸️  {cfg['name']} 已暂停申购，今日不加份额")
        current["last_date"] = today_date
        return 0

    daily_amount = cfg["daily_invest"]
    added = daily_amount / nav
    current["shares"] += added
    current["total_cost"] += daily_amount
    current["last_date"] = today_date
    print(f"   ✅ 定投 {daily_amount}元，净值 {nav:.4f}，购入 {added:.4f} 份")
    return added

def generate_html_report(results, total_profit, total_value, total_cost, total_accumulated_profit, total_accum_rate):
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
        accum_class = "profit-positive" if r['accum_profit'] >= 0 else "profit-negative"
        html += f"""
        <div class="fund-item">
            <div class="fund-name">【{r['name']}】({r['code']})</div>
            <div class="nav-info">持有份额: {r['shares']:.2f} | 最新净值: {r['latest_nav']:.4f} ({r['latest_date']}) | 前日净值: {r['prev_nav']:.4f}</div>
            <div style="margin-top:5px;">
                <span style="font-size:16px; font-weight:bold; class="{profit_class}">📈 今日收益: {r['profit']:+.2f} 元</span>
                <span style="margin-left:20px; color:#333;">💰 持仓市值: {r['market_value']:.2f} 元</span>
            </div>
            <div style="margin-top:5px;">
                <span style="font-size:14px; class="{accum_class}">📊 累计收益: {r['accum_profit']:+.2f} 元</span>
                <span style="margin-left:20px; color:#333;">📈 累计收益率: <span class="{accum_class}">{r['accum_rate']:+.2f}%</span></span>
                <span style="margin-left:20px; color:#666;">（本金: {r['total_cost']:.2f} 元）</span>
            </div>
        </div>
        """
    total_accum_class = "profit-positive" if total_accumulated_profit >= 0 else "profit-negative"
    html += f"""
        <div class="summary">
            <h2>💰 今日总收益: <span class="{"profit-positive" if total_profit >= 0 else "profit-negative"}">{total_profit:+.2f} 元</span></h2>
            <h2>📈 累计总收益: <span class="{total_accum_class}">{total_accumulated_profit:+.2f} 元</span></h2>
            <h2>📈 累计总收益率: <span class="{total_accum_class}">{total_accum_rate:+.2f}%</span></h2>
            <h2>💵 账户总市值: {total_value:.2f} 元</h2>
            <h2>💳 累计总本金: {total_cost:.2f} 元</h2>
        </div>
    </div>
</body>
</html>
"""
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

# ---------- 主程序 ----------
def main():
    print(f"\n{'='*55}")
    print(f"📊 基金收益日报（自动定投推算）")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*55}\n")

    state = load_state()
    total_profit = 0.0
    total_value = 0.0
    total_cost = 0.0
    results = []

    for code, cfg in FUND_CONFIG.items():
        print(f"🔍 正在处理 {cfg['name']} ({code})...")

        nav_data = fetch_fund_nav_from_api(code)
        if not nav_data or len(nav_data) < 2:
            print(f"   ❌ 获取净值数据失败（数据不足），跳过\n")
            continue

        latest = nav_data[0]
        previous = nav_data[1]
        latest_date = latest['date']
        latest_nav = latest['nav']
        prev_nav = previous['nav']

        print(f"   📅 最新净值日期: {latest_date}")
        print(f"   📊 最新净值: {latest_nav:.4f}, 前日净值: {prev_nav:.4f}")

        update_shares(state, code, cfg, {"date": latest_date, "nav": latest_nav})

        shares = state[code]["shares"]
        total_cost_fund = state[code]["total_cost"]
        daily_profit = (latest_nav - prev_nav) * shares
        market_value = latest_nav * shares
        accum_profit = market_value - total_cost_fund
        accum_rate = (accum_profit / total_cost_fund * 100) if total_cost_fund > 0 else 0.0

        total_profit += daily_profit
        total_value += market_value
        total_cost += total_cost_fund

        print(f"   📊 份额: {shares:.2f} | 市值: {market_value:.2f} 元")
        print(f"   📈 今日收益: {daily_profit:+.2f} 元")
        print(f"   📊 累计收益: {accum_profit:+.2f} 元 | 收益率: {accum_rate:+.2f}%")
        print("-" * 40)

        results.append({
            "code": code,
            "name": cfg['name'],
            "shares": shares,
            "latest_nav": latest_nav,
            "latest_date": latest_date,
            "prev_nav": prev_nav,
            "profit": daily_profit,
            "market_value": market_value,
            "total_cost": total_cost_fund,
            "accum_profit": accum_profit,
            "accum_rate": accum_rate
        })

    total_accumulated_profit = total_value - total_cost
    total_accum_rate = (total_accumulated_profit / total_cost * 100) if total_cost > 0 else 0.0

    print(f"\n{'='*55}")
    print(f"💰 今日账户总收益: {total_profit:+.2f} 元")
    print(f"📈 累计总收益: {total_accumulated_profit:+.2f} 元")
    print(f"📈 累计总收益率: {total_accum_rate:+.2f}%")
    print(f"💵 账户总市值: {total_value:.2f} 元")
    print(f"💳 累计总本金: {total_cost:.2f} 元")
    print(f"{'='*55}\n")

    save_state(state)
    generate_html_report(results, total_profit, total_value, total_cost, total_accumulated_profit, total_accum_rate)

    # 生成 nav_data.json 供 calculator.html 使用
    nav_json = {}
    for code, cfg in FUND_CONFIG.items():
        nav_data = fetch_fund_nav_from_api(code)
        if nav_data and len(nav_data) >= 2:
            nav_json[code] = {
                "name": cfg['name'],
                "latest_nav": nav_data[0]['nav'],
                "latest_date": nav_data[0]['date'],
                "prev_nav": nav_data[1]['nav']
            }
    with open("nav_data.json", "w", encoding="utf-8") as f:
        json.dump(nav_json, f, indent=2, ensure_ascii=False)
    print("✅ 净值数据已保存: nav_data.json")

    print("✅ 报告已生成: index.html")

if __name__ == "__main__":
    main()
