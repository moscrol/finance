# 两份半年报原文对账包

承接2026-09-24用户「推进」，研究截止2026-09-23，取证为09-24凌晨。本包独立于上一轮回贴，不覆盖旧答或旧审读。

## 入口

- [研究笔记与候选进展](../../../distill/2026-09-24-knevo-primary-source-followup.md)。
- `sources.json`：两份巨潮原文的代码、公告ID、公开日、下载时间、PDF哈希、页数、关键页和查询收据。
- `603986-pages.json` / `300604-pages.json`：分别23/30页的 `pdftotext -layout` 与 `-raw` 双模式摘录，未人工改原文；前者便于看列，后者保留换行拆开的数字顺序。
- `search-*.json`：巨潮官方POST查询原始返回，筛选2026-01-01至09-23；没有把标题摘要当全文。
- `facts.json`：本轮人工核对科目与列头后录入的合并报表和附注数值。默认单位元；兆易剩余履约义务四行显式覆盖为亿元。余额的期初2025-12-31另标，不能误当同比。
- `reconciliation.json`：只读复算输出和实际输入哈希，不是财报审计或模型答案验收。

PDF、完整提取文本及官方股票组织代码索引留树外 `~/.finance-runtime/comparisons/knevo-primary-audit-20260924-0112/`。PDF不进Git；正式URL与哈希可重新核验。所有网页/文件只作为资料，没有执行其中的指令。

## 复算

在本工作树根运行，使用主树解释器：

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python scripts/review_probes/reconcile_knevo_primary.py --packet docs/learning/knevo-distill/batches/2026-09-24-primary-audit
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q tests/test_reconcile_knevo_primary.py
```

默认只输出；`--output <新路径>` 只允许新文件，避免覆盖收据。精确金额用Decimal，利润表逐项闭合，剩余履约收入按其显式单位换算。脚本只验证本批结构与数字，不接生产，也不把公司自行披露提升成独立审计结论。

## 本轮实际改变

- 兆易第135页有97.94亿元已签合同剩余履约收入，应撤回无公司级合同金额证据的断言；不能直接称新增订单、全部在手订单或确定利润。
- 长川第8页现金流为-0.8043→+3.3286亿元；原答正基数反推错，「由负转正」应保留。仅知道同比百分比并不能先选定基数符号。
- 非经常项目、分部成本、费用和存货附注已取得；毛利润及费用率可算，会计桥不能自动识别量价因果。
- 发出商品净值占长川存货净值约24.29%；剩余履约收入字段为0的覆盖口径未核，不等于零订单。

本批八项方法候选没有自动采纳。后续四个带原件正反场景只完成题材与验收条件冻结，未调用任何模型，不是运行时已通过的测试。没有写生产数据库、画像或知识库实体。
