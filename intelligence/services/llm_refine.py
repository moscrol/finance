"""Optional LLM refinement of the `ask` 结论 / 交易含义 sections.

The deterministic retrieval skeleton (``ask.py``) always produces a templated
``结论`` / ``交易含义``. When an LLM credential is configured *and* the caller opts
in (``--llm`` / ``AskOptions.use_llm``), this module rewrites just those two
sections from the already-retrieved, citation-numbered evidence — it never adds
new retrieval, never invents companies/numbers, and must keep ``[编号]`` citations.

Design constraints:
- **Graceful degrade is the default.** If no provider/key is detected, or the
  call/parse fails, :func:`refine` returns ``None`` and the caller keeps the
  template. Behaviour with no key is therefore identical to before.
- **Zero extra dependencies.** Uses ``urllib`` against an OpenAI-compatible
  ``/chat/completions`` endpoint, so it works for DeepSeek / Moonshot(Kimi) /
  DashScope(Qwen) / Zhipu(GLM) / OpenAI and any compatible gateway without
  installing an SDK.
- **No secrets in code.** Keys come only from environment variables.
"""

from __future__ import annotations

import json
import os
import random
import re
import threading
import socket
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field, replace

DEFAULT_LLM_TIMEOUT = int(os.environ.get("LLM_TIMEOUT", "60"))
# 发起一次非流式调用所需的最小可行秒数。低于此值不发 HTTP，直接返回降级
# reason —— 明知不够还发，等于既烧掉这段时间又拿不到结果。
#
# 默认 15s 的依据（29 个真实 run 的 llm_call_ledger 实测）：
#   chat 成功耗时 中位 7.1s / p90 11.6s / max 14.5s
#   chat 失败耗时 p10 12.0s ≈ 中位 12.1s —— 紧贴被钳制的预算值，即"给的时间
#   刚好不够"。给不到 15s 时成功率急剧下降，不如把时间留给最终合成。
MIN_VIABLE_LLM_SECONDS = float(os.environ.get("LLM_MIN_VIABLE_SECONDS", "15"))
# The provider budget includes structured claim markers that are removed before
# display.  A visible 1,200-1,800 character answer can therefore exceed 2,200
# model tokens even though the user-facing response is still concise.
DEFAULT_SYNTHESIS_MAX_TOKENS = int(os.environ.get("LLM_SYNTHESIS_MAX_TOKENS", "3000"))
DEFAULT_SYNTHESIS_MAX_CHARS = int(os.environ.get("LLM_SYNTHESIS_MAX_CHARS", "16000"))
_ALLOWED_FINISH_REASONS = {"stop", "length", "content_filter", "tool_calls", "function_call"}

# 每个出站请求都必须自报身份。不设时 urllib 会发 ``Python-urllib/3.12``，
# 而中转/网关普遍把那个默认值当作脚本流量拦掉——实测同一把 key、同一个 URL、
# 同一份 body，只改 UA 就能从 502 变 200：
#   Python-urllib/3.12      -> 502 upstream_error（Upstream access forbidden）
#   finance-workbench/1.0   -> 200
# 症状极具误导性：错误码是 502（看起来像上游挂了），而 curl 手测恒通，于是很容易
# 误判成"网关不稳定"。这里刻意用自己的名字而不是伪装成 curl/openai-python：
# 目的是不被默认值误伤，不是绕过对方的客户端识别。
_LLM_USER_AGENT = os.environ.get("LLM_USER_AGENT", "finance-workbench/1.0")


def _llm_request_headers(
    provider: LLMProvider,
    **extra: str,
) -> dict[str, str]:
    """Return the shared outbound header set for one provider call."""

    headers = {
        "Authorization": f"Bearer {provider.api_key}",
        "Content-Type": "application/json",
        "User-Agent": _LLM_USER_AGENT,
    }
    headers.update(extra)
    return headers

# (provider, api_key_env, default_base_url, default_model). First env var that is
# set wins. A generic LLM_API_KEY (+ LLM_BASE_URL / LLM_MODEL) overrides all.
_PROVIDERS: tuple[tuple[str, str, str, str], ...] = (
    ("deepseek", "DEEPSEEK_API_KEY", "https://api.deepseek.com/v1", "deepseek-chat"),
    ("moonshot", "MOONSHOT_API_KEY", "https://api.moonshot.cn/v1", "moonshot-v1-8k"),
    ("kimi", "KIMI_API_KEY", "https://api.moonshot.cn/v1", "moonshot-v1-8k"),
    ("dashscope", "DASHSCOPE_API_KEY", "https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-plus"),
    ("qwen", "QWEN_API_KEY", "https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-plus"),
    ("zhipu", "ZHIPU_API_KEY", "https://open.bigmodel.cn/api/paas/v4", "glm-5.2"),
    ("glm", "GLM_API_KEY", "https://open.bigmodel.cn/api/paas/v4", "glm-5.2"),
    ("openai", "OPENAI_API_KEY", "https://api.openai.com/v1", "gpt-4o-mini"),
)


@dataclass
class LLMProvider:
    name: str
    api_key: str = field(repr=False)
    base_url: str
    model: str


_PROVIDER_OVERRIDE: ContextVar[LLMProvider | None] = ContextVar(
    "llm_provider_override",
    default=None,
)


class LLMStreamCancelled(RuntimeError):
    pass


class LLMStreamingUnsupported(RuntimeError):
    pass


class LLMDeadlineExceeded(RuntimeError):
    pass


class LLMOutputTooLong(RuntimeError):
    pass


class LLMCallBudgetExceeded(RuntimeError):
    """Raised before an HTTP attempt when the turn-level call budget is spent."""


@dataclass(frozen=True)
class Deadline:
    expires_at: float

    @classmethod
    def from_timeout(cls, timeout: float) -> "Deadline":
        return cls(time.monotonic() + max(0.0, float(timeout)))

    def remaining(self) -> float:
        return max(0.0, self.expires_at - time.monotonic())

    def require_remaining(self, minimum: float = 0.0) -> float:
        remaining = self.remaining()
        if remaining < minimum:
            raise LLMDeadlineExceeded()
        return remaining

    def call_timeout(self, timeout: float, *, minimum: float = 1.0) -> float:
        """本次调用真正的超时 = min(调用方给的时间片, 共享 deadline 剩余)。

        修一个静默失效：``timeout`` 参数此前只在 ``deadline is None`` 时被用来
        构造 Deadline（``deadline or Deadline.from_timeout(timeout)``）。一旦调用
        方显式传 deadline —— grounded 三段链一直这么传 —— 时间片就只是个装饰，
        每一段都能吃掉整条 deadline。

        实测代价（2026-08-03 单题）：brief 分到 22s 片、实际跑了 69.7s，composer
        进场只剩 20.2s，必然超时降级。分片算得很认真，消费端根本没读——预算字段
        必须在**强制点**被读取，只是「传下去了」不等于「被执行了」。
        """

        remaining = self.require_remaining(minimum)
        limit = max(0.0, float(timeout or 0.0))
        return min(remaining, limit) if limit > 0 else remaining


def detect_providers(model_override: str | None = None) -> tuple[LLMProvider, ...]:
    """Resolve configured providers in deterministic fallback order."""
    configured = _PROVIDER_OVERRIDE.get()
    if configured is not None:
        if model_override:
            return (replace(configured, model=model_override),)
        return (configured,)
    generic = os.environ.get("LLM_API_KEY")
    if generic:
        base = os.environ.get("LLM_BASE_URL") or os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1"
        model = model_override or os.environ.get("LLM_MODEL") or "gpt-4o-mini"
        return (LLMProvider(name="custom", api_key=generic, base_url=base, model=model),)
    providers: list[LLMProvider] = []
    seen: set[tuple[str, str, str]] = set()
    managed_key = os.environ.get("FORESIGHT_BUILTIN_LLM_API_KEY")
    if managed_key:
        managed_base_url = (
            os.environ.get("FORESIGHT_BUILTIN_LLM_BASE_URL")
            or "https://open.bigmodel.cn/api/coding/paas/v4"
        )
        managed_model = (
            model_override
            or os.environ.get("FORESIGHT_BUILTIN_LLM_MODEL")
            or "glm-5.2"
        )
        providers.append(
            LLMProvider(
                name="zhipu",
                api_key=managed_key,
                base_url=managed_base_url,
                model=managed_model,
            )
        )
        seen.add((managed_key, managed_base_url, managed_model))
    for name, env_key, base, default_model in _PROVIDERS:
        key = os.environ.get(env_key)
        if key:
            base_url = os.environ.get("LLM_BASE_URL") or os.environ.get("OPENAI_BASE_URL") or base
            model = model_override or os.environ.get("LLM_MODEL") or default_model
            identity = (key, base_url, model)
            if identity in seen:
                continue
            seen.add(identity)
            providers.append(
                LLMProvider(
                    name=name,
                    api_key=key,
                    base_url=base_url,
                    model=model,
                )
            )
    return tuple(providers)


def detect_provider(model_override: str | None = None) -> LLMProvider | None:
    """Resolve the preferred LLM provider from environment variables."""
    return next(iter(detect_providers(model_override)), None)


def judge_provider() -> LLMProvider | None:
    """语义审（grounding judge / evidence judge）的独立 provider 解析。

    背景（双审查 ③）：composer 与 judge 走同一 provider 存在相关性失败——
    同一模型的系统性偏差会同时骗过创作与审稿。配置以下 env 后语义审走
    独立模型；未配置返回 None，调用方回落主 provider（行为不变）：
    - ``LLM_JUDGE_API_KEY``（+ ``LLM_JUDGE_BASE_URL`` + ``LLM_JUDGE_MODEL``）：
      完全独立的 judge 端点；
    - 仅 ``LLM_JUDGE_MODEL``：同 key/端点、不同模型（次优但仍降低相关性）。
    """
    key = os.environ.get("LLM_JUDGE_API_KEY")
    base = os.environ.get("LLM_JUDGE_BASE_URL")
    model = os.environ.get("LLM_JUDGE_MODEL")
    if key:
        return LLMProvider(
            name="judge",
            api_key=key,
            base_url=base or "https://api.openai.com/v1",
            model=model or "gpt-4o-mini",
        )
    if model:
        main = detect_provider(None)
        if main is not None and main.model != model:
            return replace(main, name=f"{main.name}-judge", model=model)
    return None


def _provider_failure_reason(
    failures: list[tuple[LLMProvider, str]],
) -> tuple[LLMProvider, str]:
    provider, last_reason = failures[-1]
    if len(failures) == 1:
        return provider, last_reason
    summary = "；".join(
        f"{failed_provider.name}:{reason.removeprefix('LLM 调用 ')}"
        for failed_provider, reason in failures
    )
    return provider, f"所有已配置 LLM provider 均失败（{summary}）"


def stable_llm_fallback_reason(reason: str) -> str:
    """把本模块产出的降级 reason 压成稳定枚举，供 trace 聚合与策略判定。

    住在这里而不是调用方，是因为它解析的就是本模块自己写出的字符串——两者分开
    放的代价已经付过一次：``complete()`` 用的是「LLM 调用失败（XxxError）」，
    ``synthesize_messages()`` 用的是「LLM 合成超过共享截止时间」，改产出串的人
    看不到解析器，于是前者的超时至今被归进 ``provider_unavailable``。

    已知未覆盖：``LLM 调用失败（TimeoutError）`` / ``LLM 预算不足`` 都会落进
    ``provider_unavailable``。**不要顺手补规则**——本函数同时是 judge 的
    fail-closed 闸门（``_TRANSIENT_JUDGE_REASONS``），多认一个瞬时原因就等于
    放宽一次严格层。要改先补 judge 侧的测试。
    """
    normalized = str(reason or "").casefold()
    if "未配置" in normalized:
        return "provider_unavailable"
    # 本轮调用预算耗尽（``LlmCallLedger.rejection_reason``）。原先落进
    # provider_unavailable，跟「没配 key」混成一类——但两者的处置完全相反：
    # 没配 key 是配置问题该 fail-closed，预算耗尽时被审对象是无辜的。
    if "预算耗尽" in normalized:
        return "call_budget_exhausted"
    # 「共享截止时间」是**我们自己**的 deadline 走完了，不是对方慢。原先跟 provider
    # 侧超时塌成一个 ``timeout``，而 ``timeout`` 在 judge 的瞬时故障白名单里——于是
    # 自家预算饥饿被当成「供应商瞬时故障」放行，答案带一句「服务瞬时问题」发出去。
    #
    # 分界线跟本函数里 HTTP 那条一样，问的是「被审对象是不是无辜的」：供应商抖一下
    # 是例外，放行合理；自家 deadline 不够是常态（2026-08-02 那批 23 轮里 15 轮命中），
    # 放行就从例外变成常态——按注释里既有的判据，这类必须 fail-closed。
    if "截止时间" in normalized:
        return "deadline_exhausted_local"
    # 预算不够所以**没发**这次调用（准入检查拦下），跟「发了但超时」不是一回事：
    # 前者一秒没浪费，后者把剩余预算烧完才降级。加这条不放宽 judge 闸门——它不在
    # 瞬时故障白名单里，仍然 fail-closed；加它只是为了不让这类事件塌进
    # ``provider_unavailable``，那才是又一次「把自家限额记成供应商挂了」。
    if "剩余预算不足" in normalized:
        return "insufficient_budget"
    if "超时" in normalized:
        return "timeout"
    if "输出超长" in normalized or "too long" in normalized:
        return "output_too_long"
    if "截断" in normalized or "length" in normalized:
        return "truncated_response"
    if "未正常停止" in normalized or "stalled" in normalized:
        return "provider_stalled"
    # HTTP 按状态码分类，不要塌成一类。产生点（``LLM 合成 HTTP {code}`` /
    # ``LLM 调用 HTTP {code}``）本来就知道是 400 还是 529，而这两者的处置相反：
    # 429/5xx 是「那边出了事」，被审对象无辜；4xx 其余是「我们这次请求本身有问题」，
    # 重试和放行都不对。塌成一类的后果是 HTTP 400 也会走瞬时故障放行。
    http_code = re.search(r"http\s*(\d{3})", normalized)
    if http_code is not None:
        code = int(http_code.group(1))
        if code == 429:
            return "provider_rate_limited"
        if code >= 500:
            return "provider_overloaded"
        return "provider_request_rejected"
    if "http" in normalized:
        return "provider_http_error"
    if "空内容" in normalized:
        return "empty_response"
    return "provider_unavailable"


@contextmanager
def provider_override(provider: LLMProvider) -> Iterator[None]:
    token = _PROVIDER_OVERRIDE.set(provider)
    try:
        yield
    finally:
        _PROVIDER_OVERRIDE.reset(token)


# --- LLM 调用台账（P1-B 预算记账）------------------------------------------
# 背景：turn 级预算此前只统计 skill 次数，一个 research turn 实际可触发十余次
# LLM 调用（controller/judge/agent loop/planner/合成/修订/影子链）却没有任何
# 一本账在管。此处在 _post_chat* 底层入口按「provider 尝试」粒度记账（fallback
# 轮换的每次 HTTP 尝试都算一次），turn 级用 ContextVar 聚合——跨线程记账由
# 调用方用 contextvars.copy_context() 传播（台账对象共享，list.append 原子）。


@dataclass(frozen=True)
class LLMCallRecord:
    caller: str  # chat | chat_tools | synthesis | synthesis_stream
    provider: str
    model: str
    status: str  # success | failed
    elapsed_ms: int
    # 失败原因（成功为空）。不记原因就无法回答"为什么 35% 的 chat 调用失败"，
    # 诊断只能靠猜 elapsed_ms 的分布。
    reason: str = ""


@dataclass
class LLMCallLedger:
    records: list[LLMCallRecord] = field(default_factory=list)
    # 硬预算（P1-B 消费闭环）：非 None 时，尝试数达到上限后新调用被拒发
    # （入口直接返回降级 reason，不发 HTTP）。防失控为主，默认上限宽松。
    max_calls: int | None = None
    rejected_count: int = 0
    _reservation_count: int = 0
    _lock: threading.Lock = field(
        default_factory=threading.Lock,
        repr=False,
        compare=False,
    )

    def over_budget(self) -> bool:
        with self._lock:
            return (
                self.max_calls is not None
                and self._reservation_count >= self.max_calls
            )

    def try_reserve(self) -> bool:
        """Atomically reserve one real provider attempt.

        Completed records are too late to enforce a concurrent limit: two
        callers can both observe the same record count before either finishes.
        Reservations are cumulative for the turn, so fallback/retry calls each
        consume one slot and in-flight calls count immediately.
        """
        with self._lock:
            if (
                self.max_calls is not None
                and self._reservation_count >= self.max_calls
            ):
                self.rejected_count += 1
                return False
            self._reservation_count += 1
            return True

    def rejection_reason(self) -> str:
        return (
            f"LLM 调用预算耗尽（本轮上限 {self.max_calls} 次尝试），"
            "已拒发新调用并降级"
        )

    def reject(self) -> str:
        with self._lock:
            self.rejected_count += 1
        return self.rejection_reason()

    def record(self, record: LLMCallRecord) -> None:
        with self._lock:
            self.records.append(record)

    def summary(self) -> dict[str, object]:
        with self._lock:
            records = list(self.records)
            reservation_count = self._reservation_count
            rejected_count = self.rejected_count
        by_caller: dict[str, int] = {}
        for record in records:
            by_caller[record.caller] = by_caller.get(record.caller, 0) + 1
        return {
            "call_count": len(records),
            "reserved_count": reservation_count,
            "failure_count": sum(
                1 for record in records if record.status != "success"
            ),
            "total_elapsed_ms": sum(
                record.elapsed_ms for record in records
            ),
            "max_calls": self.max_calls,
            "rejected_count": rejected_count,
            "by_caller": by_caller,
            "failure_reasons": _tally_failure_reasons(records),
            "records": [
                {
                    "caller": record.caller,
                    "provider": record.provider,
                    "model": record.model,
                    "status": record.status,
                    "elapsed_ms": record.elapsed_ms,
                    **({"reason": record.reason} if record.reason else {}),
                }
                for record in records
            ],
        }


def _insufficient_budget_reason(
    timeout: float,
    min_viable_seconds: float | None,
) -> str | None:
    """预算不足以支撑一次调用时返回降级 reason，否则 None。

    与"发出去然后超时"的区别：这里一秒都不烧，把时间留给还能成功的阶段
    （通常是最终合成）。

    ``min_viable_seconds`` 为 None 时不设闸门——这是默认值，因为 ``timeout``
    参数本身无法区分两种来源：调用方主动配置的策略超时（该照发），和被
    deadline 钳制后剩下的残余预算（该跳过）。只有知道自己处在预算压力下的
    调用方才该显式传入（见 MIN_VIABLE_LLM_SECONDS 的实测依据）。
    """
    if min_viable_seconds is None or timeout >= min_viable_seconds:
        return None
    return (
        f"LLM 预算不足（剩余 {timeout:.1f}s < 最小可行 "
        f"{min_viable_seconds:.0f}s），已跳过调用以保留合成预算"
    )


def _tally_failure_reasons(records: list[LLMCallRecord]) -> dict[str, int]:
    """按原因聚合失败次数，让 trace 一眼看出是超时、限流还是别的。"""
    tally: dict[str, int] = {}
    for record in records:
        if record.status == "success":
            continue
        key = record.reason or "unknown"
        tally[key] = tally.get(key, 0) + 1
    return tally


_CALL_LEDGER: ContextVar[LLMCallLedger | None] = ContextVar(
    "llm_call_ledger",
    default=None,
)


@contextmanager
def call_ledger_scope(
    max_calls: int | None = None,
) -> Iterator[LLMCallLedger]:
    """开启 turn 级 LLM 调用台账；已有活动台账时复用（不重置嵌套作用域）。

    ``max_calls`` 只在新建台账时生效；嵌套复用时以外层限额为准。"""
    existing = _CALL_LEDGER.get()
    if existing is not None:
        yield existing
        return
    ledger = LLMCallLedger(max_calls=max_calls)
    token = _CALL_LEDGER.set(ledger)
    try:
        yield ledger
    finally:
        _CALL_LEDGER.reset(token)


def _budget_rejection() -> str | None:
    """入口预算检查：超额时返回拒发 reason，未超额/无台账返回 None。"""
    ledger = _CALL_LEDGER.get()
    if ledger is not None and ledger.over_budget():
        return ledger.reject()
    return None


def _reserve_llm_call() -> None:
    """Reserve one attempt at the actual HTTP boundary.

    Public-entry checks remain a cheap fast path, but this reservation is the
    authoritative guard because provider fallback, retries and concurrent
    callers can all pass an earlier check.
    """
    ledger = _CALL_LEDGER.get()
    if ledger is not None and not ledger.try_reserve():
        raise LLMCallBudgetExceeded(ledger.rejection_reason())


def current_call_ledger() -> LLMCallLedger | None:
    return _CALL_LEDGER.get()


# 重试退避。ch06b «API 通信层»：CC 用 BASE_DELAY_MS=500 的指数退避，并在每次退避上
# **叠加 0-25% 随机抖动**，避免多个客户端在同一时刻同步重试造成雷群（thundering
# herd）。我们这边的并发是真实的：API 有 2 个 worker，skill 线程经 copy_context
# 共享同一本调用台账，同一次 provider 抖动会让它们在同一毫秒一起失败、一起重试。
#
# **次数没有跟着抄。** CC 的预算是 10 次（总等待 2.5-3 分钟），那是 CLI 场景、
# 用户在前面等；我们每次尝试都要占一次 turn 级台账额度，而 LLM 是 5 小时滚动配额。
# 保持今天的 2 次，只把间隔从写死的 2 秒换成有依据的退避——用户要的是退避与抖动，
# 不是多花配额。将来有数据支持再调 _RETRY_MAX_ATTEMPTS。
_RETRY_BASE_DELAY_S = 0.5
_RETRY_MAX_DELAY_S = 4.0
_RETRY_JITTER = 0.25
_RETRY_MAX_ATTEMPTS = 2


def _retry_delay_seconds(attempt: int) -> float:
    """第 ``attempt`` 次失败后等多久（attempt 从 0 起）。"""

    base = min(_RETRY_MAX_DELAY_S, _RETRY_BASE_DELAY_S * (2**attempt))
    return base * (1.0 + random.random() * _RETRY_JITTER)


def _failure_reason(exc: BaseException) -> str:
    """把异常压成一行可聚合的原因，供台账统计（不含 URL/密钥等敏感串）。"""
    if isinstance(exc, urllib.error.HTTPError):
        return f"http_{exc.code}"
    if isinstance(exc, TimeoutError) or isinstance(exc, socket.timeout):
        return "timeout"
    if isinstance(exc, urllib.error.URLError):
        inner = getattr(exc, "reason", None)
        if isinstance(inner, (TimeoutError, socket.timeout)):
            return "timeout"
        return f"urlerror_{type(inner).__name__ if inner else 'unknown'}"
    return type(exc).__name__


def _record_llm_call(
    caller: str,
    provider: LLMProvider,
    status: str,
    started: float,
    reason: str = "",
) -> None:
    ledger = _CALL_LEDGER.get()
    if ledger is None:
        return
    ledger.record(
        LLMCallRecord(
            caller=caller,
            provider=provider.name,
            model=provider.model,
            status=status,
            elapsed_ms=max(0, round((time.monotonic() - started) * 1000)),
            reason=reason,
        )
    )


def synthesis_thinking_disabled() -> bool:
    configured = os.environ.get("LLM_SYNTHESIS_THINKING")
    if configured is None:
        return os.environ.get("LLM_THINKING", "").lower() != "enabled"
    return configured.lower() == "disabled"


def _stable_finish_reason(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    reason = value.strip()
    if reason in _ALLOWED_FINISH_REASONS:
        return reason
    return None


_SYSTEM_PROMPT = (
    "你是严谨的A股题材研究助手。任务：仅依据用户给出的「带编号证据」改写两段——"
    "【结论】和【交易含义】。硬性要求："
    "1) 只能使用证据中出现的事实/公司/数字，严禁引入证据里没有的内容；"
    "2) 每条关键判断后必须标注引用编号（如 [S1] [G3] [R2]），可多个；"
    "3) 不确定或证据不足时要显式说明「证据不足/仅盘面驱动」，不得编造；"
    "4) 不输出买卖指令，结尾以「（非投资建议）」收尾；"
    "5) 严格输出 JSON：{\"结论\": [\"...\"], \"交易含义\": [\"...\"]}，每个数组 1-4 条短句，不要输出额外文字。"
)


def _build_user_prompt(query: str, theme: str, evidence_text: str) -> str:
    return (
        f"题材问题：{query}\n"
        f"命中主题：{theme}\n\n"
        f"以下是已检索到的带编号证据（结论与交易含义只能据此改写）：\n"
        f"{evidence_text}\n\n"
        f"请据此输出 JSON。"
    )


def _post_chat(
    provider: LLMProvider,
    messages: list[dict],
    timeout: float,
    temperature: float = 0.2,
) -> str:
    _reserve_llm_call()
    url = provider.base_url.rstrip("/") + "/chat/completions"
    payload = {"model": provider.model, "messages": messages, "temperature": temperature}
    if os.environ.get("LLM_THINKING") == "disabled":
        payload["thinking"] = {"type": "disabled"}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers=_llm_request_headers(provider),
        method="POST",
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        _record_llm_call("chat", provider, "failed", started, _failure_reason(exc))
        raise
    _record_llm_call("chat", provider, "success", started)
    return body["choices"][0]["message"]["content"]


def _post_chat_synthesis(
    provider: LLMProvider,
    messages: list[dict],
    timeout: float,
    temperature: float,
    max_tokens: int,
    max_chars: int,
) -> tuple[str, str | None]:
    _reserve_llm_call()
    url = provider.base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": provider.model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if synthesis_thinking_disabled():
        payload["thinking"] = {"type": "disabled"}
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=_llm_request_headers(provider),
        method="POST",
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        _record_llm_call("synthesis", provider, "failed", started, _failure_reason(exc))
        raise
    choice = body["choices"][0]
    content = choice["message"]["content"]
    if len(content) > max_chars:
        _record_llm_call("synthesis", provider, "failed", started, "output_too_long")
        raise LLMOutputTooLong()
    _record_llm_call("synthesis", provider, "success", started)
    return content, _stable_finish_reason(choice.get("finish_reason"))


def complete(
    messages: list[dict],
    model_override: str | None = None,
    timeout: float = DEFAULT_LLM_TIMEOUT,
    temperature: float = 0.2,
    *,
    min_viable_seconds: float | None = None,
) -> tuple[str | None, "LLMProvider | None", str]:
    """Generic OpenAI-compatible chat call shared across services.

    Returns ``(content, provider, reason)``. On any failure (no key, HTTP error,
    network error) ``content`` is ``None`` and ``reason`` explains why so callers
    can degrade gracefully — same contract as :func:`refine_or_reason`.
    """
    rejection = _budget_rejection()
    if rejection is not None:
        return None, None, rejection
    providers = detect_providers(model_override)
    if not providers:
        return None, None, (
            "未配置 LLM key。设置 DEEPSEEK_API_KEY / MOONSHOT_API_KEY / "
            "DASHSCOPE_API_KEY / ZHIPU_API_KEY / OPENAI_API_KEY 或通用 "
            "LLM_API_KEY(+LLM_BASE_URL,+LLM_MODEL) 即可启用"
        )
    insufficient = _insufficient_budget_reason(timeout, min_viable_seconds)
    if insufficient is not None:
        return None, None, insufficient
    deadline = Deadline.from_timeout(timeout)
    failures: list[tuple[LLMProvider, str]] = []
    for provider in providers:
        try:
            remaining = deadline.require_remaining(0.001)
            content = _post_chat(provider, messages, remaining, temperature)
        except LLMCallBudgetExceeded as exc:
            return None, None, str(exc)
        except urllib.error.HTTPError as exc:  # pragma: no cover - network
            failures.append((provider, f"LLM 调用 HTTP {exc.code}"))
        except Exception as exc:  # pragma: no cover - network
            failures.append((provider, f"LLM 调用失败（{type(exc).__name__}）"))
        else:
            return content, provider, ""
        if deadline.remaining() <= 0:
            break
    provider, reason = _provider_failure_reason(failures)
    return None, provider, reason


def _post_chat_message(
    provider: LLMProvider,
    messages: list[dict],
    timeout: float,
    temperature: float = 0.2,
    tools: list[dict] | None = None,
    tool_choice: str | dict | None = None,
    disable_thinking: bool | None = None,
) -> dict:
    """Like :func:`_post_chat` but returns the full assistant *message* dict.

    The message may contain ``tool_calls`` (OpenAI-compatible function calling)
    in addition to / instead of ``content`` — needed to drive an agent loop."""
    _reserve_llm_call()
    url = provider.base_url.rstrip("/") + "/chat/completions"
    payload: dict = {"model": provider.model, "messages": messages, "temperature": temperature}
    if disable_thinking is True or (
        disable_thinking is None
        and os.environ.get("LLM_THINKING") == "disabled"
    ):
        payload["thinking"] = {"type": "disabled"}
    if tools:
        payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers=_llm_request_headers(provider),
        method="POST",
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        _record_llm_call(
            "chat_tools", provider, "failed", started, _failure_reason(exc)
        )
        raise
    _record_llm_call("chat_tools", provider, "success", started)
    message = dict(body["choices"][0]["message"])
    usage = body.get("usage")
    if isinstance(usage, dict):
        # Usage is adapter metadata only. Preserve counts without returning the
        # request prompt, provider body, or hidden reasoning payload.
        message["_usage"] = dict(usage)
    return message


def chat_with_tools(
    messages: list[dict],
    tools: list[dict],
    model_override: str | None = None,
    timeout: float = DEFAULT_LLM_TIMEOUT,
    temperature: float = 0.2,
    tool_choice: str | dict | None = "auto",
    disable_thinking: bool | None = None,
    min_viable_seconds: float | None = None,
) -> tuple[dict | None, "LLMProvider | None", str]:
    """One OpenAI-compatible chat round-trip *with tools available*.

    Returns ``(message, provider, reason)``; the agent loop inspects
    ``message["tool_calls"]`` to decide whether to dispatch tools or treat
    ``message["content"]`` as the final answer. On any failure ``message`` is
    ``None`` and ``reason`` explains why so the caller degrades gracefully."""
    rejection = _budget_rejection()
    if rejection is not None:
        return None, None, rejection
    providers = detect_providers(model_override)
    if not providers:
        return None, None, (
            "未配置 LLM key。设置 DEEPSEEK_API_KEY / MOONSHOT_API_KEY / "
            "DASHSCOPE_API_KEY / ZHIPU_API_KEY / OPENAI_API_KEY 或通用 "
            "LLM_API_KEY(+LLM_BASE_URL,+LLM_MODEL) 即可启用"
        )
    insufficient = _insufficient_budget_reason(timeout, min_viable_seconds)
    if insufficient is not None:
        return None, None, insufficient
    deadline = Deadline.from_timeout(timeout)
    failures: list[tuple[LLMProvider, str]] = []
    for provider in providers:
        try:
            remaining = deadline.require_remaining(0.001)
            msg = _post_chat_message(
                provider,
                messages,
                remaining,
                temperature,
                tools=tools,
                tool_choice=tool_choice,
                disable_thinking=disable_thinking,
            )
        except LLMCallBudgetExceeded as exc:
            return None, None, str(exc)
        except urllib.error.HTTPError as exc:  # pragma: no cover - network
            failures.append((provider, f"LLM 调用 HTTP {exc.code}"))
        except Exception as exc:  # pragma: no cover - network
            failures.append((provider, f"LLM 调用失败（{type(exc).__name__}）"))
        else:
            return msg, provider, ""
        if deadline.remaining() <= 0:
            break
    provider, reason = _provider_failure_reason(failures)
    return None, provider, reason


def _extract_json(text: str) -> dict | None:
    text = text.strip()
    # strip ```json fences if present
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    else:
        brace = re.search(r"\{.*\}", text, re.DOTALL)
        if brace:
            text = brace.group(0)
    try:
        obj = json.loads(text)
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def _as_lines(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


@dataclass
class RefineResult:
    conclusion: list[str]
    implication: list[str]
    provider: str
    model: str


def refine(
    query: str,
    theme: str,
    evidence_text: str,
    model_override: str | None = None,
    timeout: int = DEFAULT_LLM_TIMEOUT,
) -> RefineResult | None:
    """Rewrite 结论 / 交易含义 from retrieved evidence. Returns ``None`` to degrade.

    The second element of failures is surfaced to the caller via
    :func:`refine_or_reason` so the warning can explain *why* it degraded.
    """
    out, _ = refine_or_reason(query, theme, evidence_text, model_override, timeout)
    return out


def refine_or_reason(
    query: str,
    theme: str,
    evidence_text: str,
    model_override: str | None = None,
    timeout: int = DEFAULT_LLM_TIMEOUT,
) -> tuple[RefineResult | None, str]:
    provider = detect_provider(model_override)
    if provider is None:
        return None, (
            "未配置 LLM key，结论/交易含义降级为模板。设置 DEEPSEEK_API_KEY / "
            "MOONSHOT_API_KEY / DASHSCOPE_API_KEY / ZHIPU_API_KEY / OPENAI_API_KEY "
            "或通用 LLM_API_KEY(+LLM_BASE_URL,+LLM_MODEL) 即可启用精修"
        )
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": _build_user_prompt(query, theme, evidence_text)},
    ]
    try:
        content = _post_chat(provider, messages, timeout)
    except LLMCallBudgetExceeded as exc:
        return None, f"{exc}"
    except urllib.error.HTTPError as exc:  # pragma: no cover - network
        return None, f"LLM 调用 HTTP {exc.code}，已降级为模板"
    except Exception as exc:  # pragma: no cover - network
        return None, f"LLM 调用失败（{type(exc).__name__}），已降级为模板"
    obj = _extract_json(content)
    if not obj:
        return None, "LLM 返回无法解析为 JSON，已降级为模板"
    conclusion = _as_lines(obj.get("结论") or obj.get("conclusion"))
    implication = _as_lines(obj.get("交易含义") or obj.get("implication") or obj.get("trading_implication"))
    if not conclusion and not implication:
        return None, "LLM 返回缺少 结论/交易含义 字段，已降级为模板"
    return (
        RefineResult(
            conclusion=conclusion or ["（LLM 未给出结论，沿用模板）"],
            implication=implication or ["（LLM 未给出交易含义，沿用模板）"],
            provider=provider.name,
            model=provider.model,
        ),
        "",
    )


# --- 有机合成（compose）：把多源证据融成一段连贯的分析师口吻回答 ----------------
# 与 refine 的区别：refine 只重写 结论/交易含义 两段（仍是六段模板）；compose 让
# LLM 把 盘面/图谱/证据/语义召回/题材模块 有机融合成一段自由形态、带内联引用的回答，
# 更接近"对话式分析"。仍严守：只用给定证据、不编造、带引用编号、（非投资建议）。
_SYNTHESIS_SYSTEM_PROMPT = (
    "你是资深 A 股研究员。只消费给定 AnswerSpec 和证据，不能增加证据外的事实、"
    "先服从证据中的「问答编排计划」与 AnswerSpec，再按用户问题取舍；"
    "公司、数字、日期或催化。先直接回答用户问题，再按问题需要组织自然段落；"
    "事实句必须绑定合法 EvidenceAtom，推断、候选和缺口必须保持对应语气。"
    "claim marker 只用于机器核验，不要为了凑数量、标题或段数重排证据。"
    "结构、篇幅和小节由问题复杂度与证据形态决定，不强制六段、固定标题或正文行数。"
    "不能显示路径、表名、工具状态、证据计数、warning 或其他控制面字段；"
    "不得在正文显示任何内部引用编号、原始 JSON 或 L1/L2/L3/L4 代码，"
    "这些层级要转译成用户能理解的证据硬度；"
    "历史经验只作 prior，当前证据优先；缺数应明确写出缺口和验证窗口。"
    "不输出买卖指令，结尾以「（非投资建议）」收尾。"
)


@dataclass
class SynthesisResult:
    answer: str
    provider: str
    model: str
    fallback_reason: str | None = None
    finish_reason: str | None = None


def _build_synthesis_prompt(
    query: str,
    theme: str,
    evidence_text: str,
    citation_legend: str,
    quality_context: object | None = None,
    experience_guidance: str = "",
    exemplar_guidance: str = "",
) -> str:
    """Build the *user* turn content for synthesis.

    experience_guidance and exemplar_guidance are accepted for backward
    compatibility but are intentionally NOT inlined here — they are static
    blocks that belong in the system prompt (see build_synthesis_messages)
    to maximise prompt-cache hit rate.
    """
    legend = (
        "\n\n## 内部引用图例（只用于事实核验；最终回答不得显示编号）\n"
        f"{citation_legend}"
        if citation_legend
        else ""
    )
    quality_block = ""
    if quality_context is not None and hasattr(quality_context, "to_prompt_block"):
        quality_block = f"\n\n{quality_context.to_prompt_block()}"
    # experience/exemplar 两个静态块按 main 的做法移进 system prompt（见本函数
    # docstring 与 build_synthesis_messages），此处不再内联，以保 prompt-cache 命中。
    # cause_nudge 不同：它由 query 正则触发，是动态内容，放进 system prompt 会破坏
    # 缓存前缀，必须留在 user turn。
    cause_nudge = ""
    if re.search(r"(?:本周|这一周|这周|近一周|过去一周).{0,20}(?:行情|大盘|市场).{0,20}(?:下跌|走弱).{0,20}(?:原因|为什么|驱动|归因)", query):
        cause_nudge = (
            "\n\n## 原因归因题约束\n"
            "先用一句话直接回答‘本周下跌的主要机制/原因是什么’，再区分已由周内盘面证据确认的机制与仍缺外部触发证据；"
            "不得用最后一个交易日快照代替周窗口，不得把旧文章候选原因写成已核验事实，也不要追加用户未询问的交易策略、仓位或防御建议。"
        )
    return (
        f"用户问题：{query}\n"
        f"命中主题：{theme}\n\n"
        f"以下是已检索到的多源证据（你的回答只能据此展开）：\n"
        f"{evidence_text}{legend}{quality_block}{cause_nudge}\n\n"
        "请据此有机融合成一段分析师口吻的回答。优先给出直接判断，"
        "只使用真正回答问题所需的 claim；不要为了完整而逐条罗列 registry。"
    )


def build_synthesis_messages(
    query: str,
    theme: str,
    evidence_text: str,
    citation_legend: str = "",
    quality_context: object | None = None,
    experience_guidance: str = "",
    exemplar_guidance: str = "",
) -> list[dict]:
    """Assemble the turn-1 synthesis ``[system, user]`` messages.

    Static guidance blocks (experience_guidance, exemplar_guidance) are appended
    to the **system** prompt rather than the user prompt.  This keeps the large
    static prefix cacheable across different queries / evidence sets.

    Exposed so the multi-turn driver can keep the exact same evidence-laden first
    turn and then append follow-ups on top of it (grounding stays anchored to the
    evidence given here — follow-ups must not introduce new sources)."""
    # Build the static system prompt: base instructions + optional static blocks
    system_content = _SYNTHESIS_SYSTEM_PROMPT
    if experience_guidance:
        system_content += (
            "\n\n## 历史经验卡片（用于避免重复犯错）\n"
            f"{experience_guidance}"
        )
    if exemplar_guidance:
        system_content += (
            "\n\n## 高分样板（few-shot 锚：只学结构、叙事组织和论证方式；"
            "严禁照抄样板里的结论、数据或个股判断，回答只能基于上方证据）\n"
            f"{exemplar_guidance}"
        )
    return [
        {"role": "system", "content": system_content},
        {
            "role": "user",
            "content": _build_synthesis_prompt(
                query,
                theme,
                evidence_text,
                citation_legend,
                quality_context,
                # experience/exemplar now in system prompt; pass empty to
                # _build_synthesis_prompt for backward-compat (they are ignored).
            ),
        },
    ]


_DECISION_BRIEF_SYSTEM_PROMPT = (
    "你是投研总编辑，只负责形成论证计划，不写最终正文。"
    "只能使用用户提供的 claim registry，所有数组字段只能填写 registry 中存在的 claim_id。"
    "direct_answer 和 core_tension 可以自然表达，但不得加入 registry 外的公司、数字、日期或事实。"
    "registry 里若有公司/产业链映射类 claim（claim_id 以 company: 或 chain: 开头），"
    "必须把它们放进 chain_mapping，不得因为都还是候选、未获硬证据就整批省略——"
    "候选清单本身就是研究结论，省略它等于把「我库里有这 12 家」答成「什么都没有」。"
    "严格输出单个 JSON 对象，不要 Markdown："
    '{"direct_answer":"", "core_tension":"", "supports":[], '
    '"counterevidence":[], "unknowns":[], "upgrade_conditions":[], '
    '"downgrade_conditions":[], "chain_mapping":[]}。'
)

_GROUNDED_COMPOSER_SYSTEM_PROMPT = (
    "你是 A 股研究回答的 Grounded Composer。请围绕 DecisionBrief 回答用户原问题，"
    "拥有最终措辞、段落论证和自然衔接权，但只能使用 claim registry 中的事实和边界。"
    "每个正文段落或列表项必须单独一行，并在行末追加："
    "<!-- claim_ids=id1,id2; evidence_atom_ids=atom1,atom2; "
    "claim_type=fact|candidate|inference|expectation|gap -->。"
    "claim_ids 可绑定一条或多条；EvidenceAtom 只能使用这些 claim 自带的合法 ID。"
    "事实句必须绑定 EvidenceAtom；推断、候选和预期不得写成确定事实。"
    "标题和末尾「（非投资建议）」可不带 marker，其余事实/推断正文都必须带 marker。"
    "小节标题和篇幅由用户问题决定，不要求固定标题、固定段数或固定行数；"
    "不得增加证据外公司、数字、日期、催化或跨题材信息。"
    "读者是投资研究用户而不是系统维护者：用市场语言表达，"
    "不要出现内部流水线术语、字段名、评分原始数值（如优先级分数）或工程编号；"
    "证据里的内部指标（优先级、证据状态等）只用其方向和含义，不复述原始分值。"
    "DecisionBrief 的 chain_mapping 非空时，正文必须逐个写出这些公司："
    "公司名、产业链环节、层级和还缺什么证据；层级是候选就写候选，"
    "不得升级为已确认，也不得因为都是候选就整批省略。"
    "先直接回答，再按证据需要解释机制、反证或缺口；不要为了显得完整而填充无关段落。"
)

_GROUNDING_JUDGE_SYSTEM_PROMPT = (
    "你是低温事实蕴含审稿器。逐句判断 Grounded Composer 的自然语言是否真的能由"
    "该句绑定的 claim 和 EvidenceAtom 推出。重点检查：偷换主体、因果跳跃、"
    "把候选升级为事实、跨题材污染，以及虽未新增数字但语义越界。"
    "不要评价文风，不要重写答案。严格输出单个 JSON："
    '{"passed":true, "rejected_sentence_indexes":[], "issues":[]}。'
    "sentence index 只按带 marker 的正文句从 1 开始计数；有任何语义越界时 passed=false，"
    "列出对应句号和简短原因。"
)


def _required_outputs_block(required_outputs: tuple[str, ...]) -> str:
    """把本轮验收标准写进 prompt。

    这份清单就是 task_fulfillment 逐条判、判不过就把整份答案换成「请补充数据源」的
    那份清单。此前它从未进过 brief/compose 的 prompt——模型是在一张看不见的评分表
    上被打分。措辞刻意强调「只能用 registry 覆盖、没有就写成缺口」：只说「必须写到」
    而不说来源约束，等于在鼓励为了凑齐而编。
    """

    if not required_outputs:
        return ""
    items = "\n".join(f"- {item}" for item in required_outputs)
    return (
        "本轮必须覆盖的输出（每条都要在正文里真的写到，缺一条即判未完成）：\n"
        f"{items}\n"
        "只能用 claim registry 里的事实来覆盖；registry 里没有支撑的那一条，"
        "写成明确的缺口或边界，不要为了凑齐而编。\n\n"
    )


def _registry_document(registry_block: str) -> str:
    """把 claim registry 包成带标签的文档块。

    官方长上下文指引：多份材料时用 XML 标签包裹并标明来源，模型更容易在长输入里
    定位与切分。这里只有一份材料，标签的作用是给它一个明确的起止边界，避免它和
    后面的指令、问题在模型眼里糊成一片。
    """

    return (
        "<claim_registry>\n"
        "<source>本轮检索与结构化数据产出的全部 claim，每行一个 JSON</source>\n"
        "<content>\n"
        f"{registry_block}\n"
        "</content>\n"
        "</claim_registry>\n\n"
    )


# 长输入在前、问题在最后。
#
# 官方长上下文指引：「把长文档和长输入放在提示词靠顶部的位置，在问题、指令和示例
# 之上」，并注明「问题放在最后可以把回答质量提升最多 30%，多文档复杂输入尤其明显」。
# 这三个 builder 原本是完全相反的顺序——用户问题在最前，最长的 claim registry
# （12,000 字符预算，通常是整段 prompt 的绝大部分）压在最后。
#
# 与缓存不冲突：registry 每轮都变，用户消息本来就没有可复用前缀；可缓存的是它前面
# 的 system 消息，位置未动。


def build_decision_brief_messages(
    query: str,
    registry_block: str,
    *,
    required_outputs: tuple[str, ...] = (),
) -> list[dict]:
    return [
        {"role": "system", "content": _DECISION_BRIEF_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"{_registry_document(registry_block)}"
                f"{_required_outputs_block(required_outputs)}"
                f"用户问题：{query}"
            ),
        },
    ]


def build_grounded_composer_messages(
    query: str,
    decision_brief: str,
    registry_block: str,
    *,
    required_outputs: tuple[str, ...] = (),
) -> list[dict]:
    return [
        {"role": "system", "content": _GROUNDED_COMPOSER_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"{_registry_document(registry_block)}"
                f"DecisionBrief：\n{decision_brief}\n\n"
                f"{_required_outputs_block(required_outputs)}"
                f"用户问题：{query}"
            ),
        },
    ]


def build_grounding_judge_messages(
    query: str,
    grounded_answer: str,
    registry_block: str,
) -> list[dict]:
    return [
        {"role": "system", "content": _GROUNDING_JUDGE_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"{_registry_document(registry_block)}"
                f"待审答案：\n{grounded_answer}\n\n"
                f"用户问题：{query}"
            ),
        },
    ]


# 追问时附在用户问题前的薄约束：复用首轮已给证据、不引入新事实、不暴露内部编号。
_FOLLOWUP_NUDGE = (
    "（追问，请仅基于本次对话前面已经给出的多源证据回答：不要引入证据里没有的新公司/"
    "数字/催化，不要显示内部编号、字段名或工程诊断；若已有证据不足以回答就直说「证据不足」，"
    "不要编造。结尾仍以「（非投资建议）」收尾。）\n\n"
)


def followup_user_content(question: str) -> str:
    """Wrap a follow-up question with the grounding nudge sent to the model.

    The raw ``question`` is what the caller should display in a transcript; the
    wrapped form is what actually goes into the ``messages`` list."""
    return _FOLLOWUP_NUDGE + question


def synthesize_messages(
    messages: list[dict],
    model_override: str | None = None,
    timeout: int = DEFAULT_LLM_TIMEOUT,
    temperature: float = 0.3,
    *,
    deadline: Deadline | None = None,
    max_tokens: int = DEFAULT_SYNTHESIS_MAX_TOKENS,
    max_chars: int = DEFAULT_SYNTHESIS_MAX_CHARS,
) -> tuple[SynthesisResult | None, str]:
    """Run a synthesis turn from a full ``messages`` list (system + history).

    Shared by single-turn :func:`synthesize` and the multi-turn driver. Returns
    ``(result, reason)``; on any failure ``result`` is ``None`` and ``reason``
    explains why so the caller degrades gracefully."""
    rejection = _budget_rejection()
    if rejection is not None:
        return None, rejection
    provider = detect_provider(model_override)
    if provider is None:
        return None, (
            "未配置 LLM key，有机合成降级为模板。设置 DEEPSEEK_API_KEY / MOONSHOT_API_KEY / "
            "DASHSCOPE_API_KEY / ZHIPU_API_KEY / OPENAI_API_KEY 或通用 LLM_API_KEY 即可启用"
        )
    shared_deadline = deadline or Deadline.from_timeout(timeout)
    # 时间片是**这一段**的预算，不是「每次尝试」的预算。先把片折成一个子 deadline，
    # 重试在它内部消耗——否则 N 次重试就是 N × 片，实测 22s 的片跑出 44.5s（2 次尝试
    # 各超时一次），跟修好前的「片形同虚设」只差一个倍数。
    phase_deadline = Deadline(
        min(
            shared_deadline.expires_at,
            time.monotonic() + max(0.0, float(timeout or 0.0)),
        )
        if timeout
        else shared_deadline.expires_at
    )
    # 网络抖动（连接被重置/DNS 瞬断等 URLError）重试一次再降级：合成是整条回答的
    # 可读性关键，单次瞬断不值得整答退回模板。HTTP 4xx/5xx 不重试（重试大概率同样失败）。
    last_exc: Exception | None = None
    content = None
    finish_reason: str | None = None
    for attempt in range(_RETRY_MAX_ATTEMPTS):
        try:
            remaining = phase_deadline.require_remaining(1)
            content, finish_reason = _post_chat_synthesis(
                provider,
                messages,
                remaining,
                temperature,
                max_tokens,
                max_chars,
            )
            break
        except LLMCallBudgetExceeded as exc:
            return None, str(exc)
        except urllib.error.HTTPError as exc:  # pragma: no cover - network
            return None, f"LLM 合成 HTTP {exc.code}，已降级为模板"
        except LLMDeadlineExceeded:
            return None, "LLM 合成超过共享截止时间，已降级为模板"
        except LLMOutputTooLong:
            return None, "LLM 合成输出超长，已降级为模板"
        except Exception as exc:  # pragma: no cover - network
            last_exc = exc
            if attempt + 1 < _RETRY_MAX_ATTEMPTS:
                rejection = _budget_rejection()
                if rejection is not None:
                    return None, rejection
                # 按**本段**剩余判，不是整条共享 deadline：片用完了就该降级，
                # 而不是借下游几段的时间再试一次。
                remaining = phase_deadline.remaining()
                if remaining < 1:
                    return None, "LLM 合成超过共享截止时间，已降级为模板"
                # 退避 + 抖动，但绝不睡穿共享 deadline：留 0.5 秒给下一次尝试
                # 至少能发出去，否则退避本身就成了超时的原因。
                time.sleep(
                    min(_retry_delay_seconds(attempt), max(0.0, remaining - 0.5))
                )
    if content is None and last_exc is not None:
        return None, f"LLM 合成失败（{type(last_exc).__name__}），已降级为模板"
    text = (content or "").strip()
    if not text:
        return None, "LLM 合成返回空内容，已降级为模板"
    if finish_reason != "stop":
        if finish_reason == "length":
            return None, "LLM 合成响应被截断，已降级为模板"
        return None, "LLM 合成未正常停止，已降级为模板"
    return (
        SynthesisResult(
            answer=text,
            provider=provider.name,
            model=provider.model,
            finish_reason=finish_reason,
        ),
        "",
    )


def _post_chat_stream(
    provider: LLMProvider,
    messages: list[dict],
    timeout: int,
    temperature: float,
    on_delta: Callable[[str], None],
    on_connected: Callable[[], None] | None,
    is_cancelled: Callable[[], bool] | None,
    deadline: Deadline,
    max_tokens: int,
    max_chars: int,
) -> tuple[str, str | None]:
    _reserve_llm_call()
    started = time.monotonic()
    try:
        result = _post_chat_stream_raw(
            provider,
            messages,
            timeout,
            temperature,
            on_delta,
            on_connected,
            is_cancelled,
            deadline,
            max_tokens,
            max_chars,
        )
    except Exception as exc:
        _record_llm_call(
            "synthesis_stream", provider, "failed", started, _failure_reason(exc)
        )
        raise
    _record_llm_call("synthesis_stream", provider, "success", started)
    return result


def _post_chat_stream_raw(
    provider: LLMProvider,
    messages: list[dict],
    timeout: int,
    temperature: float,
    on_delta: Callable[[str], None],
    on_connected: Callable[[], None] | None,
    is_cancelled: Callable[[], bool] | None,
    deadline: Deadline,
    max_tokens: int,
    max_chars: int,
) -> tuple[str, str | None]:
    url = provider.base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": provider.model,
        "messages": messages,
        "temperature": temperature,
        "stream": True,
        "max_tokens": max_tokens,
    }
    if synthesis_thinking_disabled():
        payload["thinking"] = {"type": "disabled"}
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=_llm_request_headers(provider, Accept="text/event-stream"),
        method="POST",
    )
    chunks: list[str] = []
    output_chars = 0
    finish_reason: str | None = None
    with urllib.request.urlopen(request, timeout=timeout) as response:
        deadline_timer = threading.Timer(
            max(0.001, deadline.remaining()),
            response.close,
        )
        deadline_timer.daemon = True
        deadline_timer.start()
        if on_connected is not None:
            on_connected()
        try:
            for raw_line in response:
                if deadline.remaining() <= 0:
                    raise LLMDeadlineExceeded()
                if is_cancelled is not None and is_cancelled():
                    raise LLMStreamCancelled()
                line = raw_line.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    if finish_reason is None and chunks:
                        finish_reason = "stop"
                    break
                try:
                    event = json.loads(data)
                    choice = event["choices"][0]
                    finish_reason = (
                        _stable_finish_reason(choice.get("finish_reason"))
                        or finish_reason
                    )
                    delta = choice["delta"].get("content")
                except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                    continue
                if isinstance(delta, str) and delta:
                    output_chars += len(delta)
                    if output_chars > max_chars:
                        raise LLMOutputTooLong()
                    on_delta(delta)
                    chunks.append(delta)
        except (OSError, ValueError) as exc:
            if deadline.remaining() <= 0:
                raise LLMDeadlineExceeded() from exc
            raise
        finally:
            deadline_timer.cancel()
    if not chunks:
        raise LLMStreamingUnsupported()
    return "".join(chunks), finish_reason


# 流式→非流式回退的准入条件：**一个字都还没吐出去**。
#
# 依据是 ch06b 记的真实事故 inc-4258——流式已经开始执行工具，回退到非流式重试后
# 同一个工具执行了两次；CC 为此加了开关能禁掉整条回退路径。我们这边核实过，那个
# 形状目前不成立：全仓只有这一处 `"stream": True`，而它是合成调用、不带工具
# （带工具的 `chat_with_tools` 走非流式的 `_post_chat_message`）；两条回退的触发
# 条件也都在首个 delta 之前——`LLMStreamingUnsupported` 只在 chunks 为空时抛，
# `HTTPError` 只由 `urlopen` 在响应头阶段抛，流开起来之后 urllib 抛的是
# IncompleteRead 那一类，落到通用 except 里直接降级、不回退。
#
# 既然当前触发不了，这道闸就是零行为变化——它防的是**以后**有人在流循环里加重试、
# 或把 HTTPError 的抛出点挪到 delta 之后。真到那天，回退会把整段答案再 on_delta
# 一次，用户看到的是重复正文（工具双执行的文本版）。宁可降级为模板。
_STREAM_FALLBACK_BLOCKED = "LLM 流式合成已输出后失败，不回退非流式（避免重复正文），已降级为模板"


def synthesize_messages_stream(
    messages: list[dict],
    *,
    on_delta: Callable[[str], None],
    on_connected: Callable[[], None] | None = None,
    on_finish_reason: Callable[[str | None], None] | None = None,
    is_cancelled: Callable[[], bool] | None = None,
    model_override: str | None = None,
    timeout: int = DEFAULT_LLM_TIMEOUT,
    temperature: float = 0.3,
    deadline: Deadline | None = None,
    max_tokens: int = DEFAULT_SYNTHESIS_MAX_TOKENS,
    max_chars: int = DEFAULT_SYNTHESIS_MAX_CHARS,
) -> tuple[SynthesisResult | None, str]:
    rejection = _budget_rejection()
    if rejection is not None:
        return None, rejection
    provider = detect_provider(model_override)
    if provider is None:
        return None, (
            "未配置 LLM key，有机合成降级为模板。设置 DEEPSEEK_API_KEY / MOONSHOT_API_KEY / "
            "DASHSCOPE_API_KEY / ZHIPU_API_KEY / OPENAI_API_KEY 或通用 LLM_API_KEY 即可启用"
        )
    shared_deadline = deadline or Deadline.from_timeout(timeout)
    # 流式已经吐给用户多少字。下面两条回退非流式的路径必须先看它——见
    # ``_stream_fallback_blocked``。
    streamed_chars = 0

    def _tracked_delta(delta: str) -> None:
        nonlocal streamed_chars
        streamed_chars += len(delta)
        on_delta(delta)

    try:
        remaining = shared_deadline.call_timeout(timeout)
        content, finish_reason = _post_chat_stream(
            provider,
            messages,
            remaining,
            temperature,
            _tracked_delta,
            on_connected,
            is_cancelled,
            shared_deadline,
            max_tokens,
            max_chars,
        )
        if on_finish_reason is not None:
            on_finish_reason(finish_reason)
    except LLMStreamCancelled:
        raise
    except LLMCallBudgetExceeded as exc:
        return None, str(exc)
    except LLMDeadlineExceeded:
        return None, "LLM 流式合成超过共享截止时间，已降级为模板"
    except LLMOutputTooLong:
        return None, "LLM 流式合成输出超长，已降级为模板"
    except urllib.error.HTTPError as exc:
        if exc.code not in {400, 404, 405, 415, 422, 501}:
            return None, f"LLM 流式合成 HTTP {exc.code}，已降级为模板"
        if streamed_chars:
            return None, _STREAM_FALLBACK_BLOCKED
        if shared_deadline.remaining() < 1:
            return None, "LLM 流式合成超过共享截止时间，已降级为模板"
        fallback, reason = synthesize_messages(
            messages,
            model_override=model_override,
            timeout=max(1, int(shared_deadline.remaining())),
            temperature=temperature,
            deadline=shared_deadline,
            max_tokens=max_tokens,
            max_chars=max_chars,
        )
        if fallback is not None:
            on_delta(fallback.answer)
            fallback.fallback_reason = "stream_unsupported"
        return fallback, reason
    except LLMStreamingUnsupported:
        if streamed_chars:  # 定义上不可能（它只在 chunks 为空时抛），留着防定义漂移
            return None, _STREAM_FALLBACK_BLOCKED
        if shared_deadline.remaining() < 1:
            return None, "LLM 流式合成超过共享截止时间，已降级为模板"
        fallback, reason = synthesize_messages(
            messages,
            model_override=model_override,
            timeout=max(1, int(shared_deadline.remaining())),
            temperature=temperature,
            deadline=shared_deadline,
            max_tokens=max_tokens,
            max_chars=max_chars,
        )
        if fallback is not None:
            on_delta(fallback.answer)
            fallback.fallback_reason = "stream_unsupported"
        return fallback, reason
    except Exception as exc:  # pragma: no cover - network
        if shared_deadline.remaining() <= 0:
            return None, "LLM 流式合成超过共享截止时间，已降级为模板"
        return None, f"LLM 流式合成失败（{type(exc).__name__}），已降级为模板"
    if not content.strip():
        return None, "LLM 流式合成返回空内容，已降级为模板"
    if finish_reason != "stop":
        if finish_reason == "length":
            return None, "LLM 流式合成响应被截断，已降级为模板"
        return None, "LLM 流式合成未正常停止，已降级为模板"
    return (
        SynthesisResult(
            answer=content,
            provider=provider.name,
            model=provider.model,
            finish_reason=finish_reason,
        ),
        "",
    )


# 质检闸门 WARN 回灌修订（修订版在前契约）：把 output_review 的 WARN 意见送回同一段
# 对话做一轮定向修订，用户拿到的是可直接引用的修订版全文，审查意见退居附录。
_GATE_REVISION_PROMPT = (
    "输出质检闸门对上一条回答给出以下 WARN 意见，请针对性修订：\n{notes}\n"
    "要求：只修意见相关的问题，不改动无关内容；仍只能使用已给证据，证据不足处显式写缺口而不是补写内容；"
    "只输出修订后的最终回答正文，不输出修订说明，结尾仍以「（非投资建议）」收尾。"
)


def gate_revision_user_content(warn_notes: list[str]) -> str:
    """Build the user turn that feeds output-review WARN notes back for revision."""
    notes = "\n".join(f"- {n}" for n in warn_notes)
    return _GATE_REVISION_PROMPT.format(notes=notes)


def claim_binding_revision_user_content(
    error_notes: list[str],
    registry_block: str,
) -> str:
    joined = "\n".join(f"- {note}" for note in error_notes)
    # 同样是长输入在前、指令在后（见上面 builder 处的说明）。
    return (
        f"{_registry_document(registry_block)}"
        "上一版未通过结构化事实门禁。不要增加 registry 外事实；"
        "保留原有自然措辞，只修复门禁错误指出的 claim/EvidenceAtom 绑定或越界句。\n"
        "标题可自由组织；事实和推断正文必须保留合法 marker，允许删去无法修复的单句，"
        "但不要为满足格式而重写整篇答案。\n"
        f"门禁错误：\n{joined}"
    )


def grounded_composer_system_prompt() -> str:
    """Grounded Composer 的 system 段，供门禁修复轮复用同一套写作约束。"""

    return _GROUNDED_COMPOSER_SYSTEM_PROMPT


def fulfillment_revision_user_content(
    missing: tuple[tuple[str, str], ...],
    registry_block: str,
    answer_text: str,
) -> str:
    """把「哪几个必需输出没覆盖、为什么没绑上」回灌给模型做一轮定向补写。

    官方 Claude Code 对被拒的工具调用不是直接终止，而是**把拒绝消息作为
    tool result 交回模型**，让它换方法或说明无法继续（`PermissionDenied`
    hook 的官方用例原文就是「告诉模型它可以重试」）。我们这里对应的动作是：
    门禁判缺时先把具体缺口交回去补一轮，而不是直接把整份答案换成缺口模板。

    ``missing`` 的第二项是 ``FulfillmentItem.gap``，它已经写清了四种「为什么没
    绑上」（registry 里没有对应 claim / 候选 N 条但正文没出现它们的文本 /
    候选 N 条且正文写到了但证据没绑上 / 已绑定但正文缺少该输出的措辞标记）——
    这四句是诊断，不是骂人，模型拿它能定位到具体该改哪里。

    来源约束逐字复用 ``_required_outputs_block()`` 里那句：只说「必须写到」而
    不说来源约束，等于在鼓励为了过门禁而编。
    """

    items = "\n".join(f"- {output_id}：{gap}" for output_id, gap in missing)
    # 长输入在前、指令在最后（与三个 composer builder 一致）。
    return (
        f"{_registry_document(registry_block)}"
        "<previous_answer>\n"
        f"{answer_text}\n"
        "</previous_answer>\n\n"
        "上一版没有覆盖全部必需输出。保留已经写好的部分和原有措辞，"
        "只针对下面点名的输出补写，不要重写整篇答案。\n"
        "只能用 claim registry 里的事实来覆盖；registry 里没有支撑的那一条，"
        "写成明确的缺口或边界，不要为了凑齐而编。\n"
        f"未覆盖的输出及原因：\n{items}"
    )


def synthesize(
    query: str,
    theme: str,
    evidence_text: str,
    citation_legend: str = "",
    model_override: str | None = None,
    timeout: int = DEFAULT_LLM_TIMEOUT,
    temperature: float = 0.3,
) -> tuple[SynthesisResult | None, str]:
    """Compose a free-form, citation-grounded answer from retrieved evidence.

    Returns ``(result, reason)``. On any failure (no key / HTTP / network / empty)
    ``result`` is ``None`` and ``reason`` explains why, so the caller degrades to
    the deterministic six-section template — identical behaviour to no-key today.
    """
    messages = build_synthesis_messages(query, theme, evidence_text, citation_legend)
    return synthesize_messages(
        messages, model_override=model_override, timeout=timeout, temperature=temperature
    )
