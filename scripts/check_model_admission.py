#!/usr/bin/env python3
"""读数前的生效模型准入检查（spec 2026-09-02 §3.5.4 硬门 3 的「比对」半边）。

用法::

    python scripts/check_model_admission.py --expect-model glm-5.3 \\
        $FORESIGHT_USERS_DIR/<user>/runs/<run_id>          # run 目录
        path/to/continuous-episode.json                    # 或单个产物
        path/to/episode-store-root                         # 或整棵目录（递归找）

同一模型有多个合法名字（带日期的快照名等）就重复传 ``--expect-model``。

子分支：产物里的 ``branch_completed`` 带回了分支每轮生效模型（``served_models``）就直接查；
老产物没带时去 episode store 读分支自己的事件——``--episode-store`` 给根目录，不给就按生产
同一顺序找（``FORESIGHT_EPISODE_STORE`` → ``$FINANCE_WS/state/episodes`` →
``~/.finance-runtime/episodes``，目录存在才用）。分支调用过模型却查不到证据 → 无证据。

退出码：0 = 全部准入；1 = 有产物实际服务了别的模型（读数作废）；
2 = 证明不了（没有产物 / 没有任何 turn 带回 model / 有「未回」且未显式放行）。

只读、不发请求。判定逻辑在 ``intelligence/eval/model_admission.py``。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from intelligence.eval.model_admission import (  # noqa: E402
    VERDICT_ADMITTED,
    VERDICT_MISMATCH,
    check_paths,
    overall_exit_code,
)
from intelligence.services.episode_store import resolve_episode_store_root  # noqa: E402

_MARK = {VERDICT_ADMITTED: "✅ 准入", VERDICT_MISMATCH: "❌ 错配"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="检查读数产物里的生效模型（响应体 model）是否就是要测的模型。",
    )
    parser.add_argument("paths", nargs="+", help="run 目录、episode 产物文件或要递归查找的目录")
    parser.add_argument(
        "--expect-model",
        action="append",
        required=True,
        dest="expected",
        help="期望的生效模型名（大小写/空白不敏感；可重复传以接受别名）",
    )
    parser.add_argument(
        "--allow-unreported",
        action="store_true",
        help="有匹配证据且无错配时，放行「provider 未回 model」的 turn（默认按证据不全拦下）",
    )
    parser.add_argument(
        "--episode-store",
        default=None,
        help="子分支 episode 所在 store 根目录（老产物补证用）；默认按生产顺序找，存在才用",
    )
    parser.add_argument("--no-episode-store", action="store_true", help="不去 episode store 补证")
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    return parser


def default_episode_store() -> Path | None:
    root = resolve_episode_store_root()
    return root if root.is_dir() else None


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.no_episode_store:
        store = None
    elif args.episode_store:
        store = Path(args.episode_store).expanduser()
    else:
        store = default_episode_store()
    results = check_paths(
        args.paths, args.expected, allow_unreported=args.allow_unreported, episode_store=store
    )
    code = overall_exit_code(results)
    if args.json:
        print(
            json.dumps(
                {
                    "exit_code": code,
                    "episode_store": None if store is None else str(store),
                    "results": [item.to_dict() for item in results],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return code
    for item in results:
        print(f"{_MARK.get(item.verdict, '⚠️ 无证据')}  {item.source}\n    {item.reason}")
    summary = {0: "全部准入，可以当读数用。", 1: "有错配：对应读数作废。", 2: "证据不全：证明不了用的是哪个模型，不能当读数用。"}
    print(f"\n{len(results)} 个产物 → {summary[code]}（exit {code}）；子分支补证 store：{store or '未用'}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
