#!/usr/bin/env python3
"""情景树 v0 CLI（工单 #37 / G-15）。产品语言只用「情景树」；「推演」是口语翻译。

    # 起草：校验 + 编译，打印拒绝码，不登记
    python3 scripts/scenario_tree.py draft --spec tree.json

    # 登记（要 projection_hash / model_id / framework_version；同时在 checkpoints 落一条 scenario_tree 可证伪点）
    python3 scripts/scenario_tree.py register --spec tree.json [--user U] [--status confirmed]

    # 逐日解析：读 slice(as_of, C=as_of) 判走了哪条边；到达节点的剧本进回检队列
    python3 scripts/scenario_tree.py resolve --tree-id st-… --as-of 2026-09-02 [--user U] [--db-path …]
    python3 scripts/scenario_tree.py resolve --all --as-of 2026-09-02      # 全部 confirmed / resolving 的树

    # 看一棵树的当前状态 / 三项回检
    python3 scripts/scenario_tree.py show --tree-id st-…
    python3 scripts/scenario_tree.py recheck [--user U] [--json]

树 JSON 形状（v0）：
    {"as_of","scope","entity_ids","max_depth"(<=3),"framework_version","model_id","projection_hash",
     "nodes":[{"node_id","depth","parent","condition":{"all":[{"label","op","value"}]}|"otherwise"|null,
               "step_kind":"T+1|T+3|T+5","script":{"variables":[…],"downgrade_or_abandon_conditions":[…]}}]}
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from intelligence import userspace  # noqa: E402
from intelligence.services import scenario_trees as st  # noqa: E402


def _print_rejections(exc: st.ScenarioTreeRejected, as_json: bool) -> int:
    if as_json:
        print(json.dumps([r.to_dict() for r in exc.rejections], ensure_ascii=False, indent=2))
    else:
        print("情景树被拒：")
        for r in exc.rejections:
            print(f"  [{r.code}] {r.where}: {r.detail}")
    return 2


def _load_spec(path: str) -> dict:
    return json.loads(Path(path).expanduser().read_text(encoding="utf-8"))


def cmd_draft(args: argparse.Namespace) -> int:
    try:
        tree = st.ensure_valid(_load_spec(args.spec))
    except st.ScenarioTreeRejected as exc:
        return _print_rejections(exc, args.json)
    out = tree.to_dict()
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(f"编译通过：{len(tree.nodes)} 个节点，深度 {tree.max_depth}，scope={tree.scope} 实体={list(tree.entity_ids)}")
        for n in tree.nodes:
            cond = "根" if n.condition is None else ("otherwise" if n.condition == st.OTHERWISE else " ∧ ".join(f"{p.label} {p.op} {p.value}" for p in n.condition))
            print(f"  {'  ' * n.depth}{n.node_id} [{n.step_kind or '-'}] {cond}")
    return 0


def cmd_register(args: argparse.Namespace) -> int:
    us = userspace.user_space(args.user)
    us.ensure_dir()
    try:
        tree = st.ensure_valid(_load_spec(args.spec))
        _, rec = st.register(st.trees_path(us), tree, checkpoints_path=us.checkpoints_path, status=args.status)
    except st.ScenarioTreeRejected as exc:
        return _print_rejections(exc, args.json)
    print(json.dumps(rec if args.json else {"id": rec["id"], "status": rec["status"], "checkpoint_id": rec["checkpoint_id"]}, ensure_ascii=False, indent=2, default=str))
    return 0


def _slice_fn(db_path: str | None, checkpoints_path):
    from intelligence.services import river

    def fn(as_of: str, entity: str, **kw):
        return river.slice_river(as_of, entity, knowledge_cutoff=kw.get("knowledge_cutoff") or as_of, db_path=db_path, checkpoints_path=checkpoints_path)

    return fn


def resolve_open_trees(us, as_of: str, *, db_path: str | None = None, tree_id: str | None = None) -> list[st.ResolutionStep]:
    """解析一棵或全部 confirmed / resolving 的树，step 追加进台账。供 CLI 与每日复盘钩子共用。"""
    path = st.trees_path(us)
    records = st.load(path)
    ids = [tree_id] if tree_id else [r["id"] for r in records if r.get("record") == "tree"]
    steps: list[st.ResolutionStep] = []
    fn = _slice_fn(db_path, us.checkpoints_path)
    for tid in ids:
        state = st.current_state(records, tid)
        if state is None or state.get("status") not in ("confirmed", "resolving"):
            continue
        if as_of <= str(state["realized_path"][-1]["resolved_as_of"]):
            continue  # 这天已经解析过 / 还没到
        step = st.resolve(state, as_of, slice_fn=fn, checkpoints_path=us.checkpoints_path)
        st.append_step(path, step)
        steps.append(step)
    return steps


def cmd_resolve(args: argparse.Namespace) -> int:
    us = userspace.user_space(args.user)
    if not args.all and not args.tree_id:
        raise SystemExit("要么 --tree-id，要么 --all")
    try:
        steps = resolve_open_trees(us, args.as_of, db_path=args.db_path, tree_id=None if args.all else args.tree_id)
    except st.ScenarioTreeRejected as exc:
        return _print_rejections(exc, args.json)
    if args.json:
        print(json.dumps([s.to_dict() for s in steps], ensure_ascii=False, indent=2, default=str))
    else:
        if not steps:
            print("没有可解析的树（都在终态，或这天已解析）")
        for s in steps:
            print(f"{s.tree_id} @{s.as_of}: {s.from_node} → {s.node_id or '—'} [{s.status}] {s.reason}  projection={s.projection_hash}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    us = userspace.user_space(args.user)
    state = st.current_state(st.load(st.trees_path(us)), args.tree_id)
    if state is None:
        raise SystemExit(f"没有 {args.tree_id}")
    print(json.dumps(state, ensure_ascii=False, indent=2, default=str))
    return 0


def cmd_recheck(args: argparse.Namespace) -> int:
    us = userspace.user_space(args.user)
    rc = st.recheck(st.load(st.trees_path(us)))
    d = rc.to_dict()
    if args.json:
        print(json.dumps(d, ensure_ascii=False, indent=2))
    else:
        print(f"情景树回检：{d['trees']} 棵，{d['steps']} 步；落进声明分枝 {d['steps_declared']} / otherwise {d['steps_otherwise']} / unresolvable {d['steps_unresolvable']}")
        print(f"  otherwise 占比：{d['otherwise_share']}")
        print(f"  沿路剧本登记 {d['reached_scripts']} 条（对错见 checkpoint calibrate 的观察剧本一格）；规则样本 {d['samples']} 条（存在 step 记录里，G-16 提议器消费）")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for name, fn in (("draft", cmd_draft), ("register", cmd_register)):
        p = sub.add_parser(name)
        p.add_argument("--spec", required=True)
        p.add_argument("--user", default=None)
        p.add_argument("--json", action="store_true")
        if name == "register":
            p.add_argument("--status", default="confirmed", choices=("drafted", "confirmed"))
        p.set_defaults(func=fn)
    r = sub.add_parser("resolve")
    r.add_argument("--tree-id", default=None)
    r.add_argument("--all", action="store_true")
    r.add_argument("--as-of", required=True)
    r.add_argument("--user", default=None)
    r.add_argument("--db-path", default=None)
    r.add_argument("--json", action="store_true")
    r.set_defaults(func=cmd_resolve)
    s = sub.add_parser("show")
    s.add_argument("--tree-id", required=True)
    s.add_argument("--user", default=None)
    s.set_defaults(func=cmd_show)
    c = sub.add_parser("recheck")
    c.add_argument("--user", default=None)
    c.add_argument("--json", action="store_true")
    c.set_defaults(func=cmd_recheck)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
