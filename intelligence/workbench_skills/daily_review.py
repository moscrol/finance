from __future__ import annotations

import json
from typing import cast

from intelligence.api.structured_reports import daily_projection_modules
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
        source = (
            context.repo_root
            / "market_feature_store"
            / "exports"
            / f"{date_text}-daily-review.md"
        ).relative_to(context.repo_root).as_posix()
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
            context.repo_root / "db" / "market_feature_store.duckdb",
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
                output_contract=(
                    "直接给出市场状态、最强数据、主要风险和下一交易日验证点",
                ),
            ),
        )

