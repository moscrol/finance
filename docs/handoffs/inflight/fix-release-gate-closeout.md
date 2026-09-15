# fix/release-gate-closeout

## 这个分支做什么
用户授权的#592/#673/#593批次收口：冲突整合、四叶门禁、共享旁路库重建、漂移审计、INDEX/G-04状态纠正。

## 决策与被否方案
- 不豁免基线红、不自合main、不切8792；#592普通推送，作者树原样保留。
- 旁路库从完整副本重建，不从空库覆盖其他表；源/目标锁内复查→备份→原子替换，主库只读。
- 原作者handoff有人工/生产待办，只加当前更正，不删历史、不伪装全部完成。
- 详细决策/被否方案与收据：`docs/verification/2026-09-15-release-gate-closeout.md`。

## 当前状态
#592已推9550a931，open待合；#673已合ce9643b1，#593已合1bcb1ebc。
本枝叠9550a931，追加只读漂移审计工具/测试和收口文档；新增工具不属于#592原收据。
共享db/history_labels.duckdb已于09-15 21:56发布v6；labels1736327/outcomes2277800。
备份db/history_labels.duckdb.bak-v4-20260915-release-closeout；正式四规则收据已写，主检出原有改动未碰。

## 已验证
#592@9550a931干净树四叶全绿：pytest9745P/0F/77S/2xfail，ruff0，前端76P，e2e15P，registry四check+crosswalk全0。
收据20260915T133709Z-9550a931.json校验exit0；基线漂移0；main@1bcb1ebc的Python9692P/0F。
数据：15张其他表逐行不变，旧标签无丢行；3941个NULL→0与#49三值修复一致。
新工具4条定向通过；最终本枝门禁单独记录，不借#592的数字。

## 未验证 / 已知边界
人工stage_manual仍0/42，至少填30；G-04非全验收完成。
生产8792仍e40f22b83717，合入后统计合格新run0；未核同调用CLI实付、未填BP。
未做同一源v4/v5/v6三臂消融，不把所有统计漂移归因到单一补丁。

## 下一步
本枝提交与推送后核最终门禁；用户确认#592及文档增量合并窗口，再验main tip。
另约部署窗口→第一条生产judge_usage→自然积累≥20→成本对账/BP。
创始人填人工对照后stage-agreement，逐条归因。

## 踩过的坑
main已有与6d709cfd等价的Codex修复，别再cherry-pick。check_test_receipt必须在被测树执行。
工具沉淀：新增脚本防“只数行数看不出历史改值/重复行丢失”；未改通用harness，harness-reference现场脏故未动。
