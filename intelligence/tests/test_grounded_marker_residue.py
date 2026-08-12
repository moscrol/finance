"""公开正文不得漏出 grounded 标注的任何残片。

背景（08-01 验收 C4 实测）：公开正文尾部漏出 `claim_type=candidate -->`。
机制：`present_grounded_composer_answer` 原先**逐行**剥标注，而完整标注正则
的字符类可以跨行——模型把一条标注写成两行后，前半（`<!-- claim_ids=…;`）
有头没尾、后半（`…claim_type=candidate -->`）有尾没头，逐行匹配两半都认
不出，残片原样进入用户可见文本。

修法：整文剥完整标注 + 残片兜底正则（只认「带标注键名的注释碎块」）。
"""
from __future__ import annotations

from intelligence.services.answer_model import present_grounded_composer_answer


def test_well_formed_marker_is_stripped_and_prose_kept() -> None:
    answer = (
        "立新能源 07-21 上涨 3.2%。 "
        "<!-- claim_ids=fact:1; evidence_atom_ids=a1; claim_type=fact -->"
    )
    result = present_grounded_composer_answer(answer)
    assert result == "立新能源 07-21 上涨 3.2%。"


def test_marker_split_across_two_lines_leaves_no_residue() -> None:
    """C4 的机制复刻：标注被模型断成两行。"""
    answer = (
        "公司层面暂无硬证据。 <!-- claim_ids=counter:1;\n"
        "evidence_atom_ids=; claim_type=candidate -->\n"
        "以上为候选判断。"
    )
    result = present_grounded_composer_answer(answer)
    assert "claim_type" not in result
    assert "claim_ids" not in result
    assert "-->" not in result
    assert "<!--" not in result
    assert "公司层面暂无硬证据。" in result
    assert "以上为候选判断。" in result


def test_tail_only_fragment_is_stripped() -> None:
    """C4 泄漏的原始形状：只剩尾巴。"""
    answer = "该股当日放量。 claim_type=candidate -->"
    result = present_grounded_composer_answer(answer)
    assert result == "该股当日放量。"


def test_head_only_fragment_is_stripped() -> None:
    answer = "该股当日放量。 <!-- claim_ids=fact:9; evidence_atom_ids=a2;"
    result = present_grounded_composer_answer(answer)
    assert result == "该股当日放量。"


def test_prose_mentioning_the_word_without_equals_survives() -> None:
    """只有带 `=` 的标注键名才算残片；正文里讨论这个词本身不受影响。"""
    answer = "系统内部用 claim_type 区分事实与推断。"
    assert present_grounded_composer_answer(answer) == answer
