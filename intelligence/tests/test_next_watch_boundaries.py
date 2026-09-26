"""8792 F1: section boundaries and post-verification watch-list completeness.

These are syntax/side-effect regressions, not a certification of financial
semantics. The live answer is preserved separately; snippets keep its shape.
"""
from __future__ import annotations

import pytest

from intelligence.services.track_contract import (
    append_contract_stub,
    contract_receipt,
    ingest_next_watch,
    missing_contract_elements,
    parse_next_watch_items,
)

BASE = "无上期基线，本期建立基线。判定：信息不足。复核期限：2026-10-21。\n"
INCOMPLETE = (
    "**下期关注清单**：指标=三季报经营活动现金流量净额（累计）÷同期归母净利（累计）；"
    "时间节点=2026-10-21复查日（三季报预计10月底前披露）；\n"
)
CONDITION = "若经营现金流仍未改善，则重新评估现金流质量判断。"
VALID = "指标=经营现金流；时间节点=2026-10-21；" + CONDITION
GAP = "本地行情库在2026-09-11至09-17窗口无结构化结果，仅作补充核实用途。"


@pytest.mark.parametrize("boundary", [
    "缺口：", "**缺口**：", "### 缺口\n", "# 后续说明\n",
    "## 另一个章节\n", "**证据边界**：", "证据边界：", "风险提示：",
    "---\n", "**补充材料**\n", "**其他章节**：", "来源：", "    ## 附录\n",
])
def test_next_watch_stops_before_following_sections(tmp_path, boundary):
    # 后段也长得像有效条件，不能靠「后段无条件所以没收」取得假绿。
    other_section = GAP + "若核对后仍有差异，则回查2026-09-11的来源。"
    answer = BASE + "**下期关注清单**：" + VALID + "\n" + boundary + other_section
    items = parse_next_watch_items(answer, as_of="2026-09-18")
    assert len(items) == 1
    assert items[0].due == "2026-10-21"
    assert "2026-09-11" not in items[0].claim and GAP not in items[0].claim
    assert not items[0].claim.startswith("**")
    path = tmp_path / "checkpoints.jsonl"
    assert ingest_next_watch(
        path, answer, query="跟踪一下，但不要登记为长期跟踪", as_of="2026-09-18",
    ) == []
    assert not path.exists()
    rows = ingest_next_watch(
        path, answer, query="跟踪一下，登记为长期跟踪", as_of="2026-09-18",
        session_id="offline-f1-positive",
    )
    assert len(rows) == 1 and rows[0]["due"] == "2026-10-21"
    assert rows[0]["session_id"] == "offline-f1-positive"
    incomplete = BASE + INCOMPLETE + boundary + other_section
    assert missing_contract_elements(incomplete) == ("next_watch",)
    assert parse_next_watch_items(incomplete, as_of="2026-09-18") == ()


def test_f1_date_only_remainder_is_not_complete_or_registerable(tmp_path):
    answer = BASE + INCOMPLETE + "缺口：" + GAP
    assert missing_contract_elements(answer) == ("next_watch",)
    assert contract_receipt(answer, query="继续跟踪")['missing_outputs'] == ["track_next_watch"]
    assert parse_next_watch_items(answer, as_of="2026-09-18") == ()
    path = tmp_path / "checkpoints.jsonl"
    assert ingest_next_watch(path, answer, query="继续跟踪", as_of="2026-09-18") == []
    assert not path.exists()


@pytest.mark.parametrize("remainder", [
    "", "触发条件=", "触发条件=待补充。", "触发条件=证据不足，暂无法确定。",
    "持续关注市场情绪。", "到期复查。",
])
def test_placeholder_or_time_alone_does_not_satisfy_trigger(remainder):
    answer = BASE + INCOMPLETE + remainder
    assert "next_watch" in missing_contract_elements(answer)
    assert parse_next_watch_items(answer, as_of="2026-09-18") == ()


def test_missing_notice_does_not_fulfil_itself():
    answer = BASE + INCOMPLETE
    patched = append_contract_stub(answer, missing_contract_elements(answer))
    assert patched.startswith(answer.rstrip())
    assert missing_contract_elements(patched) == ("next_watch",)
    assert append_contract_stub(patched, missing_contract_elements(patched)) == patched
    assert parse_next_watch_items(patched, as_of="2026-09-18") == ()


@pytest.mark.parametrize("heading", [
    "## 下期关注清单", "下期关注清单：", "**下期关注清单**：",
    "### 下期关注", "下期关注：",
])
def test_wrapped_fields_are_one_complete_item(heading):
    answer = BASE + heading + "\n- 指标=经营现金流；\n  时间节点=2026-10-21；\n  触发条件=" + CONDITION
    assert missing_contract_elements(answer) == ()
    items = parse_next_watch_items(answer, as_of="2026-09-18")
    assert len(items) == 1
    assert items[0].due == "2026-10-21"
    assert "指标=经营现金流" in items[0].claim and CONDITION in items[0].claim


def test_one_complete_item_cannot_hide_another_items_missing_trigger():
    answer = BASE + "## 下期关注清单\n1. " + VALID + "\n2. 指标=存货；时间节点=2026-10-21。"
    assert missing_contract_elements(answer) == ("next_watch",)
    items = parse_next_watch_items(answer, as_of="2026-09-18")
    assert len(items) == 1 and CONDITION.rstrip("。") in items[0].claim


@pytest.mark.parametrize("heading", ["**下期关注清单（登记为长期跟踪）**：", "__下期关注清单__："])
def test_bold_fields_and_heading_suffix_are_not_bullet_markers(heading):
    answer = BASE + heading + (
        "\n**指标**：经营现金流；\n**时间节点**：2026-10-21；\n"
        "**触发条件**：" + CONDITION
    )
    assert missing_contract_elements(answer) == ()
    items = parse_next_watch_items(answer, as_of="2026-09-18")
    assert len(items) == 1 and items[0].due == "2026-10-21"
    assert "登记为长期跟踪" not in items[0].claim
    assert "指标" in items[0].claim and CONDITION in items[0].claim


def test_gap_word_inside_condition_is_not_a_section_boundary():
    answer = BASE + "## 下期关注清单\n- 若中报出现现金流缺口，则削弱扩产判断。"
    assert missing_contract_elements(answer) == ()
    assert len(parse_next_watch_items(answer, as_of="2026-09-18")) == 1
