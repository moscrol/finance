from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from intelligence.api.app import create_app  # noqa: E402
from intelligence.services.conversation_orchestrator import (  # noqa: E402
    TurnOrchestrator,
)
from intelligence.services.conversation_store import ConversationStore  # noqa: E402
from intelligence.services.run_store import RunStore  # noqa: E402
from intelligence.workbench_skills.contracts import (  # noqa: E402
    SkillDefinition,
    SkillExecutionContext,
    SkillOutput,
)
from intelligence.workbench_skills.registry import SkillRegistry  # noqa: E402
from intelligence.workbench_skills.router import (  # noqa: E402
    SkillRouteResult,
    SkillSelection,
)

_LLM_KEY_NAMES = (
    "DEEPSEEK_API_KEY",
    "MOONSHOT_API_KEY",
    "KIMI_API_KEY",
    "DASHSCOPE_API_KEY",
    "QWEN_API_KEY",
    "ZHIPU_API_KEY",
    "GLM_API_KEY",
    "OPENAI_API_KEY",
    "LLM_API_KEY",
    "FORESIGHT_BUILTIN_LLM_API_KEY",
)


def _wait_terminal(
    client: TestClient, run_id: str, *, timeout: float = 10.0
) -> dict[str, object]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/api/runs/{run_id}", params={"user": "alice"})
        response.raise_for_status()
        run = response.json()
        if run["status"] in {"completed", "failed", "cancelled"}:
            return run
        time.sleep(0.02)
    raise AssertionError(f"run {run_id} 未在 {timeout} 秒内结束")


def _send(
    client: TestClient,
    conversation_id: str,
    content: str,
    *,
    skill_mode: str = "hybrid",
    selected_skill_ids: list[str] | None = None,
) -> tuple[dict[str, object], dict[str, object]]:
    response = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={
            "content": content,
            "skill_mode": skill_mode,
            "selected_skill_ids": selected_skill_ids or [],
            "user": "alice",
        },
    )
    response.raise_for_status()
    created = response.json()
    return created, _wait_terminal(client, created["run_id"])


def _stream_payloads(response_text: str) -> list[dict[str, object]]:
    return [
        json.loads(line.removeprefix("data: "))
        for line in response_text.splitlines()
        if line.startswith("data: {")
        and '"schema_version"' in line
        and '"event_id"' in line
    ]


def test_real_conversation_round_trip_persists_skills_sse_and_three_turns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = (
        Path(__file__).parent / "fixtures" / "chat_workbench_repo"
    )
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))
    monkeypatch.setenv("FINANCE_WS", str(repo_root))
    monkeypatch.setenv("KB_VAULT", str(repo_root / "wiki"))
    for key_name in _LLM_KEY_NAMES:
        monkeypatch.delenv(key_name, raising=False)
    # 集成测试保持无外网：长尾兜底车道会按 controller 能力需求触发 W7 web 检索，
    # 真实网络取数会超出 _wait_terminal 的秒级预算。
    monkeypatch.setenv("FINANCE_NEWS_FETCH", "0")
    monkeypatch.setenv("FINANCE_WEB_SEARCH", "0")

    app = create_app(repo_root=repo_root)
    with TestClient(app) as client:
        conversation_response = client.post(
            "/api/conversations",
            json={"title": "真实集成会话", "user": "alice"},
        )
        conversation_response.raise_for_status()
        conversation_id = conversation_response.json()["conversation_id"]

        first, first_run = _send(
            client,
            conversation_id,
            "请复盘今天市场怎么样",
        )
        second, second_run = _send(
            client,
            conversation_id,
            "第二轮请看今天研究什么",
            skill_mode="manual",
            selected_skill_ids=["daily-agent"],
        )
        third, third_run = _send(
            client,
            conversation_id,
            "第三轮有哪些风险",
            skill_mode="manual",
        )

        messages_response = client.get(
            f"/api/conversations/{conversation_id}/messages",
            params={"user": "alice"},
        )
        messages_response.raise_for_status()
        messages = messages_response.json()
        assistants = [message for message in messages if message["role"] == "assistant"]

        assert [message["status"] for message in assistants] == [
            "completed",
            "completed",
            "completed",
        ]
        assert assistants[0]["selected_skill_ids"] == []
        assert assistants[0]["invoked_skill_ids"] == ["daily-review"]
        assert assistants[1]["selected_skill_ids"] == ["daily-agent"]
        assert assistants[1]["invoked_skill_ids"] == ["daily-agent"]
        assert assistants[2]["invoked_skill_ids"] == []
        assert "llm_unavailable_template_answer" not in assistants[0]["degrades"]
        assert "直接定性" in assistants[0]["content"]
        assert "最强证据" in assistants[0]["content"]
        assert "下一步验证" in assistants[0]["content"]
        assert "自然语言综合暂时不可用" not in assistants[0]["content"]
        for internal_term in (
            "图谱命中",
            "状态机",
            "graph_only",
            "检索骨架",
            "确定性结构化结果",
            "fact_market_daily",
            "canonical",
        ):
            assert internal_term not in assistants[0]["content"]
        assert first_run["parent_run_id"] is None
        assert second_run["parent_run_id"] == first["run_id"]
        assert third_run["parent_run_id"] == second["run_id"]
        assert first_run["session_id"] == conversation_id
        assert second_run["session_id"] == conversation_id
        assert third_run["session_id"] == conversation_id

        report_response = client.get(
            f"/api/runs/{first['run_id']}/report", params={"user": "alice"}
        )
        report_response.raise_for_status()
        report = report_response.json()
        module_ids = [module["module_id"] for module in report["modules"]]
        assert "daily_overview" in module_ids
        assert not any(module_id.startswith("research_") for module_id in module_ids)

        stream_response = client.get(
            f"/api/runs/{first['run_id']}/events",
            params={"user": "alice"},
        )
        stream_response.raise_for_status()
        payloads = _stream_payloads(stream_response.text)
        assert any(payload["event_type"] == "text.delta" for payload in payloads)
        assert any(payload["event_type"] == "message.complete" for payload in payloads)
        cursor = payloads[len(payloads) // 2]["seq"]

        resumed_response = client.get(
            f"/api/runs/{first['run_id']}/events",
            params={"user": "alice", "after": cursor},
        )
        resumed_response.raise_for_status()
        resumed_payloads = _stream_payloads(resumed_response.text)
        assert resumed_payloads
        assert all(payload["seq"] > cursor for payload in resumed_payloads)

        cancel_conversation = client.post(
            "/api/conversations",
            json={"title": "取消集成会话", "user": "alice"},
        ).json()
        cancel_response = client.post(
            f"/api/conversations/{cancel_conversation['conversation_id']}/messages",
            json={
                "content": "请完整分析今天研究什么以及所有风险",
                "skill_mode": "manual",
                "selected_skill_ids": ["daily-agent"],
                "user": "alice",
            },
        )
        cancel_response.raise_for_status()
        cancelled_run_id = cancel_response.json()["run_id"]
        requested = client.post(
            f"/api/runs/{cancelled_run_id}/cancel",
            params={"user": "alice"},
        )
        requested.raise_for_status()
        assert requested.json()["cancel_requested"] is True
        cancelled_run = _wait_terminal(client, cancelled_run_id)
        assert cancelled_run["status"] == "cancelled"
        cancelled_stream = client.get(
            f"/api/runs/{cancelled_run_id}/events",
            params={"user": "alice"},
        )
        cancelled_stream.raise_for_status()
        cancelled_payloads = _stream_payloads(cancelled_stream.text)
        assert any(
            payload["event_type"] == "message.error"
            and payload["payload"]["status"] == "cancelled"
            for payload in cancelled_payloads
        )
        cancelled_messages = client.get(
            f"/api/conversations/{cancel_conversation['conversation_id']}/messages",
            params={"user": "alice"},
        ).json()
        assert cancelled_messages[-1]["status"] == "cancelled"

    with TestClient(create_app(repo_root=repo_root)) as refreshed_client:
        restored = refreshed_client.get(
            f"/api/conversations/{conversation_id}/messages",
            params={"user": "alice"},
        )
        restored.raise_for_status()
        restored_messages = restored.json()
        assert len(restored_messages) == 6
        assert restored_messages[3]["invoked_skill_ids"] == ["daily-agent"]
        assert restored_messages[-1]["run_id"] == third["run_id"]


@dataclass
class _SlowSkill:
    skill_id: str = "slow-skill"

    def execute(self, context: SkillExecutionContext) -> SkillOutput:
        time.sleep(1.2)
        return SkillOutput(
            skill_id=self.skill_id,
            modules=[],
            citations=[],
            warnings=[],
            as_of=None,
            raw_result_ref=None,
        )


@dataclass
class _FastSkill:
    skill_id: str = "fast-skill"

    def execute(self, context: SkillExecutionContext) -> SkillOutput:
        return SkillOutput(
            skill_id=self.skill_id,
            modules=[
                {
                    "module_id": "fast_result",
                    "title": "快速模块",
                    "kind": "summary",
                    "status": "complete",
                    "summary": "其他模块继续完成。",
                    "content": None,
                    "metrics": [],
                    "items": [],
                    "table": None,
                    "warnings": [],
                    "provenance": {"source": "integration-fixture"},
                }
            ],
            citations=[],
            warnings=[],
            as_of=None,
            raw_result_ref=None,
        )


def test_skill_timeout_degrades_one_module_and_continues(
    tmp_path: Path,
) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    user_message = conversation_store.append_message(
        conversation.conversation_id, "user", "测试 Skill 超时"
    )
    run = run_store.create_run(
        user_message.content,
        "ask",
        session_id=conversation.conversation_id,
    )
    assistant = conversation_store.append_message(
        conversation.conversation_id,
        "assistant",
        "",
        status="pending",
        run_id=run.run_id,
    )
    definitions = {
        "slow-skill": SkillDefinition(
            skill_id="slow-skill",
            name="Slow Skill",
            description="超时测试",
            version="1.0.0",
            triggers=("slow",),
            input_schema={"type": "object"},
            permissions=("local_read",),
            timeout_seconds=1,
        ),
        "fast-skill": SkillDefinition(
            skill_id="fast-skill",
            name="Fast Skill",
            description="继续执行测试",
            version="1.0.0",
            triggers=("fast",),
            input_schema={"type": "object"},
            permissions=("local_read",),
            timeout_seconds=1,
        ),
    }
    registry = SkillRegistry(
        definitions,
        {
            "slow-skill": _SlowSkill(),
            "fast-skill": _FastSkill(),
        },
    )

    result = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        skill_registry=registry,
        route_skills_fn=lambda *_args, **_kwargs: SkillRouteResult(
            (
                SkillSelection("slow-skill", "manual", "超时测试"),
                SkillSelection("fast-skill", "manual", "继续执行测试"),
            ),
            False,
        ),
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run.run_id,
        assistant_message_id=assistant.message_id,
        query=user_message.content,
        skill_mode="manual",
        selected_skill_ids=["slow-skill", "fast-skill"],
    )

    events = run_store.load_stream_events(run.run_id)
    report = json.loads(
        (run_store.run_dir(run.run_id) / "report.json").read_text(encoding="utf-8")
    )
    assert result.status == "completed"
    assert any("slow-skill 执行超时" in warning for warning in report["warnings"])
    assert any(
        module["module_id"] == "fast_result" for module in report["modules"]
    )
    assert any(
        event["event_type"] == "skill.result"
        and event["payload"]["skill_id"] == "slow-skill"
        and event["payload"]["status"] == "degraded"
        and event["payload"]["task_may_continue"] is True
        for event in events
    )
    retrieve_step = next(
        step
        for step in run_store.load_trace(run.run_id)
        if step["step_id"] == "retrieve"
    )
    retrieve_summary = json.loads(retrieve_step["output_summary"])
    assert retrieve_summary["elapsed_ms"] >= 0
