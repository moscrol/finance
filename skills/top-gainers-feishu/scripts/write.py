"""将筛选后的强势股数据写入飞书 Bitable。

从 stdin 读取 JSON 数组，每条记录包含：
  date, code, name, industry, themes, gain, industry_hot(bool)

查重逻辑：按 日期+股票代码 联合查重，已存在则跳过。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "shared"))
from feishu_utils import (
    load_config, get_token as _get_token, batch_create,
    existing_codes, verify_write,
)

cfg = load_config()
APP_TOKEN = cfg["app_token"]
TABLE_ID = cfg["tables"]["top_gainers"]
KEY_FIELDS = ["日期", "股票代码", "股票简称", "申万行业", "核心题材", "区间涨幅"]


def get_token():
    return _get_token(cfg)


def main():
    try:
        records = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError) as e:
        print(f"stdin JSON 解析失败: {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(records, list) or not records:
        print("无数据需要写入")
        return

    # 校验必要字段
    required = {"date", "code", "name", "industry", "themes", "gain"}
    for i, r in enumerate(records):
        missing = required - set(r.keys())
        if missing:
            print(f"记录 {i} 缺少字段: {missing}", file=sys.stderr)
            sys.exit(1)

    date_str = records[0]["date"]
    token = get_token()

    existing = existing_codes(token, TABLE_ID, date_str, app_token=APP_TOKEN)
    new_records = []
    for r in records:
        if r["code"] in existing:
            continue
        new_records.append({
            "fields": {
                "日期": r["date"],
                "股票代码": r["code"],
                "股票简称": r["name"],
                "申万行业": r["industry"],
                "核心题材": r["themes"],
                "区间涨幅": r["gain"],
                "行业涨幅上榜": r.get("industry_hot", False),
            }
        })

    if not new_records:
        print(f"日期 {date_str} 的所有记录已存在，跳过")
        return

    created = batch_create(token, TABLE_ID, new_records, app_token=APP_TOKEN, chunk_size=500)
    if created > 0:
        print(f"成功写入 {created} 条记录")
    else:
        print("写入失败", file=sys.stderr)
        return

    verify_write(token, TABLE_ID, date_str, KEY_FIELDS, app_token=APP_TOKEN)


if __name__ == "__main__":
    main()
