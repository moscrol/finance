from __future__ import annotations

from pathlib import Path

from intelligence.services import runtime_provenance
from intelligence.services.runtime_provenance import build_runtime_provenance


def test_runtime_provenance_has_revision_and_dependency_fingerprint() -> None:
    payload = build_runtime_provenance(Path(__file__).resolve().parents[2])

    assert payload["source_revision"]
    assert len(str(payload["dependency_fingerprint"])) == 64
    assert payload["python_executable"]
    assert isinstance(payload["dependencies"], dict)


def test_loaded_package_root_is_derived_from_this_modules_file() -> None:
    """身份必须来自 ``__file__``，不能来自 env 或 sys.path。

    ``PYTHONPATH`` / ``WORKBENCH_REPO_ROOT`` 说的是「某人打算加载什么」；
    只有 ``__file__`` 报告「实际加载了什么」。本轮 bug 的要害正在这里：
    health 自报的 revision 描述的是 ``code_root`` 的 git 检出，而进程执行的
    是 ``PYTHONPATH`` 上的独立快照，两者可以毫无关系。
    """

    assert (
        runtime_provenance.loaded_package_root()
        == Path(runtime_provenance.__file__).resolve().parents[1]
    )


def _write_tree(root: Path, files: dict[str, str]) -> Path:
    for name, body in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return root


def test_tree_fingerprint_matches_identical_trees(tmp_path) -> None:
    files = {"a.py": "x = 1\n", "pkg/b.py": "y = 2\n"}
    left = _write_tree(tmp_path / "left", dict(files))
    right = _write_tree(tmp_path / "right", dict(files))

    assert runtime_provenance._package_tree_fingerprint(
        left
    ) == runtime_provenance._package_tree_fingerprint(right)


def test_tree_fingerprint_detects_a_missing_module(tmp_path) -> None:
    """快照缺模块 —— 本轮实际遇到的第一种漂移形态。

    实测：快照缺整个 ``intelligence/runtime/`` 包与 14 个 services 模块，
    服务起不来报 ``ModuleNotFoundError``，而 health 的 revision 一切正常。
    """

    full = _write_tree(tmp_path / "full", {"a.py": "x = 1\n", "b.py": "y = 2\n"})
    partial = _write_tree(tmp_path / "partial", {"a.py": "x = 1\n"})

    full_fp, full_n = runtime_provenance._package_tree_fingerprint(full)
    partial_fp, partial_n = runtime_provenance._package_tree_fingerprint(partial)

    assert full_fp != partial_fp
    assert (full_n, partial_n) == (2, 1)


def test_tree_fingerprint_detects_same_count_different_content(tmp_path) -> None:
    """模块数相同、内容不同 —— 最重要的一格。

    只比模块数量，或只看 git revision，都发现不了这种漂移；而本轮的
    ``app.py`` / ``episode_factory.py`` 恰好就是这个形态：文件在、数量对、
    内容是缺了身份穿透的旧版。指纹必须对内容敏感，而不只是对清单敏感。
    """

    before = _write_tree(tmp_path / "before", {"a.py": "memory_user = None\n"})
    after = _write_tree(tmp_path / "after", {"a.py": "memory_user = user_id\n"})

    before_fp, before_n = runtime_provenance._package_tree_fingerprint(before)
    after_fp, after_n = runtime_provenance._package_tree_fingerprint(after)

    assert before_n == after_n == 1
    assert before_fp != after_fp


def test_tree_fingerprint_ignores_pycache(tmp_path) -> None:
    """``__pycache__`` 不参与指纹：它是构建产物，会让同一份源码算出不同的值。"""

    tree = _write_tree(tmp_path / "tree", {"a.py": "x = 1\n"})
    baseline = runtime_provenance._package_tree_fingerprint(tree)
    _write_tree(tree, {"__pycache__/a.cpython-312.pyc": "irrelevant\n"})

    assert runtime_provenance._package_tree_fingerprint(tree) == baseline


def test_tree_fingerprint_reports_absent_tree_distinctly(tmp_path) -> None:
    """树不存在要能与「比过且相同」区分开，否则空 vs 空会假装一致。"""

    assert runtime_provenance._package_tree_fingerprint(tmp_path / "nope") == ("", 0)


def _provenance_with_trees(monkeypatch, tmp_path, loaded, repo_files):
    """Build provenance against synthetic loaded/repo trees.

    ``build_runtime_provenance`` 用 ``root / loaded_root.name`` 定位仓库侧的包，
    所以两边的目录名都必须叫 ``intelligence``。
    """

    loaded_root = _write_tree(tmp_path / "loaded" / "intelligence", loaded)
    monkeypatch.setattr(
        runtime_provenance, "loaded_package_root", lambda: loaded_root
    )
    repo_root = tmp_path / "repo"
    if repo_files is not None:
        _write_tree(repo_root / "intelligence", repo_files)
    repo_root.mkdir(parents=True, exist_ok=True)
    return build_runtime_provenance(repo_root)


def test_provenance_reports_agreement_when_snapshot_matches_repo(
    monkeypatch,
    tmp_path,
) -> None:
    files = {"a.py": "x = 1\n"}
    payload = _provenance_with_trees(monkeypatch, tmp_path, dict(files), dict(files))

    assert payload["code_matches_repo"] is True
    assert payload["loaded_tree_fingerprint"] == payload["repo_tree_fingerprint"]
    assert payload["loaded_module_count"] == payload["repo_module_count"] == 1


def test_provenance_reports_drift_when_snapshot_is_stale(
    monkeypatch,
    tmp_path,
) -> None:
    """这条是整个改动的目的：让 payload 能**陈述**漂移，而不是暗示新鲜。

    改前 health 只有 ``source_revision``（读 git HEAD）。它在合并后恰好会
    「前进」—— 也就是在最可能出错的时刻显得最可信：仓库更新了，快照没有。
    """

    payload = _provenance_with_trees(
        monkeypatch,
        tmp_path,
        {"a.py": "stale = True\n"},
        {"a.py": "stale = False\n"},
    )

    assert payload["code_matches_repo"] is False
    assert payload["loaded_tree_fingerprint"] != payload["repo_tree_fingerprint"]


def test_provenance_distinguishes_loaded_root_from_code_root(
    monkeypatch,
    tmp_path,
) -> None:
    """``code_root`` 与 ``loaded_code_root`` 必须是两个可分辨的字段。

    生产形态就是二者不同：``code_root`` 指仓库，执行的却是 ``PYTHONPATH``
    上的独立快照。把它们合成一个字段，就无法表达这个差异。
    """

    payload = _provenance_with_trees(
        monkeypatch,
        tmp_path,
        {"a.py": "x = 1\n"},
        {"a.py": "x = 1\n"},
    )

    assert payload["loaded_code_root"] != payload["code_root"]
    assert str(payload["loaded_code_root"]).endswith("intelligence")


def test_provenance_uses_none_when_there_is_no_repo_tree_to_compare(
    monkeypatch,
    tmp_path,
) -> None:
    """纯快照部署：无从比较。

    三态是刻意的。压成 ``False`` 会在没有漂移可言时误报；压成 ``True``
    则重犯原来的错误 —— 断言一个从未检查过的一致性。
    """

    payload = _provenance_with_trees(
        monkeypatch,
        tmp_path,
        {"a.py": "x = 1\n"},
        None,
    )

    assert payload["code_matches_repo"] is None
    assert payload["repo_tree_fingerprint"] == "unknown"
    assert payload["repo_module_count"] == 0


def test_provenance_keeps_legacy_keys_for_existing_consumers() -> None:
    """既有消费者读的键不能改名。

    ``eval/acceptance.py`` 与 ``eval/semantic_acceptance`` 都按名字读
    ``source_revision`` / ``dependency_fingerprint``；新能力只能加字段。
    """

    payload = build_runtime_provenance(Path(__file__).resolve().parents[2])

    for key in (
        "source_revision",
        "source_dirty",
        "code_root",
        "python_executable",
        "python_version",
        "python_prefix",
        "dependency_fingerprint",
        "dependencies",
    ):
        assert key in payload, key
