# 在途：输入与底座验收

## 这个分支做什么
按用户「列 spec 并推进」完成阶段 A：固定身份、只读盘点、修审计假绿。规格 `docs/superpowers/specs/2026-09-24-architecture-input-foundation-audit-spec.md`。

## 决策与被否方案
- 复用原运营/数据/RAG 检查，否新健康服务与重复能力表；缺的是闭环证据。
- WARN + None/error 表达未知，否缺报告当零；保留 CLI 原退出合同，标 inventory_only。
- 业务恢复归既有 owner，否直接补库/改 KB 冲突/重建索引；需独立授权与版本证据。
- 展开：`docs/handoffs/2026-09-24-architecture-audit-decisions.md`。

## 当前状态
实现、规格及首轮证据已提交 `6e6a2eac2`。未推送/开 PR/合 main/部署。本交接提交只补干净定向收据与接力说明。
生产仍是采样时的 `3b7e473575b0`，readiness 503；数据快照 09-24，标准市场/个股 09-22、板块等 09-18。KB 索引 source_dirty=true；源有35处在途（含未解冲突），未碰。

## 未验证 / 已知边界
阶段 B/C/D 未完成：真实问答消费、方法审批/收益、跨日稳定与优化对照未签。只做只读本地 GET/数据检查和临时夹具测试，无新模型、生产写入或采集。
卖方/晨汇候选不等于生产可见。当前账户 linxiaoqi5111，不是字面 default；两者视角数据不同。
全量 Python/前端/E2E/registry 发布门禁未跑，不具备合入批准。

## 下一步
1. 读 `docs/verification/2026-09-24-architecture-audit/README.md`：九条输入线、底座层、P0/P1 顺序及精确重跑命令。
2. #61 owner 先闭合行情身份/范围/字段与授权换库；KB owner 解决在途源/发布差异，不替他人提交。
3. 对齐晨汇/卖方标准目录和索引，再按 #76 前置及预算做真入口验收；SPT/风远审批逐条查，不凭文章数判有效。
4. 本单要合入时另冻结候选、跑完整门禁并等用户确认。

## 已验证
原版新用例6F/4P，修复后10P；相关103P，ruff/diff-check通过。干净提交6e6a2eac2再跑103P/0F、dirty=false；原件已复制到收据目录 `clean-targeted-receipt.json`。提交钩子的层级、路径、字段、数据集、工具可达性均通过，不能充当完整发布门禁。

## 踩过的坑
health=200不等于readiness；worker就绪不等于证据新鲜；default不是服务默认账户；目录存在不等于文件存在。工具沉淀在原脚本和测试；通用原则沿用共享 nullable-classification-must-preserve-unknown，不另造清单。
