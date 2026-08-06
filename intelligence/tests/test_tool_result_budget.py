from intelligence.services.tool_result_budget import (
    FULL_RECORD_ARTIFACT,
    MAX_EVIDENCE_DETAIL_CHARS,
    MAX_OBSERVATION_CHARS,
    budget_tool_observation,
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


def test_budget_is_deterministic_for_prompt_cache_reuse():
    # provider 的 prompt cache 以字节前缀为 key。同一份观察每次压出不同预览，
    # 恢复会话时缓存全失效，省下的 token 还不够抵重算成本。
    payload = _observation(observation="市" * 5000)

    assert budget_tool_observation(payload) == budget_tool_observation(payload)
