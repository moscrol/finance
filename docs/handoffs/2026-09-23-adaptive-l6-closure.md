# 2026-09-23 #76 L6 收尾与 #75 队列核对

## 背景

本快照承接同日 `adaptive-l6-preparation`。用户授权的是固定候选 `31f1b40dd788d36c71da249d59fb769c50d7cd30` 的三题各一次，先 L6 后独立 QC；不是合入授权。后续 BGE-M3 权重可离线加载，预检通过，正式执行由隔离 19897/19898 完成。没有改候选、换模型、补库或做 llm/off 对照。

## 按发现顺序

1. Q1 唯一 run `run_20260923_142128_565528` completed，但 report partial；finance_query parse_error，只有大盘 evidence。规划/终稿阶段超时后恢复出稿，实际 served model 为 `kimi-k3-eas`；repair 再次超时，无新修订稿。
2. Q2 唯一 run `run_20260923_142823_856635` 首轮与 repair 均 `LLMDeadlineExceeded`，零工具调用。按 run_failed 停批，Q3 不提交。Q2 没进查询，不能归因于库无数据。
3. Q1 逐句复核绑定原 episode SHA256；初次漏绑被审计器拒收，补齐后得到 `BLOCKED_JUDGE_UNAVAILABLE`。8 个对照条目有来源，但不是 8 条独立数值条件；空删除集不能证明 repair 保真。
4. closure 为 NOT_PASSED。冻结 751/751 无漂移、候选干净、生产稳定身份未变、进程/锁释放、密钥扫描无命中。KB/外部来源未声称冻结。
5. shim 两次 BrokenPipe，落盘请求数却为 0。回读代码发现它仅启动/退出 finally 写计数，而 runner 以 SIGTERM 结束。零计数不可作实际请求收据。
6. 后续宿主离线对照证明原 shim `read(65536)` 缓冲 SSE：上游先发小块，等 0.6s 结束；直连约 1ms 收到，shim 等约 606ms 才交完整响应。0 模型请求，不据此认定历史超时全部由 shim 导致，也没修后重跑。
7. #75 队列仍待审，没有本候选独立双轴终稿。本次仅更新固定候选和验收边界；不把宿主代码阅读、作者测试或自然验收代签独立 QC。五处 timeout 直接来源已列明；旧取消转发变异 15 passed 是历史测试缺口，未在新候选重新证明。
8. 认证 Gitea 重新确认 #868 WIP/open/unmerged。冻结 main `bbd53487f4cefdae97eae90f7322394d36e65462` 与分支 head `cd520152f9bbf435de81d7b7f662bfa695eef26a` 的 merge-tree clean；没有前向合入或测试联合树。

## 决策与备选

| 决策 | 未选方案 | 理由 |
|---|---|---|
| 新增 protocol-closure，保留原运行快照 | 改写原 protocol 的 pending 状态 | 原件不倒写；终态另带内容 hash 和明确接替关系 |
| L6 维持 NOT_PASSED | completed / 无删句即 PASS | 没有效判官与真实 repair 新稿，Q2/Q3 未执行到业务 |
| 工装缺陷单列 | 把全部超时归咎产品或模型 | 私有 shim 改变流式交付，根因未被完整隔离 |
| 停在本批收尾 | 修 shim 后补 Q3 / 重发 | 首发额度已消费，失败即停的协议不能事后改 |
| #75 仍待独立执行 | 作者自验冒充 K3 终审 | 工单要求不同会话、探针独立记账及可核请求计数 |

## 证据与工具归位

完整报告、具名 JSON 字节副本、可复跑离线 probe 及 hash 在 `docs/verification/2026-09-23-adaptive-l6-closure/README.md`。原始根 `~/.finance-runtime/reviews/pr868-l6-natural-20260923-1455/live-r2/` 保留。审计器重放与原结论逐字节相同，exit 1 表示拒签 PASS。

离线 probe 已归位到报告的 `probes/`，不是丢在临时目录；原 shim 以 `.py.txt` 原样封存。这轮没有把有缺陷的 runner 提升为共享工具，没有修改生产运行代码。共享 `harness-reference` 开工已脏，未触碰；本次可迁移教训是流式中间层必须用“首块先到、EOF 后到”的假服务检查，终态退出还须单独验证计数持久化，不能拿全量响应成功证明流式等价。

## 后续

修工装与新验收另行处理，先离线证明小块透传、断连清理、退出计数可回收；不覆盖本轮失败证据。#75 按 K3 唯一通道、独占树与分段会话执行，先满足工装/网关准入；取消转发停顿探针仍欠。最终工程门禁、独立审查、自然质量和用户合入确认四件分别记账。不得重启生产、补跑本批 Q3 或扩大真实模型预算。
