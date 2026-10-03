# 记忆召回标注准入实施计划

**Goal:** FINANCEWORKS-8 的评分先证明目标记录可达、身份不歧义，避免用失效题集指导召回默认值。

**Architecture:** 复用生产 judgments/corrections loader 判定有效状态和最近 200 条窗口。评测层提供旧 ts 与显式 stable 身份两种口径，旧题集不静默迁移。CLI 和直接评测 API 在出分前准入；不改生产召回、用户台账或默认模式。

**Tech Stack:** Python 3.12、现有 JSONL 标注、pytest；不加依赖或模型调用。

## 设计与取舍

- 选择新增 `intelligence/eval/memory_recall_labels.py` 统一身份及准入。stable 格式为 `judgment:<id>` / `correction:<id>`；旧行没有 id 时复用 `memory_status.memory_record_id(kind, ts, content)` 派生，绝不回写。
- 拒绝把过期题直接从分母删除：旧集保留，返回每条 missing / inactive / outside_window / ambiguous 原因并拒绝出分。
- 拒绝自动把 ts 转成 id：同秒多条无法知道原标注指向谁；只能由重新标注的新集显式使用 `--memory-identity stable`。
- 有效但未召回的标签仍正常计 miss；准入不检验语义相关性，相关性仍须人工标注。不同 source 的同秒记录也不得合并。
- 这一步只修评测可信度；真实语义模型、更新题集、产品/开发记忆分流和最终答案质量仍属后续验收。

## 执行清单

- [x] 先加回归：两个不同纠偏共用 ts 时旧模式拒绝；stable 模式只标 A 却返回 B 必须为 miss；同秒不同记录非标注召回分别计数。
- [x] 再加回归：归档、窗口外及不存在目标分别诊断；CLI 返回 2 且无 hit/recall 分数；有效目标未命中仍返回 0 分。
- [x] 实现 `memory_identity(kind, record, mode)`、`audit_memory_labels(cases, users_root, user, identity_mode)` 和携带 report 的 `InvalidMemoryLabels`。
- [x] 将 `user_memory_retriever`、`evaluate_cases`、`compare_memory_tiers` 和 CLI 统一接入；非 user_memory 通道不改身份。
- [x] 运行 `.venv-workbench/bin/python -m pytest -q intelligence/tests/test_retrieval_recall.py intelligence/tests/test_memory_semantic.py`；红绿日志放仓外。
- [x] 对冻结真实快照执行新版入口，确认明确拒绝旧15题；保留原始诊断读数和私有结果，只提交统计及哈希索引。
- [ ] 更新 `docs/retrieval-recall-at-k-contract.md` 与验证报告，独立双轴审查；固定 SHA 跑本机完整门禁与 GitHub 检查后才合并。

## 已冻结证据

原始代码 `eb927244c0530b7840ee9d79b5f068084a7c61a2`；私有快照在 `~/.finance-runtime/harness-quality-closeout-1003/memory-recall-20261004/`。15题24个引用中，可达6、窗口外12、归档6；仅4题有任何可达目标。原 ts 口径在 r-008 返回5条时计为4个身份，stable 明细保留5条。该诊断不支持调整生产默认值。
