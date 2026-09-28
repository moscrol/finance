"""候选经验的生命周期状态（终局 spec §5.1、§7.10；V1「候选经验队列」那一件）。

    feedback → candidate → discovery_passed → validation_passed → holdout_passed
             → personal_method → shared_candidate → shared_method

## 为什么是**推导**出来的，不是再存一份 status

规则文件里已经有 ``sharing`` / ``owner``，收据目录里已经有每次跑的窗口与四态。
再给规则加一个可变的 ``lifecycle_status`` 字段，等于给同一个事实开第二个真源——
它会漂，而且漂的时候没人知道（今天这一整天修的多半是这个形状）。

所以本模块只做一件事：**读规则 + 读它全部收据 → 算出它现在在哪一档**。
spec §5.1 要求「状态转移必须附带收据」——推导式实现让这条不可能违反：
状态本身就是收据算出来的，没有收据就没有状态。

## 三条不肯让步的门

1. **窗口必须真的往后走。** validation 的窗口要**整段晚于** discovery，holdout 又晚于
   validation。重叠、倒序、同窗重跑都不算过门（spec §7.1「验证数据的时间必须晚于发现
   数据；Holdout 不得被探索过程读取」）。只看「跑了三次」不看窗口，等于把同一段数据
   数了三遍。
2. **共享层不能由 agent 批准。** 无论统计多漂亮，本模块**推不出** ``shared_candidate`` /
   ``shared_method``——它们必须有一条人工签字记录（spec §7.10）。没有签字就停在
   ``personal_method``，并在 ``blocked_by`` 里写明「等人工审阅」。
3. **过门之后仍会掉下来。** 达到方法档后新窗口出现 ``refuted`` → ``invalidated``
   （spec §6.3 失效监测）。方法库不是一进永进。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from intelligence.services.methodology_backtest.receipts import RECEIPT_SCHEMA

# 晋升链，顺序即等级。
LADDER: tuple[str, ...] = (
    "candidate",
    "discovery_passed",
    "validation_passed",
    "holdout_passed",
    "personal_method",
    "shared_candidate",
    "shared_method",
)
# 终态：spec §5.1「任何阶段都可以进入」。
TERMINAL: tuple[str, ...] = ("insufficient", "contradicted", "invalidated", "superseded")

# 只有人能签的两档。**agent 推导永远到不了这里**（spec §7.10）。
HUMAN_ONLY: frozenset[str] = frozenset({"shared_candidate", "shared_method"})

SUPPORTED = "supported"
REFUTED = "refuted"
INSUFFICIENT = "insufficient_n"


@dataclass(frozen=True)
class Window:
    start: str
    end: str

    def strictly_after(self, other: "Window") -> bool:
        """整段晚于 ``other``：本段起点要**严格晚于**对方终点，不许重叠。"""
        return bool(self.start and other.end) and self.start > other.end


@dataclass(frozen=True)
class Step:
    """一次检验：哪个窗口、什么结论、哪份收据。"""

    window: Window
    verdict: str
    receipt_path: str
    generated_at: str


@dataclass(frozen=True)
class MethodState:
    rule_id: str
    state: str
    sharing: str
    owner: str
    evidence: tuple[str, ...]
    blocked_by: str | None
    needs_human: bool = False

    @property
    def in_method_library(self) -> bool:
        """spec §5.2「未过门不进入方法库」——只有到方法档才算数。"""
        return self.state in ("personal_method", "shared_candidate", "shared_method")

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "state": self.state,
            "sharing": self.sharing,
            "owner": self.owner,
            "in_method_library": self.in_method_library,
            "needs_human": self.needs_human,
            "blocked_by": self.blocked_by,
            "evidence": list(self.evidence),
        }


def load_steps(root: str | Path, rule_id: str) -> list[Step]:
    """读某条规则的**全部**收据，按 ``generated_at`` 升序。

    不用 ``latest_receipt``：晋升看的是历史轨迹（发现 → 验证 → holdout 三段窗口），
    只看最近一次就永远只有一段窗口，晋升条件恒不成立。
    """
    base = Path(root).expanduser()
    if not base.is_dir():
        return []
    steps: list[Step] = []
    for folder in sorted(base.glob(f"{rule_id}@v*")):
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.json")):
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if not isinstance(doc, dict) or doc.get("schema_version") != RECEIPT_SCHEMA:
                continue
            if str((doc.get("rule") or {}).get("rule_id")) != rule_id:
                continue
            win = doc.get("window") or {}
            steps.append(
                Step(
                    window=Window(str(win.get("start") or ""), str(win.get("end") or "")),
                    verdict=str((doc.get("stats") or {}).get("verdict") or ""),
                    receipt_path=str(path),
                    generated_at=str(doc.get("generated_at") or ""),
                )
            )
    return sorted(steps, key=lambda s: (s.generated_at, s.receipt_path))


def _advancing_chain(steps: list[Step]) -> list[Step]:
    """挑出「窗口一段比一段晚」且结论为 supported 的链。

    贪心取最早可用的那条：每往前一步都要求窗口严格晚于上一步。这样「同一段数据跑三遍」
    只会算成一步，而不是三步。
    """
    chain: list[Step] = []
    for step in steps:
        if step.verdict != SUPPORTED:
            continue
        if not chain or step.window.strictly_after(chain[-1].window):
            chain.append(step)
    return chain


def derive_state(
    rule: dict[str, Any],
    steps: list[Step],
    *,
    human_approval: dict[str, Any] | None = None,
) -> MethodState:
    """算出这条候选现在在哪一档。``human_approval`` 只能由人写入，agent 不得伪造。"""
    rule_id = str(rule.get("rule_id") or rule.get("id") or "")
    sharing = str(rule.get("sharing") or "private")
    owner = str(rule.get("owner") or "")

    if not steps:
        return MethodState(
            rule_id, "candidate", sharing, owner, (),
            blocked_by="还没跑过任何检验：先 `methodology_backtest.py run` 出一份发现窗收据",
        )

    latest = steps[-1]
    chain = _advancing_chain(steps)

    # 终态优先判：最近一次说被证伪 / 样本不足，就不是「在晋升路上」。
    if latest.verdict == REFUTED:
        # 已经进过方法库又被推翻 = invalidated；从没进过 = contradicted。
        was_method = len(chain) >= 3
        return MethodState(
            rule_id,
            "invalidated" if was_method else "contradicted",
            sharing, owner,
            tuple(s.receipt_path for s in steps[-1:]),
            blocked_by="最近一次检验被证伪；要复活需要新窗口重新走三段门",
        )
    if latest.verdict == INSUFFICIENT and not chain:
        return MethodState(
            rule_id, "insufficient", sharing, owner, (latest.receipt_path,),
            blocked_by="样本不足（N < min_n）；等更多事件累积，**不出比率**",
        )

    passed = len(chain)
    if passed == 0:
        return MethodState(
            rule_id, "candidate", sharing, owner, (),
            blocked_by="跑过但没有一次 supported：仍是候选，不进方法库",
        )
    if passed == 1:
        return MethodState(
            rule_id, "discovery_passed", sharing, owner, (chain[0].receipt_path,),
            blocked_by="缺时间外验证：换一段**整段晚于**发现窗的数据再跑一次",
        )
    if passed == 2:
        return MethodState(
            rule_id, "validation_passed", sharing, owner,
            tuple(s.receipt_path for s in chain),
            blocked_by="缺 Holdout：再换一段更晚的数据，且该段不得被前两步读过",
        )

    evidence = tuple(s.receipt_path for s in chain)
    # 三段全过。到方法档为止——再往上是人的事。
    if not human_approval:
        return MethodState(
            rule_id, "personal_method", sharing, owner, evidence,
            blocked_by="升共享层需人工审阅 + 脱敏 + 跨用户复现（spec §7.10：不得由 agent 批准）",
            needs_human=True,
        )
    target = str(human_approval.get("state") or "")
    if target not in HUMAN_ONLY:
        return MethodState(
            rule_id, "personal_method", sharing, owner, evidence,
            blocked_by=f"人工记录的目标档 {target!r} 不在 {sorted(HUMAN_ONLY)}，忽略",
            needs_human=True,
        )
    if not str(human_approval.get("approved_by") or "").strip():
        return MethodState(
            rule_id, "personal_method", sharing, owner, evidence,
            blocked_by="人工记录缺 approved_by：没有署名的批准不算批准",
            needs_human=True,
        )
    return MethodState(
        rule_id, target, sharing, owner,
        evidence + (f"human:{human_approval.get('approved_by')}",),
        blocked_by=None,
    )


def render_queue(states: list[MethodState]) -> str:
    """候选经验队列：谁在哪一档、卡在什么上。按等级升序——**最该动手的排在前面**。"""
    order = {name: i for i, name in enumerate(LADDER)}
    ranked = sorted(states, key=lambda s: (order.get(s.state, -1), s.rule_id))
    out = ["# 候选经验队列", ""]
    if not states:
        return "\n".join(out + ["（没有候选规则。`methodology_backtest.py propose` 从纠偏登记一条。）"])
    in_lib = sum(1 for s in states if s.in_method_library)
    out.append(f"> 共 {len(states)} 条 · 已进方法库 {in_lib} 条 · 待人工审阅 {sum(1 for s in states if s.needs_human)} 条")
    out.append("")
    for s in ranked:
        flag = "✔" if s.in_method_library else " "
        out.append(f"{flag} {s.rule_id}  [{s.state}]  {s.sharing}/{s.owner}")
        if s.blocked_by:
            out.append(f"    卡在：{s.blocked_by}")
        for ev in s.evidence:
            out.append(f"    收据：{ev}")
    return "\n".join(out)
