# 工单：长尾变形题与 ReAct 臂差距收口（2026-08-27 四臂对照产出）

- 状态：**§P0 已收口**（2026-08-27 21:20）：`R-20260827-07a` refuted（归因升格 controller 层）→ `R-20260827-10` 修复 **live confirmed**（修复树 8822@`111af0f7` 复跑 D6：controller 地板生效、detail 破案=GLM 只回三键被全等校验拒收、tool 步 0→4、machine-truth rate **0.0→1.0**）→ **#454 检验通过**（答案引用 `limit_advance_daily` 与 12 行真值逐字吻合）。PR #465 open 待验收。收据 `~/.finance-runtime/p0-d6-20260827/`。§P1/§P2 仍待认领（§P1 是 §P2 跨臂差分的前置）；§P2-D5 定层前先查 controller 步 `llm_failure_reason`（D6 教训：unparsable 降级会让「从未发出某类查询」在 plan 之前就成立）
- 状态补记（2026-08-28 01:10）：**§P2-D2 已收口**——`b614daf0` 经 #473 合入、8792 切 `33026dc1ef1a`，预注册判据复跑 D2 rate 0.25→**1.0**（judge repaired）、搭车 D10 0.0→**0.8**，`R-20260827-08` **confirmed**（38-run 遥测窗留观）。**§P1 档 A 已交付**——映射表落 `docs/trace-profile.md` §6（`claude-console-session`），D2 双侧 M2 验收报告 RC:0 且 residual 含 plan/observe 两条损耗（`~/.finance-runtime/react-gap-m2-20260828/m2-d2.md`）；档 B（驱动器 plan 地标 + 返回摘要）待下轮实验前实施。**§P2-D5 M2 已取证**（同目录 `m2-d5.md` RC:0）——缺口钉死 tool 前缀（0 次实体解析类查询，形状①②排除、controller 干净），定层收窄至 H2 送达层（plan 阶段表未进 episode task 载荷）vs H3 模型选择层，消融预注册在 `R-20260827-09`；不变性复跑（run_20260828_010136_666196）证 #473 不触及本案（graph_lookup 仍 0 次），并暴露 D5 失败面复合（该次自选 sector_daily×3 但 `missing_required_output` 核验不过）。剩余：`-09` 消融实施（改生产行为，等用户裁决 H2 注入方案 vs 确定性预取）＋档 B。
- 状态补记（2026-08-28 01:50）：**H2 送达消融已执行并 refuted（不充分）**——PR #482（阶段表送达，四钉红绿+206P 回归+wiring 五环 live 证明）挂起等裁决；8823 临时臂 D5×3 全 0.0（判据 ≥2/3 未达），r3 解剖钉出**精确板块名解析缺失**（主体拓宽→`contains "核"`/成交额 top8，全程未按「可控核聚变」精确名查 sector_daily；react 臂即精确名命中）＋查询 cutoff 弹回摩擦＋判官当晚 3/5 unavailable 噪声。`R-20260827-09` 已回填 refuted（归因升格）。**下一步=确定性预取设计**（theme subject→精确 sector_daily/sector_stock_daily 行，形状同 `2026-08-25-step-trajectory-qualification-design.md` 的 subject 解析梯先例），新行用 #481 取号器预注册，设计稿等用户过目再实施。
- 来源：四臂对照 `~/.finance-runtime/four-arm-20260827/`（38 题 × 4 臂：`8792` / `8796` / `component` / `react-claude`）。
  两条产品臂 `8792` = `8796` = `40fd5a847c65`，dirty=false，backend=continuous_glm，model=glm-5.3；
  react-claude 臂 = Claude 控制台 ReAct 驱动器，产物为每题 `session.json`（合同字段 + calls 数组）+ `answer.md`。
- 判分真值：`analysis/machine-truth-unseen.json` / `machine-truth-seen.json`（generated_at 2026-08-27T08:43Z）。
  判分器已过变异测试（数字抽取正则的有序交替坑，见 `analysis/defects-found.md` 附录——新判分器没被变异证伪过就是假门禁）。
- 读数（mean_rate，[实测]）：unseen 集 react **0.857** > 8796 0.595 > 8792 **0.567** ≫ component 0.111；
  seen 集 react 1.0 > 8792 0.721。
- 台账：`R-20260827-07a/-08/-09` 三行已随本单**同批**写入 `docs/prediction-ledger.md`
  （crosswalk 正反向均可对上；不重犯 `2026-08-27-qc-gate-and-ledger-integrity-workorder.md` §P1-b 点名的「spec 引号、台账无行」）。
  ⚠ D6 行**原号 `-07`**：预注册落在本分支期间，main 经 #462 落了 export-increment 事故同号行，
  按 `-03a` 先例改号 `-07a` 留档（本单全部引用已同步）；该行 2026-08-27 21:00 已回填 **refuted**。

---

## §0 · 差距在哪（冻结读数，全部 [实测]）

D 组（unseen / 改写变形，即长尾鲁棒性组）10 题，8792 落后 react 臂的三题 + 两条本单核实新增的附注：

| case | 8792 | 8796 | react | 差距 | 根因状态 |
|---|---|---|---|---|---|
| D2-stock-rephrased | 0.25 | 0.5 | 1.0 | −0.75 | 判官扣留（**假设**，待 M2 确认）；修复 `b614daf0` 在分支 `fix/range-cutoff-and-judge-fallback`，**未合 main** |
| D5-theme-unseen | 0.0 | 0.0 | 1.0 | −1.0 | 检索计划缺实体解析跳（**假设**，待 M2 确认）；**无对应改动** |
| D6-ladder-rephrased | 0.0 | 0.0 | 1.0 | −1.0 | ~~工具层缺表~~ → **复跑证伪（`R-20260827-07a` refuted）**：controller `unparsable_response` 一次失败即降级 chat 零检索，检索计划从未生成，#454 装没装上轮不到问；归因 controller 层（`R-20260827-10`）。D9 也在同一 unparsable 簇里（8792 侧 4 个 unparsable = 全部 chat lane：B6/C8/D6/D9） |
| D10-multiday-evolution | 0.0 | 0.0 | 0.0 | 三臂全灭 | 区间截止日取**起点**（**已证**，缺陷 D-1，`requested_information_cutoff` 守卫词表分叉）；修复与 D2 同在 `b614daf0` |
| D9-temporal-leakage | None | None | None | 判分器对三臂均无法判 | 判分侧缺口，非产品缺口，本单不修（§5 非目标） |

三题现场证据锚点：

- **D2**（8792 run `run_20260827_152937_309324`，probe.json [实测]）：`judge_status=unavailable`、
  issues=`["semantic judge provider error"]`、`verified_status=partial`、`terminal_phase=evidence_gap_fallback`、
  `judge_unavailable_count=1`。同形生产面读数：**8/38 = 21%** 的 run 判官不可用、整篇被扣（`b614daf0` commit 内实测）。
  main 现状：`episode_semantic_verifier.py::_stable_semantic_judge_error` 的瞬时档只认
  `retryable = "empty_model_response" in normalized`，grok CLI 故障串是**类名**（`GrokCli…`），
  会被 `invalid` 分支抢走判成永久（retryable=False），三连重试机制被短路。
- **D5**（对照锚点 [实测]）：react 臂首跳 `graph_lookup`（题材 → 产业链/公司实体解析），随后
  `kb_search → evidence_search → finance_query sector_daily → sector_stock_daily` 共 5 跳；
  8792 侧 trace（run `run_20260827_134712_662543`）只见 6 次粗粒度 `research` 调用，
  具体工具与参数在 `continuous-episode.json` 载荷内，**尚未取证**——这正是 M2 的活。
- **D6**（缺陷 D-4，已证）：`finance_query` dataset 白名单里没有连板晋级全集表，
  `fact_limit_advance_daily` 有完整数据但模型够不着——「表现是模型答不好，根因是没给它数据」，加提示词无效。
  #454 已注册 `limit_advance_daily` + `theme_limit_stock_daily` 两个 dataset（工具 schema 全派生，注册即生效）。
- 8792 修前三题 run 产物均在 `/Users/a77/.local/share/finance-workbench/users/fourarm0827-8792/runs/`
  （D6 = `run_20260827_153157_271373`，trace.jsonl 8.7KB + stream.jsonl 19.7KB）。

> 题面与期望值刻意不抄进本单：评测题面/答案侧事实不进 git 文档（与 prediction-ledger 记账规则同源），
> 判分一律回指 runtime 目录的 machine-truth 文件复打。

## §1 · 判别机制约定（动手前先读）

1. **「8792 在哪掉队」的判别器只有一个：`agent-run-triage` M2**（同题 A/B 按 L1 九步对齐找第一次分叉）。
   `harness-architecture-review` 判的是「该补哪层」，其互斥路由第一行就写着「给了 trace → 走 agent-run-triage」。
   正确接法是**串联**：M2 定位第 n 步分叉 → 架构审查判该步属哪层 → 修。跳过 M2 直接审架构 = 没有分叉证据猜层。
2. **混杂变量声明**（m2-differential.md 对齐规则第 7 条：一次只解释一个 ablation 变量）：
   react 臂与 8792 之间**模型（Claude vs glm-5.3）与引擎（ReAct vs episode）双变量混杂**。因此：
   - 跨臂 M2 只用于**假设生成**（分叉发生在哪个 L1 前缀）；
   - **假设确认一律用 8792 自对照消融**：修前 run vs 修后复跑，单变量 = 该修复本身，结论不受模型差异污染。
3. **「该分叉却没分叉」是一等结论**（m2-differential.md 第 25 行起）：预期某步出现变换而两侧仍相同，
   输出 `expected_divergence_step` + `observed: none`——「该动没动」比「动错了」信息量大，因为错误动作留痕、遗漏只有沉默。

## §P0 · D6 自对照复跑（最便宜：改已落地、只差复跑）

> **已执行（2026-08-27，结论 → `R-20260827-07a` refuted）**：双臂 8820@`31809161`（pre-#454）/
> 8821@`3816b297`（post-#454）+ 冻结原始，三 run controller 输出一字不差
> `unparsable_response → chat 零检索`，`ablation_activation_step=none observed`——但归因不在下表
> 预写的「装了没用」形状：**检索计划从未生成**，判据一在 controller 层就短路了。
> 修复与复验接力 `R-20260827-10`；本节判据表对「controller 正常出牌」的 run 仍然有效，
> `-10` 落地后按原判据复跑检验 #454。环境防坑四查两台全绿（cwd 指对树、RAG env 四条齐）。

**动作**：在含 `3816b297` 的树上（main ≥ `470e43a3`；⚠ 生产 8792 当前 `40fd5a847c65` **不含**该提交，
须新 worktree 起临时服务复跑，或等下次切流后在生产复跑）用 frozen 题面复跑 D6，
对照修前 run `run_20260827_153157_271373` 做 M2 自对照（单变量 = #454 dataset 注册）。

**判据（可判定）**：

| 观测量 | 阈值/形状 | 含义 |
|---|---|---|
| `ablation_activation_step` | 修后 trace 的 finance_query 调用出现 `dataset=limit_advance_daily`（或 `theme_limit_stock_daily`） | 「装上了」 |
| 若 `observed: none` | `expected_divergence_step=tool` + observed none → **一等结论** | 「装了没用」：dataset 已注册但检索计划不选它 → 升格检索计划层，与 §P2-D5 合并归因 |
| 机器判分 | D6 rate 0.0 → **≥0.5**（按 machine-truth 判分器对该 case 的 checks 复打） | 产品面收口 |
| 报告 | `validate-report.sh` RC:0；结论**携带 revision 条件**（对哪棵树成立） | 收据卫生 |

## §P1 · claude-console ↔ L1 九步双向映射表（一次性成本，之后所有跨臂 M2 复用）

**事实**：`docs/trace-profile.md` §6 投影表现有 source kind 只有 `workbench-trace` / `codex-rollout` /
`codex-exec` / `runtime-benchmark` 四类 [实测]，react 臂 session.json 无从投影。
SKILL.md 第 139 行：被审系统已有自己的步骤词表时，**必须先出双向映射表并显式声明损耗，不得静默压缩**——
「静默压缩会让 `first_divergence_step` 失去行为含义而不报错」。

**session.json 形状**（[实测] D2 样本）：顶层 `case_id / question / as_of / required_outputs /
allowed_capabilities / authorized_tools / code_root` + `calls[]`（`step_id / tool / arguments /
elapsed_seconds / called_at / error`）+ `answer / answer_sha256 / finished_at / tool_call_count`。

**映射草案**（落 `docs/trace-profile.md` §6 新增 source kind `claude-console-session`，provenance 全部 `normalized`）：

| L1 step | 投影来源 | 损耗声明 |
|---|---|---|
| `configure` | 顶层 `allowed_capabilities` / `authorized_tools` / `code_root` / `as_of`（装配合同地标） | 无 system prompt 正文（刻意） |
| `intent` | `question` + `required_outputs` | — |
| `plan` | **不可表达**：ReAct 驱动器不落决策事件 | 必须显式声明，见下 |
| `route` | **结构性不存在**（单引擎、无 skill 分派）——同 codex `route` 先例（trace-profile §8「结构性差异非缺口」） | 不造事件凑指标 |
| `tool` | `calls[].tool` + `arguments`（原生序列） | — |
| `observe` | `calls[].elapsed_seconds` + `error` | **只有存在性证据、无内容证据**（无原始返回载荷）；`error=None` ≠ 结果可用 |
| `synthesize` | `answer`（终态） | 无中间稿 |
| `stop` | `finished_at` + `answer_sha256` | — |

**门槛核算**：`configure → intent → plan` 三步两侧非空是 M2 前缀可比的门槛（workbench/codex 现为 3/3）；
claude-console 侧 `plan` 结构性缺失 → 只有 2/3。处置分两档：

- **档 A（纯文档，本单交付）**：映射表落 §6；`plan` 的压缩按 skill 139 条写成 `residual_uncertainty`
  并连到报告的 Observability prescription，不硬造事件。
- **档 B（下轮实验生效）**：react 驱动器（`~/.finance-runtime/four-arm-20260827/scripts/`）补一条 plan 地标
  （记 step 预算 + 工具白名单决策，与 codex 侧 `context.policy` 投影同义）。只改实验驱动器，不改生产。

**验收**：用映射表对 D2 双侧 trace 出一份 M2 报告，`validate-report.sh` RC:0，
且 `residual_uncertainty` 段含 `plan`（不可表达）与 `observe`（无内容证据）两条损耗。

## §P2 · D2 / D5 跨臂假设生成 + 自对照确认

### D2（假设：掉在判官层，不是作答层——8792 的答案可能本来够好，是被扣住的）

1. 跨臂 M2（依赖 §P1 档 A）：预期 8792 侧 `first_failure_step` 落在 `synthesize` 之后的核验段而非 retrieve/tool 前缀。
   **拿到 trace 才能定，本单不预设结论**——若 M2 发现前缀就分叉，`R-20260827-08` 按 refuted 处理并重立。
2. 修复 = 合并 `fix/range-cutoff-and-judge-fallback`（`b614daf0`，含 TDD 钉与「单前导日期不被区间守卫吞掉」反向锁），
   走正常 PR 流程（CI 绿才可合）。该修复**只把 grok CLI 瞬时故障放回重试档**（MAX_SEMANTIC_JUDGE_ATTEMPTS=3 本来就在），
   「未经复核的草稿不出稿」红线不动。
3. 自对照确认（合并 + 切流后同题复跑）：`judge_status ≠ unavailable`、`verified_status=verified`、
   D2 rate 0.25 → **≥0.75**；生产面下一个 38-run 等宽窗口 `judge_unavailable ≤ 3/38`（当前 8/38）。
4. **搭车判据**：`b614daf0` 同时修 D10 的区间截止日（缺陷 D-1）→ 合并后
   `requested_information_cutoff`（区间题）取**终点**、D10 复跑 rate > 0（当前三臂 0.0）。

### D5（假设：检索计划少一跳——缺题材 → 实体解析）

1. 跨臂 M2（依赖 §P1）：8792 `run_20260827_134712_662543` 的 `continuous-episode.json` research 载荷
   vs react calls 序列按映射表对齐，确认 8792 是否**从未发出** graph_lookup / 实体解析类查询。
2. 若确认 → 修复属检索计划层（`retrieval_planner` / `research_plan` 一族；fix_type 待 M2 定层后修正）。
   **本单不预写修法**——没有分叉证据不猜层（§1 第 1 条）。
3. 自对照复跑：D5 rate 0.0 → 按 machine-truth 该 case checks 复打 **≥2/3**。

## §P3 · 闭环：三行预注册（已随本单落账）

`R-20260827-07a`（D6 复跑，原号 `-07` 撞号改号）/ `-08`（D2 判官）/ `-09`（D5 检索跳）已写入 `docs/prediction-ledger.md` Open 表，
`verification_prediction` 与失败形状**预先写死**（预注册先于执行，防「先看结果再写预测」）。

为什么这步不能省：账本住址必须固定（SKILL.md 第 152 行）——「若 A harness 把结论留在自己的报告里、
B harness 下次去别处找 pending，闭环就断了而且不报错」。本次四臂的全部发现留在 `~/.finance-runtime/`，
`docs/` 里零字提及，正是这个失败形状的现场。升格线（同类 fix_type 连续 ≥3 次 refuted → 质疑 HARNESS 架构层）
靠账本累计 streak；不进账本，streak 永远攒不出来，「问题不在你以为的那层」的报警机制不会响。

## §5 · 非目标

- component 臂 0.111 的归因——能力开关板是消融 runner 专用登记表，「生产不读本表」，它登记单变量消融、不做差分。
- D9 判分器三臂全 None——判分侧缺口（与 defects-found.md 附录同族），不阻塞本单，可另立 EVAL_ONLY 单。
- 模型 / SDK 胜负结论——模型是混杂变量（§1 第 2 条），本单只修 harness 层。
- 「未经复核的草稿不出稿」红线——不动（`b614daf0` 同款边界）。
- 缺陷 D-2（华工科技价格链断裂 / 缺交易日）、D-3（auction 连板数开盘前口径未标注）、
  D-5（graph_lookup 对不存在实体子串模糊匹配、gaps 不置位）——独立数据/工具缺陷，已在
  `analysis/defects-found.md` 留档，各自另立单，不搭本车。

## §6 · 执行顺序与依赖

```
0. 预注册三行（本单已完成）
1. §P0  D6 复跑 + 自对照 M2          ← 无依赖，最便宜，今天可做
2. §P1  映射表档 A（纯文档）          ← D2/D5 跨臂 M2 的前置
3. §P2  D2：跨臂 M2 → 合 b614daf0 → 切流 → 复跑确认（顺带 D10）
4. §P2  D5：跨臂 M2 → 定层 → 设计 → 实施 → 复跑确认
5. 回填账本三行 outcome（confirmed / refuted，refuted 不粉饰成 pending）
```
