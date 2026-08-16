"""Per-provider latency floors for repair-window sizing.

``repair_coordinator._REPAIR_SECONDS_CAP`` 的 docstring 已经把原则写对了：一次
LLM 调用的成本由**固定延迟地板**（网络 + prompt 处理）主导，与缺口数无关，
**低于地板的窗口注定超时，还要白烧掉授予本身**。

它没写对的是：那个地板是 **provider 的属性**，不是全局常数。30.0 这个值来自
2026-08-08 对中转 `gpt-5.6-terra` 的实测（P50≈28s），并由 2026-08-13 的生产收据
（R7/R21：16/24s 窗 0/5 全超时，30s 窗 5/5 全成功）确认。换 provider 时它没跟着换。

2026-08-16 事故坐实了这一点：中转全站 5xx 后 8792 切到 GLM 主链，模型、工具、
证据全部恢复正常，但 `run_20260816_230528_976709` 的两个修复轮**各在整 30.0 秒
超时**——窗口卡在 GLM 的 p90 底下。

    GLM `glm-5.2` @ coding plan，8795 已有成功 model_turn n=32：
      min 6.2 / p50 17.3 / p90 34.4 / max 49.4 秒；6/32 超过 30s

于是 30s 窗对 GLM 的结构性超时率约 19%（6/32），且**修复轮恰好是最贵的一轮**
（带完整历史，input token 最多）。

## 取值口径

按 **生效 provider 的实测 p90 + 余量** 取，不是「谁慢就调大全局 30」：

- p90 而非 p50：修复轮只有 1–2 次机会，按中位数取会让一半的轮次白烧。
- p90 而非 max：max（49.4s）会吃掉 standard 档 90s 预算的一大半，把成本转嫁给
  检索阶段。p90 是「大部分能过、少数放弃」的折中。
- 留一档余量再取整：GLM 34.4 → 40.0（约 16% 余量，仍低于 max）。

新增 provider 时**必须附实测样本量与分位数**，不要照感觉填。查不到实测就别加
条目——落到 ``DEFAULT_REPAIR_SECONDS_CAP`` 是安全行为（等同当前生产），凭感觉
填一个数不是。

## 全路由影响面

- 研究题 + GLM 主链：修复单笔上限 30→40（仅 repair / transient retry）。
- 研究题 + 中转 openai：取值仍 30，行为零变化。
- 非研究题（追问、foresight、模板回退）不走 ``admit_repair``，0pp。
- ``_REPAIR_SECONDS_CAP`` 常数保持 30.0，未传 ``seconds_cap`` 的调用方逐字节不变。

## 为什么不做成自适应

「按运行时观测自动调窗」在这里是坏主意：修复轮样本极稀疏（每 episode 至多 1–2
次），用它估分位数是拿高方差量做低采样。先用实测表把已知的两个 provider 钉住。
"""

from __future__ import annotations

import os

# 未知 provider 的地板。等于 2026-08-13 之前的全局常数，故新 provider 在补进
# 下表之前的行为与当前生产逐字节一致（fail-safe to current behaviour）。
DEFAULT_REPAIR_SECONDS_CAP = 30.0

# 2026-08-16 8795 GLM 成功轮 n=32。测试钉「窗口必须盖过这个数」，不钉 40 本身。
GLM_MEASURED_P90_SECONDS = 34.4

# provider.name（llm_refine.LLMProvider.name）→ 修复轮单笔授予帽（秒）。
# 每条都必须能指到一次实测。
_REPAIR_SECONDS_BY_PROVIDER: dict[str, float] = {
    # 中转 gpt-5.6-terra：P50≈28s（2026-08-08 实测 N=8）。
    # 2026-08-13 生产收据 R7/R21：30s 窗 5/5 成功、16/24s 窗 0/5 全超时。
    # 保持 30.0——这条线**不改**，故非 GLM 路由的行为零变化。
    "openai": 30.0,
    # GLM glm-5.2 @ coding plan：p90=34.4s（2026-08-16 实测 n=32）。
    "zhipu": 40.0,
}

# 逃生阀：实验窗里想单独压/放窗口时用，不必改代码重启。
# 非法值（非数、≤0）一律忽略并落回表值——配置写错不该让修复轮静默变成 0 秒。
ENV_OVERRIDE = "ASK_REPAIR_SECONDS_CAP"


def repair_seconds_cap_for(
    provider_name: str | None,
    *,
    env: dict[str, str] | None = None,
) -> float:
    """Return the repair-window cap (seconds) for one provider.

    ``provider_name`` 取 ``llm_refine.LLMProvider.name``（``zhipu`` / ``openai`` /
    ``custom``）。None、空串或表中没有的名字一律落 ``DEFAULT_REPAIR_SECONDS_CAP``。

    环境变量 ``ASK_REPAIR_SECONDS_CAP`` 覆盖一切（含未知 provider）；无法解析成
    正数时忽略。
    """

    source = os.environ if env is None else env
    raw = str(source.get(ENV_OVERRIDE) or "").strip()
    if raw:
        try:
            override = float(raw)
        except ValueError:
            override = 0.0
        if override > 0.0:
            return override
    key = str(provider_name or "").strip().casefold()
    return _REPAIR_SECONDS_BY_PROVIDER.get(key, DEFAULT_REPAIR_SECONDS_CAP)


def known_providers() -> tuple[str, ...]:
    """已有实测条目的 provider 名，供收据与测试枚举。"""

    return tuple(sorted(_REPAIR_SECONDS_BY_PROVIDER))


def provider_name_from(runtime: object) -> str | None:
    """问 runtime / model client 它实际在用的 provider 链链首名。

    鸭子类型而非 isinstance：``AgentRuntime`` 是协议，壳有多个实现。
    问不到返回 None → 调用方落默认帽，等于改动前行为，不 raise。

    **为什么不直接 detect_providers()**：那读的是 env（配置值），而生产在
    ``api/app.py`` 显式注入 ``runtime_providers_for(user_id)`` 的结果（生效值）；
    BYOK 用户两者不同。窗口要跟着真正在发请求的那个 provider 走。
    """

    for attr in ("_providers", "providers"):
        chain = getattr(runtime, attr, None)
        if chain:
            head = next(iter(chain), None)
            name = getattr(head, "name", None)
            if name:
                return str(name)
    client = getattr(runtime, "model_client", None) or getattr(runtime, "_client", None)
    if client is not None and client is not runtime:
        return provider_name_from(client)
    model = getattr(runtime, "_model", None)
    if model is not None and model is not runtime:
        return provider_name_from(model)
    return None


__all__ = [
    "DEFAULT_REPAIR_SECONDS_CAP",
    "ENV_OVERRIDE",
    "GLM_MEASURED_P90_SECONDS",
    "known_providers",
    "provider_name_from",
    "repair_seconds_cap_for",
]
