"""多棵树并跑时，`latest.json` 会张冠李戴——收据指针必须按树隔离。

失败形状（2026-09-22 实测，两次撞上）：

- 本树全量刚跑完 12442 passed，去读 `~/.finance-runtime/test-receipts/latest.json`，
  拿到的是另一棵树的读数（`fwp-wt-research-empty-delivery-0922`，7585 passed / 1 failed）；
  再过一小时又变成第三棵树（`mutation-timeout-attribution-20260922`）。
- `scripts/session_facts.sh` 的判据是「收据 revision == 本树 HEAD 且 dirty=false →
  可直接采信，不必重跑」。同 base 的两棵干净树 revision 天然相等，于是它会拿**别人跑的**
  读数劝你别重跑。
- `scripts/run_main_gate.sh` 曾在跑完 pytest 后立刻读 latest.json，中间别人的全量一结束，
  它就把别人的 passed/failed 抄成本次门禁结果。（#814 已改成每轮显式传
  `FWP_TEST_RECEIPT_PATH`、读自己那张 `gate-*/pytest.json`，完全不碰共享指针——
  主动调用方拿自己那张，比「猜最新那张」更强，所以它不再是本指针的消费者。）

所以 conftest 另写一份按树区分的指针，被动读者（`session_facts.sh`）与校验器改读它。
命名规则要在 **Python 与 shell 两侧**算出同一个名字，这种跨语言接缝最容易单边漂移，
故本文件把它锁成测试：改了任一侧而不改另一侧即红。
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

import conftest as root_conftest

_REPO = Path(__file__).resolve().parents[1]
_SCRIPT = _REPO / "scripts" / "check_test_receipt.py"
_spec = importlib.util.spec_from_file_location("check_test_receipt_pointer", _SCRIPT)
ctr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ctr)

# run_main_gate.sh 自 #814 起读自己那张显式收据，不再是共享指针的消费者（见模块 docstring）。
_SHELL_CONSUMERS = ("scripts/session_facts.sh",)
_ELSEWHERE = Path.home() / "someone-elses-tree"  # 「别人的树」——从位置推导，不写死家目录
_SHELL_RULE = "tr -c 'A-Za-z0-9._-' '_'"


@pytest.mark.parametrize(
    "tree",
    [
        _REPO,
        Path.home() / "finance-workspace-private",
        Path("/private/var/folders/t1/tmpdir/tree"),
    ],
)
def test_pointer_name_is_a_safe_filename(tree: Path) -> None:
    name = root_conftest.latest_pointer_name(tree)
    assert name.startswith("latest-") and name.endswith(".json")
    assert "/" not in name and " " not in name
    assert Path(name).name == name  # 不会意外指到别的目录


def test_different_trees_get_different_pointers() -> None:
    a = root_conftest.latest_pointer_name(Path.home() / "tree-a")
    b = root_conftest.latest_pointer_name(Path.home() / "tree-b")
    assert a != b


@pytest.mark.parametrize("relpath", _SHELL_CONSUMERS)
def test_shell_consumers_use_the_same_naming_rule(relpath: str) -> None:
    """跨语言锁：shell 侧的规则字面量必须在，且算出的名字与 Python 逐字相同。"""
    text = (_REPO / relpath).read_text(encoding="utf-8")
    assert _SHELL_RULE in text, f"{relpath} 不再用约定的 slug 规则"
    assert "latest-$" in text, f"{relpath} 没在读按树区分的指针"

    for tree in (str(Path.home() / "fwp-wt-x"), "/private/var/folders/t1/q6/T/tree.1"):
        shell = subprocess.run(
            ["sh", "-c", f"printf '%s' \"$1\" | {_SHELL_RULE}", "sh", tree],
            capture_output=True, text=True, check=True,
        ).stdout
        assert f"latest-{shell}.json" == root_conftest.latest_pointer_name(Path(tree))


def test_python_rule_is_the_one_the_shell_can_reproduce() -> None:
    """反向锁：规则只能用「非白名单字符→下划线」这类 shell 也能算的写法。

    若有人把 Python 侧换成哈希/取 basename（shell 不易复制），上面那条跨语言锁
    会红——这条把「为什么不能换」写在判据里，省得下一个人以为是巧合。
    """
    sample = str(Path.home() / "fwp-wt-x")
    assert root_conftest.latest_pointer_name(Path(sample)) == (
        "latest-" + re.sub(r"[^A-Za-z0-9._-]", "_", sample) + ".json"
    )


def test_default_receipt_prefers_this_tree(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(ctr, "RECEIPT_DIR", tmp_path)
    tree = Path.home() / "fwp-wt-mine"
    mine = tmp_path / root_conftest.latest_pointer_name(tree)
    (tmp_path / "latest.json").write_text("{}", encoding="utf-8")
    assert ctr.default_receipt(tree) == tmp_path / "latest.json"  # 本树还没跑过 → 回落
    mine.write_text("{}", encoding="utf-8")
    assert ctr.default_receipt(tree) == mine  # 本树跑过 → 只认自己的


def _receipt(tree: str) -> dict:
    return {
        "revision": ctr._git("rev-parse", "HEAD") or "(unknown)",
        "interpreter": sys.executable,
        "python_version": ctr.platform.python_version(),
        "dependency_fingerprint": ctr._fingerprint(),
        "tree": tree,
        "dirty": False,
        "worktree_dirty_total": 0,
        "dependency_gate_bypassed": False,
        "target": tree,
        "scope": {"ignore": [], "ignore_glob": [], "deselect": [], "keyword": "",
                  "markexpr": "", "maxfail": 0, "last_failed": False, "collected": 3},
        "counts": {"passed": 3, "failed": 0, "error": 0, "skipped": 0,
                   "xfailed": 0, "xpassed": 0},
        "failed_ids": [],
        "exit_status": 0,
        "finished_at": "2026-09-22T13:30:58+00:00",
    }


def test_default_path_refuses_a_receipt_from_another_tree(
    tmp_path, monkeypatch, capsys
) -> None:
    monkeypatch.setattr(ctr, "RECEIPT_DIR", tmp_path)
    (tmp_path / "latest.json").write_text(
        json.dumps(_receipt(str(_ELSEWHERE))), encoding="utf-8"
    )
    monkeypatch.setattr(sys, "argv", ["check_test_receipt.py"])
    assert ctr.main() == 1
    out = capsys.readouterr().out
    assert "默认收据来自别的树" in out
    assert str(_ELSEWHERE) in out
    assert "✅ 可采信" not in out


def test_an_explicitly_given_receipt_may_come_from_another_tree(
    tmp_path, monkeypatch, capsys
) -> None:
    """跨树采信本身是收据制度的目的（复核者在自己树上验执行方的收据）。

    要拦的是「默认去读全机 latest.json，结果读到别人的」，不是跨树本身——
    这条对照用例挡住把拦截写宽。
    """
    path = tmp_path / "theirs.json"
    path.write_text(json.dumps(_receipt(str(_ELSEWHERE))), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["check_test_receipt.py", str(path)])
    ctr.main()
    out = capsys.readouterr().out
    assert "默认收据来自别的树" not in out
    assert f"来自树   {_ELSEWHERE}" in out  # 但必须摆到明面上


def test_a_real_run_writes_both_pointers_into_the_dir_it_was_told_to_use(
    tmp_path,
) -> None:
    """端到端：FWP_TEST_RECEIPT_DIR 要真被认，且本树指针要真被写。

    run_main_gate.sh 一直在读这个环境变量，而 conftest 原本写死家目录——
    设了变量的人收据写到 A、脚本去 B 找，报「没找到收据」exit 4。
    """
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider",
         "tests/test_check_receipt_zero_count_gate.py", "-k", "main_blocks_zero_count"],
        cwd=_REPO,
        env={"HOME": str(Path.home()), "PATH": "/opt/homebrew/bin:/usr/bin:/bin",
             "TMPDIR": "/tmp", "FWP_TEST_RECEIPT_DIR": str(tmp_path)},
        capture_output=True, text=True, timeout=600,
    )
    assert proc.returncode == 0, proc.stdout[-2000:]

    written = sorted(p.name for p in tmp_path.glob("*.json"))
    pointer = root_conftest.latest_pointer_name(_REPO)
    assert "latest.json" in written, written          # 旧读法不破
    assert pointer in written, written                # 本树指针
    assert len(written) == 3, written                 # 另有带时间戳的那张

    same = json.loads((tmp_path / pointer).read_text(encoding="utf-8"))
    assert same["tree"] == str(_REPO)
    assert same["counts"]["passed"] == 1
