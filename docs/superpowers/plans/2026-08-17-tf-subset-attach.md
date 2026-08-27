# T-F 摘接对照 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在吸收前底座 `83e83b42` 上只接 EpisodeScope + 工具阶段，过工程门后跑 `A1-market-overview` × 每臂 5 次，交出「接得上 / 接得上但慢了 / 摘不干净」三选一读数。

**Architecture:** 臂 0 用现成树。臂 1 从同一 pin 新开 worktree，整取 spec §4 白名单（用户 2026-08-17 已验分离性：四个接线文件未新增禁止名单 import）。读数口径与 PR #140 一致：repair 看末条 finish，Trace 对账带「有事件则」，空事件不算通过。本窗是可行性探针，不宣称吸收兑现。

**Tech Stack:** 既有 `scripts/run_agent_runtime_benchmark.py`、`.venv-workbench`、`gpt-5.6-terra` @ `x.ailzd.com`。不新写生产代码。

**Spec（已点头，#139 已合 `ef5cb9e4`，本文不改）：** `docs/superpowers/specs/2026-08-17-tf-subset-attach-design.md`

---

## 0. 执行前先读（零上下文）

| 项 | 值 |
|---|---|
| 底座 / 臂 0 | `/Users/a77/fwp-wt-tf-arm-a-83e83b42` @ `83e83b429965a7c084443dbfc775532e92960366` |
| 摘接来源 | 同一仓的 `2a2523f7d26c666ee398d2da730d13cdee778c85`。**禁止**当前 main |
| 整包 A′ 树（对照用，**不是臂 1**） | `/Users/a77/fwp-wt-tf-arm-aprime-2a2523f7` |
| 臂 1 新树 | `/Users/a77/fwp-wt-tf-arm-1-subset`（本计划创建） |
| 题集 | `/Users/a77/fwp-wt-dsh-sample-lock/intelligence/eval/fixtures/frozen-thirty-2026-08-16.questions.json` |
| 解释器 | `/Users/a77/finance-workspace-private/.venv-workbench/bin/python` |
| 数据根 | `/Users/a77/finance-workspace-private` + `/Users/a77/knowledge-base-private/wiki` |
| 产物 | `~/.finance-runtime/tf-subset-20260817/` |
| 烟测 hash 对照 | 两臂 `task_frame_hash` 须仍是 `beb73ad53210cf8138be545ec12c24b35ec4e408fa47daf2614b240c6f67a437` |

硬停：不开 900；不切 8792；不动 T / 30 / 档位 / `ASK_TOOL_BATCH_TIMEOUT`；不退回整包 A′；不改 spec；不为补 repair 样本加跑。

用户已替 §6 预验：两个整取文件顶层 import 只依赖 `research_tool_registry` 与 `agent_runtime.EpisodeEvent`；缺的 3 个符号是 `TOOL_PRE_EXECUTE` / `TOOL_RESULT` / `TOOL_ERROR`，已在接线 hunk 里。分离性成立，仍要在臂 1 树上**再跑一遍**扫描，不能用预验代替工程门。

---

## File Structure

- 臂 1 worktree：只多出 spec §4 那 11 个路径（7 整取 + 4 接线），相对 `83e83b42` 无 §5 路径。
- Create: `~/.finance-runtime/tf-subset-20260817/graft-scan.txt`（工程门扫描收据）
- Create: `docs/handoffs/2026-08-17-tf-subset-attach-readings.md`（10 次读数 + 三选一结论）
- 不改 `intelligence/` 生产逻辑于 gitea/main；摘接只活在臂 1 树。

---

### Task 1: 开臂 1 树并整取白名单

**Files:**
- Create worktree: `/Users/a77/fwp-wt-tf-arm-1-subset`
- Checkout from `2a2523f7` only the §4 paths

- [ ] **Step 1: 确认四棵树和题集还在**

```bash
test -d /Users/a77/fwp-wt-tf-arm-a-83e83b42
test -d /Users/a77/fwp-wt-tf-arm-aprime-2a2523f7
test -f /Users/a77/fwp-wt-dsh-sample-lock/intelligence/eval/fixtures/frozen-thirty-2026-08-16.questions.json
test ! -e /Users/a77/fwp-wt-tf-arm-1-subset
git -C /Users/a77/fwp-wt-tf-arm-a-83e83b42 rev-parse HEAD
# 期望：83e83b429965a7c084443dbfc775532e92960366
```

- [ ] **Step 2: 从臂 0 的仓开新 worktree（detached 底座）**

```bash
git -C /Users/a77/fwp-wt-tf-arm-a-83e83b42 worktree add --detach \
  /Users/a77/fwp-wt-tf-arm-1-subset 83e83b42
git -C /Users/a77/fwp-wt-tf-arm-1-subset rev-parse HEAD
# 期望：83e83b429965a7c084443dbfc775532e92960366
```

- [ ] **Step 3: 整取 §4（用户已验四个接线文件无禁止名单 import，故整文件取，不手剥 hunk）**

```bash
cd /Users/a77/fwp-wt-tf-arm-1-subset
git checkout 2a2523f7 -- \
  intelligence/services/episode_scope.py \
  intelligence/services/episode_event_lanes.py \
  intelligence/tests/test_episode_scope.py \
  intelligence/tests/test_episode_event_lanes.py \
  intelligence/tests/test_tool_stage_events.py \
  intelligence/tests/test_tool_reachability_audit.py \
  scripts/audit_tool_reachability.py \
  intelligence/runtime/agent_episode.py \
  intelligence/runtime/episode_tool_batch.py \
  intelligence/services/research_tool_registry.py \
  intelligence/runtime/headless_tool_gateway.py
```

Expected: 这 11 条进入 index。`git diff --name-only 83e83b42` **恰好**这 11 个路径（测试/脚本若底座没有则是新文件）。

- [ ] **Step 4: 本地分支记下摘接，不推 main**

```bash
git -C /Users/a77/fwp-wt-tf-arm-1-subset switch -c tf/subset-attach-arm1
git -C /Users/a77/fwp-wt-tf-arm-1-subset commit -m "$(cat <<'EOF'
experiment: graft EpisodeScope + tool stages onto 83e83b42

Whitelist only. Do not merge to main.
EOF
)"
```

不要 `git push gitea HEAD:main`。需要备份再 `git push gitea tf/subset-attach-arm1`。

---

### Task 2: 工程门扫描（脏则停）

**Files:**
- Create: `~/.finance-runtime/tf-subset-20260817/graft-scan.txt`

- [ ] **Step 1: §5 路径不得出现在 diff**

```bash
mkdir -p ~/.finance-runtime/tf-subset-20260817
cd /Users/a77/fwp-wt-tf-arm-1-subset
git diff --name-only 83e83b42 > ~/.finance-runtime/tf-subset-20260817/graft-names.txt
python3 - <<'PY'
from pathlib import Path
names = Path.home().joinpath(".finance-runtime/tf-subset-20260817/graft-names.txt").read_text().splitlines()
forbidden = [
    "intelligence/services/runtime_handle.py",
    "intelligence/tests/test_runtime_handle.py",
    "intelligence/services/research_profile.py",
    "intelligence/tests/test_research_profile.py",
    "intelligence/runtime/dsh_stub_runtime.py",
    "intelligence/tests/test_dsh_stub_runtime.py",
    "intelligence/services/episode_projection.py",
    "intelligence/tests/test_episode_projection.py",
    "intelligence/runtime/agent_runtime_factory.py",
    "intelligence/runtime/glm_agent_runtime.py",
    "intelligence/runtime/openai_agents_runtime.py",
    "intelligence/runtime/continuous_turn_adapter.py",
    "intelligence/api/app.py",
]
hit = [n for n in names if n in forbidden or n.endswith("episode_progress.py")]
print("files", len(names))
print("forbidden_hits", hit)
raise SystemExit(1 if hit else 0)
PY
```

Expected: `forbidden_hits []`，exit 0。非空 → **停**，写收据「哪条路径被拖进来」，不准改取整包 A′。

- [ ] **Step 2: 禁止名单符号不得被 import**

```bash
cd /Users/a77/fwp-wt-tf-arm-1-subset
python3 - <<'PY'
from pathlib import Path
root = Path(".")
needles = (
    "runtime_handle",
    "research_profile",
    "dsh_stub_runtime",
    "episode_projection",
    "agent_runtime_factory",
)
allow_comment = True
hits = []
for rel in Path.home().joinpath(".finance-runtime/tf-subset-20260817/graft-names.txt").read_text().splitlines():
    p = Path(rel)
    if not p.exists() or p.suffix != ".py":
        continue
    text = p.read_text()
    for i, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if s.startswith("#"):
            continue
        if s.startswith("import ") or s.startswith("from "):
            if any(n in s for n in needles):
                hits.append(f"{rel}:{i}:{s}")
print("import_hits", hits)
raise SystemExit(1 if hits else 0)
PY
```

Expected: `import_hits []`。注释里出现 RuntimeHandle **允许**（spec §5）。

- [ ] **Step 3: 把两步输出追加进 `graft-scan.txt`**

失败就停。不要进 Task 3 的 live。

---

### Task 3: 单测 + 层级门

**Files:**
- Test: 臂 1 树上的四个新测试 + 被改文件的旧测试
- Run: `scripts/layer_audit.py`

解释器锁死：`PY=/Users/a77/finance-workspace-private/.venv-workbench/bin/python`

- [ ] **Step 1: 四个新测试必绿**

```bash
export PY=/Users/a77/finance-workspace-private/.venv-workbench/bin/python
cd /Users/a77/fwp-wt-tf-arm-1-subset
"$PY" -m pytest -q \
  intelligence/tests/test_episode_scope.py \
  intelligence/tests/test_episode_event_lanes.py \
  intelligence/tests/test_tool_stage_events.py \
  intelligence/tests/test_tool_reachability_audit.py
```

Expected: 全绿。红了 → 停（摘接不干净或底座缺符号）。

- [ ] **Step 2: 旧测试红了就停，不准改断言**

```bash
"$PY" -m pytest -q \
  intelligence/tests/test_agent_episode.py \
  intelligence/tests/test_continuous_turn_adapter.py
```

`test_continuous_turn_adapter.py` 若因**没接** Handle/投影而红：记下失败名。若失败全是「缺 RuntimeHandle / episode_projection」→ 这正是工程门要的信号，**停**，不要为过门去取 §5。

若 `test_agent_episode.py` 绿、adapter 红且原因是没取投影：在收据写「旧 adapter 测试依赖整包，不是这一对的编译失败」。然后只把 `test_agent_episode.py` 当门；adapter 红**单独**判断：

- 失败信息含 `runtime_handle` / `research_profile` / `dsh_stub` / `episode_projection` → 视为「整包测试咬合」，**不**据此去取 §5。继续 dry-run。
- 失败信息是 `EpisodeScope` / `TOOL_*` / `LiveEventSink` 未定义 → 摘接失败，停。

- [ ] **Step 3: 层级审计 0 ERROR**

```bash
"$PY" scripts/layer_audit.py
```

Expected: `ERROR 0`。

---

### Task 4: 烟测（1 题 dry + live，不读快慢）

**Files:**
- Create: `~/.finance-runtime/tf-subset-20260817/arm0-dry.json`
- Create: `~/.finance-runtime/tf-subset-20260817/arm1-dry.json`
- Create: `~/.finance-runtime/tf-subset-20260817/arm0-smoke-live.json`
- Create: `~/.finance-runtime/tf-subset-20260817/arm1-smoke-live.json`

环境（live 与 #68 / 复烟测同一条，禁止 GLM 三件套）：

```bash
unset PYTHONPATH RAG_WORKER_ENABLED
unset FORESIGHT_BUILTIN_LLM_API_KEY FORESIGHT_BUILTIN_LLM_BASE_URL FORESIGHT_BUILTIN_LLM_MODEL
export FORESIGHT_LLM_KEYCHAIN=0
export LLM_BASE_URL="https://x.ailzd.com/v1"
export LLM_MODEL="gpt-5.6-terra"
export OPENAI_API_KEY="$(security find-generic-password -s finance-workbench-test-relay -a a77 -w)"
export PY=/Users/a77/finance-workspace-private/.venv-workbench/bin/python
export Q=/Users/a77/fwp-wt-dsh-sample-lock/intelligence/eval/fixtures/frozen-thirty-2026-08-16.questions.json
export OUT="$HOME/.finance-runtime/tf-subset-20260817"
```

- [ ] **Step 1: 记下 8792 rag 计数（只读）**

```bash
curl -sS -m 3 http://127.0.0.1:8792/api/readiness | python3 -c \
  'import sys,json; d=json.load(sys.stdin); r=d.get("workers",{}).get("rag",{}); print(r.get("model_load_count"), d.get("source_revision"))'
```

Expected: `model_load_count` 仍为烟测前的值（复烟测时是 1）。记下 `source_revision`，全程不得变。

- [ ] **Step 2: 两臂 dry-run**

```bash
cd /Users/a77/fwp-wt-tf-arm-a-83e83b42
"$PY" scripts/run_agent_runtime_benchmark.py \
  --dry-run --backend continuous_glm --case A1-market-overview \
  --questions-file "$Q" \
  --finance-root /Users/a77/finance-workspace-private \
  --knowledge-wiki /Users/a77/knowledge-base-private/wiki \
  --output "$OUT/arm0-dry.json"

cd /Users/a77/fwp-wt-tf-arm-1-subset
"$PY" scripts/run_agent_runtime_benchmark.py \
  --dry-run --backend continuous_glm --case A1-market-overview \
  --questions-file "$Q" \
  --finance-root /Users/a77/finance-workspace-private \
  --knowledge-wiki /Users/a77/knowledge-base-private/wiki \
  --output "$OUT/arm1-dry.json"
```

Expected: 两文件 `task_frame_hash` 都是 `beb73ad53210cf8138be545ec12c24b35ec4e408fa47daf2614b240c6f67a437`；`canonical_runtime_touched` 为 false。

- [ ] **Step 3: 两臂各 1 次 live 烟测**

同一环境，去掉 `--dry-run`，输出 `arm0-smoke-live.json` / `arm1-smoke-live.json`。

Expected: exit 0；`resolved` 模型含 `gpt-5.6-terra`。墙钟**不准**读成「臂 1 更快」。

- [ ] **Step 4: 再读 8792**

`model_load_count` 与 `source_revision` 与 Step 1 相同。变了 → 停，查谁碰了生产。

---

### Task 5: 小窗 5×5

**Files:**
- Create: `~/.finance-runtime/tf-subset-20260817/arm0-r{1..5}.json`
- Create: `~/.finance-runtime/tf-subset-20260817/arm1-r{1..5}.json`

- [ ] **Step 1: 串行 10 次，仍用 Task 4 同一环境**

```bash
for i in 1 2 3 4 5; do
  cd /Users/a77/fwp-wt-tf-arm-a-83e83b42
  "$PY" scripts/run_agent_runtime_benchmark.py \
    --backend continuous_glm --case A1-market-overview \
    --questions-file "$Q" \
    --finance-root /Users/a77/finance-workspace-private \
    --knowledge-wiki /Users/a77/knowledge-base-private/wiki \
    --output "$OUT/arm0-r${i}.json"
  cd /Users/a77/fwp-wt-tf-arm-1-subset
  "$PY" scripts/run_agent_runtime_benchmark.py \
    --backend continuous_glm --case A1-market-overview \
    --questions-file "$Q" \
    --finance-root /Users/a77/finance-workspace-private \
    --knowledge-wiki /Users/a77/knowledge-base-private/wiki \
    --output "$OUT/arm1-r${i}.json"
done
```

不要并行（配额和 8792 卫生）。一次 `runner_exception` 记下来，继续跑完 10 次，除非 8792 被碰。

- [ ] **Step 2: 跑完后再读 8792，revision 仍不变**

---

### Task 6: 读数页（#140 口径）

**Files:**
- Create: `docs/handoffs/2026-08-17-tf-subset-attach-readings.md`
- 在 **docs 树**（`/Users/a77/fwp-wt-r17-01-live` 或干净 main worktree）提交，不要写进臂 1 摘接树。

口径（与 #140 契约一致；#140 未合也必须遵守，禁止用臂级 `stop_reason` 算 repair）：

```python
def first_deadline(arm):
    events = (arm.get("diagnostics") or {}).get("events") or []
    for e in events:
        if e.get("kind") == "finish":
            return (e.get("payload") or {}).get("stop_reason") == "deadline_exhausted"
    return None  # 空事件：未定义，不是 0

def repair_recovered(arm):
    events = (arm.get("diagnostics") or {}).get("events") or []
    if not any(e.get("kind") == "repair_goal" for e in events):
        return None
    finishes = [
        (e.get("payload") or {}).get("stop_reason")
        for e in events if e.get("kind") == "finish"
    ]
    if not finishes:
        return None
    return finishes[-1] in {
        "repair_model_finish", "repair_model_stop", "model_finish"
    }

def trace_count_ok(arm):
    events = (arm.get("diagnostics") or {}).get("events") or []
    if not events:
        return None  # 空事件不是通过对账
    kinds = [e.get("kind") for e in events]
    return kinds.count("tool_request") == kinds.count("tool_result") + kinds.count("tool_error")
```

若 #140 已合进执行时的 docs 树：优先 `from intelligence.eval.metric_field_contract import ...` 的同名 resolver，不要抄第二套。未合则用上面这段。

- [ ] **Step 1: 汇总 10 个 json**

对每个 arm 文件取 `cases[0].arms[0]`：`latency_seconds`、`stop_reason`（只作旁注）、上面三个 resolver。

- [ ] **Step 2: 写读数页，只许这三行主表**

1. 还能跑：每臂 `runner_exception` 数；`trace_count_ok` 为 True 的条数 / 有事件条数（None 单独报「空事件」）。
2. 墙钟：每臂 min / 中位 / max。计算 `median(臂1) / median(臂0)`。
3. 修复：进入 `repair_goal` 的次数；其中 `repair_recovered is True` 的次数。5+5 里一次都没进入 → 写「本窗无修复样本」，**不加跑**。

结论只许 spec §8 三选一。n=1 烟测墙钟不得写入主表。

- [ ] **Step 3: 提交读数页（docs only）**

```bash
git add docs/handoffs/2026-08-17-tf-subset-attach-readings.md
git commit -m "$(cat <<'EOF'
docs(handoff): T-F 摘接小窗读数——Scope+工具阶段可行性

不开 900。结论集只有接得上 / 慢了 / 摘不干净。
EOF
)"
```

---

### Task 7: 下一块怎么选（写进读数页末节，不改 spec）

本窗大概率是「能跑、没变慢」。EpisodeScope 是授权门控，工具阶段事件是纯观测，**两者都不太会改善延迟或 repair 恢复**——而 #137 说只有这两项在 450 内可判。所以本窗不解渴是预期，不是失败。

读数页末节必须用这段（可略改句子，意思不准漂）：

> 下一块不要再做「另一个不太能动延迟/repair 的可行性窗」。二选一：
>
> 1. **选可能动可判指标的接缝**：RuntimeHandle（取消 / 排空 / close）。这要先做 §9.2 失败注入，否则 cancel/resume 样本永远是 0。另开 spec，不并进 900。
> 2. **承认吸收收益不在可判指标上**：改判形状价值（T-E 静态对照 / Scope.dump 可达性收据），不再用墙钟证明吸收兑现。
>
> 不要接着摘 ResearchProfile 或 dsh stub 再开一个 5×5——那还是可行性探针，结论集不会出现「收益」。

用户看过读数再开下一块 spec。本计划到读数页为止。

---

## Self-review（对照 spec）

| spec | 本计划任务 |
|---|---|
| §4 白名单整取 / 接线 | Task 1 |
| §5 禁止名单 | Task 2 |
| §6 工程门（pytest / layer_audit / dry+live / hash / 8792 / diff） | Task 2–4 |
| §7 1 题 × 5×2 | Task 5 |
| §7 读数三行 + 空事件前提 + 末条 finish | Task 6（#140） |
| §8 三选一 | Task 6 |
| §2.2 不开 900 / 不切 8792 / 不整包 | §0 硬停 + 各 Task |
| §10.4 下一块另开 spec | Task 7（前瞻，不改 spec） |

无 TBD。无「类似 Task N」。未要求改生产 main 代码。
