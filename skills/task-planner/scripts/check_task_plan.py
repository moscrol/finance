#!/usr/bin/env python3
"""task-plan 关卡校验（Inversion 模式的「代码门控」）。

定位：task-planner 这个 Inversion skill 的硬关卡。Agent 在批量/会话级高风险任务
（复盘批处理、DuckDB 大回填、开新题材）动手前，要先「采访」用户、把回答合成成一份
`task-plan` JSON；本脚本检查这份计划是否把所有**不可协商的门控字段**都答全且合法。

- 全部通过 → 打印 OK 摘要，退出码 0 → 才允许进入抓数/回填/写库
  （market-overview / duckdb-backfill / theme-radar / top-gainers-feishu ...）。
- 任一缺失/非法 → 打印 GATE VIOLATIONS 列表，退出码 1 → 禁止抓数/写任何库。
- 用法错误（没传文件/JSON 解析失败）→ 退出码 2。

这把原来「问全才动手」的散文约定硬化成 exit-code 门，体例同知识库仓
`disclosure-archive` 的 `--apply` 菱形门、本仓 `opinion-cross` 的复核门
（exit-0 才算过）。脚本**只读**，不抓任何数据、不写任何库文件，且
**自包含**（不依赖 obs_log 等共享库，本仓 skills/lib 无该模块）。

用法::

    python3 skills/task-planner/scripts/check_task_plan.py /tmp/task-plan.json
    python3 skills/task-planner/scripts/check_task_plan.py --template

退出码 0 = 计划合法可放行，1 = 门控未过，2 = 用法/解析错误。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 任务类型：决定哪些门控强约束（如无前视）。
_TASK_TYPES = {"复盘批处理", "批量回填", "开新题材"}
# 需要「无前视确认」的任务类型（涉及历史区间的盘面数据，绝不能引用 D0 之后数据）。
_LOOKBACK_TASKS = {"复盘批处理", "批量回填"}
# 允许的数据来源（可多选）。
_DATA_SOURCES = {"fupanhui", "ifind", "akshare", "duckdb", "feishu", "wiki"}
# 结果落库去向（单选）：飞书 Bitable / 本地 DuckDB / 只读分析不落库。
_TARGET_SINKS = {"feishu", "duckdb", "readonly"}
# 遇到缺数据/异常的处置。
_ON_MISSING_MODES = {"ask", "skip", "pending"}
# 禁止直接在其上做大任务的分支。
_PROTECTED_BRANCHES = {"main", "master"}

# 模板：每个 key 都是一个不可协商的门控；agent 采访完用户后逐项填写。
_TEMPLATE = {
    "task_id": "",
    "goal": "",
    "task_type": "",
    "scope": {"date_range": {"start": "", "end": ""}, "symbols": [], "themes": []},
    "data_source": [],
    "target_sink": "",
    "env": {"branch": ""},
    "credentials_ready": None,
    "no_lookahead_ack": None,
    "require_dryrun_approval": None,
    "skip_rules": [],
    "on_missing_data": "",
    "handoff": [],
}


def _is_nonempty_str(value) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _is_nonempty_list(value) -> bool:
    return isinstance(value, list) and len(value) > 0


def _is_bool(value) -> bool:
    return isinstance(value, bool)


def validate(plan: dict) -> list[str]:
    """返回门控违规说明列表；空列表表示全部通过。"""
    issues: list[str] = []

    if not isinstance(plan, dict):
        return ["计划顶层必须是一个 JSON 对象"]

    if not _is_nonempty_str(plan.get("task_id")):
        issues.append("task_id 缺失：必须给这次任务一个非空标识")
    if not _is_nonempty_str(plan.get("goal")):
        issues.append("goal 缺失：必须说明这次任务要达成什么")

    task_type = plan.get("task_type")
    if task_type not in _TASK_TYPES:
        issues.append(
            "task_type 非法（得到 {!r}）：必须是 复盘批处理/批量回填/开新题材 之一".format(task_type)
        )

    scope = plan.get("scope")
    if not isinstance(scope, dict):
        issues.append("scope 缺失：必须给出范围（date_range 或 symbols 或 themes）")
    else:
        dr = scope.get("date_range")
        has_range = (
            isinstance(dr, dict)
            and _is_nonempty_str(dr.get("start"))
            and _is_nonempty_str(dr.get("end"))
        )
        has_symbols = _is_nonempty_list(scope.get("symbols"))
        has_themes = _is_nonempty_list(scope.get("themes"))
        if not (has_range or has_symbols or has_themes):
            issues.append(
                "scope 未定范围：date_range（start+end 都填）/ symbols 非空 / themes 非空，至少给一个"
            )

    data_source = plan.get("data_source")
    if not _is_nonempty_list(data_source):
        issues.append(
            "data_source 缺失：必须列出数据来源（fupanhui/ifind/akshare/duckdb/feishu/wiki 的非空子集）"
        )
    else:
        bad = [s for s in data_source if s not in _DATA_SOURCES]
        if bad:
            issues.append(
                "data_source 含非法项 {!r}：只能取 {}".format(bad, sorted(_DATA_SOURCES))
            )

    target_sink = plan.get("target_sink")
    if target_sink not in _TARGET_SINKS:
        issues.append(
            "target_sink 非法（得到 {!r}）：必须是 feishu/duckdb/readonly 之一（显式声明结果去向）".format(
                target_sink
            )
        )

    env = plan.get("env")
    if not isinstance(env, dict):
        issues.append("env 缺失：必须给出 branch")
    else:
        branch = env.get("branch")
        if not _is_nonempty_str(branch):
            issues.append("env.branch 缺失：必须指定任务分支")
        elif branch.strip() in _PROTECTED_BRANCHES:
            issues.append(
                f"env.branch 不能是 {branch.strip()}：大任务必须开任务分支，不在 main/master 上做"
            )

    if not _is_bool(plan.get("credentials_ready")):
        issues.append(
            "credentials_ready 缺失：必须显式声明飞书/fupanhui/iFinD 凭证是否就位（bool）"
        )

    no_lookahead = plan.get("no_lookahead_ack")
    if not _is_bool(no_lookahead):
        issues.append("no_lookahead_ack 缺失：必须显式声明是否确认无前视（bool）")
    elif task_type in _LOOKBACK_TASKS and no_lookahead is not True:
        issues.append(
            "no_lookahead_ack 必须为 true：{} 涉及历史区间，必须确认只用 D0 及以前数据、绝不引用未来".format(
                task_type
            )
        )

    require_dryrun = plan.get("require_dryrun_approval")
    if not _is_bool(require_dryrun):
        issues.append("require_dryrun_approval 缺失：必须显式声明写入前是否要 dry-run 复核（bool）")
    elif target_sink in {"feishu", "duckdb"} and require_dryrun is not True:
        issues.append(
            "require_dryrun_approval 必须为 true：target_sink={} 会写库，落库前必须先 dry-run 复核".format(
                target_sink
            )
        )

    if not isinstance(plan.get("skip_rules"), list):
        issues.append("skip_rules 缺失：必须给出跳过规则列表（可为空列表，但 key 必须在）")

    on_missing = plan.get("on_missing_data")
    if on_missing not in _ON_MISSING_MODES:
        issues.append(
            "on_missing_data 非法（得到 {!r}）：遇到缺数据/异常的处置必须是 ask/skip/pending".format(
                on_missing
            )
        )

    if not _is_nonempty_list(plan.get("handoff")):
        issues.append("handoff 缺失：必须列出计划交接给哪些下游 skill")

    return issues


def main() -> None:
    parser = argparse.ArgumentParser(
        description="校验 task-plan 是否答全所有不可协商门控（Inversion 代码门）。"
    )
    parser.add_argument("plan", nargs="?", help="task-plan JSON 文件路径")
    parser.add_argument(
        "--template",
        action="store_true",
        help="打印一份空白 task-plan 模板（逐项填写）后退出",
    )
    args = parser.parse_args()

    if args.template:
        print(json.dumps(_TEMPLATE, ensure_ascii=False, indent=2))
        sys.exit(0)

    if not args.plan:
        parser.print_usage()
        print("error: 需要传入 task-plan JSON 文件路径（或用 --template）")
        sys.exit(2)

    path = Path(args.plan)
    if not path.is_file():
        print(f"error: 找不到计划文件 {path}")
        sys.exit(2)

    try:
        plan = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"error: 计划文件不是合法 JSON：{exc}")
        sys.exit(2)

    issues = validate(plan)

    if not issues:
        print(f"TASK PLAN GATE: OK — {len(_TEMPLATE)} 项门控全部答全，放行抓数/回填/写库。")
        sys.exit(0)

    print(f"TASK PLAN GATE VIOLATIONS — {len(issues)} 项门控未过，禁止抓数/写库：")
    for issue in issues:
        print(f"  [GATE] {issue}")
    sys.exit(1)


if __name__ == "__main__":
    main()
