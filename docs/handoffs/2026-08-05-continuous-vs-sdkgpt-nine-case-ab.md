# Handoff：九题 A/B（Continuous 壳 vs SDK 壳，同模型 gpt-5.6-sol）

日期：2026-08-05 · 交接自：claude · 分支：`fix/continuous-runtime-provider-neutral@20c25445`（已推 origin，未合并 main）

---

## 0. 一句话

**三次实跑全部作废。环境类问题已修完（RAG 生效、账号池健康、级联缺陷已修），
但剩下两个阻塞不是环境问题，都要先解决才可能拿到可用数字：**

1. ✅ **预算不对称——口径已拍（2026-08-05，用户）：复现生产 30 / 90。**
   原状 continuous 30s / sdk 60s 这一对**只存在于 benchmark**，生产是 30 / 90；
   benchmark 给 sdk 的研究预算比生产少 30 秒，而 continuous 两边一致，所以那把尺子
   既不是「对齐」也不是「复现生产」。**待做的代码改动**：`_fresh_context` 的 else 分支
   改成 `reserve=0`，干跑验到 `initial_seconds` 实际是 30 / 90。详见 §5.3。
2. **瞬时 502 会终止整轮**：第 8 题命中即整轮中断（§3.1 更正 1），需要重试机制。**未做。**

目前关于「GPT 下自建壳 vs SDK 壳谁更好」仍是**零数据**，不要引用任何倾向性说法。

---

## 1. 这件事在回答什么问题

用户的决策拆成两个**正交**的轴，别压成一条：

| 轴 | 状态 |
|---|---|
| **模型** | ✅ **已定**：`gpt-5.6-sol`，走 Keychain。GLM 模型退役。 |
| **执行壳** | ❓ **未定**：自建 Continuous vs Agent SDK。**本次 A/B 就是为了定它。** |

> 「不用 GLM 的 model」**不等于**「改用 sdk 壳」。这是交接前一轮已被用户明确纠正的错误框架，
> 不要重犯。2026-07-25 同模型九题盲评：Continuous **195** / SDK **175**（6 维 0-4 分制），
> SDK 只赢在**协议稳定性**（4→0）和**延迟**（53.5s→48.5s）。用户的要求是「择优 + 有机结合」，
> 即把 SDK 的协议纪律移植进 Continuous，而不是换壳。收据：
> `docs/verification/agent-runtime-backends-2026-07-25.md`

`codex_headless` 是**对照线**（`benchmark_only=true`），不是产品候选。

---

## 2. 已完成的代码（不用重做）

`fix/continuous-runtime-provider-neutral@93ac264d`，改动 66 行（含 50 行测试）：

**解开了一个由门禁造出来、而非架构造成的约束。** `agent_runtime_factory.py` 的凭证门
过去只认 `session_provider == "zhipu"`，把一个 provider-neutral 的执行壳锁死在 GLM 上
（`GLMModelClient` 的 docstring 明写 adapter 本身 provider-neutral，吃的是调用方注入的
providers 链，而 `api/app.py` 早已把已解析 provider 的 name/model 透传进来）。
现在接受任一允许的 session provider 与 `OPENAI_API_KEY`，`reason` 从
`glm_api_key_missing` 改为更诚实的 `llm_credential_missing`。

**刻意没做**：没改名、没翻默认值。`continuous_turn_adapter.py:105`、
`run_agent_runtime_benchmark.py:554/619` 与存量台账 JSON 都按 `continuous_glm` 这个
字符串分支——**现在改名会砸坏正要用来跑对照的那把尺子**。默认值另有
`test_default_runtime_backend_preserves_continuous_glm` 显式锁住，翻它是一次有意翻转，需用户点头。

验证：全量 `3687 passed / 13 failed / 2 skipped`。13 条红是**已知宿主基线**——其中 2 条
`test_acceptance_board` 已用 `git stash` 在**未改动的 origin/main** 上复现同名同数，
另 8 条 `test_subconscious` + 3 条 `test_userspace` 是记录在案的环境噪声。ruff 干净，
pre-commit 全过。三条新测试；把凭证门还原成 GLM-only 会打红其中 2 条（第 3 条守的是
`reason` 字符串，那处未变异，如实记录）。

**追加 `a6cdc862`：修 harness 的 root budget 级联缺陷。** `_LIVE_ROOT_BUDGETS`
（`research_contract.py:588`）有写入、有检查，**没有释放**。它一直没被发现，是因为注册表是
`WeakValueDictionary`——正常返回的 arm，ledger 被 GC 后条目自动消失；只有**抛异常退出**的
arm 会留下条目（traceback 抓住栈帧 → 栈帧抓住 context → context 抓住 ledger）。同一题两臂
共用一个 `episode_id`（`task_id` 不含 backend 维度），于是下一臂 0.0004s 撞死在
`root budget already exists`，**看起来像那个壳坏了**。新增 `release_root_budget()`，在
`_run_research_arm` 的 `finally` 里按 `case_id` 释放（不依赖 `context`，故建 context 之前
就崩也照样释放）。验证：`test_repair_invariant_regression.py` 16 passed（含新增 3 条）、
相邻 3 个测试文件 29 passed、ruff 干净、pre-commit 全过（2026-08-06 复核逐条重跑，读数一致）。

> ⚠️ **这个修复有一处没被测试保护，动名字之前必看。** 注册键在 `_fresh_context`
> （`benchmark:572`，`task_id=f"runtime-benchmark:{case.case_id}"` → `episode_factory:322`
> 用 `task_id` 当 `episode_id`），释放键在 `_run_research_arm` 的 `finally`
> （`benchmark:1370`）**重新拼了一遍同样的字面量**。两处目前确实相等（`execution_case`
> 只 `replace` 了 `timeout`，`case_id` 不变），但**没有任何测试断言它们相等**——
> 三条新测试都只测 `release_root_budget` 本身，没覆盖调用点。
> 一旦这个格式改了而只改了一处，释放会**静默变成 no-op**，级联缺陷原样回来，
> 而且症状还是「那个壳 0.0004s 就崩了」。§6 第 3 步的改名正是会碰它的那次改动。
> 便宜的加固：把键收进一个 `_episode_id_for(case)` 之类的单一来源，或补一条断言两者相等的测试。

---

## 3. 🚧 跑之前必须先确认（**上一轮就是死在这**）

### 3.1 账号池必须只剩健康账号（**必要但不充分**，见下方更正）

网关 = `http://localhost:57244/v1`，进程 `cockpit-cliproxy`（Cockpit Tools），
config `~/.antigravity_cockpit/codex_local_access_sidecar/config.json`，
`routing.strategy = round-robin`。

2026-08-05 最后一次实测，池内 3 个：

| # | base-url | 状态 |
|---|---|---|
| #0 | `x.ailzd.com` | 200 ✅（25 模型） |
| #1 | `x.ailzd.com` | 200 ✅（25 模型） |
| #2 | `api.fenno.ai` | **429 `WEEKLY_LIMIT`，仍在池内** ← 必须停用 |

**危害不是「跑不完」，是「随机污染」**：round-robin 轮到坏账号就 502 `no auth available`，
50 分钟的长跑可能反复命中，抖动会随机砸到某一臂，被误读成「那个壳不稳定」。

> ⚠️ **2026-08-05 更正两处，都是我上一版写错的：**
>
> 1. **「#2 未停用」不是唯一阻塞。** 用户移出 fenno 后，开跑前自查 3/3 全 200，第 8 题
>    `unfamiliar-methodology` 的 sdk 臂**照样** 502 `sdk_upstream_unavailable`；跑完再查
>    又是 3/3 全 200。**那个 502 是瞬时抖动**，不是池里有坏账号。它一命中就终止整轮
>    （`RuntimeBenchmarkInfrastructureError` 在 benchmark:1351 是 re-raise，不像普通异常
>    那样降级成单臂失败），所以**这仍是硬阻塞，但根因是抖动，需要重试而不是清池**。
> 2. **「预算不公已被排除」是错的，恰恰相反。** 我当时只看了 `effective_timeout`（外层
>    墙钟，两臂都是 90），没看 `root_budget.initial_seconds`（研究阶段真实秒数）。实测
>    **continuous 30.0s / sdk 60.0s，逐题如此**。详见 §5.3。continuous 那两题恰好
>    30.0s，就是卡死在自己的 30s 研究预算上，**不是网关抖动**。

**开跑前自查（必须三次全 200，别只打一次）**：

⚠️ **不要用 heredoc**（`python - <<'PY'`），本机实测会卡住终端。**存成文件再跑。**
⚠️ 本 worktree **没有** `.venv-workbench`（实测 2026-08-05），解释器只有主仓那一个，
必须用绝对路径 —— 与 §4 用的是同一个 python。

第一步，存为 `/tmp/pool-health-check.py`：

```python
import json, sys, urllib.request, urllib.error

# 脚本在 /tmp，cwd 不会自动进 sys.path，必须显式加 repo 根
sys.path.insert(0, "/Users/a77/finance-workspace-private/.worktrees/continuous-provider-neutral")
from intelligence.services.llm_settings import SessionLLMSettings

p = SessionLLMSettings().byok_provider("linxiaoqi5111")
if p is None:
    print("FATAL: byok_provider 返回 None —— 检查 FORESIGHT_LLM_KEYCHAIN=1（见 §3.3）")
    raise SystemExit(1)
print("provider =", p.name, "| model =", p.model, "| base_url =", p.base_url)

for i in range(3):
    req = urllib.request.Request(
        p.base_url.rstrip("/") + "/chat/completions",
        data=json.dumps({
            "model": p.model,
            "messages": [{"role": "user", "content": "ok"}],
            "max_tokens": 5,
        }).encode(),
        method="POST",
    )
    req.add_header("Authorization", f"Bearer {p.api_key}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            print(i + 1, r.status, "OK")
    except urllib.error.HTTPError as e:
        print(i + 1, e.code, e.read()[:120])
```

第二步跑它：

```bash
FORESIGHT_LLM_KEYCHAIN=1 \
  /Users/a77/finance-workspace-private/.venv-workbench/bin/python /tmp/pool-health-check.py
echo "REAL_EXIT=$?"
```

**判据：三行必须全是 `200 OK`。** 出现任何 429 / 502 就停下——池里还有坏账号，往下跑
只会产出被污染的读数（见上一段）。

> **判额度不能只看网关返回。** 曾经「经网关 429 WEEKLY_LIMIT」而「直连同一个 key 同一个
> 模型 200」——网关那层会把真因盖住。要判账号，直连 `config.json` 里各 `base-url` 的
> `/v1/models` 比对。另注意 `model_not_available`（模型白名单）与 429（额度）是两回事。

### 3.2 环境变量必须补齐（漏了会伪装成「代码回归」）

benchmark **不会**继承生产启动器的环境。上一轮只传了 `--knowledge-wiki` 就开跑，
结果两臂几乎全部输出「现有证据不足」、continuous 引用总数为 **1**——
**不是模型问题（`llm_calls=4` 证明模型调通了），是证据检索根本没工作**。

必须与 `/Users/a77/.local/bin/start-finance-workbench` 对齐（**除 GLM 三件套外全带上**）：
`KB_RAG_PYTHON`、`RAG_INDEX_DIR`、`RAG_WORKER_ENABLED=1`、`RAG_WORKER_PREWARM_TIMEOUT=240`、
`ASK_AGENT_LOOP=auto`、`ASK_EVIDENCE_JUDGE=auto`、`LLM_TIMEOUT=180`、`FINANCE_L3_*`（6 个）。
补齐后 sdk_gpt 单题引用从 0 → **20**，证明这条判断成立。

### 3.3 `FORESIGHT_LLM_KEYCHAIN=1` 是必需的

Keychain store 是 **opt-in**：`llm_settings._credential_store_from_environment()` 不认这个值
就返回 `None`，于是 `byok_provider()` 返回 `None`，报 `saved Keychain provider unavailable`
——**凭证在、账号对，也照样拿不到**。服务名是 `com.foresight.workbench.llm`、account = user_id
（`linxiaoqi5111`）；`openai/gpt-5.6-sol` 是 **payload 里的 provider/model 对，不是服务名**。

### 3.4 题集的 `as_of` 不能丢

`/Users/a77/.finance-runtime/evals/frozen-nine-2026-07-25.questions.json`（已重建好，直接用）。
loader 是 `as_of=str(raw.get("as_of") or date.today().isoformat())`——**丢字段就默认成今天**，
既触发数据新鲜度门，也**悄悄改掉信息截止口径、破坏与冻结集的可比性**（后者不会报错）。
九题必须全部 `as_of=2026-07-24`。

### 3.5 跑前跑后各记一次 `max(trade_date)`

另一个 agent 正在补数（待办 K）。**两臂必须看到同一份数据，否则比的就不是壳。**
变了就标注该次读数不可比，不要照发数字。

```bash
/opt/homebrew/bin/python3 -c "import duckdb;print(duckdb.connect('/Users/a77/finance-workspace-private/db/market_feature_store.duckdb',read_only=True).execute('select max(trade_date) from fact_market_daily').fetchone()[0])"
```

---

## 4. 跑的命令

```bash
cd /Users/a77/finance-workspace-private/.worktrees/continuous-provider-neutral
export FORESIGHT_LLM_KEYCHAIN=1
export KNOWLEDGE_WIKI="/Users/a77/knowledge-base-private/wiki"
export KB_RAG_PYTHON="/Users/a77/knowledge-base-private/.rag_venv/bin/python"
export RAG_INDEX_DIR="/Users/a77/knowledge-base-private/.rag_index"
export RAG_WORKER_ENABLED=1 RAG_WORKER_PREWARM_TIMEOUT=240
export ASK_AGENT_LOOP=auto ASK_EVIDENCE_JUDGE=auto LLM_TIMEOUT=180
export FINANCE_L3_PYTHON="/Users/a77/finance-workspace-private/.venv-workbench/bin/python"
export FINANCE_L3_PYTHONPATH="/Users/a77/finhot/finhot"
export FINANCE_L3_CWD="/Users/a77/finhot/finhot"
export FINANCE_L3_LOOKUP_DAYS=90 FINANCE_L3_LOOKUP_LIMIT=5 FINANCE_L3_CACHE_TTL_SECONDS=900
export FINANCE_L3_COMPANY_CMD='{python_sh} -m disclosure_lookup.cli company {company_sh} --days {days} --source cninfo --limit {limit} --sort triage --json'

/Users/a77/finance-workspace-private/.venv-workbench/bin/python scripts/run_agent_runtime_benchmark.py \
  --backend continuous_glm --backend sdk_gpt \
  --questions-file /Users/a77/.finance-runtime/evals/frozen-nine-2026-07-25.questions.json \
  --keychain-user linxiaoqi5111 \
  --finance-root /Users/a77/finance-workspace-private \
  --knowledge-wiki /Users/a77/knowledge-base-private/wiki \
  --output /Users/a77/.finance-runtime/evals/continuous-vs-sdkgpt-<date>-run3.json
echo "REAL_EXIT=$?"
```

> **不要把命令接管道**（`| tail` 之类）。本轮被假 `exit 0` 骗了三次——管道的退出码是最后
> 一个命令的。至少保留 `echo "REAL_EXIT=$?"`，并且**读输出正文**，不要只看退出码。
> 约 9 题 × 2 臂 × 上限 180s，最坏 ~55 分钟，建议后台跑。

---

## 5. 结果怎么读（**别读成质量结论**）

1. **剔除 `deterministic_fast_path`**：`index-rebound-space` 两臂都 0.4s 走确定性快路径，
   **根本没过 LLM**，不参与壳的比较。真正可比样本 ≤ 8 题。
2. **确认两臂 `model` 都是 `gpt-5.6-sol`**。上一轮 sdk_gpt 的 model 集合里混进过 `unavailable`。
3. **预算对等看 `diagnostics.root_budget.initial_seconds`，不是 `effective_timeout_seconds`。**
   2026-08-05 实测：五道可比题**逐题**都是 continuous `initial_seconds=30.0` /
   sdk `60.0`，而 `effective_timeout` 两边都是 90.0 —— 只看外层墙钟会得出「对等」的
   假结论（我上一版就是这么误判的）。算式：standard tier `total=90 / reserve=20`；
   continuous 走 `GLMAgentRuntime.synthesis_reserve_for_task` 拿 `min(75, 60)=60`
   → 研究 30s；sdk 走 `min(90*0.4, max(20,30))=30` → 研究 60s。
   **continuous 的研究秒数只有 sdk 的一半，延迟/完成度/引用数全部被这个不对称污染，
   不能当壳的差异读。** `ruihuatai-valuation` 的 continuous 臂 30.006s 即是此因：
   卡在 initial 30s 上抛 `production adapter did not reach semantic verification`，
   而不是网关问题。

   ⚠️ **别当 bug 直接抹平——这个不对称可能是有意的。** `_fresh_context`
   （benchmark:555-568）的注释说明：GLM adapter 有独立的 internal finalizer，需要自己的
   合成预算，若按 sdk 的口径给就会被重复扣、把 standard 台账压到 30 秒。
   补一句它没写的：那个 finalizer 是 **adapter 层结构，不是模型层**——
   `EpisodeFinalizer` 吃的是 provider-neutral 的 `GLMModelClient`，所以 continuous 壳
   即使跑 gpt-5.6-sol，这个 finalizer 照样执行。**continuous 那 60s 是站得住的。**

   #### ⚠️ 2026-08-06 复核：口径有三个，benchmark 用的是谁也不是的那个

   `api/app.py:297-300` 的**生产**接线是：

   ```python
   synthesis_reserve_for_task=(
       GLMAgentRuntime.synthesis_reserve_for_task     # 只有 continuous_glm 走这条
       if selection.name == "continuous_glm"
       else _zero_inner_synthesis_reserve             # 其余全部 → 0.0
   ),
   ```

   `_zero_inner_synthesis_reserve`（`app.py:147-155`）恒返回 **0.0**，docstring：
   「SDK/headless already draft inside the episode; reserve only outside it」。
   即生产给 sdk_gpt 的 **inner reserve 是 0**，研究台账吃满 tier total。
   而 `sdk_gpt` 在生产里同样走 `_build_continuous_turn_adapter`（`app.py:245` 分支），
   所以这条对比是同一条代码路径上的，不是两套东西。

   standard tier（total=90）三个数**实测**：

   | | continuous_glm | sdk_gpt |
   |---|---|---|
   | **生产**（`api/app.py`） | reserve 60 → 研究 **30s** | reserve 0 → 研究 **90s** |
   | **benchmark**（`_fresh_context`） | reserve 60 → 研究 **30s** | reserve 30 → 研究 **60s** |

   **continuous 两边一致，sdk 被 benchmark 比生产少给了 30 秒。**
   生产的真实不对称是 **3×**，benchmark 造出来的是 2×。所以现有这把尺子既不复现生产、
   也不对齐两臂，是第三种在任何地方都不存在的配置。

   还有一条不对劲的地方要一起看：`GLMAgentRuntime.synthesis_reserve_for_task` 的 docstring
   写的是「Allocate one fixed total budget by task shape, **never by model choice**」——
   函数自己的契约说预算只由 tier + question_type 决定。**按 backend 分叉这件事发生在两个
   调用点上，不在函数里。** 这到底是有意设计还是漂移，是拍口径时要先答的。

   #### ✅ 口径已拍（2026-08-05，用户）：**复现生产 30 / 90**

   benchmark 的 sdk 臂改成与 `api/app.py:147-155` 一致的 `reserve=0`，continuous 维持
   `synthesis_reserve_for_task`（60）不动。**改完干跑必须看到 `initial_seconds` 实际是
   30 / 90，不是 30 / 60**——断言生效值，不是断言改没改配置。

   理由：这份数据要回答的是「上生产该选哪个壳」，那就该量生产会发生的事；
   不对称本身是各壳的真实成本结构，不是要抹平的噪声。

   另两个口径记录在此，说明为什么没选，避免下一个人重新讨论一遍：

   - **对齐研究秒数**（都给 60 或都给 90）——把两臂拉平，比的是研究能力本身。
     没选：这个配置生产里不存在，赢家不一定迁移得到线上。
   - **对齐总墙钟**（改动前的 benchmark 现状）——认为合成开销属于壳的固有成本。
     没选：现状连这条都没做到——它给 sdk 的 30 是 `min(90*0.4, max(20,30))` 算出来的
     第三个数，既非生产值也非 continuous 值，是个哪儿都不存在的配置。

   ⚠️ **口径是跑之前定的，不能跑完再挑。** 三种口径会给出不同胜负，事后选口径
   等于事后选赢家。
4. **`semantic_status` 本 harness 基本给 `unavailable`——质量维度没有信号。**
   本次能得出的只有**协议稳定性 / 延迟 / 完成度 / 引用数**这类确定性指标。
   **07-25 的 195/175 是盲评 6 维打分，不是这套 harness 产出的；不要用完成度替代质量结论。**
   要质量结论必须另行组织盲评（那是单独一件事）。
5. 方法论对表：`/Users/a77/agent-memory/10_knowledge/eval-harness-variance-governance.md`
   （`.agent-memory` 那个 symlink **只在主工作树有，本 worktree 里不存在**，用绝对路径）
   ——尤其「方差要用干净对照测，不能跨修复比」「确定性手段优先，LLM 判官只吃残差」。

---

## 6. 拿到数字之后的下一步（**顺序不能反**）

1. **A/B 出数字** ← 本 handoff
2. 按结果决定壳，并把 SDK 赢的两项（协议稳定性、延迟）作为 Continuous 的**具体修复清单**
   ——07-25 收据把「针对 Continuous 的 4 个协议问题补回归」列为未竟事项，
   2026-07-28 的 parity handoff 显示当时还剩 2 个，**未清干净**。
3. 改名：`continuous_glm` → provider-agnostic（**A/B 之后**，否则破坏可比性）
   ⚠️ 改名会同时踩到两处**按 backend 名分叉的预算逻辑**——`api/app.py:299` 与
   `benchmark:555`，两处都写死 `== "continuous_glm"`，改名后会静默落到 else 分支
   （生产那条 else 是 reserve=0）。另外 §2 那条注记里的注册/释放键也是 `case_id` 拼串，
   同一次改动要一起过一遍。**改名前先把 §5.3 的口径拍死**，否则口径和名字一起动，
   出了偏差分不清是哪一个造成的。
4. 翻默认值 `factory:58`（消灭「忘设 env 就静默回 GLM」；需改那条 preserve 测试，**要用户点头**）
5. 切生产 8792：改启动器（属主是 launchd，**必须重启才生效**），**需用户确认**

### 切生产时要改的（这份清单被实跑追加过两次，共 5 处）

1. `FORESIGHT_LLM_KEYCHAIN=1`（启动器目前**没有**）
2. 删 GLM 三件套 `FORESIGHT_BUILTIN_LLM_API_KEY/_MODEL/_BASE_URL`
3. 设 `AGENT_RUNTIME_BACKEND=<选定的壳>`
4. 保证 `providers[0].name == "openai"`
5. ⚠️ **env 造不出 openai provider**：`built_in_provider()` 在有
   `FORESIGHT_BUILTIN_LLM_API_KEY` 时把 name 硬编成 `"zhipu"`（`llm_settings.py:190`），
   `detect_providers` 那条叫 `"custom"`（`llm_refine.py:146`）。全仓唯一另一处 `name="openai"`
   在 `codex_headless_runtime.py:569`。**所以 Keychain BYOK 是目前唯一能喂出 openai provider
   的通路——这不是可选项，是硬约束。**

---

## 7. 判断「生产实际在跑哪份代码」

用 `lsof -a -p <8792 pid> -d cwd`，**不要看 `/api/health` 的 `code_root`/`source_revision`**
——2026-08-05 实测两者打架：health 报 dirty 的 dev 树，cwd 实为 clean 快照
`~/.finance-runtime/finance-workspace-bdb0bd77…`。加载哪份代码由 **cwd** 决定。
（`/api/health` 的 `agent_runtime.backend` 字段本身可信。）

---

## 8. 本轮踩过的坑（同一形状踩了三次，别再踩）

1. 只试一个 model → 断言「账号没额度」。**实际是网关路由错账号**，直连上游 200。
2. 只对齐部分环境 → 差点把「RAG env 缺失」当成壳的差异。
3. 差点把网关抖动当成 continuous 不稳定 —— 我当时**以为**「查 `effective_timeout` 已排除
   预算解释」。**那次排除是假的**：该字段是外层墙钟，两臂都 90，看不见 continuous 的研究
   秒数只有 sdk 一半（30 vs 60，见 §5.3）。**部分核验不只会漏掉问题，还会发出假的「已排除」**
   ——比没查更危险，因为它会关掉这条追问线。真对照是 `root_budget.initial_seconds`。

4. **（2026-08-06 追加）查到了两臂的差，就以为查到了全部。** 上一条把
   `initial_seconds` 30/60 挖出来之后，追问停在「两臂之间不对称」，没再往外走一步问
   **「这两个数在生产里各是多少」**。实际生产是 30/90——benchmark 的 sdk 那个 60
   是它自己算出来的第三个数。**两臂互比只能证明「不相等」，证明不了「哪个是对的」；
   要判对错必须跟臂外的基准（这里是生产接线）对一次。**

**共同点：部分核验带来的踏实感会让人停止追问。**
每次救回来的都是同一个动作：**找一个不经过可疑中间层的对照**
（直连 vs 经网关、有 RAG env vs 没有、`root_budget.initial_seconds` vs `effective_timeout`）。

**选对照时先问一句：这个字段是我要量的东西，还是它外面那层？**
`effective_timeout` 是墙钟、`initial_seconds` 才是研究预算；前者看起来能回答预算问题，
其实量的是外层，于是给出「对等」的假结论。第 3 条就是这么错的。

---

## 9. 产物位置

- 题集：`/Users/a77/.finance-runtime/evals/frozen-nine-2026-07-25.questions.json`
- 作废跑 1（缺 RAG env）：`…/continuous-vs-sdkgpt-2026-08-05.json`
- 作废跑 2（第 4 题账号池 502）：`…/continuous-vs-sdkgpt-2026-08-05-full-env.json`
- 作废跑 3（`…-run3.json`，`REAL_EXIT=3`、`summary.passed=false`、9 题只完成 7 题）：
  **环境已全部对齐**（引用 continuous 33 / sdk 40，上一轮 continuous 只有 1；
  `source_revision=7dc94f5c`、`source_dirty=false`；跑前跑后 `max(trade_date)` 均为
  `2026-08-04`）。死于三件事：`ruihuatai` 两臂级联（已由 `a6cdc862` 修）、第 8 题瞬时 502
  终止整轮、以及**预算不对称**。
  ⚠️ **它是目前唯一携带预算不对称证据的产物**（`diagnostics.root_budget.initial_seconds`
  逐题 30/60），别删。
- **三份都不可作为壳的结论依据**，仅留作环境与 harness 问题的证据。
