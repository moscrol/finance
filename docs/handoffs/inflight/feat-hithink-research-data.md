# 同花顺研究数据第一批

## 这个分支做什么
`feat/hithink-research-data` / `~/fwp-wt-hithink-research-data`：当日异动、完整热度轨迹、估值观察值接既有采集和只读查询；诊断已有源停更。

## 决策与被否方案
- 复用客户端/DuckDB/staging/finance_query，否另起SDK和生产写入链。
- 默认当天热榜30码，否全市场无界请求和旧榜回退。
- 采集日参与截止；否给最新快照换历史日期。事实是最后观察值，非PIT版本库。
- 财务三表/基金/期货延后，先核披露、单位、代码口径。
- 详见 `docs/handoffs/2026-09-21-hithink-research-data.md`。

## 当前状态
代码已提交 `06047324`（基线728f3271）。未push/合main/部署/生产换库。主树他人改动未碰；本交接为随后文档提交。
实际loaded launchd仍指 `finance-workspace-sync@6382c13b`、local计划，无同花顺步骤。该树有未提交指数修补，禁止覆盖/reset。只读主库相关表停09-08，09-18无行；不能称夜跑已恢复。

## 未验证 / 已知边界
- 未跑本候选全量pytest、前端、E2E、独立QC，未验LLM问答质量和真实夜跑发布。
- 真实异动凌晨为空，非空正文需盘后重验；空/partial不补零、不等于覆盖全。
- 事实重采覆盖旧观察，不支持历史版本回放；日期截止只有日粒度。
- 巡检只读plist/源码声明/行数，不证明loaded或值完整；本轮loaded另经launchctl核实。

## 下一步
审候选并跑完整合入检查；合并/部署须用户确认。先保留核对部署树指数热补丁，再准备批准版本部署根；当天盘后走daily-full staging，查请求收据、值覆盖和只读消费。历史缺口按duckdb-backfill，不回补latest-only接口。

## 踩过的坑
只有配置里的步骤会执行，旧任务exit0不代表新源更新。Shanghai采集日单列，不能用UTC日期截断冒充。禁止子进程锁冲突退旁库。专用巡检已入scripts；harness-reference有他人脏BUILD.md未动。

## 已验证
干净06047324：445P/8S（8项旧contains测试缺工作树本地主库）；收据 `~/.finance-runtime/test-receipts/20260920T181549Z-06047324.json`，dirty=false。全仓Ruff、consumption/dataset注册、提交门禁通过。删热度采集截止后预期1F，恢复复验绿。
真实两股隔离库 `/tmp/hithink-research-acceptance-20260921.duckdb`：估值2行、热度10点，真实FinanceQuery读回2/10；异动0行。全部生产数据只读。合同/请求ID见 `docs/data-sources/hithink-research-data.md`。
