---
name: pdf-ingest
description: PDF 研报入库到 Obsidian 知识库并对齐 Theme Radar 底层数据。Use when the user says PDF ingest、pdf入库、研报PDF入库、处理研报PDF、OCR研报、评级日报/脱水研报/强势脱水/风口研报入库，或要求把 PDF/source note/concept/entity/entity_exposures/evidence_index/report_contexts 与题材雷达底层对齐。
---

# PDF Ingest Skill Shim

这是给只扫描 `.claude/skills` 的 IDE 使用的稳定入口。

## 必读权威文件

skill 本体已迁入知识库仓（2026-06-12）。先读取并遵守：

`<知识库>/skills/pdf-ingest/SKILL.md`

如需完整批量流程，再读取：

`<知识库>/.devin/workflows/pdf-ingest.md`

## 关键路径（均在知识库仓）

- 统一入口：`python3 <知识库>/scripts/ingest.py pdf ...`
- Writer：`<知识库>/skills/entity-delta-ingest/scripts/entity_delta_writer.py`
- 图片 PDF 切图：`<知识库>/skills/entity-delta-ingest/scripts/extract_pdf_images.py`
- Lint：`<知识库>/skills/lib/pdf_ingest_lint.py`

路径解析：知识库仓位置可用环境变量 `KB_VAULT`（wiki 根目录）指定；默认在本仓同级目录自动探测。

## 不可违反的硬规则

- 券商/脱水/评级日报/风口研报默认 `source_quality=broker_research_high`。
- broker 源不直接写 `hard_fact` / `delta` / `## 边际变化`。
- broker 源公司级事实关键词只能走 `curated_research + review_candidate + L1_L3_candidate + review_required=true`。
- 纯名单/受益映射走 `graph_only + peripheral` 或 `observation_only`。
- 写入后必须运行：

```bash
python3 "<知识库>/skills/lib/pdf_ingest_lint.py" "source_name"
```

要求 0 errors；warnings 也应尽量清零。
