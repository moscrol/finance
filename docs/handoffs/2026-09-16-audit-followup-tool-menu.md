# 2026-09-16 · E-008 审计补漏：研究过程投影实际工具菜单（fix/audit-followup-0916）

> 分支 `fix/audit-followup-0916`，代码单提交 `ef1d56f5`，PR #760。写作时 PR 开着、未合并、未部署。
> **真值化（2026-09-16 15 时后）**：#760 已合并为 main `0758a423`，分支与工作树已删，在途交接已从 inflight 移除；
> 部署与真实 run 读数见 `docs/handoffs/2026-09-16-8792-switch-0758a423.md`。以下正文保持写作时口径不改。
> 作者 session 做了实现与主要验证，接手 session 补前端 lint/vitest、registry 叶、推分支、开 PR、写本文。

## 一、背景（不读这段会误判后面每个决定）

- **E-008 是什么**：Knevo 蒸馏审计的一条探针记录
  （`docs/learning/knevo-distill/E-008-methodology-source-and-tool-selection-probes.md`）。
  M2e 观察到对方照路由表承诺派单、随后承认子 skill 未挂载。C 线失效模式清单
  （`failure-modes-2026-09-16.md`）把它抽象成「声明能力表被当成本轮可调用集合」。
- **本仓的镜像缺口**：Workbench 研究过程 UI 没有任何一步的实际工具菜单。持久事件流里最早的
  `configure` 携带 `contract.allowed_capabilities`，但它记录在 `derived_calculation` / `sub_research`
  动态装配**之前**，且授权只是上限，还要经预算、时间窗、去重裁剪。09-09 的 E-008 §5 把它定位为
  「投影缺口不是仪表缺口」，并建议先收敛 `allowed_capabilities` 的十几处读取点。
- **09-16 复核推翻了「收敛读取点」这条路**：读取点不该是授权字段，而是模型请求前那份实际菜单。
  运行时已有 `tool_session.menu()` 与 `tool_menu` 事件（此前只在藏了工具时落账），缺的是
  「每步都落 + 投影到公开边界」。
- 同轮顺带复核 E-009 工作清单（`docs/superpowers/specs/2026-09-10-knevo-arch-delta-worklist.md`）
  W1–W6 的主干状态，把 C 线已有证据汇成失效模式清单。这两件是文档订正，不改代码。
- 8792 生产实例当时跑 `6e23dd57`（`/tmp/audit-followup-8792-health.json`：continuous_glm / kimi-k3 / ready）。
  本轮**没有**切流、没有真实模型回归。

## 二、按发现顺序做了什么（北京时间；证据在 `/tmp/audit-followup-*.log`，重启即失）

| 时刻 | 事 | 读数 |
|---|---|---|
| 13:06–13:07 | 刷代码地图；探 8792 健康 | 8792 @6e23dd57 ready |
| 13:13 | 先写 `intelligence/tests/test_tool_menu_progress.py`，实现前跑 | 4F / 5P（红） |
| 13:15 | 落账 + 投影 + 封闭语法实现后 | 47P；E-009 五个定向文件 151P |
| 13:16 | runtime 回归 | `test_agent_episode.py::test_progress_sink_observes_append_only_events_before_and_during_model_work` 1F / 484P。该测试在假模型内部断言首轮 durable 事件序列，序列里没有新加的 `tool_menu`；断言异常被运行器吞成 `status=failed`。修法是把 `tool_menu` 加进期望序列并**新增**「visible == 交给模型的工具名」断言，不是放宽 |
| 13:16 | 前端 typecheck + build | 绿 |
| 13:19 | e2e 第一次 | webServer 用宿主 `python3.14` 起服务，无 uvicorn，未启动 |
| 13:29 | e2e 第二次（venv 进 PATH） | 30P / 1F / 2S；红的是 desktop `research-evolution-binding.spec.ts`「表单建绑定→服务端落账→投影刷新」 |
| 13:53 | e2e 第三次（同代码） | 31P / 2S |
| 14:10 | 变异 A：删两条 loop 的 `ledger.add("tool_menu")` | `test_real_episode_menu_includes_only_bound_tools_even_when_model_is_down[True/False]` 2F；参数 `coordinator_present` = 子研究协调器装配 / 未装配，两种都在模型不可用下跑 |
| 14:11 | 变异 B：公开边界改回只验前缀 | `test_public_boundary_rejects_forged_menu_prose` 三例红：`secret-tool` 单独、`盘面快照、secret-tool` 混入、`盘面快照、盘面快照` 重复 |
| 14:12 | 还原 | 151P |
| 14:27 | 提交 `ef1d56f5` | 15 文件 +391 / −39 |
| 14:28–14:29 | 干净树 ruff、e2e | 绿；31P / 2S |
| 14:34 | 干净树全量第一次 | 约 69% 处中断，无汇总行；收据 `20260916T063317Z-ef1d56f5.json` 计数全零，**不可用** |
| 14:43 | 干净树全量重跑 | 10961P / 0F / 83S / 2xf，exit 0；收据 `20260916T064327Z-ef1d56f5.json` |
| 14:37–14:40 | vault：能力图谱加「在途」行、`contract-vs-delivery-mismatch` 补方法段、项目笔记一行；`graph_audit.py` OK | vault lint 对这三份无新增错误（16 个错误均为存量） |
| 接手 | 前端 lint / vitest / typecheck / build、registry 四条 `--check` | 全绿；vitest 95P |
| 接手 | 推分支、开 PR #760、补两份交接 | — |

## 三、决策与方案对比

### D1 · 投影读什么

| 方案 | 评价 | 结果 |
|---|---|---|
| 投影 `configure.allowed_capabilities` | 早于动态装配，会把未装配的子研究报成可调用；授权 ≠ 装配 ≠ 可用 | 否 |
| 收敛十几处 `allowed_capabilities` 读取点后再投影（09-09 建议） | 投影的仍是授权上限，工作量大且不解决装配时序 | 否 |
| 在 UI / API 层重算一份权限清单 | 第二事实源，必漂 | 否 |
| **读模型请求前的 `tool_menu.visible`** | 与 `tool_definitions_for_menu` 同源，已过授权、装配、时间窗、去重 | **选** |

### D2 · 什么时候落账 `tool_menu`

| 方案 | 评价 | 结果 |
|---|---|---|
| 保留「只在 `menu.hidden` 时落」 | 无裁剪轮没记录，UI 分不清「没工具」与「没记」；投影只会偶尔出现 | 否 |
| **每个开放工具的模型步都落** | 代价：放弃旧不变量「无裁剪轮事件流与改前逐字节相同」；`test_no_pruning_leaves_the_event_stream_untouched` 换成「无裁剪也留菜单且与模型输入一致」 | **选** |
| 收口阶段（`finalization_started`）也算菜单 | 那一步不给模型工具，算出来就是把「可调用」记在一个不会调用的步 | 否，`definitions=[]` |

### D3 · 公开边界怎么放行菜单句

| 方案 | 评价 | 结果 |
|---|---|---|
| 沿用集合成员（只放行固定句） | 菜单是标签组合，集合装不下 | 否 |
| 只验前缀「此步模型可调用工具：」 | 模型或别的 trace 生产者写这个前缀就能把私有名带到公开面（变异 B 证实） | 否 |
| 枚举全部标签子集 | 指数空间 | 否 |
| **封闭语法**：固定句 ∪ {空菜单句, 未记录句} ∪ 前缀 + 闭集标签（唯一）+ 后缀 | 标签表与投影同源；重复标签、未知标签、缺后缀都不过 | **选** |

### D4 · 三种「没有」分三句

空菜单「此步未开放可调用工具」、未记录 / 畸形「此步工具菜单未记录；不能推断可调用范围」、未知名「未识别工具（不展示名称）」。
否掉的是合成一句「无工具」：旧 run 没记录会被读成「当时没工具」，反推出错误授权结论。

### D5 · 出口放哪

进研究过程 / 运行详情（`episode_progress` → RunStore trace / SSE → `api.app._public_trace_step`），
不进 `session_projection.view()`。后者是终局金融答案的纯函数出口，不是工具状态面；
09-09 曾以「它不读授权字段」为由考虑在那里加，复核否掉。

## 四、验证与收据

- 四叶全在 `ef1d56f5` 干净树，表格见 PR #760。可采信收据只有 `20260916T064327Z-ef1d56f5.json`
  （`scripts/check_test_receipt.py --expect-revision ef1d56f5` 七项一致）。同 revision 另两张收据计数全零，是中断产物。
- **不成立的结论**：13:29 e2e 的 1F 是 n=1，后两次 31P/2S 不能证明它偶发，也不能证明与本改动无关；
  该用例依赖隔离服务 + 真实市场库。合并前若再红，先看它自己的 trace 再归因。
- 变异证据在提交前的脏树上取得（收据名带 `32bff514`），**未在 `ef1d56f5` 上重做**；
  全量 10961P 覆盖这些用例的绿，不覆盖它们的红。
- 前端 lint / vitest 由接手 session 在已提交树补跑；作者 session 只跑了 typecheck / build。
- 没有任何生产读数：8792 未切流，无真实模型回归；SSE 到浏览器只有既有 e2e 覆盖，
  没有「菜单句出现在页面」的 e2e。

## 五、后续要做的

1. 用户确认后合并 #760：先重探 `git merge-tree --write-tree gitea/main fix/audit-followup-0916`；
   main 漂动超 `check_test_receipt.py --base-drift-max` 就重跑门禁。
2. 部署到 8792 后，用一条真实问题看研究过程里是否出现「此步模型可调用工具：…」；
   模型不可用时应仍看到请求前菜单，且没有「已取得…」。
3. 若要让 e2e 钉住页面出现菜单句，加一条 workbench spec。本轮没加：e2e 走真实服务，菜单内容随合同变，需先定一条稳定题。
4. E-008 §5 回灌候选、W3 `RELIABILITY_DOWNWEIGHT_THRESHOLD=None`、W4 暂停 B 线：全部待用户裁决，与本分支无关。

## 六、不要做的（含理由）

- 不要把 `allowed_capabilities` 再接回投影：它是授权上限、装配前记录，改回去就是 E-008 那个失败形状。
- 不要为了「事件流逐字节不变」把落账改回 `if menu.hidden`：那条不变量被本轮有意放弃，理由见 D2。
- 不要在 `_public_trace_step` 按前缀放行：变异 B 证明会漏私有工具名。
- 不要用 `20260916T063317Z` / `063939Z` 两张零计数收据当证据。
- 不要因为 8792 健康就写「线上已有菜单」：health 的 `source_revision` 是滞后标签，线上跑的是 `6e23dd57`。

## 七、沉淀盘点

| 问 | 答 |
|---|---|
| 同一手工排查做了两次以上？ | 没有 |
| 建了只在 /tmp 跑的脚本？ | 没有；所有验证都是既有命令 |
| 现有门禁的洞？ | 公开边界原是集合成员判断，本身没洞；新增菜单句后若不改会全部落到「已完成一项证据核对」。已由封闭语法 + 变异 B 钉住 |
| 可迁移模式？ | 「配置快照 ≠ 执行快照：投影消费者前最后那份实际状态，不重算权限」+「桩内断言会被生产 except 吞，先捕获再在运行器外断言」，已进 agent-memory `10_knowledge/contract-vs-delivery-mismatch.md` |
| 为什么是手法不是工具？ | 前者是设计选择，要靠语义判断读取点在哪；后者是测试写法。都不是可执行检查 |
