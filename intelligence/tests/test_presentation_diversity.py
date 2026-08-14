from intelligence.eval.presentation_diversity import (
    audit_presentation_diversity,
    template_similarity,
)


def test_same_five_heading_template_is_flagged_despite_different_numbers() -> None:
    left = """# A\n## 结论\n- 上涨 10% [S1]\n## 最强证据\n- 成交 20 亿\n## 风险\n- 需求下降\n## 条件边界\n- 若失守则降级\n## 下一步验证\n- 看明日"""
    right = """# B\n## 结论\n- 下跌 3% [S2]\n## 最强证据\n- 成交 40 亿\n## 风险\n- 供给增加\n## 条件边界\n- 若反弹则修正\n## 下一步验证\n- 看下周"""
    assert template_similarity(left, right) >= 0.82


def test_natural_structures_are_not_misreported_as_identical() -> None:
    causal = """这周更像风险偏好收缩。\n\n## 为什么\n指数放量下跌，但外部事件仍缺时间对齐证据。"""
    method = """## 检索为什么跑偏\nRAG 只解决找材料，planner 才决定缺什么。\n\n## 最小改法\n先保留事实门，再删格式门。"""
    report = audit_presentation_diversity((("a", causal), ("b", method)))
    assert report.max_template_similarity < report.threshold
    assert report.advisory is True
