## 这个分支做什么
强制用户历史截止，按来源真实日期交付事实；`local_only` 只暴露已授权的本地行情快照。

## 决策与被否方案
- 取用户/调用方较早截止，保留 requested；否了只靠模型守窗。
- 窄快照工具而非综合 market_data；离线入口不能因此获得联网能力。
- 日文件自行定日期/质量、保 NULL/0；否了借 latest/meta 补历史。
- 证据、文本、gaps、trace、缓存一并隔离；否了只过滤证据列表。
- 先记录读取尝试再断言；替身异常被吞不能算“未读取”。

## 当前状态
候选 `53054bfd4336bebd0d570273a58e92758fb623be`，tree `2aa8e01864722bd6a659a672e9cd76813f398eeb`。源码未漂移。retry-01 Spec/Quality 各 exit 1、usage limit、无 verdict；仍为 `AUTHOR_TARGETED_CHECKS_PASSED_ACCEPTANCE_BLOCKED`，新 K3 未启动。
归档补齐提交 `4ac4ad0f9`、交接提交 `ca4cdcb89` 已推 Gitea；2026-09-23 质检复核两者均 181/181。独立树 `~/.finance-runtime/reviews/market-cutoff-independent-53054bfd4-tree-20260922` 保持原候选干净快照；没有合 main、部署或生产写入。

## 已验证
以下为原候选历史收据，非本次重跑：Ruff 0；Python 12594P/87S/2X、0F/0E，收据 `20260921T185949Z-53054bfd.json` 与 JUnit 一致；前端 110P、E2E 34P/2S、registry 五项 0。24/24 变异捕获；授权单层撤 guard 仍被最终过滤阻断，双撤才失败。敏感扫描未分类 0。

## 未验证 / 已知边界
真实 Workbench 未接受；市场题误路由、完整自然语言截止/PIT、后来 main 组合、浏览器业务、夜跑和生产效果未验。归档完整不等于独立审查通过。retry-01 原件在归档 `raw/53054bfd4/independent-retry-01/`；CLI 重试时刻未标时区。不换账号/模型绕限额。外部验证目录 Ruff 的历史 fixture 裸文本不代表候选门禁结果。

## 下一步
额度恢复且独立审查可用后，固定准确 SHA 完成审查与主线核对；重新绑定 K3 writer/GLM judge，经真实 conversations/messages 两原题复验。旧 runner 与“新目录旧身份”副本禁止直接跑。读详情再开服务，不把历史进程/端口状态当现况。

## 踩过的坑
runner 启动不等于 pytest 启动，须核 resource_admission 与子进程收据；敏感匹配逐位置核上下文。收据、候选 SHA、归档包、合入状态不能互相移签。
详情：`docs/handoffs/2026-09-22-market-cutoff-followup.md`；归档 README；本次 #63 质检 `~/.finance-runtime/reviews/push-s1-63-qc-20260923T001455/report.md`。
