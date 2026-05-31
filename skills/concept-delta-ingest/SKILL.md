---
name: concept-delta-ingest
description: 概念边际变化入库——必须在“材料主题已存在于 wiki/concepts/，但材料提供了新的催化、边际变化、关键数据、新增/强化标的、风险或反证”时使用。适用于研报、市场逻辑、早知道、会议纪要、公告、PDF/网页/粘贴文本中的已有概念更新；不要新建重复概念页。若 concept-ingest 判断 existing_concept 非空或 concept_writer.py 返回 update_needed，下一步必须调用本 skill 更新已有概念页。触发词：concept delta、概念增量、更新concept、已有概念更新、概念催化入库、合并到已有概念、update_needed。
---

# Concept Delta Ingest Skill

把材料中“已有概念发生了什么新变化”写入 `wiki/concepts/`。它补足 `concept-ingest` 遇到 `existing_concept` 时只提示 `update_needed`、不自动合并内容的问题。

## 自动触发规则

只要满足以下任一条件，就应触发本 skill：

1. 用户说“更新已有概念 / 合并到已有概念 / 概念增量 / 概念催化 / 不要新建重复页”。
2. 材料中的主题已经能在 `wiki/concepts/` 找到同名或近义概念页。
3. 使用 `concept-ingest` 抽取时，`existing_concept` 应为非空。
4. 运行 `concept_writer.py` 后返回 `status=update_needed`。
5. 一篇材料同时包含新概念和已有概念：已有概念部分必须继续用本 skill 写入，不要停在提示用户手动合并。

## Skill 分流表

| 材料内容 | 目标 | 使用 skill |
|---|---|---|
| 全新产业主题/细分工艺/可交易概念，库里没有对应概念页 | 新建 `concepts/` 页面 | `concept-ingest` |
| 已有概念出现新事件、新订单、新政策、新数据、新标的、新风险 | 更新已有 `concepts/` 页面 | `concept-delta-ingest` |
| 单家公司或多家公司各自发生边际变化，重点是公司页 | 更新 `entities/` 页面 | `entity-delta-ingest` |
| 纯涨跌榜、历史新高、无原因名单 | 不自动写入 | watchlist |

## 与 concept-ingest 的衔接

- 先用 `concept-ingest` 判断“新概念 vs 已有概念”。
- 如果是新概念，正常调用 `concept_writer.py`。
- 如果是已有概念，不要只输出 `existing_concept` 或 `update_needed`；应把同一材料重整为本 skill 的 `updates[]` JSON，并调用 `concept_delta_writer.py`。
- 如果一篇材料里两类都有，先新建新概念，再把已有概念增量写入；两步都要引用同一个 `source_name`。
- 批量写入硬规则：同一篇 source 的所有已有概念增量，必须合并到一个 `updates[]`，一次调用 `concept_delta_writer.py`。不要为每个概念单独调用 writer，避免 source note 重复、frontmatter 多次改写和质检成本膨胀。
- 压缩写入硬规则：本 skill 只处理 `priority="must_write"` 的概念增量。`light_note` 只保留在 source note/最终汇总，不调用 writer；`watchlist` 不写库。

## 单篇批量流程

处理单篇材料时，本 skill 只负责 `ingest-plan.concept_delta_candidates` 中已经确认存在且 `priority="must_write"` 的概念：

```
接收单篇 ingest-plan
  ↓
过滤 light_note / watchlist / 不存在的概念
  ↓
把 must_write 概念整理成一个 updates[] JSON
  ↓
一次调用 concept_delta_writer.py
  ↓
记录 updated_concepts / skipped_updates
```

写入前先用 `rg --files wiki/concepts | rg '/概念名\.md$'` 或等价方式确认概念页存在。不存在的候选概念不要在本 skill 中新建，交回 `concept-ingest` 或放入 watchlist。

## must_write 判定

满足以下任一条件才进入 `updates[]`：

- 原文给出新的关键数据、财务数据、订单、合同、产能、客户导入、政策落地或技术突破。
- 概念本身出现明确边际变化，足以改变“为什么现在关注”。
- 新增核心标的带有清晰公司级证据，而不是单纯名单。

以下情况默认不进入 `updates[]`：

- “关注/挖掘/点名/链条”但没有新增事实。
- 已有概念的常识复述。
- 同一材料中从主线派生出的弱相关概念，只作为 `light_note`。

## 适用场景

- 材料中的主题已经有概念页，例如 `玻璃基板`、`人形机器人`。
- 需要追加新催化、新边际变化、新关键数据、新增/强化标的、新风险或反证。
- 一篇材料同时包含新概念和已有概念：新概念用 `concept-ingest`，已有概念用本 skill。

不适用：
- 完全新概念：用 `concept-ingest` 新建概念页。
- 公司层面的边际变化：用 `entity-delta-ingest` 更新 `entities/`。
- 纯行情名单、没有原因或产业逻辑：默认只放入 watchlist，不写概念页。

## 读取材料

优先复用已经落入 `wiki/sources/` 的 source。若只有 PDF，先抽文本并写入 source（写脚本文件再执行，不使用 heredoc）：

```python
# /tmp/extract_pdf_to_source.py
from pathlib import Path
from pypdf import PdfReader

pdf = Path("材料.pdf")
out = Path.home() / "Desktop/c c/知识库/wiki/sources/材料名.md"
parts = [f"# {out.stem}", "", f"来源文件：{pdf}", ""]
for i, page in enumerate(PdfReader(str(pdf)).pages, 1):
    parts += [f"## Page {i}", "", (page.extract_text() or "").strip(), ""]
out.write_text("\n".join(parts), encoding="utf-8")
print(f"Written to {out}")
```

```bash
python3 /tmp/extract_pdf_to_source.py
```

## 抽取 JSON

从原文抽取为以下 JSON。字段来自原文，不确定则留空；不要编造。

```json
{
  "source_name": "20260522 市场逻辑精选",
  "source_date": "2026-05-22",
  "source_file": "/Users/lbq/Desktop/研报/20260522 市场逻辑精选.pdf",
  "updates": [
    {
      "concept": "玻璃基板",
      "date": "2026-05-22",
      "title": "京东方A牵手康宁，玻璃基封装载板预期升温",
      "summary": "一句话概括本次材料对该概念的新增信息。",
      "key_insights": [
        "发生了什么变化 + 意味着什么"
      ],
      "key_data": [
        {"indicator": "封单金额", "value": "超百亿元", "note": "2026-05-21，京东方A一字涨停"}
      ],
      "catalysts": [
        {"time": "2026-05-20", "event": "京东方A与康宁签署三年合作备忘录", "impact": "玻璃基封装、光互连等商业化预期升温"}
      ],
      "companies": [
        {"name": "京东方A", "code": "000725", "tier": "core", "role": "中游封装载板/光互连应用", "reason": "合作备忘录直接催化"}
      ],
      "risks": [
        "合作备忘录不等于量产订单，产业化节奏仍需验证"
      ],
      "related_concepts": ["TGV（玻璃通孔技术）", "先进封装", "CPO"],
      "parent_concepts": ["先进封装"],
      "relationships": {"TGV（玻璃通孔技术）": "子工艺", "CPO": "下游应用"},
      "supply_chain_layers": {
        "上游": ["高性能玻璃", "激光加工设备"],
        "中游": ["玻璃基封装载板", "TGV加工"],
        "下游": ["CPO", "AI芯片封装"]
      },
      "confidence": "medium",
      "evidence": "短原文依据，便于复核"
    }
  ],
  "watchlist": [
    {"concept": "某主题", "reason": "已有信息不足，未写入"}
  ]
}
```

## 抽取规则

- `concept` 必须匹配已有 `wiki/concepts/{concept}.md`；不存在则跳过并报告。
- `title` 是本次增量的小标题，不是重命名概念页。
- `key_insights` 只写边际变化，避免重复概念页已有常识。
- `key_data` 写成结构化指标；缺少时点/来源可写在 `note`。
- `companies` 写本次材料明确提到且与概念增量相关的上市公司。`code` 可留空，脚本会尝试用 akshare 补；失败则仍写公司名。
- `evidence` 只保留短依据，不要整段搬运。
- `parent_concepts`、`relationships`、`supply_chain_layers`、`companies[].role`、`confidence` 会同步进入 `wiki/relations/`；只在原文支持时填写，不确定留空。

## 写入

同一篇材料只执行一次写入；`updates` 只包含本 source 的 `must_write` 概念增量。写 JSON 到临时文件再执行（不使用 heredoc）：

```python
# /tmp/concept_delta_payload.py
import json, subprocess

payload = {
    "source_name": "20260522 市场逻辑精选",
    "source_date": "2026-05-22",
    "updates": []
}

with open('/tmp/concept_delta_payload.json', 'w') as f:
    json.dump(payload, f, ensure_ascii=False, indent=2)

result = subprocess.run(
    ['python3', '/Users/lbq/Desktop/c c/金融/skills/concept-delta-ingest/scripts/concept_delta_writer.py'],
    input=json.dumps(payload, ensure_ascii=False),
    capture_output=True, text=True
)
print(result.stdout)
```

```bash
python3 /tmp/concept_delta_payload.py
```

脚本会：

1. 匹配 `wiki/concepts/{概念}.md`。
2. 更新 frontmatter：`updated`、`revision`、`sources`，并合并新增 `tickers`。
3. 在正文追加 `## 概念增量` dated entry，含边际变化、关键数据、催化事件、标的增量、风险、相关概念和原文依据。
4. 自动维护 `## 相关概念`，把本次 `related_concepts` 合并进去。
5. 同步更新 `wiki/relations/concept_graph.json`、`entity_exposures.json`、`evidence_index.json`。
6. 更新或创建 `wiki/sources/{source_name}.md`，记录已更新概念和跳过项。
7. 返回 JSON 报告：`updated_concepts`、`skipped_updates`、`source_file`、`graph_files`。

## Frontmatter 约束

- `sources` 必须写成字符串数组：`sources: ["[[20260522 市场逻辑精选]]"]`。
- 禁止裸 wikilink：`sources: [[...]]` 会导致 YAML 解析错误。
- writer 会自动剥掉 `[[...]]` 和 `.md` 后再生成规范 wikilink。

## 质量门槛

- 写入前确认这是“已有概念的新信息”，不是应新建的细分概念。
- 写入后对本批次所有目标文件统一检查：`rg -n "sources:\s*\[\[|\?\（" wiki/concepts/概念1.md wiki/concepts/概念2.md`。
- 写入后检查 source note 中 `## 已更新概念`、`## 跳过概念增量` 是否重复；如重复，人工合并到一个小节。
- 写入后检查 `wiki/relations/concept_graph.json` 中有本次 concept，`entity_exposures.json` 中有本次 `companies[]` 暴露。
- 如果概念页已经有同一 source 的同一标题，先人工判断是否重复；脚本默认追加，不做复杂语义去重。
