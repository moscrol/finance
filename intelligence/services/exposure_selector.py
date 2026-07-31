"""按问题意图从图谱暴露候选池里挑公司（待办 C）。

## 解决什么

确定性排序（``knowledge._exposure_rank_key``）只能按图谱的静态标注排：
strength(core/related/peripheral) × confidence(high/medium/low)。「固态电池」实测
86 家候选挤在 9 个桶里，core/medium 一档就有 13 家而配额只有 12——档内仍然按
公司名取舍，当升科技排 19、赣锋锂业排 20、宁德时代排 29，全在配额外。

标注回答的是「这家公司跟这个题材有多相关」，回答不了「**对这个问题**谁最相关」。
「谁最受益」要的是链上位置和弹性，「谁在扩产」要的是产能证据——同一批候选，
不同问题该选出不同的 12 家。这一层得让模型来判。

## 抄的是什么，没抄什么

形状来自 Claude Code 的记忆检索（参考资料库 ⑦ yuker 源码走读）：不做关键词匹配、
不做向量检索，让模型扫候选的标题+描述选出最多 N 条，策略「精确度优先于召回率」。

**三处量纲不同，没照抄：**

1. **CC 用 Haiku，我们没有小模型。** 本机只配了 glm-5.2 一个。``ASK_EXPOSURE_SELECTOR_MODEL``
   留了口子，等有更便宜的模型再指过去。所以这里省的是「选得准」，不是「选得便宜」。
2. **CC 每轮都选，我们只在截断真的发生时选。** 候选 8 家配额 12 家时选择器毫无意义，
   还要吃掉一次 5 小时滚动配额。触发判断在调用方（``evidence_providers``）。
3. **CC 是「宁缺毋滥」，我们不能缺。** CC 的记忆多塞一条只是污染上下文；我们的
   12 个槽位是答案覆盖面，模型只选出 3 家会让「谁最受益」直接塌掉。所以模型选不满时
   用确定性排序补齐——补进来的不是噪声，是上一版的最优解。

## 失败关闭

任何一步出问题都回退确定性排序（马书原则三）：这里的「最安全项」不是「不返回」，
而是「返回上一版已知可用的结果」。回退**必须留证**，``reason`` 会一路进 trace ——
不然就成了本轮一直在治的那个病：降级了但没人知道为什么。
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from intelligence.services import llm_refine

# 选择器的超时。它在答问的关键路径上，超时就该赶紧让位给合成，而不是把整轮
# 预算耗在挑公司上。实测一次选择 3~8 秒。
_SELECTOR_TIMEOUT = 25.0

_MAX_ROLE_CHARS = 60


@dataclass
class ExposureSelection:
    """选择结果 + 全过程留证。``telemetry`` 会进 trace。"""

    items: list[dict[str, Any]]
    telemetry: dict[str, Any] = field(default_factory=dict)


def selector_mode() -> str:
    """``auto``（截断时选一次）/ ``off``（永不调用，行为回到纯确定性）。

    对齐仓内既有 idiom（``ASK_AGENT_LOOP`` / ``ASK_EVIDENCE_JUDGE`` 都用 auto）。
    """
    raw = str(os.environ.get("ASK_EXPOSURE_SELECTOR") or "auto").strip().lower()
    return "off" if raw in {"off", "0", "false", "no"} else "auto"


def _candidate_line(index: int, row: dict[str, Any]) -> str:
    role = re.sub(r"\s+", " ", str(row.get("role") or "")).strip()
    if len(role) > _MAX_ROLE_CHARS:
        role = role[:_MAX_ROLE_CHARS] + "…"
    parts = [
        f"{index}. {row.get('company') or ''}",
        f"强度={row.get('strength') or '未标注'}",
        f"置信={row.get('confidence') or '未标注'}",
    ]
    if role:
        parts.append(f"线索={role}")
    return "｜".join(parts)


def _messages(question: str, rows: list[dict[str, Any]], limit: int) -> list[dict]:
    catalog = "\n".join(_candidate_line(i, row) for i, row in enumerate(rows, start=1))
    system = (
        "你在为一份 A 股研究报告挑选产业链公司。给你一个问题和一批候选公司，"
        "从候选里选出与**这个问题**最相关的若干家。\n"
        "- 只能从候选里选，不得凭记忆补充候选之外的公司。\n"
        "- 按相关性从高到低排列。\n"
        "- 不确定的不要选：宁可少选，也不要为凑数把弱相关的塞进来。\n"
        "- 候选的「强度/置信」是图谱的静态标注，可参考但不是唯一依据；"
        "问题问的是什么，就按什么排。\n"
        f'只输出 JSON，格式 {{"companies": ["公司名", ...]}}，最多 {limit} 家，不要解释。'
    )
    user = f"问题：{question}\n\n候选公司（共 {len(rows)} 家）：\n{catalog}"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _parse_companies(content: str) -> list[str] | None:
    """从模型输出里取公司名列表；取不到返回 None（区别于「取到了但是空」）。"""
    text = content.strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match is None:
        return None
    try:
        payload = json.loads(match.group(0))
    except (ValueError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    names = payload.get("companies")
    if not isinstance(names, list):
        return None
    return [str(name).strip() for name in names if str(name).strip()]


def select_exposures(
    question: str,
    candidates: list[dict[str, Any]],
    limit: int,
    *,
    complete: Callable[..., tuple[str | None, Any, str]] | None = None,
    model_override: str | None = None,
) -> ExposureSelection:
    """让模型按问题意图从 ``candidates`` 里挑最多 ``limit`` 家。

    任何失败都回退到 ``candidates`` 的既有顺序（调用方已按确定性排序排好）。
    """
    fallback = list(candidates[:limit])
    telemetry: dict[str, Any] = {
        "mode": "deterministic",
        "reason": "",
        "candidate_count": len(candidates),
        "llm_selected": 0,
        "backfilled": 0,
    }

    if not candidates:
        telemetry["reason"] = "no_candidates"
        return ExposureSelection(items=fallback, telemetry=telemetry)
    if len(candidates) <= limit:
        # 候选没超配额，没有可挑的余地——这次调用本身就是浪费。
        telemetry["reason"] = "pool_within_limit"
        return ExposureSelection(items=fallback, telemetry=telemetry)
    if selector_mode() == "off":
        telemetry["reason"] = "selector_off"
        return ExposureSelection(items=fallback, telemetry=telemetry)

    call = llm_refine.complete if complete is None else complete
    started = time.monotonic()
    try:
        content, _provider, failure_detail = call(
            _messages(question, candidates, limit),
            model_override=model_override
            or os.environ.get("ASK_EXPOSURE_SELECTOR_MODEL")
            or None,
            timeout=_SELECTOR_TIMEOUT,
        )
    except Exception as exc:  # noqa: BLE001 - 选择器不可用必须能降级，但要留证
        content, failure_detail = None, f"选择器调用抛出（{type(exc).__name__}）"
    telemetry["elapsed_ms"] = max(0, round((time.monotonic() - started) * 1000))

    if content is None:
        # provider 没回话。跟「回了但读不懂」是两回事，分开记——混成一类会把一次
        # prompt/schema 回归误判成外部故障（和 turn_controller 那次同一个教训）。
        telemetry["reason"] = f"provider_unavailable:{failure_detail or 'unknown'}"[:200]
        return ExposureSelection(items=fallback, telemetry=telemetry)

    names = _parse_companies(content)
    if names is None:
        telemetry["reason"] = "unparsable_response"
        return ExposureSelection(items=fallback, telemetry=telemetry)

    by_company: dict[str, dict[str, Any]] = {}
    for row in candidates:
        key = str(row.get("company") or "").strip()
        if key and key not in by_company:
            by_company[key] = row

    picked: list[dict[str, Any]] = []
    seen: set[str] = set()
    hallucinated = 0
    for name in names:
        row = by_company.get(name)
        if row is None:
            # 模型报了候选之外的公司名。不追加、只计数——这里放行等于让模型
            # 凭记忆往研究报告里塞公司。
            hallucinated += 1
            continue
        if name in seen:
            continue
        seen.add(name)
        picked.append(row)
        if len(picked) >= limit:
            break

    telemetry["hallucinated"] = hallucinated
    if not picked:
        telemetry["reason"] = "no_valid_pick"
        return ExposureSelection(items=fallback, telemetry=telemetry)

    telemetry["llm_selected"] = len(picked)
    # 没选满就用确定性排序补齐：12 个槽位是答案的覆盖面，模型只给 3 家会让
    # 「谁最受益」直接塌掉。补进来的是上一版最优解，不是噪声。
    for row in candidates:
        if len(picked) >= limit:
            break
        key = str(row.get("company") or "").strip()
        if key and key not in seen:
            seen.add(key)
            picked.append(row)
            telemetry["backfilled"] += 1

    telemetry["mode"] = "llm"
    return ExposureSelection(items=picked, telemetry=telemetry)
