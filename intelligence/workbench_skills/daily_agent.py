from __future__ import annotations

import json
from typing import cast

from intelligence.api.daily_reports import project_daily_agent
from intelligence.api.structured_reports import daily_agent_projection_modules
from intelligence.workbench_skills.contracts import (
    JsonObject,
    JsonValue,
    SkillExecutionContext,
    SkillOutput,
    build_module_answer_contract,
    redact_json,
)


class DailyAgentSkill:
    skill_id = "daily-agent"

    def execute(self, context: SkillExecutionContext) -> SkillOutput:
        exports = context.repo_root / "market_feature_store" / "exports"
        candidates = sorted(exports.glob("*-daily-agent.json"), reverse=True)
        if not candidates:
            return SkillOutput(
                skill_id=self.skill_id,
                modules=[],
                citations=[],
                warnings=["未找到 canonical Daily Agent JSON；日报研究模块缺失。"],
                as_of=None,
                raw_result_ref=None,
            )
        source_path = candidates[0]
        source = source_path.relative_to(context.repo_root).as_posix()
        try:
            payload = json.loads(source_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("Daily Agent payload must be an object")
            projection = project_daily_agent(payload, source_path=source)
        except (json.JSONDecodeError, OSError, UnicodeError, ValueError):
            return SkillOutput(
                skill_id=self.skill_id,
                modules=[],
                citations=[],
                warnings=["canonical Daily Agent JSON 无法读取。"],
                as_of=None,
                raw_result_ref=None,
            )
        safe_projection = cast(
            JsonObject, redact_json(cast(JsonValue, projection))
        )
        modules = [
            cast(JsonObject, redact_json(cast(JsonValue, module)))
            for module in daily_agent_projection_modules(projection)
        ]
        provenance = projection.get("provenance", {})
        warnings = [
            str(redact_json(warning))
            for warning in provenance.get("warnings", [])
        ]
        as_of_value = projection.get("date")
        as_of = as_of_value if isinstance(as_of_value, str) else None
        citations: list[JsonObject] = [
            {
                "source": source,
                "title": "Canonical Daily Agent",
                "evidence_layer": "canonical",
                "as_of": as_of,
            }
        ]
        raw_result: JsonObject = {
            "skill_id": self.skill_id,
            "as_of": as_of,
            "projection": safe_projection,
            "modules": modules,
            "citations": citations,
            "warnings": warnings,
        }
        artifact = context.run_store.add_artifact(
            context.run_id,
            "daily-agent-skill-result.json",
            json.dumps(
                cast(JsonObject, redact_json(raw_result)),
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            renderer="json",
            title="Daily Agent Skill 原始结果",
        )
        return SkillOutput(
            skill_id=self.skill_id,
            modules=modules,
            citations=citations,
            warnings=warnings,
            as_of=as_of,
            raw_result_ref=artifact.path,
            answer_contract=build_module_answer_contract(
                skill_id=self.skill_id,
                title="研究雷达",
                modules=modules,
                citations=citations,
                warnings=warnings,
                as_of=as_of,
                retrieval_plan=("读取最新 canonical Daily Agent 研究队列",),
                output_contract=(
                    "先裁决研究优先级，再给证据缺口和可执行核验动作",
                ),
            ),
        )
