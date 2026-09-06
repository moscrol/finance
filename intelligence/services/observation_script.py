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

本模块只用标准库：可离线跑、可独立单测，与 ``checkpoints.py`` 同规格。
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import date as date_cls, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from intelligence.services import checkpoints as checkpoints_svc
from intelligence.services import compliance_gate

# 剧本作用域：只到指数 / 板块 / 题材。个股不在其列——这是产品定位红线，不是配置项。
SCOPES = ("index", "sector", "theme")
VISIBILITIES = ("private", "shared_candidate", "shared")
STATUSES = ("drafted", "confirmed", "skipped", "late", "expired")

# 判断轨对象分三类（roadmap §13.2 F2）；观察剧本是其中一类，写进 checkpoint 记录，
# 供 G-09 的胜率面板按对象类型分列——三类混算会让「用户决策」的胜率被系统草稿稀释。
OBJECT_TYPE = "observation_script"
CHECKPOINT_CATEGORY = "observation_script"
CHECKPOINT_SOURCE = "observation_script"

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
    """能不能进方法校准：只有**及时确认**的剧本算数。

    ``skipped`` 不是失败（spec §3.1「跳过本身是有效行为」），但它也不是判断，
    所以同样不进分母——把跳过记成落空，会把「今天没看法」惩罚成「今天看错了」。
    """
    return str(record.get("status")) == "confirmed"


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
    读数上像「判不了」，其实是「问错了日子」。
    """
    return default_next_open(as_of).date().isoformat()


def register(
    path: str | Path,
    script: ObservationScript,
    *,
    checkpoints_path: str | Path | None = None,
    due: str | None = None,
    next_open: datetime | None = None,
    recorded_at: str | None = None,
    session_id: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    """登记剧本，返回 ``(path, record)``。硬门不过直接抛 ``ObservationScriptRejected``。

    只有 ``status=confirmed`` 且不 late 时才登记 checkpoint——草稿和跳过不该进回检队列，
    late 的不该进校准。登记成功后 ``checkpoint_id`` 回写进剧本记录，两条台账可互相追溯。
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
    checkpoint_id: str | None = None
    due_norm = due or default_due(stamped.as_of)

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
            session_id=session_id,
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
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return p, record


def load(path: str | Path) -> list[dict[str, Any]]:
    """读取全部剧本记录（保留顺序）。文件不存在返回空列表。"""
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
