"""题材跟踪表达契约（slice 4）：delta-only + 观点四态对照 + 结论 TTL + 下期关注。

背景（knevo q8 蒸馏的回灌）：
    knevo finance-industry-track 的核心是「上期基线为锚，只报变化」的 delta-only
    跟踪契约：观点四态对照（支持/削弱/无变化/信息不足）、观点有效期（TTL）、
    「下期关注 + 触发条件」作为下一轮输入形成自衔接链。本仓的 theme_track 路由
    已有检索与模板，但输出没有这三件纪律——跟踪题容易被答成一次性全景重跑。

设计（沿 scenario_tree 的表达层模式，零取数）：
    - 这是**表达层模板**（注入 synthesis prompt 的格式契约），不是数据块：
      不新增证据、不改证据链，只约束输出组织方式。
    - **确定性意图路由**：问题类型为 theme_track，或命中「跟踪/近况/新变化/
      自上次」类词面才注入；普通问答不注入，行为不变。
    - 四态对照的「上期结论」来源是 [M]（用户记忆）与 [V]（回检）块——没有
      相关记录时必须显式声明「无上期基线，本期建立基线」，禁止虚构上期结论。
"""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import re

# 跟踪类词面：持续性 + 增量性表述。刻意不收「最近怎么样」这类泛化问法——
# 它们既可能是跟踪也可能是首次全景，由 route/question_type 判定兜底。
_TRACK_TERMS = (
    "跟踪",
    "追踪",
    "近况",
    "新变化",
    "有什么变化",
    "最新进展",
    "进展如何",
    "自上次",
    "上次之后",
    "相比上次",
    "更新一下",
    "有没有新",
)


# 明确拒绝登记的表述。要同时满足三件事才算数：否定词 + 登记类动词 + 跟踪类宾语。
# 只认「不」+「跟踪」会把「排产不及预期，跟踪一下」误判成退出；三件套是为了高精度，
# 宁可漏一句奇怪写法，也不能把用户真正想要的跟踪静默关掉。
# 逗号不进间隔字符集：否定词和登记动词必须在同一个小句里，跨句不算。
# 否定词前面不能是「要 / 需 / 用」：「要不要登记」「需不需要纳入」是提问，不是拒绝。
_OPT_OUT_NEGATION = (
    r"(?<![要需用])(?:不需要|不要|不用|无需|无须|不必|不得|请勿|禁止|别|勿|"
    r"不(?=[登记录建入存写纳做作列设]))"
)
_OPT_OUT_VERB = r"(?:登记|记录|记进|建档|建立|入库|存档|写入|写进|加进|纳入|列为|设为|做|作为)"
_OPT_OUT_OBJECT = (
    r"(?:长期|持续)?(?:跟踪|追踪|回检|复核|观察项|关注清单|checkpoint)"
    r"(?:观察项|清单|记录|任务)?"
)
# 按小句扫描词元，不用多个无限 GAP 做回溯：长宾语不能截断，重复「登记」也不能
# 让一次漏判变成二次方扫描。换行是边界。限定语必须修饰否定/登记动作，不能因
# 宾语里有「一百只」「遗漏指标」「仅供参考」就把明确的拒绝登记取消。
_OPT_OUT_TOKENS = re.compile(
    rf"(?P<negation>{_OPT_OUT_NEGATION})|(?P<verb>{_OPT_OUT_VERB})"
    rf"|(?P<object>{_OPT_OUT_OBJECT})"
    r"|(?P<qualifier>忘记|忘了|遗忘|遗漏|漏掉|忘|漏|仅仅|仅|只)"
)
_PREPOSED_OBJECT_TAIL = re.compile(r"(?:项|观察项|清单|记录|任务)?(?:本次|这次|此次)?")
_QUALIFIER_LINK = re.compile(r"(?:再三|再|又|也|还|千万)*")
_REMINDER_BEFORE_ACTION = re.compile(rf"(?:了)?{_OPT_OUT_VERB}")
_POSTPOSED_REMINDER = re.compile(
    r"(?:的时候|时|过程中)(?:再|又|也)?(?:忘记|忘了|遗忘|遗漏|漏掉|忘|漏)"
)


def _opt_out_spans(text: str) -> tuple[tuple[int, int], ...]:
    spans: list[tuple[int, int]] = []
    for clause in re.finditer(r"[^，,。；;!！?？\r\n]+", text):
        body = clause.group()
        start: int | None = None
        qualifier_position = -1
        has_verb = has_object = False
        previous_object: re.Match[str] | None = None
        for token in _OPT_OUT_TOKENS.finditer(body):
            kind = token.lastgroup
            if kind == "negation":
                # 「长期跟踪不用登记」的前置对象只认紧邻形态，不能吞掉前面的
                # 「跟踪一下中际旭创但……」正面研究诉求。
                has_object = bool(previous_object and _PREPOSED_OBJECT_TAIL.fullmatch(
                    body[previous_object.end():token.start()]
                ))
                start = previous_object.start() if has_object else token.start()
                # 每个否定只扫一次副词前缀。若对每个「只」重扫长串「再……」，
                # 正确的量词判定也会退化为重复的二次方工作。
                link = _QUALIFIER_LINK.match(body, token.end())
                qualifier_position = link.end() if link is not None else token.end()
                has_verb = False
            elif kind == "qualifier":
                modifies_negation = token.start() == qualifier_position
                modifies_action = (
                    token.group() not in {"仅仅", "仅", "只"}
                    and _REMINDER_BEFORE_ACTION.match(body, token.end())
                )
                if start is not None and (modifies_negation or modifies_action):
                    start = None  # 别忘/请勿遗漏/不要只：不是退出持久化
                    previous_object = None
            elif kind == "object":
                previous_object = token
                has_object = True
            elif kind == "verb":
                has_verb = True
            if start is not None and has_verb and has_object:
                # 「不要登记为跟踪时漏掉到期日」是在提醒登记细节，不是取消登记。
                if not _POSTPOSED_REMINDER.match(body, token.end()):
                    spans.append((clause.start() + start, clause.start() + token.end()))
                start = None
                previous_object = None
    return tuple(spans)


def persistence_opt_out(query: str) -> bool:
    """用户是否明确说了「本次不要登记为长期跟踪」。

    这是**写入前**的闸门，不是答案里的口头承诺。R-20260916-05 的真实会话里，
    题面写明「不登记长期跟踪」、答案也照抄了这句，运行时仍往用户目录写了 4 条
    checkpoint——因为承诺在文本层，写入在运行时层，两层根本没连上。边界只能由
    调用方在写之前判断，所以判据取**用户问题**，不取模型答案（模型说了不算）。
    """

    text = re.sub(r"[^\S\r\n]+", "", str(query or ""))
    if not text:
        return False
    return bool(_opt_out_spans(text))


def parse_track_intent(query: str, question_type: str | None = None) -> bool:
    """问题类型为 theme_track，或命中跟踪/增量词面即触发。

    否定句里的「跟踪」不算跟踪意图：「不登记长期跟踪」整句被抠掉后再匹配词面，
    避免一句明确的退出声明反而把跟踪契约打开（词面匹配的经典反噬）。句子里另有
    正面跟踪诉求时（「跟踪一下液冷，但别登记为长期跟踪」）仍然路由，只是后面
    不落盘——表达纪律和持久化是两件事，别合成一个开关。
    """
    if question_type == "theme_track":
        return True
    text = re.sub(r"[^\S\r\n]+", "", str(query or ""))
    if not text:
        return False
    spans = _opt_out_spans(text)
    kept: list[str] = []
    cursor = 0
    for start, end in spans:
        kept.append(text[cursor:start])
        cursor = end
    kept.append(text[cursor:])
    scrubbed = "".join(kept)
    return any(term in scrubbed for term in _TRACK_TERMS)


def build_track_guidance() -> str:
    """跟踪表达契约（注入 synthesis prompt；确定性文本，无取数）。"""
    return "\n".join(
        [
            "## 跟踪表达契约（本题为持续跟踪类问题，回答必须按此结构组织）",
            "1. **delta-only 纪律**：以上期基线为锚只报有信息量的变化；上期结论仍成立的项"
            "写一句「无变化」即可，禁止重跑全景模板凑字数。上期基线取 [M]（用户既有判断）与"
            " [V]（回检记录）块；两块都无相关记录时，开头显式声明「无上期基线，本期建立基线」，"
            "禁止虚构或臆测上期说过什么。",
            "2. **观点四态对照**：对 [M]/[V] 中每条相关既有判断给显式判定——"
            "「支持 / 削弱 / 无变化 / 信息不足」四态之一，判定后必须紧跟本轮证据编号"
            "（如 [D0]/[D6]/[W7]/[L1-x]）；没有证据支撑的判定只能写「信息不足」。",
            "3. **结论 TTL**：本期每条新结论标注有效期「复核期限：YYYY-MM-DD」——"
            "跟踪级结论默认 30 天、框架级结论默认 90 天；到期未复核视为待复核，"
            "不得在后续轮次当作已验证事实引用。",
            "4. **下期关注清单**（结尾必给）：每项 = 指标/事件 + 时间节点 + 触发条件"
            "（可观察、可证伪，如「若 X 月中报毛利率 <Y% 则削弱扩产逻辑」），"
            "作为下一轮跟踪开头的强制对照输入；禁止「持续关注市场情绪」这类不可证伪表述。",
            "5. 数据缺口照常显式声明；跟踪不改变证据纪律——变化必须来自本轮检索块，"
            "不得由「距上次隔了很久」推断「肯定有变化」。",
        ]
    )


def build_track_guidance_for_episode() -> str:
    """episode 主路径版跟踪契约——纪律同 :func:`build_track_guidance`，术语换血。

    legacy 版的「上期基线」指向 [M]/[V] 检索块、证据引用用 [D0]/[W7] 编号——
    这些是 ask_synthesis 路径的记号，episode 里不存在：episode 的记忆通道是
    memory_lookup 工具、证据纪律是 evidence_hash 绑定。原样注入会让模型对照
    一个不存在的块。两版共存于本模块（单一真本源），改纪律要两边一起动。
    """
    return "\n".join(
        [
            "【跟踪表达契约】本题为持续跟踪类问题，draft 必须按此结构组织：\n"
            "1. delta-only 纪律：以上期基线为锚只报有信息量的变化；上期结论仍成立的项"
            "写一句「无变化」即可，禁止重跑全景模板凑字数。上期基线只能来自 "
            "memory_lookup 召回的用户既有判断或 conversation_context 里的先前结论；"
            "两处都无相关记录时，draft 开头显式声明「无上期基线，本期建立基线」，"
            "禁止虚构或臆测上期说过什么。\n"
            "2. 观点四态对照：对每条召回的既有判断给显式判定——"
            "「支持 / 削弱 / 无变化 / 信息不足」四态之一；判定必须由本轮 evidence "
            "支撑并进入对应 binding，没有证据支撑的判定只能写「信息不足」。\n"
            "3. 结论 TTL：本期每条新结论标注「复核期限：YYYY-MM-DD」——跟踪级默认 "
            "30 天、框架级默认 90 天；到期未复核视为待复核，不得当作已验证事实引用。\n"
            "4. 下期关注清单（draft 结尾必给）：每项 = 指标/事件 + 时间节点 + 触发条件"
            "（可观察、可证伪，如「若 X 月中报毛利率 <Y% 则削弱扩产逻辑」）；"
            "禁止「持续关注市场情绪」这类不可证伪表述。\n"
            "5. 跟踪不改变证据纪律：变化必须来自本轮工具证据，"
            "不得由「距上次隔了很久」推断「肯定有变化」。"
        ]
    )


def track_guidance_for_query(query: str, question_type: str | None = None) -> str:
    """命中意图返回表达契约，否则空串（不注入，行为不变）。"""
    if not parse_track_intent(query, question_type):
        return ""
    return build_track_guidance()


def episode_track_rule(query: str, question_type: str | None = None) -> str:
    """episode 指令的条件注入口：命中跟踪意图返回 episode 版契约，否则空串。"""
    if not parse_track_intent(query, question_type):
        return ""
    return build_track_guidance_for_episode()


# 结构门：prompt 对中转模型约束力有限（2026-08-13 live）。缺段用确定性文本补上，
# 不覆盖模型已写的正文——与 ensure_forecast_scenarios_visible 同一形状。
_QUAD_MARKERS = ("削弱", "无变化", "信息不足", "四态")
_TTL_MARKERS = ("复核期限", "valid_until")
_BASELINE_MARKERS = ("无上期基线",)
CONTRACT_STUB_HEADING = "## 跟踪契约补全（模型未按强制结构输出的段落）"


def missing_contract_elements(answer: str) -> tuple[str, ...]:
    """扫描回答里缺了契约的哪几件。非跟踪题的调用方应先自己判断是否要查。"""
    # 补全提示是在报告缺件，不是缺件已被模型补好；不能让它自己满足契约。
    text = str(answer or "").split(CONTRACT_STUB_HEADING, 1)[0]
    missing: list[str] = []
    has_baseline_decl = any(m in text for m in _BASELINE_MARKERS)
    has_quad = any(m in text for m in _QUAD_MARKERS) or ("支持 /" in text) or ("判定：支持" in text)
    if not has_quad and not has_baseline_decl:
        missing.append("quad_or_baseline")
    if not any(m in text for m in _TTL_MARKERS):
        missing.append("ttl")
    claims = _split_watch_claims(_watch_section_body(text))
    if not claims or not all(_is_registerable_watch(claim) for claim in claims):
        missing.append("next_watch")
    return tuple(missing)


_STUB_LINES = {
    "quad_or_baseline": (
        "- **观点四态对照**：正文未给出「支持 / 削弱 / 无变化 / 信息不足」，"
        "也未声明「无上期基线」。按契约视为信息不足，不得把未对照的旧判断当成仍成立。"
    ),
    "ttl": (
        "- **结论 TTL**：正文未标注「复核期限」。跟踪级默认 30 天、框架级默认 90 天；"
        "到期未复核不得当已验证事实引用。"
    ),
    "next_watch": (
        "- **下期关注清单**：正文未给出「指标 + 时间节点 + 触发条件」。"
        "下一轮跟踪缺少强制对照输入，本期只建立观察、不升格为已验证。"
    ),
}


def append_contract_stub(answer: str, missing: tuple[str, ...]) -> str:
    """把缺件以可见补全段追加到回答末尾；missing 为空则原文返回。"""
    if not missing:
        return str(answer or "")
    lines = [CONTRACT_STUB_HEADING]
    lines.extend(_STUB_LINES[key] for key in missing if key in _STUB_LINES)
    stub = "\n".join(lines)
    body = str(answer or "").rstrip()
    if CONTRACT_STUB_HEADING in body:
        # 重复投影不叠加；旧提示也不参与 missing_contract_elements 的完成度核对。
        return body
    if not body:
        return stub
    disclaimer = "（非投资建议）"
    if body.endswith(disclaimer):
        head = body[: -len(disclaimer)].rstrip()
        return f"{head}\n\n{stub}\n\n{disclaimer}"
    return f"{body}\n\n{stub}"


# —— Q4（bookgap S8）：契约缺件的程序核对——「能程序判定的约束进程序，不堆 prompt」。
# 三件套（四态对照/无基线声明、TTL、下期关注）是可确定检查的输出结构，此前只有
# prompt 约束 + 可见补全段（append_contract_stub），live 遵守不全且缺件不进任何
# 机器可读通道。这里把缺件映射成 ``repair_coordinator.missing_outputs`` 词表里的
# 输出项 id（直接可并入 ``build_repair_goal(missing_outputs=...)`` 的缺口修复环），
# 并给出 EVAL 可读收据。episode 运行时由 continuous_turn_adapter 合并进
# missing_outputs，表达层-only 缺口走 ``contract_rewrite_candidate``（tool-closed
# delivery），不写进 verifier ``issues``（#224 放行门吃前缀，生造文案会改门禁）。
# prompt 原文一字不动。
TRACK_CONTRACT_OUTPUT_IDS: dict[str, str] = {
    "quad_or_baseline": "track_quad_or_baseline",
    "ttl": "track_ttl",
    "next_watch": "track_next_watch",
}
TRACK_CONTRACT_OUTPUT_ID_SET = frozenset(TRACK_CONTRACT_OUTPUT_IDS.values())
_VERDICT_RE = re.compile(r"(?:判定|判断)?[：:]\s*(支持|削弱|无变化|信息不足)")
_VALID_UNTIL_RE = re.compile(
    r"(?:复核期限|valid_until)\s*[：:=]\s*(20\d{2}-\d{2}-\d{2})"
)
EXPIRED_MARK = "已过期，待复核"
_EXPIRED_SUFFIX = "（已过期，待复核）"


def contract_missing_outputs(
    answer: str,
    *,
    query: str = "",
    question_type: str | None = None,
) -> tuple[str, ...]:
    """程序核对：跟踪题的契约缺件 → missing_outputs 词表输出项 id。

    非跟踪意图恒返回空元组（普通问答零改动）。返回值形状与
    ``repair_coordinator.build_repair_goal(missing_outputs=...)`` 兼容。
    """
    if not parse_track_intent(query, question_type):
        return ()
    return tuple(
        TRACK_CONTRACT_OUTPUT_IDS[key]
        for key in missing_contract_elements(answer)
        if key in TRACK_CONTRACT_OUTPUT_IDS
    )


def merge_track_missing_outputs(
    existing: tuple[str, ...] | list[str],
    answer: str,
    *,
    query: str = "",
    question_type: str | None = None,
) -> tuple[str, ...]:
    """把跟踪契约缺件并入 repair 用的 missing_outputs。非跟踪题原样返回。"""
    extra = contract_missing_outputs(
        answer, query=query, question_type=question_type
    )
    return tuple(dict.fromkeys((*tuple(existing or ()), *extra)))


def is_contract_rewrite_only(
    missing_outputs: tuple[str, ...] | list[str],
    *,
    rejected_claims: tuple[str, ...] = (),
    semantic_gap_outputs: tuple[str, ...] = (),
) -> bool:
    """缺口全是表达槽（跟踪四态/TTL/下期关注，或排序矩阵/改判条件…），没有证据/语义缺口。"""
    from intelligence.services.ranking_contract import RANKING_CONTRACT_OUTPUT_ID_SET

    if rejected_claims or semantic_gap_outputs:
        return False
    missing = tuple(missing_outputs or ())
    if not missing:
        return False
    expression_slots = TRACK_CONTRACT_OUTPUT_ID_SET | RANKING_CONTRACT_OUTPUT_ID_SET
    return all(item in expression_slots for item in missing)


def parse_prior_verdict_check(answer: str) -> str | None:
    """正文里第一条显式四态。没有则 None，不猜。"""
    found = _VERDICT_RE.search(str(answer or ""))
    if found:
        return found.group(1)
    return None


def parse_valid_until(answer: str) -> str | None:
    """解析「复核期限：YYYY-MM-DD」或 ``valid_until=...``。没有则 None。"""
    found = _VALID_UNTIL_RE.search(str(answer or ""))
    if found:
        return found.group(1)
    return None


def ttl_status(valid_until: str | None, *, as_of: str | None = None) -> str:
    raw = str(valid_until or "").strip()[:10]
    if not raw:
        return "missing"
    try:
        until = date.fromisoformat(raw)
    except ValueError:
        return "missing"
    return "expired" if until < _as_of_date(as_of) else "current"


def annotate_expired_conclusions(text: str, *, as_of: str | None = None) -> str:
    """过期只标注、不删结论。同一处不重复盖章。"""
    raw = str(text or "")
    if not raw:
        return raw
    pieces: list[str] = []
    cursor = 0
    for match in _VALID_UNTIL_RE.finditer(raw):
        pieces.append(raw[cursor : match.end()])
        if ttl_status(match.group(1), as_of=as_of) == "expired":
            window = raw[match.end() : match.end() + 16]
            if EXPIRED_MARK not in window:
                pieces.append(_EXPIRED_SUFFIX)
        cursor = match.end()
    pieces.append(raw[cursor:])
    return "".join(pieces)


def downgrade_expired_text(
    text: str,
    *,
    valid_until: str | None = None,
    as_of: str | None = None,
) -> str:
    """消费端降级：扫正文 TTL，或按机器可读 ``valid_until`` 补标注。"""
    annotated = annotate_expired_conclusions(text, as_of=as_of)
    if ttl_status(valid_until, as_of=as_of) == "expired" and EXPIRED_MARK not in annotated:
        body = annotated.rstrip()
        return f"{body}{_EXPIRED_SUFFIX}" if body else _EXPIRED_SUFFIX
    return annotated


def contract_receipt(
    answer: str,
    *,
    query: str = "",
    question_type: str | None = None,
    as_of: str | None = None,
) -> dict[str, object]:
    """EVAL 可读收据：``missing_outputs`` 字段恒在场（空列表 = 契约齐/非跟踪题）。

    只含 JSON 原生类型，可直接落 ledger/trace/eval 载荷；``track_intent``
    区分「契约齐」与「本题不适用契约」两种空缺件。
    """
    track_intent = parse_track_intent(query, question_type)
    missing = contract_missing_outputs(
        answer, query=query, question_type=question_type
    )
    body = str(answer or "")
    valid = parse_valid_until(body) if track_intent else None
    verdict = parse_prior_verdict_check(body) if track_intent else None
    return {
        "check": "track_contract",
        "track_intent": track_intent,
        "missing_outputs": list(missing),
        "prior_verdict_check": verdict,
        "valid_until": valid,
        "ttl_status": ttl_status(valid, as_of=as_of) if track_intent else "missing",
        "baseline_declared": bool(
            track_intent and any(marker in body for marker in _BASELINE_MARKERS)
        ),
    }


# —— P1-E4：下期关注消费端。产出侧已有 prompt + stub；缺口是次日流程不读。
# 只登记可证伪条目到既有 checkpoints.jsonl（不新开台账），foresight 发问时强制对照。
# 补全 stub 本身不是观察项，解析时丢掉。直写 checkpoint 不是 memory_gate 晋升。
NEXT_WATCH_SOURCE = "track_next_watch"
NEXT_WATCH_CATEGORY = "下期关注"
_DATE_RE = re.compile(r"(20\d{2}-\d{2}-\d{2})")
_CN_DATE_RE = re.compile(r"(20\d{2})年(\d{1,2})月(\d{1,2})日")
_DAYS_RE = re.compile(r"(\d+)\s*天")
# 日历月（时点），与「N 个月」（时长）互斥；见 calendar_month_due 的说明。
# 「年」写法必须带「月」且后面不能再跟数字：「2026年10月15日」是日期、「2026年10亿元」不是月份；
# 「-」「/」写法后面不能再接分隔符或数字：「2026-10-15」「2026/10/15」是日期。
_YEAR_MONTH_RE = re.compile(
    r"(20\d{2})(?:\s*年\s*(\d{1,2})\s*月(?!\s*\d)|\s*[-/]\s*(\d{1,2})(?!\s*[-/\d]))"
)
_BULLET_RE = re.compile(r"^\s*(?:[-*•]|\d+[.)、）])\s+(.+)$")
# live 模型常写成「下期关注清单：1）…。2）…」或标题行内联若干「若/则」。
# lookbehind 定长：行首 / 句号 / 分号之后的项目符号或 1. 1) 1、1）
_ITEM_START = re.compile(
    r"(?:(?<=^)|(?<=[\n。；;]))\s*(?:[-•]|\*(?!\*)|\d+[.)、）])\s*"
)
_WATCH_HEADING_RE = re.compile(
    r"(?:#{1,6}\s+)?(?:\*\*|__)?下期关注(?:清单)?"
    r"(?:[（(][^）)\n]*[）)])?(?:\*\*|__)?[：: \t]*(?:\*\*|__)?"
)
_SECTION_STOP_PREFIXES = (
    "证据边界", "缺口", "证据缺口", "数据缺口", "信息缺口", "风险提示",
    "补充说明", "来源", "资料来源", "参考来源", "免责声明",
)
# 日期/到期只说明「何时看」，不说明「看到什么才改判」。这里只查条件形状，
# 不代替数字/引用/事实核验。中报/周度等可沿用既有隐式时间节点与默认到期日。
_FALSIFIABLE_MARKERS = ("若", "如果", "则", "低于", "高于", "<", ">", "≤", "≥", "≦", "≧", "跌破", "突破")
_WATCH_FIELD_RE = re.compile(r"^(?:指标(?:/事件)?|事项|事件|时间节点|时间|触发条件|条件)\s*[：:=]")
_VAGUE_WATCH = ("持续关注市场情绪", "持续关注", "继续观察")
# A standalone receipt describes a side effect, not an additional watch item.
# Match the whole sentence only: a receipt prefix cannot excuse missing fields.
_WATCH_RECEIPT_RE = re.compile(
    r"(?:^|(?<=。))\s*[（(]?(?:本条|本项|该事项|上述事项|本次研究|本次)"
    r"(?:已|已经|未|不)(?:登记|纳入|写入)(?:为)?(?:长期|持续)?(?:跟踪|关注清单)"
    r"(?:。[）)]?|[）)]。?|。?)\s*$"
)
_WATCH_TTL_METADATA_RE = re.compile(
    r"[（(]?\s*(?:复核期限|valid_until)\s*[：:=]\s*20\d{2}-\d{2}-\d{2}\s*[）)]?[。]?"
)
_ARROW_CONDITION_RE = re.compile(
    r"(?:上升|下降|走平|增长|减少|恶化|改善|不及预期|未达预期)[^。；;→]*→\s*[^。；;\s]+"
)
# Date roles precede date order. A report period or a publication deadline must
# not win merely because it occurs before the user's review appointment.
_DUE_TOKEN = r"(?:20\d{2}-\d{2}-\d{2}|20\d{2}年\d{1,2}月\d{1,2}日)"
_REVIEW_DATE_RE = re.compile(
    r"(?:复查|复核|回检|核查)(?:日期|时间|日|期限)?\s*(?:[：:=]|为|定于|安排在)?\s*(?P<before>"
    + _DUE_TOKEN + r")|(?P<after>" + _DUE_TOKEN + r")\s*(?:前|后)?(?:复查|复核|回检|核查)"
)
_WATCH_TIME_FIELD_RE = re.compile(r"(?:^|[；;。\n])\s*(?:时间节点|时间)\s*[：:=]([^；;。\n]*)")
_REPORT_PERIOD_DATE_RE = re.compile(
    r"(?:截至|报告期(?:为|截至)?\s*[：:=]?)\s*" + _DUE_TOKEN
    + r"|" + _DUE_TOKEN + r"(?=\s*报告期)"
)


@dataclass(frozen=True)
class NextWatchItem:
    claim: str
    due: str


def _as_of_date(as_of: str | None) -> date:
    raw = str(as_of or "").strip()[:10]
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return date.today()


def calendar_month_due(text: str) -> str | None:
    """「2026-10 月底」「2026年10月」这类**日历月**对应的到期日（当月最后一天）。

    日历月是时点，不是时长。不先把它认出来，下游按「\\d+ 个月」解析会把
    「2026-10月底」读成「10 个月后」——R-20260916-05 真实写进用户目录的
    due=2027-07-13 就是这么来的（正确答案是 2026-10-31）。取月末而非月初，
    是因为「约 X 月底披露」给上界更安全：早到期会让回检提前判空。
    """

    match = _YEAR_MONTH_RE.search(str(text or ""))
    if match is None:
        return None
    year, month = int(match.group(1)), int(match.group(2) or match.group(3))
    if not 1 <= month <= 12:
        return None
    return date(year, month, monthrange(year, month)[1]).isoformat()


def chinese_full_date(text: str) -> str | None:
    """「2026年10月15日」→ ISO 日期；年月日拼不成合法日期时返回 None，不把「13 月」拼成字符串。

    track_contract 与 ranking_contract 两条写入链共用这一个推导：同一句观察项在两本
    contract 里算出不同 due，回检就对不上号。
    """

    match = _CN_DATE_RE.search(str(text or ""))
    if match is None:
        return None
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3))).isoformat()
    except ValueError:
        return None


def _due_in_text(text: str, as_of: str | None) -> str | None:
    found = _DATE_RE.search(text)
    if found:
        try:
            return date.fromisoformat(found.group(1)).isoformat()
        except ValueError:
            return None
    cn_due = chinese_full_date(text)
    if cn_due:
        return cn_due
    month_due = calendar_month_due(text)
    if month_due:
        return month_due
    days = _DAYS_RE.search(text)
    if days:
        return (_as_of_date(as_of) + timedelta(days=int(days.group(1)))).isoformat()
    return None


def _review_dates(line: str) -> tuple[str | None, ...]:
    plain = str(line).replace("**", "").replace("__", "")
    return tuple(
        _due_in_text(match.group("before") or match.group("after"), None)
        for match in _REVIEW_DATE_RE.finditer(plain)
    )


def _item_due(line: str, as_of: str | None) -> str:
    plain = str(line).replace("**", "").replace("__", "")
    # Strongest role: a named review date, including a date after a disclosure
    # deadline within the same time field. Never rewrite the preserved claim.
    reviews = _review_dates(plain)
    if reviews and len(set(reviews)) == 1 and reviews[0] is not None:
        return reviews[0]
    time_field = _WATCH_TIME_FIELD_RE.search(plain)
    candidate = time_field.group(1) if time_field else plain
    candidate = _REPORT_PERIOD_DATE_RE.sub("", candidate)
    return _due_in_text(candidate, as_of) or (_as_of_date(as_of) + timedelta(days=30)).isoformat()


def _is_registerable_watch(line: str) -> bool:
    text = str(line or "").strip()
    if len(text) < 8:
        return False
    if any(vague in text and "则" not in text for vague in _VAGUE_WATCH):
        return False
    reviews = _review_dates(text)
    if reviews and (None in reviews or len(set(reviews)) != 1):
        return False
    return any(marker in text for marker in _FALSIFIABLE_MARKERS) or bool(_ARROW_CONDITION_RE.search(text))


def _watch_section_end(line: str) -> bool:
    stripped = line.strip()
    if re.match(r"^#{1,6}\s", stripped) or re.fullmatch(r"(?:[-*_]\s*){3,}", stripped):
        return True
    plain = stripped.replace("**", "").replace("__", "")
    if any(
        re.match(rf"^{re.escape(prefix)}(?:\s*[：:]|\s*$)", plain)
        for prefix in _SECTION_STOP_PREFIXES
    ):
        return True
    # 无 # 的独立粗体标题也是章节边界；指标/时间/条件等项内字段不是。
    return bool(
        re.match(r"^(?:\*\*|__)[^\n：:。；;!?！？]+?(?:\*\*|__)(?:\s*[：:]|\s*$)", stripped)
        and not _WATCH_FIELD_RE.match(plain)
    )


def _watch_section_body(answer: str) -> str:
    text = str(answer or "").split(CONTRACT_STUB_HEADING, 1)[0]
    heading = _WATCH_HEADING_RE.search(text)
    if heading is None:
        return ""
    kept: list[str] = []
    for line in text[heading.end():].splitlines():
        if _watch_section_end(line):
            break
        kept.append(line)
    return "\n".join(kept)


def _split_watch_claims(body: str) -> tuple[str, ...]:
    chunks: list[str] = []
    explicit_list = False
    for raw_line in str(body or "").splitlines():
        line = _WATCH_RECEIPT_RE.sub("", raw_line.strip()).strip()
        if not line:
            continue
        plain = line.replace("**", "").replace("__", "")
        if _WATCH_TTL_METADATA_RE.fullmatch(plain):
            continue
        starts_item = _ITEM_START.match(line) is not None
        is_field = _WATCH_FIELD_RE.match(plain) is not None
        if (
            explicit_list and not starts_item and not is_field
            and not raw_line[:1].isspace()
        ):
            # A marked list ends before unindented prose. Don't whitelist the
            # prose's wording or let its own 「若」 turn it into a checkpoint.
            break
        explicit_list = explicit_list or starts_item
        if chunks and not _ITEM_START.match(line) and (
            raw_line[:1].isspace() or _WATCH_FIELD_RE.match(plain)
            or (not _is_registerable_watch(chunks[-1]) and _is_registerable_watch(line))
        ):
            chunks[-1] += " " + line
            continue
        parts = [part.strip(" \t；;") for part in _ITEM_START.split(line)]
        parts = [part.strip(" 。；;") for part in parts if part.strip(" 。；;")]
        if len(parts) <= 1 and line.count("若") >= 2 and "。" in line:
            parts = [part.strip(" \t；;") for part in line.split("。")]
            parts = [part.strip(" 。；;") for part in parts if part.strip(" 。；;")]
        chunks.extend(parts)
    return tuple(chunks)


def parse_next_watch_items(
    answer: str, *, as_of: str | None = None
) -> tuple[NextWatchItem, ...]:
    """从跟踪题正文抽出可证伪的下期关注项。忽略契约补全 stub。"""
    items: list[NextWatchItem] = []
    seen: set[str] = set()
    for claim in _split_watch_claims(_watch_section_body(answer)):
        match = _BULLET_RE.match(claim)
        if match:
            claim = match.group(1).strip()
        if any(claim.startswith(prefix) for prefix in _SECTION_STOP_PREFIXES):
            continue
        if not _is_registerable_watch(claim):
            continue
        key = re.sub(r"\s+", "", claim)
        if key in seen:
            continue
        seen.add(key)
        items.append(NextWatchItem(claim=claim, due=_item_due(claim, as_of)))
    return tuple(items)


def ingest_next_watch(
    checkpoints_path: str | Path,
    answer: str,
    *,
    query: str = "",
    question_type: str | None = None,
    as_of: str | None = None,
    theme: str | None = None,
    session_id: str | None = None,
) -> list[dict[str, Any]]:
    """把可证伪的下期关注登记进 checkpoints.jsonl。非跟踪题 / 无条目时空操作。"""
    from intelligence.services.checkpoints import (
        load_checkpoints,
        load_verdicts,
        register_checkpoint,
    )

    if persistence_opt_out(query):
        # 用户说了不登记就一条都不写。放在最前面：意图判定、条目解析都还没跑，
        # 没有任何「先算出来再决定要不要写」的中间态可以被后面某一层重新用上。
        return []
    if not parse_track_intent(query, question_type):
        return []
    items = parse_next_watch_items(answer, as_of=as_of)
    if not items:
        return []
    path = Path(checkpoints_path).expanduser()
    existing, _ = load_checkpoints(path)
    verdicts, _ = load_verdicts(path.with_name("verdicts.jsonl"))
    open_claims = {
        re.sub(r"\s+", "", str(row.get("claim") or ""))
        for row in open_next_watch_records(existing, verdicts)
    }
    written: list[dict[str, Any]] = []
    themes = [theme] if theme and str(theme).strip() else None
    for item in items:
        key = re.sub(r"\s+", "", item.claim)
        if key in open_claims:
            continue
        _, record = register_checkpoint(
            path,
            claim=item.claim,
            due=item.due,
            category=NEXT_WATCH_CATEGORY,
            source=NEXT_WATCH_SOURCE,
            themes=themes,
            session_id=session_id,
            metric={"type": "manual"},
        )
        open_claims.add(key)
        written.append(record)
    return written


def open_next_watch_records(
    checkpoint_rows: list[dict[str, Any]],
    verdict_rows: list[dict[str, Any]],
) -> tuple[dict[str, Any], ...]:
    """尚未拿到终态裁决的下期关注条目（到期与未到期都要对照）。"""
    from intelligence.services.checkpoints import TERMINAL_VERDICTS

    scored = {
        str(row.get("id") or "")
        for row in verdict_rows
        if row.get("verdict") in TERMINAL_VERDICTS
    }
    return tuple(
        row
        for row in checkpoint_rows
        if row.get("source") == NEXT_WATCH_SOURCE
        and str(row.get("id") or "") not in scored
        and str(row.get("claim") or "").strip()
    )


def render_next_watch_for_prompt(records: tuple[dict[str, Any], ...] | list[dict[str, Any]]) -> str:
    if not records:
        return ""
    lines = []
    for row in records:
        due = str(row.get("due") or "未标到期")
        claim = str(row.get("claim") or "").strip()
        lines.append(f"- [due={due}] {claim}")
    return "\n".join(lines)
