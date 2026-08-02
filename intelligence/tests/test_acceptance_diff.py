"""逐题对比工具的回归测试。

锁住的核心行为：**同输入复跑的差异不能被报成信号**。board 实测过，事实层
0% 翻转、措辞层 33%——把两者压成一个「变了 N 题」，这个数就不能用来判断
「这一刀有没有用」，而那正是这个工具存在的唯一理由。
"""

from __future__ import annotations

import json

from intelligence.eval import acceptance_diff


def _run_payload(case_id: str, tier: str, turn: dict) -> dict:
    return {
        "generated_at": "2026-08-02T00:00:00Z",
        "base": "http://127.0.0.1:8792",
        "preflight_ok": True,
        "cases": [{"case_id": case_id, "tier": tier, "turns": [turn], "blocked_reason": None}],
    }


def _write(tmp_path, name: str, payload: dict):
    path = tmp_path / name
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_observable_only_change_is_not_reported_as_truth_change(tmp_path, capsys):
    """降级计数抖动 ±1 但真值不变时，只进「可观测量」段，不进「真值变化」段。

    实测基准：20260801T025854Z 与 034001Z 是同输入复跑，真值 0 变化，
    但 4 道题的降级计数差 1。那 4 题不是回归。
    """
    base_turn = {
        "question": "q",
        "answer": "a",
        "status": "completed",
        "degrades": [],
        "evidence_bound": 3,
        "invoked_skill_ids": ["daily-review"],
        "elapsed_s": 10.0,
    }
    before = _write(tmp_path, "before.json", _run_payload("A1-market-overview", "high_freq", base_turn))
    after = _write(
        tmp_path,
        "after.json",
        _run_payload(
            "A1-market-overview",
            "high_freq",
            {**base_turn, "degrades": ["盘面快照回退"]},
        ),
    )

    assert acceptance_diff.main([str(before), "--after", str(after)]) == 0
    out = capsys.readouterr().out
    assert "## 真值判定：无变化" in out
    assert "降级 0→1" in out
    assert "0 题真值变化" in out


def test_no_shared_cases_exits_nonzero(tmp_path, capsys):
    """两侧没有共同题目时必须失败退出，而不是打印一份「无变化」的空报告。

    空报告和「真的没变化」长得一模一样，而后者是要拿来做决定的——
    这正是本仓反复栽过的那类静默降级（覆盖率正常、值是空壳）。
    """
    before = _write(
        tmp_path,
        "before.json",
        _run_payload("A1-market-overview", "high_freq", {"status": "completed"}),
    )
    after = _write(
        tmp_path,
        "after.json",
        _run_payload("C8-nonexistent-table", "long_tail", {"status": "completed"}),
    )
    assert acceptance_diff.main([str(before), "--after", str(after)]) == 2
    assert "无法对比" in capsys.readouterr().err


def test_unreadable_run_is_skipped_not_silently_empty(tmp_path, capsys):
    """损坏的 run 文件要显式报出来，不能被当成「这份里没有题」。"""
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")
    before = _write(
        tmp_path,
        "before.json",
        _run_payload("A1-market-overview", "high_freq", {"status": "completed"}),
    )
    acceptance_diff.main([str(tmp_path / "broken.json"), str(before), "--after", str(before)])
    assert "跳过无法读取的 run" in capsys.readouterr().err


def test_noise_verdict_uses_measured_flip_rate():
    """判据层的噪声等级来自实测翻转率，不是拍脑袋。"""
    assert acceptance_diff._LAYER_FLIP_RATE["fact"] == 0.0
    assert acceptance_diff._LAYER_FLIP_RATE["product_language"] > acceptance_diff._NOISE_THRESHOLD

    def state(layers):
        return acceptance_diff.CaseState(
            case_id="X", tier="high_freq", truth="FAIL", status="completed",
            degrades=0, evidence_bound=0, skills=(), reason_code="", elapsed_s=0.0,
            layers=layers,
        )

    assert acceptance_diff._noise_verdict(state(("fact",)), state(())) == "signal"
    assert acceptance_diff._noise_verdict(state(("product_language",)), state(())) == "noise-suspect"
    # 未实测过的层既不当信号也不当噪声，避免给一个没有依据的绿灯
    assert acceptance_diff._noise_verdict(state(("refusal",)), state(())) == "unknown"
