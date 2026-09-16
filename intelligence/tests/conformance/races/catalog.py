"""竞态目录表 v1（母单 §6.5 P4 第 1 条）：每条两序、两种合法历史。

表是声明，夹具是证明：``test_catalog.py`` 钉住「表里每条竞态都有对应的两序测试」，
新增竞态先加行再写夹具，删夹具不删行会红。pi §9.2 的目录形状（竞态 × 两序 × 合法终态）
搬过来，pi 的确定性调度器 / SQLite 事务不搬——我们用步点（``STEP_PHASES``）替代调度器。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Race:
    key: str
    title: str
    module: str  # conformance/races/ 下的测试文件名（不含 .py）
    order_a: str
    order_b: str
    legal_history_a: str
    legal_history_b: str
    shared_invariants: str = "INV-R1 派生逐字节相等（conftest 严格模式）；INV-R2 写序 oracle 三明治"


RACES: tuple[Race, ...] = (
    Race(
        key="cancel_vs_model_settlement",
        title="cancel vs model_turn 结算",
        module="test_race_cancel_vs_model_settlement",
        order_a="取消在模型请求在飞时到达（意图已 durable、结算未落）",
        order_b="取消在模型结算落账之后、下一次请求之前到达",
        legal_history_a="model_turn 结算仍落账（同 turn_id）；不派发工具；finish{cancelled, cancel_cause}；无第二条 model_intent",
        legal_history_b="tool_request/tool_result 全部结算后 finish{cancelled}；恰一条 model_intent 与一条 model_turn",
    ),
    Race(
        key="cancel_vs_tool_settlement",
        title="cancel vs tool_result 结算",
        module="test_race_cancel_vs_tool_settlement",
        order_a="取消在工具执行中到达（runner 里翻信号）",
        order_b="取消在批次结算落账之后到达",
        legal_history_a="每条 tool_request 意图都有结算（tool_result / tool_error），无孤儿意图；随后 finish{cancelled}",
        legal_history_b="批次结算完整、证据入账后 finish{cancelled}；不再开新一轮模型请求",
    ),
    Race(
        key="cancel_vs_finish",
        title="cancel vs finish",
        module="test_race_cancel_vs_finish",
        order_a="取消在模型给出终局之后、准入之前到达",
        order_b="取消在终局已获准入、finish 将落的那一刻到达",
        legal_history_a="终局不被采纳：恰一条 finish，stop_reason=cancelled，status=failed",
        legal_history_b="终局照落：恰一条 finish，stop_reason=model_finish，status=completed；取消不在 finish 里",
    ),
    Race(
        key="steer_vs_model_stop",
        title="steer vs 模型停下",
        module="test_race_steer_vs_model_stop",
        order_a="steer 在模型请求前到达（next_step 在请求前认领）",
        order_b="steer 在模型停下之后到达（next_turn 在停机点认领，再给一轮）",
        legal_history_a="inbox_inserted → inbox_claimed 先于该轮 model_intent；模型这一轮就看到话",
        legal_history_b="模型停下时认领并再跑一轮；两条 model_intent；话在第二轮可见；不丢话",
    ),
    Race(
        key="close_vs_settlement",
        title="close vs 结算",
        module="test_race_close_vs_settlement",
        order_a="RuntimeHandle.close() 在结算落账之前到达（工作单元在飞）",
        order_b="close() 在结算落账之后到达",
        legal_history_a="结算仍落账（Handle 不拥有执行）；收据记 closed_with_inflight；状态 closed",
        legal_history_b="结算落账；收据无 closed_with_inflight；状态 closed",
    ),
    Race(
        key="double_begin_work",
        title="两个 begin_work 同 Handle",
        module="test_race_double_begin_work",
        order_a="第二个 begin_work 在取消 / 关闭之前到达",
        order_b="第二个 begin_work 在 request_cancel（或 close）之后到达",
        legal_history_a="两个工作单元都被接纳：in_flight=2、两条 work_begun；各自 end_work 后 in_flight=0",
        legal_history_b="第二个被拒（RuntimeHandleCancelled / RuntimeHandleClosed，收据 work_denied_*）；第一个照常排空到 drained",
    ),
    Race(
        key="store_failure_vs_memory_ledger",
        title="store.append 失败 vs 内存 ledger",
        module="test_race_store_failure_vs_memory_ledger",
        order_a="store 在写一条意图（model_intent）时失败",
        order_b="store 在写一条结算（model_turn）时失败",
        legal_history_a="内存账本完整、episode 照常完成；store 只留失败前的严格前缀且不再被写；store_failures 收据带序号；durable 副本对 restore 仍自洽",
        legal_history_b="同上，且 store 里最后一条是意图：restore 读到「意图有、结算无」并给 retry_model，而不是把结算当没发生之外的任何猜测",
    ),
    Race(
        key="restore_vs_inflight_drive",
        title="restore vs 仍在飞的驱动",
        module="test_race_restore_vs_inflight_drive",
        order_a="restore 在驱动停在 model_pending（意图已落、结算未落）时被调用",
        order_b="restore 在驱动结束之后被调用",
        legal_history_a="restore 只回 ResumePlan(retry_model)、一字不写；驱动继续后该 turn_id 恰一条结算；终态 done",
        legal_history_b="restore 回 already_terminal、一字不写；store 与 outcome 事件逐条同形",
    ),
)

RACES_BY_KEY: dict[str, Race] = {race.key: race for race in RACES}

__all__ = ["RACES", "RACES_BY_KEY", "Race"]
