---
name: disclosure-archive
metadata:
  pattern: pointer
description: 题材证据披露归档（补公告、补公司硬证据、查年报/招股书/互动易/官网产品页、披露归档、disclosure archive）——canonical 实现已归一到 knowledge-base-private，本文件只是指针。
---

# Disclosure Archive（指针）

本 skill 的唯一实现在知识库仓：`knowledge-base-private/skills/disclosure-archive/`。

- 脚本（archive/check/review_queue/batch_summary/candidate_discovery/auto_gap_backfill/apply_review_queue）与字段参考（field-schema、evidence-classification-rules、mapping-rules）均在该目录。
- 字段枚举唯一口径：`knowledge-base-private/skills/disclosure-archive/scripts/schema.py`（归档端全集 + apply 端受限子集，导入时断言对齐）。
- 金融仓侧的运行时对接不变：`intelligence/services/l3_evidence.py` 继续通过 CLI 模板调用披露查询，与实现仓解耦。

触发本 skill 时，读取并遵循 KB 仓的 `skills/disclosure-archive/SKILL.md`。
