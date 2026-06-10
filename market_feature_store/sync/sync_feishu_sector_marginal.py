"""同步飞书「板块边际量」电子表格 -> fact_sector_daily.diff_ratio (历史回填)。

数据源: 飞书 Spreadsheet (sector_marginal_sheet), 与 Bitable 不同, 走 sheets/v2 API。
结构: A列=板块名; 第1行=日期表头(每列一个交易日); 第2行起=各板块当日 diff_ratio(边际量)。

关键: 表头日期格式混乱(部分是 Excel 序列号如 46027, 部分是 '26-01-06' 字符串),
且列顺序不保证按日期排列。因此按「每列表头解析出的真实日期」入库, 绝不依赖列位置。

只回填 diff_ratio (边际量); 不覆盖已有的 pct_chg / amount (来自复盘会 fact_sector_daily)。
"""
from __future__ import annotations

import json
import sys
import urllib.request
from datetime import date as date_cls
from datetime import datetime, timedelta

from ..db import connect, init_db, PROJECT_DIR

sys.path.insert(0, str(PROJECT_DIR / "shared"))
from feishu_utils import load_config, get_token  # noqa: E402

_COL_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _col_name(idx: int) -> str:
    """0-based 列序号 -> 电子表格列字母 (A, B, ..., Z, AA, AB, ...)。"""
    if idx < 26:
        return _COL_LETTERS[idx]
    return _COL_LETTERS[idx // 26 - 1] + _COL_LETTERS[idx % 26]


def _parse_date(val):
    """飞书表头日期 -> date。支持 Excel 序列号 / 'YY-MM-DD' / 'YYYY-MM-DD'。"""
    if val in ("", None):
        return None
    if isinstance(val, date_cls):
        return val
    if isinstance(val, (int, float)):
        return (datetime(1899, 12, 30) + timedelta(days=int(val))).date()
    s = str(val).strip()
    for fmt in ("%y-%m-%d", "%Y-%m-%d", "%Y/%m/%d", "%y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def _parse_pct(val):
    """解析 diff_ratio 单元格 -> float。去除 '+' '%' ','; '—'/'-'/空 视为 None。"""
    if val in ("", None):
        return None
    s = str(val).strip().replace("+", "").replace("%", "").replace(",", "")
    if not s or s in ("—", "-"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _code_from_suffix(name: str):
    """从 '小金属(885552)' 提取 ts_code -> '885552.TI'。"""
    import re

    m = re.search(r"\((\d{6})\)$", name)
    return f"{m.group(1)}.TI" if m else None


def _canonical(name: str) -> str:
    import re

    return re.sub(r"\(\d{6}\)$", "", name).strip()


def _sheets_get(token: str, sheet_token: str, rng: str):
    url = (f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/"
           f"{sheet_token}/values/{rng}")
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read())
    if result.get("code") != 0:
        raise RuntimeError(f"读取 {rng} 失败: {result.get('msg')}")
    return result.get("data", {}).get("valueRange", {}).get("values", [])


def _get_sheet_id(token: str, sheet_token: str) -> str:
    url = (f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/"
           f"{sheet_token}/metainfo")
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        meta = json.loads(resp.read())
    sheets = meta.get("data", {}).get("sheets", [])
    if not sheets:
        raise RuntimeError("电子表格无 sheet")
    return sheets[0].get("sheetId") or sheets[0].get("sheet_id")


def _build_code_map(con, sheet_sectors: list[str]) -> tuple[dict, dict, list[str]]:
    """板块名 -> ts_code。返回 (name->ts_code, ts_code->sw_l1, 未匹配名单)。

    优先级: 名称带 (代码) 后缀 > dim_sector 唯一同名 > dim_sector 同名按出现顺序分配未用代码。
    """
    rows = con.execute(
        "SELECT sector_ts_code, sector_name, sw_l1 FROM dim_sector"
    ).fetchall()
    sw_by_code = {r[0]: r[2] for r in rows}
    codes_by_name: dict[str, list[str]] = {}
    for ts_code, name, _ in rows:
        codes_by_name.setdefault(name, []).append(ts_code)

    name_to_code: dict[str, str] = {}
    used: set[str] = set()
    unmatched: list[str] = []
    for sec in sheet_sectors:
        suffix = _code_from_suffix(sec)
        if suffix:
            name_to_code[sec] = suffix
            used.add(suffix)
            if suffix not in sw_by_code:
                sw_by_code[suffix] = None
            continue
        base = _canonical(sec)
        candidates = codes_by_name.get(base, [])
        if len(candidates) == 1:
            name_to_code[sec] = candidates[0]
            used.add(candidates[0])
        elif len(candidates) > 1:
            unused = [c for c in candidates if c not in used]
            if unused:
                name_to_code[sec] = unused[0]
                used.add(unused[0])
            else:
                unmatched.append(sec)
        else:
            unmatched.append(sec)
    return name_to_code, sw_by_code, unmatched


def sync_sector_marginal(batch_cols: int = 20) -> dict:
    """从飞书电子表格回填 fact_sector_daily 的 diff_ratio (边际量)。"""
    import pandas as pd

    cfg = load_config()
    token = get_token(cfg)
    sheet_token = cfg["tables"]["sector_marginal_sheet"]
    sheet_id = _get_sheet_id(token, sheet_token)

    init_db()
    con = connect()
    try:
        # 1) 表头 -> 每列日期 (按解析结果, 不靠列位置)
        header = _sheets_get(token, sheet_token, f"{sheet_id}!A1:CZ1")
        header = header[0] if header else []
        total_cols = 0
        for idx, h in enumerate(header):
            if h not in ("", None):
                total_cols = idx + 1
        col_date: dict[int, date_cls] = {}
        bad_headers: list = []
        for idx in range(1, total_cols):
            d = _parse_date(header[idx]) if idx < len(header) else None
            if d:
                col_date[idx] = d
            elif header[idx] not in ("", None):
                bad_headers.append((idx, header[idx]))

        # 2) A列板块名 (按行顺序)
        a_col = _sheets_get(token, sheet_token, f"{sheet_id}!A2:A300")
        sectors = [str(r[0]).strip() for r in a_col if r and r[0]
                   and str(r[0]).strip() != "板块"]
        n_sectors = len(sectors)

        name_to_code, sw_by_code, unmatched = _build_code_map(con, sectors)

        # 3) 分批读数据列, 组装 (date, ts_code, name, sw_l1, diff_ratio)
        recs: list[tuple] = []
        now = datetime.now()
        cells_seen = 0
        for start in range(1, total_cols, batch_cols):
            end = min(start + batch_cols - 1, total_cols - 1)
            rng = f"{sheet_id}!{_col_name(start)}1:{_col_name(end)}{n_sectors + 1}"
            data = _sheets_get(token, sheet_token, rng)
            if not data:
                continue
            for bc in range(end - start + 1):
                acol = start + bc
                d = col_date.get(acol)
                if not d:
                    continue
                for ri in range(n_sectors):
                    drow = ri + 1  # data[0] 是表头行
                    if drow >= len(data) or bc >= len(data[drow]):
                        continue
                    diff = _parse_pct(data[drow][bc])
                    if diff is None:
                        continue
                    sec = sectors[ri]
                    ts_code = name_to_code.get(sec)
                    if not ts_code:
                        continue
                    cells_seen += 1
                    recs.append((d.isoformat(), ts_code, _canonical(sec),
                                 sw_by_code.get(ts_code), diff, "feishu:sector_marginal", now))

        # 4) bulk upsert (只写 diff_ratio, 不动 pct_chg/amount)
        written = 0
        if recs:
            _buf_df = pd.DataFrame(recs, columns=[  # noqa: F841
                "trade_date", "sector_ts_code", "sector_name", "sw_l1",
                "diff_ratio", "source", "updated_at"])
            con.register("_buf_df", _buf_df)
            try:
                con.execute("""
                    INSERT INTO fact_sector_daily
                        (trade_date, sector_ts_code, sector_name, sw_l1, diff_ratio, source, updated_at)
                    SELECT trade_date, sector_ts_code, sector_name, sw_l1, diff_ratio, source, updated_at
                    FROM _buf_df
                    ON CONFLICT (trade_date, sector_ts_code) DO UPDATE SET
                        diff_ratio = EXCLUDED.diff_ratio,
                        sector_name = EXCLUDED.sector_name,
                        sw_l1 = COALESCE(fact_sector_daily.sw_l1, EXCLUDED.sw_l1),
                        updated_at = EXCLUDED.updated_at
                """)
            finally:
                con.unregister("_buf_df")
            written = len(recs)

        agg = con.execute(
            "SELECT COUNT(*), COUNT(DISTINCT trade_date), COUNT(DISTINCT sector_ts_code),"
            " MIN(trade_date), MAX(trade_date),"
            " SUM(CASE WHEN diff_ratio IS NULL THEN 1 ELSE 0 END)"
            " FROM fact_sector_daily"
        ).fetchone()
        sheet_dates = sorted({d for d in col_date.values()})
    finally:
        con.close()

    return {
        "sheet_token": sheet_token,
        "sheet_id": sheet_id,
        "date_cols": len(col_date),
        "sheet_date_min": str(sheet_dates[0]) if sheet_dates else None,
        "sheet_date_max": str(sheet_dates[-1]) if sheet_dates else None,
        "bad_headers": bad_headers,
        "sectors": n_sectors,
        "unmatched_sectors": unmatched,
        "rows_written": written,
        "table_total": agg[0],
        "table_dates": agg[1],
        "table_sectors": agg[2],
        "table_date_min": str(agg[3]) if agg[3] else None,
        "table_date_max": str(agg[4]) if agg[4] else None,
        "table_null_diff": agg[5] or 0,
    }
