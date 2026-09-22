"""CLI 侧的证据解析：判据不可靠时必须喊出来，不能悄悄退 0。

2026-09-22 审查在 #850 上压出两条 fail-open：
1. `--scope-total` 给了、但 episode 里解析不出比较范围数 → 范围规则静默且退 0；
2. 日历/资金流证据靠对整份 payload 做子串匹配 → 任一段文本（如 kb_search 的
   检索词）写了「交易日历」就把证据判成取过，规则随即静默。
两条都用真实首跑的 payload 形状复现，这里钉成回归。
"""

import json
from pathlib import Path

import pytest

from scripts import check_answer_claims as cli

QUESTION = "请复盘长电科技（600584）最近一个交易日的表现。"
# 2026-09-21 首跑原句
FLOW_SENTENCE = "成交额放大至 114.90 亿元，显示资金当日集中流入封测方向。"
SCOPE_SENTENCE = "长电科技当日涨幅 7.75%，跑赢其所有归属板块。"


def _episode(requests: list[dict], dates: tuple[str, ...] = ("2026-09-18",)) -> dict:
    return {
        "outcome": {
            "events": [{"kind": "tool_request", "payload": p} for p in requests],
            "evidence": [{"source_date": d} for d in dates],
        }
    }


def _finance_query(metrics: list[str], sector_codes: list[str] | None = None) -> dict:
    filters = []
    if sector_codes is not None:
        filters.append({"field": "sector_code", "op": "in", "value": sector_codes})
    return {
        "name": "finance_query",
        "arguments": {
            "dataset": "sector_stock_daily",
            "metrics": metrics,
            "filters": filters,
        },
    }


def _write_run(tmp_path: Path, answer: str, episode: dict) -> Path:
    run_dir = tmp_path / "run_20260921_183642_325351"
    run_dir.mkdir()
    (run_dir / "run.json").write_text(
        json.dumps({"run_id": run_dir.name, "question": QUESTION}), encoding="utf-8"
    )
    (run_dir / "continuous-episode.json").write_text(
        json.dumps(episode), encoding="utf-8"
    )
    (run_dir / "answer.md").write_text(answer, encoding="utf-8")
    return run_dir


def _build(episode: dict, scope_total=None, calendar_source=None):
    return cli.build_context(
        {"question": QUESTION}, episode, scope_total, calendar_source
    )


def test_fund_flow_evidence_requires_a_registered_metric() -> None:
    episode = _episode([_finance_query(["fund_flow_1d"])])
    context, diagnostics = _build(episode)
    assert context.fund_flow_evidence is True
    assert diagnostics["fund_flow_metrics_seen"] == ["fund_flow_1d"]


def test_amount_metrics_are_not_fund_flow_evidence() -> None:
    # 成交额是活跃度，不是方向——这正是首跑那条越界的来源。
    episode = _episode([_finance_query(["amount", "turnover"])])
    context, diagnostics = _build(episode)
    assert context.fund_flow_evidence is False
    assert diagnostics["fund_flow_metrics_seen"] == []


def test_calendar_keyword_in_tool_arguments_is_not_calendar_evidence() -> None:
    # 旧实现对整份 payload 做子串匹配，这条会把 calendar_evidence 判成 True，
    # 于是「最近一个已收盘交易日」那条规则整篇静默。
    episode = _episode([{"name": "kb_search", "arguments": {"query": "交易日历安排"}}])
    context, diagnostics = _build(episode)
    assert context.calendar_evidence is False
    assert "finance_query 无交易日历 dataset" in diagnostics["calendar_evidence_source"]


def test_calendar_evidence_only_comes_from_an_explicit_source() -> None:
    episode = _episode([])
    context, diagnostics = _build(episode, calendar_source="人工核对 trading_days.py")
    assert context.calendar_evidence is True
    assert diagnostics["calendar_evidence_source"] == "人工核对 trading_days.py"


def test_scope_total_without_parsed_scope_is_degraded(tmp_path: Path) -> None:
    # 取数形状一变（板块不走 filters），比较数就解析不出来。
    episode = _episode([_finance_query(["return_pct"], sector_codes=None)])
    context, diagnostics = _build(episode, scope_total=20)
    assert context.compared_scope_count is None
    assert diagnostics["degraded"], "解析不出比较范围必须显式降级"


def test_parsed_scope_is_not_degraded() -> None:
    episode = _episode([_finance_query(["return_pct"], sector_codes=["A", "B"])])
    context, diagnostics = _build(episode, scope_total=20)
    assert context.compared_scope_count == 2
    assert diagnostics["degraded"] == []


def _run_cli(monkeypatch, run_dir: Path, *extra: str) -> int:
    monkeypatch.setattr("sys.argv", ["check_answer_claims.py", str(run_dir), *extra])
    return cli.main()


def test_cli_exits_2_when_context_is_degraded(monkeypatch, tmp_path, capsys) -> None:
    run_dir = _write_run(
        tmp_path, SCOPE_SENTENCE, _episode([_finance_query(["return_pct"])])
    )
    assert _run_cli(monkeypatch, run_dir, "--scope-total", "20") == 2
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["context_diagnostics"]["degraded"]


def test_cli_exits_1_on_a_real_hit(monkeypatch, tmp_path, capsys) -> None:
    run_dir = _write_run(
        tmp_path, FLOW_SENTENCE, _episode([_finance_query(["amount"])])
    )
    assert _run_cli(monkeypatch, run_dir) == 1
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["rules_hit"] == ["fund_flow_claim_without_flow_evidence"]


def test_cli_exits_0_when_clean(monkeypatch, tmp_path, capsys) -> None:
    run_dir = _write_run(
        tmp_path,
        "成交额放大至 114.90 亿元，成交活跃度显著提升。",
        _episode([_finance_query(["amount"])]),
    )
    assert _run_cli(monkeypatch, run_dir) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["clean"] is True


def test_missing_artifacts_still_exit_2(monkeypatch, tmp_path) -> None:
    empty = tmp_path / "run_empty"
    empty.mkdir()
    assert _run_cli(monkeypatch, empty) == 2


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
