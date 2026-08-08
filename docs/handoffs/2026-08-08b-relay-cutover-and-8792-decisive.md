# Handoff: 生产 8792 切中转 + 在生产线上复跑决证

> **日期**：2026-08-08
> **写给**：agent A
> **前一份**：`2026-08-08-prior-recall-and-runtime-fixes.md`（已于本日 14:xx 订正，
> 读它请读订正后的版本——原正文的决证状态与快照配方都已过期）
> **范围 revision**：`0c4b2dcb`（main，未 push）
> **用户决策（2026-08-08）**：**不再用 cockpit**。生产 LLM 出口切到 8788 在用的那套中转。

---

## 0. 一句话

生产 8792 的 LLM 出口现在指向已经没有上游凭证的 cockpit（`localhost:57244`），
把它改成 8788 已经验证可用的中转（`https://x.ailzd.com/v1` + `gpt-5.6-sol`），
然后在**生产线上**把 `memory_lookup → prior_recall` 那条链再验一次。

链本身已经验通了，但**只在 8788 上**。8788 不是生产形态（不同 code root、
不同 users 目录、不同凭证路径），那条线的绿灯不传递到 8792。

---

## 1. 事实核验表

下面每一条我都在 `0c4b2dcb` 上实测过，注明了当前位置。**smoke 脚本
`/tmp/smoke_8788_relay.sh` 的注释里有三处引用已经漂了，别照抄**：

| 事实 | 当前位置 | 状态 |
|---|---|---|
| 中转可用 | `https://x.ailzd.com/v1` | ✅ `GET /v1/models → 200`（用下述 Keychain key） |
| key 存放 | Keychain service `finance-workbench-test-relay`，account `a77` | ✅ 条目存在 |
| cockpit 已空 | `~/.antigravity_cockpit/codex_local_access_sidecar/auths/` | ❌ 0 个 `.json` / 13 个 `.bak`，`quota-pool-state.json` = `{"accounts": {}}` |
| 关掉 Keychain 开关会落回 env | `llm_settings.py:205-218` `runtime_providers_for` | ✅ `byok` 为 None 时 `return llm_refine.detect_providers()` |
| Keychain 开关判据 | `llm_settings.py:64` `_credential_store_from_environment` | ✅ 值不在 `{1,true,yes,on}` 即返 None |
| provider 解析顺序 | `llm_refine.py:160-211` `detect_providers` | ✅ contextvar 覆盖 → `LLM_API_KEY`(name=`custom`) → `FORESIGHT_BUILTIN_LLM_API_KEY`(name=`zhipu`) → `_PROVIDERS` 循环 |
| `LLM_BASE_URL` 优先于 `OPENAI_BASE_URL` | `llm_refine.py:169` 与 `:197` | ✅ |
| readiness 只认四个 key env | `intelligence/runtime/agent_runtime_factory.py:89-92` | ✅ `FORESIGHT_BUILTIN_LLM_API_KEY` / `ZHIPU_API_KEY` / `GLM_API_KEY` / `OPENAI_API_KEY`，**不认 `LLM_API_KEY`** |
| provider 链注入点 | `api/app.py:1793` 与 `:2244` | ⚠️ smoke 脚本写的 `app.py:2214` **已漂**，别引用 |
| factory 位置 | `intelligence/runtime/agent_runtime_factory.py` | ⚠️ smoke 脚本写的 `services/agent_runtime_factory.py` **已不存在**（`b6900f47` 搬进 runtime/） |
| `detect_providers` 位置 | `intelligence/services/llm_refine.py:160` | ⚠️ smoke 脚本写的 `llm_refine.py:138-168` 行号已漂 |
| 生产 users 台账 | `/Users/a77/.local/share/finance-workbench/users` | ❌ 27 个 user，**零个 `judgments.jsonl`** |
| tester 台账 | `/Users/a77/agent-memory/.foresight/tester/judgments.jsonl` | ✅ 496 行 |

---

## 2. 任务 A：把生产 LLM 出口切到中转

### A.1 现状（启动器 `/Users/a77/.local/bin/start-finance-workbench`）

**有两条路都指向 cockpit，只改一条会静默降级**：

```zsh
19: export FORESIGHT_LLM_KEYCHAIN=1          # ← 路径①：BYOK 劫持，Keychain 条目 base=localhost:57244
20-25: export LLM_API_KEY="$(… byok_provider("linxiaoqi5111").api_key …)"
26: export LLM_BASE_URL="http://localhost:57244/v1"   # ← 路径②：env 直指 cockpit
27: export LLM_MODEL="gpt-5.6-sol"
```

路径①的优先级**高于** env：`app.py:1793/2244` 显式传
`llm_providers=llm_settings.runtime_providers_for(user_id)`，而它在 byok 存在时
直接 `return (byok,)`，根本不看 env。所以**只改第 26 行没用**，请求照样往
cockpit 发——这就是 08-08 那次「env 里明明写着中转地址，四次重试全 502」的成因。

### A.2 改法

备份已有一份 `start-finance-workbench.bak-20260807`，**再存一份带今天日期的**。

```zsh
# ① 关掉 BYOK 劫持。不是删 Keychain 条目——那是用户资产，且改天要用。
#    关掉开关后 runtime_providers_for 落回 detect_providers()（已实测，见事实表）。
export FORESIGHT_LLM_KEYCHAIN=0

# ② 第 20-25 行整段删掉（那段是从 Keychain 里抠 BYOK key，现在不需要了），
#    换成从中转专用的 Keychain 条目读，且**用 OPENAI_API_KEY 而不是 LLM_API_KEY**：
export OPENAI_API_KEY="$(security find-generic-password -s finance-workbench-test-relay -a a77 -w)"
export LLM_BASE_URL="https://x.ailzd.com/v1"
export LLM_MODEL="gpt-5.6-sol"
```

**为什么是 `OPENAI_API_KEY` 而不是继续用 `LLM_API_KEY`**（这是本次唯一一个
有替代方案的决策点，理由要留下来）：

| | `LLM_API_KEY` | `OPENAI_API_KEY`（选它） |
|---|---|---|
| provider.name | `custom`（`llm_refine.py:171`） | `openai`（`_PROVIDERS` 表 `llm_refine.py:87`） |
| readiness 探针 | 看不见 → `credential_available` 恒 false | 认（`agent_runtime_factory.py:92`） |
| 将来切 `sdk_gpt` | ❌ `app.py` 硬要求 `provider.name == "openai"`，会 raise | ✅ 直接满足 |
| base_url | 同样走 `LLM_BASE_URL` | 同样走 `LLM_BASE_URL`（`llm_refine.py:197`） |

两者都能让 `continuous_glm` 跑起来（该壳不检查 name），差别在**仪表可读性**和
**将来切壳的成本**。壳轴 A/B 还没定，选 `OPENAI_API_KEY` 等于不给将来挖坑。

⚠️ **改完确认 provider 链长度是 1**。`detect_providers` 的 `_PROVIDERS` 循环会把
env 里**每一个**命中的 key 都加进链（DEEPSEEK / MOONSHOT / DASHSCOPE / ZHIPU …）。
launchd 环境里若混进别的 key，链会变长，round-robin 到坏的那条就是随机污染——
和 MOC 里 codex sidecar 那条🔴阻塞是同一个形状。

### A.3 A 的影响面（改之前想清楚）

关掉 `FORESIGHT_LLM_KEYCHAIN` 是**全局**的，不只影响 `linxiaoqi5111`：任何存过
自己 BYOK key 的 user 都会改走服务端 env 那条链。当前 27 个 user 是自用场景、
台账全空，判断影响可接受；但这是个**产品语义变更**，写进 commit message，
别当成配置微调。

---

## 3. 任务 B：在生产线上复跑决证

### B.1 先解决台账为空的问题（决策点，请按推荐做）

生产 users 目录 27 个 user **零个 `judgments.jsonl`**，直接跑的话
`memory_lookup` 只会返回空命中——那验到的是「工具注册成功」，**验不到「真召回」**，
和 8788 上已经验过的不是同一件事。

| 方案 | 做法 | 影响面 |
|---|---|---|
| **(a) 推荐：给生产 seed 一个 tester** | `mkdir -p $PU/tester && cp /Users/a77/agent-memory/.foresight/tester/judgments.jsonl $PU/tester/` | 只多一个 user 目录，可随时删 |
| (b) 改 `FORESIGHT_USERS_DIR` 指向 agent-memory | 改启动器第 8 行 | ❌ 27 个 user 的会话/runs/sqlite 全部换位置，blast radius 太大 |

两边目录结构兼容（都有 `conversations` / `runs` / `workbench.sqlite3`），
seed 只需 `judgments.jsonl` 一个文件。

### B.2 部署（**不要手工 cp**）

```bash
cd /Users/a77/finance-workspace-private
scripts/deploy_workbench_runtime.sh
```

⛔ 别逐文件 `cp` 补快照。`b93e4a00` 实测：补 2 个起不来（缺 `runtime/` 整包）、
补上还缺 `tool_result_budget.py`、`services/` 实缺 14 个。**模块重组后差哪些
文件无法靠读 diff 推断**，且快照里的陈旧模块会被 import 到，留着比缺着更危险。

⚠️ 该脚本**当前有未提交改动**（见任务 D），先看 `git diff` 确认你跑的是哪一版。

### B.3 发决证请求

```bash
CID=$(curl -s -X POST localhost:8792/api/conversations \
  -H 'Content-Type: application/json' \
  -d '{"user":"tester","title":"decisive-8792"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["conversation_id"])')

curl -s -X POST "localhost:8792/api/conversations/$CID/messages" \
  -H 'Content-Type: application/json' \
  -d '{"content":"液冷题材现在怎么看？我之前的判断还成立吗","skill_mode":"auto","user":"tester"}'
```

题目里必须有**指向用户自己历史看法**的措辞（"我之前的判断"），否则
`_PRIOR_REFERENCE_RE` 不命中，`prior_recall` 槽位根本不开——那时的"没召回"
不是缺陷，是没触发。

### B.4 判定

```bash
RUN=run_2026xxxx_xxxxxx_xxxxxx    # 从上一步响应里取
EP=/Users/a77/.local/share/finance-workbench/users/tester/runs/$RUN/continuous-episode.json
python3 -c "
import json,pathlib
ep=json.loads(pathlib.Path('$EP').read_text())
o=ep['outcome']
seq=[c.get('name') for e in ep.get('events',[]) for c in (e.get('payload') or {}).get('tool_calls',[]) if c.get('name')]
print('backend :', ep.get('runtime_backend'))
print('status  :', o.get('status'), '|', o.get('stop_reason'))
print('tools   :', seq)
print('memory_lookup called :', 'memory_lookup' in seq)
print('prior_recall binding :', [b for b in o.get('bindings',[]) if b.get('output_id')=='prior_recall'])
"
```

**通过判据（三条全中才算）**：

1. `memory_lookup` 出现在 `tools` 里
2. `prior_recall` binding 存在且 `basis=user_premise`、有 `evidence_hashes`
3. 答案正文里没有台账文件路径泄漏

**`status=partial` 不算失败。** 8788 那次决证也是 partial，原因在数据源侧
（evidence_search 超时、finance_query 返 `request_error`、后两个工具撞
`MAX_BATCH_TOOL_CALLS=4`，见 `episode_tool_batch.py:34`），与 prior_recall 链无关。
**判的是那条链闭不闭合，不是这一轮答得好不好**——别把数据源的问题读成链路的问题。

---

## 4. 任务 C：8788 的去留（请找用户确认后再动）

8788 现在是**第二条无人看管的代码线**：进程 pid 79613，rev `9380b3b9`，落后 main
4 个提交，且 health 里没有 `loaded_code_root` / `code_matches_repo`（那两个字段是
`45d51616` 才加的）——**它自己不知道自己漂了**。

任务 A 做完后，8792 和 8788 会走同一个中转，8788 的存在理由（"生产凭证坏了，
需要一条能跑的线"）就消失了。两个选项：

- **关掉**：决证已迁到 8792，不再需要平行线
- **留着并升级**：升到 main、纳入部署闸门；理由是保留一条不影响生产的实验线

我的建议是关掉。**平行线的成本不是资源，是"在哪条线上验过"这个问题会一直存在**——
今天订正的三份文档里就有一份栽在这上面。

---

## 5. 任务 D：提交 `deploy_workbench_runtime.sh`

`scripts/deploy_workbench_runtime.sh` 有**未提交改动**，改的是核心正确性：

> `python - <<PY` 从 stdin 读脚本时 `sys.path[0]` 是 `''`，优先级**高于**
> `PYTHONPATH`。不 `cd` 到快照的话，`intelligence` 会从仓库导入，校验退化成
> 「仓库跟自己比」，`code_matches_repo` 恒真且无意义。

这是**他人足迹**（不是我写的）。按 `77b3386d` 的纪律：逐行认领、禁用 `git add -A`、
一律 `git commit -- <文件列表>`。请确认作者与意图后再提交，别顺手吞进别的提交。

同目录下还有 `docs/span-io-trace-prd.md` 未跟踪（28KB，署名「Devin + 用户」，
08-06 起挂到现在），**不是本次范围，别一起提交**。

---

## 6. 红线与已知坑

- 🚫 **key 不进仓库任何文件**，包括示例、注释、测试夹具。启动器里也只写
  `security find-generic-password …` 的读取命令，不写字面值。
- 🚫 **不擅自合并 main、不强推**。当前 main 有 3 个未 push 的提交
  （`6620f175` / `9d7d97b6` / `0c4b2dcb`），push 要用户确认。
- ⚠️ **不要把 `.bak` 改回 `.json` 去救 cockpit**。用户已决定不用它了。
- ⚠️ **不要在服务启动时对快照不一致做 `sys.exit`**。launchd 是
  `KeepAlive=true` + `ThrottleInterval=10`，那会变成每 10 秒重启一次的无限
  崩溃循环。闸门必须放在部署一侧。
- ⚠️ **解释器只认 `.venv-workbench/bin/python`**。宿主 `python3` 是 3.14 缺依赖，
  用它得出的"符号不存在"/"缺包"全是假结论。
- ⚠️ **行号会漂**。本文档引用的行号是 `0c4b2dcb` 上的实测值；`b6900f47` 那次
  模块搬迁已经让一批文档里的路径失效（本文档事实表里标了三条）。引用前先
  `grep` 现查符号名，别信固定行号。

---

## 7. 完工验收（每条都是可执行命令）

```bash
# ① 出口切对了：base_url 是中转不是 cockpit，链长度为 1
curl -s localhost:8792/api/health | python3 -m json.tool | grep -A 8 agent_runtime

# ② 快照与仓库一致（部署闸门自己会查，这里是复核）
curl -s localhost:8792/api/health \
  | python3 -c 'import sys,json;r=json.load(sys.stdin)["runtime"];print("matches:",r["code_matches_repo"])'

# ③ readiness 全绿
curl -s localhost:8792/api/readiness \
  | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d["status"], d["missing_critical"])'

# ④ 决证三条判据（见 §3.4）

# ⑤ 没引入新红。基线 13 failed, 4387 passed, 3 skipped @ 0c4b2dcb
#    并与 --collect-only 对账：13+4387+3 == collect 条数
.venv-workbench/bin/python -m pytest -q --collect-only | tail -1
.venv-workbench/bin/python -m pytest -q 2>&1 | tail -20

# ⑥ 分层门禁 ERROR 0
.venv-workbench/bin/python scripts/layer_audit.py
```

---

## 8. 明确不在本次范围

- ❌ **改 `AGENT_RUNTIME_BACKEND`**。壳轴 A/B（continuous vs sdk_gpt）还没数据，
  启动器第 33 行的 `continuous_glm` 是显式化当前生效值，**不是**在做选择。
  枚举名里的 `glm` 是历史包袱，该壳自 `93ac264d` 起 provider-neutral。
- ❌ **改 `MAX_BATCH_TOOL_CALLS`**。决证里第 5 个工具被拒是撞这个上限，属预期
  行为，不是本次要修的东西。要改需要先有预算分布数据。
- ❌ **Phase 1 #1 的压缩策略**。路线图写明**先量后改**：要先跑一批真实题拿
  `max_turn_input_tokens` 的 P50/P95/max 分布。生产默认 `continuous_glm` 恰好是
  能拿精确逐轮值的那条路，任务 A/B 做完后这批数据才跑得出来——**顺序不能反**。
- ❌ **清 `tmp/` 下 4 个历史工作 clone**。`pytest.ini` 已经挡住它们，且它们是
  `intelligence/tests/test_pytest_collection_scope.py` 变异测试的唯一冲突源，
  删了那条测试会 skip。要清请连同那条测试的 skip 分支一起想清楚。

---

## 9. 交接时请回写

做完后按 `CLAUDE.md` 的分层：

- 项目级决策（LLM 出口切换、8788 去留）→ `agent-memory/20_projects/finance-workspace-private.md`
  的「交接记录」，并**更新 MOC 里「🚦 Agent Runtime 线路」那节**——它现在还写着
  cockpit 那条🔴阻塞，任务 A 做完后那条就过期了。
- 能力变更 → 回写 `agent-memory/10_knowledge/finance-agent-capability-graph.md`，
  跑 `graph_audit.py` 应 exit 0。**不要另建第二份能力清单。**
- 路线图 Phase 1 第 2 项现在标着「决证只在 8788 验过，生产线仍欠一次」——
  任务 B 通过后把这个限定去掉。
