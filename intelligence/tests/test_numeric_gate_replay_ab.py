"""scripts/numeric_gate_replay_ab.py：存证往返保真 + run/diff 端到端（2026-10-01）。

重放工具的价值全在「还原出来的核验对象和线上那一刻一样」。这里按线上写存证的同一序列化
（``contract.to_dict()`` + ``structural.to_dict()``，见 continuous_turn_adapter 落盘处）
造 run 目录，断言还原后门禁结论逐 token 不变；存证格式一改，这里先红。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from intelligence.services import episode_semantic_verifier as esv
from intelligence.services.episode_verifier import VerifiedEpisodeOutcome
from intelligence.tests.test_field_name_units import FLOW, MKT, STOCK
from intelligence.tests.test_numeric_note_false_positives import _dated
from scripts import numeric_gate_replay_ab as replay

CASES = [
    (STOCK, "若市盈率回到 35.2 倍（E1）则减仓。"),
    (STOCK, "若市盈率超过 40 倍（E1）则减仓。"),
    (MKT, "若上证跌破 3150 点（E1）则减仓。"),
    (FLOW, "若机构净卖出超过 5600 万元（E1）则减仓。"),
    (FLOW, "若机构净买入超过 0.56 亿元（E1）则加仓。"),
]


def _payload(row: str, draft: str) -> tuple[VerifiedEpisodeOutcome, str]:
    _, verified = _dated(draft, detail=row)
    text = json.dumps(
        {"contract": verified.contract.to_dict(), "structural_verifier": verified.to_dict()},
        ensure_ascii=False,
        default=str,
    )
    return verified, text


def _tokens(verified: VerifiedEpisodeOutcome) -> dict[int, list[str]]:
    found = esv._novel_numeric_condition_tokens(esv._numbered_sentences(verified.outcome.draft), verified)
    return {int(index): sorted(map(str, tokens)) for index, tokens in found.items()}


@pytest.mark.parametrize(("row", "draft"), CASES)
def test_restored_episode_reaches_the_same_gate_verdict(row: str, draft: str) -> None:
    verified, text = _payload(row, draft)
    restored = replay._restore(json.loads(text), VerifiedEpisodeOutcome)
    assert restored.contract is not None
    assert len(restored.outcome.evidence) == len(verified.outcome.evidence)
    assert _tokens(restored) == _tokens(verified)


def test_run_and_diff_end_to_end(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    for index, (row, draft) in enumerate(CASES):
        run_dir = tmp_path / "runs" / f"run_{index}"
        run_dir.mkdir(parents=True)
        (run_dir / "continuous-episode.json").write_text(_payload(row, draft)[1], encoding="utf-8")
    (tmp_path / "runs" / "broken").mkdir()
    (tmp_path / "runs" / "broken" / "continuous-episode.json").write_text("{}", encoding="utf-8")
    root = str(Path(replay.__file__).resolve().parents[1])
    out = tmp_path / "a.jsonl"
    assert replay.main(["run", "--runs-dir", str(tmp_path), "--code-root", root, "--out", str(out)]) == 0
    summary = capsys.readouterr().out
    # 还原失败要计数并给原因，不静默跳过
    assert "restored=5 failed=1" in summary
    assert "restore-failure x1: KeyError" in summary
    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    flagged = {row["run"].rsplit("/", 1)[-1]: row["flagged"] for row in rows}
    assert flagged["run_0"] == {}
    assert next(iter(flagged["run_1"].values()))["tokens"] == ["40 倍"]
    assert replay.main(["diff", str(out), str(out)]) == 0
    assert "disappeared=0 appeared=0" in capsys.readouterr().out
