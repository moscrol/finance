import json

from intelligence.services.episode_protocol import strip_hashes_for_model
from intelligence.services.tool_result_budget import (
    FULL_RECORD_ARTIFACT,
    MAX_EVIDENCE_DETAIL_CHARS,
    MAX_OBSERVATION_CHARS,
    budget_tool_observation,
    lean_observation_enabled,
    lean_tool_observation,
)


def _observation(**overrides) -> dict:
    payload = {
        "ok": True,
        "tool": "market_data",
        "query": "上证指数近5日",
        "observation": "指数收于3421点，成交额放大。",
        "evidence": [
            {
                "tool": "market_data",
                "title": "上证指数日线",
                "detail": "收盘3421.2，成交额8900亿。",
                "source": "盘面快照",
                "source_date": "2026-08-06",
                "evidence_tier": "A",
                "supports": ["current_baseline"],
                "contradicts": ["duration_assessment"],
                "independent_key": "sse:2026-08-06",
                "freshness": "same_day",
                "content_hash": "abc123def456",
            }
        ],
        "evidence_hashes": ["abc123def456"],
        "gaps": ["缺少成因证据"],
    }
    payload.update(overrides)
    return payload


def test_short_observation_is_byte_identical_to_pre_budget_payload():
    # 没超预算时不得附加任何元数据，否则每个既有 run 的上下文都变了字节，
    # 白白打掉 provider 的 prompt cache。
    payload = _observation()

    assert budget_tool_observation(payload) == payload
    assert "context_budget" not in budget_tool_observation(payload)


def test_long_narrative_is_clipped_within_the_bound():
    payload = _observation(observation="市" * 5000)

    budgeted = budget_tool_observation(payload)

    assert len(budgeted["observation"]) == MAX_OBSERVATION_CHARS
    assert budgeted["observation"].endswith("…")
    assert budgeted["context_budget"]["truncated"] is True
    assert budgeted["context_budget"]["omitted_chars"] > 0
    assert budgeted["context_budget"]["full_record_in"] == FULL_RECORD_ARTIFACT


def test_identifiers_and_boundary_fields_survive_truncation():
    # 压缩红线：来源 / 时点 / 状态 / 缺口 / 完整性 必须原样留存。
    # 截短 content_hash 不会让答案变短，只会让 binding 门禁无法满足。
    payload = _observation(
        observation="市" * 5000,
        evidence=[
            {
                **_observation()["evidence"][0],
                "detail": "详" * 3000,
                "title": "标" * 3000,
            }
        ],
    )

    budgeted = budget_tool_observation(payload)
    item = budgeted["evidence"][0]

    assert item["content_hash"] == "abc123def456"
    assert budgeted["evidence_hashes"] == ["abc123def456"]
    assert item["source"] == "盘面快照"
    assert item["source_date"] == "2026-08-06"
    assert item["evidence_tier"] == "A"
    assert item["freshness"] == "same_day"
    assert item["independent_key"] == "sse:2026-08-06"
    # 反证被丢掉会把有争议的发现静默升级成干净结论。
    assert item["contradicts"] == ["duration_assessment"]
    assert item["supports"] == ["current_baseline"]
    assert budgeted["gaps"] == ["缺少成因证据"]
    # 叙述该截的照截。
    assert len(item["detail"]) == MAX_EVIDENCE_DETAIL_CHARS


def test_budgeting_never_mutates_the_audit_copy():
    # 调用点把同一份 payload 交给 ledger 和 messages 两个 sink，
    # 就地改写会让审计档跟着变短——那不是压缩，是毁证据。
    payload = _observation(observation="市" * 5000)
    original_observation = payload["observation"]
    original_detail = payload["evidence"][0]["detail"]

    budget_tool_observation(payload)

    assert payload["observation"] == original_observation
    assert payload["evidence"][0]["detail"] == original_detail
    assert "context_budget" not in payload


def test_absent_fields_are_not_invented():
    # tool_error 那条 payload 没有 observation/evidence 字段，
    # 预算函数不能顺手补出空字符串来改变协议形状。
    payload = {"ok": False, "tool": "market_data", "error": "tool_timeout"}

    assert budget_tool_observation(payload) == payload


def test_non_mapping_evidence_items_pass_through_untouched():
    payload = _observation(evidence=["unexpected", 42])

    assert budget_tool_observation(payload)["evidence"] == ["unexpected", 42]


def test_non_string_narrative_fields_pass_through_instead_of_emptying():
    # 变异测试：把 _clip 改回 `value if isinstance(value, str) else ""`，本条必红。
    # 强转成空串是**静默删数据**：omitted_chars 不增 → 不挂 context_budget →
    # 模型看不出这个字段被动过，正是本模块存在的意义所要防的那件事。
    # 与「非 Mapping 的 evidence 项原样透传」保持同一条口径。
    payload = _observation(
        observation={"structured": "not a string"},
        evidence=[
            {
                **_observation()["evidence"][0],
                "title": 12345,
                "detail": ["a", "b"],
            }
        ],
    )

    budgeted = budget_tool_observation(payload)
    item = budgeted["evidence"][0]

    assert budgeted["observation"] == {"structured": "not a string"}
    assert item["title"] == 12345
    assert item["detail"] == ["a", "b"]
    # 什么都没截，所以不得附完整性元数据。
    assert "context_budget" not in budgeted


def test_context_budget_names_only_fields_the_model_still_has():
    """预算说明里点名的字段，必须在**整条流水线之后**仍在模型那份里。

    真实顺序是 ``strip_hashes_for_model(budget_tool_observation(pruned))``
    （``agent_episode``）：strip 紧跟在预算之后，把 ``evidence_hashes`` /
    ``content_hash`` 换成 E 号。修前说明写「需要完整原文时以 evidence_hashes
    为准」，指的正是下一步就被删掉的字段——模型手上根本没有它，注册表里
    也没有任何工具接受哈希或证据编号当参数。指针指向不存在的东西，比不给
    指针更糟：模型会以为还有一条取回路径。

    钉的是两层之间的一致性，不是某个字面量。变异测试：把 ``preserved`` 里的
    "evidence_id" 换回 "evidence_hashes"，本条必红。
    """

    payload = _observation(
        observation="市" * 5000,
        # 夹具必须带 evidence_id：``strip_hashes_for_model`` 只在存在 E 号时
        # 才摘掉 evidence_hashes。少了它就走不到真实那条分支，断言全落空。
        evidence=[{**_observation()["evidence"][0], "evidence_id": "E1"}],
    )

    model_view = strip_hashes_for_model(budget_tool_observation(payload))
    budget = model_view["context_budget"]
    item = model_view["evidence"][0]

    # 先证明这次两层都真的动手了，否则下面的断言只是空转。
    assert budget["truncated"] is True
    assert "evidence_hashes" not in model_view
    assert "content_hash" not in item

    for field in budget["preserved"]:
        assert field in model_view or field in item, field
    for stripped in ("evidence_hashes", "content_hash"):
        assert stripped not in budget["instruction"]


def test_lean_drops_only_empties_and_independent_key_and_keeps_every_red_line_field():
    """spec 2026-09-07 §3.1：脚手架不进模型上下文，红线字段一个不动。

    变异：把 ``supports`` 非空也删掉 → 红（矛盾被静默升级）；把 ``independent_key`` 留回来 → 红。
    """

    payload = _observation(
        evidence=[
            {
                # 真实 sub_research 行的形状：一堆空值 + 校验器专用键
                "tool": "evidence_search", "title": "固态电池", "detail": "# 固态电池 section…",
                "source": "wiki/concepts/固态电池.md", "source_date": "None", "evidence_tier": "",
                "supports": [], "contradicts": [], "independent_key": "wiki/concepts/固态电池.md",
                "freshness": "fresh", "content_hash": "f5b2101b", "evidence_id": "E1",
            },
            _observation()["evidence"][0] | {"evidence_id": "E2"},  # 红线字段全非空
        ],
        evidence_hashes=[], payload_field_names=[], payload_sha256="", dataset="", caliber="",
    )

    leaned = lean_tool_observation(payload)

    scaffold, full = leaned["evidence"]
    assert scaffold == {
        "tool": "evidence_search", "title": "固态电池", "detail": "# 固态电池 section…",
        "source": "wiki/concepts/固态电池.md", "freshness": "fresh", "content_hash": "f5b2101b", "evidence_id": "E1",
    }
    # 非空的 supports / contradicts / freshness / evidence_tier / source_date 全在；只少 independent_key。
    assert full == {k: v for k, v in _observation()["evidence"][0].items() if k != "independent_key"} | {"evidence_id": "E2"}
    for key in ("evidence_hashes", "payload_field_names", "payload_sha256", "dataset", "caliber"):
        assert key not in leaned
    # 非空的顶层键原样保留；gaps 永不动。
    assert leaned["gaps"] == ["缺少成因证据"] and leaned["observation"] == payload["observation"]
    kept = lean_tool_observation({**payload, "dataset": "stock_daily", "caliber": "fact_stock_daily"})
    assert (kept["dataset"], kept["caliber"]) == ("stock_daily", "fact_stock_daily")
    # 纯函数：输入不动、可重入。
    assert payload["evidence"][0]["supports"] == [] and lean_tool_observation(payload) == leaned
    # 顺序与真实流水线一致：strip 仍能在 lean 之后把 hash 换成 E 号。
    view = strip_hashes_for_model(lean_tool_observation(budget_tool_observation(payload)))
    assert "content_hash" not in view["evidence"][0] and view["evidence_ids"] == ["E1", "E2"]
    assert len(json.dumps(view, ensure_ascii=False)) < len(
        json.dumps(strip_hashes_for_model(budget_tool_observation(payload)), ensure_ascii=False)
    )


def test_lean_switch_is_off_unless_explicitly_on(monkeypatch):
    for raw, expected in (("", False), ("off", False), ("0", False), ("on", True), ("1", True), ("TRUE", True)):
        monkeypatch.setenv("ASK_EPISODE_LEAN_OBSERVATION", raw)
        assert lean_observation_enabled() is expected, raw
    monkeypatch.delenv("ASK_EPISODE_LEAN_OBSERVATION", raising=False)
    assert lean_observation_enabled() is False


def test_budget_is_deterministic_for_prompt_cache_reuse():
    # provider 的 prompt cache 以字节前缀为 key。同一份观察每次压出不同预览，
    # 恢复会话时缓存全失效，省下的 token 还不够抵重算成本。
    payload = _observation(observation="市" * 5000)

    assert budget_tool_observation(payload) == budget_tool_observation(payload)
