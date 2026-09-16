"""板块维度一致化: 供应商换码系后的「旧码 → 现行码」映射, 以及按名/按码的解析器。

## 问题形状 (2026-09-03 只读审计)

dim_sector 630 行 = 223 个 `.TI` 码 + 407 个 `.FP` 码, 但真实板块只有 ~400 个:
117 个板块名同时挂在两个码下。两套码在事实表里并存 124 个交易日
(2025-10-09 ~ 2026-07-24), 同名板块**数值不同**——是两家供应商各算一套, 不是重复行。
另有 53 个码历史上改过名 (`PCB` ↔ `PCB概念`)。`config_sector_alias` 为此而设, 却一直 0 行。

后果: 按 sector_name GROUP BY 双计; `WHERE sector_name = ?` 在并存日把两个供应商的
成分股混成一张表; 跨 2026-07-24 的时间序列在换码日断裂。

## 处方

数仓里这叫 conformed dimension: `sector_name` 是展示属性, 键必须是稳定的代码。
- 「旧码 → 现行码」是唯一不能从数据推出来的人工事实, 落 `config_sector_alias`
  (本模块按**同名唯一匹配**机械生成, 同名多码的歧义留给人, 不猜)。
- 解析走 `dim_sector_canonical` 视图 (schema.sql), 输入名或码, 输出按优先级排好的
  候选码; 查询方拿**码**去查事实表, 不再拿名字当键。
- 同名对应多个 canonical 组 (如 `国防军工` 两个 .FP 码) 是真歧义: 解析器显式标
  `ambiguous=True` 并给出全部候选, 不静默合并。

映射只解决「这条线该接到哪」, 不解决「两套口径数值能否相加」——不能。
"""
from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

import duckdb

from . import db as _db

RETIRED_SUFFIX = ".TI"
CURRENT_SUFFIX = ".FP"
PROVIDER_MIGRATION_CONFIDENCE = 0.9
PROVIDER_MIGRATION_TAG = "provider-migration"


# ---------------------------------------------------------------------------
# 规划 / 应用
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AliasRow:
    alias: str
    sector_ts_code: str
    sector_name: str
    confidence: float
    note: str


@dataclass
class AliasPlan:
    rows: list[AliasRow] = field(default_factory=list)
    # 退役码找不到同名现行码: 留给人工 (可能改名了, 也可能供应商真砍了)。
    unmapped: list[tuple[str, str]] = field(default_factory=list)
    # 退役码同名对应 ≥2 个现行码: 不猜, 列出来。
    ambiguous: list[tuple[str, str, list[str]]] = field(default_factory=list)

    def summary(self) -> dict:
        return {
            "mapped": len(self.rows),
            "unmapped": len(self.unmapped),
            "ambiguous": len(self.ambiguous),
            "unmapped_codes": [f"{code} {name}" for code, name in self.unmapped],
            "ambiguous_codes": [
                f"{code} {name} -> {','.join(targets)}"
                for code, name, targets in self.ambiguous
            ],
        }


def _fact_spans(con: duckdb.DuckDBPyConnection) -> dict[str, tuple[str | None, str | None]]:
    rows = con.execute(
        """
        SELECT sector_ts_code, MIN(trade_date), MAX(trade_date)
        FROM fact_sector_daily_generation
        GROUP BY sector_ts_code
        """
    ).fetchall()
    return {code: (str(lo) if lo else None, str(hi) if hi else None) for code, lo, hi in rows}


def _span_text(code: str, spans: dict[str, tuple[str | None, str | None]]) -> str:
    lo, hi = spans.get(code, (None, None))
    if lo is None:
        return code
    return f"{code}({lo}→{hi})"


def plan_provider_migration(
    con: duckdb.DuckDBPyConnection,
    *,
    retired_suffix: str = RETIRED_SUFFIX,
    current_suffix: str = CURRENT_SUFFIX,
) -> AliasPlan:
    """按 dim_sector 同名精确匹配, 生成「退役码 → 现行码」映射。

    只写唯一匹配。0 个匹配进 unmapped, ≥2 个进 ambiguous——两者都不写库,
    机械匹配没有资格替人裁决同名不同义的板块。
    """
    dim = con.execute(
        "SELECT sector_ts_code, sector_name FROM dim_sector ORDER BY sector_ts_code"
    ).fetchall()
    current_by_name: dict[str, list[str]] = {}
    for code, name in dim:
        if code.endswith(current_suffix):
            current_by_name.setdefault(name, []).append(code)
    spans = _fact_spans(con)

    plan = AliasPlan()
    for code, name in dim:
        if not code.endswith(retired_suffix):
            continue
        targets = current_by_name.get(name, [])
        if not targets:
            plan.unmapped.append((code, name))
            continue
        if len(targets) > 1:
            plan.ambiguous.append((code, name, list(targets)))
            continue
        target = targets[0]
        note = (
            f"{PROVIDER_MIGRATION_TAG}: {_span_text(code, spans)} → "
            f"{_span_text(target, spans)}; 同名唯一匹配; "
            "两套口径成分不同, 跨切换日数值不可直接比较"
        )
        plan.rows.append(
            AliasRow(
                alias=code,
                sector_ts_code=target,
                sector_name=name,
                confidence=PROVIDER_MIGRATION_CONFIDENCE,
                note=note,
            )
        )
    return plan


def apply_alias_rows(con: duckdb.DuckDBPyConnection, rows: list[AliasRow]) -> int:
    """幂等 upsert 到 config_sector_alias, 返回写入行数。"""
    if not rows:
        return 0
    now = datetime.now()
    con.executemany(
        """
        INSERT OR REPLACE INTO config_sector_alias
            (alias, sector_ts_code, sector_name, confidence, note, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            (r.alias, r.sector_ts_code, r.sector_name, r.confidence, r.note, now)
            for r in rows
        ],
    )
    return len(rows)


def _write_receipt(
    con: duckdb.DuckDBPyConnection,
    *,
    plan_name: str,
    started_at: datetime,
    ok: bool,
    child_pid: int | None,
    copy: dict | None,
    rows_summary: dict,
    steps_summary: list[dict],
) -> str:
    """ops_sync_run 收据: 与 daily-full 同一张台账, 让「谁何时动过库」一处可查。"""
    run_id = uuid.uuid4().hex[:12]
    finished = datetime.now()
    con.execute(
        """
        INSERT INTO ops_sync_run
            (run_id, kind, plan, trade_date, started_at, finished_at, duration_s, ok,
             pid, child_pid, copy_method, copy_seconds, source_bytes,
             rows_summary, steps_summary)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        [
            run_id,
            "sector-alias",
            plan_name,
            None,
            started_at,
            finished,
            round((finished - started_at).total_seconds(), 1),
            ok,
            os.getpid(),
            child_pid,
            (copy or {}).get("method"),
            (copy or {}).get("seconds"),
            (copy or {}).get("bytes"),
            json.dumps(rows_summary, ensure_ascii=False),
            json.dumps(steps_summary, ensure_ascii=False),
        ],
    )
    return run_id


def apply_provider_migration(
    con: duckdb.DuckDBPyConnection, *, plan_name: str = "direct"
) -> dict:
    """在给定连接上: 重放 schema (建视图) → 规划 → 写映射 → 收据。"""
    started = datetime.now()
    _db.init_db(con)
    plan = plan_provider_migration(con)
    written = apply_alias_rows(con, plan.rows)
    total = con.execute("SELECT COUNT(*) FROM config_sector_alias").fetchone()[0]
    summary = plan.summary()
    run_id = _write_receipt(
        con,
        plan_name=plan_name,
        started_at=started,
        ok=True,
        child_pid=None,
        copy=None,
        rows_summary={"config_sector_alias": total, "written": written},
        steps_summary=[{"name": "plan_provider_migration", "ok": True, **summary}],
    )
    return {"run_id": run_id, "written": written, "config_sector_alias": total, **summary}


def apply_provider_migration_staged(target: Path | None = None) -> dict:
    """生产库正门: 克隆到 staging → 在副本上应用 → 第三方写者守卫 → 原子换名。

    复用 daily-full 的四个原语 (db.clone_to_staging 等), 生产库文件只在换名一瞬
    变化, 正持旧句柄的读者不受影响。任何守卫失败都不换名, staging 留作取证。
    返回 {swapped, reason, ...}; swapped=False 时生产库一字未动。
    """
    target = Path(target) if target is not None else _db.DB_PATH
    staging = _db.staging_path(target)
    result: dict = {"target": str(target), "staging": str(staging), "swapped": False}

    result["stale_staging_removed"] = _db.remove_stale_staging(staging)
    if not target.exists():
        result["reason"] = f"目标库不存在, 拒绝开工: {target}"
        return result
    try:
        _db.probe_no_active_writer(target)
    except _db.DatabaseLockedError as exc:
        result["reason"] = f"生产库有活跃写者, 拒绝开工: {exc}"
        return result

    started = datetime.now()
    copy = _db.clone_to_staging(target, staging)
    base_stat = target.stat()
    result["copy"] = copy

    con = duckdb.connect(str(staging))
    try:
        _db.init_db(con)
        plan = plan_provider_migration(con)
        written = apply_alias_rows(con, plan.rows)
        total = con.execute("SELECT COUNT(*) FROM config_sector_alias").fetchone()[0]
        summary = plan.summary()
        run_id = _write_receipt(
            con,
            plan_name="staging-swap",
            started_at=started,
            ok=True,
            child_pid=None,
            copy=copy,
            rows_summary={"config_sector_alias": total, "written": written},
            steps_summary=[{"name": "plan_provider_migration", "ok": True, **summary}],
        )
    finally:
        con.close()
    result.update({"run_id": run_id, "written": written, "config_sector_alias": total, **summary})

    now_stat = target.stat()
    if now_stat.st_mtime_ns != base_stat.st_mtime_ns or now_stat.st_size != base_stat.st_size:
        result["reason"] = "第三方写者守卫: 生产库在应用期间被修改, 拒绝换名; staging 保留待裁决"
        return result
    try:
        _db.probe_no_active_writer(target)
    except _db.DatabaseLockedError as exc:
        result["reason"] = f"第三方写者守卫: {exc}; 拒绝换名"
        return result

    swap_started = time.monotonic()
    try:
        _db.atomic_swap_into_place(staging, target)
    except (RuntimeError, FileNotFoundError, OSError) as exc:
        result["reason"] = f"换名失败: {exc}"
        return result
    result["swap_seconds"] = round(time.monotonic() - swap_started, 3)
    result["swapped"] = True
    result["reason"] = "ok"
    return result


# ---------------------------------------------------------------------------
# 解析: 名 / 码 → 按优先级排好的候选码
# ---------------------------------------------------------------------------


@dataclass
class SectorCandidate:
    sector_ts_code: str
    sector_name: str
    provider: str
    is_active: bool
    canonical_sector_ts_code: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SectorResolution:
    query: str
    # 'code' | 'alias' | 'name' | 'historical_name' | 'none' | 'unavailable'
    matched_by: str
    # 优先级从高到低: canonical 现行码在前, 退役原码在后。
    codes: list[str] = field(default_factory=list)
    # 同名对应 ≥2 个 canonical 组 (真歧义), 调用方必须让人看见。
    ambiguous: bool = False
    candidates: list[SectorCandidate] = field(default_factory=list)

    @property
    def canonical(self) -> str | None:
        return self.codes[0] if self.codes else None

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "matched_by": self.matched_by,
            "canonical": self.canonical,
            "codes": list(self.codes),
            "ambiguous": self.ambiguous,
            "candidates": [c.to_dict() for c in self.candidates],
        }


def load_canonical_map(con: duckdb.DuckDBPyConnection) -> dict[str, SectorCandidate] | None:
    """读 dim_sector_canonical; 视图不存在 (旧库未重放 schema) 返回 None。"""
    try:
        rows = con.execute(
            """
            SELECT sector_ts_code, sector_name, provider, COALESCE(is_active, FALSE),
                   canonical_sector_ts_code
            FROM dim_sector_canonical
            """
        ).fetchall()
    except duckdb.CatalogException:
        return None
    return {
        code: SectorCandidate(code, name, provider, bool(active), canonical)
        for code, name, provider, active, canonical in rows
    }


def _preference(c: SectorCandidate) -> tuple:
    # 现行 > 退役; 当前供应商 > 旧供应商; 同级按码稳定排序, 保证结果可复现。
    return (not c.is_active, c.provider != "FP", c.sector_ts_code)


def resolve_sector_codes(con: duckdb.DuckDBPyConnection, sector: str) -> SectorResolution:
    """把用户给的板块名或码解析成事实表可用的码。

    匹配顺序: 精确码 → config_sector_alias 人工别名 → dim_sector 现名 →
    事实表历史名。命中后按 canonical 分组: 一组 = 一条线 (退役码跟在现行码后面,
    供查询方按日期回退); 多组 = 真歧义, 标 ambiguous 并保留全部候选。
    """
    text = (sector or "").strip()
    if not text:
        return SectorResolution(query=sector, matched_by="none")
    dim = load_canonical_map(con)
    if dim is None:
        return SectorResolution(query=sector, matched_by="unavailable")

    group: list[SectorCandidate] = []
    matched_by = "none"
    if text in dim:
        group = [dim[text]]
        matched_by = "code"
    else:
        alias_hit = con.execute(
            """
            SELECT sector_ts_code FROM config_sector_alias WHERE alias = ?
            ORDER BY confidence DESC NULLS LAST, sector_ts_code
            """,
            [text],
        ).fetchall()
        alias_codes = [c for (c,) in alias_hit if c in dim]
        if alias_codes:
            group = [dim[c] for c in alias_codes]
            matched_by = "alias"
        else:
            named = [c for c in dim.values() if c.sector_name == text]
            if named:
                group = named
                matched_by = "name"
            else:
                hist = con.execute(
                    """
                    SELECT DISTINCT sector_ts_code FROM fact_sector_daily_generation
                    WHERE sector_name = ?
                    """,
                    [text],
                ).fetchall()
                hist_codes = [c for (c,) in hist if c in dim]
                if hist_codes:
                    group = [dim[c] for c in hist_codes]
                    matched_by = "historical_name"
    if not group:
        return SectorResolution(query=sector, matched_by="none")

    # 每个命中成员扩到它所属的整条线: canonical 目标 + 指向同一 canonical 的退役码。
    canonicals: dict[str, list[SectorCandidate]] = {}
    for member in group:
        canonicals.setdefault(member.canonical_sector_ts_code, [])
    for cand in dim.values():
        if cand.canonical_sector_ts_code in canonicals:
            canonicals[cand.canonical_sector_ts_code].append(cand)

    ordered_groups = sorted(
        canonicals.items(),
        key=lambda kv: _preference(dim.get(kv[0], kv[1][0])),
    )
    codes: list[str] = []
    candidates: list[SectorCandidate] = []
    for canonical, members in ordered_groups:
        members = sorted(members, key=_preference)
        head = [m for m in members if m.sector_ts_code == canonical]
        tail = [m for m in members if m.sector_ts_code != canonical]
        for m in head + tail:
            if m.sector_ts_code not in codes:
                codes.append(m.sector_ts_code)
                candidates.append(m)
    return SectorResolution(
        query=sector,
        matched_by=matched_by,
        codes=codes,
        ambiguous=len(ordered_groups) > 1,
        candidates=candidates,
    )


def pick_code_with_rows(
    con: duckdb.DuckDBPyConnection,
    table: str,
    trade_date,
    codes: list[str],
) -> str | None:
    """按候选优先级, 返回第一个在 table 该日**有行**的码; 都没有返回 None。

    这是解析器「退役码跟在现行码后面」的另一半: 2025-06 问 `云计算`, 现行 .FP 码
    还没数据, 就该落到 .TI 码上, 而不是答「无数据」。
    """
    if not codes:
        return None
    placeholders = ",".join("?" for _ in codes)
    present = {
        code
        for (code,) in con.execute(
            f"""
            SELECT sector_ts_code FROM {table}
            WHERE trade_date = ? AND sector_ts_code IN ({placeholders})
            GROUP BY sector_ts_code
            """,
            [trade_date, *codes],
        ).fetchall()
    }
    for code in codes:
        if code in present:
            return code
    return None
