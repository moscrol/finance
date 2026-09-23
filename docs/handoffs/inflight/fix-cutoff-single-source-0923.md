# 信息截止日单一解析器 + 变异报告 suite 标签（#863 独立审查 F1 / F2 跟进）

## 这个分支做什么
#863 合入后，合前独立审查留下两条发现，本分支从 #863 合并提交 `8e7989372` 开出来修：
- **F1**：`historical_research/intent.py::explicit_information_cutoff` 自带一套截止日正则（无否定 / 日期角色 / 区间起点规则），`honesty_gates.requested_information_cutoff` 另有一套；`build_episode_context` 对两者取 `min()`。历史意图 + 否定式截止句（「不要以 2026-09-11 为信息截止日，历史上有没有类似情况」）时 Episode 截止日仍落 09-11。
- **F2**：`run_extraction_mutations.py` 在 `--tests/--definitions` 覆盖 `--suite` 时，`results.json` 的 `suite` 仍写 `extraction`。

## 决策与被否方案
- 单一真相放在 `honesty_gates`：新增 `explicit_information_cutoff_dates(query)`（分区 + 三条规则后的候选日期，非法历法保留 `None`），`_explicit_information_date` 与 `intent.explicit_information_cutoff` 都消费它；intent 保留「非法或不唯一即 `raise ValueError`」合同（→ `window_error`）。否了给 intent 正则补规则——第三份规则表下次还会漂。
- 副作用：历史意图现在也认「截至 X」「截止到 X」等形式。接受：Episode 截止日本来就按这些形式收紧。
- F2：覆盖时 `args.suite = "custom"`；不加新字段。`intent.py` 内延迟导入避免 import 环。

## 已验证
- ruff 5 文件通过；定向 8 个测试文件全绿（收据 `test-receipts/20260922T164747Z-8e798937-*.json`，窄集）。
- 新增测试（`intelligence/tests/test_research_tail_union_seams.py`）：7 组短语下历史意图 / `explicit_information_cutoff` / `requested_information_cutoff` 三者同值；冲突句历史侧 `window_error`、Episode 侧 `None`；端到端 `decide_turn → build_episode_context` 否定句截止日落运行日而非 09-11。
- 广域 `-k`（history / cutoff / asof / intent / honesty / mutation …，两个测试树）**1361P / 7S / 0F**；变异 runner 在 `b674e54b6` 上 5/5 改坏即红、还原即绿（新 `history-intent-bypasses-negated-cutoff` 红 2），`results.json` 已写 `suite=custom`。证据 `~/.finance-runtime/reviews/research-tail-union-postmerge-20260923/cutoff-mutations-b674e54b6/`，读数已贴 PR #870 评论。
- 门页 `docs/agent-product-door.md`「联合候选的接缝」补一句单一解析器。

## 未验证 / 边界
- 未跑全量四叶（磁盘 < 12 GiB，准入不放行）；合并前必须补，收据 revision 须等于分支尖。
- 历史线真实四题、财务 R6 四题未跑（#76）。

## 下一步
1. PR #870 已开并 WIP 守卫。磁盘恢复后跑四叶（python 叶可复用 `research-tail-union-postmerge-20260923/run_main_tip_python_leaf.py` 的准入模式，换成本分支尖的检出）。
2. 四叶绿 + 用户确认后合入；本分支自四叶起不再追加提交。
