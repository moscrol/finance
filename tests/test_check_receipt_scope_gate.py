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
