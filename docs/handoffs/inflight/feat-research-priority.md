# feat/research-priority · 研究进化 02 下一步研究排序

## 这个分支做什么

按 spec 02 实现 `intelligence/services/research_priority/`：只读适配 01 维护项 / 研究项目投影 / 旧研究队列 / 补数请求 → 确定性五组排序 + 同证据合并 + 分钟预算 → `research-priority/v1` 报告与不丢理由的投影。engineering_complete；接线与 product_verified 归 06。

## 决策与被否方案

- 任务 id 由合并键派生（证据版本集合；无证据则问句+范围+对象）；否了沿用来源 id——同证据新增判断时 id 会变，05 追踪断。
- 未到期条件进 blocked(not_yet_due)；否了「不生成任务」——P13 要时钟跨越后自动可选，藏掉对不了账。
- 纯重复读取不改写问句，多来源合成才加「同时影响 N 条来源」；否了一律改写——P10 重复读取的摘要会变。
- 队列「降级/观察」桶只 skip 不生成任务；否了当探索项——队列本意是减少投入。
- 日期按 UTC 日历日比较，裸 datetime 整份拒绝；否了默认当 UTC——差 8 小时且事后看不出。
展开见 `docs/handoffs/2026-09-13-research-priority-02.md`。

## 当前状态

已提交 46922d3f（代码 / 56 测试 / 6 夹具 / 证伪收据）、fb41459b（PROGRESS / BLOCKED / 最终收据）。树干净。未 push gitea、未开 PR、未合 main（等用户确认）。

## 已验证

主树 venv：`pytest -k research_priority` 56 passed；ruff 0；现役相关 7 套 98 passed；layer_audit / unread_fields / path_literals exit 0；11 道 pre-commit 全过。M1（未知耗时当 0）/ M2（hash 变化当放弃）各红 2，恢复后绿、cmp 字节一致（`plans/…/02/receipts/`）。01 在途 `assess()` 真产物零改动流过（P12）。

## 未验证 / 已知边界

- P12 的 01 产物来自 01 **未提交**在途版本 + 合成输入；01 定稿后按 BLOCKED §1 重跑替换夹具。
- 未接 API / UI / 用户态；未跑公共完整门禁与 e2e（06 在最终候选上跑）。
- user_pinned 未实现；队列 / 项目投影无 pit_grade，02 标 trade_date_only。
- 合成任务耗时取已知最大、as_of/cutoff 取最新——默认值，未经用户拍板。

## 下一步

1. 用户确认后 push gitea、开 PR；合并顺序由 06 按 01→02 依赖排。
2. 01 定稿 → 重跑 P12；06 接 `adapt_candidates` + `prioritize` + `render_view`，点击带 `click_payload`。
3. 05 按 task_id + policy_version 关联事件。

## 踩过的坑

- 现役 `build_research_queue` 把「降级/观察」算进 action 桶，summary.total 含它；写期望前先跑真函数。
- 同组按 due 早→晚：09-10 到期的 unverifiable 排在 09-11 前，不是 bug。
- 变异测试加 `-B -p no:cacheprovider` 并先删 `__pycache__`，防读旧 .pyc。
- 白名单不含 `scripts/`：收据 runner 与跨树 PYTHONPATH 探针只留在收据 / BLOCKED，未成工具；模式见 `~/agent-memory/10_knowledge/seam-test-inflight-sibling-module.md`。
