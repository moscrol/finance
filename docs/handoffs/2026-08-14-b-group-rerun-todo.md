# TODO：B 组 8 题在 60s 工具窗口下复跑复核

**建单**: 2026-08-14
**执行者**: 下一个 agent
**预计**: 15–25 分钟，只读不写库，烧 LLM 配额
**产出**: 一份 run artifact + 一段结论回写

---

## 0. 一句话任务

在**当前** 8792 runtime（`ASK_TOOL_BATCH_TIMEOUT=60`，今天 18:29 重启后生效）上把
B 组 8 题复跑一次，判定「证据取回来了但绑不上」这个卡点是否已随工具窗口放宽而解除。

---

## 1. 背景（读完再动手，两分钟）

- 同目录的 `2026-08-14-evidence-bound-zero-diagnosis.md` **核心结论已被推翻，不要沿用它的判断**。
  推翻依据见该文件的复核（要点：它把 9 个 `Connection refused` 读成了业务行为；
  它没读同目录的 `20260813T1855Z-qc28-c-rerun.json`）。
- 真实卡点在 **B 组**（+A6）：`status=completed`、trace 17–38 步、答案自述
  「本轮已取得 19/29/125 条证据，**但未完成核验绑定**」。
- `episode_semantic_verifier.py:1699-1708` 注释写明这个分支的含义：
  **绑定集合为空**（模型没走到 FINAL_JSON），不是绑定被判不合格。
  → **门禁没有误杀，它在如实转述上游没交货。**
- 今天已修：`~/.local/bin/start-finance-workbench:124` 加 `ASK_TOOL_BATCH_TIMEOUT="60"`
  （原 30s 窗口把 `evidence_search` 饿死）。修后单个题材题 run `112138` 结构核验全 fulfilled、
  `chain_mapping` 绑上 3 条——**但只有 1 个样本，不足以宣布修好。这单就是补样本。**
- 唯一的对照基线：`intelligence/eval/runs/20260813T1810Z-qc28-full.json`
  （revision `71b50300`，今天 02:38，**修复前 16 小时**）里的 B 组 → eb 依次
  `B1..B8 = 0,0,0,0,0,0,0,11`。

---

## 2. 前置检查（四条，不过不要跑）

```bash
cd /Users/a77/finance-workspace-private

# ① 解释器必须是这个（python3 是 3.14，缺依赖）
.venv-workbench/bin/python -V

# ② 目标服务活着，且带着 60s 窗口
curl -s http://127.0.0.1:8792/api/health | .venv-workbench/bin/python -m json.tool | head -30
ps eww -p $(lsof -ti :8792 | head -1) | tr ' ' '\n' | grep -E "ASK_TOOL_BATCH_TIMEOUT|ASK_CONTINUOUS_RUNTIME|AGENT_RUNTIME_BACKEND"
# 期望：ASK_TOOL_BATCH_TIMEOUT=60 / ASK_CONTINUOUS_RUNTIME=on / AGENT_RUNTIME_BACKEND=continuous_glm
# 若 ASK_TOOL_BATCH_TIMEOUT 不是 60 → 说明进程是旧的，本单作废，先说明再停

# ③ 记下这次跑的是哪份代码（结论必须携带它才成立）
curl -s http://127.0.0.1:8792/api/health | \
  .venv-workbench/bin/python -c "import json,sys;r=json.load(sys.stdin)['runtime'];print('revision',r['source_revision'][:8],'dirty',r['source_dirty']);print('loaded_code_root',r['loaded_code_root'])"

# ④ 别覆盖已有 artifact（cmd_run 自带 x 模式，但先看一眼）
ls intelligence/eval/runs/ | tail -3
```

> ⚠️ **最大的坑：`DEFAULT_BASE = http://127.0.0.1:8799`，不是 8792。**
> 8799 是 canary 侧服务器，现在是**关的**。命令行不显式写 `--base` 就会打到 8799。
> 前置检查会 fail closed 挡住你——**这时绝对不要加 `--force`**，
> 昨夜那 9 个 0 就是服务器不可达跑出来的假数据。

---

## 3. 跑

```bash
cd /Users/a77/finance-workspace-private
.venv-workbench/bin/python -m intelligence.eval.acceptance run \
  --base http://127.0.0.1:8792 \
  --tier mid_freq \
  --timeout 300 \
  --output intelligence/eval/runs/20260814T$(date -u +%H%M)Z-b-rerun-tool60.json
```

`--tier mid_freq` = B1–B8 全部 8 题，都是单轮无 followup。

预算不够就先跑最能说明问题的两题（B4 昨夜 125 条证据全没绑上，B1 是 19 条）：

```bash
  --case B4-fermentation-trace --case B1-theme-photoresist
```

---

## 4. 跑完立刻做（别省，这步是昨夜翻车的直接原因）

```bash
# 服务器有没有中途死掉 —— preflight 只在开跑前查一次，中途挂了没人拦
curl -s -o /dev/null -w "post-run 8792 HTTP %{http_code}\n" http://127.0.0.1:8792/api/health
```

任何一题出现 `status=error` + `elapsed_s=0.0` + `trace_steps=[]` +
`<urlopen error [Errno 61] Connection refused>` → **那题是基础设施失败，不是产品结论，
不许计入分母**，在回写里单独列出。

---

## 5. 读结果：不要只看 `evidence_bound`

`evidence_bound` 是验收台在 `acceptance.py:198` 从 `GET /api/runs/{id}/context`
数出来的 `status=="hit"` 条数，**至少混了四种因**，同色不可直接比较：

| eb=0 的因 | 怎么认出来 |
|---|---|
| 端点/服务器不可达 | `status=error`、`trace_steps=[]`（`_fill_run_detail` 取不到会静默当空） |
| 核验绑定失败（**本单要找的**） | `completed` + 答案含「已取得 N 条证据，但未完成核验绑定」 |
| deadline 耗尽 | gap 含「达到统一截止时间，已返回结构化缺口」 |
| 正常澄清轮 | 答案是反问、`gaps=[]`、elapsed 只有几秒（如昨夜 B6 2.0s） |

跑完用这段读（**逐题打印判据，不要只打总数**）：

```bash
.venv-workbench/bin/python - <<'EOF'
import json,glob,os
f=sorted(glob.glob('intelligence/eval/runs/*b-rerun-tool60*.json'))[-1]
d=json.load(open(f)); print(os.path.basename(f), '|', d['preflight_detail'], '\n')
BASE={'B1':0,'B2':0,'B3':0,'B4':0,'B5':0,'B6':0,'B7':0,'B8':11}   # 修复前基线
for c in d['cases']:
    t=c['turns'][0]
    k=c['case_id'].split('-')[0]
    eb=t.get('evidence_bound') or 0
    unbound='未完成核验绑定' in (t.get('answer') or '')
    print(f"{c['case_id']:30s} eb={eb:3d} (基线 {BASE.get(k,'?')})  {t.get('status'):9s} "
          f"{t.get('elapsed_s')}s steps={len(t.get('trace_steps') or [])} "
          f"未绑定={unbound} fulfillment={'有' if t.get('fulfillment') else '空'}")
    if t.get('gaps'): print('     gaps:', t['gaps'])
EOF
```

**关键要看 `fulfillment`**：它是逐 required_output 的终态完成情况
（`acceptance.py:268` 取最后一次判缺投影，含修复轮）。昨夜整轮它都是 `{}`——
如果这次仍是空，说明契约完成度这一层**在 artifact 里根本观测不到**，
需要直接打 `GET /api/runs/{run_id}/trace` 看每步的 `fulfillment.items`，
重点确认 `chain_mapping` / `counterpoint`（"提供主要反证或竞争性解释"）
这两项的 status 和绑定条数——它们正是昨夜 B 组答案里点名缺的。

---

## 6. 判定标准

| 结果 | 结论 | 下一步 |
|---|---|---|
| B 组 ≥6/8 转为 eb>0 且 `chain_mapping` 有绑定 | 卡点已随工具窗口解除 | 回写关账，`.agent-memory` line 161 的 🔴 卡点改 ✅ 并注明真根因是 30s 工具窗口 |
| 部分转正、部分仍 0 | 不是单一根因 | 只对**仍为 0 且答案含"未完成核验绑定"**的题继续查，其余关账 |
| 仍全 0 | 工具窗口不是根因 | 查**模型有没有走到 FINAL_JSON**（stop_reason / repair 轮），**仍然不是查门禁** |

---

## 7. 三条禁令

1. **不许放宽语义 verifier 的绑定判据。** "claim 与证据绑定"是领域层，严格就是它的价值；
   放宽 = 让未绑定证据冒充已核验 = 幻觉直通。
2. **不许在验收台按题型豁免 `evidence_bound`**（前一份诊断的"方案 B3"）。
   它会把唯一暴露这个真缺陷的信号关掉，然后门禁发绿光。
3. **不许改路由 / `DETERMINISTIC_OWNER_TYPES`。** 已实测：B 组题目一个都不命中
   `is_quick_fact_query`，这条线与本卡点无关。

> 本仓同形状已出现三次（08-02 路由正则误命中、笔记 line 187 第一个正则、08-13 夜工具窗口），
> **根因没有一次在门禁**。都是上游递空手过来、门禁如实拒绝，看起来像门禁太严。

---

## 8. 回写

1. artifact 留在 `intelligence/eval/runs/`（**不提交**，红线：不提交大 JSON 除非用户要求）。
2. 结论追加到 `.agent-memory/20_projects/finance-workspace-private.md` 的「交接记录」，
   **必须携带成立条件**：`revision=<8位> / ASK_TOOL_BATCH_TIMEOUT=60 / base=8792 / 样本数=8`。
3. 如果关账，同时更新该文件 line 161 那条 🔴 卡点，并**明确写上**：
   原记录「变量已锁定 `ASK_CONTINUOUS_RUNTIME`（off→30/13，on→0/0）」这个读数**无法从任何 run
   artifact 复核**——验收台 preflight 只记 `revision=... backend=...`（`acceptance.py:181`），
   全部 47 个 run 文件都不含 `ASK_CONTINUOUS_RUNTIME`。
   （health 里其实有 `runtime.continuous_agent.mode`，验收台没取；补记它是一行改动。）
4. 别在 `main` 上做代码改动；本单**只跑不改**，如需改代码另开 `fix/<问题>` 分支并等用户确认。
