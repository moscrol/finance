"""统一检索缓存（TTL）与 DuckDB per-run 连接复用。"""

import tempfile
import unittest
from pathlib import Path

from intelligence.services import ask_planner, retrieval_cache


class RetrievalCacheTests(unittest.TestCase):
    def test_put_get_roundtrip_and_normalized_query(self) -> None:
        cache = retrieval_cache.RetrievalCache()
        cache.put("duckdb", "AI 算力", {"rows": 1}, as_of_date="2026-07-18")
        self.assertEqual(
            cache.get("duckdb", "ai算力", as_of_date="2026-07-18"),
            {"rows": 1},
        )

    def test_as_of_date_isolation(self) -> None:
        cache = retrieval_cache.RetrievalCache()
        cache.put("duckdb", "q", "old", as_of_date="2026-07-17")
        self.assertIsNone(cache.get("duckdb", "q", as_of_date="2026-07-18"))

    def test_revision_isolation(self) -> None:
        cache = retrieval_cache.RetrievalCache()
        cache.put("wiki", "q", "hit", revision="rev1")
        self.assertIsNone(cache.get("wiki", "q", revision="rev2"))
        self.assertEqual(cache.get("wiki", "q", revision="rev1"), "hit")

    def test_ttl_expiry(self) -> None:
        cache = retrieval_cache.RetrievalCache()
        cache.put("duckdb", "q", "v", ttl_seconds=-1)
        self.assertIsNone(cache.get("duckdb", "q"))


class DuckDBRunPoolTests(unittest.TestCase):
    def _make_db(self, tmp: str) -> Path:
        import duckdb

        db_path = Path(tmp) / "pool.duckdb"
        con = duckdb.connect(str(db_path))
        con.execute("create table t(x int)")
        con.execute("insert into t values (42)")
        con.close()
        return db_path

    def test_pool_reuses_one_connection_per_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = self._make_db(tmp)
            with retrieval_cache.duckdb_run_pool() as pool:
                c1 = retrieval_cache.connect_readonly(db_path)
                c2 = retrieval_cache.connect_readonly(db_path)
                self.assertEqual(c1.execute("select x from t").fetchone()[0], 42)
                self.assertEqual(c2.execute("select x from t").fetchone()[0], 42)
                c1.close()  # 关 cursor 不影响底层连接
                self.assertEqual(len(pool._connections), 1)
                c3 = retrieval_cache.connect_readonly(db_path)
                self.assertEqual(c3.execute("select x from t").fetchone()[0], 42)

    def test_fallback_without_pool_opens_standalone_connection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = self._make_db(tmp)
            con = retrieval_cache.connect_readonly(db_path)
            self.assertEqual(con.execute("select x from t").fetchone()[0], 42)
            con.close()

    def test_pool_propagates_into_parallel_block_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = self._make_db(tmp)

            def build() -> tuple[str, None]:
                con = retrieval_cache.connect_readonly(db_path)
                value = con.execute("select x from t").fetchone()[0]
                con.close()
                return str(value), None

            with retrieval_cache.duckdb_run_pool() as pool:
                outcomes = ask_planner.run_block_tasks(
                    [
                        ask_planner.BlockTask("D0", "a", build),
                        ask_planner.BlockTask("D1", "b", build),
                    ],
                    parallel=True,
                )
                self.assertEqual([o.block for o in outcomes], ["42", "42"])
                # 并行线程借用同一个底层连接（contextvars 已随 copy_context 传播）
                self.assertEqual(len(pool._connections), 1)


if __name__ == "__main__":
    unittest.main()
