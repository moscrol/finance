"""提取前置（工单 #53 P0）：入口先取用户自己的观察剧本，再展示字段差异。

设计依据 ``~/foresight/docs/specs/2026-09-13-extraction-first-spec.md`` rev.4；
执行合同是工单 ``docs/superpowers/specs/2026-09-14-extraction-first-p0-workorder.md``。

## 这个模块只负责判定，不负责写盘

单一职责：**关联键与身份解析、提取门的顺序判定、字段差异、系统骨架引用哈希**。
四件事全是纯函数（``resolve_identity`` 只读一次库解析身份，不写盘、不生成带读）。

台账写入仍然只有 ``observation_script.py`` 一个写入者——门与写入分开，是为了让
「同一份顺序门被 CLI 与日报共用」这条验收可以直接单测：门是纯函数，喂什么进去
出什么来，不需要临时目录、不需要真库。

## 为什么顺序是「草稿 → 跳过 → 提示」而不是别的顺序

终局闭环原本是「系统生成带读 → 用户确认 / 修改 / 跳过」，用户先看到答案再表态，
留下的主要是对系统的认可。本单把提取放到披露之前：**先收用户自己写的观察剧本，
再展示字段差异**。差异只用于让用户指出遗漏与分歧，**不代表系统更正确**——所以本
模块里没有任何评分、相似度或收敛指标，只有「你写了、系统未列 / 系统列了、你未写」。

判定顺序里两处是刻意的：

1. **带读显式关闭排在最前**：关掉带读时连提取尝试都不该创建，否则「关掉后逐字节
   不变」这条既有验收会被本单的记录动作破坏。
2. **已有草稿优先于显式跳过**：用户既写了草稿又带了 ``--skip-draft`` 时用草稿，
   不重复记一条跳过——跳过率是负担指标，记虚了就测不出真实负担。
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

# 参与差异比较的业务字段。ID / 状态 / 时间 / 用户 / 证据引用 / 投影等元数据**不比较**：
# 它们两边天然不同，比进来就会让「无差异」永远不成立，用户每天看到一堆噪声。
DIFF_FIELDS: tuple[str, ...] = (
    "variables",
    "upgrade_conditions",
    "downgrade_or_abandon_conditions",
    "machine_conditions",
)

FIELD_LABELS: dict[str, str] = {
    "variables": "变量",
    "upgrade_conditions": "升级条件",
    "downgrade_or_abandon_conditions": "降级或放弃条件",
    "machine_conditions": "机检条件",
}

# 判定结果码（机器可判，写进 JSON 与测试断言）
ALLOW_DRAFT = "ALLOW_DRAFT"
ALLOW_SKIP = "ALLOW_SKIP"
BLOCK_GUIDED_READING_OFF = "GUIDED_READING_OFF"
BLOCK_DRAFT_REQUIRED = "E_DRAFT_REQUIRED"

DRAFT_REQUIRED_PROMPT = (
    "先写下你自己今天要看什么，再看系统的带读。"
    "提交：observation draft --as-of <日期> --entity <板块/题材> --variable ... --abandon ...；"
    "确实不想写就显式跳过：加 --skip-draft（跳过是有效行为，不计失败）"
)

# 系统骨架正文被遮蔽时的占位。遮蔽的是**正文**，不是这行记录的存在——
# 「有这么一条但你还没作答所以不给看」比「装作没有」诚实。
REDACTED = "（尚无提取资格，系统骨架正文未回显）"


class IdentityUnresolved(ValueError):
    """实体身份解析不出来。不猜、不模糊匹配——猜错会静默串轨，比读不出来更糟。"""


def scope_for(entity_id: str) -> str:
    """实体身份 → 作用域。**两侧共用这一个推导**，不许各推各的。

    关联键里的 scope 必须是**从身份推出来的**，不能取用户在 ``--scope`` 里填的那个：
    用户填 ``index``、系统按 id 推出 ``theme``，同一个阅读目标就会裂成两个键，
    于是「你昨天写的草稿」在今天的带读面前凭空消失。剧本正文里的 scope 仍然是用户
    填的那个（并受同一道硬门校验），两者互不干扰。
    """
    eid = str(entity_id or "").strip()
    return "index" if eid.upper().startswith("SH0") or eid in {"上证指数", "全市场"} else "theme"


@dataclass(frozen=True)
class ExtractionKey:
    """关联键：一个用户、一个所读交易日、一个作用域、一个实体身份（工单 §2.1）。

    ``as_of`` 是**所读交易日**而不是提交时刻的日期——用户可以在周六补做周五的功课，
    按提交日算会把它记成另一个阅读目标。
    """

    user_id: str
    as_of: str
    scope: str
    canonical_entity_id: str

    def as_tuple(self) -> tuple[str, str, str, str]:
        return (self.user_id, self.as_of, self.scope, self.canonical_entity_id)

    def to_dict(self) -> dict[str, str]:
        # 键里的 scope 单列成 ``extraction_scope``：剧本行本来就有一个 ``scope``
        # （用户填的正文字段），同名会让两个含义不同的东西长得一样。
        return {
            "user_id": self.user_id,
            "as_of": self.as_of,
            "extraction_scope": self.scope,
            "canonical_entity_id": self.canonical_entity_id,
        }


def make_key(user_id: str, as_of: str, canonical_entity_id: str) -> ExtractionKey:
    eid = str(canonical_entity_id or "").strip()
    return ExtractionKey(
        user_id=str(user_id or "").strip(),
        as_of=str(as_of or "").strip()[:10],
        scope=scope_for(eid),
        canonical_entity_id=eid,
    )


# --------------------------------------------------------------------------- #
# 身份：复用 River 现有解析，只解析身份、不生成带读
# --------------------------------------------------------------------------- #
def resolve_identity(as_of: str, entity: str, *, db_path: str | Path | None = None) -> str:
    """实体名 / 代码 → 跨供应商稳定的 ``canonical_id``。解析不出抛 ``IdentityUnresolved``。

    为什么不能拿用户输入的名字当身份键：2026 年换过一次板块数据供应商
    （``.TI`` → ``.FP``），同一个板块在换源前后是两个代码，而每个板块的切换日各不
    相同。拿名字或当日代码当键，同一个阅读目标会在换源日悄悄裂成两个，
    「你昨天写的草稿」就再也对不上今天的带读。

    ``import duckdb`` 与 ``river`` 都放在函数里：本模块导入期只依赖标准库，
    顺序门与差异这两件事可以完全离线单测。
    """
    import duckdb

    from intelligence.services import river

    db = Path(db_path or os.environ.get("MARKET_FEATURE_STORE_DB", river.DEFAULT_DB)).expanduser()
    if not db.exists():
        raise IdentityUnresolved(f"数据库不存在：{db}（身份解析不猜，也不自动创建）")
    con = duckdb.connect(str(db), read_only=True)
    try:
        ref = river.resolve_entity(con, str(as_of)[:10], str(entity))
    finally:
        con.close()
    if ref is None:
        raise IdentityUnresolved(
            f"{as_of} 的板块宇宙里没有「{entity}」（只做精确匹配，不做模糊匹配）"
        )
    return str(ref.canonical_id)


def identity_from_slice(slice_dict: Mapping[str, Any] | None) -> str | None:
    """从已取到的切片里读身份，省掉第二次开库。解析失败的切片返回 ``None``。

    切片在实体解析不出来时会把 ``entity_id`` 原样填成用户的输入、六轨全部标
    ``entity_unresolved``。那种情况下 ``entity_id`` 是**输入别名不是身份**，
    直接拿去当关联键就等于让「算力租赁」和「990306.FP」变成两个阅读目标。
    """
    tracks = (slice_dict or {}).get("tracks") or {}
    if tracks and all(
        isinstance(v, Mapping) and v.get("gap") and str(v.get("reason")) == "entity_unresolved"
        for v in tracks.values()
    ):
        return None
    eid = str((slice_dict or {}).get("entity_id") or "").strip()
    return eid or None


# --------------------------------------------------------------------------- #
# 顺序门：一份判定，CLI 与日报共用
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Decision:
    """一次提取资格判定。``draft`` 是被选中的那一版用户草稿记录（放行时才有）。"""

    allowed: bool
    code: str
    reason: str
    draft: dict[str, Any] | None = None
    # 放行前必须先记一条 ``draft_skipped``。判定本身不写盘，由调用方按这个标志去写——
    # 「先记后生成骨架」的顺序不能靠调用方自觉，所以标志从判定里带出来。
    needs_skip_event: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "code": self.code,
            "reason": self.reason,
            "draft_id": (self.draft or {}).get("draft_id"),
        }


def decide(
    *,
    enabled: bool,
    enabled_reason: str,
    draft: Mapping[str, Any] | None,
    skip_draft: bool,
) -> Decision:
    """提取门。**纯函数**：不读盘、不写盘、不看环境变量。

    四种结果对应工单 §2.2 那张表，顺序不可交换（理由见模块 docstring）。
    """
    if not enabled:
        return Decision(False, BLOCK_GUIDED_READING_OFF, enabled_reason)
    if draft:
        return Decision(True, ALLOW_DRAFT, "已有你自己写的观察剧本", draft=dict(draft))
    if skip_draft:
        return Decision(True, ALLOW_SKIP, "你显式跳过了本次提取", needs_skip_event=True)
    return Decision(False, BLOCK_DRAFT_REQUIRED, DRAFT_REQUIRED_PROMPT)


# --------------------------------------------------------------------------- #
# 差异：只列字段差异，不评分
# --------------------------------------------------------------------------- #
def normalize_values(values: Any) -> tuple[str, ...]:
    """去首尾空白、去空、去重、**忽略顺序**（稳定排序）。

    忽略顺序是刻意的：用户先写放弃条件再写变量，与系统的排列顺序不同，这不是分歧。
    """
    out: list[str] = []
    for v in values or []:
        s = str(v).strip()
        if s and s not in out:
            out.append(s)
    return tuple(sorted(out))


@dataclass(frozen=True)
class FieldDiff:
    field: str
    label: str
    user_only: tuple[str, ...]
    system_only: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "label": self.label,
            "user_only": list(self.user_only),
            "system_only": list(self.system_only),
        }


def diff_scripts(
    user_draft: Mapping[str, Any] | None, system_script: Mapping[str, Any] | None
) -> list[dict[str, Any]]:
    """用户草稿 × 本次实际交付的系统骨架 → 字段差异清单。

    全部一致返回 ``[]``（可显示中性的「所比较字段无差异」）。任一侧缺失返回 ``[]``，
    由渲染层说明「本次无可比较剧本」——**不能把「没得比」显示成「完全一致」**。

    只做集合差，不做语义相似度、不调模型：差异是给用户看「我漏了什么」的线索，
    不是判用户答错。相似度一旦进来，下一步必然有人拿它算收敛率，而收敛率奖励迎合。
    """
    if not user_draft or not system_script:
        return []
    out: list[dict[str, Any]] = []
    for field in DIFF_FIELDS:
        mine = normalize_values(user_draft.get(field))
        theirs = normalize_values(system_script.get(field))
        if mine == theirs:
            continue
        out.append(
            FieldDiff(
                field=field,
                label=FIELD_LABELS.get(field, field),
                user_only=tuple(v for v in mine if v not in theirs),
                system_only=tuple(v for v in theirs if v not in mine),
            ).to_dict()
        )
    return out


def render_diff(diff: list[dict[str, Any]], *, comparable: bool) -> list[str]:
    """差异 → 可读行。不带任何评分词，也不说谁对谁错。"""
    if not comparable:
        return ["- 本次无可比较剧本（系统这一天没有骨架），不代表两边一致。"]
    if not diff:
        return ["- 所比较字段无差异。"]
    lines: list[str] = []
    for item in diff:
        label = item.get("label") or item.get("field")
        for v in item.get("user_only") or []:
            lines.append(f"- {label}：你写了「{v}」，系统未列")
        for v in item.get("system_only") or []:
            lines.append(f"- {label}：系统列了「{v}」，你未写")
    return lines


def system_script_ref(
    system_script: Mapping[str, Any] | None, *, key: ExtractionKey
) -> str | None:
    """本次实际交付的系统骨架的稳定内容引用。

    骨架是构建出来的、**没有持久化 ID**（``drafted`` 骨架不落盘，落盘就等于产品替
    用户先答了）。所以收据里存的是内容哈希而不是 script_id：它能回答「这次比较的
    是哪一份骨架」，**不承诺能靠哈希把正文恢复回来**——P0 不为此新建带读快照。

    投影哈希与 knowledge_cutoff 一起进哈希：同一批业务字段在不同投影下是不同的
    交付物，混成一个 ref 会让「当时看到的材料」这条线断掉。
    """
    if not system_script:
        return None
    payload = json.dumps(
        {
            "key": key.as_tuple(),
            "scope": str(system_script.get("scope") or ""),
            "entity_ids": list(normalize_values(system_script.get("entity_ids"))),
            **{f: list(normalize_values(system_script.get(f))) for f in DIFF_FIELDS},
            "projection_hash": system_script.get("projection_hash"),
            "knowledge_cutoff": system_script.get("knowledge_cutoff"),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return "sys:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------------------------- #
# 出口：列表 / JSON 不得绕过门回显系统骨架正文
# --------------------------------------------------------------------------- #
def redact_system_skeletons(
    records: Iterable[Mapping[str, Any]], *, keys_with_draft: set[tuple[str, str, str]]
) -> list[dict[str, Any]]:
    """遮蔽「系统作者 + 仍是草稿 + 该阅读目标尚无用户草稿」那些行的业务正文。

    本仓现有写入路径不产出这种行（``skip`` 写 skipped、``confirm`` 写 confirmed，
    两者都已过门）。这一层是**纵深防御**：台账是 append-only 的纯文本，将来任何一个
    新入口只要往里写一条系统骨架草稿，列表就会把它当历史记录直接回显出去，
    而那正是本单要堵的口子。没有作者来源标记的存量行不在此列（工单 §2.3「旧记录仍可查」）。
    """
    out: list[dict[str, Any]] = []
    for rec in records:
        row = dict(rec)
        eid = str(row.get("canonical_entity_id") or "")
        if (
            str(row.get("author_origin") or "") == "system"
            and str(row.get("status") or "") == "drafted"
            and (str(row.get("user_id") or ""), str(row.get("as_of") or ""), scope_for(eid), eid)
            not in keys_with_draft
        ):
            for field in (*DIFF_FIELDS, "scope_note"):
                if field in row:
                    row[field] = [REDACTED] if isinstance(row[field], list) else REDACTED
            row["redacted"] = True
        out.append(row)
    return out
