"""Per-provider latency floors for repair-window sizing.

``runtime/repair_budget._REPAIR_SECONDS_CAP`` 的 docstring 已经把原则写对了：一次
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

# 修复轮单笔授予的**模型侧**地板（spec 2026-09-08 P1）。上表按 provider.name 键，
# 但生产链首 name="zhipu" 实际是 sol@cockpit，且同一 GLM 在 low 与 max 下修复轮
# 长度差 3 倍——provider 名量不出这个。键是（配置模型名前缀，推理档集合）。
#
# 2026-09-07 max 档 GLM-5.3-flash 思考臂修复轮 n=6：1.9K–6.8K token @ ≈33 tok/s
# ≈ 60–210s；40s 帽（按 glm-5.2 不思考 p90 34.4 标）下 6.8K 那发把已 completed 的稿
# 降成 partial（glm-ceiling-20260907 §7）。200 取 p90 量级。修复能铸的余量上限是
# synthesis_reserve（账本硬顶 − 研究额度），所以这个数只有在合成保留地板（P2）≥
# 写作 + 修复之后才起作用——两者同批上线，见 spec §4.2。
_REPAIR_SECONDS_FLOOR_BY_MODEL: tuple[tuple[str, frozenset[str], float], ...] = (
    ("glm-5.3", frozenset({"max", "high"}), 200.0),
)


def repair_seconds_cap_for(
    provider_name: str | None,
    *,
    model_name: str | None = None,
    reasoning_effort: str | None = None,
    env: dict[str, str] | None = None,
) -> float:
    """Return the repair-window cap (seconds) for one provider.

    ``provider_name`` 取 ``llm_refine.LLMProvider.name``（``zhipu`` / ``openai`` /
    ``custom``）。None、空串或表中没有的名字一律落 ``DEFAULT_REPAIR_SECONDS_CAP``。
    传了 ``model_name`` / ``reasoning_effort`` 时再按模型侧实测表取地板（只抬不压）；
    不传即老行为。

    环境变量 ``ASK_REPAIR_SECONDS_CAP`` 覆盖一切（含未知 provider 与模型地板）；
    无法解析成正数时忽略。
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
    cap = _REPAIR_SECONDS_BY_PROVIDER.get(key, DEFAULT_REPAIR_SECONDS_CAP)
    floor = _model_floor(_REPAIR_SECONDS_FLOOR_BY_MODEL, model_name, reasoning_effort)
    return cap if floor is None else max(cap, floor)


def _model_floor(
    table: tuple[tuple[str, frozenset[str], float], ...],
    model_name: str | None,
    reasoning_effort: str | None,
) -> float | None:
    model = str(model_name or "").strip().casefold()
    effort = str(reasoning_effort or "").strip().casefold()
    if not model or not effort:
        return None
    for prefix, efforts, seconds in table:
        if model.startswith(prefix) and effort in efforts:
            return seconds
    return None


def known_providers() -> tuple[str, ...]:
    """已有实测条目的 provider 名，供收据与测试枚举。"""

    return tuple(sorted(_REPAIR_SECONDS_BY_PROVIDER))


# ── 写作轮成本 → 合成保留地板（模型侧） ─────────────────────────────────────
#
# 合成保留（``ResearchPolicy.synthesis_reserve``）回答的是「留多少秒给模型写结论」。
# 答案长度归产品（档位表 quick 20 / standard 20 / deep 48 / max 60），输出速度归模型
# ——同一份档位值在不同模型上是两个完全不同的写作时长。60s 是按 sol 写 1.4–1.7K
# token 标的（sol 规划轮 0.03–0.25K、写作 1.7K，无隐藏推理）。
#
# 2026-09-07 max 档 GLM-5.3-flash 思考臂（LLM_REASONING_EFFORT=max/high）n=11 实测：
#   单个写作轮输出 3.3K–7.7K token（p50 4.9K，含隐藏推理），解码 27.5–40.6 tok/s（p50 32.8）
#   → 写作轮 p50 ≈150s、p90 ≈210s；Q1 上 3/6 还要一次修复轮（1.9–4.8K token ≈ 60–150s）。
#   被切的那发（high×Q1-r3）：研究到剩 161s 才开始写，写作 7.3K token 要 200s+ →
#   deadline_exhausted → 修复轮也没写完 → partial。60s 保留在这类模型上等于没有保留。
# 240 = 写作 p90（210）单独可容，或写作 p50 + 修复 p50（150 + 90）。max 档 600s 里留 240
# 还剩 360s 研究，盖过实测研究阶段 270–300s。收据 ~/.finance-runtime/glm-ceiling-20260907/。
#
# 键是（配置模型名前缀，推理档集合）：provider.name 不行——生产链首 name="zhipu" 实际是
# sol@cockpit（启动器注释在案），且同一 GLM 在 low 与 max 下写作成本差 4 倍。
# 未命中返回 None = 沿用档位值，sol / 未开思考的 GLM 请求体与预算逐字节同前。
# 新增条目必须附实测样本量与分位数（同上表规矩）。
_SYNTHESIS_RESERVE_FLOOR_BY_MODEL: tuple[tuple[str, frozenset[str], float], ...] = (
    ("glm-5.3", frozenset({"max", "high"}), 240.0),
)
ENV_SYNTHESIS_RESERVE_FLOOR = "ASK_SYNTHESIS_RESERVE_FLOOR"


def synthesis_reserve_floor_for(
    model_name: str | None,
    reasoning_effort: str | None,
    *,
    env: dict[str, str] | None = None,
) -> float | None:
    """该模型在该推理档下写一次结论至少要留的秒数；无实测条目返回 None。

    ``model_name`` 取配置的 ``LLMProvider.model``（如 ``glm-5.3-flash``），前缀匹配；
    ``reasoning_effort`` 取 ``LLM_REASONING_EFFORT`` 生效值。环境变量
    ``ASK_SYNTHESIS_RESERVE_FLOOR`` 覆盖一切（实验窗口用）；非法值忽略。
    """

    source = os.environ if env is None else env
    raw = str(source.get(ENV_SYNTHESIS_RESERVE_FLOOR) or "").strip()
    if raw:
        try:
            override = float(raw)
        except ValueError:
            override = 0.0
        if override > 0.0:
            return override
    return _model_floor(_SYNTHESIS_RESERVE_FLOOR_BY_MODEL, model_name, reasoning_effort)


def provider_name_from(
    runtime: object,
    *,
    _seen: frozenset[int] | None = None,
) -> str | None:
    """问 runtime / model client 它实际在用的 provider 链链首名。

    鸭子类型而非 isinstance：``AgentRuntime`` 是协议，壳有多个实现。
    问不到返回 None → 调用方落默认帽，等于改动前行为，不 raise。

    **为什么不直接 detect_providers()**：那读的是 env（配置值），而生产在
    ``api/app.py`` 显式注入 ``runtime_providers_for(user_id)`` 的结果（生效值）；
    BYOK 用户两者不同。窗口要跟着真正在发请求的那个 provider 走。

    生产组合根是 ``GLMAgentRuntime``：它自己没有 ``_providers``，链在
    ``_episode._model``（``GLMModelClient``）上。只问一层 client 会落空，
    修复帽就会静默回到 30——2026-08-17 live 两发 TimeoutError 就是这个洞。
    """

    if runtime is None:
        return None
    ident = id(runtime)
    seen = _seen or frozenset()
    if ident in seen:
        return None
    next_seen = seen | {ident}

    for attr in ("_providers", "providers"):
        chain = getattr(runtime, attr, None)
        if chain:
            head = next(iter(chain), None)
            name = getattr(head, "name", None)
            if name:
                return str(name)
    for attr in ("model_client", "_client", "client", "_episode", "_model"):
        inner = getattr(runtime, attr, None)
        if inner is None or inner is runtime:
            continue
        found = provider_name_from(inner, _seen=next_seen)
        if found:
            return found
    return None


__all__ = [
    "DEFAULT_REPAIR_SECONDS_CAP",
    "ENV_OVERRIDE",
    "ENV_SYNTHESIS_RESERVE_FLOOR",
    "GLM_MEASURED_P90_SECONDS",
    "known_providers",
    "provider_name_from",
    "repair_seconds_cap_for",
    "synthesis_reserve_floor_for",
]
