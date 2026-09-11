# 能力基线 00-k3nj：kimi-k3 × 无独立判官对照臂（2026-09-11）

## 结论速览

- **30/30 题状态定型**：28 completed（全部真形状：served_models=kimi-k3、真工具调用、真答案）+ 2 engine_missing（cb00-chain-01/02，B7 澄清闸过触发，与 00 臂同因同状，如实记录不计能力分）；**0 quota_tainted、0 skipped_cooldown**（质量闸门 rc=2 仅为 engine_missing 两题）。
- 终件：`intelligence/eval/runs/20260910T175535Z-cb00-k3nj-c423c8bd953f.json`（运行时原件 `~/.finance-runtime/capability-benchmark-00-k3nj/runs/` 同名文件，本文以仓内件为准）。
- **用户验收（2026-09-11）**：用户抽看问答全文后判「关掉判官回答的也不错」——无独立判官臂的回答质量获用户认可（注意口径：本臂是「自审在环」不是「裸答」，见下）。
- 评审包/双评未做：00 臂的人工评审同样未做，两臂评审建议同期进行（同一评审尺度下才有对照意义）。

## 臂定义（与 00 基线臂的三处有意偏离）

| 项 | 00 基线臂 | 本臂（k3nj） |
|---|---|---|
| 模型 | gpt-5.6-sol/terra 双槽主备 | **kimi-k3 单模型双槽**（writer=builtin） |
| 判官 | grok-4.6 独立判官（grok-cli） | **无独立判官**：撤 LLM_JUDGE_*，semantic verifier 回落主模型自审，receipt `correlated_judge=True` |
| 检索语义闸 | `ASK_EVIDENCE_JUDGE=auto` | **off** |

「判官全关」在配置层不存在（verifier 在 `api/app.py` 装配层硬接线），本臂交付的是配置层最远的诚实位置——这也正是 Knevo 形态（无独立判官、主模型自审）。

## 测量条件（成立条件）

| 项 | 值 |
|---|---|
| 被测 revision | `c423c8bd953f` = 00 臂被测代码 `6bea3197` + **LLM_COMPAT_PAYLOAD shim 逐字节移植**（自 e480e6c7 快照；未设 env 零行为变化，对 gpt-5.6 惰性；provenance：372d047c→6bea3197 的 services/runtime/api 零 diff） |
| 基线 | `gitea/main@5eb24515`（同 00 臂） |
| 入口 | `POST /api/conversations` → messages（skill_mode=auto，真实对话门，同 00 臂） |
| 模型出口 | Mirasim 8080，kimi-k3；`LLM_COMPAT_PAYLOAD=kimi-k3:temperature.omit`（必需：mirasim 凭证路对 kimi-k3 的 temperature 字段一律 400，见附录） |
| 判官 | 自审（kimi-k3 审 kimi-k3），无独立判官；`ASK_EVIDENCE_JUDGE=off` |
| 数据截止 | market_data_date=2026-09-10（00 臂为 09-09；题集 as_of=2026-09-07，题目钉死「09-07 及之前」故口径可比） |
| 费用口径 | 只记 token：输入 4,931,354 / 输出 151,448（对比 00 臂 4,237,478 / 120,594） |
| 耗时 | 总 6,836s（1.9h，无冷却中断）；中位单题 208.3s（00 臂 148.0s，出口与模型不同，不读快慢） |

## 主表（逐题状态）

结构/语义列：`completed` > `partial` > `failed`。判官列=自审结果：`passed/repaired/unavailable`（unavailable 且 exc_class=None = 按证据边界/复核超时的合规降级，非判官故障，与 00 臂同口径）。

| 题 | 类别 | 执行 | 结构 | 语义 | 判官(自审) | stop | 耗时s | 无效动作 |
|---|---|---|---|---|---|---|---|---|
| feel-01 | 盘感翻译 | completed | completed | completed | repaired | model_finish | 238 | 0 |
| feel-02 | 盘感翻译 | completed | completed | completed | repaired | model_finish | 92 | 0 |
| material-01 | 材料理解 | completed | completed | completed | repaired | model_finish | 287 | 1 |
| material-02 | 材料理解 | completed | completed | completed | repaired | repair_model_finish | 195 | 0 |
| calc-01 | 财务计算 | completed | completed | completed | passed | model_finish | 80 | 0 |
| calc-02 | 财务计算 | completed | completed | completed | repaired | model_finish | 85 | 2 |
| compare-01 | 跨公司比较 | completed | completed | partial | unavailable | model_finish | 592 | 0 |
| compare-02 | 跨公司比较 | completed | completed | completed | repaired | model_finish | 327 | 1 |
| chain-01 | 产业传导 | **engine_missing** | — | — | — | — | 3 | — |
| chain-02 | 产业传导 | **engine_missing** | — | — | — | — | 3 | — |
| analog-01 | 历史类比 | completed | partial | completed | repaired | model_finish | 208 | 0 |
| analog-02 | 历史类比 | completed | partial | partial | passed | model_finish | 275 | 0 |
| scenario-01 | 情景更新 | completed | completed | completed | repaired | model_finish | 123 | 0 |
| scenario-02 | 情景更新 | completed | completed | completed | repaired | model_finish | 215 | 0 |
| counter-01 | 反例推翻 | completed | completed | completed | repaired | model_finish | 122 | 1 |
| counter-02 | 反例推翻 | completed | completed | partial | unavailable | model_finish | 201 | 0 |
| continue-01 | 跨日续研 | completed | completed/partial | completed/completed | repaired/repaired | model_finish/finalization_recovered | 192 | 1 |
| continue-02 | 跨日续研 | completed | partial/completed | completed/partial | repaired/unavailable | model_finish/model_finish | 650 | 1 |
| method-01 | 方法验证 | completed | partial | completed | repaired | model_finish | 183 | 1 |
| method-02 | 方法验证 | completed | completed | partial | unavailable | model_finish | 268 | 0 |
| feel-h1 | 盘感翻译 | completed | completed | partial | unavailable | model_finish | 315 | 1 |
| material-h1 | 材料理解 | completed | completed | completed | passed | model_finish | 139 | 1 |
| calc-h1 | 财务计算 | completed | completed | completed | repaired | model_finish | 94 | 0 |
| compare-h1 | 跨公司比较 | completed | completed | partial | unavailable | model_finish | 417 | 2 |
| chain-h1 | 产业传导 | completed | partial | completed | repaired | model_finish | 88 | 1 |
| analog-h1 | 历史类比 | completed | partial | completed | passed | model_finish | 162 | 0 |
| scenario-h1 | 情景更新 | completed | partial | completed | passed | repair_model_finish | 291 | 0 |
| counter-h1 | 反例推翻 | completed | completed | partial | unavailable | model_finish | 367 | 0 |
| continue-h1 | 跨日续研 | completed | completed/completed | completed/completed | repaired/repaired | model_finish/model_finish | 214 | 0 |
| method-h1 | 方法验证 | completed | completed | completed | repaired | model_finish | 334 | 2 |

汇总：结构 completed 24 / partial 6 / 无 episode 2；语义 completed 20 / partial 8 / 无 episode 2；自审 repaired 19 / passed 5 / unavailable 7。无效动作合计 15。

## 附录：失败与边界

- **engine_missing ×2（chain-01/02）**：与 00 臂同一病灶 B7——turn_controller 把题面内回指（「这条链」「会传导到」）误判为跨轮追问（`lane=clarify`，confidence 1.0，「没有可继承的研究主体」），澄清短路 → 无 continuous-episode.json → runner 记 engine_missing。trace 实锤见快照文档。修复方向是澄清闸对「首轮自足问题」的判别（B7 已立案，修复留后续单，本单不改被测系统）。
- **自审 unavailable ×7**（compare-01/counter-02/method-02/feel-h1/compare-h1/counter-h1 + continue-02 第二轮）：episode 全部 exc_class=None（与 00 臂合规降级同口径），答案头部自标「未完成独立复核（复核服务超时）」——自审在题尾 deadline 下没出裁决。**这 7 题读数偏弱，评审按判卷合同标明，不与 24 题完整复核混算**；unavailable 多落在重题（592s/650s/417s/367s）与隐藏题（4/7 是 h1），与题重正相关。
- **invalid_actions=15**：分散在 12 题，无单题失控（00 臂 25，其中 method-01 独占 13 是出口事故；本臂无此事故形态）。
- **misconfig 事故件 ×3**（`~/.finance-runtime/capability-benchmark-00-k3nj/runs/attic-misconfig-20260911/`）：缺 shim 的两轮「假完成」（21 题 9 分钟全降级模板），未入链，留作「探针探不出字段级 400」的实物证据。

## 过程与机制验证（为什么这批读数可信）

1. **400 墙定罪链完整**：首跑全降级 → episode 事件链每次合成调用 400 → 逐字段 curl 实测定罪**双钥双门禁**：mirasim 凭证路对 kimi-k3 的 temperature 字段一律 400（0.0 也拒，只认摘除），OPENAI key 路另拒 thinking.disabled。探针用 OPENAI key 且不带这两个字段，两种 400 都探不出——**「探针放行」先问哪把钥匙、什么字段**（00 车道地雷#1 同族）。
2. **shim 移植受控**：专用 worktree（不动 8813 在服的共享 00 树），逐字节移植 + 5 调用点核实 + 冒烟三断言（摘帽/他模型惰性/未设 env 零变化）+ llm_refine 相关 27 单测绿。
3. **preflight 四查含反向判官查**：GO 的前提是 snapshot 里 `ASK_EVIDENCE_JUDGE=off` 且无 LLM_JUDGE_* 且 shim 在——「判官关了」是被断言的事实，不是事故。
4. **真实形状抽验**：首两题 episode model_turn 全 err=None、有正文有工具调用；终件 28 题 served_models 全为 kimi-k3。

## 限制（不宣称）

- **两臂通过率不可直接比**：判官门槛不同（grok 独立判官 vs 自审 correlated），只能比形状/降级率/结构语义分布，且需人工评审同尺度下进行。
- **自审 ≠ 裸答**：repaired 19 题里有自审修稿的功劳；「完全无判官」形态本轮未测（需改装配层，不是配置能到的）。
- 单跑 30 题不做显著性宣称；无同题 Knevo 样本，不报竞品胜负。
- chain 类公开题两臂同受 B7 压缩（仅 chain-h1 一道有效读数）。

## 用户方向与后续（2026-09-11）

- 用户验收后表态：**「不用这个 LLM 判官也可以了，不然成本比较高」**，grok 充值顺延至下周三。若独立判官终弃，00 臂剩余 7 题（grok 判官臂的尾巴）价值降级为「旧生产形状存档」。
- **给这个方向标一条边界**：已验证的是「无独立判官 + 自审在环」（本臂）；「自审也撤掉」是另一个未测形态，且要动 `api/app.py` 装配层（被测代码）。生产若只撤独立判官（unset LLM_JUDGE_*），与本臂同构，有据可依；若连自审也撤，需要先补一臂验证再谈。

## 复现

```bash
# 车道运行时目录：~/.finance-runtime/capability-benchmark-00-k3nj/
bash ~/.finance-runtime/capability-benchmark-00-k3nj/start-sidecar.sh     # sidecar 8814（fwp-wt-k3nj-00）
bash ~/.finance-runtime/capability-benchmark-00-k3nj/preflight-k3nj.sh    # 四查（含反向判官查）
bash ~/.finance-runtime/capability-benchmark-00-k3nj/run-k3nj-when-gateway-up.sh
# 终件已在仓内 intelligence/eval/runs/20260910T175535Z-cb00-k3nj-c423c8bd953f.json
```
