"""从飞书 Bitable 提取涨家数，写入独立表格供飞书图表视图使用，本地生成 PNG"""
import sys
import json
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "shared"))
from feishu_utils import (
    load_config, get_token as _get_token, fetch_all_records,
    api, batch_create, parse_date_str,
)

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd

cfg = load_config()
APP_TOKEN = cfg["app_token"]
DAILY_TABLE = cfg["tables"]["daily"]
CHART_TABLE = cfg["tables"]["chart"]

plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'PingFang SC', 'Heiti TC', 'STHeiti']
plt.rcParams['axes.unicode_minus'] = False


def get_token():
    return _get_token(cfg)


def parse_daily_to_df(items):
    """提取日期和涨家数，返回排序后的 DataFrame"""
    records = []
    for item in items:
        fields = item.get("fields", {})
        date_str = fields.get("日期", "")
        adv = fields.get("涨", "")
        if date_str and adv:
            try:
                dt = parse_date_str(date_str)
                records.append({"日期": dt, "涨家数": int(adv)})
            except (ValueError, TypeError):
                continue
    df = pd.DataFrame(records).sort_values("日期").reset_index(drop=True)
    df["MA5"] = df["涨家数"].rolling(5, min_periods=1).mean().round(2)
    return df


def sync_to_chart_table(token, df):
    """增量同步数据到涨家数走势表格"""
    existing = fetch_all_records(token, CHART_TABLE, app_token=APP_TOKEN)
    existing_dates = set()
    existing_map = {}
    for item in existing:
        d = item.get("fields", {}).get("日期", "")
        if d:
            existing_dates.add(d)
            existing_map[d] = item["record_id"]

    # 新增记录
    new_records = []
    for _, row in df.iterrows():
        date_key = row["日期"].strftime("%y-%m-%d")
        if date_key not in existing_dates:
            new_records.append({
                "fields": {
                    "日期": date_key,
                    "涨家数": row["涨家数"],
                    "MA5": row["MA5"]
                }
            })

    if new_records:
        added = batch_create(token, CHART_TABLE, new_records, app_token=APP_TOKEN, chunk_size=500)
        print(f"新增 {added} 条记录到飞书图表表格")

    # 更新已有记录（MA5 可能因新增数据变化，只更新最近5条）
    updated = 0
    for _, row in df.tail(5).iterrows():
        date_key = row["日期"].strftime("%y-%m-%d")
        if date_key in existing_map:
            result = api("PUT", f"/records/{existing_map[date_key]}", token,
                         {"fields": {"MA5": row["MA5"]}},
                         table_id=CHART_TABLE, app_token=APP_TOKEN)
            if result.get("code") == 0:
                updated += 1

    if updated:
        print(f"更新 {updated} 条 MA5 数据")

    if not new_records and not updated:
        print("飞书图表数据已是最新")


def plot_chart(df, output_path):
    """绘制折线图"""
    width = min(max(14, len(df) * 0.12), 30)
    fig, ax = plt.subplots(figsize=(width, 6))

    ax.plot(df["日期"], df["涨家数"], color="#2196F3", linewidth=1.2, label="涨家数", alpha=0.85)
    ax.plot(df["日期"], df["MA5"], color="#F44336", linewidth=1.8, linestyle="--", label="5日均线")

    max_idx = df["涨家数"].idxmax()
    min_idx = df["涨家数"].idxmin()
    ax.annotate(f'{df.loc[max_idx, "涨家数"]}',
                xy=(df.loc[max_idx, "日期"], df.loc[max_idx, "涨家数"]),
                textcoords="offset points", xytext=(0, 10),
                fontsize=9, color="#1565C0", fontweight="bold", ha="center")
    ax.annotate(f'{df.loc[min_idx, "涨家数"]}',
                xy=(df.loc[min_idx, "日期"], df.loc[min_idx, "涨家数"]),
                textcoords="offset points", xytext=(0, -15),
                fontsize=9, color="#B71C1C", fontweight="bold", ha="center")

    # 参考线：涨跌平衡点（总股票数的一半，约 2500）
    ax.axhline(y=2500, color="gray", linewidth=0.5, linestyle=":", alpha=0.5)

    ax.set_title("A股 涨家数走势", fontsize=16, fontweight="bold", pad=15)
    ax.set_ylabel("涨家数", fontsize=12)
    ax.legend(loc="upper left", fontsize=10)
    ax.grid(True, alpha=0.3)

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    if len(df) > 30:
        ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()

    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"图表已保存: {output_path}")


def main():
    output_path = sys.argv[1] if len(sys.argv) > 1 else str(
        Path(__file__).resolve().parents[3] / "金融" / "涨家数走势.png"
    )

    print("获取飞书数据...")
    token = get_token()
    items = fetch_all_records(token, DAILY_TABLE, app_token=APP_TOKEN)
    print(f"共获取 {len(items)} 条记录")

    df = parse_daily_to_df(items)
    if df.empty:
        print("无有效数据")
        return
    print(f"解析到 {len(df)} 个交易日（{df['日期'].iloc[0].strftime('%Y-%m-%d')} ~ {df['日期'].iloc[-1].strftime('%Y-%m-%d')}）")

    sync_to_chart_table(token, df)
    plot_chart(df, output_path)


if __name__ == "__main__":
    main()
