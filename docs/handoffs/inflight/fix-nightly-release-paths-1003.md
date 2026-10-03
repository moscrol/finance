## 这个分支做什么

固定发布快照后，夜跑同步日志/质检JSON/增量备份继续落数据根；补齐可选macOS夜跑依赖。

## 决策与被否方案

| 选择 / 被否 | 理由 |
|---|---|
| FINANCE_DATA_ROOT→FINANCE_WS→ROOT / 不加平行配置 | 复用已有双根合同，保留无配置手动执行 |
| 修真实落盘根 / 不忽略dirty或软链tracked日志 | 保住固定代码快照身份与备份生命周期 |
| 可选nightly锁 / 不复制共享venv | mootdx要求httpx<0.26，与消费侧0.28.1冲突；local不用mootdx |

完整背景与验收：`docs/handoffs/2026-10-03-nightly-release-paths.md`。

## 当前状态

代码/测试/日期文档已提交97a7f8f0b；其父b8e0e68由总控提交nightly锁与credits测试默认时钟。未改生产额度逻辑。UI树仍冻结1be7500c；本树补丁待总控整合进最终PR26候选。

## 已验证

新增12项临时代码副本/小DuckDB行为回归；三次红→绿原件均保留。相关17文件306 passed，ruff与提交hooks通过。仓外证据：`~/.finance-runtime/reviews/workspace-closeout-1003/nightly-paths-targeted.log`。

总控独立venv：nightly锁安装、pip check、doctor零drift通过；禁网导入与合成PNG通过，httpx0.28.1保留。credits测试37 passed由总控验证。

## 未验证 / 已知边界

尚非最终集成SHA全量；未运行生产夜跑、换库、模型或切服务。S7失败通知仍执行数据树notify_ops；额外KB receive shell仍用PATH python3。外部staged wrapper未获得新版daily-full整段锁编排。

## 下一步

总控合入UI候选、补规格/质量复验与精确提交完整门禁，再创建最终main快照并发布。部署审查：仓外同目录`deployment-plan-review.md`。正式启动前复核所有用户持久queued/running任务、实际python_prefix与代码根。

## 踩过的坑

doctor绿只证明开发锁；夜跑还需AkShare/matplotlib。Python可执行链接resolve后只看到基解释器，身份还要看prefix。路径测试允许临时库，禁止借生产数据验落点。本轮反例已归正式测试，复用既有发布入口，无新平行工具。
