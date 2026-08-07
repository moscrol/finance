from dataclasses import dataclass
from typing import Any

from intelligence.services.context_growth import (
    PER_TURN_EVENT_KINDS,
    SUB_AGENT_EVENT_KINDS,
    summarize_context_growth,
)


@dataclass(frozen=True)
class _Event:
    """Stand-in for ``EpisodeEvent``: the reading must accept objects too."""

    sequence: int
    kind: str
    payload: dict[str, Any]


def _model_turn(sequence: int, input_tokens: object) -> dict[str, Any]:
    return {
        "sequence": sequence,
        "kind": "model_turn",
        "payload": {"input_tokens": input_tokens, "output_tokens": 100},
    }


def _branch_completed(sequence: int, input_tokens: object) -> dict[str, Any]:
    # SubResearchResult.input_tokens 是该 branch 各次调用之和
    # （MAX_CALLS_PER_BRANCH = 8），所以这个数天然可能比任何单轮都大。
    return {
        "sequence": sequence,
        "kind": "branch_completed",
        "payload": {
            "branch_id": f"b{sequence}",
            "status": "completed",
            "input_tokens": input_tokens,
            "output_tokens": 200,
        },
    }


def test_per_turn_reading_reports_max_not_sum():
    # 每轮重发全部历史：上下文峰值是 45_000，而累加和是 90_000。
    # 这两个数差 2 倍，且只有前者能回答「离窗口上限还有多远」。
    reading = summarize_context_growth(
        [
            {"sequence": 1, "kind": "task", "payload": {}},
            _model_turn(2, 15_000),
            _model_turn(3, 30_000),
            _model_turn(4, 45_000),
        ]
    )

    assert reading["provenance"] == "per_turn"
    assert reading["turn_count"] == 3
    assert reading["per_turn_input_tokens"] == [15_000, 30_000, 45_000]
    assert reading["max_turn_input_tokens"] == 45_000
    assert reading["cumulative_input_tokens"] == 90_000
    # 末轮/首轮 = 3.0：上下文到 episode 结束时仍在长。
    assert reading["growth_ratio"] == 3.0
    assert reading["observation_only"] is True


def test_per_turn_reading_accepts_episode_event_objects():
    # 适配器边界上拿到的是 EpisodeEvent 对象，持久化后读到的是 dict。
    # 同一个读数必须两种都吃，否则「事后从 run 复算」会静默取不到值。
    reading = summarize_context_growth(
        [
            _Event(1, "task", {}),
            _Event(2, "model_turn", {"input_tokens": 20_000}),
            _Event(3, "model_turn", {"input_tokens": 25_000}),
        ]
    )

    assert reading["provenance"] == "per_turn"
    assert reading["per_turn_input_tokens"] == [20_000, 25_000]
    assert reading["max_turn_input_tokens"] == 25_000


def test_sdk_run_aggregate_refuses_to_guess_the_peak():
    # sdk_gpt / sdk_glm 把循环交给 Agents SDK，适配器边界上只能看到
    # context_wrapper.usage —— 它已经把 SDK 内部多轮加过了（requests > 1）。
    # 峰值介于均值和总和之间，SDK 不说在哪里，所以这里必须给 None 而不是
    # 拿总和或均值冒充峰值。
    reading = summarize_context_growth(
        [
            {"sequence": 1, "kind": "task", "payload": {}},
            {
                "sequence": 2,
                "kind": "runtime_result",
                "payload": {
                    "runtime": "sdk_gpt",
                    "input_tokens": 120_000,
                    "provider_attempts": 4,
                },
            },
        ]
    )

    assert reading["provenance"] == "run_aggregated"
    assert reading["turn_count"] == 4
    assert reading["cumulative_input_tokens"] == 120_000
    assert reading["mean_turn_input_tokens"] == 30_000
    # 关键断言：不猜峰值，也不给逐轮序列。
    assert reading["max_turn_input_tokens"] is None
    assert reading["per_turn_input_tokens"] is None
    assert reading["growth_ratio"] is None


def test_per_turn_events_win_over_run_aggregate():
    # continuous_glm 两种事件都会有（逐轮 model_turn + 收尾 runtime_result）。
    # 精确的那份必须赢，否则精度会被收尾事件降级掉。
    reading = summarize_context_growth(
        [
            _model_turn(1, 10_000),
            _model_turn(2, 20_000),
            {
                "sequence": 3,
                "kind": "runtime_result",
                "payload": {"input_tokens": 30_000, "provider_attempts": 2},
            },
        ]
    )

    assert reading["provenance"] == "per_turn"
    assert reading["max_turn_input_tokens"] == 20_000


def test_missing_usage_is_unavailable_not_zero():
    # 实测 08-02 那批 sdk_gpt run 的 runtime_result.input_tokens 就是 None。
    # 报 0 会被读成「上下文很小」，而真相是「这个 backend 没吐 usage」。
    reading = summarize_context_growth(
        [
            {"sequence": 1, "kind": "task", "payload": {}},
            {
                "sequence": 2,
                "kind": "runtime_result",
                "payload": {"runtime": "sdk_gpt", "input_tokens": None},
            },
            {"sequence": 3, "kind": "finish", "payload": {"status": "completed"}},
        ]
    )

    assert reading["provenance"] == "unavailable"
    assert reading["turn_count"] == 0
    assert reading["max_turn_input_tokens"] is None
    assert reading["cumulative_input_tokens"] is None


def test_bool_is_not_a_token_count():
    # isinstance(True, int) 是 True。不显式排掉 bool，一个 payload 里的
    # True 会变成 1 token，把 provenance 从 unavailable 抬成 per_turn。
    reading = summarize_context_growth([_model_turn(1, True)])

    assert reading["provenance"] == "unavailable"


def test_growth_ratio_needs_two_turns_and_nonzero_base():
    single = summarize_context_growth([_model_turn(1, 40_000)])
    assert single["provenance"] == "per_turn"
    assert single["max_turn_input_tokens"] == 40_000
    assert single["growth_ratio"] is None

    zero_base = summarize_context_growth([_model_turn(1, 0), _model_turn(2, 5_000)])
    assert zero_base["growth_ratio"] is None


def test_empty_event_stream_is_unavailable():
    reading = summarize_context_growth([])

    assert reading["provenance"] == "unavailable"
    assert reading["observation_only"] is True


def test_branch_only_stream_is_not_per_turn():
    # 变异测试：把 "branch_completed" 加回 PER_TURN_EVENT_KINDS，本条必红
    # （provenance 变成 per_turn，turn_count 变成 2）。
    # branch 跑在隔离上下文里，它的 token 从不进父 agent 的窗口，所以父 agent
    # 的上下文尺寸在这个流里是「没测到」，不是「120_000」。
    reading = summarize_context_growth(
        [
            {"sequence": 1, "kind": "task", "payload": {}},
            _branch_completed(2, 70_000),
            _branch_completed(3, 50_000),
        ]
    )

    assert reading["provenance"] == "unavailable"
    assert reading["turn_count"] == 0
    assert reading["per_turn_input_tokens"] is None
    assert reading["max_turn_input_tokens"] is None
    assert reading["cumulative_input_tokens"] is None
    # 子 agent 的花费没被丢掉，只是换了字段和 provenance：branch 数不是轮数。
    assert reading["sub_agent_provenance"] == "branch_aggregated"
    assert reading["sub_agent_branch_count"] == 2
    assert reading["sub_agent_input_tokens"] == 120_000


def test_branch_aggregate_never_becomes_the_window_peak():
    # 变异测试：把 "branch_completed" 加回 PER_TURN_EVENT_KINDS，本条必红
    # （max 变成 90_000 = branch 聚合值，turn_count 与 growth_ratio 同时被污染）。
    # 父 agent 真实峰值是 25_000；90_000 是子 agent 多次调用的和。
    reading = summarize_context_growth(
        [
            _model_turn(1, 20_000),
            _branch_completed(2, 90_000),
            _model_turn(3, 25_000),
        ]
    )

    assert reading["provenance"] == "per_turn"
    assert reading["max_turn_input_tokens"] != 90_000
    assert reading["max_turn_input_tokens"] == 25_000
    assert reading["turn_count"] == 2
    assert reading["per_turn_input_tokens"] == [20_000, 25_000]
    # 20_000 → 25_000，而不是被 branch 抬成 4.5。
    assert reading["growth_ratio"] == 1.25
    assert reading["sub_agent_input_tokens"] == 90_000


def test_sub_agent_fields_present_even_without_branches():
    # 每个读数都带 sub_agent_* 三个字段；缺分支时是 unavailable 而不是 0，
    # 否则「没跑子 agent」和「子 agent 没吐 usage」会读成同一件事。
    reading = summarize_context_growth([_model_turn(1, 30_000)])

    assert reading["sub_agent_provenance"] == "unavailable"
    assert reading["sub_agent_branch_count"] == 0
    assert reading["sub_agent_input_tokens"] is None


def test_kind_sets_are_disjoint():
    # 账单口径（agent_episode._token_usage_from_events）与上下文尺寸口径是两个
    # 读数，各用一个集合。这里锁住「不重叠」，防止有人再把两者合并回去。
    assert PER_TURN_EVENT_KINDS == frozenset({"model_turn"})
    assert SUB_AGENT_EVENT_KINDS == frozenset({"branch_completed"})
    assert not (PER_TURN_EVENT_KINDS & SUB_AGENT_EVENT_KINDS)
