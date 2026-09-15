# fix/release-gate-closeout

## 这个分支做什么
#592/#673/#593批次收口及用户授权合并；代码与数据动作已完成，保留人工和生产观察待办。

## 决策与被否方案
- 用户09-16明确说「合并」，已按#592→#747顺序合main；没有把授权扩大为切8792。
- 主检出脏树不动，主干门禁在独立干净树跑；前端也按锁文件独立安装。
- 共享旁路库复制完整旧库重建、审计后锁内原子发布，不原地DROP共享库。
- 会话测试复用消息终态等待，不sleep、不skip、不靠重跑挑绿；事件屏障变异证伪。决策 `docs/handoffs/2026-09-16-release-merge-message-wait.md`。

## 当前状态
#592已合c1f8416a；#747改base=main后已合918f8d5a。两次merge-tree均无冲突且结果等于已测文件树。
共享db/history_labels.duckdb于09-15 21:56发布v6；labels1736327/outcomes2277800，备份bak-v4-20260915-release-closeout。
收尾PR #748含状态回执和一个测试文件的等待修复；e2e7d11a原全量1红及定向1红保留。最终head、门禁及合入状态以#748最新评论为准；本轮不再重建数据，不改runtime。

## 已验证
最终业务合并点main@918f8d5a：pytest9749P/0F/77S/2xfail（367.84s）、ruff0、前端76P、e2e15P、registry四check+crosswalk全0。
收据20260915T170134Z-918f8d5a.json；fetch后expect-revision=main校验exit0，漂移0。
原始日志 `~/.finance-runtime/release-merge-20260916/`；主检出未提交代码不在收据范围。
消息等待修复定向7P；移除等待的事件屏障变异1F（message-wait-fixed/mutation.log），不冒充全量。

## 未验证 / 已知边界
人工stage_manual仍0/42，至少填30；G-04非全验收完成。
8792仍e40f22b83717，未切流；成本样本0是09-15只读扫描结果，非实时计数。未核同调用CLI实付、未填BP。
旧标签3941个NULL→0与#49一致，其他15张表逐行不变；未做同源v4/v5/v6三臂消融。

## 下一步
#592/#747已合；接手先核#748 API/最新门禁。若未合，须精确head四叶全绿再合，之后main全套复验；不把历史918f8d5a收据冒充最新main。
另约部署窗口→第一条生产judge_usage→自然积累≥20→成本对账/BP。
创始人填≥30条人工对照后stage-agreement，逐条归因。

## 踩过的坑
check_test_receipt须在被测树执行；run终态不保证消息终稿可见，等待应绑定断言对象。
屏障回归已进tests，不另建通用脚本；harness-reference的BUILD.md脏故未动，可复用原则进agent-memory。
