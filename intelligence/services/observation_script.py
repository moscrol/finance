"""观察剧本（ObservationScript）：小白入口的可登记对象 + 合规硬门 + T+1 回检登记。

终局 spec `2026-09-06-personal-research-calibration-endstate-design.md` §3.2；
路线图 `2026-09-05-time-river-gap-roadmap.md` G-03 / G-12a。

## 它替代什么

观察剧本回答「明天要看什么，以及什么条件会让它升级、降级或放弃」，**不回答「明天买什么」**。
它是「第二天的方向」这类提问的产品答案：翻译成可回检的观察项，而不是拒绝对话。

## 三条设计取舍

1. **不新开回检引擎**。剧本确认后登记进既有 ``checkpoints.jsonl``（``object_type=
   observation_script``），到期由既有 ``checkpoint recheck`` + resolver 判定。
   红线是「不建第二套台账」——判断轨已经有一套可证伪点机制，再造一套就有两个胜率口径。
2. **回检判「变量是否按条件触发」，不判涨跌**。所以机检规格走 ``market_daily``
   （盘面字段阈值），不走 ``stock_return``。没有机检条件的剧本到期是 ``unverifiable``
   （非终态、不计入胜率、下次仍进队列），**不猜**。
3. **``late`` 是标记不是拒绝**。晚于次日开盘登记的剧本照样入台账（用户的记录不该被吞），
   但 ``enters_calibration`` 为假——晚登记的剧本已经看见了盘中走势，进校准就是前视污染。
   判不出登记时刻时按 ``late`` 处理（fail closed：不能证明及时，就不能算及时）。

## 状态机

``drafted``（系统生成 / 用户起草）→ ``confirmed``（用户确认，登记 checkpoint）
                                 → ``skipped``（用户跳过——**有效行为，不计失败**，spec §3.1）
``confirmed`` 但晚登记 → ``late``；到期仍停在 ``drafted`` → ``expired``。

## 提取前置（工单 #53）：同一个台账文件，三类记录

入口先收用户自己的观察剧本、再披露系统骨架。为此本台账用 ``record_kind`` 分型存
**剧本 / 提取尝试 / 提取事件**三类（缺该字段 = 存量剧本），写入者仍然只有本模块一个。
判定侧（关联键、顺序门、字段差异）在 ``observation_extraction.py``——那边全是纯函数，
不写盘。为什么不另开台账、也不写 ``interactions.jsonl``：见「台账分型」那节的注释。

本模块只用标准库：可离线跑、可独立单测，与 ``checkpoints.py`` 同规格。
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import date as date_cls, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping

from intelligence.services import checkpoints as checkpoints_svc
from intelligence.services import compliance_gate
from intelligence.services import observation_extraction as extraction

# 剧本作用域：只到指数 / 板块 / 题材。个股不在其列——这是产品定位红线，不是配置项。
SCOPES = ("index", "sector", "theme")
VISIBILITIES = ("private", "shared_candidate", "shared")
STATUSES = ("drafted", "confirmed", "skipped", "late", "expired")

# 判断轨对象分三类（roadmap §13.2 F2）；观察剧本是其中一类，写进 checkpoint 记录，
# 供 G-09 的胜率面板按对象类型分列——三类混算会让「用户决策」的胜率被系统草稿稀释。
OBJECT_TYPE = "observation_script"
CHECKPOINT_CATEGORY = "observation_script"
CHECKPOINT_SOURCE = "observation_script"

# --------------------------------------------------------------------------- #
# 台账分型（工单 #53 §2.4）：一个文件，三类记录
#
# 为什么不另建文件：``interactions.jsonl`` 是「新用户 / 老用户」默认开关的判据台账，
# 往里写任何一行都会把新用户翻成老用户，带读默认值随之改变——记录过程反而改变了
# 被观测的行为。checkpoint 台账同理：过程事件混进去，回检队列与胜率分母就脏了。
# 所以尝试与事件寄存在剧本台账里，用 ``record_kind`` 区分，消费方各取所需。
# --------------------------------------------------------------------------- #
RECORD_SCRIPT = "script"
RECORD_ATTEMPT = "attempt"
RECORD_EVENT = "event"
RECORD_KINDS = (RECORD_SCRIPT, RECORD_ATTEMPT, RECORD_EVENT)
# 认不出来的类型（将来的新分型）既不算剧本也不算事件，但仍留在原始导出里。
RECORD_UNKNOWN = "unknown"

# 作者来源。**不复用 ``user_authored``**——后者表示「产品外手填、没有上下文投影」，
# 是投影门禁的豁免声明，与「这条是不是用户在提取入口写的」是两件事。
AUTHOR_USER = "user"
AUTHOR_SYSTEM = "system"

# 五个业务事件（工单 §2.4 那张表）。尝试记录不是第六个事件。
EVENT_DRAFT_SUBMITTED = "draft_submitted"
EVENT_DRAFT_SKIPPED = "draft_skipped"
EVENT_SCRIPT_CONFIRMED = "script_confirmed"
EVENT_ABANDONED = "abandoned"
EVENT_READ_COMPLETED = "read_completed"
EVENTS = (
    EVENT_DRAFT_SUBMITTED,
    EVENT_DRAFT_SKIPPED,
    EVENT_SCRIPT_CONFIRMED,
    EVENT_ABANDONED,
    EVENT_READ_COMPLETED,
)

# 入口名。``manual_confirm`` 是完整手填确认——它没有对应的提取尝试，
# ``attempt_id`` 必须是 null，不能伪造一个「曾进入提取流程」的假象。
ENTRYPOINT_MANUAL_CONFIRM = "manual_confirm"

ATTEMPT_PENDING = "pending"
ATTEMPT_CLOSED = "closed"

# A 股开盘 09:30（+08:00）。登记截止时刻 = as_of 的下一个自然日 09:30。
# 用自然日而非交易日是**故意从严**：遇周末 / 节假日时真实开盘更晚，按自然日算只会
# 更早判 late，不会漏判。调用方拿得到交易日历时应显式传 ``next_open``。
CN_TZ = timezone(timedelta(hours=8))
DEFAULT_OPEN_TIME = (9, 30)
# 与 river.py 同一个默认库路径常量，不各写各的（改一处漏一处会让两边读不同的库）。
DEFAULT_DB = "db/market_feature_store.duckdb"

DISCLAIMER = "本条为观察项，不构成投资建议。"


@dataclass(frozen=True)
class Rejection:
    """硬门拒绝的一条理由。``field`` 指出哪个字段要改，``hint`` 指出怎么改。"""

    code: str
    field: str
    detail: str
    hint: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "field": self.field, "detail": self.detail, "hint": self.hint}


class ObservationScriptRejected(ValueError):
    """硬门拒绝。``rejections`` 是可修正的错误清单，不是一句「不合规」。"""

    def __init__(self, rejections: list[Rejection]) -> None:
        self.rejections = rejections
        super().__init__("；".join(f"[{r.code}] {r.detail}" for r in rejections))

    def to_dict(self) -> dict[str, Any]:
        return {"rejected": True, "rejections": [r.to_dict() for r in self.rejections]}


# 结构性错误码（词表类错误码在 compliance_gate 里）
E_SCOPE = "E_SCOPE"
E_NO_VARIABLES = "E_NO_VARIABLES"
E_NO_ABANDON_CONDITION = "E_NO_ABANDON_CONDITION"
E_INVALID_AS_OF = "E_INVALID_AS_OF"
E_INVALID_STATUS = "E_INVALID_STATUS"
E_INVALID_VISIBILITY = "E_INVALID_VISIBILITY"

_STRUCTURAL_HINTS = {
    E_SCOPE: f"scope 只能是 {SCOPES}——个股请换成它所在的题材或板块",
    E_NO_VARIABLES: "至少写一个要观察的变量：剧本回答「明天看什么」",
    E_NO_ABANDON_CONDITION: "至少写一个降级 / 放弃条件——没有放弃条件的剧本不可证伪，回检时判不了",
    E_INVALID_AS_OF: "as_of 需 YYYY-MM-DD",
    E_INVALID_STATUS: f"status 只能是 {STATUSES}",
    E_INVALID_VISIBILITY: f"visibility 只能是 {VISIBILITIES}",
}


@dataclass(frozen=True)
class ObservationScript:
    """spec §3.2 的对象。元组而非列表：登记后不可静默改写（append-only 台账的前提）。"""

    as_of: str
    scope: str
    entity_ids: tuple[str, ...]
    variables: tuple[str, ...]
    downgrade_or_abandon_conditions: tuple[str, ...]
    upgrade_conditions: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    # 可机检的盘面条件（``advancers>=3000`` 形式，字段=fact_market_daily 列名）。
    # 空 → 到期走人工判定，回检出 unverifiable，不猜。
    machine_conditions: tuple[str, ...] = ()
    user_id: str = "default"
    visibility: str = "private"
    scope_note: str = ""
    framework_version: str | None = None
    knowledge_cutoff: str | None = None
    status: str = "drafted"
    recorded_at: str | None = None
    checkpoint_id: str | None = None
    id: str | None = None
    # 这条剧本是从**事后视角**的切片派生的（上游 knowledge_cutoff > as_of）。
    # 终局 spec §4.1：hindsight 只用于人工复核，不得进入任何校准或方法有效性统计。
    # 标记必须逐跳传下去：切片 → 带读草稿 → 剧本 → checkpoint → calibrate，
    # 中间断在哪一跳，最后那道门就形同虚设。
    hindsight: bool = False
    # 生成这条剧本时读者 / 模型看到的上下文投影（工单 #34；09-06 spec §4.2 / §4.5）。
    # agent 派生的剧本必带；用户在产品外手写的可以为空，登记时显式声明 ``user_authored``，
    # 台账单列——「忘了传」与「本来就没有」必须分得开。
    projection_hash: str | None = None
    model_id: str | None = None

    @property
    def text_fields(self) -> dict[str, tuple[str, ...]]:
        """要过词表硬门的自由文本字段。``evidence_refs`` 是引用不是主张，不扫。"""
        return {
            "variables": self.variables,
            "upgrade_conditions": self.upgrade_conditions,
            "downgrade_or_abandon_conditions": self.downgrade_or_abandon_conditions,
            "scope_note": (self.scope_note,) if self.scope_note else (),
        }

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        for key in (
            "entity_ids",
            "variables",
            "upgrade_conditions",
            "downgrade_or_abandon_conditions",
            "evidence_refs",
            "machine_conditions",
        ):
            out[key] = list(out[key])
        return out


def _clean(values: Any) -> tuple[str, ...]:
    out: list[str] = []
    for v in values or []:
        s = str(v).strip()
        if s and s not in out:
            out.append(s)
    return tuple(out)


def make(
    *,
    as_of: str,
    scope: str,
    entity_ids: Any,
    variables: Any,
    downgrade_or_abandon_conditions: Any,
    upgrade_conditions: Any = (),
    evidence_refs: Any = (),
    machine_conditions: Any = (),
    user_id: str = "default",
    visibility: str = "private",
    scope_note: str = "",
    framework_version: str | None = None,
    knowledge_cutoff: str | None = None,
    status: str = "drafted",
    recorded_at: str | None = None,
    hindsight: bool = False,
    projection_hash: str | None = None,
    model_id: str | None = None,
) -> ObservationScript:
    """构造对象（只规整、不校验）。校验走 ``validate`` / 登记走 ``register``。"""
    return ObservationScript(
        as_of=str(as_of or "").strip()[:10],
        scope=str(scope or "").strip(),
        entity_ids=_clean(entity_ids),
        variables=_clean(variables),
        downgrade_or_abandon_conditions=_clean(downgrade_or_abandon_conditions),
        upgrade_conditions=_clean(upgrade_conditions),
        evidence_refs=_clean(evidence_refs),
        machine_conditions=_clean(machine_conditions),
        user_id=str(user_id or "default").strip(),
        visibility=str(visibility or "private").strip(),
        scope_note=str(scope_note or "").strip(),
        framework_version=framework_version,
        knowledge_cutoff=knowledge_cutoff,
        status=str(status or "drafted").strip(),
        recorded_at=recorded_at,
        hindsight=bool(hindsight),
        projection_hash=(str(projection_hash).strip() or None) if projection_hash else None,
        model_id=(str(model_id).strip() or None) if model_id else None,
    )


def validate(script: ObservationScript) -> list[Rejection]:
    """硬门：结构 + 词表。返回空列表即通过。

    个股判定走两道：``scope`` 不能是个股（结构），``entity_ids`` 与自由文本里不能出现
    个股代码（词表）。只查其中一道会漏——用户可以把 scope 填成 ``theme`` 却在变量里
    写「600519 涨到 2000 元」。
    """
    out: list[Rejection] = []

    if script.scope not in SCOPES:
        out.append(Rejection(E_SCOPE, "scope", f"scope={script.scope!r} 不在 {SCOPES}", _STRUCTURAL_HINTS[E_SCOPE]))
    if script.status not in STATUSES:
        out.append(Rejection(E_INVALID_STATUS, "status", f"status={script.status!r}", _STRUCTURAL_HINTS[E_INVALID_STATUS]))
    if script.visibility not in VISIBILITIES:
        out.append(
            Rejection(E_INVALID_VISIBILITY, "visibility", f"visibility={script.visibility!r}", _STRUCTURAL_HINTS[E_INVALID_VISIBILITY])
        )
    try:
        date_cls.fromisoformat(script.as_of)
    except ValueError:
        out.append(Rejection(E_INVALID_AS_OF, "as_of", f"as_of={script.as_of!r}", _STRUCTURAL_HINTS[E_INVALID_AS_OF]))
    if not script.variables:
        out.append(Rejection(E_NO_VARIABLES, "variables", "没有可观察变量", _STRUCTURAL_HINTS[E_NO_VARIABLES]))
    if not script.downgrade_or_abandon_conditions:
        out.append(
            Rejection(
                E_NO_ABANDON_CONDITION,
                "downgrade_or_abandon_conditions",
                "没有降级 / 放弃条件",
                _STRUCTURAL_HINTS[E_NO_ABANDON_CONDITION],
            )
        )

    for eid in script.entity_ids:
        if compliance_gate.is_stock_entity(eid):
            out.append(
                Rejection(
                    compliance_gate.E_STOCK_SCOPE,
                    "entity_ids",
                    f"实体 {eid!r} 是个股",
                    compliance_gate.CODE_HINTS[compliance_gate.E_STOCK_SCOPE],
                )
            )

    for field_name, values in script.text_fields.items():
        for value in values:
            for hit in compliance_gate.scan(value):
                out.append(Rejection(hit.code, field_name, f"命中「{hit.term}」：{hit.context}", hit.hint))

    for cond in script.machine_conditions:
        try:
            checkpoints_svc.normalize_metric({"type": "market_daily", "conditions": [cond]})
        except ValueError as exc:
            out.append(Rejection("E_MACHINE_CONDITION", "machine_conditions", str(exc), "形如 advancers>=3000（字段=fact_market_daily 列名）"))

    return out


def ensure_valid(script: ObservationScript) -> ObservationScript:
    """通过则原样返回，否则抛 ``ObservationScriptRejected``。"""
    rejections = validate(script)
    if rejections:
        raise ObservationScriptRejected(rejections)
    return script


# --------------------------------------------------------------------------- #
# 时间：late 判定
# --------------------------------------------------------------------------- #
def default_next_open(as_of: str) -> datetime:
    """``as_of`` 之后第一个**非周末**日的 09:30(+08:00)。

    跳周末不是放水：周五收盘到周一开盘之间没有交易，用户看不到任何后续行情，
    截止线放到周一才是「次日开盘」的本义。按自然日算会把「周六补做周五的功课」
    判成 late，把一条及时的判断挡在校准之外——那是误判，不是从严。

    节假日仍按从严处理（本库没有节假日表，见 ``next_trading_open`` 的说明）：
    国庆前最后一个交易日的剧本，若拖到长假中段才登记会被标 late。宁可多标几个，
    不可放进前视样本。
    """
    day = date_cls.fromisoformat(as_of[:10]) + timedelta(days=1)
    while day.weekday() >= 5:  # 5=周六 6=周日
        day += timedelta(days=1)
    return datetime(day.year, day.month, day.day, *DEFAULT_OPEN_TIME, tzinfo=CN_TZ)


def next_trading_open(as_of: str, *, db_path: str | Path | None = None) -> datetime | None:
    """下一个**已在库里**的交易日 09:30(+08:00)；查不到返回 ``None``（调用方回落默认）。

    ⚠ 只对**历史日期**有效：库里最新一天是已收盘的交易日，所以「今天登记今天的剧本」
    这条主路径永远查不到下一天，必然回落到 ``default_next_open``。它真正解决的是
    节假日附近的**回填 / 回放**——那时下一个交易日已经在库里，能算准。
    本库没有独立交易日历表（实测 ``dim_*`` 只有板块维度），所以未来日只能靠周末规则。

    ``import duckdb`` 放在函数里：本模块在导入期保持只依赖标准库，离线可测。
    """
    import duckdb

    db = Path(db_path or os.environ.get("MARKET_FEATURE_STORE_DB", DEFAULT_DB)).expanduser()
    if not db.exists():
        return None
    con = duckdb.connect(str(db), read_only=True)
    try:
        row = con.execute(
            "SELECT MIN(CAST(trade_date AS DATE)) FROM fact_market_daily "
            "WHERE CAST(trade_date AS DATE) > CAST(? AS DATE)",
            [as_of[:10]],
        ).fetchone()
    except Exception:  # pragma: no cover - 老库没这张表：回落自然日，不阻断登记
        return None
    finally:
        con.close()
    if not row or row[0] is None:
        return None
    day = row[0]
    return datetime(day.year, day.month, day.day, *DEFAULT_OPEN_TIME, tzinfo=CN_TZ)


def _parse_recorded_at(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=CN_TZ)


def is_late(script: ObservationScript, *, next_open: datetime | None = None) -> bool:
    """晚于次日开盘登记 = ``late``。判不出登记时刻也算 late（fail closed）。"""
    recorded = _parse_recorded_at(script.recorded_at)
    if recorded is None:
        return True
    try:
        deadline = next_open or default_next_open(script.as_of)
    except ValueError:
        return True
    return recorded >= deadline


def enters_calibration(record: dict[str, Any]) -> bool:
    """能不能进方法校准：只有**及时确认、且非事后视角**的剧本算数。

    ``skipped`` 不是失败（spec §3.1「跳过本身是有效行为」），但它也不是判断，
    所以同样不进分母——把跳过记成落空，会把「今天没看法」惩罚成「今天看错了」。

    ``hindsight`` 一票否决：它是从 ``knowledge_cutoff > as_of`` 的切片派生的，
    拿它进校准等于用「后来才知道的事」证明「当时判得准」（spec §4.1 明禁）。
    """
    return str(record.get("status")) == "confirmed" and not record.get("hindsight")


# --------------------------------------------------------------------------- #
# 台账
# --------------------------------------------------------------------------- #
def _make_id(script: ObservationScript, recorded_at: str) -> str:
    payload = json.dumps(
        {
            "as_of": script.as_of,
            "scope": script.scope,
            "entity_ids": list(script.entity_ids),
            "variables": list(script.variables),
            "recorded_at": recorded_at,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return f"os-{script.as_of}-{hashlib.sha1(payload.encode('utf-8')).hexdigest()[:6]}"


def _confirm_action_key(
    script: ObservationScript, *, attempt_id: str | None, entrypoint: str | None
) -> str:
    """确认动作的稳定身份：由**内容 + 尝试 + 入口**算出，**不含录入时刻**。

    动作身份一旦掺进时间戳，重试就会换键，而重试恰恰是唯一需要去重的场景。
    """
    payload = json.dumps(
        {
            "user_id": script.user_id,
            "as_of": script.as_of,
            "scope": script.scope,
            "entity_ids": list(extraction.normalize_values(script.entity_ids)),
            **{
                f: list(extraction.normalize_values(getattr(script, f)))
                for f in extraction.DIFF_FIELDS
            },
            "entrypoint": str(entrypoint or ""),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return _action_key(
        EVENT_SCRIPT_CONFIRMED, attempt_id, hashlib.sha1(payload.encode("utf-8")).hexdigest()
    )


def to_claim(script: ObservationScript) -> str:
    """剧本 → 可证伪陈述（checkpoint 的 ``claim``）。

    句式固定、由字段拼出：回检读的是「变量是否按条件触发」，claim 必须把条件写进去，
    否则半年后看台账只剩一句「关注 XX」，判不了对错。
    """
    entities = "/".join(script.entity_ids) or "（未指定实体）"
    parts = [f"观察剧本｜{script.scope}:{entities}", "变量：" + "；".join(script.variables)]
    if script.upgrade_conditions:
        parts.append("升级条件：" + "；".join(script.upgrade_conditions))
    parts.append("降级或放弃：" + "；".join(script.downgrade_or_abandon_conditions))
    return "｜".join(parts)


def build_metric(script: ObservationScript, *, due: str) -> dict[str, Any] | None:
    """机检规格：有盘面条件走 ``market_daily``，否则 ``None``（人工判定）。"""
    if not script.machine_conditions:
        return None
    return checkpoints_svc.normalize_metric(
        {"type": "market_daily", "conditions": list(script.machine_conditions), "trade_date": due}
    )


def default_due(as_of: str) -> str:
    """默认回检日 = ``default_next_open`` 那一天（同一条跳周末规则，不另立第二套）。

    周六当回检日会让盘面 resolver 查不到当日行 → ``unverifiable`` 挂在队列里重试，
    读数上像「判不了」，其实是「问错了日子」。**节假日同理，但周末规则挡不住**——
    所以能查日历时一律走 ``resolve_due``。
    """
    return default_next_open(as_of).date().isoformat()


def resolve_due(as_of: str, *, db_path: str | Path | None = None) -> str:
    """回检日 = 下一个**交易日**；查不到日历时回落到跳周末规则。

    为什么必须这么绕：``default_due`` 只跳周末，节假日照样会落在不开盘的日子上。
    那时盘面 resolver 查无当日行 → ``unverifiable``，而 ``unverifiable`` 是**非终态**，
    于是这条剧本每晚重判一次、每次都判不了，**永远卡在队列里**。
    resolver 那边不肯拿相邻交易日顶替是对的（原文「那是换了个题目在答」），
    所以只能在**登记侧**把日子定对。

    ⚠ 「今天登记明天」这条主路径仍然可能落空：库里最新一天是已收盘的交易日，
    明天还没发生，日历查不到 → 回落周末规则 → 撞上节假日就还是错的。
    那批漏网的靠 ``nontrading_dues`` 检出、``repoint_due`` 改点，不靠猜。
    """
    day = next_trading_open(as_of, db_path=db_path)
    return day.date().isoformat() if day else default_due(as_of)


def nontrading_dues(
    records: list[dict[str, Any]], trading_days: set[str], *, today: str | None = None
) -> list[dict[str, Any]]:
    """挑出 ``due`` 落在非交易日、且那天已经过去（日历已知）的剧本。

    只挑已过去的：未来的 due 还没到，日历本来就查不到，不算错。
    """
    today = today or date_cls.today().isoformat()
    out: list[dict[str, Any]] = []
    for rec in records:
        due = str(rec.get("due") or "")
        if not due or due > today:
            continue
        if rec.get("status") != "confirmed" or not rec.get("checkpoint_id"):
            continue
        if due not in trading_days:
            out.append(rec)
    return out


def repoint_due(
    path: str | Path,
    record: dict[str, Any],
    *,
    checkpoints_path: str | Path,
    verdicts_path: str | Path,
    trading_days: set[str],
) -> dict[str, Any] | None:
    """把一条 due 落在非交易日的剧本改点到下一个真交易日，返回新记录。

    三件事一起做，缺一件都会留下不一致：

    1. 追加一条新的剧本记录（``due`` 修正、``repointed_from`` 指回旧的）——台账 append-only，
       不改写历史行；
    2. 用修正后的 due 登记**新的 checkpoint**；
    3. 给旧 checkpoint 记一条 ``unverifiable``，``degradation`` 里写明改点到哪天。
       用 ``unverifiable`` 而不是造一个终态：它本来就判不了，这是实话；而且它不进胜率，
       不会污染校准。旧点仍留在队列里但带着去向，人一看就知道该看新的那条。
    """
    due = str(record.get("due") or "")
    as_of = str(record.get("as_of") or "")
    later = sorted(d for d in trading_days if d > as_of)
    if not later:
        return None  # 日历还没长到那儿，改不了就别乱改
    new_due = later[0]
    if new_due == due:
        return None

    script = make(
        **{
            k: v
            for k, v in record.items()
            if k in ObservationScript.__dataclass_fields__ and k not in {"id", "checkpoint_id"}
        }
    )
    _, ck = checkpoints_svc.register_checkpoint(
        Path(checkpoints_path),
        claim=to_claim(script),
        due=new_due,
        category=CHECKPOINT_CATEGORY,
        source=CHECKPOINT_SOURCE,
        themes=list(script.entity_ids),
        metric=build_metric(script, due=new_due),
        framework_version=script.framework_version,
        object_type=OBJECT_TYPE,
        hindsight=script.hindsight,
        # 改点不是新判断：沿用原记录的投影哈希与「用户手写」声明，不重新要一份。
        projection_hash=script.projection_hash,
        model_id=script.model_id,
        user_authored=str(record.get("projection_hash_missing") or "") == checkpoints_svc.USER_AUTHORED,
    )
    checkpoints_svc.record_verdict(
        Path(verdicts_path),
        id=str(record["checkpoint_id"]),
        verdict="unverifiable",
        data_source="observation_script:repoint",
        reason=f"due={due} 不是交易日，已改点到 {new_due}",
        degradation={"kind": "nontrading_due", "old_due": due, "new_due": new_due, "new_checkpoint_id": ck["id"]},
    )
    new_record = {
        **record,
        "id": f"{record['id']}-rp{new_due.replace('-', '')}",
        "due": new_due,
        "checkpoint_id": str(ck["id"]),
        "repointed_from": {"id": record["id"], "due": due, "checkpoint_id": record["checkpoint_id"]},
    }
    # 改点是**修一个日期**，不是第二次确认。整行复制会把原确认的动作元数据一起复制，
    # 于是同一个 event_id / action_key 被投影两次，读起来像用户确认过两次
    # （质检 S7 实测），而且第二条还指着旧的 checkpoint_id。
    new_record.pop("action_event", None)
    p = Path(path).expanduser()
    with _ledger_lock(p):
        _append_line(p, new_record)
    return new_record


def register(
    path: str | Path,
    script: ObservationScript,
    *,
    checkpoints_path: str | Path | None = None,
    due: str | None = None,
    next_open: datetime | None = None,
    recorded_at: str | None = None,
    session_id: str | None = None,
    db_path: str | Path | None = None,
    user_authored: bool = False,
    author_origin: str | None = None,
    canonical_entity_id: str | None = None,
    attempt_id: str | None = None,
    entrypoint: str | None = None,
    source_draft_id: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    """登记剧本，返回 ``(path, record)``。硬门不过直接抛 ``ObservationScriptRejected``。

    只有 ``status=confirmed`` 且不 late 时才登记 checkpoint——草稿和跳过不该进回检队列，
    late 的不该进校准。登记成功后 ``checkpoint_id`` 回写进剧本记录，两条台账可互相追溯。

    ``user_authored``：剧本是用户在产品外手写的、没有对应的上下文投影。只有这样声明了，
    ``projection_hash`` 才允许为空（台账单列）；否则 agent 派生的剧本缺哈希是硬故障，
    ``register_checkpoint`` 会拒收（工单 #34）。

    ``entrypoint`` 给了（= 由受控入口调用）且最终状态是 ``confirmed`` / ``late`` 时，
    记录里带一份 ``script_confirmed`` 的动作元数据，事件由 ``projected_events`` 投影读出，
    **不再追加第二条成功事件行**（工单 #53 §2.4）。``late`` 仍算确认动作——它只是不进校准，
    不是「没确认」。``author_origin`` / ``attempt_id`` / ``source_draft_id`` 是来源声明，
    由受控入口写入；用户不能注入。
    """
    stamped = ObservationScript(
        **{
            **script.to_dict(),
            "entity_ids": script.entity_ids,
            "variables": script.variables,
            "upgrade_conditions": script.upgrade_conditions,
            "downgrade_or_abandon_conditions": script.downgrade_or_abandon_conditions,
            "evidence_refs": script.evidence_refs,
            "machine_conditions": script.machine_conditions,
            "recorded_at": recorded_at
            or script.recorded_at
            or datetime.now(CN_TZ).isoformat(timespec="seconds"),
        }
    )
    ensure_valid(stamped)

    status = stamped.status
    late = False
    if status == "confirmed":
        late = is_late(stamped, next_open=next_open)
        if late:
            status = "late"

    record_id = _make_id(stamped, str(stamped.recorded_at))
    # 能查日历就用真交易日，查不到才回落跳周末规则——节假日周末规则挡不住。
    due_norm = due or resolve_due(stamped.as_of, db_path=db_path)
    # 受控入口的确认动作要有**稳定身份**：键由内容 + 尝试算出，不含录入时刻。
    # 之前用 record_id 当判别位，而 record_id 派生自 recorded_at（秒级）——
    # 跨秒重试就换了一把键，于是「去重」在最需要它的场景（重试）恰好失效
    # （质检 S6 实测：两条同一确认，还多登记了一个可证伪点）。
    action_key = (
        _confirm_action_key(stamped, attempt_id=attempt_id, entrypoint=entrypoint)
        if entrypoint and status in {"confirmed", "late"}
        else None
    )

    p = Path(path).expanduser()
    with _ledger_lock(p):
        # 认领与去重必须在**产生 checkpoint 之前**：先登记再发现重复，
        # 回检队列里已经多了一条，删不掉也不该删（台账 append-only）。
        if action_key is not None:
            for existing in load_raw(p):
                if (
                    record_kind_of(existing) == RECORD_SCRIPT
                    and str((existing.get("action_event") or {}).get("action_key") or "") == action_key
                ):
                    return p, dict(existing)

        checkpoint_id: str | None = None
        if status == "confirmed":
            cpath = Path(checkpoints_path).expanduser() if checkpoints_path else None
            if cpath is None:
                raise ValueError("确认剧本必须给 checkpoints_path：确认即入回检队列，不留空转")
            _, ck = checkpoints_svc.register_checkpoint(
                cpath,
                claim=to_claim(stamped),
                due=due_norm,
                category=CHECKPOINT_CATEGORY,
                source=CHECKPOINT_SOURCE,
                themes=list(stamped.entity_ids),
                metric=build_metric(stamped, due=due_norm),
                framework_version=stamped.framework_version,
                object_type=OBJECT_TYPE,
                hindsight=stamped.hindsight,
                session_id=session_id,
                projection_hash=stamped.projection_hash,
                model_id=stamped.model_id,
                user_authored=user_authored,
            )
            checkpoint_id = str(ck["id"])

        record = stamped.to_dict()
        record.update(
            {
                "id": record_id,
                "status": status,
                "late": late,
                "due": due_norm,
                "checkpoint_id": checkpoint_id,
                "object_type": OBJECT_TYPE,
            }
        )
        if stamped.projection_hash is None and user_authored:
            record["projection_hash_missing"] = checkpoints_svc.USER_AUTHORED
        if author_origin:
            record["author_origin"] = str(author_origin)
        if canonical_entity_id:
            record["canonical_entity_id"] = str(canonical_entity_id)
        if attempt_id:
            record["extraction_attempt_id"] = str(attempt_id)
        if source_draft_id:
            record["source_draft_id"] = str(source_draft_id)
        if entrypoint:
            record["record_kind"] = RECORD_SCRIPT
            record["entrypoint"] = str(entrypoint)
            if action_key is not None:
                meta: dict[str, Any] = {
                    "event": EVENT_SCRIPT_CONFIRMED,
                    "event_id": _event_id(action_key),
                    "action_key": action_key,
                    "occurred_at": str(stamped.recorded_at),
                    "entrypoint": str(entrypoint),
                    "attempt_id": attempt_id,
                    "script_status": status,
                    "checkpoint_id": checkpoint_id,
                }
                if source_draft_id:
                    meta["source_draft_id"] = str(source_draft_id)
                record["action_event"] = meta
        _append_line(p, record)
    return p, record


def record_kind_of(rec: Mapping[str, Any] | None) -> str:
    """记录分型。**缺字段 = 剧本**（存量行没有这个字段），认不出的值归 ``unknown``。

    认不出就 fail closed：一条来自未来分型的记录既不进剧本分母、也不进事件查询，
    但它仍留在原始导出里——「看不懂」不等于「可以丢」。
    """
    kind = str((rec or {}).get("record_kind") or "").strip()
    if not kind:
        return RECORD_SCRIPT
    return kind if kind in RECORD_KINDS else RECORD_UNKNOWN


def load_raw(path: str | Path) -> list[dict[str, Any]]:
    """读取台账全部记录（含尝试与事件，保留顺序）。原始导出用这个。"""
    p = Path(path).expanduser()
    if not p.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict) and rec.get("id"):
            out.append(rec)
    return out


def load(path: str | Path) -> list[dict[str, Any]]:
    """读取**剧本**记录（保留顺序）。文件不存在返回空列表。

    过程事件与提取尝试不在其中：它们一旦混进来，``status_counts`` 的分母、
    ``expire_stale`` 的扫描面与回检队列都会跟着涨，而那三处量的都是「剧本」。
    """
    return [rec for rec in load_raw(path) if record_kind_of(rec) == RECORD_SCRIPT]


def load_attempts(path: str | Path) -> list[dict[str, Any]]:
    """读取提取尝试记录（append-only：同一 ``attempt_id`` 的最后一行是它的现状）。"""
    return [rec for rec in load_raw(path) if record_kind_of(rec) == RECORD_ATTEMPT]


def load_events(path: str | Path) -> list[dict[str, Any]]:
    """读取五业务事件：独立事件行 + 从成功剧本行投影出来的成功事件。"""
    return projected_events(load_raw(path))


def expire_stale(records: list[dict[str, Any]], *, today: str | None = None) -> list[dict[str, Any]]:
    """到期日已过却还停在 ``drafted`` 的剧本 → ``expired``（只算不写盘）。

    ``expired`` 与 ``skipped`` 必须分开：跳过是用户做了决定，过期是产品没接住他。
    合成一个状态，负担指标（spec §6.1「跳过率」）就测不出来了。
    """
    today = today or date_cls.today().isoformat()
    out: list[dict[str, Any]] = []
    for rec in records:
        if rec.get("status") == "drafted" and str(rec.get("due") or "") and str(rec["due"]) < today:
            rec = {**rec, "status": "expired"}
        out.append(rec)
    return out


def status_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    counts = {s: 0 for s in STATUSES}
    for rec in records:
        st = str(rec.get("status") or "")
        if st in counts:
            counts[st] += 1
    return counts


# --------------------------------------------------------------------------- #
# 提取前置：用户草稿 / 提取尝试 / 五业务事件（工单 #53 §2.1 / §2.4）
#
# 写入仍然只有本模块一个入口。并发认领（同键最多一个未结束尝试）、追加与去重
# 全在同一把锁里完成——让 CLI「先查再写」就是 check-then-act：两个进程同时看到
# 「还没有未结束尝试」，最后会各开一个。本仓已经在配额那里踩过同一个形状。
# --------------------------------------------------------------------------- #
@contextmanager
def _ledger_lock(path: Path) -> Iterator[None]:
    """台账互斥锁。锁在旁边的 ``.<name>.lock`` 上，不锁台账本身——

    锁文件与数据文件分开，读者永远不需要拿锁，也不会因为写者持锁而读到半截。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(f".{path.name}.lock")
    with lock_path.open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _append_line(path: Path, record: dict[str, Any]) -> None:
    """整行落盘 + flush + fsync，并先隔离上一次留下的半行。

    **半行不算成功**——断电留下半行 JSON，读者的 ``json.JSONDecodeError`` 分支会静默
    跳过它，于是「写过」和「没写过」在台账上长得一模一样。

    但只做到这一步还不够：残片**没有结尾换行**，下一次 append 会直接粘在它后面，
    于是连这次成功写入的记录一起变成不可解析的一行——一个断电吃掉两条记录，
    而第二条是 CLI 刚刚回报「已记下」的那条（质检 N2 实测）。``flock`` 只防同时写、
    ``fsync`` 只保证已写字节落盘，两者都不修残片。

    修法是**补一个换行把残片封口**，不是截断它：残片是「这里发生过一次未完成写入」
    的证据，抹掉它等于把事故现场清理干净。封口后残片仍是不可解析的一行（照旧被
    ``load_raw`` 跳过、被原始导出带走），新记录则是独立完整的一行。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    # 末字节检查走二进制：文本模式只能 seek 到 tell() 给过的位置，
    # 拿 tell()-1 去 seek 在多字节内容上是未定义行为。
    needs_newline = False
    if path.exists() and path.stat().st_size:
        with path.open("rb") as probe:
            probe.seek(-1, os.SEEK_END)
            needs_newline = probe.read(1) != b"\n"
    with path.open("a", encoding="utf-8") as fh:
        if needs_newline:
            fh.write("\n")
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def _now_iso() -> str:
    return datetime.now(CN_TZ).isoformat(timespec="seconds")


def _key_of(rec: Mapping[str, Any]) -> tuple[str, str, str, str]:
    """从一条记录还原它的关联键。

    ``scope`` **推导**而不是读字段：剧本行里的 ``scope`` 是用户填的正文字段，可能和
    身份推出来的不一致；读它会让同一个阅读目标的草稿与带读对不上。推导只有一处
    （``extraction.scope_for``），所以两侧不可能漂。
    """
    eid = str(rec.get("canonical_entity_id") or "")
    return (
        str(rec.get("user_id") or ""),
        str(rec.get("as_of") or ""),
        extraction.scope_for(eid),
        eid,
    )


def _action_key(event: str, attempt_id: str | None, discriminator: str = "") -> str:
    """同一动作的去重键。``attempt_id`` 为空时用 ``manual_confirm``——
    完整手填确认没有尝试，但它仍然需要一个稳定的去重标识。"""
    return "|".join([event, str(attempt_id or ENTRYPOINT_MANUAL_CONFIRM), discriminator])


def _event_id(action_key: str) -> str:
    return "oe-" + hashlib.sha1(action_key.encode("utf-8")).hexdigest()[:12]


def projected_events(raw: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """五业务事件的统一读取面：独立事件行 + 剧本行里的动作元数据投影。

    为什么成功事件不另写一行：保存剧本与追加事件是两次写，中间崩溃就会留下
    「剧本在、事件不在」的断裂，而那种断裂事后无法与「根本没提交」区分。
    把成功事件的元数据放进剧本行本身，一次写落地，读的时候投影出来——
    事件的存在与剧本的存在从此是同一个事实。

    **按 ``action_key`` 去重，首次出现胜出**（质检 S6 / S7）。台账是 append-only 的，
    同一个动作可能在多行里留下痕迹：改点会复制整行剧本、重试会再追加一次。
    「一次动作 = 一个事件」这条不变量必须在读取面上成立，不能只指望每个写入者都守规矩——
    写入侧的认领是第一道，这里是第二道，两道都要有。
    """
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for rec in raw:
        kind = record_kind_of(rec)
        if kind == RECORD_EVENT:
            akey = str(rec.get("action_key") or "")
            if akey and akey in seen:
                continue
            if akey:
                seen.add(akey)
            out.append(dict(rec))
            continue
        if kind != RECORD_SCRIPT:
            continue
        meta = rec.get("action_event")
        if not isinstance(meta, Mapping) or str(meta.get("event")) not in EVENTS:
            continue
        projected = {
            "record_kind": RECORD_EVENT,
            "event": str(meta.get("event")),
            "event_id": meta.get("event_id"),
            "user_id": rec.get("user_id"),
            "as_of": rec.get("as_of"),
            "canonical_entity_id": rec.get("canonical_entity_id"),
            "occurred_at": meta.get("occurred_at"),
            "entrypoint": meta.get("entrypoint"),
            "attempt_id": meta.get("attempt_id"),
            "action_key": meta.get("action_key"),
            "draft_id": rec.get("draft_id"),
            "script_id": rec.get("id"),
            "projected_from": rec.get("id"),
        }
        for extra_key in ("script_status", "checkpoint_id", "source_draft_id"):
            if extra_key in meta:
                projected[extra_key] = meta[extra_key]
        akey = str(meta.get("action_key") or "")
        if akey and akey in seen:
            continue
        if akey:
            seen.add(akey)
        out.append(projected)
    return out


def user_drafts(
    raw: Iterable[Mapping[str, Any]], *, key: extraction.ExtractionKey
) -> list[dict[str, Any]]:
    """该关联键下**用户自己提交的草稿**的全部版本，按提交先后。

    两道判据缺一不可：

    - ``author_origin == "user"``——不是 ``status == "drafted"``：系统骨架同样是 drafted，
      拿状态当判据就会把产品自己生成的东西当成用户作答；
    - ``action_event.event == draft_submitted``——**「用户作者」不等于「草稿提交动作」**。
      ``confirm --from-draft`` 写出的 confirmed 行作者也是 user，只看第一道判据它就会被
      选成「最新草稿」，而那一行根本没有 ``draft_id``：下游读收据里的来源关联随之丢失，
      再提交一版还会跳号（质检 S5 实测 version 从 2 跳到 3）。确认是确认，不是新草稿版。
    """
    target = key.as_tuple()
    return [
        dict(rec)
        for rec in raw
        if record_kind_of(rec) == RECORD_SCRIPT
        and str(rec.get("author_origin") or "") == AUTHOR_USER
        and str((rec.get("action_event") or {}).get("event") or "") == EVENT_DRAFT_SUBMITTED
        and _key_of(rec) == target
    ]


def draft_for_attempt(
    raw: Iterable[Mapping[str, Any]], *, key: extraction.ExtractionKey, attempt_id: str
) -> dict[str, Any] | None:
    """该尝试里提交的那一版草稿（同一尝试内多版取最后一版）。

    存在的理由是工单 §2.4.4「后续确认可关联**已完成尝试的具体草稿版本**」：
    一律取 latest 就没法回到「我当时确认的是哪一版」。
    """
    rows = [d for d in user_drafts(raw, key=key) if str(d.get("extraction_attempt_id") or "") == str(attempt_id)]
    return rows[-1] if rows else None


def latest_user_draft(
    raw: Iterable[Mapping[str, Any]], *, key: extraction.ExtractionKey
) -> dict[str, Any] | None:
    """同键最后一次成功提交的那一版。失败提交从未落盘，所以不会顶掉已有有效版。"""
    drafts = user_drafts(raw, key=key)
    return drafts[-1] if drafts else None


def keys_with_user_draft(raw: Iterable[Mapping[str, Any]]) -> set[tuple[str, str, str]]:
    """有用户草稿的全部阅读目标——列表 / JSON 的遮蔽判据。"""
    return {
        _key_of(rec)
        for rec in raw
        if record_kind_of(rec) == RECORD_SCRIPT
        and str(rec.get("author_origin") or "") == AUTHOR_USER
    }


def attempt_states(raw: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """``attempt_id -> 现状``。append-only 台账里同一 ID 的最后一行即现状。"""
    out: dict[str, dict[str, Any]] = {}
    for rec in raw:
        if record_kind_of(rec) != RECORD_ATTEMPT:
            continue
        aid = str(rec.get("attempt_id") or "")
        if aid:
            out[aid] = {**out.get(aid, {}), **dict(rec)}
    return out


def pending_attempt(
    raw: Iterable[Mapping[str, Any]], *, key: extraction.ExtractionKey
) -> dict[str, Any] | None:
    """同键那个尚未结束的尝试（最多一个）。"""
    target = key.as_tuple()
    for state in attempt_states(raw).values():
        if _key_of(state) == target and str(state.get("status")) == ATTEMPT_PENDING:
            return state
    return None


def open_attempt(
    path: str | Path,
    *,
    key: extraction.ExtractionKey,
    entrypoint: str,
    attempt_id: str | None = None,
    opened_at: str | None = None,
) -> tuple[dict[str, Any], bool]:
    """认领 / 创建提取尝试，返回 ``(尝试记录, 是否新建)``。

    显式传 ``attempt_id`` 是**续接**：ID 必须属于同一用户与同一阅读目标，否则抛
    ``ValueError``——跨用户续接会让一个人的动作记到另一个人名下。已结束的尝试不能
    复活：显式 close 之后要重新开始就得开新尝试，否则「用户明确离开」这个事实会被
    后来的动作抹掉。
    """
    p = Path(path).expanduser()
    with _ledger_lock(p):
        raw = load_raw(p)
        states = attempt_states(raw)
        if attempt_id:
            state = states.get(str(attempt_id))
            if state is None:
                raise ValueError(f"没有这个提取尝试：{attempt_id}")
            if _key_of(state) != key.as_tuple():
                raise ValueError(
                    f"提取尝试 {attempt_id} 不属于该用户 / 阅读目标"
                    f"（它是 {_key_of(state)}，你给的是 {key.as_tuple()}）"
                )
            if str(state.get("status")) != ATTEMPT_PENDING:
                raise ValueError(f"提取尝试 {attempt_id} 已结束，不能复活；要重新读取请开新尝试")
            return state, False
        existing = pending_attempt(raw, key=key)
        if existing is not None:
            return existing, False
        new_id = "oa-" + uuid.uuid4().hex[:12]
        record = {
            "record_kind": RECORD_ATTEMPT,
            "id": f"{new_id}#open",
            "attempt_id": new_id,
            "status": ATTEMPT_PENDING,
            "entrypoint": str(entrypoint),
            "opened_at": opened_at or _now_iso(),
            **key.to_dict(),
        }
        _append_line(p, record)
        return record, True


def close_attempt(
    path: str | Path,
    *,
    attempt_id: str,
    user_id: str,
    reason: str,
    entrypoint: str,
    occurred_at: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """结束一个提取尝试，返回 ``(关闭记录, abandoned 事件 | None)``。

    只有**从未提交 / 跳过 / 成功读取**的尝试才记 ``abandoned``；否则只关尝试、
    保留已发生的事件。read 提示后什么都没做就走开**不算 abandoned**——关掉终端
    没有任何可证明的结束信号，推断一个超时出来等于凭空造事实。
    """
    p = Path(path).expanduser()
    with _ledger_lock(p):
        raw = load_raw(p)
        state = attempt_states(raw).get(str(attempt_id))
        if state is None:
            raise ValueError(f"没有这个提取尝试：{attempt_id}")
        if str(state.get("user_id") or "") != str(user_id):
            raise ValueError(f"提取尝试 {attempt_id} 不属于用户 {user_id}")
        key = extraction.make_key(
            str(state.get("user_id") or ""),
            str(state.get("as_of") or ""),
            str(state.get("canonical_entity_id") or ""),
        )
        if str(state.get("status")) == ATTEMPT_CLOSED:
            # 已关闭 → 重试是**补齐**，不是空转。关闭行与 abandoned 事件是两次追加，
            # 第二次失败会留下「closed/abandoned=true，但事件查询恒空」的永久断裂
            # （质检 N3 实测）。关闭行自己记了 ``abandoned``，所以这里能判出该补哪一条；
            # ``_record_event_locked`` 按 action_key 去重，补齐是幂等的。
            if not state.get("abandoned"):
                return state, None
            return state, _record_event_locked(
                p,
                raw=raw,
                event=EVENT_ABANDONED,
                key=key,
                entrypoint=entrypoint,
                attempt_id=str(attempt_id),
                occurred_at=str(state.get("closed_at") or "") or occurred_at or _now_iso(),
            )[0]
        acted = any(
            str(ev.get("attempt_id") or "") == str(attempt_id)
            and str(ev.get("event"))
            in {EVENT_DRAFT_SUBMITTED, EVENT_DRAFT_SKIPPED, EVENT_READ_COMPLETED}
            for ev in projected_events(raw)
        )
        when = occurred_at or _now_iso()
        closed = {
            "record_kind": RECORD_ATTEMPT,
            "id": f"{attempt_id}#close",
            "attempt_id": str(attempt_id),
            "status": ATTEMPT_CLOSED,
            "entrypoint": str(entrypoint),
            "opened_at": state.get("opened_at"),
            "closed_at": when,
            "close_reason": str(reason),
            "abandoned": not acted,
            **key.to_dict(),
        }
        _append_line(p, closed)
        event = None
        if not acted:
            event = _record_event_locked(
                p,
                raw=[*raw, closed],
                event=EVENT_ABANDONED,
                key=key,
                entrypoint=entrypoint,
                attempt_id=str(attempt_id),
                occurred_at=when,
            )[0]
        return closed, event


def ensure_attempt_writable(
    raw: Iterable[Mapping[str, Any]], *, attempt_id: str, key: extraction.ExtractionKey
) -> dict[str, Any]:
    """持锁时复验尝试仍可写：存在、属于这个用户与阅读目标、且还没结束。

    为什么不能只在 CLI 入口查一次：``open_attempt`` 返回之后、真正落盘之前，
    另一条命令可以把这个尝试 close 掉。CLI 先查过**不等于**落盘时仍然有效——
    这就是 check-then-act，两个进程各自「查过了」，结果是关闭之后还能提交
    （质检 S9 实测：台账里同时有 closed、abandoned、draft_submitted 三条）。
    判定必须和追加在同一把锁里完成。
    """
    state = attempt_states(raw).get(str(attempt_id))
    if state is None:
        raise ValueError(f"没有这个提取尝试：{attempt_id}")
    if _key_of(state) != key.as_tuple():
        raise ValueError(
            f"提取尝试 {attempt_id} 不属于该用户 / 阅读目标"
            f"（它是 {_key_of(state)}，你给的是 {key.as_tuple()}）"
        )
    if str(state.get("status")) != ATTEMPT_PENDING:
        raise ValueError(f"提取尝试 {attempt_id} 已结束，不能再往里写")
    return state


def _record_event_locked(
    path: Path,
    *,
    raw: list[dict[str, Any]],
    event: str,
    key: extraction.ExtractionKey,
    entrypoint: str,
    attempt_id: str | None,
    discriminator: str = "",
    extra: Mapping[str, Any] | None = None,
    occurred_at: str | None = None,
) -> tuple[dict[str, Any], bool]:
    """已持锁时追加一条独立事件行；同动作重试直接返回原事件。"""
    if event not in EVENTS:
        raise ValueError(f"未知业务事件：{event!r}（只有 {EVENTS}）")
    action_key = _action_key(event, attempt_id, discriminator)
    for existing in projected_events(raw):
        if str(existing.get("action_key") or "") == action_key:
            return dict(existing), False
    record = {
        "record_kind": RECORD_EVENT,
        "id": _event_id(action_key),
        "event_id": _event_id(action_key),
        "event": event,
        "occurred_at": occurred_at or _now_iso(),
        "entrypoint": str(entrypoint),
        "attempt_id": attempt_id,
        "action_key": action_key,
        **key.to_dict(),
        **dict(extra or {}),
    }
    _append_line(path, record)
    return record, True


def record_event(
    path: str | Path,
    *,
    event: str,
    key: extraction.ExtractionKey,
    entrypoint: str,
    attempt_id: str | None,
    discriminator: str = "",
    extra: Mapping[str, Any] | None = None,
    occurred_at: str | None = None,
) -> tuple[dict[str, Any], bool]:
    """追加一条独立业务事件，返回 ``(事件, 是否新建)``。

    ``draft_submitted`` / ``script_confirmed`` **不走这里**——它们随成功剧本行
    一起落盘（见 ``projected_events``）。

    带 ``attempt_id`` 的提取内动作在同一把锁里复验尝试仍可写（见
    ``ensure_attempt_writable``）：已关闭的尝试不能再往里记跳过或完成。
    ``abandoned`` 由 ``close_attempt`` 内部走 ``_record_event_locked``，不经这道复验——
    它正是在关闭那一刻写的。
    """
    p = Path(path).expanduser()
    with _ledger_lock(p):
        raw = load_raw(p)
        if attempt_id:
            ensure_attempt_writable(raw, attempt_id=str(attempt_id), key=key)
        return _record_event_locked(
            p,
            raw=raw,
            event=event,
            key=key,
            entrypoint=entrypoint,
            attempt_id=attempt_id,
            discriminator=discriminator,
            extra=extra,
            occurred_at=occurred_at,
        )


def find_event(
    raw: Iterable[Mapping[str, Any]], *, event: str, attempt_id: str
) -> dict[str, Any] | None:
    """某个尝试下某类事件的第一条（成功收据的重放依据）。"""
    for ev in projected_events(raw):
        if str(ev.get("event")) == event and str(ev.get("attempt_id") or "") == str(attempt_id):
            return dict(ev)
    return None


def _draft_content_hash(script: ObservationScript, key: extraction.ExtractionKey) -> str:
    payload = json.dumps(
        {
            "key": key.as_tuple(),
            "scope": script.scope,
            "entity_ids": list(extraction.normalize_values(script.entity_ids)),
            **{
                f: list(extraction.normalize_values(getattr(script, f)))
                for f in extraction.DIFF_FIELDS
            },
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def submit_draft(
    path: str | Path,
    script: ObservationScript,
    *,
    key: extraction.ExtractionKey,
    attempt_id: str,
    entrypoint: str,
    submitted_at: str | None = None,
) -> tuple[dict[str, Any], bool]:
    """提交一版**用户自己写的**观察剧本草稿，返回 ``(记录, 是否新版)``。

    先过同一道结构 + 合规硬门再落盘：被拒的提交什么都不写，已有的有效版本不受影响。
    保存草稿**不生成系统骨架、不登记 checkpoint**——草稿只是用户的答卷。

    同一个尝试里重跑同一条命令是重试（内容哈希相同 → 同一个动作键 → 返回原记录）；
    内容改了、或换了新尝试再提交，都是**新版本**：旧版保留，``latest_user_draft``
    取最后一版。作者来源与尝试 ID 由本函数写入，不接受调用方注入。
    """
    stamped = ObservationScript(
        **{
            **script.to_dict(),
            "entity_ids": script.entity_ids,
            "variables": script.variables,
            "upgrade_conditions": script.upgrade_conditions,
            "downgrade_or_abandon_conditions": script.downgrade_or_abandon_conditions,
            "evidence_refs": script.evidence_refs,
            "machine_conditions": script.machine_conditions,
            "user_id": key.user_id,
            "as_of": key.as_of,
            "status": "drafted",
            "recorded_at": submitted_at or script.recorded_at or _now_iso(),
        }
    )
    ensure_valid(stamped)

    content_hash = _draft_content_hash(stamped, key)
    action_key = _action_key(EVENT_DRAFT_SUBMITTED, attempt_id, content_hash)
    p = Path(path).expanduser()
    with _ledger_lock(p):
        raw = load_raw(p)
        for existing in raw:
            if (
                record_kind_of(existing) == RECORD_SCRIPT
                and str((existing.get("action_event") or {}).get("action_key") or "") == action_key
            ):
                return dict(existing), False
        # 复验放在**去重之后、追加之前**：同一条命令重跑该拿回原记录（幂等），
        # 但尝试一旦被 close 掉就不能再往里塞新版本（质检 S9）。
        ensure_attempt_writable(raw, attempt_id=str(attempt_id), key=key)
        seq = len(user_drafts(raw, key=key)) + 1
        when = str(stamped.recorded_at)
        draft_id = f"od-{key.as_of}-{seq:03d}-{content_hash[:8]}"
        record = stamped.to_dict()
        record.update(
            {
                "record_kind": RECORD_SCRIPT,
                "id": draft_id,
                "draft_id": draft_id,
                "draft_version": seq,
                "author_origin": AUTHOR_USER,
                "canonical_entity_id": key.canonical_entity_id,
                "extraction_attempt_id": attempt_id,
                "entrypoint": str(entrypoint),
                "submitted_at": when,
                "status": "drafted",
                "late": False,
                "due": resolve_due_safe(key.as_of),
                "checkpoint_id": None,
                "object_type": OBJECT_TYPE,
                "action_event": {
                    "event": EVENT_DRAFT_SUBMITTED,
                    "event_id": _event_id(action_key),
                    "action_key": action_key,
                    "occurred_at": when,
                    "entrypoint": str(entrypoint),
                    "attempt_id": attempt_id,
                },
            }
        )
        _append_line(p, record)
        return record, True


def resolve_due_safe(as_of: str) -> str:
    """草稿的到期日只用跳周末规则：草稿不进回检队列，没必要为它开库查日历。

    确认时 ``register`` 会重新按交易日历定 due——那一刻才真的要进队列。
    """
    try:
        return default_due(as_of)
    except ValueError:  # pragma: no cover - as_of 已过 validate，这里是兜底
        return as_of
