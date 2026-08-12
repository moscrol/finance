#!/usr/bin/env python3
"""参数构造试验场：模型看到工具 schema 之后，写出来的参数合不合法。

**为什么需要它，以及它和 ``probe_tool.py`` 的分界**：

| 脚本 | 测什么 | 调模型吗 |
|---|---|---|
| ``probe_provider_latency.py`` | provider 快慢，不碰工具 | 是 |
| ``probe_tool.py`` | **单个工具本身**：多久、返回什么、空结果长什么样 | **否（路由用 stub）** |
| **本脚本** | **模型构造参数的合法率**：给定 schema，它写出来的参数能不能过校验 | 是 |
| ``run_episode_seam_ladder.py`` | 一组能力装配起来跑不跑得通 | 是 |

2026-08-12 要改 ``finance_query`` 的参数描述时，第一反应是用 ``probe_tool.py``
验证——**错了**。那个脚本第三条设计选择写着「路由用 stub，不调模型」，而参数
描述唯一影响的就是模型构造参数那一步，正好被 stub 掉。用它测等于量具复刻不了
生产（TOOLKIT 三条量具陷阱之一）。全树 grep 确认当时没有别的量具能测这一步：
碰 ``tool_definitions`` 的只有 seam_ladder / episode_ab / runtime_benchmark /
capability_monotonicity 等 3–4 档整条 episode，或事后 trace 归一。

三条刻意的设计选择：

1. **校验离线做完，不执行工具**。``_compile_query`` 是纯 SQL 构造、不需要 DB
   连接，所以 ``from_arguments → normalize_spec → _compile_query`` 这条链能在
   零成本下抓到全部已知错法。配额只花在「让模型写一次参数」上，校验不花钱。
   代价是**测不到执行期才暴露的问题**（数据真的存不存在），那是 probe_tool 的活。
2. **题集用冻结的验收台账，不自己编题**。自己编题会不自觉地往假设上靠——
   想验证「日期描述有用」就会写一道带日期的题。``acceptance_cases.json`` 是
   既有的 28 题，按 ``expect_tools`` 过滤出该工具的那几道。
3. **读数自述采样规模与局限**。``--repeat 1`` 只够回答「现在还错不错」，
   不足以支撑「改了之后变好了」——后者要看方差（TOOLKIT：高方差量上别低采样，
   2–3 次采样的排序是噪声）。所以 summary 里显式写 ``ablation_ready``，
   低于阈值时直接标 false，免得下一个人拿 N=1 的读数当消融判据。

``--dry-run`` 用 stub 模型跑完整条管道（零配额），只验证装配与校验通不通。

只读：不写 DuckDB、不外呼工具、不改任何仓内文件；``--out`` 显式给出时才落盘。
"""
from __future__ import annotations

import argparse
from collections.abc import Mapping
from dataclasses import replace
from datetime import date
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from intelligence.runtime.turn_control_core import TurnControlCore
from intelligence.services import finance_query
from intelligence.services.agent_runtime import ModelToolCall, ModelTurn
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.episode_protocol import (
    build_episode_input,
    build_episode_instructions,
)
from intelligence.services.episode_tools import build_episode_registry
from intelligence.services.research_contract import (
    InformationCutoff,
    ResearchDeadline,
    release_root_budget,
)
from intelligence.services.research_tool_registry import (
    _DEFAULT_TOOL_METADATA,
    InvalidResearchToolArguments,
)

REPO = Path(__file__).resolve().parents[1]
CASES_PATH = REPO / "intelligence/eval/cases/acceptance_cases.json"
ALL_TOOLS: tuple[str, ...] = tuple(_DEFAULT_TOOL_METADATA)

# 低于这个采样数，读数只能回答「现在还错不错」，不能回答「改了之后变好没有」。
_ABLATION_MIN_REPEAT = 3


def _jsonable(value: object) -> object:
    """深转成可序列化结构。

    ``ModelToolCall.arguments`` 经 ``_json_freeze`` 冻成 ``mappingproxy``，而
    ``dict(...)`` 只转最外层——嵌套的 ``filters``/``time_range`` 仍是 mappingproxy，
    ``json.dumps`` 到那一层才抛。2026-08-12 首次真跑就栽在这：模型调用已经花完、
    读数全部算完，**最后一步落盘崩掉，8 次配额白花**。
    序列化是读数管道的一部分，dry-run 的 stub 参数太浅，覆盖不到这条路径。
    """

    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _stub_llm_complete(*_args: object, **_kwargs: object):
    """task frame 路由不得调模型——那是另一层的成本，会污染本量具的读数。"""

    return (None, None, "probe-args-offline")


def _load_cases(tool: str, case_ids: tuple[str, ...]) -> list[dict[str, object]]:
    doc = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    cases = [
        case
        for case in doc["cases"]
        if tool in (case.get("expect_tools") or ())
        and (not case_ids or case.get("id") in case_ids)
    ]
    if not cases:
        raise SystemExit(
            f"验收台账里没有 expect_tools 含 {tool} 的题"
            + (f"（且 id 限定为 {', '.join(case_ids)}）" if case_ids else "")
        )
    return cases


def _schema_fingerprint(definitions: list[dict[str, object]], tool: str) -> str | None:
    """指纹进读数：两次读数不同时，先看是不是 schema 本身变了（结论携带成立条件）。"""

    for definition in definitions:
        function = definition.get("function")
        if isinstance(function, dict) and function.get("name") == tool:
            blob = json.dumps(function, ensure_ascii=False, sort_keys=True)
            return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]
    return None


def _classify(exc: Exception) -> str:
    """把校验失败压成可计数的类目。**未知形状必须单列，不能并进 other**。

    认不出来就 fail closed（BUILD 模式 7）：一个静默归入 ``other`` 的新错法，
    会让下一轮读数看起来「没有新问题」。
    """

    message = str(exc)
    table = {
        "date filters must use time_range": "date_in_filters",
        "in filter requires an array": "in_needs_array",
        "unknown field": "cross_dataset_field",
        "unknown dataset": "unknown_dataset",
        # 2026-08-12 首次真实基线的**头号错法**（9/13），而历史 run 挖掘里一次都没见过
        # ——历史那批是另一个模型（glm 时代），现在生产是 gpt-5.6-terra。
        # **失败分类学是模型专属的**，换模型要重测，别拿旧 taxonomy 当当前事实。
        #
        # 具体形状：order_by 写成单个对象 {"field":..,"direction":..} 而不是
        # 数组 [{...}]。schema 里明明是 "type":"array"，但没有例子——正是
        # ai-agent-book ch4 §3 点名的「JSON Schema 描述得了类型，描述不了
        # 典型的参数组合，这些隐式约定靠例子最容易传达」。
        "order_by must be an array": "order_by_not_array",
        "filters must be an array": "filters_not_array",
        "must be an array of strings": "string_array_shape",
    }
    for needle, label in table.items():
        if needle in message:
            return label
    if isinstance(exc, InvalidResearchToolArguments):
        return f"invalid_arguments:{getattr(exc, 'code', 'unknown')}"
    return f"unclassified:{type(exc).__name__}"


def _validate_finance_call(
    call: ModelToolCall,
    *,
    as_of: date,
    max_rows: int,
) -> dict[str, object]:
    """跑生产同一条校验链，但停在编译，不执行。"""

    cutoff = InformationCutoff(as_of, "requested")
    # 保真性观测必须在校验之前取。第一版放在成功分支里，dry-run 当场证伪：
    # stub 写了 limit=200 却报 limit_over_cap=0——因为字段错误先抛，早退跳过了
    # 这条观测。**一个错法不该掩盖另一个错法的计数。**
    requested = call.arguments.get("limit")
    observation: dict[str, object] = {
        "limit_requested": requested,
        "limit_over_cap": bool(isinstance(requested, int) and requested > max_rows),
    }
    try:
        spec = finance_query.FinanceQuerySpec.from_arguments(call.arguments)
        normalized, notes = finance_query.normalize_spec(spec)
        finance_query._compile_query(
            normalized,
            information_cutoff=cutoff,
            max_rows=max_rows,
        )
    except Exception as exc:  # noqa: BLE001 - 试验场要如实报告任何失败
        return observation | {
            "valid": False,
            "failure": _classify(exc),
            "detail": str(exc)[:180],
        }
    return observation | {
        "valid": True,
        # 代偿不是免费的：它意味着模型第一次写错了，只是 harness 兜住了。
        # 分开计数，否则「合法率 100%」会掩盖「每次都要兜」。
        "compensated": [str(note)[:120] for note in notes],
    }


def _probe_case(
    case: dict[str, object],
    *,
    tool: str,
    client,
    timeout: float,
    attempt: int,
) -> dict[str, object]:
    question = str(case["query"])
    as_of = str(case.get("date") or date.today().isoformat())
    control = TurnControlCore().control(
        question,
        context="",
        previous_frame=None,
        previous_intent=None,
        previous_turn_id=None,
        llm_complete=_stub_llm_complete,
    )
    task_id = f"probe-args:{case['id']}:{attempt}:{int(time.time()*1000)}"
    try:
        context = build_episode_context(
            control.task_frame,
            task_id=task_id,
            capabilities=ALL_TOOLS,
            tier="deep",
            timeout=timeout,
            today=as_of,
            latest_data_date=as_of,
        )
        registry = build_episode_registry(control.task_frame, context)
        context = replace(context, deadline=ResearchDeadline.from_timeout(timeout))
        definitions = registry.tool_definitions(context.contract.allowed_capabilities)
        fingerprint = _schema_fingerprint(definitions, tool)
        # 活性检查：工具没进 definitions 就是无效样本，绝不能记成「模型没用它」。
        if fingerprint is None:
            return {
                "case_id": case["id"],
                "attempt": attempt,
                "live": False,
                "skipped": (
                    f"{tool} 未出现在本题的 tool_definitions 里"
                    f"（question_type={control.task_frame.question_type}）——无效样本"
                ),
            }
        messages: list[dict[str, object]] = [
            {
                "role": "system",
                "content": build_episode_instructions(
                    control.task_frame, context, registry
                ),
            },
            {
                "role": "user",
                "content": build_episode_input(control.task_frame, context),
            },
        ]
        started = time.monotonic()
        turn: ModelTurn = client.complete(
            messages=messages,
            tools=definitions,
            timeout=timeout,
        )
        elapsed = round(time.monotonic() - started, 2)
        # provider 报错的样本是**废样本**，绝不能记成「模型这轮没调工具」。
        # 2026-08-12 首跑就栽在这：8/8 显示「没调目标工具」，看着像个结论，
        # 实际是 `未配置 LLM key`、每次 0.0 秒、配额一分没花。量具陷阱第一条
        # ——红灯来自工具。认不出来就 fail closed（BUILD 模式 7）。
        if turn.error:
            return {
                "case_id": case["id"],
                "attempt": attempt,
                "live": False,
                "model_error": turn.error,
                "seconds": elapsed,
                "skipped": f"provider 未产出可判样本：{turn.error}",
            }
        calls = [call for call in turn.tool_calls if call.name == tool]
        results = [
            _validate_finance_call(
                call,
                as_of=date.fromisoformat(as_of),
                max_rows=_agent_max_rows(),
            )
            | {"arguments": _jsonable(call.arguments)}
            for call in calls
        ]
        return {
            "case_id": case["id"],
            "attempt": attempt,
            "live": True,
            "seconds": elapsed,
            "schema_fingerprint": fingerprint,
            "provider": turn.provider_name,
            "model_error": turn.error,
            "tool_calls_total": len(turn.tool_calls),
            "tool_calls_for_target": len(calls),
            "other_tools": sorted(
                {call.name for call in turn.tool_calls if call.name != tool}
            ),
            "validations": results,
        }
    finally:
        release_root_budget(task_id)


def _agent_max_rows() -> int:
    from intelligence.services.episode_tools import _AGENT_FINANCE_QUERY_MAX_ROWS

    return _AGENT_FINANCE_QUERY_MAX_ROWS


class _StubClient:
    """dry-run 用：一坏一好两个调用，把量具的两条分支都走到。零配额。

    只发坏调用是不够的——那样只证明「能报错」，不能证明「合法的不会被误报」。
    误报的量具比没有量具更糟：它会把改进读成退步。
    """

    def complete(self, *, messages, tools, timeout):  # noqa: ANN001, ARG002
        return ModelTurn(
            content="",
            tool_calls=(
                ModelToolCall(
                    call_id="stub-bad",
                    name="finance_query",
                    arguments={
                        "dataset": "market_daily",
                        # 跨 dataset 字段：market_daily 的成交额叫 total_amount
                        "metrics": ["amount"],
                        "dimensions": ["trade_date"],
                        # 同时超上限：验证一个错法不会掩盖另一个的计数
                        "limit": 200,
                    },
                ),
                ModelToolCall(
                    call_id="stub-good",
                    name="finance_query",
                    arguments={
                        "dataset": "market_daily",
                        "metrics": ["total_amount"],
                        "dimensions": ["trade_date"],
                        "time_range": {"start": "2026-07-23", "end": "2026-07-23"},
                        "limit": 5,
                    },
                ),
                ModelToolCall(
                    call_id="stub-compensated",
                    name="finance_query",
                    arguments={
                        # 日期写进 filters 的 eq 形态：76aa7d26（2026-08-07）起会被
                        # 自动搬进 time_range 并回话，判定「合法但被代偿」。
                        # 这一路必须有 stub 覆盖，否则 compensated 计数器永远是 0，
                        # 而没人会发现它其实从来没被走到过。
                        "dataset": "market_daily",
                        "metrics": ["total_amount"],
                        "dimensions": ["trade_date"],
                        "filters": [
                            {"field": "trade_date", "op": "eq", "value": "2026-07-23"}
                        ],
                        "limit": 5,
                    },
                ),
            ),
            provider_name="stub",
        )


def _provenance(model: str, repeat: int) -> dict[str, object]:
    def _git(*args: str) -> str:
        try:
            return subprocess.run(
                ["git", *args], cwd=REPO, capture_output=True, text=True, timeout=10
            ).stdout.strip()
        except Exception:  # noqa: BLE001
            return ""

    dirty = _git("status", "--porcelain")
    return {
        "interpreter": sys.executable,
        "tree": str(REPO),
        "revision": _git("rev-parse", "HEAD")[:12],
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "dirty": bool(dirty),
        "model": model,
        "repeat": repeat,
        "agent_max_rows": _agent_max_rows(),
        # 读数自述它能不能当消融判据用，别让下一个人自己猜。
        "ablation_ready": repeat >= _ABLATION_MIN_REPEAT,
        "ablation_note": (
            ""
            if repeat >= _ABLATION_MIN_REPEAT
            else (
                f"repeat={repeat} < {_ABLATION_MIN_REPEAT}：本读数只能回答"
                "「现在还错不错」，不能回答「改了之后是否变好」——"
                "低采样下的排序是噪声。做消融请重跑并抬 --repeat。"
            )
        ),
    }


def _summarize(readings: list[dict[str, object]]) -> dict[str, object]:
    live = [r for r in readings if r.get("live")]
    validations = [v for r in live for v in r.get("validations", [])]
    failures: dict[str, int] = {}
    compensated = 0
    over_cap = 0
    for item in validations:
        # 保真性观测与合法性是**两个独立维度**，不能嵌套在 valid 分支里数。
        # 第一版嵌套了，dry-run 当场读出 limit_over_cap=0 而 stub 明明写了 200——
        # 同一个「错误路径掩盖观测」的毛病，在取值处和汇总处各犯了一次。
        if item.get("limit_over_cap"):
            over_cap += 1
        if item.get("valid"):
            if item.get("compensated"):
                compensated += 1
        else:
            key = str(item.get("failure"))
            failures[key] = failures.get(key, 0) + 1
    valid = sum(1 for item in validations if item.get("valid"))
    errored = [r for r in readings if r.get("model_error")]
    return {
        # usable=false 时**下面所有数都不成立**，别读。放在第一个键，
        # 因为被截断时首先要活下来的是这条限定语（BUILD 模式 4）。
        "usable": bool(live) and not errored,
        "unusable_reason": (
            f"{len(errored)}/{len(readings)} 个样本 provider 报错："
            f"{errored[0].get('model_error')}"
            if errored
            else ("没有任何 live 样本" if not live else "")
        ),
        "cases_attempted": len(readings),
        "cases_live": len(live),
        "cases_model_error": len(errored),
        "cases_skipped": len(readings) - len(live) - len(errored),
        "tool_calls_validated": len(validations),
        "valid": valid,
        "invalid": len(validations) - valid,
        "valid_rate": (round(valid / len(validations), 3) if validations else None),
        "compensated_but_valid": compensated,
        "limit_over_cap": over_cap,
        "failure_taxonomy": dict(sorted(failures.items())),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="参数构造试验场：模型看到 schema 后写出来的参数合不合法",
    )
    parser.add_argument("--tool", default="finance_query", choices=ALL_TOOLS)
    parser.add_argument("--repeat", type=int, default=1, help="每题跑几次")
    parser.add_argument("--case-ids", default="", help="逗号分隔，限定题目")
    parser.add_argument("--model", default="glm-5.2")
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--dry-run", action="store_true", help="stub 模型，零配额")
    parser.add_argument("--out", type=Path, default=None, help="读数落盘路径")
    args = parser.parse_args()

    if args.tool != "finance_query":
        raise SystemExit(
            "当前只实现了 finance_query 的离线校验链。"
            "别的工具吃自由文本 query，没有等价的『合法性』判据——"
            "要扩先想清楚那个工具的判据是什么，不要硬套。"
        )

    cases = _load_cases(args.tool, tuple(x for x in args.case_ids.split(",") if x))
    client = _StubClient() if args.dry_run else _build_client(args.model)

    print(f"题集：{len(cases)} 道 × repeat {args.repeat}"
          f"{'（dry-run，零配额）' if args.dry_run else ''}")
    readings: list[dict[str, object]] = []
    for attempt in range(1, args.repeat + 1):
        for case in cases:
            reading = _probe_case(
                case,
                tool=args.tool,
                client=client,
                timeout=args.timeout,
                attempt=attempt,
            )
            readings.append(reading)
            _print_reading(reading)

    summary = _summarize(readings)
    provenance = _provenance("stub" if args.dry_run else args.model, args.repeat)
    payload = {"provenance": provenance, "summary": summary, "readings": readings}

    print("\n" + "=" * 62)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not provenance["ablation_ready"]:
        print(f"\n⚠ {provenance['ablation_note']}")
    if args.out:
        args.out.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\n读数落盘：{args.out}")
    if not summary["usable"]:
        # 退出码要能被调用方读懂：无效读数必须是红的，否则它会被当成
        # 「测过了，没问题」写进下一份报告。
        print(f"\n❌ 读数不可用：{summary['unusable_reason']}", file=sys.stderr)
        return 2
    return 0


def _build_client(model: str):
    from intelligence.runtime.glm_agent_runtime import GLMModelClient

    return GLMModelClient(model)


def _print_reading(reading: dict[str, object]) -> None:
    case_id = reading.get("case_id")
    if not reading.get("live"):
        print(f"  ⊘ {case_id}: {reading.get('skipped')}")
        return
    validations = reading.get("validations") or []
    if not validations:
        others = reading.get("other_tools") or []
        print(
            f"  · {case_id}: 模型这轮没调目标工具"
            f"（调了 {', '.join(others) if others else '无'}）"
        )
        return
    for item in validations:
        if item.get("valid"):
            marks = []
            if item.get("compensated"):
                marks.append("代偿")
            if item.get("limit_over_cap"):
                marks.append(f"limit={item.get('limit_requested')}>上限")
            suffix = f"  [{'/'.join(marks)}]" if marks else ""
            print(f"  ✓ {case_id}: 合法{suffix}")
        else:
            print(f"  ✗ {case_id}: {item.get('failure')} — {item.get('detail')}")


if __name__ == "__main__":
    raise SystemExit(main())
