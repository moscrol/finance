# E27引用数字门 · 第一修复片

## 这个分支做什么
隔离证据引用编号与业务数量，修复8792诊断中第20句的E27误报，不放宽真实阈值检查。

## 决策与被否方案
- 复用协议引用语法，只改答案/证据的数量分析副本；否决删公开引用、另造正则和关数字门。
- 两端同修：证据文字的E27也不能支持正文“评分低于27”。
- 背景/方案比较：`docs/handoffs/2026-09-17-citation-numeric-gate.md`。

## 当前状态
工作树`~/fwp-wt-citation-numeric-gate-0917`，分支`fix/citation-numeric-gate-0917`，基线`gitea/main@0a1cb8c4`。代码已提交`2841ce66`；未push、未合main、未部署，本轮未改/重启8792。前轮诊断收尾已核对为`40321402`。

## 未验证 / 已知边界
未跑修复版真实Workbench API/模型会话、前端四步、浏览器/E2E、完整registry workflow或外部独立审查。数字门通过不证明金融判断有据；24/25句保持原判不代签量纲/语义正确性。其他诊断缺陷仍在，manual mappingproxy根因未定位。

## 下一步
1. 下一小片：区间榜参数错误后的有界恢复与明确取数失败状态；别只扩工具预算。
2. 修复版同hybrid设置走隔离候选入口复验；未经确认不切8792、不合main。
3. 合并前补齐四叶检查；本轮Python收据不可代替前端/E2E/registry。

## 踩过的坑
- `[20]`是拒绝句索引，不是拒绝20次。
- 重放脚本`runtime_revision`属原探针；裸`quantity_tokens`仍有27，修复看`rejected_with_citation`。
- 新树地图为空；前轮主树查询只当定位，不作架构结论。
- 本轮12份日志/收据在`~/.local/share/finance-workbench/diagnostics/20260917-citation-numeric-gate/`，原样本在同级`20260917-sector-history-2030/`；不清理这两包。

## 已验证
代码提交`2841ce66`干净树全量：11472P/81S/2x，17warnings；全仓Ruff通过。收据`~/.finance-runtime/test-receipts/20260917T133812Z-2841ce66.json`固定revision校验8项通过。后续文档提交不冒称该新头全量。
新增37例；定向285P。撤屏蔽18F、关数字门21F，恢复285P。冻结原件拒绝索引`[20,24,25]→[24,25]`，其他重放字段不变。入口`docs/verification/2026-09-17-citation-numeric-gate/README.md`。工具沉淀为helper和回归，不复制既有重放脚本。
