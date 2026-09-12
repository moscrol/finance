"""候选经验的生命周期状态（终局 spec §5.1、§7.10；V1「候选经验队列」那一件；工单 #42 晋升认证）。

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

## 认证门（工单 #42，补强 spec OPT-04）

上面三条门在 PR #607 落地时有四个漏洞，都是「把不该拼在一起的收据拼成了一条链」：
跨 ``@v*`` 收集、读 ``stats.verdict`` 而不是顶层最终结论、任意 supported 收据贪心成链、
refuted 之后再来一份 supported 就复活。补法只有一个原则——**一条链只认一个身份**：

4. **同身份**：``(rule_version, rule_sha256, label_version)`` 任一变化就是新的验证轮次；
   旧轮次的收据保留为历史，不进新轮次的链。规则文档给了 ``version`` / 内容 hash 时只看
   那份身份的收据。
5. **预声明阶段**：只有跑之前就声明了 ``declared_stage`` 的收据才是晋升证据，且每级只认
   声明为该级的那份；没声明的是探索或历史观察。证伪不需要声明——同身份的 ``refuted``
   照旧生效（证据的不对称性：推翻不用预注册，晋升要）。
6. **顶层最终结论**：读收据顶层 ``verdict``（scan 下已含 BH 校正），``stats.verdict`` 只用来
   向用户解释「原始读数过了、校正后没过」。缺顶层结论或缺 ``rule.sha256`` 的老收据只算历史观察，
   不自动补一个「通过」身份。
7. **失效开新轮次**：``refuted`` 结束当前轮次；之后的收据从 discovery 重新走，一份 supported
   不能复活方法。
8. **同级不许换窗**：同一阶段在同一轮次出现两个不同窗口 = 事后挑窗，卡住并说明；同窗重跑
   是正当的（数据修订后重算），以**最新**一份为准，不能挑好的那次。

状态仍然是纯推导：同一组收据算两遍结果相同，同一份收据投递两次不多算一步——这就是
「晋升写入幂等」在推导式实现里的形状。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from intelligence.services.methodology_backtest.receipts import DECLARED_STAGES, RECEIPT_SCHEMA

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

# 三段门的声明角色，顺序即阶梯。与 receipts.DECLARED_STAGES 同源，这里只是给个短名。
STAGES: tuple[str, ...] = DECLARED_STAGES

_STAGE_HINT = {
    "discovery": "先出一份发现窗收据",
    "validation": "换一段**整段晚于**发现窗的数据",
    "holdout": "再换一段更晚、且前两步没读过的数据",
}


@dataclass(frozen=True)
class Window:
    start: str
    end: str

    def strictly_after(self, other: "Window") -> bool:
        """整段晚于 ``other``：本段起点要**严格晚于**对方终点，不许重叠。"""
        return bool(self.start and other.end) and self.start > other.end


@dataclass(frozen=True)
class Step:
    """一次检验：哪个窗口、什么结论、哪份收据、属于哪个身份、声明了哪个角色。"""

    window: Window
    verdict: str
    receipt_path: str
    generated_at: str
    rule_version: int | None = None
    rule_sha256: str | None = None
    label_version: str | None = None
    declared_stage: str | None = None
    verdict_internal: str | None = None

    @property
    def identity(self) -> tuple[int | None, str | None, str | None]:
        return (self.rule_version, self.rule_sha256, self.label_version)

    @property
    def has_final_verdict(self) -> bool:
        """有顶层最终结论、且带规则内容身份，才进入轮次推导；老收据缺这些只算历史观察。"""
        return bool(self.verdict) and self.rule_sha256 is not None

    @property
    def promotable(self) -> bool:
        """能当晋升证据：认证过 + 跑之前声明了阶段。"""
        return self.has_final_verdict and self.declared_stage in STAGES


@dataclass(frozen=True)
class MethodState:
    rule_id: str
    state: str
    sharing: str
    owner: str
    evidence: tuple[str, ...]
    blocked_by: str | None
    needs_human: bool = False
    validation_cycle: int = 0
    history_receipts: int = 0

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
            "validation_cycle": self.validation_cycle,
            "history_receipts": self.history_receipts,
        }


def _int_or_none(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _version_from_ref(ref: Any) -> int | None:
    """``r1@v3`` → 3。老收据 ``rule.version`` 缺失时从 ref 兜底，兜不到就是 None。"""
    text = str(ref or "")
    if "@v" not in text:
        return None
    tail = text.rsplit("@v", 1)[1]
    return int(tail) if tail.isdigit() else None


def load_steps(root: str | Path, rule_id: str) -> list[Step]:
    """读某条规则的**全部**收据（所有版本），按 ``generated_at`` 升序。

    不用 ``latest_receipt``：晋升看的是历史轨迹（发现 → 验证 → holdout 三段窗口），
    只看最近一次就永远只有一段窗口，晋升条件恒不成立。
    跨版本读是为了让历史不丢；**按身份过滤发生在 ``derive_state``**，不在这里。
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
            rule_block = doc.get("rule") or {}
            if str(rule_block.get("rule_id")) != rule_id:
                continue
            win = doc.get("window") or {}
            sha = rule_block.get("sha256")
            label_version = (doc.get("conditions") or {}).get("label_version")
            stage = doc.get("declared_stage")
            steps.append(
                Step(
                    window=Window(str(win.get("start") or ""), str(win.get("end") or "")),
                    verdict=str(doc.get("verdict") or ""),
                    receipt_path=str(path),
                    generated_at=str(doc.get("generated_at") or ""),
                    rule_version=_int_or_none(rule_block.get("version")) or _version_from_ref(rule_block.get("ref")),
                    rule_sha256=str(sha) if sha else None,
                    label_version=str(label_version) if label_version is not None else None,
                    declared_stage=str(stage) if stage else None,
                    verdict_internal=str((doc.get("stats") or {}).get("verdict") or "") or None,
                )
            )
    return sorted(steps, key=_chronological_key)


def _chronological_key(step: Step) -> tuple[datetime, str]:
    """排序键：**解析后的时刻**优先，文件名只作同一时刻内的稳定 tiebreak。

    不用裸字符串比较：新旧收据的 ``generated_at`` 精度不同（秒级 `…T12:00:00+00:00`
    与微秒级 `…T12:00:00.500000+00:00`），字典序在 `+` 与 `.` 上的先后是巧合不是语义。
    更要紧的是文件名后缀含内容 hash——时刻一旦相同，「谁更晚」就由 hash 随机决定，
    实测能让稍后的 not_distinguishable 排到更早的 supported 前面（09-12 复核）。
    """
    raw = step.generated_at
    try:
        ts = datetime.fromisoformat(raw)
    except ValueError:
        ts = datetime.min.replace(tzinfo=timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return (ts.astimezone(timezone.utc), step.receipt_path)


def _identity_diff(prev: Step, cur: Step) -> str:
    parts = []
    if prev.rule_version != cur.rule_version:
        parts.append(f"version v{prev.rule_version} → v{cur.rule_version}")
    if prev.rule_sha256 != cur.rule_sha256:
        parts.append("rule_sha256 变化（规则内容改了）")
    if prev.label_version != cur.label_version:
        parts.append(f"label_version {prev.label_version} → {cur.label_version}")
    return "、".join(parts) or "身份变化"


def _cycles(certified: list[Step]) -> tuple[list[list[Step]], list[str]]:
    """把认证收据切成验证轮次：身份一变、或出现 refuted，当前轮次结束。

    返回 ``(轮次列表, 每个轮次的开启原因)``；第一轮的原因是空串。
    """
    cycles: list[list[Step]] = []
    reasons: list[str] = [""]
    current: list[Step] = []
    for step in certified:
        if current and step.identity != current[-1].identity:
            cycles.append(current)
            reasons.append(f"身份变化开启新轮次：{_identity_diff(current[-1], step)}，无兼容声明，旧收据不计入")
            current = []
        current.append(step)
        if step.verdict == REFUTED:
            cycles.append(current)
            reasons.append("上一轮次被证伪后开启：要复活需在新轮次重新走三段门")
            current = []
    if current:
        cycles.append(current)
    else:
        # 最后一步是 refuted：它所在的那段就是当前轮次，没有「之后」。
        reasons.pop()
    return cycles, reasons


def _stage_ladder(cycle: list[Step]) -> tuple[list[Step], str]:
    """在一个轮次里按 discovery → validation → holdout 逐级取证。

    返回 ``(过门的步, 卡住的原因)``；三级全过时原因为空串。每级只认声明为该级的收据。
    """
    passed: list[Step] = []
    prev: Step | None = None
    undeclared = sum(1 for s in cycle if s.has_final_verdict and s.declared_stage not in STAGES and s.verdict != REFUTED)
    for stage in STAGES:
        mine = [s for s in cycle if s.promotable and s.declared_stage == stage]
        if not mine:
            note = f"；另有 {undeclared} 份未声明阶段的收据只算历史观察" if undeclared else ""
            return passed, (
                f"缺 {stage} 阶段收据：{_STAGE_HINT[stage]}，"
                f"`methodology_backtest.py run <rule> --stage {stage}`{note}"
            )
        windows = {(s.window.start, s.window.end) for s in mine}
        if len(windows) > 1:
            return passed, (
                f"{stage} 阶段在同一轮次跑了 {len(windows)} 个不同窗口，属事后挑窗，本轮不认；"
                "要换窗请升 version 开新轮次"
            )
        latest = mine[-1]  # 已按 generated_at 升序：同窗重跑以最新一份为准
        if latest.verdict != SUPPORTED:
            extra = (
                "（内部原始读数 supported，经多重校正后的最终结论未通过）"
                if latest.verdict_internal == SUPPORTED
                else ""
            )
            return passed, f"{stage} 阶段最终结论为 {latest.verdict}{extra}：未过门"
        if prev is not None and not latest.window.strictly_after(prev.window):
            return passed, (
                f"{stage} 窗口 {latest.window.start}→{latest.window.end} 未整段晚于 "
                f"{prev.declared_stage} 窗口（须在 {prev.window.end} 之后）：不算过门"
            )
        passed.append(latest)
        prev = latest
    return passed, ""


def derive_state(
    rule: dict[str, Any],
    steps: list[Step],
    *,
    human_approval: dict[str, Any] | None = None,
    rule_sha256: str | None = None,
    current_label_version: str | None = None,
) -> MethodState:
    """算出这条候选现在在哪一档。``human_approval`` 只能由人写入，agent 不得伪造。

    ``rule["version"]`` / ``rule_sha256`` 给了就只看那份身份的收据；其余收据是历史，
    计入 ``history_receipts`` 但不进链。

    ``current_label_version`` 给了就再加一道**绝对**身份检查：标签口径升版之后，旧版本
    收据一律降为历史观察。没有它时 ``_cycles`` 只能看出收据**彼此之间**的版本变化——
    三份同为 v4 的成功收据在 v5 代码下仍然彼此一致，于是照样成链、照样 personal_method，
    要等到有人跑出第一份 v5 收据才切轮次。「升级后旧收据自动成为历史观察」这句话，
    在传入当前版本之前是不成立的（09-12 实测）。重建旁路库本身不触发失效，也是同一个洞。
    """
    rule_id = str(rule.get("rule_id") or rule.get("id") or "")
    sharing = str(rule.get("sharing") or "private")
    owner = str(rule.get("owner") or "")

    if not steps:
        return MethodState(
            rule_id, "candidate", sharing, owner, (),
            blocked_by="还没跑过任何检验：先 `methodology_backtest.py run <rule> --stage discovery` 出一份发现窗收据",
        )

    rule_version = _int_or_none(rule.get("version"))
    scoped = [
        s for s in steps
        if (rule_version is None or s.rule_version == rule_version)
        and (rule_sha256 is None or s.rule_sha256 == rule_sha256)
        # 标签口径是身份的一部分：升版后旧收据不可比，降为历史观察（不是「等下一份新收据再说」）
        and (current_label_version is None or s.label_version == current_label_version)
    ]
    certified = [s for s in scoped if s.has_final_verdict]
    if not certified:
        stale = (
            sorted({s.label_version or "(无)" for s in steps if s.label_version != current_label_version})
            if current_label_version is not None
            else []
        )
        if stale:
            return MethodState(
                rule_id, "candidate", sharing, owner, (),
                blocked_by=(
                    f"有 {len(steps)} 份收据，但标签口径已升到 {current_label_version}，"
                    f"它们产自 {'、'.join(stale)}：口径不可比，全部降为历史观察。"
                    "重建旁路库后按阶段重跑（`methodology_backtest.py run <rule> --stage discovery` 起）"
                ),
                history_receipts=len(steps),
            )
        return MethodState(
            rule_id, "candidate", sharing, owner, (),
            blocked_by=(
                f"有 {len(steps)} 份收据但没有一份是本身份的认证收据（缺顶层 verdict / rule.sha256，"
                "或属其他版本 / 内容）：只算历史观察，不补「通过」身份。"
                "用 `methodology_backtest.py run <rule> --stage discovery` 重跑"
            ),
            history_receipts=len(steps),
        )

    cycles, reasons = _cycles(certified)
    current = cycles[-1]
    cycle_no = len(cycles)
    cycle_note = f"第 {cycle_no} 轮次（{reasons[-1]}）" if cycle_no > 1 else ""
    history = len(steps) - sum(1 for s in current if s.promotable)

    def _state(state: str, evidence: tuple[str, ...], blocked_by: str | None, *, needs_human: bool = False) -> MethodState:
        if blocked_by and cycle_note:
            blocked_by = f"{blocked_by}；{cycle_note}"
        return MethodState(
            rule_id, state, sharing, owner, evidence, blocked_by,
            needs_human=needs_human, validation_cycle=cycle_no, history_receipts=history,
        )

    latest = current[-1]
    passed, block = _stage_ladder([s for s in current if s.verdict != REFUTED])

    # 终态优先判：最近一次说被证伪 / 样本不足，就不是「在晋升路上」。
    if latest.verdict == REFUTED:
        # 本轮次已经走完三段门又被推翻 = invalidated；没走完 = contradicted。
        was_method = len(passed) == len(STAGES)
        return _state(
            "invalidated" if was_method else "contradicted",
            (latest.receipt_path,),
            "最近一次检验被证伪；要复活需要新窗口在新轮次重新走三段门",
        )
    if latest.verdict == INSUFFICIENT and not passed:
        return _state(
            "insufficient", (latest.receipt_path,),
            "样本不足（N < min_n）；等更多事件累积，**不出比率**",
        )

    n = len(passed)
    if n == 0:
        return _state("candidate", (), block)
    if n == 1:
        return _state("discovery_passed", (passed[0].receipt_path,), block)
    if n == 2:
        return _state("validation_passed", tuple(s.receipt_path for s in passed), block)

    evidence = tuple(s.receipt_path for s in passed)
    # 三段全过。到方法档为止——再往上是人的事。
    if not human_approval:
        return _state(
            "personal_method", evidence,
            "升共享层需人工审阅 + 脱敏 + 跨用户复现（spec §7.10：不得由 agent 批准）",
            needs_human=True,
        )
    target = str(human_approval.get("state") or "")
    if target not in HUMAN_ONLY:
        return _state(
            "personal_method", evidence,
            f"人工记录的目标档 {target!r} 不在 {sorted(HUMAN_ONLY)}，忽略",
            needs_human=True,
        )
    if not str(human_approval.get("approved_by") or "").strip():
        return _state(
            "personal_method", evidence,
            "人工记录缺 approved_by：没有署名的批准不算批准",
            needs_human=True,
        )
    return _state(target, evidence + (f"human:{human_approval.get('approved_by')}",), None)


def state_for_rule(
    rules_dir: str | Path,
    receipts_dir: str | Path,
    rule_id: str,
    *,
    human_approval: dict[str, Any] | None = None,
    current_label_version: str | None = None,
) -> MethodState | None:
    """按 ``rule_id`` 找当前生效的规则文件并推导状态；找不到规则文件返回 ``None``。

    给经验卡门等**规则目录之外的晋升入口**用的统一读法：与 ``queue`` 同一口径——
    身份用规则文件字节的 sha256 锁定（写收据的 run/scan 也是这个 hash），所以任何
    入口看到的生命周期状态与 `methodology_backtest.py queue` 一致，不存在第二套判定。
    「当前生效」= 同 ``rule_id`` 的文件里 ``version`` 最大那份（文件名序兜底）。
    """
    base = Path(rules_dir).expanduser()
    if not base.is_dir():
        return None
    best: tuple[tuple[int, str], Path, dict[str, Any]] | None = None
    for path in sorted(base.glob("*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(doc, dict):
            continue
        rid = str(doc.get("rule_id") or doc.get("id") or path.stem.split(".v")[0])
        if rid != rule_id:
            continue
        rank = (_int_or_none(doc.get("version")) or 0, path.name)
        if best is None or rank > best[0]:
            best = (rank, path, doc)
    if best is None:
        return None
    _, path, doc = best
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    steps = load_steps(receipts_dir, rule_id)
    if current_label_version is None:
        from .labels import LABEL_VERSION

        current_label_version = LABEL_VERSION
    return derive_state(
        {**doc, "rule_id": rule_id}, steps, human_approval=human_approval,
        rule_sha256=sha, current_label_version=current_label_version,
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
        out.append(
            f"{flag} {s.rule_id}  [{s.state}]  {s.sharing}/{s.owner}  "
            f"轮次 {s.validation_cycle} · 历史收据 {s.history_receipts}"
        )
        if s.blocked_by:
            out.append(f"    卡在：{s.blocked_by}")
        for ev in s.evidence:
            out.append(f"    收据：{ev}")
    return "\n".join(out)
