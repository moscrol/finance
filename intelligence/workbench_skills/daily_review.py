from __future__ import annotations

import json
import re
from datetime import date as date_cls
from typing import cast

from intelligence.api.structured_reports import daily_projection_modules
from intelligence.paths import default_market_db_path
from intelligence.services.ask_blocks import mainline_knowledge_module
from intelligence.services.query_understanding import (
    market_review_requested_date,
)
from intelligence.workbench_skills.contracts import (
    JsonObject,
    JsonValue,
    SkillExecutionContext,
    SkillOutput,
    build_module_answer_contract,
    redact_json,
)


# 问题子话题 → 正式日报里的章节标题关键词。
#
# 为什么需要这一层：daily_projection_modules 给聊天的基础模块只带核心看板和每节
# 的结论句（有 JSON 真本源后多了 15 节结论，但表格仍留给产物库的复盘页——进模型
# 上下文要有预算）。细分问题要的恰是表里的行：实测「连板」「断层」「立新能源」
# 在模块里出现 0 次，而正式日报的「## 11. 3板及以上个股」里立新能源 6 连板、
# 梯队 6→4→3（缺 5 板）全都在。所以这里走附加式：只在问题问到某个子话题时，
# 额外把对应章节原文挂上去。
#
# 按标题**关键词**匹配而不是章节号：日报的编号会随模板调整漂移，标题词稳定。
_SUBTOPIC_SECTIONS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("连板", "梯队", "断层", "晋级"), ("3板及以上", "连板", "晋级")),
    (("新高",), ("新高",)),
    (("双红",), ("双红题材", "单红题材")),
    (("涨停",), ("涨停题材",)),
    (("情绪", "强度", "沸点", "赚钱效应"), ("市场情绪", "市场强度")),
    (("主线",), ("市场环境总评", "板块涨幅")),
)

# 章节原文直接进模型上下文，必须有预算。十原则 9.5：优化目标是可治理不是更多。
# 6000 字够装下最大的单章（涨停题材 5311 字），装不下就截断并留证。
_SECTION_BUDGET = 6000


def select_review_sections(
    markdown: str,
    query: str,
    *,
    budget: int = _SECTION_BUDGET,
) -> tuple[list[dict[str, str]], list[str]]:
    """按问题意图从正式日报里挑相关章节原文。

    返回 ``(sections, warnings)``。问题没问到任何子话题就返回空——泛问
    「今天市场怎么样」时通用模板本来就够，多拖章节是白烧上下文预算。
    """
    wanted: list[str] = []
    for triggers, headings in _SUBTOPIC_SECTIONS:
        if any(trigger in query for trigger in triggers):
            wanted.extend(headings)
    if not wanted:
        return [], []

    parts = re.split(r"(?m)^(## .+)$", markdown)
    sections: list[dict[str, str]] = []
    warnings: list[str] = []
    remaining = budget
    for index in range(1, len(parts), 2):
        heading = parts[index].lstrip("# ").strip()
        if not any(keyword in heading for keyword in wanted):
            continue
        body = parts[index + 1].strip()
        if remaining <= 0:
            warnings.append(
                f"正式日报章节「{heading}」因上下文预算未纳入；未展示不代表不存在"
            )
            continue
        if len(body) > remaining:
            warnings.append(
                f"正式日报章节「{heading}」共 {len(body)} 字，"
                f"按上下文预算截断到 {remaining} 字；未展示不代表不存在"
            )
            body = body[:remaining]
        remaining -= len(body)
        sections.append({"heading": heading, "body": body})
    return sections, warnings


class DailyReviewSkill:
    skill_id = "daily-review"

    def execute(self, context: SkillExecutionContext) -> SkillOutput:
        requested_date = market_review_requested_date(context.query)
        try:
            date_text, projected_modules, projected_warnings = (
                daily_projection_modules(
                    context.repo_root,
                    requested_date=requested_date,
                )
            )
        except (OSError, UnicodeError, ValueError):
            return SkillOutput(
                skill_id=self.skill_id,
                modules=[],
                citations=[],
                warnings=["本地复盘报告无法读取。"],
                as_of=None,
                raw_result_ref=None,
            )
        warnings = [str(redact_json(warning)) for warning in projected_warnings]
        modules = [
            cast(JsonObject, redact_json(cast(JsonValue, module)))
            for module in projected_modules
        ]
        if date_text is None:
            return SkillOutput(
                skill_id=self.skill_id,
                modules=modules,
                citations=[],
                warnings=warnings,
                as_of=None,
                raw_result_ref=None,
            )
        source_path = (
            context.repo_root
            / "market_feature_store"
            / "exports"
            / f"{date_text}-daily-review.md"
        )
        source = source_path.relative_to(context.repo_root).as_posix()
        # 问题问到子话题时，把正式日报里对应的章节原文补进来。四个固定模块
        # 是「日常复盘」的形状，回答不了「连板有没有断层」这类细分问题。
        subtopic_sections: list[dict[str, str]] = []
        try:
            subtopic_sections, section_warnings = select_review_sections(
                source_path.read_text(encoding="utf-8"),
                context.query,
            )
        except (OSError, UnicodeError):
            section_warnings = ["正式日报章节原文读取失败；本轮只用投影模块。"]
        warnings.extend(str(redact_json(note)) for note in section_warnings)
        if subtopic_sections:
            modules.append(
                cast(
                    JsonObject,
                    redact_json(
                        cast(
                            JsonValue,
                            {
                                "module_id": "daily_review_sections",
                                "kind": "list",
                                "title": "正式日报·问题相关章节",
                                "status": "ok",
                                # 正文必须放 summary：_module_fact_lines 只读
                                # items 的 title/summary，放进 content 会被静默丢掉——
                                # 实测模型收到的只有标题，答案原话是「知道日报里有这张
                                # 表、但看不到表里任何一行数据」。
                                "items": [
                                    {
                                        "title": section["heading"],
                                        "summary": section["body"],
                                    }
                                    for section in subtopic_sections
                                ],
                                "provenance": {"source": source, "as_of": date_text},
                            },
                        )
                    ),
                )
            )
        citations: list[JsonObject] = [
            {
                "source": source,
                "title": "本地正式日报",
                "evidence_layer": "canonical",
                "as_of": date_text,
            }
        ]
        # 第二条腿：盘面说哪个方向在走，知识库说我对这个方向研究到什么程度。
        # 这个 skill 拥有日常复盘答案（market_watch 走 workflow 车道），所以知识库
        # 视角必须接在这里；只挂在 ask 侧的复盘合成器上，用户在工作台里看不到。
        anchor_warnings: list[str] = []
        knowledge_module = mainline_knowledge_module(
            # 数据根，不是代码根。context.repo_root 来自 WORKBENCH_REPO_ROOT，
            # 部署契约里那是「候选代码根」，盘面库在 FINANCE_WS 数据根下；写成代码根
            # 会让这条腿在蓝绿运行时静默失效，而且返回 None 时连告警都没有。
            default_market_db_path(),
            as_of=date_text,
            warnings=anchor_warnings,
        )
        warnings.extend(str(redact_json(note)) for note in anchor_warnings)
        if knowledge_module is not None:
            modules.append(cast(JsonObject, redact_json(cast(JsonValue, knowledge_module))))
            citations.append(
                {
                    "source": "knowledge-base/wiki",
                    "title": "主线方向的知识库积累",
                    "evidence_layer": "graph",
                    "as_of": date_text,
                }
            )
        payload: JsonObject = {
            "skill_id": self.skill_id,
            "as_of": date_text,
            "modules": modules,
            "citations": citations,
            "warnings": warnings,
        }
        # 答案由这份 output_contract 驱动。模块进了 contract 但 contract 不要求写它，
        # 模型就不会写——实测知识库模块和引用都到位了，正文里一个概念页都没提。
        output_contract: list[str] = [
            "直接给出市场状态、最强数据、主要风险和下一交易日验证点",
        ]
        if subtopic_sections:
            # 模块进了 contract 但 contract 不要求写它，模型就不会写——上面知识库
            # 那条腿已经踩过一次。这里把「先回答用户问的那件事」放到第一条：
            # 实测 A6 问连板梯队，模型拿着通用模板答涨停方向，一个字没碰连板。
            headings = "、".join(
                section["heading"] for section in subtopic_sections
            )
            output_contract.insert(
                0,
                f"**先直接回答用户问的那个问题**：本轮已附上正式日报的「{headings}」"
                "章节原文，逐条引用其中的具体数字与个股，不要用通用复盘模板绕开它；"
                "问题问到的口径（如梯队是否断层）要给出明确结论而不只是罗列",
            )
        if date_text != date_cls.today().isoformat():
            output_contract.insert(
                0,
                f"正文第一句写明数据截至 {date_text}；"
                "全文不得把它称作今天/今日/当天（盘后到夜间入库之间，"
                "最新可用数据就是上一交易日）",
            )
        if knowledge_module is not None:
            output_contract.append(
                "单独说明主线方向在知识库里的积累：各方向已有哪些概念页与公司暴露"
                "（带上公司的角色），以及哪些方向盘面已进主线但知识库尚无积累"
                "（那是当天最该补的研究）；盘面强弱与知识库积累是两件事，"
                "不得互相推导"
            )
        safe_payload = cast(JsonObject, redact_json(payload))
        artifact = context.run_store.add_artifact(
            context.run_id,
            "daily-review-skill-result.json",
            json.dumps(safe_payload, ensure_ascii=False, indent=2) + "\n",
            renderer="json",
            title="Daily Review Skill 原始结果",
        )
        return SkillOutput(
            skill_id=self.skill_id,
            modules=modules,
            citations=citations,
            warnings=warnings,
            as_of=date_text,
            raw_result_ref=artifact.path,
            answer_contract=build_module_answer_contract(
                skill_id=self.skill_id,
                title="每日市场复盘",
                modules=modules,
                citations=citations,
                warnings=warnings,
                as_of=date_text,
                retrieval_plan=(
                    (
                        f"读取 {requested_date} 的 canonical 正式日报"
                        if requested_date
                        else "读取最新 canonical 正式日报"
                    ),
                ),
                output_contract=tuple(output_contract),
            ),
        )

