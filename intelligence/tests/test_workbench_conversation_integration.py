from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from intelligence.api import app as app_module  # noqa: E402
from intelligence.api.app import create_app  # noqa: E402
from intelligence.runtime.continuous_turn_adapter import (  # noqa: E402
    ContinuousTurnResult,
)
from intelligence.runtime.conversation_orchestrator import (  # noqa: E402
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


def _wait_message_terminal(
    client: TestClient,
    conversation_id: str,
    *,
    timeout: float = 10.0,
) -> list[dict[str, object]]:
    """轮询到**消息自身**终态再返回，不能只看 run 状态。

    run 终态（claim_terminal_run）和消息终稿（revise_message）是两次文件写：
    读者以 run 状态为信号立刻读消息，会命中「run=completed 但消息还没带
    citations」的窗口。消息的 status 与 citations 在同一次写入里原子落盘，
    所以消息级断言必须等消息级终态。
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        messages = client.get(
            f"/api/conversations/{conversation_id}/messages",
            params={"user": "alice"},
        ).json()
        if messages and messages[-1]["status"] in {
            "completed",
            "failed",
            "cancelled",
        }:
            return messages
        time.sleep(0.02)
    raise AssertionError(f"conversation {conversation_id} 消息未在 {timeout} 秒内终态")


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


def test_continuous_episode_citations_survive_run_context_reload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = Path(__file__).parent / "fixtures" / "chat_workbench_repo"
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))
    monkeypatch.setenv("FINANCE_WS", str(repo_root))
    monkeypatch.setenv("KB_VAULT", str(repo_root / "wiki"))

    class CitationAdapter:
        def handle(self, **_kwargs: object) -> ContinuousTurnResult:
            return ContinuousTurnResult(
                handled=True,
                status="completed",
                answer="当前主线是半导体，失效条件是量能与核心股承接同步转弱。",
                as_of="2026-07-24",
                citations=(
                    {
                        "title": "半导体板块成交集中度居前",
                        "source": "本地市场数据",
                        "date": "2026-07-24",
                    },
                ),
                warnings=(),
                private_artifact={"runtime_backend": "test_episode"},
                events=(),
                llm_provider="test",
            )

    monkeypatch.setattr(
        app_module,
        "_build_continuous_turn_adapter",
        lambda **_kwargs: CitationAdapter(),
    )

    with TestClient(create_app(repo_root=repo_root)) as client:
        conversation_id = client.post(
            "/api/conversations",
            json={"title": "证据恢复", "user": "alice"},
        ).json()["conversation_id"]
        created, run = _send(
            client,
            conversation_id,
            "目前市场的主线是什么，给出判断依据和失效条件",
        )

        assert run["status"] == "completed"
        messages = _wait_message_terminal(client, conversation_id)
        assert len(messages[-1]["citations"]) == 1

        context = client.get(
            f"/api/runs/{created['run_id']}/context",
            params={"user": "alice"},
        ).json()
        bound_evidence = [
            item
            for item in context["evidence"]
            if item["classification"] == "bound_evidence"
        ]
        assert [item["label"] for item in bound_evidence] == [
            "[E1] 本地市场数据"
        ]


def test_open_gaps_mirror_into_message_followups(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """缺口镜像端到端：episode 报缺口 → 消息带「缺口补齐」追问 + artifact。

    R15 knevo 对照 9:2:0 的失分形状：降级声明把缺口变成句号，追问负担全在
    用户。缺口必须镜像成可点击的下一步（knevo q12 的 suggest_options 形状），
    且确定性生成——模型没机会顺嘴编数据。
    """
    repo_root = Path(__file__).parent / "fixtures" / "chat_workbench_repo"
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))
    monkeypatch.setenv("FINANCE_WS", str(repo_root))
    monkeypatch.setenv("KB_VAULT", str(repo_root / "wiki"))

    class GapAdapter:
        def handle(self, **_kwargs: object) -> ContinuousTurnResult:
            return ContinuousTurnResult(
                handled=True,
                status="degraded",
                answer="关于当前主线，现有证据不足，暂不能给出可靠结论。仍需核验：主线判断依据、失效条件。",
                as_of="2026-07-24",
                citations=(),
                warnings=("证据或语义核验未完全通过，已按证据边界降级。",),
                private_artifact={"runtime_backend": "test_episode"},
                events=(),
                llm_provider="test",
                open_gaps=("主线判断依据", "失效条件"),
            )

    monkeypatch.setattr(
        app_module,
        "_build_continuous_turn_adapter",
        lambda **_kwargs: GapAdapter(),
    )

    with TestClient(create_app(repo_root=repo_root)) as client:
        conversation_id = client.post(
            "/api/conversations",
            json={"title": "缺口镜像", "user": "alice"},
        ).json()["conversation_id"]
        created, run = _send(
            client,
            conversation_id,
            "目前市场的主线是什么，给出判断依据和失效条件",
        )

        assert run["status"] == "completed"
        messages = _wait_message_terminal(client, conversation_id)
        followups = messages[-1]["followups"]
        assert len(followups) == 2
        assert all(item["type"] == "gap" for item in followups)
        assert all(item["type_label"] == "缺口补齐" for item in followups)
        assert "主线判断依据" in followups[0]["full_prompt"]
        assert all(len(item["label"]) <= 20 for item in followups)
        # full_prompt 是替用户写好的完整问题，直接可发。
        assert all(item["full_prompt"].strip() for item in followups)

        # artifact 端点是最终一致的旁路（#321 写序：消息终稿先于 artifact
        # 落盘，run=completed 不保证 followups.json 已写完），按其语义轮询。
        # 消息里的 followups 才是交付主通道，上面已即时断言。
        deadline = time.monotonic() + 5.0
        document: dict[str, object] = {"followups": []}
        while time.monotonic() < deadline:
            document = client.get(
                f"/api/runs/{created['run_id']}/followups",
                params={"user": "alice"},
            ).json()
            if document.get("followups"):
                break
            time.sleep(0.02)
        assert len(document["followups"]) == 2
        assert document["llm_used"] is False


def test_terminal_claim_and_message_revise_are_adjacent_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """钉死写序：run 终态 claim 之后、消息终稿之前，不得插入 artifact 落盘。

    2026-08-13 定位的竞态：claim 先把 run=completed 落盘，随后三份 artifact
    （含 MB 级 json.dumps）再落盘，最后才 revise 消息。轮询方以 run 状态为
    信号读消息，几百毫秒窗口内读到零 citations——全量测试负载下
    citations_survive_run_context_reload 就是这么红的。claim 必须先行
    （终态线性化，防与取消赛跑），所以修法是把消息终稿挪到 claim 紧后。
    顺序断言即产品属性：窗口宽度 = claim 与 revise 之间的写盘次数。
    """
    repo_root = Path(__file__).parent / "fixtures" / "chat_workbench_repo"
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))
    monkeypatch.setenv("FINANCE_WS", str(repo_root))
    monkeypatch.setenv("KB_VAULT", str(repo_root / "wiki"))

    class CitationAdapter:
        def handle(self, **_kwargs: object) -> ContinuousTurnResult:
            return ContinuousTurnResult(
                handled=True,
                status="completed",
                answer="当前主线是半导体，失效条件是量能与核心股承接同步转弱。",
                as_of="2026-07-24",
                citations=(
                    {
                        "title": "半导体板块成交集中度居前",
                        "source": "本地市场数据",
                        "date": "2026-07-24",
                    },
                ),
                warnings=(),
                private_artifact={"runtime_backend": "test_episode"},
                events=(),
                llm_provider="test",
            )

    monkeypatch.setattr(
        app_module,
        "_build_continuous_turn_adapter",
        lambda **_kwargs: CitationAdapter(),
    )

    ops: list[str] = []
    original_claim = RunStore.claim_terminal_run
    original_artifact = RunStore.add_artifact
    original_revise = ConversationStore.revise_message

    def spy_claim(self, *args, **kwargs):
        ops.append("claim")
        return original_claim(self, *args, **kwargs)

    def spy_artifact(self, *args, **kwargs):
        ops.append("artifact")
        return original_artifact(self, *args, **kwargs)

    def spy_revise(self, *args, **kwargs):
        ops.append("revise")
        return original_revise(self, *args, **kwargs)

    monkeypatch.setattr(RunStore, "claim_terminal_run", spy_claim)
    monkeypatch.setattr(RunStore, "add_artifact", spy_artifact)
    monkeypatch.setattr(ConversationStore, "revise_message", spy_revise)

    with TestClient(create_app(repo_root=repo_root)) as client:
        conversation_id = client.post(
            "/api/conversations",
            json={"title": "写序回归", "user": "alice"},
        ).json()["conversation_id"]
        _, run = _send(
            client,
            conversation_id,
            "目前市场的主线是什么，给出判断依据和失效条件",
        )

    assert run["status"] == "completed"
    assert "claim" in ops and "revise" in ops
    claim_at = ops.index("claim")
    revise_after_claim = next(
        (i for i in range(claim_at + 1, len(ops)) if ops[i] == "revise"),
        None,
    )
    assert revise_after_claim is not None, f"claim 后没有消息终稿：{ops}"
    between = ops[claim_at + 1 : revise_after_claim]
    assert "artifact" not in between, (
        f"run 终态与消息终稿之间插入了 artifact 落盘，竞态窗口回宽：{ops}"
    )


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
