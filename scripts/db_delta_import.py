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
import argparse, hashlib, json, os, sys, tempfile, zipfile
import duckdb

# 能识别的最高 manifest 契约版本（见 db_delta_export.SCHEMA_VERSION）。
SUPPORTED_SCHEMA_VERSION = 1


class DeltaImportError(Exception):
    """包级数据契约校验失败（安全/完整性/一致性任一不满足）。"""


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


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
    if not isinstance(ver, int) or ver > SUPPORTED_SCHEMA_VERSION:
        raise DeltaImportError(
            f"manifest schema_version={ver} 超出支持范围（本脚本最高 {SUPPORTED_SCHEMA_VERSION}）")
    if "trade_date" not in man or "tables" not in man:
        raise DeltaImportError("manifest 缺少 trade_date / tables 字段")
    return man


def _validate_entry(con, tmp: str, date: str, item: dict, existing: set[str]) -> None:
    """对单张表做导入前的契约校验（不写库）。任何不一致 → 抛 DeltaImportError。"""
    t = item.get("table")
    dc = item.get("date_col")
    rows = item.get("rows")
    if not t or not dc or rows is None:
        raise DeltaImportError(f"manifest 表项字段不完整: {item!r}")

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

    fn = item.get("file")
    if not fn:
        raise DeltaImportError(f"表 {t} rows={rows} 但 manifest 未记录文件名")
    pq = os.path.join(tmp, fn)
    if not os.path.exists(pq):
        raise DeltaImportError(f"表 {t} 声明的文件缺失: {fn}")

    # SHA-256 完整性
    want_sha = item.get("sha256")
    if want_sha:
        got_sha = _sha256(pq)
        if got_sha != want_sha:
            raise DeltaImportError(
                f"表 {t} 文件 {fn} SHA-256 不匹配（期望 {want_sha[:12]}… 实得 {got_sha[:12]}…）")

    pql = pq.replace("'", "''")
    # schema 兼容：parquet 列必须都在目标表里（否则 INSERT BY NAME 会失败/漂移）
    pq_cols = [d[0] for d in con.execute(
        "select * from read_parquet('%s') limit 0" % pql).description]
    drift = [c for c in pq_cols if c not in target_cols]
    if drift:
        raise DeltaImportError(f"表 {t} schema drift：parquet 多出目标库没有的列 {drift}")

    # parquet 实际行数 == manifest rows
    actual = con.execute("select count(*) from read_parquet('%s')" % pql).fetchone()[0]
    if actual != rows:
        raise DeltaImportError(f"表 {t} 行数不符：manifest {rows} 行，parquet 实有 {actual} 行")

    # 日期列每一行都必须等于 manifest trade_date（防混入其它日期）
    bad = con.execute(
        'select count(*) from read_parquet(\'%s\') where cast("%s" as varchar) <> ?'
        % (pql, dc), [date]).fetchone()[0]
    if bad:
        raise DeltaImportError(
            f"表 {t} 有 {bad} 行日期列 {dc} 不等于 manifest trade_date {date}（串日期）")


def import_delta(zip_path: str, db_path: str, dry_run: bool = False) -> dict:
    """校验并把单日增量 zip 幂等合并进本地 DuckDB。返回摘要 dict；不一致时抛异常。"""
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
        print(f"[*] 增量日期 {date}，contract v{man['schema_version']}，"
              f"{len(man['tables'])} 张表，目标库 {db_path}"
              + ("  (dry-run)" if dry_run else ""))

        con = duckdb.connect(db_path, read_only=dry_run)
        existing = {r[0] for r in con.execute(
            "select table_name from information_schema.tables "
            "where table_schema='main'").fetchall()}

        # 先全量校验（fail-fast）：任一表不过关就在写任何库之前直接失败
        for item in man["tables"]:
            _validate_entry(con, tmp, date, item, existing)

        if dry_run:
            for item in man["tables"]:
                t, dc, rows = item["table"], item["date_col"], item["rows"]
                before = con.execute(
                    'select count(*) from "%s" where cast("%s" as varchar)=?'
                    % (t, dc), [date]).fetchone()[0]
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
                    'select count(*) from "%s" where cast("%s" as varchar)=?'
                    % (t, dc), [date]).fetchone()[0]
                # 幂等 + 零行更正：无论包内 rows 是否为 0，都先删当天分区
                con.execute('delete from "%s" where cast("%s" as varchar)=?'
                            % (t, dc), [date])
                if rows > 0:
                    pql = os.path.join(tmp, item["file"]).replace("'", "''")
                    con.execute(
                        'insert into "%s" by name select * from read_parquet(\'%s\')'
                        % (t, pql))
                after = con.execute(
                    'select count(*) from "%s" where cast("%s" as varchar)=?'
                    % (t, dc), [date]).fetchone()[0]
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
    a = ap.parse_args()
    try:
        import_delta(a.zip, a.db, dry_run=a.dry_run)
    except DeltaImportError as e:
        print(f"[err] 数据契约校验失败，未写库: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
