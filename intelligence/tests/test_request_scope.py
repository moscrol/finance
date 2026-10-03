"""Domain-independent scope tests; no financial entities or routing rules."""
import pytest

from intelligence.services.request_scope import active_request_text


@pytest.mark.parametrize("question", [
    "不要解释实验失败的原因。",
    "不必分析交通拥堵原因。",
    "无需对项目延期的原因进行分析。",
    "不要分析、推测或解释故障原因。",
    "不要分析，推测或解释故障原因。",
    "不是要你解释事故原因。",
    "我不是要你解释事故原因。",
    "请勿解释设备故障的原因。",
    "不需要分析故障原因。",
    "请不要再尝试分析故障原因。",
    "不要解释‘为什么超时’，给出日志。",
    "不要 解释 故障原因。",
])
def test_prohibited_action_is_masked(question):
    scoped = active_request_text(question)
    assert "原因" not in scoped and "为什么" not in scoped
    assert len(scoped) == len(question)
    assert active_request_text(scoped) == scoped


@pytest.mark.parametrize("question", [
    "请解释为什么设备没有启动。",
    "请解释设备为什么不能启动。",
    "失败原因不明，帮我分析。",
    "不要忽略故障原因。",
    "不要回避失败原因。",
    "不能不解释失败原因。",
    "不得不分析故障原因。",
    "不是不需要解释失败原因。",
    "并非不需要解释失败原因。",
    "不仅分析原因，还要给出证据。",
    "不要只解释原因，还要给出证据。",
    "能不能解释原因？",
    "可不可以分析原因？",
    "需不需要解释原因？",
    "要不要解释原因？",
    "请回答‘为什么延误’。",
    "请解释报告中提到的‘为什么延误’。",
    "“设备甲”为什么故障？",
    "不合理的设计为什么会失败？",
    "",
])
def test_positive_request_and_world_negation_are_unchanged(question):
    assert active_request_text(question) == question


@pytest.mark.parametrize("question,excluded,retained", [
    ("不要解释故障原因，但请解释延期原因。", "故障", "请解释延期原因"),
    ("不必比较日志，请解释延期原因。", "日志", "请解释延期原因"),
    ("请解释故障原因，但不要预测明天的天气。", "天气", "请解释故障原因"),
    ("不要解释噪声来源，而是请分析延期的原因。", "噪声", "请分析延期的原因"),
    ("不要解释故障原因而是比较日志。", "原因", "比较日志"),
    ("故障出现。不要归因于配置，请分析真正原因。", "配置", "请分析真正原因"),
    ("报告写道“为什么延期”，我只需要日志对比。", "为什么", "我只需要日志对比"),
    ('报告提到"延期的原因"，只查询日志。', "原因", "只查询日志"),
    ("‘为什么延期’不是我的问题，只比较日志。", "为什么", "只比较日志"),
    ("报告说‘为什么延期？为什么失败？’，请查询日志。", "为什么", "请查询日志"),
])
def test_clause_quote_and_positive_restart_scope(question, excluded, retained):
    scoped = active_request_text(question)
    assert excluded not in scoped
    assert retained in scoped
    assert len(scoped) == len(question)
    assert active_request_text(scoped) == scoped
