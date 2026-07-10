#!/usr/bin/env python3
"""db_delta_export.py / db_delta_import.py 包级数据契约测试。

覆盖：正常往返、重复导入幂等、rollback、缺表、schema drift、rows mismatch、
混入其它日期、零行更正、zip 目录穿越、SHA-256 篡改。
"""
from __future__ import annotations
import json
import os
import sys
import zipfile
import unittest
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import duckdb  # noqa: E402
from scripts import db_delta_export as exp  # noqa: E402
from scripts.db_delta_import import (  # noqa: E402
    import_delta, safe_extract, DeltaImportError,
)

DATE = "2026-07-10"
OTHER = "2026-07-09"


def _build_db(path: str) -> None:
    con = duckdb.connect(path)
    con.execute("create table fact_a (trade_date varchar, val integer)")
    con.execute("create table fact_b (trade_date varchar, name varchar)")
    con.execute("create table fact_c (trade_date varchar, x integer)")
    # 当天数据
    con.execute("insert into fact_a values (?, 1), (?, 2)", [DATE, DATE])
    con.execute("insert into fact_b values (?, 'aa')", [DATE])
    # 其它日期（不该被单日增量带走）
    con.execute("insert into fact_a values (?, 9)", [OTHER])
    con.execute("insert into fact_c values (?, 5)", [OTHER])  # 当天 fact_c = 0 行
    con.close()


def _export(db: str, out_zip: str) -> None:
    argv = ["db_delta_export.py", "--trade-date", DATE, "--db", db, "--out", out_zip]
    old = sys.argv
    sys.argv = argv
    try:
        rc = exp.main()
    finally:
        sys.argv = old
    assert rc == 0, rc


def _repack(src_zip: str, dst_zip: str, mutate):
    """解包 → 交给 mutate(dir) 改内容 → 重新打包。"""
    d = tempfile.mkdtemp()
    try:
        with zipfile.ZipFile(src_zip) as z:
            z.extractall(d)
        mutate(d)
        with zipfile.ZipFile(dst_zip, "w", zipfile.ZIP_DEFLATED) as z:
            for fn in os.listdir(d):
                z.write(os.path.join(d, fn), fn)
    finally:
        shutil.rmtree(d)


def _read_manifest(zip_path: str) -> dict:
    with zipfile.ZipFile(zip_path) as z:
        return json.loads(z.read("manifest.json"))


class DeltaContractTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = os.path.join(self.tmp, "mfs.duckdb")
        self.zip = os.path.join(self.tmp, "delta.zip")
        _build_db(self.db)
        _export(self.db, self.zip)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _count(self, table, date=DATE):
        con = duckdb.connect(self.db, read_only=True)
        try:
            return con.execute(
                'select count(*) from "%s" where cast("trade_date" as varchar)=?'
                % table, [date]).fetchone()[0]
        finally:
            con.close()

    # ---- 正常往返 & 零行登记 ----
    def test_manifest_records_zero_row_table(self):
        man = _read_manifest(self.zip)
        self.assertEqual(man["schema_version"], exp.SCHEMA_VERSION)
        by = {e["table"]: e for e in man["tables"]}
        self.assertEqual(by["fact_a"]["rows"], 2)
        self.assertEqual(by["fact_b"]["rows"], 1)
        # fact_c 当天 0 行，仍必须登记，且不带文件
        self.assertIn("fact_c", by)
        self.assertEqual(by["fact_c"]["rows"], 0)
        self.assertIsNone(by["fact_c"]["file"])
        self.assertTrue(by["fact_a"]["sha256"])

    def test_roundtrip_into_empty_target(self):
        # 清空当天数据后重新导入 → 恢复
        con = duckdb.connect(self.db)
        con.execute("delete from fact_a where trade_date=?", [DATE])
        con.execute("delete from fact_b where trade_date=?", [DATE])
        con.close()
        res = import_delta(self.zip, self.db)
        self.assertEqual(res["applied"], 3)
        self.assertEqual(self._count("fact_a"), 2)
        self.assertEqual(self._count("fact_b"), 1)
        # 其它日期不受影响
        self.assertEqual(self._count("fact_a", OTHER), 1)

    def test_repeated_import_is_idempotent(self):
        import_delta(self.zip, self.db)
        import_delta(self.zip, self.db)
        import_delta(self.zip, self.db)
        self.assertEqual(self._count("fact_a"), 2)
        self.assertEqual(self._count("fact_b"), 1)

    # ---- 零行更正：目标非零 → 改成零 ----
    def test_zero_row_correction(self):
        con = duckdb.connect(self.db)
        con.execute("insert into fact_c values (?, 111), (?, 222)", [DATE, DATE])
        con.close()
        self.assertEqual(self._count("fact_c"), 2)
        import_delta(self.zip, self.db)
        self.assertEqual(self._count("fact_c"), 0)  # 被更正为零

    # ---- 缺表 → fail-fast + rollback ----
    def test_missing_table_fails_and_rolls_back(self):
        con = duckdb.connect(self.db)
        con.execute("delete from fact_a where trade_date=?", [DATE])  # 制造可观测差异
        con.execute("drop table fact_b")
        con.close()
        with self.assertRaises(DeltaImportError):
            import_delta(self.zip, self.db)
        # rollback：fact_a 当天仍是 0（没有因为部分成功而被写入）
        self.assertEqual(self._count("fact_a"), 0)

    # ---- rows mismatch ----
    def test_rows_mismatch_fails(self):
        bad = os.path.join(self.tmp, "bad.zip")

        def mut(d):
            m = json.load(open(os.path.join(d, "manifest.json")))
            for e in m["tables"]:
                if e["table"] == "fact_a":
                    e["rows"] = 99
            json.dump(m, open(os.path.join(d, "manifest.json"), "w"))
        _repack(self.zip, bad, mut)
        with self.assertRaises(DeltaImportError):
            import_delta(bad, self.db)

    # ---- 混入其它日期 ----
    def test_foreign_date_row_fails(self):
        bad = os.path.join(self.tmp, "bad.zip")

        def mut(d):
            # 往 fact_a.parquet 里塞一行其它日期，并同步 manifest rows / sha256
            pq = os.path.join(d, "fact_a.parquet")
            c = duckdb.connect()
            c.execute("create table t as select * from read_parquet('%s')" % pq)
            c.execute("insert into t values (?, 7)", [OTHER])
            os.remove(pq)
            c.execute("copy t to '%s' (format parquet)" % pq)
            c.close()
            m = json.load(open(os.path.join(d, "manifest.json")))
            for e in m["tables"]:
                if e["table"] == "fact_a":
                    e["rows"] = 3
                    e["sha256"] = exp._sha256(pq)
            json.dump(m, open(os.path.join(d, "manifest.json"), "w"))
        _repack(self.zip, bad, mut)
        with self.assertRaises(DeltaImportError):
            import_delta(bad, self.db)

    # ---- schema drift：parquet 多列，目标库没有 ----
    def test_schema_drift_fails(self):
        con = duckdb.connect(self.db)
        con.execute("alter table fact_a drop column val")  # 目标库少了 val 列
        con.close()
        with self.assertRaises(DeltaImportError):
            import_delta(self.zip, self.db)

    # ---- SHA-256 篡改 ----
    def test_sha256_tamper_fails(self):
        bad = os.path.join(self.tmp, "bad.zip")

        def mut(d):
            m = json.load(open(os.path.join(d, "manifest.json")))
            for e in m["tables"]:
                if e["table"] == "fact_a":
                    e["sha256"] = "0" * 64
            json.dump(m, open(os.path.join(d, "manifest.json"), "w"))
        _repack(self.zip, bad, mut)
        with self.assertRaises(DeltaImportError):
            import_delta(bad, self.db)

    # ---- schema_version 缺失 / 超前 ----
    def test_missing_schema_version_fails(self):
        bad = os.path.join(self.tmp, "bad.zip")

        def mut(d):
            m = json.load(open(os.path.join(d, "manifest.json")))
            m.pop("schema_version", None)
            json.dump(m, open(os.path.join(d, "manifest.json"), "w"))
        _repack(self.zip, bad, mut)
        with self.assertRaises(DeltaImportError):
            import_delta(bad, self.db)

    def test_future_schema_version_fails(self):
        bad = os.path.join(self.tmp, "bad.zip")

        def mut(d):
            m = json.load(open(os.path.join(d, "manifest.json")))
            m["schema_version"] = exp.SCHEMA_VERSION + 99
            json.dump(m, open(os.path.join(d, "manifest.json"), "w"))
        _repack(self.zip, bad, mut)
        with self.assertRaises(DeltaImportError):
            import_delta(bad, self.db)


class SafeExtractTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_rejects_parent_traversal(self):
        zp = os.path.join(self.tmp, "evil.zip")
        with zipfile.ZipFile(zp, "w") as z:
            z.writestr("../escape.txt", "pwned")
        dest = os.path.join(self.tmp, "out")
        os.makedirs(dest)
        with self.assertRaises(DeltaImportError):
            safe_extract(zp, dest)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "escape.txt")))

    def test_rejects_absolute_path(self):
        zp = os.path.join(self.tmp, "evil2.zip")
        with zipfile.ZipFile(zp, "w") as z:
            z.writestr("/tmp/abs_escape.txt", "pwned")
        dest = os.path.join(self.tmp, "out2")
        os.makedirs(dest)
        with self.assertRaises(DeltaImportError):
            safe_extract(zp, dest)

    def test_allows_normal_members(self):
        zp = os.path.join(self.tmp, "ok.zip")
        with zipfile.ZipFile(zp, "w") as z:
            z.writestr("manifest.json", "{}")
            z.writestr("fact_a.parquet", "data")
        dest = os.path.join(self.tmp, "out3")
        os.makedirs(dest)
        safe_extract(zp, dest)
        self.assertTrue(os.path.exists(os.path.join(dest, "manifest.json")))


if __name__ == "__main__":
    unittest.main()
