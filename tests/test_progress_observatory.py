"""进度观测台 Phase 1：CLI 缝（--check / render）。夹具在 testdata/progress_observatory/。"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "progress_observatory.py"
FIXTURE = Path(__file__).parent / "testdata" / "progress_observatory"
SHA_A = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
SHA_B = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"


def _run(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd or ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _bookgap(*, s4_done: bool) -> str:
    body = "# 书距清单\n\n## 4. 执行记录（各 agent 追加）\n\n"
    if s4_done:
        body += "### S4 · recall@k 标注集 v1\n\n- 交付：基线在场。\n\n### S5 · 独立出题人 uq15\n\n- 交付：题集在场。\n"
    return body


def _ledger() -> str:
    return """# Prediction Ledger

### Open（pending）

| ID | 来源 | fix_type | verification_prediction | 怎么验 | outcome |
|---|---|---|---|---|---|
| `R-1` | t | `EVAL_ONLY` | p | v | `pending` |
| `R-2` | t | `EVAL_ONLY` | p | v | `pending` |

### Closed

| ID | 来源 | fix_type | verification_prediction | outcome | evidence |
|---|---|---|---|---|---|
| `R-3` | t | `EVAL_ONLY` | p | `confirmed` | e |
| `R-4` | t | `EVAL_ONLY` | p | `refuted` | e |
"""


def _inflight(claimed: str) -> str:
    return (
        "# 在途交接 · main\n\n"
        "## 当前状态\n\n"
        f"- **8792 = `{claimed}`**（夹具）\n"
    )


def _batch() -> str:
    return json.dumps(
        {
            "generated_at": "20260815T100000Z",
            "sha256": "deadbeef",
            "cases": [
                {"case_id": "A1", "turns": [{"evidence_bound": 2}]},
                {"case_id": "A2", "turns": [{"evidence_bound": 0}]},
            ],
        },
        ensure_ascii=False,
        indent=2,
    )


def _health(revision: str) -> str:
    return json.dumps({"runtime": {"source_revision": revision, "source_dirty": False}})


def _pulls() -> str:
    return json.dumps(
        [
            {
                "number": 45,
                "title": "docs(observatory): Phase 0",
                "merged_at": "2026-08-15T15:00:00Z",
            }
        ]
    )


def _tree(dst: Path, roadmap: str, *, s4_done: bool = True, claimed: str = SHA_A, health: str = SHA_A) -> Path:
    _write(dst / "docs" / "roadmap.md", roadmap)
    _write(dst / "docs" / "prediction-ledger.md", _ledger())
    _write(
        dst / "docs" / "superpowers" / "specs" / "2026-08-15-bookgap-index.md",
        _bookgap(s4_done=s4_done),
    )
    _write(dst / "docs" / "handoffs" / "inflight" / "main.md", _inflight(claimed))
    _write(
        dst / "docs" / "handoffs" / "2026-08-15-runtime-trace-triage-loop.md",
        "### Round 6 批 #3\n\n- 判定：PASS\n",
    )
    _write(dst / "intelligence" / "eval" / "runs" / "batch.json", _batch())
    _write(dst / "health.json", _health(health))
    _write(dst / "pulls.json", _pulls())
    return dst


def _git_repo(dst: Path, *, extra_commit: bool = True) -> str:
    def git(*args: str) -> str:
        out = subprocess.run(
            ["git", "-C", str(dst), *args],
            check=True,
            capture_output=True,
            text=True,
        )
        return out.stdout.strip()

    git("init")
    git("config", "user.email", "obs@example.test")
    git("config", "user.name", "observatory")
    git("add", "-A")
    git("commit", "-m", "base")
    first = git("rev-parse", "HEAD")
    if extra_commit:
        _write(dst / "extra.txt", "x\n")
        git("add", "extra.txt")
        git("commit", "-m", "ahead")
    return first


@pytest.fixture
def good_tree(tmp_path: Path) -> Path:
    roadmap = (FIXTURE / "good" / "roadmap.md").read_text(encoding="utf-8")
    return _tree(tmp_path / "good", roadmap)


def test_check_good_roadmap_exits_zero(good_tree: Path) -> None:
    proc = _run(
        ["--check", "--root", str(good_tree), "--health-file", str(good_tree / "health.json")]
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout


def test_check_bad_roadmap_schema_exits_nonzero() -> None:
    proc = _run(
        [
            "--check",
            "--root",
            str(FIXTURE / "bad"),
            "--health-file",
            str(FIXTURE / "bad" / "health.json"),
        ]
    )
    assert proc.returncode != 0
    combined = proc.stderr + proc.stdout
    assert "ROADMAP_SCHEMA" in combined


def test_check_l1_stale_when_bookgap_done_but_roadmap_planned(tmp_path: Path) -> None:
    roadmap = (FIXTURE / "good" / "roadmap.md").read_text(encoding="utf-8")
    roadmap = roadmap.replace("| L1-S4 | recall 标注集 | done |", "| L1-S4 | recall 标注集 | planned |")
    tree = _tree(tmp_path / "stale", roadmap, s4_done=True)
    proc = _run(["--check", "--root", str(tree), "--health-file", str(tree / "health.json")])
    assert proc.returncode != 0
    assert "L1_STALE" in (proc.stderr + proc.stdout)
    assert "L1-S4" in (proc.stderr + proc.stdout)


def test_check_inflight_revision_mismatch(tmp_path: Path) -> None:
    roadmap = (FIXTURE / "good" / "roadmap.md").read_text(encoding="utf-8")
    tree = _tree(tmp_path / "stale-health", roadmap, claimed=SHA_A, health=SHA_B)
    proc = _run(["--check", "--root", str(tree), "--health-file", str(tree / "health.json")])
    assert proc.returncode != 0
    assert "INFLIGHT_REVISION_STALE" in (proc.stderr + proc.stdout)


def test_render_missing_ledger_fails_loud(tmp_path: Path) -> None:
    roadmap = (FIXTURE / "good" / "roadmap.md").read_text(encoding="utf-8")
    tree = _tree(tmp_path / "noledger", roadmap)
    (tree / "docs" / "prediction-ledger.md").unlink()
    first = _git_repo(tree)
    _write(tree / "health.json", _health(first))
    proc = _run(
        [
            "render",
            "--root",
            str(tree),
            "--health-file",
            str(tree / "health.json"),
            "--pulls-file",
            str(tree / "pulls.json"),
            "--out",
            str(tree / "out.html"),
        ]
    )
    assert proc.returncode != 0
    assert "PREDICTION_LEDGER" in (proc.stderr + proc.stdout)
    assert not (tree / "out.html").exists()


def test_render_answers_five_questions_and_splits_l2(tmp_path: Path) -> None:
    roadmap = (FIXTURE / "good" / "roadmap.md").read_text(encoding="utf-8")
    tree = _tree(tmp_path / "render", roadmap)
    first = _git_repo(tree)
    _write(tree / "health.json", _health(first))
    out = tree / "var" / "observatory" / "index.html"
    proc = _run(
        [
            "render",
            "--root",
            str(tree),
            "--health-file",
            str(tree / "health.json"),
            "--pulls-file",
            str(tree / "pulls.json"),
            "--out",
            str(out),
            "--as-of",
            "2026-08-15",
        ]
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    html = out.read_text(encoding="utf-8")
    text = proc.stdout
    assert "未闭合的最低层" in text and "P1" in text
    assert "本周合并" in text and "#45" in text
    assert "账本 open" in text and "2" in text
    assert "生产落后" in text
    assert "下一个裁决" in text and "是否切 8792" in text
    assert 'id="l2-local"' in html
    assert 'id="l2-repo"' in html
    assert "参照系" in html and "推进" in html and "运行" in html


def test_render_is_idempotent(tmp_path: Path) -> None:
    roadmap = (FIXTURE / "good" / "roadmap.md").read_text(encoding="utf-8")
    tree = _tree(tmp_path / "idemp", roadmap)
    first = _git_repo(tree)
    _write(tree / "health.json", _health(first))
    out = tree / "out.html"
    args = [
        "render",
        "--root",
        str(tree),
        "--health-file",
        str(tree / "health.json"),
        "--pulls-file",
        str(tree / "pulls.json"),
        "--out",
        str(out),
        "--as-of",
        "2026-08-15",
    ]
    first_run = _run(args)
    html1 = out.read_text(encoding="utf-8")
    second_run = _run(args)
    html2 = out.read_text(encoding="utf-8")
    assert first_run.returncode == 0 and second_run.returncode == 0
    assert html1 == html2
    assert first_run.stdout == second_run.stdout


def test_check_rejects_over_120_lines(tmp_path: Path) -> None:
    roadmap = (FIXTURE / "good" / "roadmap.md").read_text(encoding="utf-8")
    roadmap = roadmap + ("\n# pad\n" * 80)
    tree = _tree(tmp_path / "long", roadmap)
    proc = _run(["--check", "--root", str(tree), "--health-file", str(tree / "health.json")])
    assert proc.returncode != 0
    assert "ROADMAP_BUDGET" in (proc.stderr + proc.stdout)


def test_testdata_fixtures_exist() -> None:
    assert (FIXTURE / "good" / "roadmap.md").is_file()
    assert (FIXTURE / "bad" / "docs" / "roadmap.md").is_file()
