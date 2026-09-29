"""Independent examples of deleting a reference, not its surviving observations.

These are offline prose/verification contracts, not a natural-model quality gate.
"""

from __future__ import annotations

import pytest

from intelligence.services.episode_semantic_verifier import (
    SemanticEpisodeVerifier,
    _drop_rejected_sentences,
    _numbered_sentences,
    _repair_dangling_condition_references,
)
from intelligence.services.research_contract import ResearchDeadline
from intelligence.tests.test_episode_semantic_verifier import _judge, _structural


_DEFINITIONS = "升级条件：站稳20日线。降级条件：跌破前低。"


def _repair(text: str) -> str:
    return _repair_dangling_condition_references(
        text, before=_DEFINITIONS, rejected_sentence_indexes=(1, 2)
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("该股放量上攻，满足升级条件中的2条。", "该股放量上攻。"),
        ("该股放量上攻；满足升级条件中的2条。", "该股放量上攻。"),
        ("该股放量上攻，满足升级条件中的2条", "该股放量上攻"),
        ("**满足升级条件中的2条**，量能配合。", "量能配合。"),
        ("量能配合，**满足升级条件中的2条**。", "量能配合。"),
        ("- **满足升级条件中的2条**，量能配合。", "- 量能配合。"),
        ("满足升级条件中的2条；量能配合。", "量能配合。"),
        ("量能配合，满足升级条件中的2条；值得跟踪。", "量能配合；值得跟踪。"),
        ("目前不满足升级条件中的2条，需继续观察。", "需继续观察。"),
        ("目前仍未满足升级条件中的2条，需继续观察。", "需继续观察。"),
        ("目前并未满足升级条件中的2条，需继续观察。", "需继续观察。"),
        ("当前满足升级条件中的2条，量能配合。", "量能配合。"),
        ("当前仅已满足升级条件中的2条，量能配合。", "量能配合。"),
        ("满足升级条件中的2条，但尚未满足降级条件中的1条，需观察。", "需观察。"),
        ("量能配合，但尚未满足升级条件中的2条，需观察。", "量能配合，需观察。"),
        ("**目前尚未满足升级条件中的2条**，需观察。", "需观察。"),
        ("观察。满足升级条件中的2条。继续观察。", "观察。继续观察。"),
        ("多头结构未破坏。目前尚未满足升级条件中的2条。", "多头结构未破坏。"),
        ("多头结构未破坏。目前尚未满足升级条件中的2条，需继续观察。", "多头结构未破坏。需继续观察。"),
        ("观察结果良好。当前满足升级条件中的2条。", "观察结果良好。"),
        ("量能配合，暂时满足升级条件中的2条。", "量能配合。"),
        ("量能配合；目前满足升级条件中的2条，需观察。", "量能配合；需观察。"),
        ("- 量能配合。**目前尚未满足升级条件中的2条**。", "- 量能配合。"),
        ("量能配合：目前满足升级条件中的2条，需观察。", "量能配合：需观察。"),
        ("量能配合，截至目前满足升级条件中的2条。", "量能配合。"),
        ("量能仅满足当前研究需要，满足升级条件中的2条。", "量能仅满足当前研究需要。"),
        ("**当前观察良好**，满足升级条件中的2条。", "**当前观察良好**。"),
        ("1. 满足升级条件中的2条，量能配合。", "1. 量能配合。"),
        ("1. 满足升级条件中的2条。", ""),
        ("**量能配合**，满足升级条件中的2条，**仍需观察**。", "**量能配合**，**仍需观察**。"),
    ],
)
def test_removed_reference_heals_only_its_clause(text, expected):
    assert _repair(text) == expected


def test_surviving_definitions_use_the_same_sentence_boundaries_as_deletions():
    retained = "升级条件：量能改善。降级条件：风险可控。已满足降级条件中的1条。"
    before = _DEFINITIONS + "\n" + retained
    assert [item["index"] for item in _numbered_sentences(before)] == [1, 2, 3, 4, 5]
    draft = _drop_rejected_sentences(before, (1, 2))
    assert draft == retained
    assert _repair_dangling_condition_references(
        draft, before=before, rejected_sentence_indexes=(1, 2)
    ) == retained


def test_retained_label_count_does_not_hide_later_orphaned_label_count():
    retained = "降级条件：风险可控。\n已满足降级条件中的1条，且满足升级条件中的2条，需跟踪。"
    assert _repair_dangling_condition_references(
        retained, before=_DEFINITIONS + "\n" + retained, rejected_sentence_indexes=(1, 2)
    ) == "降级条件：风险可控。\n已满足降级条件中的1条，需跟踪。"


def test_untouched_lines_and_their_line_endings_are_preserved():
    text = "# 观察\r\n\r\n该股放量上攻，满足升级条件中的2条。\r\n- **保留原文**\r\n"
    assert _repair(text) == "# 观察\r\n\r\n该股放量上攻。\r\n- **保留原文**\r\n"


@pytest.mark.parametrize(
    "text",
    [
        "目前不满足升级条件中的2条，需观察。",
        "**满足升级条件中的2条**，量能配合。",
        "量能配合，满足升级条件中的2条。",
    ],
)
def test_no_deleted_definition_means_no_prose_rewrite(text):
    assert _repair_dangling_condition_references(
        text, before=text, rejected_sentence_indexes=()
    ) == text
    assert _repair_dangling_condition_references(
        text, before="普通条件：观察。" + text, rejected_sentence_indexes=(1,)
    ) == text


_DEFINITION_PREFIXES = (
    "", "- ", "* ", "+ ", "• ", "1. ", "2) ", "3） ", "4、 ",
    "一、", "(1) ", "（2）", "① ", "10. **",
)


@pytest.mark.parametrize("prefix", _DEFINITION_PREFIXES)
def test_deleted_list_definition_removes_only_its_count(prefix):
    closing = "**" if prefix.endswith("**") else ""
    before = f"{prefix}升级条件{closing}：若涨停60家以上，则升级。\n"
    draft = "- 量能改善，满足升级条件中的2条。\r\n- 独立观察。\r\n"
    assert _repair_dangling_condition_references(
        draft, before=before + draft, rejected_sentence_indexes=(1,)
    ) == "- 量能改善。\r\n- 独立观察。\r\n"


@pytest.mark.parametrize("prefix", _DEFINITION_PREFIXES)
def test_surviving_list_definition_preserves_its_count(prefix):
    closing = "**" if prefix.endswith("**") else ""
    retained = (
        f"{prefix}升级条件{closing}：量能改善。\n"
        "已满足升级条件中的1条，需观察。"
    )
    before = "升级条件：若涨停60家以上，则升级。\n" + retained
    assert _repair_dangling_condition_references(
        retained, before=before, rejected_sentence_indexes=(1,)
    ) == retained


@pytest.mark.usefixtures("numeric_delete_mode")
@pytest.mark.parametrize("prefix", _DEFINITION_PREFIXES)
def test_list_definition_deletion_reaches_public_answer(prefix):
    closing = "**" if prefix.endswith("**") else ""
    frame, structural = _structural(
        f"{prefix}升级条件{closing}：若涨停60家以上，则升级。\n"
        "该股放量上攻。目前尚未**满足升级条件中的2条**。"
    )
    result = SemanticEpisodeVerifier(judge_fn=_judge(True)).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert result.judge_status == "repaired"
    assert result.public_answer == "该股放量上攻。"
    assert result.verified.outcome.draft == result.public_answer
    assert any(
        row["decision"] == "deleted" and "60家" in row["sentence"]
        for row in result.sentence_verdicts
    )


@pytest.mark.parametrize("prefix", ["观察到", "2026-09-24 ", "1. 观察到", "普通条件："])
def test_non_definition_prose_does_not_authorize_count_removal(prefix):
    draft = "满足升级条件中的2条，需观察。"
    assert _repair_dangling_condition_references(
        draft, before=f"{prefix}升级条件：量能改善。", rejected_sentence_indexes=(1,)
    ) == draft


@pytest.mark.usefixtures("numeric_delete_mode")
def test_repair_is_delivered_through_semantic_verifier_and_records_real_deletion():
    judge = _judge(True)
    frame, structural = _structural(
        "升级条件：若涨停60家以上，则升级。\n"
        "该股放量上攻。目前尚未**满足升级条件中的2条**。"
    )
    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert result.judge_status == "repaired"
    assert result.public_answer == "该股放量上攻。"
    assert result.verified.outcome.draft == result.public_answer
    assert len(judge.calls) == 1
    assert result.sentence_verdicts
    assert any(
        row["sentence"].startswith("升级条件") and row["decision"] == "deleted"
        for row in result.sentence_verdicts
    )
