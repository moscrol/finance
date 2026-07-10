#!/usr/bin/env python3
"""把 db_delta_export.py 导出的单日增量 zip 幂等合并进本地 DuckDB。

用途：另一台电脑收到当天的 mfs-delta-<date>.zip 后，跑这个脚本就把当天的 fact 行
合并进它本地的 market_feature_store.duckdb，之后所有复盘/查询 skill 都能看到今天的数据。

幂等原理：对每张表，先 `DELETE WHERE trade_date = 当天` 再 `INSERT`，所以同一个包
重复导多次结果一致，不会重复累加。整个过程包在一个事务里，要么全成要么全不动。

数据契约与 fail-fast（本脚本的核心安全边界）：
- **安全解压**：zip 内成员若含绝对路径或 `..` 逃逸，直接拒绝（防目录穿越写坏宿主文件系统）。
- **schema_version**：manifest 必须带受支持的契约版本，旧/未来不兼容包一律拒绝，不静默降级。
- **完整性**：每个 parquet 的 SHA-256 必须与 manifest 记录一致；manifest 声明的文件必须存在。
- **一致性**：parquet 实际行数 == manifest rows；日期列每一行都等于 manifest trade_date（防串日期）；
  目标库必须已有同名表且 schema 兼容（parquet 列 ⊆ 目标表列）。
- **零行更正**：manifest 里 rows=0 的分区表也会执行 DELETE，把目标从「非零」修正为「零」。
- **导入后自检**：写入后重新点当天行数，必须 == manifest rows（rows=0 则必须 == 0）。
- 以上任何一条不满足 → 抛异常 → 事务 rollback → 退出码非 0；**绝不 skip 后报成功**。

技术选型 / 替代方案对比（教学）：
- `INSERT INTO t BY NAME SELECT * FROM read_parquet(...)`：`BY NAME` 按列名对齐，
  两边列顺序不同也不会错位（比按位置 INSERT 稳）；前提是目标表已存在同名 schema。
- delete+insert vs `INSERT OR REPLACE`/MERGE：DuckDB 的 upsert 依赖主键约束，而这些
  fact 表大多没声明主键，所以用「按分区键 delete 再 insert」最稳、最好懂，也天然幂等。
- 要求目标库已有表结构：单日增量不负责建表/迁移 schema。第一次在新机器上，应先用整库
  快照（db_delta_export 的整库 zip / EXPORT DATABASE）建好底库，之后再每天打增量。

可复用知识点：分区表的增量同步普遍用「同一分区先删后插 + 事务」保证幂等，离线数仓、
特征平台、报表库都这么做；配合「manifest + 每文件校验和 + 导入后自检」形成端到端数据契约。
"""
from __future__ import annotations
import argparse, hashlib, json, os, re, sys, tempfile, zipfile
import duckdb

# 复用 export 端的表发现逻辑，保证「可参与单日增量的表集合」两端语义一致。
# 兼容两种运行方式：作为脚本（scripts/ 在 sys.path）与作为包（from scripts import ...）。
try:
    from scripts import db_delta_export as _exp
except ImportError:  # pragma: no cover - 脚本直跑时的退路
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import db_delta_export as _exp

# 能识别的 manifest 契约版本集合（见 db_delta_export.SCHEMA_VERSION）。
# 只接受明确在列的版本；0 / 负数 / 未来版本均拒绝，不静默降级。
SUPPORTED_SCHEMA_VERSIONS = frozenset({1})

_HEX64 = re.compile(r"\A[0-9a-f]{64}\Z")


class DeltaImportError(Exception):
    """包级数据契约校验失败（安全/完整性/一致性任一不满足）。"""


def _qi(name: str) -> str:
    """把标识符（表名/列名）安全地双引号 quote，防止 manifest 插值注入。"""
    if not isinstance(name, str) or '"' in name or "\x00" in name:
        raise DeltaImportError(f"非法标识符: {name!r}")
    return '"' + name + '"'


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _resolve_member(tmp: str, fn: str) -> str:
    """把 manifest 里的 file 字段解析成解压目录内的真实路径。

    拒绝绝对路径 / `..` 逆回 / 指向解压目录外；只允许包内普通文件（非目录/非符链）。
    """
    if not isinstance(fn, str) or not fn:
        raise DeltaImportError(f"非法文件名: {fn!r}")
    if os.path.isabs(fn) or fn.startswith(("/", "\\")) or (len(fn) >= 2 and fn[1] == ":"):
        raise DeltaImportError(f"file 字段含绝对路径，拒绝: {fn!r}")
    troot = os.path.realpath(tmp)
    target = os.path.realpath(os.path.join(tmp, fn))
    if target != troot and not target.startswith(troot + os.sep):
        raise DeltaImportError(f"file 字段越出解压目录（目录穿越），拒绝: {fn!r}")
    if os.path.islink(target) or not os.path.isfile(target):
        raise DeltaImportError(f"file 字段非包内普通文件，拒绝: {fn!r}")
    return target


def safe_extract(zip_path: str, dest: str) -> None:
    """把 zip 解压到 dest，拒绝任何绝对路径 / `..` 目录穿越成员。"""
    dest_real = os.path.realpath(dest)
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            if name.endswith("/"):
                continue  # 目录条目
            # 绝对路径（含 Windows 盘符 / UNC）或以分隔符开头 → 拒绝
            if os.path.isabs(name) or name.startswith(("/", "\\")) or (
                    len(name) >= 2 and name[1] == ":"):
                raise DeltaImportError(f"zip 含绝对路径成员，拒绝: {name!r}")
            target = os.path.realpath(os.path.join(dest, name))
            if target != dest_real and not target.startswith(dest_real + os.sep):
                raise DeltaImportError(f"zip 成员越出解压目录（目录穿越），拒绝: {name!r}")
        z.extractall(dest)


def _load_manifest(tmp: str) -> dict:
    mpath = os.path.join(tmp, "manifest.json")
    if not os.path.exists(mpath):
        raise DeltaImportError("包内缺少 manifest.json")
    with open(mpath) as f:
        man = json.load(f)
    ver = man.get("schema_version")
    if ver is None:
        raise DeltaImportError(
            "manifest 缺少 schema_version（旧格式不兼容，请用新版 db_delta_export.py 重新导出）")
    # 只接受明确支持的版本；bool 是 int 子类需单独排除。0/负数/未知版本一律拒绝。
    if isinstance(ver, bool) or not isinstance(ver, int) or ver not in SUPPORTED_SCHEMA_VERSIONS:
        raise DeltaImportError(
            f"manifest schema_version={ver!r} 不在支持集合 {sorted(SUPPORTED_SCHEMA_VERSIONS)}")
    if "trade_date" not in man or "tables" not in man:
        raise DeltaImportError("manifest 缺少 trade_date / tables 字段")
    if not _exp.is_iso_date(man["trade_date"]):
        raise DeltaImportError(
            f"manifest trade_date 非严格 ISO YYYY-MM-DD: {man['trade_date']!r}")
    if not isinstance(man["tables"], list):
        raise DeltaImportError("manifest tables 必须是列表")
    return man


def _validate_entry(con, tmp: str, date: str, item: dict, existing: set[str]) -> None:
    """对单张表做导入前的契约校验（不写库）。任何不一致 → 抛 DeltaImportError。"""
    t = item.get("table")
    dc = item.get("date_col")
    rows = item.get("rows")
    if not isinstance(t, str) or not t or not isinstance(dc, str) or not dc:
        raise DeltaImportError(f"manifest 表项字段不完整: {item!r}")
    # rows 必须是非负整数（bool 是 int 子类，单独排除）
    if isinstance(rows, bool) or not isinstance(rows, int) or rows < 0:
        raise DeltaImportError(f"表 {t} rows 非法（需非负整数）: {rows!r}")

    # 目标缺表 → fail-fast（不 skip）
    if t not in existing:
        raise DeltaImportError(f"目标库无表 {t}（schema 不匹配，先用整库快照建底库）")

    target_cols = {r[0] for r in con.execute(
        "select column_name from information_schema.columns where table_name=?",
        [t]).fetchall()}
    if dc not in target_cols:
        raise DeltaImportError(f"表 {t} 目标库无日期列 {dc}")

    if rows == 0:
        # 零行分区表：不该带文件；仅登记以便把目标从非零修正为零
        if item.get("file"):
            raise DeltaImportError(f"表 {t} rows=0 却带了文件 {item['file']}")
        return

    # v1 非零表：sha256 / columns 必须存在（不允许缺失后静默跳过校验）
    fn = item.get("file")
    if not fn:
        raise DeltaImportError(f"表 {t} rows={rows} 但 manifest 未记录文件名")
    pq = _resolve_member(tmp, fn)

    want_sha = item.get("sha256")
    if not isinstance(want_sha, str) or not _HEX64.match(want_sha):
        raise DeltaImportError(f"表 {t} sha256 缺失或格式非法（需 64 位小写十六进制）: {want_sha!r}")
    got_sha = _sha256(pq)
    if got_sha != want_sha:
        raise DeltaImportError(
            f"表 {t} 文件 {fn} SHA-256 不匹配（期望 {want_sha[:12]}… 实得 {got_sha[:12]}…）")

    man_cols = item.get("columns")
    if not isinstance(man_cols, list) or not man_cols or not all(
            isinstance(c, str) for c in man_cols):
        raise DeltaImportError(f"表 {t} manifest columns 缺失或非法")

    pql = pq.replace("'", "''")
    # manifest columns 必须与 parquet 实际列（名称与顺序）完全一致
    pq_cols = [d[0] for d in con.execute(
        "select * from read_parquet('%s') limit 0" % pql).description]
    if pq_cols != man_cols:
        raise DeltaImportError(
            f"表 {t} manifest columns 与 parquet 实际列不一致：manifest={man_cols} parquet={pq_cols}")

    # schema 兼容：parquet 列必须都在目标表里（否则 INSERT BY NAME 会失败/漂移）
    drift = [c for c in pq_cols if c not in target_cols]
    if drift:
        raise DeltaImportError(f"表 {t} schema drift：parquet 多出目标库没有的列 {drift}")

    # parquet 实际行数 == manifest rows
    actual = con.execute("select count(*) from read_parquet('%s')" % pql).fetchone()[0]
    if actual != rows:
        raise DeltaImportError(f"表 {t} 行数不符：manifest {rows} 行，parquet 实有 {actual} 行")

    # 日期列每一行都必须等于 manifest trade_date（防混入其它日期 / NULL）
    bad = con.execute(
        'select count(*) from read_parquet(\'%s\') where %s is null or cast(%s as varchar) <> ?'
        % (pql, _qi(dc), _qi(dc)), [date]).fetchone()[0]
    if bad:
        raise DeltaImportError(
            f"表 {t} 有 {bad} 行日期列 {dc} 为 NULL 或不等于 manifest trade_date {date}（串日期）")


def import_delta(zip_path: str, db_path: str, dry_run: bool = False,
                 allow_partial: bool = False) -> dict:
    """校验并把单日增量 zip 幂等合并进本地 DuckDB。返回摘要 dict；不一致时抛异常。

    allow_partial=False（默认）时，只接受「当日完整日期分区表集」包；partial 子集包
    （export 用 --tables / --include-skipped 产出）必须显式 allow_partial=True 才导入。
    """
    if not os.path.exists(zip_path):
        raise DeltaImportError(f"zip 不存在: {zip_path}")
    if not os.path.exists(db_path):
        raise DeltaImportError(f"目标 DB 不存在: {db_path}（请先用整库快照建底库）")

    tmp = tempfile.mkdtemp(prefix="mfs-delta-")
    con = None
    try:
        safe_extract(zip_path, tmp)
        man = _load_manifest(tmp)
        date = man["trade_date"]
        kind = "partial 子集" if man.get("partial") else "完整表集"
        print(f"[*] 增量日期 {date}，contract v{man['schema_version']}（{kind}），"
              f"{len(man['tables'])} 张表，目标库 {db_path}"
              + ("  (dry-run)" if dry_run else ""))

        con = duckdb.connect(db_path, read_only=dry_run)
        existing = {r[0] for r in con.execute(
            "select table_name from information_schema.tables "
            "where table_schema='main'").fetchall()}

        # 拒绝重复 table / 重复 file（同一包里重复会让 delete+insert 语义不确定）
        seen_tables: set[str] = set()
        seen_files: set[str] = set()
        for item in man["tables"]:
            t = item.get("table")
            if t in seen_tables:
                raise DeltaImportError(f"manifest 重复表项: {t}")
            seen_tables.add(t)
            f = item.get("file")
            if f:
                if f in seen_files:
                    raise DeltaImportError(f"manifest 重复文件: {f}")
                seen_files.add(f)

        # 完整表集合契约：
        #  - 完整包（partial=false）：manifest 表集合必须与目标库「可参与单日增量的表集合」
        #    完全一致——漏表（少同步一张 → 目标留过期数据）或额外表都 fail-fast。
        #  - 子集包（partial=true，来自 --tables / --include-skipped）：只有显式 --allow-partial
        #    才接受，否则拒绝，防止子集包被误当成完整同步。
        partial = bool(man.get("partial"))
        if partial:
            if not allow_partial:
                raise DeltaImportError(
                    "manifest 标记 partial（子集导出），需显式 --allow-partial 才能导入")
        else:
            eligible = {t for t, _dc in _exp.discover_tables(con, include_skipped=False)}
            missing = eligible - seen_tables
            extra = seen_tables - eligible
            if missing or extra:
                raise DeltaImportError(
                    "完整包表集合与目标库不一致（"
                    f"漏表={sorted(missing)} 额外表={sorted(extra)}）；"
                    "如确为子集，请用 --tables 导出并以 --allow-partial 导入")

        # 先全量校验（fail-fast）：任一表不过关就在写任何库之前直接失败
        for item in man["tables"]:
            _validate_entry(con, tmp, date, item, existing)

        if dry_run:
            for item in man["tables"]:
                t, dc, rows = item["table"], item["date_col"], item["rows"]
                before = con.execute(
                    "select count(*) from %s where cast(%s as varchar)=?"
                    % (_qi(t), _qi(dc)), [date]).fetchone()[0]
                print(f"  {t:42s} 现有当天 {before} 行 → 将替换为包内 {rows} 行")
            print("[dry-run] 未写库")
            return {"trade_date": date, "applied": 0, "dry_run": True,
                    "tables": len(man["tables"])}

        applied = 0
        con.execute("begin transaction")
        try:
            for item in man["tables"]:
                t, dc, rows = item["table"], item["date_col"], item["rows"]
                before = con.execute(
                    "select count(*) from %s where cast(%s as varchar)=?"
                    % (_qi(t), _qi(dc)), [date]).fetchone()[0]
                # 幂等 + 零行更正：无论包内 rows 是否为 0，都先删当天分区
                con.execute("delete from %s where cast(%s as varchar)=?"
                            % (_qi(t), _qi(dc)), [date])
                if rows > 0:
                    pql = _resolve_member(tmp, item["file"]).replace("'", "''")
                    con.execute(
                        "insert into %s by name select * from read_parquet('%s')"
                        % (_qi(t), pql))
                after = con.execute(
                    "select count(*) from %s where cast(%s as varchar)=?"
                    % (_qi(t), _qi(dc)), [date]).fetchone()[0]
                # 导入后自检：当天行数必须精确等于 manifest rows
                if after != rows:
                    raise DeltaImportError(
                        f"表 {t} 导入后自检失败：期望 {rows} 行，实得 {after} 行")
                tag = "" if rows else "  (零行更正)"
                print(f"  {t:42s} {before:>8} → {after:>8} 行{tag}")
                applied += 1
            con.execute("commit")
        except Exception:
            con.execute("rollback")
            raise
        print(f"\n[ok] 已合并 {applied} 张表的 {date} 增量进 {db_path}")
        return {"trade_date": date, "applied": applied, "dry_run": False,
                "tables": len(man["tables"])}
    finally:
        if con is not None:
            con.close()
        for root, _dirs, files in os.walk(tmp, topdown=False):
            for fn in files:
                os.remove(os.path.join(root, fn))
            if root != tmp:
                os.rmdir(root)
        os.rmdir(tmp)


def main() -> int:
    ap = argparse.ArgumentParser(description="把单日增量 zip 合并进本地 DuckDB（幂等 + 数据契约校验）")
    ap.add_argument("--zip", required=True, help="db_delta_export.py 产出的 zip")
    ap.add_argument("--db", default="db/market_feature_store.duckdb")
    ap.add_argument("--dry-run", action="store_true", help="只校验并打印将要做的操作，不写库")
    ap.add_argument("--allow-partial", action="store_true",
                    help="接受 partial 子集包（export 用 --tables/--include-skipped 产出）；"
                         "默认只接受当日完整表集包")
    a = ap.parse_args()
    try:
        import_delta(a.zip, a.db, dry_run=a.dry_run, allow_partial=a.allow_partial)
    except DeltaImportError as e:
        print(f"[err] 数据契约校验失败，未写库: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
