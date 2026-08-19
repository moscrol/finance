# #224 门禁放行 live 对照（2026-08-19，生产 8792）

> 派单轨道 A：`docs/handoffs/2026-08-19-depth-gap-execution-dispatch.md`  
> 清单真本源：`docs/handoffs/inflight/fix-gate-partial-release.md`「下一步」  
> 生产：`:8792`，`source_revision=441c60f27cc2` / `source_dirty=false` / `code_matches_repo=true`  
> 入口：`POST /api/conversations` → `.../messages`（`perspective_mode=single`, `selected_perspective_ids=["sptfei"]`）  
> 用户：`linxiaoqi5111`  
> `live_probe ask` **不能**带视角，本轨道按契约打生产，没用 sidecar。

## 判定

**轨道 A 主验收通过。轨道 B 可以链切。**

SPT 原题在 #224 上线后重放：公开稿放出 SPT 结构判断（量能段 / 轮动脉冲 vs 主线发育 / 次日观察 / 证伪条件），带 E 号。不再出现「现有证据不足」整篇换模板。

财务锚 live 仍 fail-closed（估值题公开稿是缺口模板）。精确文案 `missing required evidence type for financial_business_anchor` 本发没打中——模型零绑定、全槽自报 gap，走的是更前置的「无一槽 fulfilled 不放行」。契约里 `financial_business_anchor` 仍 `required=True`；单测钉住的 floor 前缀不在放行名单。

一周 telemetry 只开了 T+0 快照，不能结案。

## 题目与入口

1. **原题重放**（逐字，`run_20260819_130854_564464`）：「用SPT视角看2026-08-18的盘面数据，给出次日8月19日的看法：当前量能状态处于哪一段、8.18的板块表现该读成主线发育还是轮动脉冲、次日重点观察什么、什么条件出现就证伪」
   - `user=linxiaoqi5111`，`skill_mode=auto`，`perspective_mode=single`，`selected_perspective_ids=["sptfei"]`
   - 会话 `conv_8ccbd829d7dc4bc9a12368b9e63b2737`
2. **估值题**：「立新能源现在贵不贵，隐含了什么预期」
   - 中立泳道（不带视角），`conv_99ba24376eca47199e61e1bd8447f451`

## 验收对照

| 条 | 要求 | 读数 | 结果 |
|---|---|---|---|
| 1 | 原题 verified=completed 或 partial 放行正文 | 对外 `completed`；`research_status=partial`；公开稿 2232 字节，有基准判断 + E2/E3/E7/E12 等 | 过 |
| 2 | issues 至多剩 `stripped unsupported evidence type` | 结构核验 `completed` / issues=`[]`。语义层只剩 `semantic judge transient provider error`（R-06 既有形状，带「未完成独立复核」caveat 放行）。**零** stripped / unsupported type | 过（比预期更干净） |
| 3 | 不再出「现有证据不足」模板 | 正文无该句；旧发 `130854` 整篇是该模板（772 字节） | 过 |
| 4 | 财务锚 floor 仍 fail-closed | 估值题公开稿是缺口模板。issues=`required output reports gap:` ×5 + `missing mandatory capability evidence: market_data,financial_data`。`financial_business_anchor` 仍 required。**未**发出 `missing required evidence type for`（零绑定，floor 函数没走到） | 过（路径说明见下） |
| 5 | 视角真的进了 SPT | 公开稿抬头「当前视角：SPT-Molmansk」；不是中立泳道 | 过 |

## 相对病灶基线

| | 病灶 `130854_564464`（切前） | 重放 `152316_348138`（#224 生产） |
|---|---|---|
| 生产 revision | 切前（#224 未上） | `441c60f27cc2` |
| `prime_quote` | `required=True`，`evidence_types=["market_data"]` | `required=False`（#224 残差改可选），类型不变 |
| 结构 issues | `unsupported evidence type for prime_quote: finance_query` | `[]`，`verified_status=completed` |
| `prime_quote` 绑定 | 混绑 finance_query → 整槽作废 | 8 条，**全是** `market_data` |
| 工具 | finance_query 多次 | `market_data` + `mainline_context` + `finance_query`（finance_query 进了 invalidation/supporting，各 3 条，不进 prime_quote） |
| 证据 | — | 40 条（finance_query 25 / market_data 8 / mainline 7） |
| 公开稿 | 「现有证据不足」模板 | SPT 判断正文 + E 号；判官超时 caveat |
| 用时 | 13:08:54 → 13:09:35（41s） | 15:23:16 → 15:26:09（173s） |
| 模型 | glm-5.2 @ zhipu | glm-5.2 @ openai 适配（runtime `continuous_glm`） |

机制对齐（部署树，不是本验收树）：

- G7 剔除式：`episode_verifier` 混绑时剔非法哈希、留合法；本发 prime_quote 根本没混进 finance_query，所以连 `stripped …` 痕迹都没有。
- G11 放行名单：`stripped unsupported` / `unsupported evidence type` / 自报 gap / 强制能力未绑。本发结构层已 completed，名单没被用到。
- 判官暂态：与 15:06 长电台账同一形状（R-06），**不是 #224 回归**。

## 估值题：fail-closed 走了哪条闸

`run_20260819_152635_937314`（15:26:35 → 15:28:31，117s），`question_type=valuation_estimate`。

- 契约仍要 `financial_business_anchor`（`evidence_types=["financial_data","evidence_lookup","kb_search"]`，`required=True`）。
- 工具取到 `financial_data` ×12，但 **5 个 required 槽全部 `missing`、零绑定**。另缺 `market_data` 能力证据。
- 公开稿 = 「现有证据不足」模板。这是对的：`_can_semantically_release_partial` 要求至少一个槽 `fulfilled`，全缺则不能放行。
- **没打中** `missing required evidence type for financial_business_anchor`。那条只在「绑了哈希、kept 之后仍缺 floor 工具」时发出。本发零绑定，floor 函数没跑到。
- 因此：live 证明「估值题不能靠空绑定放行」；精确 floor 文案仍靠单测 `test_financial_floor_issue_still_fails_closed_without_judge`。不要把本发写成「floor 前缀已 live 命中」。

## T+0 telemetry（一周观察的起点，不是结案）

扫描 `users/linxiaoqi5111/runs` 今日 19 发：

| 信号 | 今日计数 | 备注 |
|---|---|---|
| `stripped unsupported evidence type` | 0 | 重放也没有 |
| `unsupported evidence type`（无 stripped 前缀） | 1 | 仅病灶旧发 `130854` |
| `missing required evidence type` | 0 | 估值题没走到这条 |
| 「现有证据不足」模板 | 3 | 旧 SPT 病灶 + 本发估值 fail-closed + 15:06 长电（R-06/发明阈值，与 #224 无关） |

**还不能决定 A3**（`finance_query` 进不进 `prime_quote` 白名单）。派单把这件事留给用户，数据口径至少再看一周。

## 产物

- SPT 重放：`~/.local/share/finance-workbench/users/linxiaoqi5111/runs/run_20260819_152316_348138/`
- 估值对照：`~/.local/share/finance-workbench/users/linxiaoqi5111/runs/run_20260819_152635_937314/`
- 病灶基线：`~/.local/share/finance-workbench/users/linxiaoqi5111/runs/run_20260819_130854_564464/`
- 压缩读数：`~/.finance-runtime/gate-partial-release-live/receipt.json`

## 给轨道 B

A 重放已完成。8792 这两发都已 `completed`，无 in-flight。链切前仍按规程确认当时没有新的在途 run（kickstart 会杀 in-flight）。
