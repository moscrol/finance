"""09 连续研究：Workbench 真实对话入口（假模型）端到端。

走 ``POST /api/conversations/{id}/messages`` 这扇门，不用 CLI 冒充会话 id。
适配器是假的（记录模型看到的 conversation_context，返回固定答案），
编排器、存储、路由、投影全是真的。
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from intelligence.api import app as app_module  # noqa: E402
from intelligence.api.app import create_app  # noqa: E402
from intelligence.runtime.continuous_turn_adapter import (  # noqa: E402
    ContinuousTurnResult,
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
_REPO_ROOT = Path(__file__).parent / "fixtures" / "chat_workbench_repo"


class RecordingAdapter:
    """记录每轮模型可见的 conversation_context；按轮次返回不同答案。"""

    def __init__(self) -> None:
        self.contexts: list[str] = []
        self.calls = 0

    def handle(self, **kwargs: object) -> ContinuousTurnResult:
        control = kwargs.get("control")
        self.contexts.append(str(getattr(control, "conversation_context", "") or ""))
        self.calls += 1
        gaps: tuple[str, ...] = ("1.6T 订单口径",) if self.calls == 1 else ()
        return ContinuousTurnResult(
            handled=True,
            status="degraded" if gaps else "completed",
            answer=f"**第{self.calls}轮判断：光模块主线延续。**\n证据见公告。",
            as_of=f"2026-09-0{min(8, self.calls + 6)}",
            citations=(),
            warnings=("证据或语义核验未完全通过，已按证据边界降级。",) if gaps else (),
            private_artifact={"runtime_backend": "test_episode"},
            events=(),
            llm_provider="test",
            open_gaps=gaps,
        )


def _env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))
    monkeypatch.setenv("FINANCE_WS", str(_REPO_ROOT))
    monkeypatch.setenv("KB_VAULT", str(_REPO_ROOT / "wiki"))
    monkeypatch.delenv("FORESIGHT_USER", raising=False)
    for name in _LLM_KEY_NAMES:
        monkeypatch.delenv(name, raising=False)


def _wait_terminal(client: TestClient, run_id: str, user: str, timeout: float = 10.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        run = client.get(f"/api/runs/{run_id}", params={"user": user}).json()
        if run["status"] in {"completed", "failed", "cancelled"}:
            return run
        time.sleep(0.02)
    raise AssertionError(f"run {run_id} 未在 {timeout} 秒内结束")


def _wait_messages(client: TestClient, conversation_id: str, user: str, timeout: float = 10.0) -> list[dict]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        messages = client.get(
            f"/api/conversations/{conversation_id}/messages", params={"user": user}
        ).json()
        if messages and messages[-1]["status"] in {"completed", "failed", "cancelled"}:
            return messages
        time.sleep(0.02)
    raise AssertionError("消息未终态")


def _send(
    client: TestClient,
    conversation_id: str,
    content: str,
    *,
    user: str = "alice",
    continuation: dict | None = None,
) -> tuple[dict, list[dict]]:
    body: dict[str, object] = {
        "content": content,
        "skill_mode": "hybrid",
        "selected_skill_ids": [],
        "user": user,
    }
    if continuation is not None:
        body["continuation"] = continuation
    response = client.post(f"/api/conversations/{conversation_id}/messages", json=body)
    response.raise_for_status()
    created = response.json()
    run = _wait_terminal(client, created["run_id"], user)
    assert run["status"] == "completed", run
    return created, _wait_messages(client, conversation_id, user)


def _project(client: TestClient, conversation_id: str, user: str = "alice") -> dict:
    response = client.get(
        f"/api/conversations/{conversation_id}/research-project", params={"user": user}
    )
    response.raise_for_status()
    return response.json()


def _install(monkeypatch: pytest.MonkeyPatch, adapter: RecordingAdapter) -> None:
    monkeypatch.setattr(
        app_module, "_build_continuous_turn_adapter", lambda **_kwargs: adapter
    )


def test_three_rounds_carry_state_and_survive_restart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _env(monkeypatch, tmp_path)
    adapter = RecordingAdapter()
    _install(monkeypatch, adapter)

    with TestClient(create_app(repo_root=_REPO_ROOT)) as client:
        cid = client.post(
            "/api/conversations", json={"title": "光模块研究", "user": "alice"}
        ).json()["conversation_id"]

        # 轮 1：首问。没有先验，模型输入里不得出现研究项目块。
        _, messages = _send(client, cid, "光模块这个题材近三个月怎么演绎，包括逻辑和股价")
        assert "研究项目状态" not in adapter.contexts[0]
        cards = messages[-1]["followups"]
        assert 2 <= len(cards) <= 4
        assert all(card["kind"] in {"gap_fill", "alternative_explanation", "condition_test", "continue"} for card in cards)
        assert len({card["kind"] for card in cards}) >= 2
        assert all(card["kind_label"] for card in cards)
        gap_card = next(card for card in cards if card["kind"] == "gap_fill")
        first_run = messages[-1]["run_id"]

        project = _project(client, cid)
        assert project["completed_rounds"] == 1
        assert project["open_questions"] == ["1.6T 订单口径"]
        assert project["rounds"][0]["run_id"] == first_run
        # 轮 1 是降级轮（run.degrades 带「已按证据边界降级」）：它的首行不是判断，当前判断留空。
        # 不断言 report.json 的 research_status：#321 写序是消息终稿先落盘、artifact 随后，
        # 此刻 report.json 可能还没写完；降级判定不依赖它（run.degrades 在消息终稿前已落）。
        assert project["rounds"][0]["warnings"] == ["证据或语义核验未完全通过，已按证据边界降级。"]
        assert project["current_judgment"] == ""

        # 轮 2：点卡片延续。模型看到先验块；用户消息落 continuation；run 链接上。
        continuation = {
            "run_id": first_run,
            "kind": gap_card["kind"],
            "source": gap_card.get("source", ""),
            "label": gap_card["label"],
            "full_prompt": gap_card["full_prompt"],
            "inherits": gap_card.get("inherits", {}),
        }
        created, messages = _send(client, cid, gap_card["full_prompt"], continuation=continuation)
        prior = adapter.contexts[1]
        assert "## 研究项目状态（跨轮先验，非市场事实）" in prior
        assert "已研究 1 轮" in prior
        # 降级轮不当既有判断喂给模型（真实验收里 429 降级模板曾被当成「上轮结论」）。
        assert "上轮未形成可用结论（按证据边界降级），不要把它当既有判断。" in prior
        assert "上轮结论标题" not in prior
        assert "未解问题：1.6T 订单口径" in prior
        # label 是压缩过的短标签（去空格、≤20 字），先验块里引用的就是它。
        assert f"本轮延续：补关键缺口「{gap_card['label']}」" in prior
        user_message = next(m for m in messages if m["run_id"] == created["run_id"] and m["role"] == "user")
        assert user_message["continuation"]["run_id"] == first_run
        assert user_message["continuation"]["kind"] == "gap_fill"
        second_cards = messages[-1]["followups"]
        # 上一张卡的原文不再被生成成同义改写。
        assert all(card["full_prompt"] != gap_card["full_prompt"] for card in second_cards)
        run2 = client.get(f"/api/runs/{created['run_id']}", params={"user": "alice"}).json()
        assert run2["parent_run_id"] == first_run

        project = _project(client, cid)
        assert project["completed_rounds"] == 2
        assert project["rounds"][1]["continuation"]["kind"] == "gap_fill"
        assert project["open_questions"] == ["1.6T 订单口径"]  # 最近有缺口的一轮仍是轮 1

    # 服务重启：新进程、同一用户目录。已完成节点全在，不需要用户重贴背景。
    restarted = RecordingAdapter()
    _install(monkeypatch, restarted)
    with TestClient(create_app(repo_root=_REPO_ROOT)) as client:
        recovered = _project(client, cid)
        assert recovered["completed_rounds"] == 2
        assert [r["run_id"] for r in recovered["rounds"]] == [r["run_id"] for r in project["rounds"]]
        assert recovered["current_judgment"] == project["current_judgment"]

        _, messages = _send(client, cid, "接着昨天的光模块研究，只报变化和下一步")
        assert "已研究 2 轮" in restarted.contexts[0]
        assert "上轮结论标题：第2轮判断：光模块主线延续。" in restarted.contexts[0]
        assert _project(client, cid)["completed_rounds"] == 3


def test_continuation_must_reference_a_run_of_this_conversation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _env(monkeypatch, tmp_path)
    _install(monkeypatch, RecordingAdapter())

    with TestClient(create_app(repo_root=_REPO_ROOT)) as client:
        first = client.post("/api/conversations", json={"title": "甲", "user": "alice"}).json()["conversation_id"]
        second = client.post("/api/conversations", json={"title": "乙", "user": "alice"}).json()["conversation_id"]
        _, messages = _send(client, first, "光模块怎么看")
        run_of_first = messages[-1]["run_id"]

        body = {
            "content": "继续",
            "skill_mode": "hybrid",
            "selected_skill_ids": [],
            "user": "alice",
        }
        missing = client.post(
            f"/api/conversations/{first}/messages",
            json={**body, "continuation": {"run_id": "run_20990101_000000_000000", "kind": "gap_fill"}},
        )
        assert missing.status_code == 422
        foreign = client.post(
            f"/api/conversations/{second}/messages",
            json={**body, "continuation": {"run_id": run_of_first, "kind": "gap_fill"}},
        )
        assert foreign.status_code == 422
        unknown_kind = client.post(
            f"/api/conversations/{first}/messages",
            json={**body, "continuation": {"run_id": run_of_first, "kind": "paraphrase"}},
        )
        assert unknown_kind.status_code == 422
        # 被拒的请求不能留下悬空 run / 消息。
        assert len(client.get(f"/api/conversations/{second}/messages", params={"user": "alice"}).json()) == 0


def test_two_users_same_topic_do_not_share_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _env(monkeypatch, tmp_path)
    adapter = RecordingAdapter()
    _install(monkeypatch, adapter)

    with TestClient(create_app(repo_root=_REPO_ROOT)) as client:
        alice = client.post("/api/conversations", json={"title": "光模块", "user": "alice"}).json()["conversation_id"]
        _send(client, alice, "光模块这个题材近三个月怎么演绎", user="alice")
        _send(client, alice, "光模块 800G 这条线谁的订单最硬", user="alice")

        bob = client.post("/api/conversations", json={"title": "光模块", "user": "bob"}).json()["conversation_id"]
        _send(client, bob, "光模块这个题材近三个月怎么演绎", user="bob")

        assert "研究项目状态" not in adapter.contexts[2]  # bob 首轮看不到 alice 的先验
        assert _project(client, bob, user="bob")["completed_rounds"] == 1
        assert _project(client, alice, user="alice")["completed_rounds"] == 2
        assert client.get(
            f"/api/conversations/{alice}/research-project", params={"user": "bob"}
        ).status_code == 404
