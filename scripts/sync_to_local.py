"""飞书 → DuckDB 同步脚本。

从飞书 Bitable/Spreadsheet 读取数据，写入本地 DuckDB。
支持增量同步（只拉取 DuckDB 中不存在的日期）。

用法:
    python3 scripts/sync_to_local.py              # 全量同步
    python3 scripts/sync_to_local.py --incremental # 增量同步
"""
import sys
import json
import re
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from datetime import date as date_cls
from datetime import datetime, timedelta

# 项目路径
PROJECT_DIR = Path(__file__).parent.parent
DB_PATH = PROJECT_DIR / "db" / "market.duckdb"
SHARED_DIR = Path.home() / ".claude" / "shared"

sys.path.insert(0, str(SHARED_DIR))
from feishu_utils import load_config, get_token, fetch_all_records

import duckdb


def parse_pct(val):
    """解析百分比字符串，返回 float。'+' 和 '%' 自动去除。"""
    if val is None:
        return None
    s = str(val).strip().replace("+", "").replace("%", "").replace(",", "")
    if not s or s == "—" or s == "-":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_num(val):
    """解析数值，返回 float。"""
    if val is None:
        return None
    s = str(val).strip().replace(",", "").replace("亿", "")
    if not s or s == "—" or s == "-":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_int(val):
    """解析整数。"""
    if val is None:
        return None
    s = str(val).strip().replace(",", "")
    if not s or s == "—" or s == "-":
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


def parse_date(val):
    """解析飞书日期为 Python date。

    支持 YY-MM-DD、YYYY-MM-DD，以及 Spreadsheet 读出的 Excel serial number。
    """
    if not val:
        return None
    if isinstance(val, date_cls):
        return val
    if isinstance(val, (int, float)):
        return (datetime(1899, 12, 30) + timedelta(days=int(val))).date()
    s = str(val).strip()
    for fmt in ("%y-%m-%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def init_db():
    """初始化数据库，执行 schema.sql。"""
    con = duckdb.connect(str(DB_PATH))
    migrate_sector_schema_if_needed(con)
    schema_path = PROJECT_DIR / "db" / "schema.sql"
    con.execute(schema_path.read_text())
    con.close()
    print(f"数据库已初始化: {DB_PATH}")


def migrate_sector_schema_if_needed(con):
    """丢弃旧版板块镜像表；数据会在同步阶段从飞书重建。"""
    exists = con.execute("""
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_name = 'sector_marginal'
    """).fetchone()[0]
    if not exists:
        return
    cols = {
        row[1]
        for row in con.execute("PRAGMA table_info('sector_marginal')").fetchall()
    }
    if "ts_code" not in cols:
        con.execute("DROP TABLE IF EXISTS sector_marginal")
        con.execute("DROP TABLE IF EXISTS sector_dim")


def ensure_sector_tables(con):
    """重建板块相关表，确保主键使用 ts_code + date。"""
    con.execute("DROP TABLE IF EXISTS sector_marginal")
    con.execute("DROP TABLE IF EXISTS sector_dim")
    con.execute("""
        CREATE TABLE sector_dim (
            ts_code TEXT PRIMARY KEY,
            sector TEXT,
            first_seen_date DATE,
            last_seen_date DATE
        )
    """)
    con.execute("CREATE INDEX IF NOT EXISTS idx_sector_dim_sector ON sector_dim(sector)")
    con.execute("""
        CREATE TABLE sector_marginal (
            ts_code TEXT,
            sector TEXT,
            date DATE,
            diff_ratio DOUBLE,
            pct_chg DOUBLE,
            amount DOUBLE,
            PRIMARY KEY (ts_code, date)
        )
    """)
    con.execute("CREATE INDEX IF NOT EXISTS idx_sector_marginal_date ON sector_marginal(date)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_sector_marginal_ts_code ON sector_marginal(ts_code)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_sector_marginal_sector ON sector_marginal(sector)")


def sync_daily_market(con, token, cfg):
    """同步 每日指标 表。"""
    print("\n--- 同步 每日指标 ---")
    table_id = cfg["tables"]["daily"]
    records = fetch_all_records(token, table_id, app_token=cfg["app_token"])
    print(f"飞书记录数: {len(records)}")

    existing = con.execute("SELECT date FROM daily_market").fetchall()
    existing_dates = {r[0] for r in existing}

    rows = []
    for rec in records:
        f = rec["fields"]
        d = parse_date(f.get("日期"))
        if not d or d in existing_dates:
            continue
        rows.append((
            d,
            parse_num(f.get("成交额")),
            parse_pct(f.get("较昨日比")),
            parse_num(f.get("20日均")),
            parse_pct(f.get("相对量能比")),
            str(f.get("量能状态", "")),
            parse_int(f.get("涨停")),
            parse_int(f.get("跌停")),
            parse_num(f.get("周均线")),
            parse_pct(f.get("偏离度")),
            parse_pct(f.get("前三占比")),
            str(f.get("集中度", "")),
            str(f.get("行业1", "")),
            parse_pct(f.get("占比1")),
            str(f.get("行业2", "")),
            parse_pct(f.get("占比2")),
            str(f.get("行业3", "")),
            parse_pct(f.get("占比3")),
        ))

    if rows:
        con.executemany(
            "INSERT OR REPLACE INTO daily_market VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            rows,
        )
    print(f"新增 {len(rows)} 条")


def sync_advancers(con, token, cfg):
    """同步 涨家数走势 表。"""
    print("\n--- 同步 涨家数走势 ---")
    table_id = cfg["tables"]["chart"]
    records = fetch_all_records(token, table_id, app_token=cfg["app_token"])
    print(f"飞书记录数: {len(records)}")

    existing = con.execute("SELECT date FROM advancers").fetchall()
    existing_dates = {r[0] for r in existing}

    rows = []
    for rec in records:
        f = rec["fields"]
        d = parse_date(f.get("日期"))
        if not d or d in existing_dates:
            continue
        rows.append((
            d,
            parse_int(f.get("涨家数")),
            parse_num(f.get("MA5")),
        ))

    if rows:
        con.executemany(
            "INSERT OR REPLACE INTO advancers VALUES (?,?,?)",
            rows,
        )
    print(f"新增 {len(rows)} 条")


def sync_stocks(con, token, cfg):
    """同步 强势股 + 大成交 到 stocks 表。"""
    for source, key in [("top_gainers", "top_gainers"), ("high_volume", "high_volume_gainers")]:
        print(f"\n--- 同步 {source} ---")
        table_id = cfg["tables"][key]
        records = fetch_all_records(token, table_id, app_token=cfg["app_token"])
        print(f"飞书记录数: {len(records)}")

        rows = []
        for rec in records:
            f = rec["fields"]
            # 日期可能是区间 "YY-MM-DD~YY-MM-DD"
            date_str = str(f.get("日期", ""))
            if "~" in date_str:
                parts = date_str.split("~")
                start_d = parse_date(parts[0])
                end_d = parse_date(parts[1])
            else:
                start_d = end_d = parse_date(date_str)

            # 查重: 按代码+起始日期
            if start_d:
                dup = con.execute(
                    "SELECT 1 FROM stocks WHERE stock_code=? AND start_date=? AND source=? LIMIT 1",
                    [str(f.get("股票代码", "")), start_d, source],
                ).fetchone()
                if dup:
                    continue

            rows.append((
                str(f.get("股票代码", "")),
                str(f.get("股票简称", "")),
                str(f.get("申万行业", "")),
                str(f.get("核心题材", "")),
                start_d,
                end_d,
                parse_pct(f.get("区间涨幅") or f.get("涨幅(%)")),
                parse_num(f.get("日均成交额(亿)")),
                parse_num(f.get("加权涨幅")),
                parse_num(f.get("UP")),
                parse_pct(f.get("偏离度")),
                source,
            ))

        if rows:
            con.executemany(
                "INSERT INTO stocks (stock_code, stock_name, industry, themes, "
                "start_date, end_date, gain_pct, avg_volume, weighted_gain, "
                "up_value, deviation, source) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                rows,
            )
        print(f"新增 {len(rows)} 条")


def sync_sector_marginal(con, token, cfg):
    """同步 板块边际量 (Spreadsheet)。

    飞书 Spreadsheet 的结构: A列=板块名，后续每列=一个交易日。
    第1行=日期头，第2-228行=diff_ratio。
    """
    print("\n--- 同步 板块边际量 ---")
    sheet_token = cfg["tables"]["sector_marginal_sheet"]

    # Spreadsheet API 获取数据
    url = f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{sheet_token}/values/{sheet_token}"
    headers = {"Authorization": f"Bearer {token}"}
    import urllib.request

    # 先获取 spreadsheet 的 sheet 信息
    meta_url = f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{sheet_token}/metainfo"
    req = urllib.request.Request(meta_url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        meta = json.loads(resp.read())

    sheets = meta.get("data", {}).get("sheets", [])
    if not sheets:
        print("未找到 sheet")
        return

    sheet_id = sheets[0].get("sheetId") or sheets[0].get("sheet_id") or "e8a204"

    # Bitable sector_daily 保存同一日期的涨幅和成交额；Spreadsheet 只保存边际量。
    # 回测需要 pct_chg 构建板块收益序列，所以这里合并两边的飞书数据。
    daily_metrics, daily_sector_names = fetch_sector_daily_metrics(token, cfg)

    # 分批读取，每次最多 10 列（避免超限）
    # 先读第一行获取总列数和日期头
    range_header = f"{sheet_id}!A1:ZZ1"
    val_url = f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{sheet_token}/values/{range_header}"
    req = urllib.request.Request(val_url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        result = json.loads(resp.read())
    if result.get("code") != 0:
        print(f"读取 Spreadsheet 头失败: {result.get('msg')}")
        return
    header_row = result.get("data", {}).get("valueRange", {}).get("values", [[]])[0]

    # 读取板块名（A列）
    range_sectors = f"{sheet_id}!A2:A300"
    val_url = f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{sheet_token}/values/{range_sectors}"
    req = urllib.request.Request(val_url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        result = json.loads(resp.read())
    sector_data = result.get("data", {}).get("valueRange", {}).get("values", [])
    sectors = [str(row[0]).strip() for row in sector_data if row and row[0]]
    sectors = disambiguate_sector_names(sectors, daily_sector_names)

    # 分批读取数据列（每批 5 列 × 228 行）
    col_letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    def col_name(idx):
        if idx < 26:
            return col_letters[idx]
        return col_letters[idx // 26 - 1] + col_letters[idx % 26]

    rows = []
    batch_size = 5
    total_cols = 0
    for idx, header in enumerate(header_row):
        if header not in ("", None):
            total_cols = idx + 1
    date_headers = [
        parse_date(header_row[idx])
        for idx in range(1, total_cols)
        if parse_date(header_row[idx])
    ]
    sector_codes = fetch_sector_code_map(date_headers, sectors)
    for start_col in range(1, total_cols, batch_size):
        end_col = min(start_col + batch_size - 1, total_cols - 1)
        col_start = col_name(start_col)
        col_end = col_name(end_col)
        range_str = f"{sheet_id}!{col_start}1:{col_end}{len(sectors) + 1}"
        val_url = f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{sheet_token}/values/{range_str}"
        req = urllib.request.Request(val_url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read())
        except Exception as e:
            print(f"  读取列 {col_start}-{col_end} 失败: {e}")
            continue
        if result.get("code") != 0:
            print(f"  读取列 {col_start}-{col_end} 失败: {result.get('msg')}")
            continue

        batch_data = result.get("data", {}).get("valueRange", {}).get("values", [])
        if not batch_data:
            continue

        for batch_col in range(len(batch_data[0]) if batch_data else []):
            actual_col = start_col + batch_col
            date_val = parse_date(header_row[actual_col]) if actual_col < len(header_row) else None
            if not date_val:
                continue
            for row_idx in range(len(sectors)):
                data_row = row_idx + 1  # batch_data 第0行是日期头
                if data_row >= len(batch_data):
                    break
                if batch_col >= len(batch_data[data_row]):
                    continue
                val = batch_data[data_row][batch_col]
                diff = parse_pct(val)
                if diff is None:
                    continue
                sector = sectors[row_idx]
                ts_code = sector_codes.get(sector)
                if not ts_code:
                    raise ValueError(f"未找到板块代码: {sector}")
                metrics = daily_metrics.get((sector, date_val), {})
                rows.append((
                    ts_code,
                    sector,
                    date_val,
                    diff,
                    metrics.get("pct_chg"),
                    metrics.get("amount"),
                ))

    if rows:
        # 先删后插，保证幂等
        con.execute("DELETE FROM sector_marginal")
        con.execute("DELETE FROM sector_dim")
        dim_rows = []
        for ts_code, sector in sorted({(r[0], r[1]) for r in rows}):
            dates = [r[2] for r in rows if r[0] == ts_code]
            dim_rows.append((ts_code, sector, min(dates), max(dates)))
        con.executemany(
            "INSERT INTO sector_dim (ts_code, sector, first_seen_date, last_seen_date) VALUES (?,?,?,?)",
            dim_rows,
        )
        con.executemany(
            "INSERT INTO sector_marginal (ts_code, sector, date, diff_ratio, pct_chg, amount) VALUES (?,?,?,?,?,?)",
            rows,
        )
    print(f"同步 {len(rows)} 条板块边际量记录，{len(set(r[0] for r in rows))} 个板块代码")


def fetch_sector_daily_metrics(token, cfg):
    """从 Bitable sector_daily 读取 {(sector, date): {pct_chg, amount}} 和板块顺序。"""
    table_id = cfg["tables"]["sector_daily"]
    records = fetch_all_records(token, table_id, app_token=cfg["app_token"])
    metrics = {}
    sector_names = []
    for rec in records:
        fields = rec["fields"]
        sector = str(fields.get("板块", "")).strip()
        if not sector:
            continue
        sector_names.append(sector)
        for field_name, value in fields.items():
            if field_name == "板块":
                continue
            if field_name.endswith("涨幅"):
                d = parse_date(field_name[:-2])
                if d:
                    metrics.setdefault((sector, d), {})["pct_chg"] = parse_pct(value)
            elif field_name.endswith("成交额"):
                d = parse_date(field_name[:-3])
                if d:
                    metrics.setdefault((sector, d), {})["amount"] = parse_num(value)
    print(f"  sector_daily 指标: {len(metrics)} 个 sector-date")
    return metrics, sector_names


def disambiguate_sector_names(sectors, reference_names):
    """Use Bitable names to disambiguate duplicate Spreadsheet sector names."""
    seen = {}
    result = []
    for idx, name in enumerate(sectors):
        seen[name] = seen.get(name, 0) + 1
        fixed = name
        if seen[name] > 1 and idx < len(reference_names):
            ref = reference_names[idx]
            if ref == name or ref.startswith(f"{name}("):
                fixed = ref
        result.append(fixed)
    return result


def canonical_sector_name(sector):
    """去掉用于去重的代码后缀，得到 fupanhui 原始板块名。"""
    return re.sub(r"\(\d{6}\)$", "", sector).strip()


def code_from_sector_suffix(sector):
    """从 小金属(885552) 这类名称中提取 ts_code。"""
    m = re.search(r"\((\d{6})\)$", sector)
    if not m:
        return None
    return f"{m.group(1)}.TI"


def fupanhui_get_json(url, retries=4):
    last_err = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=25) as resp:
                return json.loads(resp.read())
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as e:
            last_err = e
            time_sleep = 0.5 * (attempt + 1)
            import time
            time.sleep(time_sleep)
    raise RuntimeError(f"fupanhui 请求失败: {url} ({last_err})")


def fetch_sector_code_map(dates, sectors):
    """按日期从 fupanhui 获取板块代码，返回 {display_sector: ts_code}。"""
    needed_names = {canonical_sector_name(s) for s in sectors}
    name_to_codes = {}
    for d in sorted(set(dates)):
        query = urllib.parse.urlencode({"trade_date": d.strftime("%Y-%m-%d"), "mode": "auto"})
        url = f"https://fupanhui.com/api/v1/client/reviews/sectors/search?{query}"
        data = fupanhui_get_json(url)
        items = data.get("data", {}).get("sectors") or data.get("data", {}).get("data") or []
        for item in items:
            name = str(item.get("name", "")).strip()
            code = item.get("ts_code")
            if name in needed_names and code:
                codes = name_to_codes.setdefault(name, [])
                if code not in codes:
                    codes.append(code)
        if needed_names.issubset(name_to_codes.keys()):
            multi_needed = [
                s for s in sectors
                if code_from_sector_suffix(s) and code_from_sector_suffix(s) not in name_to_codes.get(canonical_sector_name(s), [])
            ]
            if not multi_needed:
                break

    result = {}
    used_codes = set()
    for sector in sectors:
        suffix_code = code_from_sector_suffix(sector)
        base = canonical_sector_name(sector)
        codes = name_to_codes.get(base, [])
        if suffix_code:
            result[sector] = suffix_code
            used_codes.add(suffix_code)
        elif len(codes) == 1:
            result[sector] = codes[0]
            used_codes.add(codes[0])
        else:
            unused = [code for code in codes if code not in used_codes]
            if unused:
                result[sector] = unused[0]
                used_codes.add(unused[0])

    missing = [sector for sector in sectors if sector not in result]
    if missing:
        raise ValueError(f"未能映射 ts_code: {missing[:20]}")
    return result


def reset_local_tables(con):
    """全量同步前清空本地镜像表，确保 DuckDB 和飞书一致。"""
    for table in ["daily_market", "advancers", "stocks", "sector_marginal", "sector_dim"]:
        con.execute(f"DELETE FROM {table}")


def validate_local_db(con):
    """打印关键数据质量摘要，回测前快速发现半同步或缺字段。"""
    print("\n--- 数据质量检查 ---")

    for table in ["daily_market", "advancers", "stocks", "sector_dim", "sector_marginal"]:
        count = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table}: {count} 条")

    dup = con.execute("""
        SELECT COUNT(*) FROM (
            SELECT ts_code, date, COUNT(*) AS c
            FROM sector_marginal
            GROUP BY ts_code, date
            HAVING COUNT(*) > 1
        )
    """).fetchone()[0]
    print(f"  sector_marginal 重复主键: {dup}")

    coverage = con.execute("""
        SELECT COUNT(*) AS total,
               COUNT(diff_ratio) AS diff_nonnull,
               COUNT(pct_chg) AS pct_nonnull,
               COUNT(amount) AS amount_nonnull,
               COUNT(DISTINCT date) AS dates,
               COUNT(DISTINCT ts_code) AS sectors,
               MIN(date) AS min_date,
               MAX(date) AS max_date
        FROM sector_marginal
    """).fetchone()
    print(
        "  sector_marginal 覆盖: "
        f"rows={coverage[0]} diff={coverage[1]} pct={coverage[2]} amount={coverage[3]} "
        f"dates={coverage[4]} sectors={coverage[5]} range={coverage[6]}~{coverage[7]}"
    )

    missing = con.execute("""
        SELECT date,
               COUNT(*) AS rows,
               SUM(CASE WHEN pct_chg IS NULL THEN 1 ELSE 0 END) AS missing_pct,
               SUM(CASE WHEN amount IS NULL THEN 1 ELSE 0 END) AS missing_amount
        FROM sector_marginal
        GROUP BY date
        HAVING missing_pct > 0 OR missing_amount > 0
        ORDER BY date DESC
        LIMIT 8
    """).fetchall()
    if missing:
        print("  pct_chg/amount 缺失日期 TOP:")
        for row in missing:
            print(f"    {row[0]} rows={row[1]} missing_pct={row[2]} missing_amount={row[3]}")
    else:
        print("  pct_chg/amount 无缺失")


def main():
    incremental = "--incremental" in sys.argv

    if not DB_PATH.parent.exists():
        DB_PATH.parent.mkdir(parents=True)

    init_db()
    con = duckdb.connect(str(DB_PATH))

    cfg = load_config()
    token = get_token(cfg)

    try:
        con.execute("BEGIN TRANSACTION")
        if incremental:
            print("同步模式: 增量")
        else:
            print("同步模式: 全量镜像")
            ensure_sector_tables(con)
            reset_local_tables(con)

        sync_daily_market(con, token, cfg)
        sync_advancers(con, token, cfg)
        sync_stocks(con, token, cfg)
        sync_sector_marginal(con, token, cfg)
        validate_local_db(con)
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        con.close()
        raise

    con.close()
    print("\n同步完成!")


if __name__ == "__main__":
    main()
