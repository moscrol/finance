"""预注册号「先占后用」取号器（scripts/claim_ledger_id.py，R-20260828-01）。

治的形状：预注册号旧取法是 check-then-act（分支上读当日 max、落盘占号不原子），
2026-08-27 单日四例撞号且双向避撞不收敛。取号器把「占号」做成 flock 锁内的
原子预占：max(主干台账, 登记簿) + 1，追加登记簿；坏行/锁超时/git 失败一律
fail-closed 不发号。
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "claim_ledger_id.py"
_spec = importlib.util.spec_from_file_location("claim_ledger_id", _SCRIPT)
cli = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("claim_ledger_id", cli)
_spec.loader.exec_module(cli)

DATE = "20260828"


@pytest.fixture()
def ledger_repo(tmp_path: Path) -> Path:
    """最小 git 仓：一份含历史段与超码后缀行的台账，claim 用 --ledger-ref HEAD 读。"""
    repo = tmp_path / "repo"
    (repo / "docs").mkdir(parents=True)
    (repo / "docs" / "prediction-ledger.md").write_text(
        "\n".join(
            [
                "# Prediction Ledger",
                "",
                "### Open（pending）",
                "",
                "| ID | 来源 | outcome |",
                "|---|---|---|",
                f"| `R-{DATE}-02` | 工单 a | `pending` |",
                f"| `R-{DATE}-01` | 工单 b | `pending` |",
                "| `R-20260827-14` | 前一日的号不参与今日 max | `pending` |",
                "",
                "### 历史回填段",
                "",
                "| `R-20260827-07a` | 超码后缀留档行（前缀匹配读成 -07，无害） | 保持 |",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    for cmd in (
        ["git", "init", "-q"],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A"],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "seed"],
    ):
        subprocess.run(cmd, cwd=repo, check=True)
    return repo


def _claim_cmd(repo: Path, claims: Path, branch: str, date: str = DATE) -> list[str]:
    return [
        sys.executable,
        str(_SCRIPT),
        "claim",
        "--branch",
        branch,
        "--date",
        date,
        "--repo",
        str(repo),
        "--ledger-ref",
        "HEAD",
        "--no-fetch",
        "--claims-file",
        str(claims),
    ]


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=60)


def test_first_claim_continues_from_ledger_max(ledger_repo: Path, tmp_path: Path):
    """空登记簿：号从台账当日 max（-02）续，前一日号不掺和。"""
    claims = tmp_path / "claims.jsonl"
    proc = _run(_claim_cmd(ledger_repo, claims, "feat/x"))
    assert proc.returncode == 0, proc.stderr
    assert f"R-{DATE}-03" in proc.stdout
    rows = [json.loads(x) for x in claims.read_text().splitlines()]
    assert [r["id"] for r in rows] == [f"R-{DATE}-03"]


def test_claims_ledger_double_source_max(ledger_repo: Path, tmp_path: Path):
    """登记簿已预占 -05（> 台账 max -02）→ 下一号 -06：两个来源都参与仲裁。

    只看台账会发出 -03，与已预占未落盘的 -05 无冲突假象下重蹈撞号覆辙。
    """
    claims = tmp_path / "claims.jsonl"
    claims.write_text(
        json.dumps({"id": f"R-{DATE}-05", "branch": "other", "ts": "t"}) + "\n",
        encoding="utf-8",
    )
    proc = _run(_claim_cmd(ledger_repo, claims, "feat/y"))
    assert proc.returncode == 0, proc.stderr
    assert f"R-{DATE}-06" in proc.stdout


def test_concurrent_claims_unique_and_consecutive(ledger_repo: Path, tmp_path: Path):
    """并发压测（工单验收 1）：8 进程同时 claim，号两两不同且连续。

    这是本单要害——flock 不在（或失效）时这里会出现同号。
    """
    claims = tmp_path / "claims.jsonl"
    procs = [
        subprocess.Popen(
            _claim_cmd(ledger_repo, claims, f"feat/c{i}"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for i in range(8)
    ]
    outs = [p.communicate(timeout=120) for p in procs]
    assert all(p.returncode == 0 for p in procs), [o[1] for o in outs]
    rows = [json.loads(x)["id"] for x in claims.read_text().splitlines()]
    assert len(rows) == 8
    assert len(set(rows)) == 8, f"出现同号：{sorted(rows)}"
    nns = sorted(int(r.rsplit("-", 1)[1]) for r in rows)
    assert nns == list(range(3, 11)), f"号不连续：{nns}"


def test_corrupt_claims_line_fails_closed(ledger_repo: Path, tmp_path: Path):
    """登记簿坏一行 → 报错退出不发号（工单验收 4）；跳行续发=fail-open 复辟。"""
    claims = tmp_path / "claims.jsonl"
    claims.write_text('{"id": "R-20260828-05"\n', encoding="utf-8")  # 截断的 JSON
    proc = _run(_claim_cmd(ledger_repo, claims, "feat/z"))
    assert proc.returncode == 2
    assert "损坏" in proc.stderr
    assert claims.read_text().count("\n") == 1  # 未追加新行


def test_self_report_contains_four_fields(ledger_repo: Path, tmp_path: Path):
    """自述四项（工单验收 2）：主干 revision / 台账 max / 登记簿 max / 取到号。"""
    claims = tmp_path / "claims.jsonl"
    proc = _run(_claim_cmd(ledger_repo, claims, "feat/r"))
    assert proc.returncode == 0
    for needle in ("主干 revision", "台账", "登记簿", "取到"):
        assert needle in proc.stdout, f"自述缺「{needle}」：\n{proc.stdout}"


def test_supersuffix_rows_do_not_break_parsing(ledger_repo: Path, tmp_path: Path):
    """超码后缀行（-07a）前缀匹配读成 -07：不炸、不占新号（前一日，与今日无关）。"""
    claims = tmp_path / "claims.jsonl"
    proc = _run(_claim_cmd(ledger_repo, claims, "feat/s", date="20260827"))
    assert proc.returncode == 0
    # 该日台账 max=-14（-07a 读作 -07 不超过它）→ 发 -15
    assert "R-20260827-15" in proc.stdout


def test_list_filters_by_date(ledger_repo: Path, tmp_path: Path):
    claims = tmp_path / "claims.jsonl"
    _run(_claim_cmd(ledger_repo, claims, "feat/a"))
    _run(_claim_cmd(ledger_repo, claims, "feat/b", date="20260830"))
    proc = _run(
        [
            sys.executable,
            str(_SCRIPT),
            "list",
            "--date",
            DATE,
            "--claims-file",
            str(claims),
        ]
    )
    assert proc.returncode == 0
    assert f"R-{DATE}-03" in proc.stdout
    assert "R-20260830-01" not in proc.stdout


def test_number_overflow_fails_closed(ledger_repo: Path, tmp_path: Path):
    """两位号用尽（>99）→ 报错不发号，升位属人工裁决。"""
    claims = tmp_path / "claims.jsonl"
    claims.write_text(
        json.dumps({"id": f"R-{DATE}-99", "branch": "o", "ts": "t"}) + "\n",
        encoding="utf-8",
    )
    proc = _run(_claim_cmd(ledger_repo, claims, "feat/o"))
    assert proc.returncode == 2
    assert "用尽" in proc.stderr
