# 8792 边界组合候选

## 这个分支做什么
组合readiness三类边界与引用数字隔离，再补限定语归属/重复扫描；不是#770整合或生产切流。

## 当前状态
树`~/fwp-wt-8792-boundary-integration`；代码已提交`3faf64fb`，基线`gitea/main@0a1cb8c4`。
来源`c57633bb`+`3c5f485a`，合流`51894716`，补功能`ef9e1c19`、补扫描`3faf64fb`。
未push/开PR/合main/部署。只读8792仍`bf662e9310ff` healthy、dirty=false、matches=true；semantic默认llm/evidence=auto未改。

## 未验证 / 已知边界
- 未用修复版真实模型从Workbench会话入口验证拒登记、格式化财务问题及带日期引用的复查计划；替身与fixture E2E不代签金融答案质量/成本/稳定性。
- #770跨轮材料/local_only/判官拒收反馈、RE06/#53真人验证未组合；判官off观察期未开始。
- 冻结样本只修第20句引用误删；81%与去重并集46.875%差异、区间查询invalid_query、manual mappingproxy故障仍在，重放exit0不等于答案合格。
- 中文判据有限，不是通用自然语言同意解析器；行情/真人台账/生产配置未改。

## 下一步
1. 读[决策快照](../2026-09-17-8792-boundary-integration.md)与[验证索引](../../verification/2026-09-17-8792-boundary-integration/README.md)。
2. 用户确认后才交付远端/合main/切8792。upstream是gitea/main，推本分支必须显式目标。
3. 获授权后在隔离真实Workbench入口验三类任务；若纳入新main/#770，重验最终整合revision，不搬旧收据。

## 决策与被否方案
- 两门验最终交付；否分别拿旧绿拼签，因串接仍会误删计划。
- 限定语只修饰否定/登记动作；否量词字表与全句忘漏扫描，宾语也含这些词。
- 每否定扫一次前缀+计数回归；否秒数上限作为唯一门，主机负载会抖。
- 原QC/冻结重放复用脚本；反例进入pytest，变异片段入验证文档，不另造框架。

## 已验证
精确代码3faf64fb：Python11612P/81S/2x/17warnings，Ruff；前端lint/typecheck/107P/build；E2E34P2S；registry五项+catalog通过。
边界114例+组合26例；七类反证均exit1；原QC15/15；冻结拒绝索引[20,24,25]→[24,25]。
收据`~/.finance-runtime/test-receipts/20260917T152129Z-3faf64fb.json`八项通过、base drift0；原件根`~/.finance-runtime/reviews/8792-boundary-integration-20260917/`。

## 踩过的坑
- docs-only头不冒充精确代码收据；最近收据会被变异覆盖，指定上述文件。
- QueryEnvelope无question；排序写口不看question_type放行。先核实际契约/阳性，避免空测。
- ef9e1c19虽四叶绿，长副词前缀仍重复扫描；3faf64fb已另跑全量，不迁移旧11611P。
- 共享记忆lint前后均19errors/17warnings，非本轮代码门禁红；不顺手修其他笔记或脏harness。
