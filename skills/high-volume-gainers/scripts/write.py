"""大成交涨幅排行写入飞书 Bitable。

从 stdin 读取 JSON 数组，每条记录包含：
  date, code, name, themes, avg_vol, gain, weighted_gain

查重逻辑：按 日期+股票代码 联合查重，已存在则跳过。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "shared"))
from feishu_utils import (
    load_config, get_token as _get_token, api, batch_create,
    existing_codes, verify_write,
)

cfg = load_config()
APP_TOKEN = cfg["app_token"]
TABLE_KEY = "high_volume_gainers"
TABLE_NAME = "大成交涨幅排行"
KEY_FIELDS = ["日期", "股票代码", "股票简称", "核心题材", "日均成交额(亿)", "涨幅(%)", "加权涨幅"]


def get_token():
    return _get_token(cfg)


def get_or_create_table(token):
    """获取或创建表格，返回 table_id。"""
    # 检查配置
    tid = cfg["tables"].get(TABLE_KEY)
    if tid:
        return tid

    # 按名称查找
    result = api("GET", "/tables", token, app_token=APP_TOKEN)
    for t in result.get("data", {}).get("items", []):
        if t.get("name") == TABLE_NAME:
            tid = t["table_id"]
            cfg["tables"][TABLE_KEY] = tid
            CFG_PATH = Path(__file__).resolve().parents[3] / "shared" / "feishu_config.json"
            CFG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
            return tid

    # 创建表格（带完整字段）
    fields = [
        {"field_name": "股票简称", "type": 1},
        {"field_name": "日期", "type": 1},
        {"field_name": "股票代码", "type": 1},
        {"field_name": "核心题材", "type": 1},
        {"field_name": "日均成交额(亿)", "type": 2},
        {"field_name": "涨幅(%)", "type": 2},
        {"field_name": "加权涨幅", "type": 2},
    ]
    body = {
        "table": {
            "name": TABLE_NAME,
            "fields": fields,
        }
    }
    result = api("POST", "/tables", token, body, app_token=APP_TOKEN)
    if result.get("code") != 0:
        print(f"创建表格失败: {result.get('msg', '')}", file=sys.stderr)
        sys.exit(1)

    tid = result.get("data", {}).get("table_id") or result.get("data", {}).get("table", {}).get("table_id")
    if not tid:
        print("创建表格失败: 未返回 table_id", file=sys.stderr)
        sys.exit(1)

    # 保存到配置
    cfg["tables"][TABLE_KEY] = tid
    CFG_PATH = Path(__file__).resolve().parents[3] / "shared" / "feishu_config.json"
    CFG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"表格已创建: {tid}")
    return tid


def main():
    try:
        records = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError) as e:
        print(f"stdin JSON 解析失败: {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(records, list) or not records:
        print("无数据需要写入")
        return

    required = {"date", "code", "name", "themes", "avg_vol", "gain", "weighted_gain"}
    for i, r in enumerate(records):
        missing = required - set(r.keys())
        if missing:
            print(f"记录 {i} 缺少字段: {missing}", file=sys.stderr)
            sys.exit(1)

    date_str = records[0]["date"]
    token = get_token()
    table_id = get_or_create_table(token)

    existing = existing_codes(token, table_id, date_str, app_token=APP_TOKEN)
    new_records = []
    for r in records:
        if r["code"] in existing:
            continue
        new_records.append({
            "fields": {
                "日期": r["date"],
                "股票代码": r["code"],
                "股票简称": r["name"],
                "核心题材": r["themes"],
                "日均成交额(亿)": r["avg_vol"],
                "涨幅(%)": r["gain"],
                "加权涨幅": r["weighted_gain"],
            }
        })

    if not new_records:
        print(f"日期 {date_str} 的所有记录已存在，跳过")
        return

    created = batch_create(token, table_id, new_records, app_token=APP_TOKEN, chunk_size=500)
    if created > 0:
        print(f"成功写入 {created} 条记录到 {TABLE_NAME} (table_id={table_id})")
    else:
        print("写入失败", file=sys.stderr)
        return

    verify_write(token, table_id, date_str, KEY_FIELDS, app_token=APP_TOKEN)


if __name__ == "__main__":
    main()
