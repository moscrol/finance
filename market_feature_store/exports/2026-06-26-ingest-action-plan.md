# 2026-06-26 Ingest Action Plan (read-only)

> 本计划只渲染已有知识库 dry-run / 只读命令；不执行任何写库动作。写库仍需各脚本自身 --apply + 人工确认。

## 摘要

- **item_count**: 16
- **action_mode_counts**: `{"already_indexed": 5, "dry_run": 7, "manual": 1, "read_only": 3}`
- **command_kind_counts**: `{"kb_audit_missing_concepts": 3, "kb_ima_stock_ingest_dry_run": 1, "kb_materialize_source_stubs_dry_run": 6, "manual_name_theme": 1, "skip_already_indexed": 5}`

## 明细

| Mode | Risk | Gap | 题材 | Concept | Recommended (dry-run) Command |
|---|---|---|---|---|---|
| already_indexed | none | missing_evidence | 玻璃玻纤 | 玻璃纤维 | `概念页已在 RAG index 中，无需补库。` |
| already_indexed | none | missing_evidence | MR(混合现实) | HAMR | `概念页已在 RAG index 中，无需补库。` |
| already_indexed | none | missing_evidence | TOPCON电池 | TOPCon电池 | `概念页已在 RAG index 中，无需补库。` |
| already_indexed | none | missing_evidence | 共封装光学(CPO) | CPO | `概念页已在 RAG index 中，无需补库。` |
| already_indexed | none | missing_evidence | 光学光电子 | LED芯片 | `概念页已在 RAG index 中，无需补库。` |
| read_only | low | missing_concept | 长安汽车 | 长安汽车 | `python3 scripts/audit_missing_concepts.py --vault /Users/lbq/Desktop/c c/知识库/wiki` |
| read_only | low | missing_concept | 钙钛矿电池 | 钙钛矿电池 | `python3 scripts/audit_missing_concepts.py --vault /Users/lbq/Desktop/c c/知识库/wiki` |
| read_only | low | missing_concept | 海峡两岸 | 海峡两岸 | `python3 scripts/audit_missing_concepts.py --vault /Users/lbq/Desktop/c c/知识库/wiki` |
| dry_run | low | missing_entity_exposures | 长安汽车 | 长安汽车 | `python3 scripts/ima_stock_ingest_batch.py --vault /Users/lbq/Desktop/c c/知识库` |
| dry_run | low | missing_evidence | 长安汽车 | 长安汽车 | `python3 scripts/materialize_missing_source_stubs.py --vault /Users/lbq/Desktop/c c/知识库/wiki` |
| dry_run | low | missing_evidence | 机器视觉 | 机器视觉 | `python3 scripts/materialize_missing_source_stubs.py --vault /Users/lbq/Desktop/c c/知识库/wiki` |
| dry_run | low | missing_evidence | 元件 | 光学元件 | `python3 scripts/materialize_missing_source_stubs.py --vault /Users/lbq/Desktop/c c/知识库/wiki` |
| dry_run | low | missing_evidence | 钙钛矿电池 | 钙钛矿电池 | `python3 scripts/materialize_missing_source_stubs.py --vault /Users/lbq/Desktop/c c/知识库/wiki` |
| dry_run | low | missing_evidence | 海峡两岸 | 海峡两岸 | `python3 scripts/materialize_missing_source_stubs.py --vault /Users/lbq/Desktop/c c/知识库/wiki` |
| dry_run | low | missing_evidence | 光纤 | 光纤 | `python3 scripts/materialize_missing_source_stubs.py --vault /Users/lbq/Desktop/c c/知识库/wiki` |
| manual | manual | placeholder_market_theme | 连板未映射 | - | `题材名是占位（如连板未映射），需要人工先确认题材名再进入补库。` |
