# opinion-cross 输出 JSON schema（要点）

> 本文件由 `skills/opinion-cross/SKILL.md` 外置（ADK Reviewer/Generator 模式：检查内容与检查方式解耦 + 渐进披露）；正文与原 SKILL.md 逐字节一致。

```jsonc
{
  "term": "CPO", "theme": "CPO", "concept_matched": true,
  "divergence": { "verdict": "...", "bull_count": 11, "bear_count": 10,
                  "expectation_pivots": ["符合预期就是超预期", "英伟达…辟谣…"], "sources": ["国投硬科技", ...] },
  "opportunities": [
    { "target": "罗博特科", "resonance_tier": "Tier 2：双重验证…",
      "kb": { "concept": "1.6T CPO", "chain_layer": "封装设备", "role": "...", "kb_fact_hardness": "research_claim" },
      "hardness": { "dominant": "硬证据", "hard": ["…订单已超过15个亿…"], "soft": ["CPO首选标的…罗博特科"], "noise": [] },
      "stance": { "stance": "看多", "bull": [...], "bear": [...], "expectation_gap": [...] },
      "dimension_rows": [ {"dimension":"公告/事实","signal":"…","tier":"Tier 2"}, ... ],
      "catalysts": ["…"], "action": "双重验证，已有跟踪价值；等第三维补齐再下重手。" }
  ],
  "summary": { "target_count": 9, "tier_counts": {"Tier 2":2,"Tier 3":7}, "hard_evidence_targets": 2 }
}
```
