"""RAG 就绪自检脚本的行为约定。

它存在的理由：索引新鲜度守卫只在查询时才 fail-closed，而工作台历史上把该错误
显示成"退出码 3"。实测那个状态持续了一整天没被发现。
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check_rag_readiness.py"


def load_script():
    spec = importlib.util.spec_from_file_location("check_rag_readiness", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def kb(tmp_path):
    root = tmp_path / "kb"
    for name in ("entities", "concepts", "sources", "synthesis", "briefings"):
        (root / "wiki" / name).mkdir(parents=True)
    (root / ".rag_index").mkdir(parents=True)
    subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "t"], check=True)
    (root / "wiki" / "sources" / "a.md").write_text("x", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "init"], check=True)
    return root


def write_meta(kb_root: Path, **overrides) -> None:
    meta = {
        "built_at": "2026-07-30T03:43:40",
        "num_chunks": 100,
        "source_git_revision": "abc123",
        "source_dirty": False,
    }
    meta.update(overrides)
    (kb_root / ".rag_index" / "meta.json").write_text(
        json.dumps(meta), encoding="utf-8"
    )


def run(kb_root: Path) -> int:
    # 必须显式钉夹具自己的索引。启动器常带 RAG_INDEX_DIR 指向生产库，
    # 只传 --kb-root 时脚本会去审那份真索引，脏/缺 meta 夹具永远绿。
    return load_script().main([
        "--kb-root",
        str(kb_root),
        "--index-dir",
        str(kb_root / ".rag_index"),
        "--quiet",
    ])


def test_clean_committed_index_is_ready(kb) -> None:
    write_meta(kb)
    assert run(kb) == 0


def test_uncommitted_indexed_file_blocks(kb) -> None:
    write_meta(kb)
    (kb / "wiki" / "synthesis" / "new.md").write_text("y", encoding="utf-8")

    assert run(kb) == 1


def test_change_outside_indexed_dirs_does_not_block(kb) -> None:
    """守卫只覆盖被索引的目录；raw/ 与 scripts/ 的改动不该拦问答。"""
    write_meta(kb)
    (kb / "wiki" / "raw").mkdir(parents=True, exist_ok=True)
    (kb / "wiki" / "raw" / "dump.md").write_text("y", encoding="utf-8")

    assert run(kb) == 0


def test_dirty_built_index_blocks(kb) -> None:
    """rag update 在脏工作区上重建会记下 source_dirty=true，本身即不新鲜。"""
    write_meta(kb, source_dirty=True)

    assert run(kb) == 1


def test_missing_meta_blocks(kb) -> None:
    assert run(kb) == 1


def test_missing_kb_root_is_undetermined(tmp_path) -> None:
    assert load_script().main(["--kb-root", str(tmp_path / "nope"), "--quiet"]) == 2
