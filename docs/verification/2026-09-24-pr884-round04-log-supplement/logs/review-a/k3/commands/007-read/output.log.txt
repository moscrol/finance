"""崩溃窗口里的**未知效果**：既不能当没发生退款，也不能当已发生造结果。

来源：``docs/superpowers/specs/2026-09-07-runtime-base-endstate-design.md`` §6.3（效果三明治）
与 ``research_contract.restore_root_budget`` 里那句悬空多轮的
``A future driver must reconcile unknown effects before using this ledger``。

问题的形状
==========

本仓两条记账路径都是**事后结算**，而 ``budget_snapshot`` 只在相位边界拍：

- 工具批：``_settle_tool_batch`` 在批次跑完后 ``consume_call``（结算已发生的工作不能
  fail closed，见该函数 docstring 的生产事故说明）；
- 模型轮：``_consume_root_seconds`` 在 ``model_turn`` 落账之后。

于是「意图已落、结算未落」的那段窗口里，durable 账本记的是 **0**：

    put_state(tools_pending)   ← 快照在此，不含本批
    tool_request               ← 意图
    ……外部请求真的出门了，供应商的计费表在走字……
    tool_result                ← 结算
    consume_call               ← 账本此刻才扣

崩在中间三行的任意一行，恢复方读到的余额是**派发前**的余额。合成
``tool_error{interrupted}`` 对**证据**是诚实的（确实没有结果可用），但它在事件流里
读起来与「这次调用从未发生」无法区分；而 ``retry_model`` / ``replay_tools`` 更进一步，
主动提议再付一次钱——``replay="safe"`` 是关于**效果幂等**的声明，不是关于**费用**的声明
（注册表默认 ``cost="external"`` 且 ``replay="safe"``，「重跑语义无害、财务照付两次」
正是默认配置）。

本模块编码的原则
================

**未知效果双向保守：对证据按「没发生」处理，对成本按「已发生」处理。**

两句话朝相反方向保守，因为两种风险不对称——凭空造结果会污染答案，凭空退款会烧真钱，
且在崩溃循环下可以无限重复。此前的代码只做对了前一半。

三条边界
========

1. **只记可界定的量。** 账本能表达的单位是「调用格」与「秒」。一条意图至多对应一次调用，
   所以扣**一格**是有界且诚实的；秒**不扣**——崩溃窗口的真实耗时无从得知，编一个数字是
   在伪造测量值。``cost`` / ``io_effect`` / ``replay`` 原样记进凭证，交给能付钱的人判断，
   而不是在这里假装已经结清。
2. **未派发的声明不是未知效果。** ``application_tool_call`` 声明了却从没变成
   ``tool_request``，意味着请求根本没出门，没有外部效果也没有费用。它仍要合成
   ``tool_error`` 配平模型历史，但**不**进本清单——把它算进来是虚报。
3. **清单本身就是去重凭证。** 对账 = 扣账 + 清空，一次原子跃迁。对账前谁都不许花这份
   余额；对账后清单为空，重复恢复不可能重复扣费。因此本模块不碰
   ``InMemoryRootBudgetLedger`` 的快照 schema，也不另造一套 dedup identity。
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

__all__ = [
    "EffectDisposition",
    "EffectKind",
    "UnknownEffect",
    "UnreconciledEffects",
    "charge_unknown_effects",
    "merge_unknown_effects",
    "unknown_effects_from_payload",
    "unknown_effects_payload",
]

EffectKind = Literal["model", "tool"]

#: 恢复对这段未知窗口**做了什么**——不是对「它是否已执行」的判断（那个判断做不出来）。
#: ``settled_interrupted``：合成了 interrupted 结算，窗口就此封存；
#: ``retry_proposed`` / ``replay_proposed``：恢复提议再发一次，即**可能第二次付费**。
EffectDisposition = Literal["settled_interrupted", "retry_proposed", "replay_proposed"]

_EFFECT_KINDS: frozenset[str] = frozenset({"model", "tool"})
_DISPOSITIONS: frozenset[str] = frozenset(
    {"settled_interrupted", "retry_proposed", "replay_proposed"}
)
#: 与 ``ResearchToolSpec.cost`` / ``io_effect`` 同域，外加 ``unknown``：注册表解析不到该
#: 工具时不能猜成 local（fail closed——猜错的方向是少记账）。
_COSTS: frozenset[str] = frozenset({"local", "external", "unknown"})
_IO_EFFECTS: frozenset[str] = frozenset({"local_read", "external_or_mixed", "unknown"})
_REPLAYS: frozenset[str] = frozenset({"safe", "never", "unknown"})


@dataclass(frozen=True)
class UnknownEffect:
    """一条「意图已落、结算未落」的窗口凭证。

    它**不**声称那次调用发生过，也不声称没发生过——这正是它存在的理由：这个问题在
    本进程里答不出来，所以把问题本身持久化，而不是把某个方便的假设持久化。
    """

    effect: EffectKind
    reserved_id: str
    intent_sequence: int
    disposition: EffectDisposition
    name: str = ""
    cost: str = "unknown"
    io_effect: str = "unknown"
    replay: str = "unknown"

    def __post_init__(self) -> None:
        if self.effect not in _EFFECT_KINDS:
            raise ValueError(f"unknown effect kind: {self.effect!r}")
        reserved_id = str(self.reserved_id or "").strip()
        if not reserved_id:
            raise ValueError("unknown effect must carry the reserved id it settles against")
        if (
            isinstance(self.intent_sequence, bool)
            or not isinstance(self.intent_sequence, int)
            or self.intent_sequence < 1
        ):
            raise ValueError("unknown effect intent sequence must be a positive integer")
        if self.disposition not in _DISPOSITIONS:
            raise ValueError(f"unknown effect disposition: {self.disposition!r}")
        if self.cost not in _COSTS:
            raise ValueError(f"unknown effect cost: {self.cost!r}")
        if self.io_effect not in _IO_EFFECTS:
            raise ValueError(f"unknown effect io_effect: {self.io_effect!r}")
        if self.replay not in _REPLAYS:
            raise ValueError(f"unknown effect replay declaration: {self.replay!r}")
        object.__setattr__(self, "reserved_id", reserved_id)
        object.__setattr__(self, "name", str(self.name or ""))

    @property
    def key(self) -> tuple[str, str, int]:
        """去重身份：同一条意图被反复观察到，只算一段窗口。"""

        return (self.effect, self.reserved_id, self.intent_sequence)

    @property
    def may_have_been_billed(self) -> bool:
        """这段窗口是否**可能**已经产生外部费用。

        模型轮一律算（供应商按 token 计费，请求出门就可能计上）。工具看声明，
        且 ``unknown`` 算「可能」——解析不到的工具不能当本地读。
        """

        if self.effect == "model":
            return True
        return self.cost != "local" or self.io_effect != "local_read"

    def to_dict(self) -> dict[str, object]:
        return {
            "effect": self.effect,
            "reserved_id": self.reserved_id,
            "intent_sequence": self.intent_sequence,
            "disposition": self.disposition,
            "name": self.name,
            "cost": self.cost,
            "io_effect": self.io_effect,
            "replay": self.replay,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> UnknownEffect:
        if not isinstance(payload, Mapping):
            raise ValueError("unknown effect record must be an object")
        unexpected = set(payload) - {
            "effect", "reserved_id", "intent_sequence", "disposition",
            "name", "cost", "io_effect", "replay",
        }
        if unexpected:
            # 未知键可能承载着本读者不认识的对账语义，静默丢弃等于伪造一份「已理解」的凭证。
            raise ValueError(f"unknown effect record has unexpected keys: {sorted(unexpected)}")
        sequence = payload.get("intent_sequence")
        if isinstance(sequence, bool) or not isinstance(sequence, int):
            raise ValueError("unknown effect intent sequence must be an integer")
        return cls(
            effect=str(payload.get("effect") or ""),  # type: ignore[arg-type]
            reserved_id=str(payload.get("reserved_id") or ""),
            intent_sequence=sequence,
            disposition=str(payload.get("disposition") or ""),  # type: ignore[arg-type]
            name=str(payload.get("name") or ""),
            cost=str(payload.get("cost") or "unknown"),
            io_effect=str(payload.get("io_effect") or "unknown"),
            replay=str(payload.get("replay") or "unknown"),
        )


#: ``EpisodeState.unreconciled_effects`` 的读侧类型别名。
UnreconciledEffects = tuple[UnknownEffect, ...]


def merge_unknown_effects(
    existing: Iterable[UnknownEffect], incoming: Iterable[UnknownEffect]
) -> UnreconciledEffects:
    """按 ``key`` 求并集，**先到的记录不被后到的覆盖**，按意图序号排序。

    同一段窗口可能被多次恢复反复观察到（``retry_proposed`` 这类计划不合成任何结算，
    下一次恢复照样看得见那条悬空意图）。保留首次记录是有意的：后来的恢复决定改变不了
    「这段窗口没对账」这个事实，而首次记录保存的是它最初被发现时的样子。合并必须是
    幂等的并集，否则重复恢复会让清单无限膨胀。
    """

    merged: dict[tuple[str, str, int], UnknownEffect] = {}
    for effect in existing:
        merged.setdefault(effect.key, effect)
    for effect in incoming:
        merged.setdefault(effect.key, effect)
    return tuple(sorted(merged.values(), key=lambda item: (item.intent_sequence, item.reserved_id)))


def unknown_effects_payload(effects: Iterable[UnknownEffect]) -> list[dict[str, object]]:
    return [effect.to_dict() for effect in effects]


def unknown_effects_from_payload(payload: object) -> UnreconciledEffects:
    """读回一串凭证并校验；损坏的凭证**抛错**，不跳过。

    跳过一条读不懂的未清记录，等于把「有笔账没对」降级成「没有账要对」——那正是本模块
    要堵的那类静默假设。
    """

    if payload is None:
        return ()
    if isinstance(payload, Mapping) or not isinstance(payload, Sequence):
        raise ValueError("unreconciled effects must be a list of records")
    return tuple(UnknownEffect.from_dict(item) for item in payload)


def charge_unknown_effects(
    snapshot: Mapping[str, object] | None, effects: Sequence[UnknownEffect]
) -> tuple[dict[str, object], dict[str, object]]:
    """按「可能已执行」保守扣账，返回（扣过账的快照, 收据）。

    **作用在快照而不是活账本上**，是因为另一种写法有个先有鸡还是先有蛋：未对账时
    ``restore_root_budget`` 根本不放行，拿不到活账本就无处可扣。作用在快照上还有个
    更重要的性质：对账是一次**原子跃迁**——扣过账的快照与清空的未清单写进同一份
    检查点，要么都生效要么都不生效，中途崩溃不会留下「扣了钱但清单还在」或反过来的脑裂态。

    为什么只扣格不扣秒：一条意图至多对应一次调用，这个上界是硬的；而窗口的真实耗时
    无从得知（崩溃到重启之间的挂钟时间与调用耗时毫无关系），编一个数字是伪造测量值。

    格数不够就如实记 ``slots_unavailable``，绝不记成负余额；这是在结算已经可能发生的
    工作，把它变成新的失败源撤不回任何东西（与 ``_settle_tool_batch`` 同源的纪律）。

    没有快照却有未清效果→ **抹**：旧日志没有可扣的余额，此时返回一份「已对账」的空
    快照等于把账销掉。这种情况只能人工判，代码不替它做主。
    """

    if snapshot is None:
        raise ValueError(
            "cannot reconcile unknown effects without a budget snapshot: "
            "there is no balance to charge them against"
        )
    debited = dict(snapshot)
    remaining = debited.get("remaining_calls")
    if isinstance(remaining, bool) or not isinstance(remaining, int) or remaining < 0:
        raise ValueError("budget snapshot remaining_calls must be a non-negative integer")
    requested = len(effects)
    charged = min(requested, remaining)
    debited["remaining_calls"] = remaining - charged
    receipt = {
        "effects": requested,
        "slots_charged": charged,
        "slots_unavailable": requested - charged,
        "possibly_billed": sum(1 for effect in effects if effect.may_have_been_billed),
    }
    return debited, receipt
