from __future__ import annotations

import json
import re
from datetime import date
from typing import cast

from intelligence.api.structured_reports import daily_projection_modules
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
        requested_date = _requested_date(context.query)
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


def _requested_date(query: str) -> str | None:
    match = re.search(
        r"(?<!\d)(20\d{2})(?:年|[-/.])(\d{1,2})"
        r"(?:(?:月|[-/.])(\d{1,2})日?)?(?!\d)",
        query,
    )
    if match is None or match.group(3) is None:
        return None
    try:
        return date(
            int(match.group(1)),
            int(match.group(2)),
            int(match.group(3)),
        ).isoformat()
    except ValueError:
        return None
