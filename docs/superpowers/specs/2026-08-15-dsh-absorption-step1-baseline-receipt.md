# dsh 吸收 Step 1 基线复核收据

日期：2026-08-15
对应 spec：`docs/superpowers/specs/2026-08-15-agent-base-dsh-absorption-design.md` §11 第 1 步
执行分支：`feat/dsh-absorption-p0-seams`，基于 `gitea/main@23e2a07e`

证据等级标注：**[实测]** = 跑过命令/读过代码；**[推断]** = 推理得出。本收据只在
**[实测]** 项上做断言。

## 0. 结论

第 1 步的硬闸（dsh base bundle 是否有 Arm A 实际 Provider/模型的适配器）**通过**，
可以继续第 2 步。但复核同时查出**两处基线漂移**，它们不阻塞第 2–6 步（纯 Python
接缝，不调模型），却会在第 8 步 A/B 判定时产生错误读数，必须先修：

| # | 发现 | 影响的 spec 条款 | 阻塞哪一步 |
|---|---|---|---|
| 1 | spec 声明的基线 `main@a189d6bd` 落后活基线 19 个提交，生产跑的 revision 不在本地 main 上 | §正文第 5 行 | 第 2–6 步的落点（已处理） |
| 2 | benchmark 交接命令的 `--keychain-user` 路径指向已废弃网关 + 已退役模型 | §9.2 固定变量、§10 风险表 | 第 8 步 |

## 1. 硬闸：dsh 能否跑 Arm A 的 Provider/模型

**结论：通过，且是纯配置、零代码改动。** [实测]

pinned commit `47f943859bef60e4160492346772ded9b24f765a` 下，base bundle
（`packages/bundle/base/cordis.patch.yml`）只挂两个 LLM adapter：

- `@deepseek-ai/dsh-llm-deepseek` —— 原生 DeepSeek；
- `@deepseek-ai/dsh-llm-pi-ai` —— 多 provider，**默认休眠（零路由）**，直到
  settings 里的 `llm-pi-ai:` 段供给 profile 才注册路由。

默认模型是 `provider: deepseek-official` / `model: deepseek-v4-flash`。
**没有内置 OpenAI adapter。**

但 `packages/llm/llm-pi-ai/README.md` 明确支持「手写声明路由」：pi-ai 未收录的
provider 可以整条自己声明，README 原文——

> a route pi-ai does not ship is declared outright, so an OpenAI-compatible
> gateway, a self-hosted server, or a provider newer than the installed catalog
> is **configuration rather than a code change**.

可配字段含 `api: openai-completions`、`baseURL`、`apiKeyEnv`、`models[].id`。
Arm A 的中转正是 OpenAI 兼容端点，故形状吻合。

> **取证路径**：`packages/llm/**` 起初不在 sparse cone 内（cone 只有 docs、
> packages/core、packages/bundle/base、apps/cli、packages/host），上述 README
> 当时是用 `git show HEAD:packages/llm/llm-pi-ai/README.md` 读的。**cone 已扩入
> `packages/llm`**，现在可直接 `cd tmp/dsh-source-index && cat
> packages/llm/llm-pi-ai/README.md` 复现。spec §3.2 的重建命令需同步加该路径。

### 落地时的三个前提（都不是阻塞项，但漏一个就跑不起来）

1. **pi-ai 默认休眠**，A/B 前必须在 dsh settings 供 `llm-pi-ai:` 段，否则零路由。
2. **凭证注入**（本条初版写错，已更正）：README L108 实测原文为
   「Credentials resolve per stream call through `apiKeyEnv` **and the optional
   `ctx.credentials` seam**; without that seam, the adapter reads exactly the
   referenced environment variable.」——即 `apiKeyEnv` **不是唯一通路**，
   还有 `ctx.credentials` seam。初版据此把「Keychain→env」称作**新增的密钥暴露面**，
   属于夸大：Arm A 生产今天就是 Keychain→env（`start-finance-workbench`），
   这只是同一模式的第二个消费者，不是新类别。A/B 轮的做法见 §6.2。
3. **可能需要 `compat.thinkingFormat`**：pi-ai 认不出中转的 URL 时，推理方言要显式声明。

## 2. 基线事实（第 1 步要求保存的四项）

### revision [实测]

| 对象 | 值 | 说明 |
|---|---|---|
| spec 声明基线 | `main@a189d6bd` | **已过期**，见 §3.1 |
| 本地 `main` | `a189d6bd` | 落后 `gitea/main` 19，领先 0 |
| `gitea/main`（活基线） | `23e2a07e` | fetch 后确认 |
| `origin/main`（GitHub） | 落后本地 main 13 | 非日常远程 |
| **生产 8792 实际加载** | `cb09f895` | `/api/health` 自述，`source_dirty=false` |
| 本次实现分支基于 | `gitea/main@23e2a07e` | |

`cb09f895` **是 `gitea/main` 的祖先，且不在本地 `main` 上**（`git merge-base
--is-ancestor` 双向验过）。

### 环境 [实测]

```
Python      3.12.13   （解释器必须是 .venv-workbench/bin/python）
duckdb      1.5.4
pytest      8.3.5
openai      2.48.0
agents      已安装（sdk_gpt 的就绪条件之一）
```

### Provider / 模型 [实测]

生产启动器 `/Users/a77/.local/bin/start-finance-workbench` 的生效值：

| 项 | 值 |
|---|---|
| `AGENT_RUNTIME_BACKEND` | `continuous_glm`（= Arm A，枚举名里的 glm 是历史包袱） |
| `ASK_CONTINUOUS_RUNTIME` | `on` |
| `LLM_BASE_URL` | `https://x.ailzd.com/v1` |
| `LLM_MODEL` | `gpt-5.6-terra` |
| key 来源 | Keychain `finance-workbench-test-relay` / `a77` → `OPENAI_API_KEY` |
| `FORESIGHT_LLM_KEYCHAIN` | `0`（BYOK 关闭，走 env 链） |
| 代码根 | `/Users/a77/finance-workspace-runtime`（运行快照，非开发树） |

中转连通性 [实测]：`GET https://x.ailzd.com/v1/models` → **200**，7 个模型，
`gpt-5.6-terra` 与 `gpt-5.6-sol` 均在售。

### 数据截止日 [实测]

`db/market_feature_store.duckdb` 只读查询，四张主 fact 表一致：

```
fact_market_daily     max=2026-08-13   rows=399
fact_sector_daily     max=2026-08-13   rows=100,238
fact_stock_daily      max=2026-08-13   rows=2,020,999
fact_sw_l1_daily      max=2026-08-13   rows=4,166
```

## 3. 两处漂移

### 3.1 spec 声明的基线已过期 19 个提交 [实测]

`main..gitea/main` 的 19 个提交里，**有 4 个文件正是第 2–5 步要改的**：

```
intelligence/runtime/agent_episode.py           +5
intelligence/services/episode_protocol.py       +6
intelligence/tests/test_agent_episode.py       +27
intelligence/tests/test_episode_protocol.py   +320
```

基于本地 `main` 开工会写在陈旧的 `agent_episode.py` / `episode_protocol.py` 上，
并在合回时冲突。**处理：实现分支已改基于 `gitea/main@23e2a07e`。**
spec 正文第 5 行的「基线：main@a189d6bd」应同步更正。

### 3.2 benchmark 的 Arm A 与生产 Arm A 不是同一条线 [实测]

交接 `docs/handoffs/2026-08-05-continuous-vs-sdkgpt-nine-case-ab.md:224-230` 记的
命令带 `--keychain-user linxiaoqi5111`。该 Keychain 条目
（`com.foresight.workbench.llm`）的非密字段是：

```json
{"schema_version": 1, "provider": "openai",
 "base_url": "http://localhost:57244/v1", "model": "gpt-5.6-sol"}
```

即 **cockpit 网关 + `gpt-5.6-sol`**。而：

- cockpit `http://localhost:57244/v1/models` → **401**（仍然坏着）；
- 生产用的是 `https://x.ailzd.com/v1` + `gpt-5.6-terra`（2026-08-08 因延迟实测
  由 sol 换 terra，见启动器 61-82 行）。

所以照抄那条命令，Arm A 会打到一个死网关、用一个已退役的模型——**这正是 §10 风险表
里「Provider 或模型差异污染 A/B」那一行的现场**。

**第 8 步跑 A/B 前必须**：不带 `--keychain-user`，改用与生产对齐的 env
（`credential_source` 应为 `environment`），并在 artifact 里核对 resolved 值。

## 4. 已跑的检查

| 检查 | 结果 | 备注 |
|---|---|---|
| `scripts/layer_audit.py` | ✅ ERROR 0 | 241 模块，结论自述「对 docs/dsh-absorption-spec@389756eb 成立」 |
| `scripts/check_path_literals.py` | ✅ 无新增 | 存量 34 文件/49 处，当前 32/47 |
| `scripts/check_unread_fields.py` | ✅ 无新增 | 存量 40 文件/100 字段，当前 40/99 |
| `scripts/check_agent_workspace_facts.py` | ✅ | |
| Runtime benchmark `--dry-run` | ✅ EXIT=0 | 9 题装载正常，`mode=dry_run`，`credential_source=environment` |
| 全量单元测试 | ✅ 4924 passed / 4 skipped / 0 failed | 见下 |

> **退出码纪律**：benchmark 那条**没有接管道**。交接里记过「本轮被假 `exit 0` 骗了
> 三次」——管道的退出码是最后一段的，`cmd | tail` 永远读不到 cmd 的失败。

### 全量单元测试 [实测]

**第 2–6 步的对照基线（对 `feat/dsh-absorption-p0-seams@23e2a07e` 成立）：**

```
4924 passed, 4 skipped, 8 warnings in 366.90s
PYTEST_EXIT=0
实际加载 intelligence 于: /Users/a77/fwp-wt-dsh-seams/intelligence
```

跑法（三个细节都是必须的，少一个就测错东西）：

```bash
cd /Users/a77/fwp-wt-dsh-seams
PY=/Users/a77/finance-workspace-private/.venv-workbench/bin/python
$PY -c "import intelligence,os;print(os.path.dirname(intelligence.__file__))"  # 断言加载源
$PY -m pytest -q -p no:cacheprovider > /tmp/x.log 2>&1; echo "PYTEST_EXIT=$?"    # 不接管道
```

1. **解释器用主检出树的绝对路径**：`.venv-workbench` 被 gitignore，新工作树里没有，
   直接跑 `.venv-workbench/bin/python` 会 `exit 127`。
2. **cwd 必须是工作树**：venv 里没有 `.pth`/egg-link（已验），`import intelligence`
   由 cwd 决定，所以「主树的解释器 + 工作树的 cwd」加载的是工作树代码——上面那行
   断言就是为了证明这一点，不能只凭配置推断。
3. **不接管道**：`cmd | tail` 的退出码是 tail 的。第 1 次跑就是靠这条看见 127 的；
   接了管道会显示 exit 0 + 一行空日志，看起来像跑过了。

> 对照：在 `docs/dsh-absorption-spec` 分支（陈旧本地 main 线）上跑的是
> `4905 passed, 3 skipped`。差的 19 passed / 1 skipped 正是 §3.1 那 19 个提交
> 带进来的测试。**那份不能用作本次基线。**

## 5. 顺带查实的两件事（供第 2、6 步用）

- **`EpisodeScope` / `ToolPipeline` / `RuntimeHandle` / `ResearchProfile` /
  `dump_effective_config` 全树 0 命中** [实测]，确系新建，不是重复造。
- **但 `intelligence/services/research_policy.py:10` 已有 `GroundedBudgetProfile`**
  [实测]。第 6 步的 ResearchProfile 应当吸收它，**不要另起第二份配置源**。
- §7.2 描述的漂移是真的 [实测]：`contract.allowed_capabilities` 在
  `runtime/` 与 `services/` 的 10 个以上位置各读各的（registry、tool_batch、
  episode_tools、conversation_orchestrator、headless_tool_gateway、
  codex_headless_runtime、openai_agents_runtime、generic_research_owner、ask
  ……），这正是 EpisodeScope 要收拢的东西。

## 6. 三个待决问题的裁定（2026-08-15 检阅方定，第 8 步执行前生效）

### 6.1 A/B 样本量：校准先行，门槛不动

九题不够——n=9 配对下，5pp 只在单题方差 ≤5pp 时才可分辨，不现实。故：

1. **先做校准**：第 8 步前用冻结九题 × 5 重复跑**纯 Arm A**（45 次），
   实测每题配对差值的方差 σ_d；
2. **题集扩到 30 题**，按 quick / deep / daily-review 分层，**九题作为子集保留**，
   冻结成新题集文件（沿用现有冻结机制，不改判据表达力）；
3. **每臂每题 3 重复**，成本地板 2；
4. **判定用同题配对差值的 bootstrap 95% CI，门槛落在 CI 上界**，不看点估计；
5. 若校准显示 30×3 压不住 5pp，**加题或加重复，不许放宽门槛**——这正是 §9.4
   现在的写法（样本量不足时先扩大题集或重复次数，不得直接判定）。
   本条与冲突矩阵 row 10 互为钉死：5pp 不是旋钮。2026-08-16 校准后按
   v=0.1375 锁 30×15=450/臂；草稿 0.125→30×13 标 dropped。

### 6.2 dsh 凭证注入：走 `apiKeyEnv`，但用专用变量名

A/B 轮走 `apiKeyEnv`（`ctx.credentials` host 插件记为 **P2**，只有 Adapter 熬过
A/B 进入长期维护才评估）。四条要点：

- **专用变量名**（如 `DSH_AB_RELAY_KEY`），**不复用 `OPENAI_API_KEY`**：
  README 写明 `apiKeyEnv` 省略时 catalog route 会走 pi-ai 的 provider-native
  **ambient discovery**，共用通用变量名容易被别的工具误拾；
- **只注入 dsh 子进程环境**，不进当前 shell、不进 launchd plist；
- `settings.yaml` 本来就只存**引用**不存密钥，保持；
- **artifact 只记指纹**，不记 key 本身。

### 6.3 spec 基线行：改

`docs/superpowers/specs/2026-08-15-agent-base-dsh-absorption-design.md` 第 5 行
改为 `gitea/main@23e2a07e`，同行注明生产实跑 `cb09f895`（gitea/main 祖先），
并引用本收据。

> ⚠️ **合回时留意**：`gitea/main` 已推进到 `f43f2507`，越过了本实现分支的分叉点
> `23e2a07e`。合并前需重新对表，本收据的「基线」一节只对 `23e2a07e` 成立。

## 7. 交付外的发现（不属本次范围，记录备查）

`ceiling fixture` 的三个测试文件**对 umask 敏感**：`umask 077` 下 mode 审计必挂
（检阅方复跑时得到 16 个失败，校正回 022 后 35/35 全过）。进 CI 或换执行环境时
会咬人，值得加一个 umask fixture 或在测试内显式设权限。
