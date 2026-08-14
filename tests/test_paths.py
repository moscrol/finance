import importlib
import os
import unittest
from pathlib import Path
from unittest.mock import patch


class DefaultPathsTest(unittest.TestCase):
    def _default_paths_with_env(self, env, home=None):
        keys = {
            "FINANCE_WS",
            "FINANCE_ROOT",
            "KB_VAULT",
            "KNOWLEDGE_WIKI",
            "CONCEPT_VAULT",
            "ENTITY_VAULT",
            "FINANCE_SITE",
            "MARKET_SNAPSHOT_DIR",
            "VECTOR_INDEX_DIR",
            "RAG_INDEX_DIR",
            # data_repo_root() 也读这个变量——不清掉就测不到真正的回退行为
            "WORKBENCH_REPO_ROOT",
        }
        clean_env = {key: value for key, value in os.environ.items() if key not in keys}
        clean_env.update(env)
        with patch.dict(os.environ, clean_env, clear=True):
            import intelligence.paths as paths
            importlib.reload(paths)
            if home is not None:
                with patch.object(paths.Path, "home", return_value=Path(home)):
                    return paths.default_paths()
            return paths.default_paths()

    def test_prefers_finance_ws_and_kb_vault(self):
        paths = self._default_paths_with_env({
            "FINANCE_WS": "/tmp/finance-ws",
            "FINANCE_ROOT": "/tmp/finance-root",
            "KB_VAULT": "/tmp/kb-vault/wiki",
            "KNOWLEDGE_WIKI": "/tmp/knowledge-wiki",
        })

        self.assertEqual(paths.finance_root, Path("/tmp/finance-ws"))
        self.assertEqual(paths.knowledge_wiki, Path("/tmp/kb-vault/wiki"))

    def test_market_snapshot_dir_env_override(self):
        paths = self._default_paths_with_env({
            "MARKET_SNAPSHOT_DIR": "/tmp/market-snapshot",
        })

        self.assertEqual(paths.market_snapshot_dir, Path("/tmp/market-snapshot"))

    def test_vector_index_dir_env_override(self):
        paths = self._default_paths_with_env({
            "VECTOR_INDEX_DIR": "/tmp/vector-index",
            "RAG_INDEX_DIR": "/tmp/rag-index",
        })

        self.assertEqual(paths.vector_index_dir, Path("/tmp/vector-index"))

    def test_keeps_legacy_env_names(self):
        paths = self._default_paths_with_env({
            "FINANCE_ROOT": "/tmp/finance-root",
            "KNOWLEDGE_WIKI": "/tmp/knowledge-wiki",
        })

        self.assertEqual(paths.finance_root, Path("/tmp/finance-root"))
        self.assertEqual(paths.knowledge_wiki, Path("/tmp/knowledge-wiki"))

    def test_knowledge_alias_precedence_after_kb_vault(self):
        paths = self._default_paths_with_env({
            "CONCEPT_VAULT": "/tmp/concept-vault/wiki",
            "ENTITY_VAULT": "/tmp/entity-vault/wiki",
        })

        self.assertEqual(paths.knowledge_wiki, Path("/tmp/concept-vault/wiki"))

    def test_defaults_use_current_home_not_fixed_user(self):
        # knowledge_wiki / finance_site / vector_index_dir 仍用 home 回退。
        # finance_root 已改为回退 data_repo_root()（代码根），不再用 home。
        # 这是故意修复：旧的 home 回退导致 DuckDB 路径（代码根）和
        # exports/快照路径（home Desktop）不一致，造成静默失真。
        home = Path("/tmp/current-home")
        paths = self._default_paths_with_env({}, home=home)

        # finance_root 落在代码根，不是 home
        from intelligence.paths import data_repo_root
        self.assertEqual(paths.finance_root, data_repo_root())
        self.assertNotIn("Desktop", str(paths.finance_root))
        self.assertNotIn("/Users/lbq", str(paths.finance_root))

        # market_snapshot_dir 跟 finance_root 走（finance_root 已对齐）
        self.assertEqual(paths.market_snapshot_dir, paths.finance_root / "market_snapshot")

        # knowledge_wiki / vector_index_dir 仍用 home 回退
        self.assertEqual(paths.knowledge_wiki, home / "Desktop/c c/知识库/wiki")
        self.assertEqual(paths.vector_index_dir, home / "Desktop/c c/知识库/.rag_index")
        self.assertNotIn("/Users/lbq", str(paths.knowledge_wiki))

    def test_finance_root_and_duckdb_are_on_the_same_data_root(self):
        # 两根一致是这次修复的核心约束。
        # finance_root 若指向另一棵树，_runtime_market_reference_date() 从旧仓
        # exports 取 floor，再拿它去查本仓 DuckDB，每条结构化查询都被判「数据旧」。
        from intelligence.paths import default_market_db_path
        paths = self._default_paths_with_env({})

        expected_db_root = default_market_db_path().parent.parent
        self.assertEqual(paths.finance_root, expected_db_root,
                         "finance_root 和 DuckDB 所在根不一致，会导致盘面证据静默失真")


if __name__ == "__main__":
    unittest.main()
