"""冻结快照当内容版本源：回答「当时看到的是哪个值」（OPT-01 第二刀）。

补强 spec `2026-09-08-research-foundation-optimization-design.md` OPT-01 的存储侧结论是
**复用已有冻结快照及分代机制**，不新建版本表：`intelligence/eval/pit_snapshot.py` 每晚
把 14 张骨干表的 as-of 内容连同封印（gzip sha → payload sha → manifest sha）写进
`~/fidelity-replay/pit-snapshots/`，这已经是 append-only 的内容版本账——缺的只是
**取回**那半边。本模块补它：

- ``connect_frozen(root, snapshot_as_of, db_path)``：验证封印后把一份快照装成内存
  DuckDB，河的六轨 provider 直接在它上面跑——payload、派生字段、ref 全由同一套
  读取面构造，不存在第二份重建逻辑可漂。
- 快照**没有**的表分两类如实处理：舆论表（``fact_research_report_catalog`` 等）自带
  写一次不更新的 ``created_at``，本来就不会被重发布冲刷，VIEW 到当前库 + cutoff
  过滤即为严格；config 配置表（别名映射等）没有历史版本可取，用当前值并在
  ``content_source`` 里如实声明——它影响实体解析口径，不影响事实值。
- 修订语义：T 日原值被 T+7 重发布覆盖后，主库只剩新值（``updated_at`` 被推到 T+7，
  河据此降档滤除——第一刀 #43 的行为，保守但答不出旧值）；本模块让
  ``slice_river(T, C=T, frozen_snapshot_root=...)`` 从 ≤C 最新快照取回**当时的行**。
  选 ≤C 的快照只会取到偏旧、不会取到偏未来的版本——PIT 的安全方向。

失败语义 fail closed：封印任何一环校验不过（内容被删、gz 被改、manifest 被改）都抛
``FrozenSnapshotError``，**不静默回退**到更早快照或当前库——回退会把「版本源损坏」
伪装成「当时就是这个值」。spec OPT-01 验收 3：删除可解析内容后，回放门必须失败，
而非只看 hash 字符串通过。
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any

import duckdb

from intelligence.eval.pit_snapshot import (
    SNAPSHOT_TABLES,
    _canonical_bytes,
    _sha256,
    validate_frozen_snapshot,
)

# 行内注解键（pit_snapshot._annotate_pit_row 加的），不是表列，装库与内容 hash 前剔除。
_ANNOTATION_KEYS = ("_pit",)


class FrozenSnapshotError(RuntimeError):
    """冻结快照不可用：封印校验失败 / 文件对不完整 / 无法装载。不可静默吞掉。"""


def available_snapshots(root: str | Path) -> list[str]:
    """列出 root 下有 manifest 的快照日（升序）。只看文件名，不做校验——校验在装载时。"""
    base = Path(root).expanduser()
    if not base.is_dir():
        return []
    return sorted(p.name[:10] for p in base.glob("*.manifest.json"))


def best_snapshot_for(root: str | Path, knowledge_cutoff: str) -> str | None:
    """≤ cutoff 的最新快照日；没有则 None（调用方如实回落并声明，不猜）。"""
    cut = str(knowledge_cutoff)[:10]
    candidates = [d for d in available_snapshots(root) if d <= cut]
    return candidates[-1] if candidates else None


def _strip_annotations(row: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in row.items() if k not in _ANNOTATION_KEYS}


def load_snapshot_data(root: str | Path, snapshot_as_of: str) -> dict[str, list[dict[str, Any]]]:
    """验证封印并返回 ``{table: rows}``。任何一环校验失败抛 ``FrozenSnapshotError``。"""
    base = Path(root).expanduser()
    try:
        validate_frozen_snapshot(base, snapshot_as_of)
    except (ValueError, OSError) as exc:
        raise FrozenSnapshotError(f"冻结快照 {snapshot_as_of} 封印校验失败：{exc}") from exc
    compressed = (base / f"{snapshot_as_of}.snapshot.json.gz").read_bytes()
    snapshot = json.loads(gzip.decompress(compressed))
    data = snapshot.get("data")
    if not isinstance(data, dict):
        raise FrozenSnapshotError(f"冻结快照 {snapshot_as_of} 缺 data 段")
    return {str(t): list(rows or []) for t, rows in data.items()}


def connect_frozen(
    root: str | Path,
    snapshot_as_of: str,
    *,
    db_path: str | Path,
) -> "duckdb.DuckDBPyConnection":
    """把一份封印快照装成内存 DuckDB，表名与主库一致，供河的 provider 直接查。

    - 快照里的表：结构从主库 ``LIMIT 0`` 拷（schema 演进后快照缺的新列如实为 NULL），
      数据全部来自快照——这是「当时的内容版本」。
    - 快照外的表与视图：``CREATE VIEW`` 指向主库当前值（舆论表靠自身 ``created_at``
      过滤即严格；config 表无历史版本，用现值是**声明过的**口径，见模块 docstring）。

    返回的连接由调用方负责 ``close()``。主库以 READ_ONLY attach，写锁并存可读。
    """
    data = load_snapshot_data(root, snapshot_as_of)
    db = str(Path(db_path).expanduser())
    con = duckdb.connect(":memory:")
    try:
        con.execute(f"ATTACH '{db}' AS live (READ_ONLY)")
        live_objects = {
            str(name): str(kind)
            for name, kind in con.execute(
                "SELECT table_name, table_type FROM information_schema.tables "
                "WHERE table_catalog = 'live' AND table_schema = 'main'"
            ).fetchall()
        }
        for table in sorted(live_objects):
            if table in SNAPSHOT_TABLES:
                # 快照覆盖集内的表**只**用快照数据。这份快照没拍到（老快照缺新表）就是
                # 空表——「当时版本不可得」如实表现为缺口，不能 VIEW 到当前库冒充当时。
                con.execute(f'CREATE TABLE main."{table}" AS SELECT * FROM live.main."{table}" LIMIT 0')
                _insert_rows(con, table, data.get(table) or [])
            else:
                # 覆盖集外的表按设计走当前库：舆论表自带写一次不更新的 created_at（cutoff
                # 过滤即严格）；config / 台账 / generation 底表无「被冲刷的当时值」问题。
                con.execute(f'CREATE VIEW main."{table}" AS SELECT * FROM live.main."{table}"')
        orphan = sorted(set(data) - set(live_objects))
        if orphan:
            # 快照里有、主库已删的表：没有结构可拷，provider 也不再查它——记事实不装载。
            con.execute("CREATE TABLE IF NOT EXISTS _frozen_orphan_tables (table_name TEXT)")
            con.executemany("INSERT INTO _frozen_orphan_tables VALUES (?)", [(t,) for t in orphan])
    except FrozenSnapshotError:
        con.close()
        raise
    except Exception as exc:  # duckdb.Error 等装载失败：版本源不可用，fail closed
        con.close()
        raise FrozenSnapshotError(f"冻结快照 {snapshot_as_of} 装载失败：{exc}") from exc
    return con


def _insert_rows(con: "duckdb.DuckDBPyConnection", table: str, rows: list[dict[str, Any]]) -> None:
    """快照行批量装入内存表。走 ``read_json``（newline_delimited）而不是逐行
    executemany——整份快照十几万行，后者实测把装载拖到十几秒。列按名对齐取交集：
    快照缺的新列如实为 NULL，快照多出的已删列丢弃。"""
    if not rows:
        return
    import tempfile

    table_cols = [
        str(c)
        for (c,) in con.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_catalog = 'memory' AND table_schema = 'main' AND table_name = ? "
            "ORDER BY ordinal_position",
            [table],
        ).fetchall()
    ]
    with tempfile.NamedTemporaryFile("w", suffix=".ndjson", encoding="utf-8", delete=False) as f:
        tmp = Path(f.name)
        for row in rows:
            f.write(json.dumps(_strip_annotations(row), ensure_ascii=False, default=str) + "\n")
    try:
        tmp_sql = str(tmp).replace("'", "''")  # 路径来自 NamedTemporaryFile，转义只为防御
        con.execute(
            "CREATE OR REPLACE TEMP VIEW _frozen_load AS "
            f"SELECT * FROM read_json('{tmp_sql}', format = 'newline_delimited', "
            "auto_detect = true, sample_size = -1)"
        )
        loaded_cols = {
            str(c)
            for (c,) in con.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = '_frozen_load'"
            ).fetchall()
        }
        common = [c for c in table_cols if c in loaded_cols]
        quoted = ", ".join(f'"{c}"' for c in common)
        con.execute(f'INSERT INTO main."{table}" ({quoted}) SELECT {quoted} FROM _frozen_load')  # noqa: S608
        con.execute("DROP VIEW _frozen_load")
    finally:
        tmp.unlink(missing_ok=True)


def content_hash(row: dict[str, Any]) -> str:
    """行内容的身份 hash：剔除注解键后的 canonical JSON sha256（与快照封印同一套字节化）。"""
    return _sha256(_canonical_bytes(_strip_annotations(row)))


def list_content_versions(
    root: str | Path,
    table: str,
    match: dict[str, Any],
    *,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    """一行事实的版本史：它在各快照里的内容版本序列 + 主库当前值（OPT-01「T+7 查询
    能看到修订与原版本关系」）。

    ``match``：列名 → 值，全部相等（字符串化比较，日期只比前 10 位）才算同一行。
    每份快照都过完整封印校验；相邻快照内容 hash 不变时归并为同一版本（``last_seen``
    前移），变化即新版本，新版本的 ``supersedes`` 指向上一版 hash——替代关系可见。
    """
    versions: list[dict[str, Any]] = []
    for snap in available_snapshots(root):
        data = load_snapshot_data(root, snap)
        row = _find_row(data.get(table) or [], match)
        if row is None:
            continue
        clean = _strip_annotations(row)
        digest = content_hash(row)
        if versions and versions[-1]["content_sha256"] == digest:
            versions[-1]["last_seen_snapshot"] = snap
            continue
        versions.append(
            {
                "content_sha256": digest,
                "first_seen_snapshot": snap,
                "last_seen_snapshot": snap,
                "supersedes": versions[-1]["content_sha256"] if versions else None,
                "payload": clean,
            }
        )
    current: dict[str, Any] | None = None
    if db_path is not None:
        current = _current_row(db_path, table, match)
    return {
        "table": table,
        "match": {k: _norm_value(v) for k, v in match.items()},
        "versions": versions,
        "current": current,
        "current_matches_version": (
            content_hash(current) == versions[-1]["content_sha256"] if current and versions else None
        ),
    }


def _norm_value(value: Any) -> str:
    return str(value)[:10] if _looks_like_date(value) else str(value)


def _looks_like_date(value: Any) -> bool:
    s = str(value)
    return len(s) >= 10 and s[4:5] == "-" and s[7:8] == "-"


def _find_row(rows: list[dict[str, Any]], match: dict[str, Any]) -> dict[str, Any] | None:
    for row in rows:
        ok = True
        for key, want in match.items():
            got = row.get(key)
            if got is None or _norm_value(got) != _norm_value(want):
                ok = False
                break
        if ok:
            return row
    return None


def _current_row(db_path: str | Path, table: str, match: dict[str, Any]) -> dict[str, Any] | None:
    con = duckdb.connect(str(Path(db_path).expanduser()), read_only=True)
    try:
        where = " AND ".join(f'CAST("{k}" AS VARCHAR) LIKE ?' for k in match)
        params = [f"{_norm_value(v)}%" for v in match.values()]
        cur = con.execute(f'SELECT * FROM "{table}" WHERE {where} LIMIT 1', params)  # noqa: S608 —— 表名/列名来自调用方白名单
        cols = [d[0] for d in cur.description]
        row = cur.fetchone()
        return dict(zip(cols, row, strict=True)) if row else None
    finally:
        con.close()
