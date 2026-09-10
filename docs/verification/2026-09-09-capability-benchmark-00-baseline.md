# 能力基线 00：30 题真实工作基线（2026-09-09 ～ 2026-09-10）

## 结论速览

- **30/30 题状态定型**：28 completed + 2 engine_missing（cb00-chain-01/02，路由层缺陷 B7，如实记录不计能力分）；**0 quota_tainted、0 skipped_cooldown、0 判官真坏**（质量闸门 rc=0）。
- 终件：`intelligence/eval/runs/20260910T105119Z-cb00-baseline-372d047c0b0f.json`（运行时原件 `~/.finance-runtime/capability-benchmark-00/runs/` 同名文件，本文以仓内件为准）。
- 评审包（含反向验证 decoy）：`~/.finance-runtime/capability-benchmark-00/review-pack-20260910/`，30 份匿名 sheet + `mapping.sealed.json`（评审禁止打开）+ 6 题双评名单。**人工评审（含 ≥20% 双评）尚未进行**——单臂基线无对照臂，评审/aggregate 待对比臂（升级后同题集重跑）产生后一并进行。

## 测量条件（成立条件）

| 项 | 值 |
|---|---|
| 被测 revision | sidecar 冻结快照 `cdb16985`（09-09 晚 25 题段为 `372d047c`；两 revision 间 diff 只含评测侧 runner/docs/tests，被测 runtime 零改动，故同臂 `baseline-372d047c0b0f`） |
| 基线 | `gitea/main@5eb24515` |
| 入口 | `POST /api/conversations` → `POST /api/conversations/{id}/messages`（skill_mode=auto，真实对话门） |
| 模型 | gpt-5.6-sol（69 turn）/ gpt-5.6-terra（19 turn），provider 链主备 |
| 模型出口 | **混合**：09-09 晚 25 题走 Mirasim 8080；09-10 白天 5 题走 Cockpit 57244（8080 整夜 502/503 未愈，按用户 kick 切换，见 blocked B8） |
| 判官 | grok-4.6（grok-cli）；**偏离生产 env 两点**：`LLM_JUDGE_GROK_BIN=~/.grok/bin/grok`（launcher 钉的 1.0.5 被自动更新清掉，B5）、`LLM_JUDGE_GROK_SANDBOX=off` |
| 数据截止 | market_data_date=2026-09-09；题集 as_of=2026-09-07 |
| 已知数据态 | 09-09 段 readiness `market_data_consistency=false`（快照 09-08 领先库 09-07，B2，生产同态） |
| 费用口径 | 只记 token：输入 4,237,478 / 输出 120,594（仓内无 cost 埋点） |
| 耗时 | 总 5,354.6s；中位单题 148.0s |

## 主表（逐题状态）

结构/语义列：`completed` > `partial` > `failed`（None = 未产生 episode）。判官列：`passed/repaired/unavailable`（unavailable 且 exc_class=None = 按证据边界的合规降级，非判官故障；5 道，均经 episode 实证）。

| 题 | 类别 | 执行 | 结构 | 语义 | 判官 | stop | 耗时s | 无效动作 |
|---|---|---|---|---|---|---|---|---|
| feel-01 | 盘感翻译 | completed | partial | completed | repaired | model_finish | 82 | 0 |
| feel-02 | 盘感翻译 | completed | completed | completed | repaired | model_finish | 151 | 0 |
| material-01 | 材料理解 | completed | partial | partial | unavailable | invalid_repair_finish | 49 | 0 |
| material-02 | 材料理解 | completed | partial | partial | unavailable | invalid_repair_finish | 26 | 0 |
| calc-01 | 财务计算 | completed | partial | partial | unavailable | invalid_repair_finish | 40 | 0 |
| calc-02 | 财务计算 | completed | completed | completed | passed | model_finish | 89 | 0 |
| compare-01 | 跨公司比较 | completed | partial | completed | repaired | repair_model_finish | 141 | 0 |
| compare-02 | 跨公司比较 | completed | completed | completed | repaired | model_finish | 331 | 0 |
| chain-01 | 产业传导 | **engine_missing** | — | — | — | — | 3 | 0 |
| chain-02 | 产业传导 | **engine_missing** | — | — | — | — | 3 | 0 |
| analog-01 | 历史类比 | completed | partial | completed | passed | finalization_recovered | 99 | 0 |
| analog-02 | 历史类比 | completed | partial | completed | repaired | repair_model_finish | 76 | 0 |
| scenario-01 | 情景更新 | completed | partial | completed | repaired | finalization_recovered | 147 | 0 |
| scenario-02 | 情景更新 | completed | partial | completed | repaired | finalization_recovered | 304 | 1 |
| counter-01 | 反例推翻 | completed | partial | completed | repaired | model_finish | 82 | 0 |
| counter-02 | 反例推翻 | completed | completed | completed | repaired | model_finish | 102 | 0 |
| continue-01 | 跨日续研 | completed | partial | partial | passed/unavailable | repair_model_finish/invalid_model_finish | 134 | 1 |
| continue-02 | 跨日续研 | completed | partial | completed | unavailable/passed | repair_deadline_exhausted/model_finish | 252 | 0 |
| method-01 | 方法验证 | completed | partial | completed | passed | repair_model_stop | 131 | 13 |
| method-02 | 方法验证 | completed | partial | completed | repaired | model_finish | 353 | 0 |
| feel-h1 | 盘感翻译 | completed | completed | completed | repaired | model_finish | 308 | 0 |
| material-h1 | 材料理解 | completed | completed | completed | passed | model_finish | 166 | 2 |
| calc-h1 | 财务计算 | completed | completed | completed | passed | model_finish | 140 | 1 |
| compare-h1 | 跨公司比较 | completed | partial | completed | repaired | invalid_repair_finish | 472 | 0 |
| chain-h1 | 产业传导 | completed | completed | completed | passed | model_finish | 219 | 5 |
| analog-h1 | 历史类比 | completed | partial | completed | repaired | model_finish | 362 | 0 |
| scenario-h1 | 情景更新 | completed | completed | completed | passed | model_finish | 213 | 0 |
| counter-h1 | 反例推翻 | completed | partial | completed | repaired | model_finish | 417 | 2 |
| continue-h1 | 跨日续研 | completed | completed | completed | passed/passed | model_finish/model_finish | 239 | 0 |
| method-h1 | 方法验证 | completed | completed | completed | passed | model_finish | 151 | 0 |

汇总：结构 completed 12 / partial 18 / failed 1（continue-01 第二轮 invalid_model_finish）/ 无 episode 2；语义 completed 25 / partial 5 / failed 1 / 无 episode 2。隐藏题（h1）整体强于公开题——10 道 h1 里 8 道结构 completed，全部语义 completed。

## 附录：失败与边界

- **engine_missing ×2（chain-01/02）**：确定性路由把题面内回指「这条链」误判为跨轮追问（`classify_reference` 正则无前文也触发），新会话无可继承主体 → clarify → 引擎 A 不接手（`llm.used=false`，3s 返回）。B7 已立案，**修复留后续单**（本单不改被测系统，改了换臂混读数）。产业传导类公开题因此无量，只有 chain-h1 一道有效读数。
- **合规降级 ×5**（material-01/02、calc-01、continue-01、continue-02）：episode 走完修复轮后按证据边界收尾（`invalid_repair_finish` / `repair_deadline_exhausted`），判官 `exc_class=None` 实证判官在岗——这是**干净的能力读数**（答案是降级模板形态，评审按内容判分），与 B5 的判官真坏（exc_class 非 None）严格区分。
- **method-01 六轮才干净**：09-10 白天在 57244 上前 5 轮全部死在 finalization 阶段的 LLM 出口故障（503/429/400 各轮不同），episode `exc_class=None`，全是出口不稳非能力问题；第 6 轮（18:51）judge=passed 干净完成。**15:36 与 17:28 两个 2×200 窗口在题中转 503/400，间歇稳态下「探针放行 ≠ 题中不烧」由 runner 的题中烧穿打标兜底，未污染终件。**
- **invalid_actions=25**：method-01 独占 13（修复轮反复尝试被拒），scenario-02/continue-01/material-h1/calc-h1/chain-h1/counter-h1 各 1–5。

## 过程与机制验证（为什么这批读数可信）

1. **B4 机制两轮实证**：冷却下不跑题（探不通即 rc=4 中止）、题中烧穿打 `quota_tainted` 待重跑、`--resume` 只搬干净题。09-09 晚 8080 间歇窗口抢出 25 题；09-10 白天 57244 上 round4 探针拦下 terra 429（reset=7585s）零污染、round2 烧穿 3 题打标后 round3 全部洗净。终件 0 tainted 是机制筛出来的，不是运气好。
2. **B5 判官修复实证**：grok 二进制换 `~/.grok/bin/grok` 符号链接后，19 个 episode 判官 exc_class=None、verdict 完整（feel-01/02 等）。
3. **反向验证 decoy 已入包**：cb00-calc-01 第三份匿名答案 = 文风流畅、结构完整、每步带算式，但**单季营收还原用错减数**（2026Q2 = 中报 − **2025**一季报 = 265.95 亿，正确应减 2026 一季报得 192.71 亿），同比 +145.1%、净利率 4.11%、环比 −2.92pp 全跟着错；仅 (4) 全年三档碰巧正确。评审若让 decoy 胜出，`aggregate` 返回 rc=3，证明评审被流畅度带偏。
   > 教训（已兑现）：第一版 decoy 落盘后逐数核对发现「错得不够」——单季数全对，等于放了份正确参照。**decoy 必须经独立核算后再入包**；本版（350.14−84.19 张冠李戴）已经过二次核算确认错误链完整。
4. **混合出口注明**：本批 25 题（8080）+ 5 题（57244）跨两个模型出口，同被测 revision、同 provider 链语义。served_models 收据逐 turn 落盘可逐题溯源。

## 限制（不宣称）

- 单跑 30 题**不做显著性宣称**（分辨 5pp 需 30×15 样本）。
- 无同题 Knevo 样本，**不报竞品胜负**；旧对比只作失败样本。
- 单臂基线无对照：主表胜负列留待升级后同题集重跑出对比臂，评审与 aggregate 一并进行。
- chain/continue 类公开题覆盖受 B7 路由缺陷压缩（chain 仅 h1 一道有效）。

## 复现

```bash
# 终件已在仓内，以下命令可重新生成评审包（decoy 答案文件不在仓内，按需重造）
python3 -m intelligence.eval.capability_benchmark review-pack \
  --artifact intelligence/eval/runs/20260910T105119Z-cb00-baseline-372d047c0b0f.json \
  --output-dir <dir> --seed cb00-baseline-20260909 \
  --sealed-dir ~/capability-benchmark-00-sealed-20260909 \
  --decoy-case cb00-calc-01 --decoy-answer-file <decoy.md>
# 评审填分后：
python3 -m intelligence.eval.capability_benchmark aggregate \
  --review-dir <dir> --artifact <终件> --output <out.json>   # decoy 胜则 rc=3
```
