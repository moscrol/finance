# 在途 · fix/8792-boundary-ttl-baseline-0922 · 结论有效期自相矛盾 + 比较基线不存在

## 这个分支做什么
接 8792 边界组合候选剩下的两条真缺口（选期、用户截止已由 R5/R6 承接并前向整合到 #835，不重修）：

1. **同一条结论被标注两个有效期**。F1 原件正文写「复核期限：2026-10-22」（那其实是用户指定的复查日），同一条结论尾句又写「本结论30天内（至2026-10-17）未复核即视为待复核」。`parse_valid_until` 只 `search` 取首个匹配，散文体那个日期根本不在正则里，于是矛盾静默通过。
2. **触发条件依赖一个本轮没取到的历史基线**。阳性原件自述「经营现金流净额两期均未取得……净现比不可算」，触发条件却是「净现比……不低于两期中较低值」——到复查日无从比较，看着可证伪，实际不可证伪。结构门只看形状齐不齐，`registerable=true`、`watch_missing=[]`。

## 基线与血统
从 `d82cb16b5`（#835 财务前向整合头）拉新分支，**不在 #835 头上追加提交**——那个 SHA 是已冻结的审阅对象。本分支因此同样**未进 main**，合并前须重验。

## 决策与被否方案
- **不改 `parse_valid_until` 的取值**：改首个匹配的选取规则会连带改 `ttl_status` / `annotate_expired_conclusions` 的行为面。缺的是「没人查冲突」，不是「取错了日期」，所以新增独立信号。
- **不把全文日期拉平**：契约本来就允许每条结论各标有效期（跟踪级 30 天 / 框架级 90 天），披露截止日、复查进度日、下期关注时间节点都是**别的角色**。只认自指「本/该结论……至 YYYY-MM-DD……未复核」的重述，且仅当它与**所有**已声明期限都不一致时报冲突。
- **缺基线走补数、不走删句子**：否了接进 `_financial_claim_mismatch_indexes`（那条路是句子级删改，触碰 V8 删除权合同）；选 `_issue_backfill_plan` 复用 `NUMERIC_UNSUPPORTED` → 主体锚定的 `finance_query` 去把历史读数补回来。缺数的正确答案是补数，不是把话删干净。
- **带数值的比较不重复管**：`不低于上期0.5` 这类由既有数量支持门处理，本检查只管「连基准值都不存在」。
- **不改 `test_adapter_backfill_plan_uses_outcome_events` 的被测意图**：它用极简替身测事件互斥，已 patch 掉另一道门；新门同样 patch。否了把生产代码改成 `getattr` 容错——那是用宽容掩盖类型契约。

## 当前状态
- 改动：`track_contract.conclusion_ttl_conflicts()` + 收据新字段 `ttl_conflicts`；`financial_claim_checks.comparison_baseline_gaps()`；`episode_semantic_verifier.comparison_baseline_unsupported()`；两处接线在 `continuous_turn_adapter`（`_track_public_delivery` 只披露不改写、`_issue_backfill_plan` 走补数）。
- 新回归 `intelligence/tests/test_boundary_ttl_and_baseline.py`（23 条），题面逐字取自 R3 封存原件。
- **未 push、未开 PR、未合 main、未部署**。

## 已验证
- 先红后绿：15 条新测试全红（真实断言失败、0 收集错误）→ 实现后全绿。
- **突变验证 7/7 全被打红**，跑完按 sha256 校验源码已还原：冲突检查失效、不再比对已声明期限、收据不暴露冲突、基线缺口失效、带数值条件不跳过、只认 OCF 半边输入、不限主体。
- 反例同样来自原件：F1 的「回到2025年报1.009的水平」有基线值、两条不同结论各标期限、披露截止日 10-31 —— 都**不得**被判为缺陷。
- 全量：首轮 13329 passed / **1 failed**（新门撞上极简替身，已按上面的方式修）→ 终轮 **13330 passed / 85 skipped / 2 xfailed、exit 0、26:17**（`~/.finance-runtime/reviews/8792-ttl-baseline-20260922/full-suite-final.log`）。ruff 干净。

## 未验证 / 已知边界
- **无真实模型验收**。R3 固定 `c481272e` 与 R6 固定 `dfd7b4ff` 的四题仍各 0/4，本轮不倒签、不据此改判。这两条检查能否改善整题质量**未经证明**。
- 冲突检查只认**自指本结论**的重述形式；跨句指代（「该同一条结论……」）不认，本仓不做通用指代解析。
- 基线检查只覆盖净现比一族（需 `ocf_cum_yi` + `net_profit_cum_yi`）与「两期/上期/同期」量词；别的指标族、别的比较措辞会漏。
- `comparison_baseline_unsupported` 会多触发一次补数回合（有 mutex 与能力限流），**真实成本未测**。
- TTL 冲突会把该轮 status 降为 partial（notices 非空即降级），真实语料上的误判率未测。

## 下一步
1. 用户授权后开 PR（目标：叠在 #835 之上，或 #835 合入后重基）。
2. 真实模型验收要另行授权；验收前不得声称 8792 边界任务收口。
3. 若扩指标族/措辞，先补原件正反例再动正则——本轮所有题面均有封存出处。

## 踩过的坑
- 突变脚本的锚点必须唯一：`return tuple(dict.fromkeys(gaps))` 在同一文件出现两次，`dict.fromkeys` 这种成语在本仓到处都是，务必带上下文。
- 全量约 38 分钟，容易被中断；后台 `nohup` + `.exit` 落盘再轮询。
