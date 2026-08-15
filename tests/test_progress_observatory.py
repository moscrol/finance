"""进度观测台 Phase 1–2：CLI 缝（--check / render / 趋势 SVG）。夹具在 testdata/progress_observatory/。"""

from __future__ import annotations

import json
import re
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


def _batch(generated_at: str = "20260815T100000Z", bounds: list[int] | None = None) -> str:
    if bounds is None:
        bounds = [2, 0]
    return json.dumps(
        {
            "generated_at": generated_at,
            "sha256": "deadbeef",
            "cases": [
                {"case_id": f"A{i}", "turns": [{"evidence_bound": bound}]}
                for i, bound in enumerate(bounds, start=1)
            ],
        },
        ensure_ascii=False,
        indent=2,
    )


def _batch_no_eb(generated_at: str) -> str:
    return json.dumps(
        {
            "generated_at": generated_at,
            "cases": [{"case_id": "Z", "turns": [{"answer": "no key"}]}],
        },
        ensure_ascii=False,
    )


def _ledger_backfills() -> str:
    return """# Prediction Ledger

### Open（pending）

| ID | 来源 | fix_type | verification_prediction | 怎么验 | outcome |
|---|---|---|---|---|---|
| `R-1` | t | `EVAL_ONLY` | p | v | `pending` |

### 2026-08-01 Round 1 回填

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-a` | e | `confirmed` | x |
| `R-b` | e | `refuted` | x |

### 2026-08-02 Round 2 回填

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-c` | e | `confirmed` | x |
| `R-d` | e | `confirmed` | x |

### 2026-08-04 Round 4 仅 pending 回填

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-skip` | e | `pending` | 保持 Open |

### 2026-08-03 Round 3 回填

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-e` | e | `confirmed` | x |
| `R-f` | e | `refuted` | x |
| `R-g` | e | `pending` | 保持 Open |

### Closed

| ID | 来源 | fix_type | verification_prediction | outcome | evidence |
|---|---|---|---|---|---|
| `R-3` | t | `EVAL_ONLY` | p | `confirmed` | e |
"""


def _recall_baseline() -> str:
    return """# recall@k 首份基线

- 标注集：`intelligence/eval/cases/retrieval_recall_v1.jsonl`

## 1. 总表

| 通道 | n | recall@1 | recall@3 | recall@5 | hit@1 | hit@3 | hit@5 |
|---|---|---|---|---|---|---|---|
| user_memory | 15 | 15.6% | 42.2% | 42.2% | 26.7% | 46.7% | 46.7% |
| kb_rag | 2 | — | — | — | — | — | — |
"""


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


def _tree(
    dst: Path,
    roadmap: str,
    *,
    s4_done: bool = True,
    claimed: str = SHA_A,
    health: str = SHA_A,
    ledger: str | None = None,
    batches: dict[str, str] | None = None,
    recall: str | None = None,
) -> Path:
    _write(dst / "docs" / "roadmap.md", roadmap)
    _write(dst / "docs" / "prediction-ledger.md", ledger if ledger is not None else _ledger())
    _write(
        dst / "docs" / "superpowers" / "specs" / "2026-08-15-bookgap-index.md",
        _bookgap(s4_done=s4_done),
    )
    _write(dst / "docs" / "handoffs" / "inflight" / "main.md", _inflight(claimed))
    _write(
        dst / "docs" / "handoffs" / "2026-08-15-runtime-trace-triage-loop.md",
        "### Round 6 批 #3\n\n- 判定：PASS\n",
    )
    if batches is None:
        _write(dst / "intelligence" / "eval" / "runs" / "batch.json", _batch())
    else:
        for name, body in batches.items():
            _write(dst / "intelligence" / "eval" / "runs" / name, body)
    if recall is not None:
        _write(dst / "docs" / "verification" / "2026-08-15-recall-baseline.md", recall)
    _write(dst / "health.json", _health(health))
    _write(dst / "pulls.json", _pulls())
    return dst


def _render(tree: Path) -> tuple[subprocess.CompletedProcess[str], str]:
    first = _git_repo(tree)
    _write(tree / "health.json", _health(first))
    out = tree / "out.html"
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
    html = out.read_text(encoding="utf-8") if out.is_file() else ""
    return proc, html


def _svg_meta(html: str, svg_id: str) -> tuple[int, list[float]]:
    match = re.search(
        rf'<svg[^>]*\bid="{re.escape(svg_id)}"[^>]*>',
        html,
    )
    assert match, f"missing svg#{svg_id} in {html[:800]}"
    tag = match.group(0)
    n_match = re.search(r'data-n="(\d+)"', tag)
    v_match = re.search(r'data-values="([^"]*)"', tag)
    assert n_match and v_match, tag
    values = [float(part) for part in v_match.group(1).split(",") if part]
    return int(n_match.group(1)), values


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


def test_render_fixture_batches_make_svg_with_three_delivery_points(tmp_path: Path) -> None:
    roadmap = (FIXTURE / "good" / "roadmap.md").read_text(encoding="utf-8")
    tree = _tree(
        tmp_path / "curves",
        roadmap,
        ledger=_ledger_backfills(),
        batches={
            "late.json": _batch("20260803T000000Z", [0, 0]),
            "mid.json": _batch("20260802T000000Z", [1, 1]),
            "early.json": _batch("20260801T000000Z", [2, 0]),
            "no-gen.json": json.dumps(
                {"cases": [{"case_id": "X", "turns": [{"evidence_bound": 9}]}]}
            ),
            "no-eb.json": _batch_no_eb("20260804T000000Z"),
            "broken.json": "{not-json",
        },
        recall=_recall_baseline(),
    )
    proc, html = _render(tree)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert "<script" not in html.lower()
    assert "fonts.googleapis" not in html.lower()
    assert "@font-face" not in html.lower()
    n, values = _svg_meta(html, "curve-delivery")
    assert n == 3
    assert values == [0.5, 1.0, 0.0]
    assert html.count('id="curve-delivery"') == 1
    delivery_svg = html[html.index('id="curve-delivery"') : html.index("</svg>", html.index('id="curve-delivery"'))]
    assert delivery_svg.count("<circle") == 3
    hit_n, hit_values = _svg_meta(html, "curve-hit")
    assert hit_n == 3
    assert hit_values == [0.5, 1.0, 0.5]
    recall_n, recall_values = _svg_meta(html, "curve-recall")
    assert recall_n == 1
    assert recall_values == [0.422]


def test_render_missing_curve_sources_do_not_invent_points(tmp_path: Path) -> None:
    roadmap = (FIXTURE / "good" / "roadmap.md").read_text(encoding="utf-8")
    tree = _tree(
        tmp_path / "empty-curves",
        roadmap,
        ledger=_ledger(),
        batches={
            "no-gen.json": json.dumps(
                {"cases": [{"case_id": "X", "turns": [{"evidence_bound": 1}]}]}
            ),
            "no-eb.json": _batch_no_eb("20260801T000000Z"),
            "broken.json": "{not-json",
        },
    )
    proc, html = _render(tree)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert 'id="curve-delivery"' not in html
    assert 'id="curve-hit"' not in html
    assert 'id="curve-recall"' not in html
    assert "0.422" not in html
    assert re.search(r"data-n=\"[1-9]", html) is None
    assert "未闭合的最低层" in proc.stdout
