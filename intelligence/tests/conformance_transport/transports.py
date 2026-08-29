"""参数表（按 transport，禁按厂商名）+ 声明表 + 两路传输的探针替身。

缝：``llm_refine.complete()`` 的返回契约 ``(content, provider, reason)`` ×
两个独立演化的传输实现——HTTP OpenAI-compatible（``_post_chat``，urllib）
与 CLI judge（``grok_cli_judge.complete_grok_cli``，子进程）。

**按 transport 参数化，禁止按厂商名参数化**：``_PROVIDERS`` 的 8 个厂商槽
共用同一条 HTTP 路径，是配置不是实现（缝普查已定性，别重新发现）。

零网络：HTTP 路 = 假 ``urlopen``（在 ``llm_refine`` 模块面替换，让
``_post_chat`` 的 headers/payload/timeout 组装真实走过）；CLI 路 = 假
``subprocess.run``（在 ``grok_cli_judge`` 模块面替换 + 假二进制解析，让
prompt 落盘/argv 组装/stdout 提取真实走过）——两路都只截最外层 IO 边界。

provider 注入走官方缝 ``llm_refine.provider_override``（ContextVar），
不碰 env 键；预算/台账走 ``call_ledger_scope``。
"""

from __future__ import annotations

import io
import json
import subprocess
import urllib.error
from dataclasses import dataclass, field

import pytest

from intelligence.services import grok_cli_judge, llm_refine
from intelligence.services.llm_refine import LLMProvider

TRANSPORT_NAMES: tuple[str, ...] = ("http", "cli")

LT_INVARIANT_IDS: tuple[str, ...] = ("LT-1", "LT-2", "LT-3", "LT-4", "LT-5")

TRANSPORT_DECLARATIONS: dict[str, dict[str, str]] = {
    name: {inv: "supported" for inv in LT_INVARIANT_IDS}
    for name in TRANSPORT_NAMES
}
TRANSPORT_NOTES: dict[str, str] = {
    "http": (
        "失败分类：HTTPError → reason 带状态码（LLM 调用 HTTP 500），其余异常"
        "带类型名（LLM 调用失败（URLError））。8 个厂商槽共用本路径。"
    ),
    "cli": (
        "两条已声明偏差：①超时地板 max(1.0, timeout)——预算残窗 <1s 时子进程"
        "仍可跑满 1s（防退化超时的设计取舍，LT-3 按此断言）；②故障种类由异常"
        "**类名**承载（GrokCliExit/GrokCliEmptyResponse/...），因为 complete()"
        " 只把类型名透传进 reason（2026-08-27 生产 8/38 教训，类注释在案）。"
    ),
}

SECRET = "sk-conf-secret-XYZ"


def make_provider(transport: str) -> LLMProvider:
    if transport == "http":
        return LLMProvider(
            name="conf-http",
            api_key=SECRET,
            base_url="https://conformance.invalid/v1",
            model="conf-model",
        )
    return LLMProvider(
        name="grok-cli-judge",
        api_key=SECRET,  # CLI 实际不用 key；放进去正为断言它不外泄
        base_url=grok_cli_judge.CLI_GROK_URL,
        model="conf-grok",
        transport="cli",
    )


@dataclass
class TransportProbe:
    """记录传输边界收到的调用与超时。"""

    invocations: int = 0
    timeouts: list[float] = field(default_factory=list)


class _FakeHttpResponse:
    def __init__(self, content: str) -> None:
        self._body = json.dumps(
            {"choices": [{"message": {"content": content}}]}
        ).encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_FakeHttpResponse":
        return self

    def __exit__(self, *_exc: object) -> None:
        return None


def install_transport(
    monkeypatch: pytest.MonkeyPatch,
    transport: str,
    probe: TransportProbe,
    *,
    content: str = "探针答案",
    failure: str | None = None,
) -> None:
    """在最外层 IO 边界装探针。``failure``：http_500/网络异常/cli_exit/cli_empty。"""

    if transport == "http":

        def fake_urlopen(request, timeout: float = 0.0):
            probe.invocations += 1
            probe.timeouts.append(float(timeout))
            if failure == "http_500":
                raise urllib.error.HTTPError(
                    request.full_url, 500, "boom", None, io.BytesIO(b"")
                )
            if failure == "transport_error":
                raise urllib.error.URLError("connection refused")
            return _FakeHttpResponse(content)

        monkeypatch.setattr(llm_refine.urllib.request, "urlopen", fake_urlopen)
        return

    monkeypatch.setattr(
        grok_cli_judge, "resolve_grok_binary", lambda env=None: "/fake/grok"
    )

    def fake_run(argv, **kwargs):
        probe.invocations += 1
        probe.timeouts.append(float(kwargs.get("timeout") or 0.0))
        if failure == "cli_exit":
            return subprocess.CompletedProcess(
                args=argv, returncode=3, stdout="", stderr="cli 炸了"
            )
        if failure == "cli_empty":
            return subprocess.CompletedProcess(
                args=argv, returncode=0, stdout="", stderr=""
            )
        return subprocess.CompletedProcess(
            args=argv,
            returncode=0,
            stdout=json.dumps({"text": content}, ensure_ascii=False),
            stderr="",
        )

    # 注意不能 patch ``grok_cli_judge.subprocess.run``：``complete_grok_cli``
    # 的 ``runner=subprocess.run`` 默认参数在**函数定义时**就绑定了真身，
    # 事后改模块属性打不进去。走它自己的 ``runner=`` 注入缝，包一层转发——
    # ``llm_refine._complete_cli_judge`` 是调用点内 late import，patch 模块
    # 属性对它生效；argv 组装/提示词落盘/stdout 提取全走原码。
    original_complete = grok_cli_judge.complete_grok_cli

    def patched_complete(provider, messages, timeout):
        return original_complete(provider, messages, timeout, runner=fake_run)

    monkeypatch.setattr(grok_cli_judge, "complete_grok_cli", patched_complete)


# 每路一个「传输层真实失败」形状与其在 complete() reason 里的期望投影。
FAILURE_CASES: dict[str, tuple[str, str]] = {
    "http": ("http_500", "LLM 调用 HTTP 500"),
    "cli": ("cli_exit", "LLM 调用失败（GrokCliExit）"),
}


def run_complete(
    transport: str,
    monkeypatch: pytest.MonkeyPatch,
    probe: TransportProbe,
    *,
    timeout: float = 30.0,
    content: str = "探针答案",
    failure: str | None = None,
    max_calls: int | None = None,
) -> tuple[
    tuple[str | None, LLMProvider | None, str],
    "llm_refine.LLMCallLedger",
]:
    """标准驱动：override provider + 台账作用域 + 探针传输，跑一次 complete()。"""

    provider = make_provider(transport)
    install_transport(
        monkeypatch, transport, probe, content=content, failure=failure
    )
    with llm_refine.call_ledger_scope(max_calls=max_calls) as ledger:
        with llm_refine.provider_override(provider):
            result = llm_refine.complete(
                [{"role": "user", "content": "conformance 探针问题"}],
                timeout=timeout,
            )
    return result, ledger
