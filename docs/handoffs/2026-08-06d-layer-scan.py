"""层边界扫描原型 — 2026-08-06d handoff 附件。

这是原型，不是门禁。落成 scripts/layer_audit.py 时按 handoff B.1 的三条要求改造：
  1) harness 白名单写成显式常量（别靠文件名前缀猜）
  2) 输出自述审的是哪个 revision
  3) 以当前 7 条接缝为基线，只减不增

用法（仓根）：.venv-workbench/bin/python docs/handoffs/2026-08-06d-layer-scan.py
"""
import ast
import pathlib
import collections
import json

ROOT = pathlib.Path("intelligence")
PKG = "intelligence"

# harness 种子：循环 / 编排 / 运行时 / 工具注册与执行
HARNESS_SEED = {
    "services.agent_episode", "services.continuous_turn_adapter", "services.episode_protocol",
    "services.episode_tools", "services.episode_factory", "services.episode_finalizer",
    "services.episode_semantic_verifier", "services.episode_session", "services.episode_progress",
    "services.turn_controller", "services.turn_control_core", "services.conversation_orchestrator",
    "services.openai_agents_runtime", "services.agent_runtime_factory", "services.glm_agent_runtime",
    "services.agent_runtime", "services.research_tool_registry", "services.sub_research",
    "services.continuous_sub_research", "services.codex_headless_runtime",
    "services.headless_tool_gateway", "services.agent.py",
}

def modname(p: pathlib.Path) -> str:
    rel = p.relative_to(ROOT).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)

files = [p for p in ROOT.rglob("*.py") if "/tests/" not in str(p) and p.name != "__init__.py"]
mods, loc = {}, {}
for p in files:
    m = modname(p)
    mods[m] = p
    loc[m] = sum(1 for _ in p.open(encoding="utf-8", errors="ignore"))

edges = collections.defaultdict(set)
for m, p in mods.items():
    try:
        tree = ast.parse(p.read_text(encoding="utf-8", errors="ignore"))
    except SyntaxError:
        continue
    for node in ast.walk(tree):
        tgt = None
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith(PKG + "."):
            tgt = node.module[len(PKG) + 1:]
        elif isinstance(node, ast.Import):
            for a in node.names:
                if a.name.startswith(PKG + "."):
                    t = a.name[len(PKG) + 1:]
                    if t in mods:
                        edges[m].add(t)
            continue
        if tgt and tgt in mods and tgt != m:
            edges[m].add(tgt)

harness = {m for m in mods if m in HARNESS_SEED}
json.dump({"mods": {m: loc[m] for m in mods},
           "edges": {k: sorted(v) for k, v in edges.items()},
           "harness": sorted(harness)},
          open("/tmp/layer_graph.json", "w"), ensure_ascii=False)
print(f"模块 {len(mods)}  边 {sum(len(v) for v in edges.values())}  harness 种子命中 {len(harness)}/{len(HARNESS_SEED)}")

# ============ 第二段：积木 / 接缝 / 搬迁顺序 ============
g = json.load(open("/tmp/layer_graph.json"))
mods, loc = g["mods"], g["mods"]
edges = {k: set(v) for k, v in g["edges"].items()}
# 修正：这两个名字带 episode、行为也属 harness，补进种子
HARNESS = set(g["harness"]) | {"services.agent", "services.episode_tool_batch",
                               "services.episode_verifier"}
ENTRY = {"api.app", "api.structured_reports", "cli", "eval.runner"}   # 入口/工具，本就要重写
domain = set(mods) - HARNESS - ENTRY

# 传递闭包：某模块能否在不碰 harness 的前提下自洽
def closure(m, seen=None):
    seen = seen if seen is not None else set()
    for t in edges.get(m, ()):
        if t not in seen:
            seen.add(t)
            closure(t, seen)
    return seen

clean, tainted = {}, {}
for m in domain:
    deps = closure(m)
    bad = sorted(deps & HARNESS)
    (tainted if bad else clean)[m] = (loc[m], bad)

print("=== 干净积木（传递闭包不碰 harness，可原样搬）===")
print(f"  {len(clean)} 个模块 / {sum(v[0] for v in clean.values())} 行")
print("=== 被污染积木（间接依赖 harness，要先拆）===")
print(f"  {len(tainted)} 个模块 / {sum(v[0] for v in tainted.values())} 行")
print()
print("=== 污染源排行（拆掉谁能解放最多积木）===")
blame = collections.Counter()
for m, (n_lines, bad) in tainted.items():
    for b in bad:
        blame[b] += 1
for b,c in blame.most_common(10):
    print(f"  {b:<44} 污染 {c} 个领域模块")
print()
print("=== 契约层：harness 与 domain 双方都依赖的（新底座必须说这套话）===")
for m in ("services.research_contract","services.task_frame","services.agent_research",
          "services.evidence_ledger","services.evidence_capabilities","services.research_plan"):
    deps = closure(m)
    bad = sorted(deps & HARNESS)
    print(f"  {m:<40} {loc[m]:>5}行  {'✅ 自身干净' if not bad else '⚠️ 依赖 '+','.join(x.replace('services.','') for x in bad)}")

print()
print("=== 要拆的 7 个污染模块（全部清单）===")
for m, (n_lines, bad) in sorted(tainted.items(), key=lambda kv: -kv[1][0]):
    direct = sorted(edges.get(m,set()) & HARNESS)
    print(f"  {m:<42} {n_lines:>5}行  直接依赖: {', '.join(x.replace('services.','') for x in direct) or '(间接)'}")

g = json.load(open("/tmp/layer_graph.json"))
mods, loc = g["mods"], g["mods"]
edges = {k:set(v) for k,v in g["edges"].items()}
rev = collections.defaultdict(set)
for a,bs in edges.items():
    for b in bs:
        rev[b].add(a)

MOVE = ["services.episode_semantic_verifier","services.episode_tools","services.turn_controller",
        "services.research_tool_registry","services.agent_runtime","services.episode_protocol",
        "services.episode_factory","services.episode_verifier"]
LOOP = {"services.agent_episode","services.glm_agent_runtime","services.agent_runtime_factory",
        "services.episode_session","services.episode_finalizer","services.sub_research",
        "services.continuous_sub_research","services.episode_tool_batch","services.agent",
        "services.turn_control_core","services.episode_progress","services.openai_agents_runtime",
        "services.continuous_turn_adapter","services.conversation_orchestrator",
        "services.codex_headless_runtime","services.headless_tool_gateway"}
MOVESET=set(MOVE)
print(f"{'模块':<38}{'行':>6}{'被引用':>7}{'依赖loop层':>34}")
for m in MOVE:
    dep_loop = sorted((edges.get(m,set()) & LOOP))
    print(f"{m.replace('services.',''):<38}{loc[m]:>6}{len(rev[m]):>7}   "
          f"{', '.join(x.replace('services.','') for x in dep_loop) or '✅ 无'}")
print("\n=== 建议搬迁顺序（依赖 loop 层为 0 的先搬）===")
order=[m for m in MOVE if not (edges.get(m,set()) & LOOP)]
rest=[m for m in MOVE if (edges.get(m,set()) & LOOP)]
for i,m in enumerate(order+rest,1):
    tag = "✅可直接搬" if m in order else "⚠️需先断依赖"
    print(f"  {i}. {m.replace('services.',''):<34}{loc[m]:>6}行  {tag}")
