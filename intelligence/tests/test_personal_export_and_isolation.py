"""终局 spec §10 最小验收集第 6、8 条。

- **第 6 条**：一次用户反馈不会改变共享提示词、授课框架或其他用户的输出。
- **第 8 条**：用户退出后可导出自己的判断台账，且私有对象不出现在其他用户的查询里。

第 6 条的判据不能是「读一读代码觉得没问题」。这里用**整棵用户根目录的哈希**：
给用户 A 写一条反馈，除了 ``users/A/`` 底下，**别处一个字节都不许变**。
这条断言不依赖我对某个函数的理解，加一条静默写共享层的路径就会当场红。
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from intelligence import userspace
from intelligence.services import checkpoints, corrections
from intelligence.services import observation_script as osc
from intelligence.services import personal_export


def _tree_hashes(root: Path) -> dict[str, str]:
    """整棵树 路径 → 内容哈希。目录不存在返回空。"""
    out: dict[str, str] = {}
    if not root.exists():
        return out
    for p in sorted(root.rglob("*")):
        if p.is_file():
            out[str(p.relative_to(root))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def _space(root: str, uid: str):
    with mock.patch.dict(os.environ, {"FORESIGHT_USERS_DIR": root}, clear=False):
        us = userspace.user_space(uid)
    us.root.mkdir(parents=True, exist_ok=True)
    return us


def _seed(us) -> None:
    checkpoints.register_checkpoint(
        us.checkpoints_path, claim=f"{us.user_id} 的判断", due="2026-09-10", category="估值切换"
    )
    osc.register(
        us.observation_scripts_path,
        osc.make(
            as_of="2026-09-02",
            scope="theme",
            entity_ids=["算力租赁"],
            variables=["题材轨：题材所处阶段是否推进"],
            downgrade_or_abandon_conditions=["题材轨阶段标签回退或转为缺口"],
            recorded_at="2026-09-03T08:00:00+08:00",
            status="confirmed",
        ),
        checkpoints_path=us.checkpoints_path,
    )


class FeedbackTouchesOnlyItsOwner(unittest.TestCase):
    """第 6 条：一次反馈只准落在自己那个目录里。"""

    def test_only_that_users_subtree_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a, b = _space(tmp, "alice"), _space(tmp, "bob")
            _seed(a)
            _seed(b)
            before = _tree_hashes(root)

            corrections.record_correction(a.corrections_path, correction="以后别用这个口径")

            after = _tree_hashes(root)
            changed = {k for k in set(before) | set(after) if before.get(k) != after.get(k)}
            self.assertTrue(changed, "反馈总得写点东西，否则这条测试自己是假的")
            outside = {k for k in changed if not k.startswith("alice/")}
            self.assertEqual(outside, set(), f"反馈碰了自己目录以外的东西：{outside}")

    def test_other_users_ledger_is_byte_identical(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            a, b = _space(tmp, "alice"), _space(tmp, "bob")
            _seed(a)
            _seed(b)
            before = _tree_hashes(b.root)
            corrections.record_correction(a.corrections_path, correction="改一下口径")
            self.assertEqual(_tree_hashes(b.root), before, "另一个用户的台账逐字节不变")

    def test_shared_repo_artifacts_untouched(self) -> None:
        """共享层活在仓里（提示词 / 方法论文档）。反馈不该改仓内任何文件。"""
        shared = [Path("intelligence/foresight_methodology.md"), Path("docs/marketing/claims.yaml")]
        shared = [p for p in shared if p.exists()]
        self.assertTrue(shared, "没找到任何共享层文件，这条测试会假绿")
        before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in shared}
        with tempfile.TemporaryDirectory() as tmp:
            a = _space(tmp, "alice")
            corrections.record_correction(a.corrections_path, correction="共享层不许动")
        after = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in shared}
        self.assertEqual(after, before)


class PrivateObjectsDoNotLeak(unittest.TestCase):
    """第 8 条后半：私有对象不出现在其他用户的查询里。"""

    def test_checkpoints_are_per_user(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            a, b = _space(tmp, "alice"), _space(tmp, "bob")
            _seed(a)
            cks_b, _ = checkpoints.load_checkpoints(b.checkpoints_path)
            self.assertEqual(cks_b, [], "bob 不该看到 alice 的可证伪点")
            cks_a, _ = checkpoints.load_checkpoints(a.checkpoints_path)
            self.assertTrue(cks_a)

    def test_observation_scripts_are_per_user(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            a, b = _space(tmp, "alice"), _space(tmp, "bob")
            _seed(a)
            self.assertEqual(osc.load(b.observation_scripts_path), [])
            self.assertTrue(osc.load(a.observation_scripts_path))

    def test_two_users_get_different_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            a, b = _space(tmp, "alice"), _space(tmp, "bob")
            self.assertNotEqual(a.root, b.root)
            self.assertNotEqual(a.checkpoints_path, b.checkpoints_path)


class ExportIsCompleteAndOwnOnly(unittest.TestCase):
    """第 8 条前半：能把自己的台账整份带走。"""

    def test_export_contains_own_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            a = _space(tmp, "alice")
            _seed(a)
            res = personal_export.export_ledger(a, now="2026-09-06T00:00:00+00:00")
            self.assertEqual(res.user_id, "alice")
            self.assertGreaterEqual(res.counts["checkpoints"], 1)
            self.assertGreaterEqual(res.counts["observation_scripts"], 1)
            self.assertIn("alice 的判断", json.dumps(res.to_dict(), ensure_ascii=False))

    def test_export_does_not_contain_other_users(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            a, b = _space(tmp, "alice"), _space(tmp, "bob")
            _seed(a)
            _seed(b)
            blob = json.dumps(personal_export.export_ledger(a).to_dict(), ensure_ascii=False)
            self.assertIn("alice 的判断", blob)
            self.assertNotIn("bob 的判断", blob)

    def test_manifest_says_what_was_left_out(self) -> None:
        """只给数据不给清单，用户没法判断这份导出完不完整。"""
        with tempfile.TemporaryDirectory() as tmp:
            a = _space(tmp, "alice")
            _seed(a)
            m = personal_export.export_ledger(a).to_dict()["manifest"]
            self.assertTrue(m["excluded"])
            self.assertTrue(all(e["why"] for e in m["excluded"]), "排除项必须写理由")
            self.assertEqual(m["total_records"], sum(m["counts"].values()))

    def test_empty_user_exports_cleanly(self) -> None:
        """没产生过记录的用户导出应是空而不是报错——空台账也是一个诚实答案。"""
        with tempfile.TemporaryDirectory() as tmp:
            res = personal_export.export_ledger(_space(tmp, "newbie"))
            self.assertEqual(sum(res.counts.values()), 0)
            self.assertTrue(res.missing, "文件不存在要如实列出，不能装作导出过了")

    def test_export_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a = _space(tmp, "alice")
            _seed(a)
            before = _tree_hashes(root)
            personal_export.export_ledger(a)
            self.assertEqual(_tree_hashes(root), before, "导出不许改动任何台账")

    def test_render_shows_counts_and_exclusions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            a = _space(tmp, "alice")
            _seed(a)
            text = personal_export.render(personal_export.export_ledger(a))
            self.assertIn("checkpoints", text)
            self.assertIn("刻意未导出", text)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
