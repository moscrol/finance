"""东财主力资金净流入 → 补 local:stitch 行的 fund_flow_1d/5d → 题材资金面板本地重建。

背景：复盘会 2026-09-07 账号风控后，日更链路（plan=local）的
``fact_sector_stock_daily`` 改为 ``local:stitch``（identity=最近 fupanhui 名单 ×
value=当日东财真值），但拼接器只有行情真值、没有资金流，``fund_flow_1d/5d``
一直是 NULL，于是「板块篮子加总」兜底（sync_theme_capital_from_baskets）算不出
资金，``fact_theme_flow_daily``（题材资金表）停更在 2026-09-02。

复盘会题材资金面板的处理逻辑已用 09-02 留底数据核实：
  total_fund  = SUM(篮子内个股 fund_flow_1d)
  total_amount = SUM(amount)；stock_count = COUNT(*)
（煤炭面板 5.47/25.15/2 = 云煤能源+郑州煤电 两只逐值相加，误差 0.00。）
篮子本身是编辑部人工分组、原始个股清单未留底，还原不了；但「个股资金流 →
篮子求和」这层处理可以在自己的 403 板块篮子上等价重建——本模块补的就是
缺失的那个原料：个股主力资金净流入。

口径警示（不要跨源混算）：东财「主力净额」= 超大单+大单净流入（push2/push2his
tick 分类），与复盘会 fund_flow_1d 不是同一口径——09-02 同股对比：招金黄金
em 0.64亿 vs fph 2.21亿；中际旭创 em -30.66亿 vs fph -25.99亿。两种口径写同
一列，靠行级 source 区分（fupanhui 行是供应商值，local:stitch 行是东财值），
本模块**只填 source='local:stitch' 且 fund_flow_1d IS NULL 的行**，绝不覆盖
供应商值。跨 2026-09-02/03 边界做资金连续对比时必须按 source 分段。

两条取数路径：
1. snapshot（当日盘后）：push2delay clist 全市场翻页，字段 f12(代码)
   f62(今日主力净额,元) f164(5日主力净额,元)，秒级完成。与
   sync_eastmoney_stock_snapshot 同样的「最新快照」语义——必须盘后、且
   trade_date 必须就是快照所属交易日，否则会把别日的值写错日期；因此仅当
   trade_date == 上海时区今天时才允许走这条。
2. history（回补）：push2his 个股 fflow daykline，一只股一请求覆盖近 ~120 个
   交易日（一次拉全、多日共用）。

   本机网络陷阱（2026-09-11 实测，别再误判成限流）：本机 VPN/代理是 fake-IP
   模式，eastmoney 全部域名都被劫持到 198.18.x.x；代理对 push2delay/push2 放行，
   但对 **push2his 直接掐连接**——表现为 TCP 443 connect 成功、随即
   RemoteDisconnected、耗时 0.12s（不是超时，也不是 429）。当时误判为「IP 被
   限流、进了惩罚窗」，实际是本地代理规则。解法：用公共 DNS 拿真实 IP、直连
   该 IP，TLS SNI 仍填域名（curl --resolve 的等价物），实测 120 天 /0.07s 秒回。
   因此 history 路径走 _direct_get_json，不走 urllib 默认解析。2026-09-22 起劫持范围
   扩到 push2delay/push2（快照也中招、连挂两晚），这套绕法已上移到
   sync_eastmoney_stock_snapshot 供两条路径共用，本模块从那里导入。

单位统一亿（元 / 1e8），与 fupanhui 行同量纲。
"""
from __future__ import annotations

import json
import os
import random
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from ..db import connect, init_db
from .sync_eastmoney_stock_snapshot import (
    EM_FS,
    EM_PAGE_MAX,
    EM_URL,
    _direct_get_json,
    _get_json,
    _num,
)
from .sync_theme_capital_from_baskets import sync_from_sector_baskets

_SHANGHAI = ZoneInfo("Asia/Shanghai")

# 原始快照留底目录。先落原始再汇总：快照是易死数据（clist 只给「最新」，
# 下一个交易日一开盘就覆盖），而历史接口 push2his 从本机不可靠。只要原始留住，
# 后续计算/写库失败都能本地重放，不用再去求上游。
# 落在**数据根**而非代码树: 代码走发布快照会换目录, 留底不能跟着搬家。
RAW_DIR = Path(
    os.environ.get("FINANCE_DATA_ROOT", str(Path(__file__).resolve().parents[2]))
) / "market_snapshot" / "fund_flow"

# clist 快照的资金流字段: f12=代码 f62=今日主力净额(元) f164=5日主力净额(元)
FLOW_FIELDS = "f12,f62,f164"

FFLOW_HOST = "push2his.eastmoney.com"
# fields2: f51=日期 f52=主力净额 f53=小单 f54=中单 f55=大单 f56=超大单 (元)
FFLOW_PATH = (
    "/api/qt/stock/fflow/daykline/get?lmt=0&klt=101"
    "&fields1=f1,f2,f3,f7&fields2=f51,f52,f53,f54,f55,f56&secid={secid}"
)
STITCH_SOURCE = "local:stitch"


def _yi(value_yuan) -> float | None:
    if value_yuan is None:
        return None
    return round(float(value_yuan) / 1e8, 4)


def _secid(ts_code: str) -> str:
    """600519.SH -> 1.600519; 000001.SZ / 833171.BJ -> 0.xxxxxx。"""
    code, _, suffix = ts_code.partition(".")
    market = "1" if suffix.upper() == "SH" else "0"
    return f"{market}.{code}"


# ── 路径1: 全市场快照 (当日盘后) ──────────────────────────────


def fetch_flow_snapshot(page_size: int = EM_PAGE_MAX, timeout: float = 20.0,
                        sleep: float = 0.1) -> dict[str, tuple[float | None, float | None]]:
    """分页拉全市场当日主力净额快照。返回 {纯代码: (f62元, f164元)}。

    复用 sync_eastmoney_stock_snapshot 的分页/双 host/重试机制与 fs 过滤,
    只换 fields。fltt=2 保证十进制实值。
    """
    pz = max(1, min(page_size, EM_PAGE_MAX))
    out: dict[str, tuple[float | None, float | None]] = {}
    pn = 1
    total: int | None = None
    fetched = 0
    while pn <= 1000:
        url = (
            f"{EM_URL}?pn={pn}&pz={pz}&po=1&np=1&fltt=2&invt=2&fid=f62"
            f"&fs={EM_FS}&fields={FLOW_FIELDS}"
        )
        data = _get_json(url, timeout).get("data") or {}
        if total is None:
            total = int(data.get("total") or 0)
        diff = data.get("diff") or []
        if isinstance(diff, dict):
            diff = list(diff.values())
        if not diff:
            break
        fetched += len(diff)
        for it in diff:
            code = str(it.get("f12") or "").strip()
            if code:
                out[code] = (_num(it.get("f62")), _num(it.get("f164")))
        if total and fetched >= total:
            break
        pn += 1
        if sleep:
            time.sleep(sleep)
    return out


# 全市场实测 ~5900 只。低于此数说明上游截断/空响应，那不是数据而是故障。
MIN_RECORDS = 3000
# 收盘 15:00，再给上游结算留 30 分钟。早于此刻的快照只是盘中快照。
CLOSE_HHMM = (15, 30)


def _archive_status(trade_date: str, count: int, now_sh: datetime) -> str:
    """判定归档可用状态。

    - ``rejected``: 条数不足（空响应/截断），存证但**永不重放**。
    - ``provisional``: 归属日当天且尚未收盘结算，是盘中值，不能当终值固定下来。
    - ``final``: 收盘后或次日之后采集。
    """
    if count < MIN_RECORDS:
        return "rejected"
    if now_sh.date().isoformat() > trade_date:
        return "final"
    return "final" if (now_sh.hour, now_sh.minute) >= CLOSE_HHMM else "provisional"


def capture_raw_snapshot(trade_date: str, *, raw: dict | None = None,
                         out_dir: Path | None = None, inferred: bool = False) -> Path:
    """将当日资金快照原样落盘（含采集时刻/来源/口径/归属日推断依据/可用状态）。

    写的是**原始元**（不除 1e8），保留上游原貌；单位换算留给汇总环节，
    以免留底本身带上不可逆的加工。不合格的快照照写不误，但标 status 拦在
    重放之外——否则盘中值/空响应会被固定成永久输入。
    """
    raw = fetch_flow_snapshot() if raw is None else raw
    out_dir = out_dir or RAW_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{trade_date}.json"
    now_sh = datetime.now(_SHANGHAI)
    payload = {
        "trade_date": trade_date,
        "trade_date_inferred": inferred,
        "status": _archive_status(trade_date, len(raw), now_sh),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "fetched_at_shanghai": now_sh.isoformat(),
        "source": "eastmoney:push2delay:clist",
        "caliber": "em-main-net",
        "caliber_note": "主力净额=超大单+大单; 与复盘会 fund_flow_1d 不同口径, 不可相加",
        "unit": "yuan",
        "fields": {"f62": "当日主力净额", "f164": "5日主力净额"},
        "record_count": len(raw),
        "records": {c: {"f62": v[0], "f164": v[1]} for c, v in sorted(raw.items())},
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def load_raw_snapshot(trade_date: str, *, out_dir: Path | None = None) -> dict | None:
    """读回原始快照用于本地重放；无留底返回 None。

    **先校元数据再用值**：归属日/单位/口径任一对不上就报错。归属日是推断的
    （clist 不返回日期），重放时把推断当既成事实会把整份快照安到错的日子上，
    而这种错会安静地生成一整天看着合理的资金数。

    Returns: {"records": {code: (f62, f164)}, "meta": {...}}
    """
    path = (out_dir or RAW_DIR) / f"{trade_date}.json"
    if not path.exists():
        return None
    doc = json.loads(path.read_text(encoding="utf-8"))
    got_date = doc.get("trade_date")
    if got_date != trade_date:
        raise ValueError(f"留底归属日 {got_date!r} ≠ 请求 {trade_date!r}: {path}")
    if doc.get("unit") != "yuan":
        raise ValueError(f"留底单位 {doc.get('unit')!r} 非 yuan, 拒绝重放: {path}")
    if doc.get("caliber") != "em-main-net":
        raise ValueError(f"留底口径 {doc.get('caliber')!r} 不是东财主力净额: {path}")
    # 标签一致只证明没拿错文件，不证明内容合格。非 final 的归档不可重放：
    # 盘中快照会把 09:05 的 1 亿当成终值，空响应会把全市场填成零。
    count = int(doc.get("record_count") or 0)
    status = doc.get("status")
    if status is None:
        # 旧归档无此字段: 用已记录的采集时刻按**同一规则**推定, 不默认放行。
        fetched = doc.get("fetched_at_shanghai")
        if not fetched:
            raise ValueError(f"留底既无 status 也无采集时刻, 无法判定可用性: {path}")
        status = _archive_status(trade_date, count, datetime.fromisoformat(fetched))
    if status != "final":
        return None  # 盘中/不合格: 交给调用方重新采集并覆盖
    records = {
        c: (v.get("f62"), v.get("f164")) for c, v in (doc.get("records") or {}).items()
    }
    meta = {k: v for k, v in doc.items() if k != "records"}
    return {"records": records, "meta": meta}


# ── 路径2: 个股 fflow daykline (历史回补) ─────────────────────


def fetch_flow_history(ts_code: str, timeout: float = 15.0, retries: int = 5) -> dict[str, float]:
    """单股近 ~120 交易日主力净额序列。返回 {YYYY-MM-DD: 主力净额元}。

    走直连真实 IP (见模块头「本机网络陷阱」); 仍失败则指数退避重试,
    重试耗尽抛最后一个异常, 由调用方计失败、下轮续跑。
    """
    secid = _secid(ts_code)
    path = FFLOW_PATH.format(secid=secid)
    last: Exception | None = None
    for attempt in range(retries):
        try:
            data = _direct_get_json(FFLOW_HOST, path, timeout)
            out: dict[str, float] = {}
            for k in (data.get("data") or {}).get("klines") or []:
                parts = k.split(",")
                if len(parts) >= 2:
                    try:
                        out[parts[0]] = float(parts[1])
                    except ValueError:
                        continue
            return out
        except Exception as exc:  # noqa: BLE001 — 限流/网络抖动统一退避
            last = exc
            time.sleep(0.6 * (2 ** attempt) + random.uniform(0.0, 0.4))
    raise RuntimeError(f"fflow daykline 拉取失败 {ts_code}: {last}") from last


def _rolling_5d(series: dict[str, float], trade_date: str) -> float | None:
    """截至 trade_date（含）最近 5 个交易日主力净额之和（元）。不足 5 日不算。"""
    days = sorted(d for d in series if d <= trade_date)
    if trade_date not in series or len(days) < 5:
        return None
    window = days[-5:]
    return sum(series[d] for d in window)


# 5 日窗口结构性不足的留痕表: 区分「上市不满 5 天、这一天永远算不出 5 日值」与
# 「只是还没拉到数据」。前者若不留痕就会每轮重试到天荒地老——注意它**不会**随时间
# 自愈: 某股上市次日那条历史记录, 无论多久以后回看, 截至那天也只有两天数据。
GAP_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS ops_fund_flow_5d_gap (
    trade_date    DATE,
    stock_ts_code TEXT,
    reason        TEXT,
    recorded_at   TIMESTAMP,
    PRIMARY KEY (trade_date, stock_ts_code)
)
"""


def _ensure_gap_table(con) -> None:
    con.execute(GAP_TABLE_SQL)


def _mark_5d_gap(con, trade_date: str, codes: list[str], reason: str) -> int:
    if not codes:
        return 0
    _ensure_gap_table(con)
    now = datetime.now(timezone.utc).isoformat()
    con.executemany(
        "INSERT INTO ops_fund_flow_5d_gap VALUES (?,?,?,?) ON CONFLICT DO NOTHING",
        [(trade_date, c, reason, now) for c in codes],
    )
    return len(codes)


# ── 写入 ──────────────────────────────────────────────────


def _pending_codes(con, trade_date: str) -> list[str]:
    """当日仍缺资金流的 local:stitch 成员（去重个股）。

    1 日与 5 日**任一为空就算待补**：只看 1 日的话，早期写入 1日=1.0/5日=NULL 的行
    会永远退出待补集，即使接口后来给出完整序列，5 日值也再没机会被填上。
    """
    _ensure_gap_table(con)
    rows = con.execute(
        """
        SELECT DISTINCT g.stock_ts_code
        FROM fact_sector_stock_daily_generation g
        WHERE g.trade_date = ? AND g.source = ?
          AND (g.fund_flow_1d IS NULL
               OR (g.fund_flow_5d IS NULL AND NOT EXISTS (
                     SELECT 1 FROM ops_fund_flow_5d_gap x
                     WHERE x.trade_date = g.trade_date
                       AND x.stock_ts_code = g.stock_ts_code)))
        ORDER BY 1
        """,
        [trade_date, STITCH_SOURCE],
    ).fetchall()
    return [r[0] for r in rows]


def _fill_rows(con, trade_date: str, flows: dict[str, tuple[float | None, float | None]]) -> int:
    """flows: {ts_code: (f1亿, f5亿)}。只填 local:stitch 且该列为 NULL 的行, 返回更新行数。

    **逐列补空**: 1 日已有、5 日为空的行也要能续补; 用 COALESCE 保证既有值不被覆盖。
    """
    payload = [
        (ts, f1, f5)
        for ts, (f1, f5) in flows.items()
        if f1 is not None or f5 is not None
    ]
    if not payload:
        return 0
    now = datetime.now(timezone.utc).isoformat()
    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE _flow_fill (
            stock_ts_code VARCHAR, f1 DOUBLE, f5 DOUBLE
        )
        """
    )
    con.executemany("INSERT INTO _flow_fill VALUES (?,?,?)", payload)
    before = con.execute(
        """
        SELECT count(*) FROM fact_sector_stock_daily_generation g
        JOIN _flow_fill u ON u.stock_ts_code = g.stock_ts_code
        WHERE g.trade_date = ? AND g.source = ?
          AND (g.fund_flow_1d IS NULL OR g.fund_flow_5d IS NULL)
        """,
        [trade_date, STITCH_SOURCE],
    ).fetchone()[0]
    con.execute(
        """
        UPDATE fact_sector_stock_daily_generation AS g
        SET fund_flow_1d = COALESCE(g.fund_flow_1d, u.f1),
            fund_flow_5d = COALESCE(g.fund_flow_5d, u.f5),
            updated_at = ?
        FROM _flow_fill AS u
        WHERE g.stock_ts_code = u.stock_ts_code
          AND g.trade_date = ?
          AND g.source = ?
          AND (g.fund_flow_1d IS NULL OR g.fund_flow_5d IS NULL)
        """,
        [now, trade_date, STITCH_SOURCE],
    )
    con.execute("DROP TABLE _flow_fill")
    return int(before)


def _coverage(con, trade_date: str) -> tuple[int, int]:
    total, covered = con.execute(
        """
        SELECT count(*), count(fund_flow_1d)
        FROM fact_sector_stock_daily WHERE trade_date = ?
        """,
        [trade_date],
    ).fetchone()
    return int(total), int(covered)


def _coverage_5d(con, trade_date: str) -> tuple[int, int]:
    """5 日覆盖单独报：合并进 1 日覆盖率会把 5 日的缺口遮住。"""
    total, covered = con.execute(
        """
        SELECT count(*), count(fund_flow_5d)
        FROM fact_sector_stock_daily WHERE trade_date = ?
        """,
        [trade_date],
    ).fetchone()
    return int(total), int(covered)


def _is_shanghai_today(trade_date: str) -> bool:
    return trade_date == datetime.now(_SHANGHAI).date().isoformat()


# ── 编排 ──────────────────────────────────────────────────


def _rebuild_panels(con, trade_date: str) -> dict:
    """从已落库成分独立重建面板。

    **不能挂在「本次填了多少行」上**：资金写成功、汇总那一步炸了之后，重跑时
    待填集为空，if filled 会永久跳过汇总，结果是覆盖率 1/1 但面板 0——数据在库里
    却永远出不来。汇总只看库里现有成分，与本次采集结果无关。

    **也不能在「当日无资金」时提前返回**：那正是必须执行撤销的情形——成分变空而
    直接 return，上一轮的旧面板会以「当日有效」的身份留在库里被查到。空负载交给
    聚合器，它会删光本口径当日的面板并报 stale_removed。
    """
    return sync_from_sector_baskets(
        trade_date, con=con, member_source=STITCH_SOURCE, manage_transaction=True
    )


def sync_snapshot(trade_date: str, *, con=None, allow_fetch: bool = True) -> dict:
    """快照路径: 优先重放本地留底, 无留底且允许时才联网采集。

    日期保护只管**新采集**: clist 只给「最新」快照, 在非归属日取数会把别天的值
    写到这天头上; 而**重放已校验的留底不受此限**——否则留底形同虚设, 次日想用
    却只能去求那个不可靠的历史接口。
    """
    own = con is None
    if own:
        init_db()
        con = connect()
    try:
        # 先落原始再汇总: 后面任何一步炸了都能本地重放, 不用再求上游。
        archive = load_raw_snapshot(trade_date)  # 元数据不符会在这里直接报错
        replayed = archive is not None
        if archive is not None:
            raw = archive["records"]
        else:
            if not allow_fetch:
                raise ValueError(f"{trade_date} 无留底且已禁止联网采集")
            if not _is_shanghai_today(trade_date):
                raise ValueError(
                    f"clist 是「最新快照」语义, 新采集只能在归属交易日当天盘后进行; "
                    f"trade_date={trade_date} 不是上海时区今天且无留底, 请用 history 模式"
                )
            raw = fetch_flow_snapshot()
            path = capture_raw_snapshot(trade_date, raw=raw)
            # **存证≠可用**: 不合格的首次采集绝不写库。_fill_rows 只补 NULL,
            # 盘中的 1 亿 一旦落库, 收盘后采到的 9 亿 就再也盖不上了——错值永久化。
            # 宁可本次什么都不写, 等收盘后重跑。
            status = (load_raw_snapshot(trade_date) or {}).get("meta", {}).get("status")
            if status != "final":
                doc = json.loads(Path(path).read_text(encoding="utf-8"))
                total, covered = _coverage(con, trade_date)
                return {
                    "trade_date": trade_date, "mode": "snapshot",
                    "fetched": len(raw), "replayed_from_raw": False,
                    "archive_status": doc.get("status"), "written": False,
                    "note": "快照不合格(盘中或条数不足), 已存证未写库",
                    "pending": 0, "filled_rows": 0, "panels": 0,
                    "coverage": f"{covered}/{total}",
                }
        # 纯代码 → 当日成员 ts_code
        members = _pending_codes(con, trade_date)
        flows = {}
        for ts in members:
            got = raw.get(ts.split(".")[0])
            if got:
                flows[ts] = (_yi(got[0]), _yi(got[1]))
        filled = _fill_rows(con, trade_date, flows)
        agg = _rebuild_panels(con, trade_date)   # 与 filled 解耦, 重跑可恢复
        total, covered = _coverage(con, trade_date)
        return {
            "trade_date": trade_date, "mode": "snapshot", "fetched": len(raw),
            "replayed_from_raw": replayed,
            "pending": len(members), "filled_rows": filled,
            "archive_status": "final", "written": True,
            "panels": agg.get("panels", 0), "caliber": agg.get("caliber"),
            "stale_removed": agg.get("stale_removed", 0),
            "coverage": f"{covered}/{total}",
            "coverage_5d": "{}/{}".format(*reversed(_coverage_5d(con, trade_date))),
        }
    finally:
        if own:
            con.close()


def sync_history(trade_dates: list[str], *, con=None, concurrency: int = 4,
                 limit: int | None = None, progress_every: int = 200) -> dict:
    """历史回补: 逐股拉 daykline (一次覆盖全部目标日), 填缺后逐日聚合。

    断点续跑: 只拉「任一目标日仍缺值」的股票; 中途失败重跑即可续。
    """
    own = con is None
    if own:
        init_db()
        con = connect()
    try:
        pending_by_date = {d: set(_pending_codes(con, d)) for d in trade_dates}
        codes = sorted(set().union(*pending_by_date.values())) if pending_by_date else []
        if limit:
            codes = codes[:limit]
        print(f"fund-flow history: {len(codes)} 只待拉, 目标日 {trade_dates}", flush=True)

        series: dict[str, dict[str, float]] = {}
        failures: list[str] = []
        done = 0

        def _one(ts: str):
            nonlocal done
            try:
                s = fetch_flow_history(ts)
                time.sleep(random.uniform(0.05, 0.2))
                return ts, s
            except Exception:  # noqa: BLE001
                failures.append(ts)
                return ts, None

        empty: list[str] = []
        with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
            for ts, s in pool.map(_one, codes):
                done += 1
                # 空字典**不是**成功: 上游返回 {} 时既没异常也没数据, 计入 fetched
                # 会让「全网返回空」报成 rc=0 并落 ok=True 的收据。
                if s:
                    series[ts] = s
                elif s is not None:
                    empty.append(ts)
                if progress_every and done % progress_every == 0:
                    print(f"  … {done}/{len(codes)} (fail={len(failures)})", flush=True)

        summary_days = []
        for d in trade_dates:
            flows = {}
            short_hist = []
            for ts in pending_by_date[d]:
                s = series.get(ts)
                if not s or d not in s:
                    continue
                r5 = _rolling_5d(s, d)
                if r5 is None:
                    # 上游已返回完整可得历史(约120天)却仍不足 5 天 → 结构性不足
                    short_hist.append(ts)
                flows[ts] = (_yi(s[d]), _yi(r5))
            filled = _fill_rows(con, d, flows)
            marked = _mark_5d_gap(con, d, short_hist, "insufficient_history")
            agg = _rebuild_panels(con, d)   # 与 filled 解耦, 重跑可恢复
            panels = agg.get("panels", 0)
            total, covered = _coverage(con, d)
            summary_days.append({
                "trade_date": d, "filled_rows": filled, "panels": panels,
                "caliber": agg.get("caliber"),
                "stale_removed": agg.get("stale_removed", 0),
                "coverage": f"{covered}/{total}",
                "coverage_5d": "{}/{}".format(*reversed(_coverage_5d(con, d))),
                "5d_gap_marked": marked,
            })
            print(f"  {d}: filled={filled} panels={panels} coverage={covered}/{total}", flush=True)
        return {
            "mode": "history", "codes": len(codes), "fetched": len(series),
            "failed": len(failures), "empty": len(empty), "days": summary_days,
        }
    finally:
        if own:
            con.close()


def sync(trade_date: str, *, mode: str = "auto", concurrency: int = 4,
         limit: int | None = None) -> dict:
    """单日入口。

    auto 的优先级: **已有留底 → 直接重放**（不论哪天）> 当天 → 联网快照
    > 历史日 → 逐股回补。把重放排在最前面，是因为留底就是为了不再求上游；
    旧实现 auto 遇历史日直接走网络，留底永远读不到。
    """
    if mode not in ("auto", "snapshot", "history"):
        raise ValueError(f"unknown mode {mode!r}")
    if mode == "snapshot":
        return sync_snapshot(trade_date)
    if mode == "auto":
        if load_raw_snapshot(trade_date) is not None or _is_shanghai_today(trade_date):
            snap = sync_snapshot(trade_date)
            # **重放不是终点**: 快照只有当日 f62/f164, 它给不了的缺口(如 5 日值为空)
            # 会在每次 auto 重放中原封不动地留着, 历史接口永远调用为零。
            # 重放后仍有待补就接着走逐股回补, 两段结果合并上报。
            con = connect()
            try:
                remaining = _pending_codes(con, trade_date)
            finally:
                con.close()
            if not remaining:
                return snap
            hist = sync_history([trade_date], concurrency=concurrency, limit=limit)
            return {**snap, "mode": "auto:snapshot+history",
                    "snapshot": {k: snap.get(k) for k in
                                 ("filled_rows", "coverage", "replayed_from_raw")},
                    "codes": hist.get("codes"), "fetched": hist.get("fetched"),
                    "failed": hist.get("failed"), "empty": hist.get("empty"),
                    "days": hist.get("days")}
    return sync_history([trade_date], concurrency=concurrency, limit=limit)
