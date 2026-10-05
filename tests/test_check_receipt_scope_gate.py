"""收据必须自证「跑的是多大一片」，否则「全量绿」不可审计。

失败形状（2026-09-22 实测）：收据里的 ``target`` 只是 pytest 的**位置参数**，
`pytest -q` 与 `pytest -q --ignore=scripts/archive` 写出来的收据逐字相同——都是
一个仓根路径。于是：

- `scripts/archive/test_kb_freshness_fix.py` 让全树收集中断的 33 天里，仍有多张
  「12000+ passed / exit 0 / 干净树」的全树收据；它们只可能带着 `--ignore` 跑，
  而收据看不出来。
- `docs/verification/re06-*/REVIEW.md` 两份复核都只能从交接正文里找回「命令含
  ``--ignore=test_codex_sandbox.py``」，并因此声明不当作自己的全量结论。

所以补两件事，并且**读侧要有人真的读**：

- ``conftest._collection_scope``：把 ignore / ignore_glob / deselect / -k / -m /
  maxfail / --lf 与实收数 collected 一并写进收据；
- ``check_test_receipt``：默认只报（验子集读数是正当用法），
  ``--require-full-scope`` 才升成拦截；旧格式收据按 fail closed 拒绝。
- 收执对账：收了 N 条就该有 N 条读数，对不上即「没跑完」。这也是 counts 补上
  xfailed/xpassed 的原因——不补的话对账永远不平，等于没有这道账。

第二个失败形状（2026-10-05 实测）：只看旋钮，不看 ``target`` 本身。59 个文件的
定向跑（`pytest -q tests/a.py …`，collected=1585，旋钮全空）在
``--require-full-scope`` 下打出「收集面未被收窄」「可采信」，而目标行明明是一串
文件。位置参数也是收窄：``target`` 只能为空、``.`` 或与 ``tree`` 相同的仓根路径。
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import conftest as root_conftest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_test_receipt.py"
_spec = importlib.util.spec_from_file_location("check_test_receipt_scope", _SCRIPT)
ctr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ctr)


def _session(collected: int = 0, **option_kwargs) -> SimpleNamespace:
    option = {
        "ignore": None, "ignore_glob": None, "deselect": None,
        "keyword": "", "markexpr": "", "maxfail": 0, "lf": False,
    }
    option.update(option_kwargs)
    return SimpleNamespace(
        config=SimpleNamespace(option=SimpleNamespace(**option)),
        testscollected=collected,
    )


def test_scope_of_an_unnarrowed_run_is_all_empty() -> None:
    scope = root_conftest._collection_scope(_session(collected=12442))
    assert scope == {
        "ignore": [], "ignore_glob": [], "deselect": [], "keyword": "",
        "markexpr": "", "maxfail": 0, "last_failed": False, "collected": 12442,
    }


@pytest.mark.parametrize(
    ("option_kwargs", "key", "expected"),
    [
        ({"ignore": ["scripts/archive"]}, "ignore", ["scripts/archive"]),
        ({"ignore_glob": ["*_live.py"]}, "ignore_glob", ["*_live.py"]),
        ({"deselect": ["tests/test_x.py::test_y"]}, "deselect", ["tests/test_x.py::test_y"]),
        ({"keyword": "not slow"}, "keyword", "not slow"),
        ({"markexpr": "not live"}, "markexpr", "not live"),
        ({"maxfail": 1}, "maxfail", 1),
        ({"lf": True}, "last_failed", True),
    ],
)
def test_every_narrowing_knob_reaches_the_receipt(option_kwargs, key, expected) -> None:
    assert root_conftest._collection_scope(_session(**option_kwargs))[key] == expected


def test_scope_survives_a_session_without_options() -> None:
    """收据是观测设施：取不到 option 也不能把 sessionfinish 炸掉。"""
    bare = SimpleNamespace(config=SimpleNamespace(), testscollected=3)
    assert root_conftest._collection_scope(bare)["collected"] == 3


def test_narrowed_receipt_is_reported_as_narrowed() -> None:
    ok, message = ctr.describe_collection_scope(
        {"scope": {"ignore": ["scripts/archive"], "collected": 12442}}
    )
    assert ok is False
    assert "收窄" in message and "scripts/archive" in message


def test_unnarrowed_receipt_passes_and_states_collected() -> None:
    ok, message = ctr.describe_collection_scope(
        {"scope": {"ignore": [], "keyword": "", "collected": 12442}}
    )
    assert ok is True
    assert "12442" in message


@pytest.mark.parametrize("receipt", [{}, {"scope": None}, {"scope": "full"}])
def test_old_format_receipt_is_unknown_not_green(receipt) -> None:
    """旧收据既不是绿也不是红，是「不知道」——不能被静默当成全量。"""
    ok, message = ctr.describe_collection_scope(receipt)
    assert ok is None
    assert "不可审计" in message


# 合成仓根：位置参数与 tree 只做词法比较，不碰文件系统，所以不必是真目录。
_TREE = "/srv/fwp-tree"
_UNNARROWED = {"ignore": [], "ignore_glob": [], "deselect": [], "keyword": "",
               "markexpr": "", "maxfail": 0, "last_failed": False, "collected": 12442}
# 2026-10-04 那张收据的形状：59 个文件、旋钮全空。
_FILE_LIST = " ".join(f"tests/test_case_{i:02d}.py" for i in range(59))


def test_file_list_target_is_narrowing_even_with_every_knob_empty() -> None:
    ok, message = ctr.describe_collection_scope(
        {"tree": _TREE, "target": _FILE_LIST, "scope": dict(_UNNARROWED)}
    )
    assert ok is False
    assert "位置参数" in message and "59" in message
    assert "tests/test_case_00.py" in message and "另 56 个" in message  # 判定行只列头几个
    assert "未被收窄" not in message


@pytest.mark.parametrize(
    "target",
    [
        "intelligence/tests",      # 本机 8 张 ≥10000 passed 的收据就是这个形状
        f"{_TREE}/tests",          # 在子目录里裸跑 pytest：pytest 补的是子目录绝对路径
        "/srv/other-tree",         # 别的树（嵌套夹具仓的收据就是这样）
    ],
)
def test_any_single_target_other_than_the_repo_root_is_narrowing(target) -> None:
    ok, message = ctr.describe_collection_scope(
        {"tree": _TREE, "target": target, "scope": dict(_UNNARROWED)}
    )
    assert ok is False
    assert "位置参数" in message and target in message


@pytest.mark.parametrize("target", ["", "  ", ".", "./", _TREE, f"{_TREE}/"])
def test_repo_root_spellings_are_not_narrowing(target) -> None:
    """守卫（旧代码上也绿）：裸 `pytest -q` 在仓根跑，pytest 把调用目录的绝对路径
    补成唯一位置参数，所以真全量收据的 target 逐字等于 tree——不能被新判据误伤。"""
    ok, message = ctr.describe_collection_scope(
        {"tree": _TREE, "target": target, "scope": dict(_UNNARROWED)}
    )
    assert ok is True
    assert "未被收窄" in message


def test_absolute_root_is_unrecognisable_without_the_tree_field() -> None:
    """没有 tree 就认不出一条绝对路径是不是仓根：按收窄报，朝安全方向错。"""
    ok, message = ctr.describe_collection_scope(
        {"target": _TREE, "scope": dict(_UNNARROWED)}
    )
    assert ok is False
    assert "位置参数" in message


def test_positional_and_knob_narrowing_are_both_listed() -> None:
    ok, message = ctr.describe_collection_scope(
        {"tree": _TREE, "target": "tests/a.py", "scope": {**_UNNARROWED, "keyword": "slow"}}
    )
    assert ok is False
    assert "位置参数" in message and "tests/a.py" in message
    assert "keyword=slow" in message


def test_old_format_receipt_with_a_file_list_is_known_narrowed() -> None:
    """无 scope 段时旋钮不可审计，但位置参数已足以判定收窄——那就不是「不知道」。"""
    ok, message = ctr.describe_collection_scope({"tree": _TREE, "target": "tests/a.py"})
    assert ok is False
    assert "位置参数" in message and "scope" in message


def test_counts_reconcile_when_nothing_was_truncated() -> None:
    ok, message = ctr.check_collected_matches_counts(
        {
            "scope": {"collected": 12529},
            "counts": {"passed": 12442, "failed": 0, "error": 0,
                       "skipped": 85, "xfailed": 2, "xpassed": 0},
        }
    )
    assert ok is True and "对账平" in message


def test_a_green_receipt_that_ran_half_of_what_it_collected_is_caught() -> None:
    ok, message = ctr.check_collected_matches_counts(
        {
            "scope": {"collected": 12442},
            "counts": {"passed": 6000, "failed": 0, "error": 0, "skipped": 0},
            "exit_status": 0,
        }
    )
    assert ok is False
    assert "没跑完" in message and "6442" in message


def test_reconciliation_needs_xfail_counts_to_be_recorded() -> None:
    """反向锁：counts 不含 xfailed 时，平衡的读数会被误判成截断。

    这条钉住 conftest 里 counts 必须带 xfailed/xpassed——少了它们，这道账
    会天天报不平，然后被当成噪声忽略，等于没有账。
    """
    ok, _ = ctr.check_collected_matches_counts(
        {"scope": {"collected": 12529},
         "counts": {"passed": 12442, "failed": 0, "error": 0, "skipped": 85}}
    )
    assert ok is False


def _receipt_matching_this_machine(**overrides) -> dict:
    receipt = {
        "revision": ctr._git("rev-parse", "HEAD") or "(unknown)",
        "interpreter": sys.executable,
        "python_version": ctr.platform.python_version(),
        "dependency_fingerprint": ctr._fingerprint(),
        "dirty": False,
        "worktree_dirty_total": 0,
        "dependency_gate_bypassed": False,
        "target": "",
        "scope": {"ignore": ["scripts/archive"], "ignore_glob": [], "deselect": [],
                  "keyword": "", "markexpr": "", "maxfail": 0,
                  "last_failed": False, "collected": 12442},
        "counts": {"passed": 12442, "failed": 0, "error": 0, "skipped": 0,
                   "xfailed": 0, "xpassed": 0},
        "failed_ids": [],
        "exit_status": 0,
        "finished_at": "2026-09-22T12:20:59+00:00",
    }
    receipt.update(overrides)
    return receipt


def _run_main(tmp_path: Path, monkeypatch, receipt: dict, *flags: str) -> int:
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(receipt), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["check_test_receipt.py", str(path), *flags])
    return ctr.main()


def test_narrowed_receipt_only_blocks_when_full_scope_is_required(
    tmp_path, monkeypatch, capsys
) -> None:
    """验子集读数是正当用法，所以默认只报不拦。"""
    _run_main(tmp_path, monkeypatch, _receipt_matching_this_machine())
    out = capsys.readouterr().out
    assert "收集面被收窄" in out
    assert "收集面被收窄或不可审计" not in out  # 未升成拦截项

    assert _run_main(
        tmp_path, monkeypatch, _receipt_matching_this_machine(), "--require-full-scope"
    ) == 1
    out = capsys.readouterr().out
    assert "收集面被收窄或不可审计" in out
    assert "✅ 可采信" not in out


def test_old_receipt_fails_closed_under_require_full_scope(
    tmp_path, monkeypatch, capsys
) -> None:
    receipt = _receipt_matching_this_machine()
    del receipt["scope"]
    assert _run_main(tmp_path, monkeypatch, receipt, "--require-full-scope") == 1
    assert "不可审计" in capsys.readouterr().out


def test_file_list_target_fails_under_require_full_scope(
    tmp_path, monkeypatch, capsys
) -> None:
    receipt = _receipt_matching_this_machine(
        tree=_TREE, target=_FILE_LIST, scope=dict(_UNNARROWED)
    )
    assert _run_main(tmp_path, monkeypatch, receipt, "--require-full-scope") == 1
    out = capsys.readouterr().out
    assert "收集面被收窄或不可审计" in out
    assert "位置参数" in out
    assert "收集面未被收窄" not in out
    assert "✅ 可采信" not in out


@pytest.mark.parametrize("target", ["", ".", _TREE])
def test_root_targets_still_pass_under_require_full_scope(
    target, tmp_path, monkeypatch, capsys
) -> None:
    """守卫（旧代码上也绿）：run_main_gate.sh 的全量收据 target == tree，不能被误拦。"""
    receipt = _receipt_matching_this_machine(
        tree=_TREE, target=target, scope=dict(_UNNARROWED)
    )
    assert _run_main(tmp_path, monkeypatch, receipt, "--require-full-scope") == 0
    out = capsys.readouterr().out
    assert "收集面未被收窄" in out
    assert "✅ 可采信" in out


def test_file_list_target_without_the_flag_reports_but_does_not_block(
    tmp_path, monkeypatch, capsys
) -> None:
    """验子集读数是正当用法（--require-target）：默认只报，不拦。"""
    receipt = _receipt_matching_this_machine(
        tree=_TREE, target=_FILE_LIST, scope=dict(_UNNARROWED)
    )
    assert _run_main(tmp_path, monkeypatch, receipt) == 0
    out = capsys.readouterr().out
    assert "✅ 可采信" in out
    assert "收集面被收窄" in out and "位置参数" in out
    assert "收集面被收窄或不可审计" not in out
    assert "收集面未被收窄" not in out


def _header(out: str) -> str:
    return next(line for line in out.splitlines() if line.lstrip().startswith("目标"))


def test_target_header_and_scope_line_agree(tmp_path, monkeypatch, capsys) -> None:
    """目标行与收集面行同源：不会一行列文件清单、另一行写「未被收窄」，
    也不会一行写「全量」、另一行写「被收窄」（旧夹具 target="" + --ignore 就是这样）。"""
    _run_main(tmp_path, monkeypatch, _receipt_matching_this_machine(
        tree=_TREE, target=_FILE_LIST, scope=dict(_UNNARROWED)))
    assert "59 个位置参数" in _header(capsys.readouterr().out)

    _run_main(tmp_path, monkeypatch, _receipt_matching_this_machine(
        tree=_TREE, target=_TREE, scope=dict(_UNNARROWED)))
    assert "仓根" in _header(capsys.readouterr().out)

    _run_main(tmp_path, monkeypatch, _receipt_matching_this_machine(tree=_TREE))
    out = capsys.readouterr().out
    assert "收集面被收窄" in out                 # 默认夹具带 --ignore=scripts/archive
    assert "全量" not in _header(out)
    assert "仓根" in _header(out)


def test_a_real_run_writes_scope_and_xfail_counts_into_its_receipt(tmp_path) -> None:
    """端到端：接线也要有人测。

    上面的单测只证明 ``_collection_scope`` 算得对、校验器读得对。若有人把
    ``"scope": _collection_scope(session)`` 那一行删掉，两边仍然全绿——门只
    覆盖它的返回值，覆盖不到「有没有接上」。这里真起一次 pytest，从它自己
    打印的收据路径把收据读回来。
    """
    import re
    import subprocess

    keyword = "main_blocks_zero_count"  # 恰好选中一条，便于对 collected 定值
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider",
         "tests/test_check_receipt_zero_count_gate.py", "-k", keyword],
        cwd=Path(__file__).resolve().parents[1],
        # 收据写到 tmp_path，不污染全机收据目录（FWP_TEST_RECEIPT_DIR 见
        # tests/test_receipt_pointer_isolation.py）。
        env={"HOME": str(Path.home()), "PATH": "/opt/homebrew/bin:/usr/bin:/bin",
             "TMPDIR": "/tmp", "FWP_TEST_RECEIPT_DIR": str(tmp_path)},
        capture_output=True, text=True, timeout=600,
    )
    assert proc.returncode == 0, proc.stdout[-2000:]
    match = re.search(r"读数收据: (\S+\.json)", proc.stdout)
    assert match, proc.stdout[-2000:]
    receipt = json.loads(Path(match.group(1)).read_text(encoding="utf-8"))

    scope = receipt["scope"]
    assert scope["keyword"] == keyword           # 收窄旋钮真的落账
    assert scope["collected"] == 1              # 实收数真的落账
    assert scope["ignore"] == [] and scope["maxfail"] == 0
    # xfailed/xpassed 必须在 counts 里，否则收执对账永远不平（见上一条反向锁）
    assert {"xfailed", "xpassed"} <= set(receipt["counts"])
    ok, _ = ctr.check_collected_matches_counts(receipt)
    assert ok is True
    # 写方与检方对同一个 target 的理解要一致：位置参数逐字落账，检方认得出它不是仓根
    assert receipt["target"] == "tests/test_check_receipt_zero_count_gate.py"
    ok, message = ctr.describe_collection_scope(receipt)
    assert ok is False
    assert "位置参数" in message and f"keyword={keyword}" in message
