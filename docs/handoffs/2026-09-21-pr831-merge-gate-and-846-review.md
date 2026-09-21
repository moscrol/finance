# #831 合流门禁与 #846 有界复审

## 身份与授权边界

用户本次要求“继续”，推进验收，不解释为合 main 或部署授权。2026-09-21 23:22 再 fetch 后，main 仍为 `028a251a1b2ca98245326a6b59376f4f7f8e5e81`，#831 head 为 `ea5c3a94618a15e37f914c8b1a13e271875e4337`，#846 本次受审 head 为 `9be77af53624630d6b8d95552382cfe1211bb567`。两 PR 均继续 WIP。

## #846：仍无独立结论

先读原有审查入口。共享 agent-review-loop 绑定另一条任务链，没有向它插入不兼容请求，也没有启动其自动 force-remove 工作树逻辑。`claude auth status` 显示 loggedIn=true、api_key_helper；只说明本地认证配置可用，不能证明模型请求成功。

一次新工具禁用的独立静态审查：bare 模式显式传入原有 apiKeyHelper、localhost:8080 网关、opus[1m] 模型及必要环境，不读取旧会话，不换账号、不加新付费通道。审查输入为固定 Git 完整分支 diff 和编号源码，不提供作者测试作为通过理由；tools 为空、MCP为空，不具备执行部署或动态测试能力。

300 秒内 stdout/stderr 均为零字节，无 verdict；按既定超时 TERM 进程组，exit143，随后确认进程结束。原因未明，不能归为认证失败。首尾源码同 SHA 且 clean。没有第二次重试。**NO CONCLUSION / NO INDEPENDENT SIGNOFF**；静态审核即使返回也不能代替动态验收。

原件 `~/.finance-runtime/reviews/deploy-help-846-resume-20260921/`：execution.json、prompt.txt、run_static_review.py、review-settings.json、stdout.json、stderr.txt。配置只有既有助手路径和网关参数，无明文凭据。PR 评论5471已发布且回读一致。原有工程收据不变；本次未修改部署脚本或测试。

## #831：完成此前缺失的主干合流工程门禁

`merge-tree --write-tree main head` 得到树 `c4ebdbd4d725a73588fe5990cedfc47a9702c265`，无冲突。通过 `commit-tree` 建立仅用于验收的双亲提交 `d97fdf775b279614c6ce4666592a44f2c1c41d11`，在独占 detached 检出 `~/fwp-wt-831-merge-gate-0921` 测试。没有修改 main 或原 PR 分支，没有把旧基线165038af的结果移签。

固定候选结果：

- 全仓 Ruff exit0；完整 pytest **12510 passed / 85 skipped / 2 xfailed / 17 warnings**，1532.13秒，exit0。
- 原生收据 `~/.finance-runtime/test-receipts/20260921T152141Z-d97fdf77.json`：dirty=false、worktree_dirty_total=0、Python3.12.13、解释器主仓venv、依赖指纹3328bed61f3e21ea、exit_status=0。
- 在候选树运行 `check_test_receipt.py ... --expect-revision <完整d97fdf77> --base-drift-max 0` exit0，基座漂移0。日志在证据根receipt-check.log。
- 前端 install/lint/typecheck/test/build/test:e2e 六步exit0；110单测，E2E34 passed/2 skipped。规范收据complete=true、identity_stable=true、dirty=false。
- Registry check-parseability/check/backfill-tables --check/generate-views --check/crosswalk 五项exit0，保留 warning 原文。
- 首尾完整revision/tree/status一致，源码全程独占且未编辑。测试使用env-i与umask022。前端使用#846中的规范runner，显式指定候选树、revision和19881/19884端口；runner哈希记入前端收据，不冒称候选内自带此入口。

完整证据根 `~/.finance-runtime/reviews/831-merge-gate-20260921/`：run_gates.py、python-registry/execution.json与JUnit/逐项日志、frontend/gate/frontend.json与六个日志、reviewed-blob-comparison.json、prior-probe-replay.json。所有后台进程已结束，测试端口无监听；候选树保留，未删除ignored缓存或其他agent材料。

## 原独立报告的适用范围

#831评论5370/5386及 `~/.finance-runtime/reviews/research-tail-integration-20260921/small-sol-review/operator-qc.md` 已有 **PASS_WITH_LIMITS**，是一个独立Codex会话的Spec/Quality两节，不是两位审核者。回读events确认定向105P/1S、Ruff0、独立探针exit0；首次探针语法错误保留。原外层缺进程退出码，不补造。

本次比对七个改动文件和直接生产消费者intelligence/api/app.py的Git blob，与原受审ea5c3a94完全相同。原独立探针仅重定向ROOT后在d97fdf77回放PASS，并断言实际加载路径来自候选树。**回放是本轮操作员复验，不是新独立签字**，原报告不移签成整棵合流树的独立审查。

保留原限制：独立小探针没有单独压满命中上限，Timer在drain前release；强边界来自当时独立重跑的正式回归。未独立动态调用真实code-review-graph后端，不外推#833/#834/#835，不认证最新main其他功能。当前结论是合流工程门禁已补齐、两项既有离线审查未见代码变化；合并仍需用户明确确认并最终固定base/head。

## 生产与后续

本次只读观察8792：adcda94b5e40 recovery，healthy、source_dirty=false、code_matches_repo=true。readiness HTTP503唯一missing_critical仍为market_data_consistency：数据库09-18、快照09-21。health-final.json/readiness-final.json留在#831证据根。没有重启、部署、行情补采或用户数据写入；更早误执行事故不因本段而抹去。

#831为测试夹具/代码地图变更，无需为它重启生产；最新main仍含已回滚K3，不能整体切入。#846无结论不解除WIP，不自动追加模型审查；后续需可用的独立验收会话。旧主检出部署脚本仍危险，不运行它探测帮助。

本轮只使用固定任务执行记录，没有新增通用框架。env-i、身份采样、收据比对均复用既有门禁入口；harness-reference仍有他人改动，不动其通用目录。磁盘已低于7GiB，不开启第二轮全量或批量清理。
