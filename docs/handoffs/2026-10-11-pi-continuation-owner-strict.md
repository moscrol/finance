# 2026-10-11 Pi 续写锁严格语义接续

## 背景与范围

接续用户移交的会话。工作树 `fwp-wt-arena-session-takeover-1009`，分支 `codex/arena-session-takeover-1009`。开工时树干净，`cc3828690` 已摘为 `beb1b929d`，不重复摘取。A 线 `b61a9a54e` 的 `finance-mode.ts` 已拒绝任何既存续写持有者，B 线尚允许同名 `reviewed-history` 再次安装。

本轮产品提交 `31ad7df7981c783a8b8482ac15b75525c5c504bd`。只统一 history 侧占锁语义、增加离线测试和入口说明，不改变金融审核算法、预算或默认配置。

## 现场核对与更正

- 用户移交已更正：七份数据库是 APFS 克隆，不能把逻辑大小相加称为额外占盘 27 GB；本轮没有删除数据库或测量物理回收量。
- PID 45955 是 B 有意保留的预览，不是占用默认前端门禁端口的遗留进程；门禁默认端口为 18981/18984。移交所述风险是预览读取会被 E2E 改写的夹具目录、后端仍为旧 `181f3c4c9`、当时 17.5 小时无访问，而非默认端口冲突。
- 停预览的动作属于前会话。本轮只读复核 PID 45955 不存在、18997 无监听；不恢复或再清理服务。旧日期快照中“可保留预览”的描述不是当前运行状态。
- 旧 B 会话无继续执行迹象，本树无其他改动；00:18 CST 已看到发布会话接续第二批。故仅运行低优先级串行短回归，不启动全仓、前端、E2E 门禁或真实模型请求，不操作 8792。

## 按发现顺序

1. 回读 Pi 0.87.1 文档和源码：`AgentSession.reload()` 先发 `session_shutdown(reason=reload)` 再重载资源；`AgentSessionRuntime.newSession()/switchSession()` 先 teardown 旧会话，再创建运行时。
2. 新增真实 Pi CLI 的 reload/new/resume 测试：shutdown 回调观察到续写锁已释放，切换后的正常题目仍产生 `revision_required -> reviewed` 两份回执和恰好一次修订。
3. 首个重复入口测试先被 Pi 自带的重复工具名检查拦住，不能证明占锁逻辑有效。改为第二入口只再次调用 `installHistoryReview`，避开路径去重和工具名去重；旧实现退出 0，拒绝断言失败，确证同名锁漏洞。
4. 把占锁判定从“已有且不同名”改为“已有就拒绝”；保留 shutdown 释放、仅复核 `maxRepairs: 0` 不占锁。重复加载反例转绿，README 同步合同。
5. 提交代码后，在固定干净 `31ad7df79` 上复跑定向回归并核对收据。

## 方案取舍

| 方案 | 评价 | 结果 |
|---|---|---|
| 任何既存 owner 都拒绝 | 同名不代表同一实例；生命周期先释放旧锁，正常重载无需豁免 | 采用，与 A 线一致 |
| 同名放行 | 第二份复核回调可独立持有修订计数，绕过互斥 | 否决，原实现反例已复现 |
| 依赖 Pi 路径或工具名去重 | 包装入口可只重复安装复核回调，未覆盖占锁本身 | 不作为锁的替代或反例证据 |
| 新增通用锁框架或进程外文件锁 | 当前互斥范围仅为同一 Pi 进程，现有共享 Symbol 足够 | 不扩大实现范围 |

## 验证与收据

- 旧判定的有效反例：`test_revision_loop_refuses_duplicate_adapter_load`，1 failed；收据 `~/.finance-runtime/test-receipts/20261010T162135Z-beb1b929-c1a05fc67b85.json`，开发中脏树，不冒充提交验收。
- 固定干净 `31ad7df79`：四个文件 `test_history_review_transport.py`、`test_history_answer_review.py`、`test_pi_history_review.py`、`test_pi_history_bridge.py`，**74 passed / 0 failed / 0 skipped**，20.64 秒。
- 最终定向收据：`~/.finance-runtime/test-receipts/20261010T162346Z-31ad7df7-4daf52ca44b5.json`；`check_test_receipt.py --expect-revision 31ad7df79 --require-target intelligence/tests/test_pi_history_review.py` exit 0，解释器、依赖、净树、收集 74 与执行 74 一致。这不是全仓收据。
- 真实 Pi 版本 0.87.1；新增 4 项覆盖重复安装和三种生命周期切换。既有异名占锁拒绝、仅复核不占锁、取消、新题和有限修订回归均通过。
- TypeScript strict/noEmit 通过，沿用私有根 `river-review-implementation-20261010/tsconfig.json` 对本树四个 TypeScript 文件检查；Ruff、`git diff --check` 及提交时适用检查通过。
- 未运行新提交的全仓 Python、前端/E2E、GitHub CI 或真实模型。旧 `a6bbe24f1` 完整工程收据不移签本提交；原金融质量 NOT_PASSED 不翻案。

## 接续与边界

本轮提交未推送、未合并、未部署，未改全局 Pi 设置或生产数据。后续需要发布时，先与发布 owner 协调验证窗口，再为实际候选补齐门禁；不要因锁修好就启用实验审核作为默认金融放行门。

旧审核路线的最终状态已回读 `~/.finance-runtime/river-review-implementation-20261010/completion.json` 和 `RESULT.md`：`ENGINEERING_PASS_REVIEWER_NOT_ACCEPTED`。它不再是待收尾的后台任务；是否继续语义复核、正文命题绑定由三线协调后决定，本轮不另建判官。

工具沉淀：未新增通用排查脚本，持久防线直接落在现有真实 Pi 测试套件；关键是反例必须越过前置去重，触达本次修改的锁判据。新增通用框架对本单没有收益。
