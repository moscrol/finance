# 在途 · 卖方观点消费截止修复

## 这个分支做什么
把卖方事件的报告日、首次入库、订正发布时间分开，给催化归因、Workbench 卖方流、教学叙事和事件定价接统一只读投影；不接线上 river。

## 决策与被否方案
- 原 `opinion-events.jsonl` 只读；更正写 `corrections/<batch>.json`，绑定原记录/原文 SHA 与字符锚点。否掉直接改台账，因会抹掉错误版本和入库时点。
- `quarantine` 是待审，不等于判错；只对两条主题/证据可定位的记录 replace，对两条署名误主体 retract。否掉给471条猜摘要。
- 北京时间日终截止；推断日期默认排除。否掉用报告日回填缺入库时间，也不把日期级截止说成日内 PIT。
- 卖方源有隔离/时间警告时，催化不因晨汇存在而判 `market_only`；Workbench 警告走既有 `data_status`。

## 当前状态
金融代码 `6de192c61`、验证/交接 `0e0671c11`，分支 `fix/sellside-consumption-0922`；KB订正已提交 `b398fcf7d`，均未合并/未部署。独立全仓 `12547 passed, 85 skipped, 2 xfailed, 17 warnings`；收据为 `docs/verification/2026-09-22-sellside-consumption.json`，不代表合并或部署验收。KB 批次 `20260922-miracle-consumption-review-v1` 已幂等发布：471 quarantine / 2 replace / 2 retract；原台账 SHA `6376356652f42292c0a648ff47745a3897e4600f3992070332729fe5af37738c` 不变。KB `wiki/log.md` 已追加 #6895；`wiki/relations/access_log.jsonl` 是测试产生的脏文件，不提交。

## 已验证
定向消费者回归 107 passed，ruff、compileall、金融提交门通过；17/17原贴字节审计通过；projection 收据绑定代码/订正/台账 SHA。KB tests 527 passed/1 quality baseline failure；strict-vocab 0错误3警告；日志 T1 纯追加，质量缺链与体积门仍红。

## 未验证 / 已知边界
前两轮金融全量分别受临时快照 `Errno 28`、临时根消失导致的 `FileNotFoundError` 影响，均不计作代码红绿；第三轮专用临时根已通过。river 仍读 `fact_research_report_catalog`，不读订正投影；晨汇、`opinion-cross` staging/outcomes writer 未迁移。教学/定价是构建日事后聚合，非严格历史开盘 PIT。09-11日期未确认；471条未逐条语义复核。

## 下一步
收据已封存到 `/Users/a77/.finance-runtime/reviews/sellside-consumption-6de192c61-20260922/`。决策见 `docs/handoffs/2026-09-22-miracle-opinion-corrections.md`。下一步是独立验收及前端叶子检查，不因Python通过授合并权。等用户确认09-11后另批次释放两条；471条逐条复核；river桥接需独立合同和授权。

## 踩过的坑
pytest共享临时根消失会引发级联错误，本次未确认删除者；独立全量使用专用 `--basetemp`，前两轮失败收据保留。#6895已使用，合流前重查并发编号。提交只用pathspec，勿带入access_log。
