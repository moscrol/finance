from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from intelligence import userspace
from intelligence.services import foresight, refresh_profile
from intelligence.services.foresight import ForesightOptions


class UserIdTests(unittest.TestCase):
    def test_valid_ids(self) -> None:
        for uid in ["default", "alice", "user-01", "a.b_c-1", "A1"]:
            self.assertEqual(userspace.resolve_user_id(uid), uid)

    def test_none_falls_back_to_default(self) -> None:
        with mock.patch.dict("os.environ", {}, clear=False):
            import os

            os.environ.pop(userspace.ENV_USER, None)
            self.assertEqual(userspace.resolve_user_id(None), "default")

    def test_env_fallback(self) -> None:
        with mock.patch.dict("os.environ", {userspace.ENV_USER: "bob"}):
            self.assertEqual(userspace.resolve_user_id(None), "bob")

    def test_explicit_overrides_env(self) -> None:
        with mock.patch.dict("os.environ", {userspace.ENV_USER: "bob"}):
            self.assertEqual(userspace.resolve_user_id("carol"), "carol")

    def test_path_traversal_rejected(self) -> None:
        for bad in ["..", ".", "../etc", "a/b", "a\\b", "   ", "-leading", "_leading", "x" * 65]:
            with self.assertRaises(ValueError):
                userspace.resolve_user_id(bad)


class UserSpacePathTests(unittest.TestCase):
    def test_default_uses_legacy_memory(self) -> None:
        us = userspace.user_space("default")
        self.assertTrue(us.is_default)
        self.assertEqual(us.memory_path, userspace.LEGACY_MEMORY)

    def test_non_default_isolated_paths(self) -> None:
        us = userspace.user_space("alice")
        self.assertFalse(us.is_default)
        self.assertEqual(us.root, userspace.USERS_DIR / "alice")
        self.assertEqual(us.memory_path, userspace.USERS_DIR / "alice" / "foresight_memory.jsonl")
        self.assertEqual(us.profile_path, userspace.USERS_DIR / "alice" / "profile.json")
        self.assertEqual(us.derived_path, userspace.USERS_DIR / "alice" / "profile.derived.json")


class EffectiveProfileTests(unittest.TestCase):
    def _us(self, tmp: str, user: str) -> userspace.UserSpace:
        with mock.patch.object(userspace, "USERS_DIR", Path(tmp)):
            return userspace.user_space(user)

    def test_pins_first_then_derived_dedup_and_skip_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(userspace, "USERS_DIR", Path(tmp)):
                us = userspace.user_space("alice")
                us.ensure_dir()
                us.profile_path.write_text(
                    json.dumps(
                        {
                            "name": "Alice",
                            "style": "逆向",
                            "horizon": "1Q",
                            "focus_themes": ["AI算力", "固态电池"],
                            "watchlist": ["中际旭创"],
                            "recent_questions": ["Q1"],
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                us.derived_path.write_text(
                    json.dumps(
                        {
                            "focus_themes": [
                                {"theme": "固态电池"},  # dup of pin -> skipped
                                {"theme": "液冷服务器"},  # new active
                                {"theme": "退潮题材", "stale": True},  # stale -> skipped
                            ],
                            "watchlist": [{"name": "新易盛"}],
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                profile, warnings = userspace.effective_profile(us)
        self.assertEqual(profile["name"], "Alice")
        self.assertEqual(profile["focus_themes"], ["AI算力", "固态电池", "液冷服务器"])
        self.assertEqual(profile["watchlist"], ["中际旭创", "新易盛"])
        self.assertEqual(warnings, [])

    def test_missing_non_default_profile_warns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(userspace, "USERS_DIR", Path(tmp)):
                us = userspace.user_space("ghost")
                profile, warnings = userspace.effective_profile(us)
        self.assertEqual(profile["focus_themes"], [])
        self.assertTrue(any("ghost" in w for w in warnings))


class ForesightResolveProfileTests(unittest.TestCase):
    def test_explicit_profile_overrides_userspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "explicit.json"
            p.write_text(json.dumps({"name": "Explicit", "focus_themes": ["X"]}, ensure_ascii=False), encoding="utf-8")
            profile, warns = foresight.resolve_profile(ForesightOptions(profile=str(p), user="alice"))
        self.assertEqual(profile["name"], "Explicit")
        self.assertEqual(warns, [])

    def test_userspace_profile_used_when_no_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(userspace, "USERS_DIR", Path(tmp)):
                us = userspace.user_space("alice")
                us.ensure_dir()
                us.profile_path.write_text(
                    json.dumps({"name": "AliceUS", "focus_themes": ["液冷服务器"]}, ensure_ascii=False),
                    encoding="utf-8",
                )
                profile, _ = foresight.resolve_profile(ForesightOptions(user="alice"))
        self.assertEqual(profile["name"], "AliceUS")
        self.assertIn("液冷服务器", profile["focus_themes"])

    def test_memory_path_resolves_per_user(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(userspace, "USERS_DIR", Path(tmp)):
                path = foresight._memory_path(ForesightOptions(user="alice"))
        self.assertEqual(path, Path(tmp) / "alice" / "foresight_memory.jsonl")

    def test_memory_file_explicit_wins(self) -> None:
        path = foresight._memory_path(ForesightOptions(user="alice", memory_file="/tmp/custom.jsonl"))
        self.assertEqual(path, Path("/tmp/custom.jsonl"))


class RefreshKbDeriveTests(unittest.TestCase):
    def _write_theme_signals(self, root: Path) -> None:
        (root / "relations").mkdir(parents=True, exist_ok=True)
        payload = {
            "updated": "2026-06-15",
            "version": 1,
            "themes": {
                "液冷服务器": {
                    "recognition_timeline": [
                        {"time_window": "2026-06-10", "recognition_stage": "★★★★"},
                        {"time_window": "2026-05-01", "recognition_stage": "★★"},
                    ],
                    "progress_ruler": [{"current_stage": "★★★", "stage_position": 60}],
                    "market_heat": ["噪声文本 / Tier 1"],
                },
                "固态电池": {
                    "recognition_timeline": [{"time_window": "2026-05-01", "recognition_stage": "★★"}],
                    "market_heat": ["Tier 3"],
                },
                "老题材": {
                    "recognition_timeline": [{"time_window": "2026-01-01", "recognition_stage": "★"}],
                },
            },
        }
        (root / "relations" / "theme_signals.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )

    def test_ranks_by_recency_then_stars(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_theme_signals(root)
            out = refresh_profile.derive_from_kb(refresh_profile.RefreshOptions(kb_wiki=str(root)))
        self.assertTrue(out["ok"])
        self.assertEqual(out["as_of"], "2026-06-15")
        names = [t["theme"] for t in out["themes"]]
        self.assertEqual(names, ["液冷服务器", "固态电池", "老题材"])
        top = out["themes"][0]
        self.assertEqual(top["signals"]["stars"], 4)
        self.assertEqual(top["signals"]["tier"], 1)
        self.assertEqual(top["signals"]["last_event"], "2026-06-10")

    def test_missing_kb_degrades(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = refresh_profile.derive_from_kb(refresh_profile.RefreshOptions(kb_wiki=str(Path(tmp) / "nope")))
        self.assertFalse(out["ok"])
        self.assertTrue(out["warnings"])


class RefreshDuckdbDegradeTests(unittest.TestCase):
    def test_duckdb_unavailable_is_graceful(self) -> None:
        # 本 VM 无 duckdb 驱动 / 无 db 文件，应优雅降级而非抛栈。
        out = refresh_profile.derive_from_duckdb(refresh_profile.RefreshOptions(db_path="/nonexistent/market.duckdb"))
        self.assertFalse(out["ok"])
        self.assertTrue(out["warnings"])
        self.assertEqual(out["directions"], [])
        self.assertEqual(out["watchlist"], [])


class RefreshCombineTests(unittest.TestCase):
    def _patched_derive(self, kb_ret: dict, duck_ret: dict, top: int = 12) -> dict:
        with mock.patch.object(refresh_profile, "derive_from_kb", return_value=kb_ret), mock.patch.object(
            refresh_profile, "derive_from_duckdb", return_value=duck_ret
        ):
            return refresh_profile.derive(refresh_profile.RefreshOptions(top=top))

    def test_source_tagging_both_kb_duckdb(self) -> None:
        kb_ret = {
            "ok": True,
            "as_of": "2026-06-15",
            "themes": [
                {"theme": "液冷服务器", "signals": {"stars": 4}},
                {"theme": "固态电池", "signals": {"stars": 2}},
            ],
            "warnings": [],
        }
        duck_ret = {
            "ok": True,
            "as_of": "2026-06-12",
            "directions": [
                {"theme": "液冷服务器", "score": 40.0, "tags": ["new_high"]},
                {"theme": "PCB", "score": 30.0, "tags": ["double_red"]},
            ],
            "watchlist": [{"name": "中际旭创", "code": "300308.SZ", "weighted": 99.0, "theme": "液冷服务器"}],
            "warnings": [],
        }
        proposal = self._patched_derive(kb_ret, duck_ret)
        by_theme = {t["theme"]: t for t in proposal["focus_themes"]}
        self.assertEqual(by_theme["液冷服务器"]["source"], "both")
        self.assertEqual(by_theme["固态电池"]["source"], "kb")
        self.assertEqual(by_theme["PCB"]["source"], "duckdb")
        # both 应排在最前
        self.assertEqual(proposal["focus_themes"][0]["theme"], "液冷服务器")
        self.assertEqual(proposal["watchlist"][0]["name"], "中际旭创")
        self.assertEqual(proposal["watchlist"][0]["source"], "duckdb")
        self.assertEqual(proposal["status"], "PASS")

    def test_status_warn_when_both_sources_off(self) -> None:
        off = {"ok": False, "as_of": None, "themes": [], "warnings": ["x"]}
        duck_off = {"ok": False, "as_of": None, "directions": [], "watchlist": [], "warnings": ["y"]}
        proposal = self._patched_derive(off, duck_off)
        self.assertEqual(proposal["status"], "WARN")
        self.assertEqual(proposal["focus_themes"], [])


class DiffAndApplyTests(unittest.TestCase):
    def test_diff_against_profile(self) -> None:
        current = {"focus_themes": ["AI算力"], "watchlist": ["中际旭创"]}
        proposal = {
            "focus_themes": [{"theme": "AI算力", "source": "kb"}, {"theme": "液冷服务器", "source": "both"}],
            "watchlist": [{"name": "中际旭创"}, {"name": "新易盛"}],
        }
        diff = refresh_profile.diff_against_profile(current, proposal)
        self.assertEqual([t["theme"] for t in diff["new_themes"]], ["液冷服务器"])
        self.assertEqual([t["theme"] for t in diff["kept_themes"]], ["AI算力"])
        self.assertEqual([w["name"] for w in diff["new_watchlist"]], ["新易盛"])

    def _proposal(self, themes: list[str]) -> dict:
        return {
            "generated_at": "2026-06-16T00:00:00+08:00",
            "user": "alice",
            "as_of": {"duckdb": "2026-06-12", "kb": "2026-06-15"},
            "sources": {"duckdb": {"ok": True}, "kb": {"ok": True}},
            "focus_themes": [{"theme": t, "source": "kb", "signals": {}} for t in themes],
            "watchlist": [],
        }

    def test_apply_decay_stale_then_drop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(userspace, "USERS_DIR", Path(tmp)):
                us = userspace.user_space("alice")
                refresh_profile.apply_derived(us, self._proposal(["A", "B"]))

                def themes_state() -> dict[str, dict]:
                    data = json.loads(us.derived_path.read_text(encoding="utf-8"))
                    return {t["theme"]: t for t in data["focus_themes"]}

                # miss 1 -> kept, not stale
                refresh_profile.apply_derived(us, self._proposal(["A"]))
                state = themes_state()
                self.assertEqual(state["B"]["misses"], 1)
                self.assertFalse(state["B"]["stale"])
                # miss 2 -> stale
                refresh_profile.apply_derived(us, self._proposal(["A"]))
                self.assertTrue(themes_state()["B"]["stale"])
                # miss 3 -> still present, stale
                refresh_profile.apply_derived(us, self._proposal(["A"]))
                self.assertTrue(themes_state()["B"]["stale"])
                # miss 4 -> dropped
                refresh_profile.apply_derived(us, self._proposal(["A"]))
                self.assertNotIn("B", themes_state())
                self.assertIn("A", themes_state())

    def test_apply_reappear_resets_misses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(userspace, "USERS_DIR", Path(tmp)):
                us = userspace.user_space("alice")
                refresh_profile.apply_derived(us, self._proposal(["A", "B"]))
                refresh_profile.apply_derived(us, self._proposal(["A"]))  # B miss 1
                refresh_profile.apply_derived(us, self._proposal(["A", "B"]))  # B back
                data = json.loads(us.derived_path.read_text(encoding="utf-8"))
                b = {t["theme"]: t for t in data["focus_themes"]}["B"]
                self.assertEqual(b["misses"], 0)
                self.assertFalse(b["stale"])

    def test_apply_then_effective_skips_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(userspace, "USERS_DIR", Path(tmp)):
                us = userspace.user_space("alice")
                us.ensure_dir()
                us.profile_path.write_text(json.dumps({"name": "A", "focus_themes": []}), encoding="utf-8")
                refresh_profile.apply_derived(us, self._proposal(["A", "B"]))
                refresh_profile.apply_derived(us, self._proposal(["A"]))
                refresh_profile.apply_derived(us, self._proposal(["A"]))  # B now stale
                profile, _ = userspace.effective_profile(us)
        self.assertIn("A", profile["focus_themes"])
        self.assertNotIn("B", profile["focus_themes"])


if __name__ == "__main__":
    unittest.main()
