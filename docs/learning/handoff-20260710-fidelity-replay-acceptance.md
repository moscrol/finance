# Handoff — 现状忠实度与历史重放验收

## 接手分支

- 续作分支：`eval/fidelity-replay-acceptance-v1`
- 基线：PR #189 的 head `8debd422f9650070663e6fce74c73256cec87ebc`
- 基础设施 PR：<https://github.com/linxiaoqi5111-del/finance-workspace-private/pull/189>
- PR #189 尚未合并；续作分支必须保留其双时态代码，不要从旧本地分支重新拼接。
- 本任务仍是只读评测，不写 DuckDB、飞书或知识库事实层，不恢复预测优化。

## 用户原始目标

暂停预测信号优化，建立并通过两道验收：

1. **现状忠实度测试**：抽取固定日期报告，逐条测数字一致率、实体归类准确率、证据覆盖率、截止违规率、事实/推断混淆率。
2. **历史重放测试**：使用严格 as-of 数据重放 50–100 个历史截面，与人工金标准比较事件时间线、阶段特征和因果陈述。

“完成基础设施”不等于“完成验收”。只有两道验收稳定通过后，才允许讨论预测信号。

## 已完成

PR #189 已实现：

- `intelligence/eval/bitemporal_history.py`
  - `build_final_history()`：当前最佳事实，cutoff 后获知的行标记 `ex-post`。
  - `build_as_known_at()`：只保留 `updated_at < cutoff` 的数据和 cutoff 前 Git 资料。
  - `compare_snapshots()`：final/PIT 行级与字段级对照。
  - `feature_contract_check()`：连续交易日窗口资格检查。
  - `iter_pilot_cases()`：同源配对、源库文件签名、内容哈希、分区不变量和活库变化拒绝。
  - `build_gold_standard_template()`：空白人工金标准模板。
- `scripts/bitemporal_history_eval.py`
  - `pilot`、`outcomes`、`gold-template`、`score`、`audit-ledger`。
- `intelligence/tests/test_bitemporal_history.py`
  - ex-post 标记、cutoff、物理隔离、窗口缺口、配对哈希/不可变性。
- 10 日 dry-run 报告：
  - `docs/learning/bitemporal-history-pilot-2026-07-10.md`
  - a77 产物：`/Users/a77/fidelity-replay/bitemporal-history-v1/`
- 验证：finance PR #189 的 `registry-check`、`workbench-check` 全绿；本地 `834 passed, 1 skipped`。

## 10 日 Pilot 真实结论

- final：`10/10 ready`
- PIT：`8 partial / 2 pending`
- 截止违规：`0`
- final/PIT 分区错误：`0`
- 配对哈希一致：`10/10`
- 20 日 `fact_market_daily.total_amount` 连续窗口：`0/10 eligible`

重要边界：

1. 03-06、04-23 的 PIT 为 pending。
2. 原计划作为无资料对照的 07-02、07-03 已找到 cutoff 前资料，不能再冒充 pending 对照。
3. 07-01 缺 06-03、06-18；07-02、07-03 缺 06-18，不能计算需要连续 20 日输入的规则。
4. 当前 DuckDB 主要保存最新行，没有 append-only revision log；`conflict_field_count=0` 不代表历史上没有发生字段修订。
5. Git commit timestamp 只能证明提交时间满足当前契约；若要评估“Agent 本地实际何时可访问”，还需要单独的入库/同步时间证据。

## 尚未完成：验收 A「现状忠实度」

当前只做了数据行与字段覆盖审计，**没有**把报告里的声明逐条抽取并对账。接手 session 需要建立 claim-level 评测。

### A1. 建立声明台账

建议新增：

```text
intelligence/eval/claim_fidelity.py
intelligence/tests/test_claim_fidelity.py
```

每个报告声明至少保存：

```json
{
  "claim_id": "...",
  "report_date": "YYYY-MM-DD",
  "text_span": "...",
  "claim_type": "number|entity|classification|fact|inference|forecast",
  "subject": "...",
  "predicate": "...",
  "value": null,
  "unit": null,
  "source_ref": null,
  "cutoff_timestamp": "...",
  "verification_status": "matched|mismatch|missing|unverifiable|needs_review"
}
```

LLM 可以生成候选声明，但不能直接裁决。数字、实体和 cutoff 应由确定性代码校验；模糊分类与事实/推断边界进入人工复核。

### A2. 五项指标

1. **数字一致率**：报告数字与 DuckDB/原始材料逐项比对；显式处理单位、百分比、四舍五入和容差。
2. **实体归类准确率**：公司、板块、题材、行业映射与当日有效维表/成分版本对照。
3. **证据覆盖率**：事实声明必须绑定可打开的 source ref；只有报告级引用不能算逐项覆盖。
4. **截止违规率**：任何使用 cutoff 后数据的声明都记违规；目标必须为 0。
5. **事实/推断混淆率**：把解释、因果和预测写成硬事实的比例；需要人工金标准。

先输出原始分子/分母和推荐阈值，不要擅自宣布“通过”。最终阈值需用户确认。

### A3. 固定日期报告样本

先用 10 日 pilot 对应日期，不要直接扩大：

```text
2026-03-06, 2026-04-23, 2026-06-02, 2026-06-11,
2026-06-22, 2026-06-23, 2026-06-24, 2026-07-01,
2026-07-02, 2026-07-03
```

必须先登记每一天实际要评测的 canonical 报告路径；没有报告就记 missing，不得用新生成报告替代历史原件。

## 尚未完成：验收 B「历史重放」

不要直接声称已完成 50–100 截面。先把 10 日 pilot 做成人工可裁定的闭环，再申请扩量。

### B1. 补齐双时态字段

历史事实至少区分：

```text
valid_time          事实发生/适用时间
source_published_at 来源真实发布时间
known_at            Agent 本地可访问时间
revision_at         字段或记录修订时间
```

公告、合同、研报、新闻不能只使用文件名日期或 Git commit 日期代替真实发布时间。

### B2. 处理会改变历史口径的版本

必须显式处理：

- 前复权/后复权与除权除息版本；
- 股票、指数、板块成分变更；
- 公司更名、证券代码和实体合并；
- 板块/题材分类规则变更；
- 交易日、停牌、新股上市和退市状态。

缺少版本证据就标 `pending` 或 `unverifiable`，不得拿当前成分反推历史分类。

### B3. 人工金标准

现有 `gold/*.gold.json` 是空模板，不是金标准。流程应为：

1. 代码生成候选事件与声明清单；
2. 人工核对原文、发布时间、事件顺序和事实/推断边界；
3. 记录 reviewer、reviewed_at、分歧和证据；
4. 明确批准后才标 `gold_status=approved`；
5. 评测代码不得自动修改 approved 金标准。

金标准至少覆盖：

- 事件时间线；
- 当时可见证据；
- 市场/板块阶段特征；
- 因果陈述是否有证据、是否只是候选解释；
- 替代解释和不可判定项。

### B4. 评分

建议分别报告，不要混成一个总分：

- timeline precision / recall；
- stage feature accuracy；
- causal statement supported / unsupported / unverifiable；
- PIT cutoff violations；
- missing / partial / needs_review；
- 人工 reviewer agreement。

## 执行顺序与硬门控

### Phase 1：完成 10 日验收闭环

1. 登记 10 日 canonical 报告。
2. 建 claim extractor + deterministic verifier。
3. 生成声明台账和五项指标。
4. 补 10 份 gold 候选，交人工审定。
5. 对公告发布时间、复权、成分版本做缺口审计。
6. 重跑 10 日，输出逐声明和逐日期报告。

### Gate：用户复核

必须向用户报告：

- 五项现状忠实度指标及分子/分母；
- 10 日历史重放评分；
- pending/partial/needs_review 明细；
- 推荐验收阈值；
- 哪些缺口会让扩量结果失真。

没有用户确认，不扩到 50–100 日。

### Phase 2：扩到 50–100 个历史截面

- 日期按月份、行情阶段、数据完整度分层抽样；
- 必须包含真正的无资料负对照；
- 每个截面仍使用自己的 cutoff 与版本化输入；
- 结果数据与答题输入继续物理隔离；
- 不因样本量扩大而降低金标准或证据门槛。

## 禁止事项

- 不优化预测、选股或信号参数。
- 不把 final_history 回流成 as_known_at 输入。
- 不用今天的实体/板块成分覆盖历史版本。
- 不自动生成并自我批准金标准。
- 不猜缺失字段；统一用 `pending / partial / needs_review / unverifiable`。
- 不写 DuckDB、飞书或知识库事实层。
- 不提交生成的数百 MB JSON、DuckDB 副本或任何密钥。
- 不合并 main；只提交续作 PR，等待用户确认。

## a77 执行环境

- workspace：`/Users/a77/finance-workspace-private`
- DuckDB：`/Users/a77/finance-workspace-private/db/market_feature_store.duckdb`
- PIT 产物：`/Users/a77/fidelity-replay/bitemporal-history-v1/`
- 远程执行使用已配置的 `CC_REMOTE_EXEC_TOKEN`，不要打印 token。
- 主库是活库；运行前后必须保留文件签名检查。若运行期间变化，应失败并重跑，不能接受混合版本。

## 最小测试要求

除现有测试外至少新增：

- 数字单位/百分比/容差对账；
- 实体同名、改名和代码变更；
- 报告级引用不能冒充逐声明证据覆盖；
- cutoff 后公告被拒绝；
- fact/inference 混淆被标记；
- 当前成分不能替代历史成分；
- approved gold 不可被覆盖；
- timeline 顺序错误与 unsupported causal statement 被计分；
- 无资料负对照保持 pending；
- 活库变化时生成失败。

提交前运行：

```bash
python3 -m pytest -q intelligence/tests
flake8 intelligence/eval scripts/bitemporal_history_eval.py intelligence/tests
pre-commit run --all-files
python3 scripts/build_registry.py check-parseability
python3 scripts/build_registry.py check
python3 scripts/build_registry.py backfill-tables --check
python3 scripts/build_registry.py generate-views --check
```

## 完成定义

本任务只有在下列条件同时满足时才算完成：

1. 10 日固定报告已经逐声明对账；
2. 五项现状忠实度指标可复现；
3. 10 份人工金标准已明确批准，而非空模板；
4. 事件时间线、阶段特征和因果陈述已有独立评分；
5. PIT 截止违规为 0；
6. 复权、成分变更、真实发布时间缺口已解决或明确阻断；
7. 用户批准后完成 50–100 截面扩量；
8. 两道验收达到用户确认的阈值；
9. 预测优化仍保持暂停，直到上述验收通过。
