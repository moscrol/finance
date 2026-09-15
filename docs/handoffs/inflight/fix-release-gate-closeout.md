# fix/release-gate-closeout

## 这个分支做什么
#592/#673/#593批次收口及用户授权合并；代码与数据动作已完成，保留人工和生产观察待办。

## 决策与被否方案
- 用户09-16明确说「合并」，已按#592→#747顺序合main；没有把授权扩大为切8792。
- 主检出脏树不动，主干门禁在独立干净树跑；前端也按锁文件独立安装。
- 共享旁路库复制完整旧库重建、审计后锁内原子发布，不原地DROP共享库。
- 详细决策快照 `docs/handoffs/2026-09-15-release-gate-closeout.md`；实际合入与门禁见 `docs/verification/2026-09-16-release-merge.md`。

## 当前状态
#592已合c1f8416a；#747改base=main后已合918f8d5a。两次merge-tree均无冲突且结果等于已测文件树。
共享db/history_labels.duckdb于09-15 21:56发布v6；labels1736327/outcomes2277800，备份bak-v4-20260915-release-closeout。
本轮仅补文档合入状态，不再重建数据。文档回执最终head和同revision门禁见其PR最新评论。

## 已验证
最终业务合并点main@918f8d5a：pytest9749P/0F/77S/2xfail（367.84s）、ruff0、前端76P、e2e15P、registry四check+crosswalk全0。
收据20260915T170134Z-918f8d5a.json；fetch后expect-revision=main校验exit0，漂移0。
原始日志 `~/.finance-runtime/release-merge-20260916/main-*.log`；主检出未提交代码不在收据范围。

## 未验证 / 已知边界
人工stage_manual仍0/42，至少填30；G-04非全验收完成。
8792仍e40f22b83717，未切流；成本样本0是09-15只读扫描结果，非实时计数。未核同调用CLI实付、未填BP。
旧标签3941个NULL→0与#49一致，其他15张表逐行不变；未做同源v4/v5/v6三臂消融。

## 下一步
合并任务已完成，不再等待#592/#747合并授权。
另约部署窗口→第一条生产judge_usage→自然积累≥20→成本对账/BP。
创始人填≥30条人工对照后stage-agreement，逐条归因。

## 踩过的坑
等价代码已入main不代表git祖先一定含原提交；check_test_receipt须在被测树执行。
新增只读漂移工具防只数行数漏历史改值/重复行丢失；未新增通用harness部件，未动脏harness-reference。
