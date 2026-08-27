# R3 · 能力对齐批次（V9b 排序 / V10 换题泛化电池 / V11 判官引导回检索设计）

- 日期：2026-08-22
- 基线：gitea/main ≥ `447fe62a`（R2 全批收口：V9a/V8 已合入并部署，生产指纹 `160db3fa`）
- 背景：R2 收口后与外部验收方 agent 的差距盘点定位出三条可关差距：
  ① top-k 槽位质量（送达带宽——V9a 只换窗内容，不管槽位分配）；
  ② 泛化验证未制度化（V9a live 是同题重放，`STRUCTURAL_SECTIONS` 黑名单归纳自长电家族页，节名变体静默不触发且 fail-open 不报错）；
  ③ 循环深度（判官发现「因果无据」只能留句打标，不能补检索——证据可能在库里没被检回）。
- 角色分离沿 R2 纪律：本文件是批次合同，不是施工 diff；实施 PR 合并需验收方复算 + 用户确认。

## 通用硬约束（三单都适用）

1. 主检出树在 `feat/reading-rules-baseline-batch1` 且脏——禁止在主树工作。从 `gitea/main` 建独立 worktree。
2. 提交一律 pathspec（禁 `git add -A`）。worktree 无 venv：symlink 主仓 `.venv-workbench`，跑测试一律用它。
3. 全量测试收据打在最终 HEAD（先提交完实现与文档，最后跑收据），`scripts/check_test_receipt.py` 必须可采信。
4. 新遥测字段/新属性必须有仓内读方（字段契约门禁拦「写了没人读」；先例：V9a 的 `pointer_dropped`/`reexcerpted` 接进 `scripts/audit_ceiling_sensors.py`，「缺字段=None 不报 0」口径不得破坏）。
5. 不碰生产 8792；不跑 live 探针；任何台账行不得由执行方标 confirmed/refuted。
6. 不改 `_repair` 函数体；不加第二修复窗；不动 `select_mode_for_remaining` 真值表与 15.0 阈值；不新增第二套降档函数；不碰 V5 `filter_structural_noise` fail-open 与 V9a `reexcerpt_hits` 既有行为（其钉保持绿）。
7. 台账行逐字抄本 spec（或对应设计文档）给出的行，不得转述。

## B1 · V9b 消费侧重排（实施单）

- 合同已在 main：`docs/superpowers/specs/2026-08-22-kb-chunk-rerank-design.md` §7.2；V9a 交付时移交的 B5③（过采样后丢结构代表块再截 k）归本单。
- 台账行已预注册：`R-20260822-02`（outcome=pending）。不需要新立案；执行方不得改 outcome，可在「怎么验」列按 R2 惯例追加离线读数。
- 判据以台账行原文为准，摘要：长电同 query 最终 top-k 中 via_neighbor 且代表段为「相关实体/相关概念」的颀中/华天/莱宝 ≤1 槽或 0；若开启 `mode=rerank`（cross-encoder）：remaining 4s 与 11.955s 零调用、20s 才允许，必须走既有 `_DENSE_MODES` 门控；变异含「rerank 移出 `_DENSE_MODES` → 红」「4s 仍打 rerank → 红」。
- 与 `-01` 的边界：不主张 #1 窗内容（已 confirmed），分表记录。

## B2 · V10 换题泛化电池（实施单）

**动机**：覆盖不足不报错是最难被探针发现的失败形状。0 档语料审计直接量出黑名单盲区；held-out 电池把验收方的临场探针变成可排程的固定评测。

**交付物**：

1. `scripts/audit_kb_section_coverage.py`：扫知识库 wiki markdown 节标题分布（`--wiki-root` 参数传入；**禁扫** `.rag_index/chunks.jsonl`）。输出：节标题出现页数排行、结构类候选（启发式写进 docstring 并有冻结小语料夹具单测）、`STRUCTURAL_SECTIONS` 覆盖率、盲区清单（JSON + 人读表）。
2. `scripts/run_probe_battery.py`：held-out 题池探针电池。base URL 必填参数、**禁默认 8792**、pytest 环境拒绝真联网（单测全 mock HTTP）。每题走 conversations API（建会话→发消息 `skill_mode:"auto"`→轮询 completed→读 run 的 `continuous-episode.json`），收 `reexcerpted` 率 / `pointer_dropped` / 正文头率（复用审计脚本的结构节启发式）/ `delivered_chars`/`detail_chars`/`hit_count`。输出 JSON 报告 + markdown 摘要。
3. 题池 `intelligence/eval/probe_pool/heldout-v1.json`：≥8 题、≥6 个不同题材，概念/个股/产业链三类问法都要有；**不得**含「长电科技怎么看」「液冷服务器产业链怎么看」及钙钛矿题（已被夹具/历史探针用过，held-out 必须避开）。题池不进任何夹具、不被任何测试 import（加静态断言钉）。
4. 台账行（逐字抄进 `docs/prediction-ledger.md` Open 表，`last_updated` 更新一句）：

| `R-20260822-04` | R3 spec §B2 换题泛化电池（黑名单覆盖审计 + held-out 探针电池） | `EVAL_ONLY` | 审计腿（可证伪预测）：全库节标题审计将发现至少 1 个出现 ≥20 页、语义上属结构节、但不在 `STRUCTURAL_SECTIONS` 的节标题变体；若未发现，记 refuted 并说明黑名单当前覆盖充分。电池腿：首轮为基线采集，held-out 题池的 reexcerpted 率/正文头率/指针丢弃分布落入报告，不预设阈值不判 pass/fail。 | 离线：审计脚本冻结语料夹具单测；电池脚本 mock HTTP 单测、禁打 8792。真跑：审计读数执行方可离线产出（写验证文档）；电池首轮归验收方（`probe-battery-<mmdd>`）。盲区清单若非空 → 黑名单扩展另立后续单，届时电池做前后对照。执行方不得自行标 confirmed/refuted。 | `pending` |

**变异击杀 ≥2**（例：结构类启发式恒 False → 覆盖率钉红；正文头判定恒 True → 报告钉红）。

## B3 · V11 判官引导的一次有界回检索（设计单，不写代码）

**动机**：差距盘点第一条。V8 探针实测三条语义 issue（散热升级因果无据等）很可能是「库里有证据没检回」而非「证据不存在」。

**交付物**：`docs/superpowers/specs/2026-08-22-v11-judge-guided-retrieval-design.md`，必须覆盖：

1. 触发分类：哪些 issue 类型触发（机械类永不触发）；触发阈值；每 episode ≤1 次。
2. 预算来源与预占：绝对 deadline 传递；从哪块 reserve；余额不足 fail-closed 回现行为；复用 `select_mode_for_remaining`，零新降档函数。
3. 管线位置：与首判/再判（monotonic rejudge、`calls==2|3` 钉）、修复窗、V8 语义标注的组合逐条对账——回检索后句子的命运（重判？保留标注？）必须给出与既有钉兼容的路径；需要重钉的逐条论证。
4. query 构造：judge issue 文本 → 检索 query 的确定性规则（不额外调 LLM 起 query，或论证为什么值得调）。
5. 遥测字段 + 仓内读方。
6. A/B 预注册草案：探针用户、分臂、n、指标——**长度守门写进合取判据**（V6 教训：完稿率 +46pp 仍因长度 −6.2% 否决）。
7. 台账行草稿（实施时逐字抄）+ 变异计划 ≥3 条。
8. 失败形状预测：至少含「回检索找到的证据稀释正确结论」「预算被回检索吃掉导致完稿率下降」两条的应对。

**硬约束**：不出代码；设计合同经验收方 + 用户确认后另派实施。

## 不在本批

- 强判官弱起草（模型分层）：等 V11 设计给出判官调用成本画像再议。
- V9c 跨仓物理重切：`R-20260822-03` 等用户裁决。
- `R-20260821-19` 机械对照半腿：自然流量续采，无需派单。

## 派单与验收

- 三单并行、独立 worktree、子代理模型按既定约定（grok 4.6 xhigh fast）。
- 验收方复算：重跑门禁、抽验 diff、变异补杀、台账逐字；实施 PR 合并需用户确认；live 探针与电池首轮归验收方。
