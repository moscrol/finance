import importlib
import os
import unittest
from pathlib import Path
from unittest.mock import patch


class DefaultPathsTest(unittest.TestCase):
    def _default_paths_with_env(self, env):
        keys = {
            "FINANCE_WS",
            "FINANCE_ROOT",
            "KB_VAULT",
            "KNOWLEDGE_WIKI",
            "CONCEPT_VAULT",
            "ENTITY_VAULT",
            "FINANCE_SITE",
        }
        clean_env = {key: value for key, value in os.environ.items() if key not in keys}
        clean_env.update(env)
        with patch.dict(os.environ, clean_env, clear=True):
            import intelligence.paths as paths
            importlib.reload(paths)
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
        paths = self._default_paths_with_env({})

        self.assertEqual(paths.finance_root, Path.home() / "Desktop/c c/金融")
        self.assertEqual(paths.knowledge_wiki, Path.home() / "Desktop/c c/知识库/wiki")
        self.assertNotIn("/Users/lbq", str(paths.finance_root))
        self.assertNotIn("/Users/lbq", str(paths.knowledge_wiki))


if __name__ == "__main__":
    unittest.main()
