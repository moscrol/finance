# 2026-09-22 严格截止与本地快照续验

## 背景

本轮承接 `53054bfd4336bebd0d570273a58e92758fb623be`。目标是修正“来源日期不一致就降级/拒答”：按来源真实日期交付事实，未知不猜、NULL不补0；用户历史截止由系统强制，`local_only`只能读取已有本地行情快照，不得借综合 `market_data` 放开联网能力。

结论仍是 **AUTHOR_TARGETED_CHECKS_PASSED_ACCEPTANCE_BLOCKED**。完整工程门禁已通过，但独立 Spec/Quality 审查因账号 usage limit 无正式结论，故不能启动新 K3；上轮真实 Workbench 仍为 `AUTHOR_REAL_ENTRYPOINT_OBSERVED_NOT_ACCEPTED`。本轮无补采、回填、生产写库、8792访问、push、PR、合main或部署。候选工作树只新增本轮证据/交接文档，源码 SHA/tree 未漂移。

## 本轮发现与决定

1. 等待其他 pytest 释放资源后，固定候选在准入时有 61,196,931,072 字节空闲、无其他 pytest；完整 Python 用规定解释器实际执行，不再沿用旧“磁盘不足未启动”状态。
2. `12594 passed, 87 skipped, 2 xfailed, 17 warnings`，Ruff 0，JUnit、精确收据和运行器计数一致；候选前后 SHA/tree/status 不变。
3. 原 24 项变异均捕获。授权附加测试分账：只撤装配层 guard 时 1P/1P，最终授权过滤仍在；同时撤装配层和最终过滤时 1P/1F、0 errors，被捕获。不能把单层存活虚报成漏洞，也不能与 24 项相加成一个“总通过率”。
4. 外部审查的首次尝试和 2026-09-22 05:08Z 的 retry-01 均因账号 usage limit 退出且无 verdict，不是审查通过；不绕过准入，不复用旧 K3 runner，也不切换账号/模型。前一轮完整门禁的两失败已分别归因：开关板漏登记已由本候选修正；结构探针失败由隔离 PATH 漏掉实际 `uvx`，同SHA/同索引对照复现。
5. 敏感模式扫描保留原始命中，184 个位置、27 个唯一值全部按测试夹具、JUnit 测试名或源码模块标识符逐条归类；未知命中会使归档失败。外部验证目录整体 Ruff 命中历史 fixture 裸文本 `来源可追溯`，不扩大为候选仓库失败。

## 收据

- Python：`~/.finance-runtime/reviews/market-cutoff-snapshot-53054bfd4-20260922/python/run.json`，精确收据 `20260921T185949Z-53054bfd.json`，SHA256 `c340686b32bd79a7b01d6226cd607a924d098d430ecad30935bbc705e1d65da1`。
- 归档：`docs/verification/2026-09-22-market-cutoff-followup/`，包含 4cf 失败、53054 完整结果、变异、环境对照、两轮审查不可用原件和敏感复核；retry-01 位于 `raw/53054bfd4/independent-retry-01/`。完整性须以提交后的 `scripts/check_evidence_archive.py` 验证；不要只看本地哈希。
- 旧 `docs/verification/2026-09-22-market-cutoff-snapshot`、旧 K3 和旧 advisory 包不移签、不重写。

## 后续

新归档的 Git blob/原件字节、三旧包、共享记忆和最终工作树均已核验。2026-09-22 03:43 CST 的首次正式重试和 05:08Z（13:08 CST）的 retry-01 均为 Spec/Quality exit 1、无 verdict，Codex 明确报账号 usage limit；retry-01 提示 try again at 4:40 PM（CLI 未标时区）。本轮不再重试、不换账号/模型、不绕过账号/计费限制。待额度真正可用、独立审查完成且主线组合核对完成后，才把新 K3 runner 重新绑定到准确 SHA，经真实 `/api/conversations` 与 messages 跑两道原题；以 `run_id` 终态和 `assistant_message_id` 取正文，核截止合同、快照日期、引用、公开稿和 GLM 判官。completed 不等于质量通过，N=1 不证明改善率。

## 明确未验证

有限日期语法不是完整 NLU/PIT；市场题误路由 `company/stock_deep_dive` 未修。后来 main 组合、真实浏览器业务、自然夜跑、生产效果和新 K3 均未验证。`market-cutoff-snapshot-k3-20260922/run_live.py` 仍是旧身份副本，禁止直接执行。
