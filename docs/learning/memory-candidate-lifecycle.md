# user_memory 候选生命周期一页（书距 S6）

> 对照 ai-agent-book 第 8 章：在线只记录证据 → **离线生成候选更新 → 独立验证后发布** → 可回滚。
> 在线记录与入口门禁本仓已有；本页描述补上的「候选产生」环：
> `intelligence/services/memory_candidate_loop.py` + `scripts/run_memory_candidate_loop.py`。
> 判据与边界见 `docs/superpowers/specs/2026-08-15-bookgap-s6-memory-offline-candidate-loop.md`。

## 1. 生命周期

```
台账信号（corrections / checkpoints / verdicts）
   │  离线扫描（经既有 loader；memory_status 归档/撤销的不参与；
   │  带 promotion 的晋升行不算用户信号——防自我放大）
   ▼
produced（v1 两条保守规则，宁缺勿滥，产出率进报告）
   │  逐条提交既有 MemoryGate.decide（fail-closed，本环无任何绕行写路径）
   ▼
gated ──接受──▶ accepted：经 record_validated_preference / record_validated_judgment
   │            落 durable 层（corrections.jsonl / judgments.jsonl 晋升行，
   │            promotion 元数据绑定内容哈希 + candidate_id）
   └──拒绝──▶ rejected：只留档，带 gate 理由（如 correction_provenance_mismatch）
   ▼
（既有出口，不在本环内）
   - durable 晋升行：`memory-status` 追加 archived/rejected 覆盖行退出召回；
   - 经验卡片：沿用自己的 `invalidated`（Q5：两套退出语义不合并）。
```

- **候选无论接受与否**都追加进 `users/<id>/memory_candidates.jsonl`（append-only）。
- 晋升仍走门禁：本环只自动化「产生」这一步，判据在 `memory_gate.py`，本环不改它。

## 2. v1 规则（都是确定性规则，不用 LLM）

| 规则 | 触发 | 候选 kind | gate 溯源 |
|---|---|---|---|
| `repeated_correction` | 同一原则文本（规范化后相同 = 同一主题且同向）出现 ≥2 条**非晋升产物**的纠偏 | `user_preference` | `correction_ts` 锚最新一条，gate 要求该 ts 恰有一条正文匹配 |
| `verdict_overturned` | 同一 checkpoint 终态判序列：最新是人工（`auto=false`）、其前有机判（`auto=true`）、两者结论不同（翻案）；人工维持原判/最新是机判/人工非终态都不算 | `decision_lesson` | `checkpoint_id` + 最新终态判（即人工翻案判） |

产不出候选是可接受的（书：优先可归因、可验证、可回滚的局部修改）；
`run` 报告里的 `production_rate` = 本轮新候选 / (corrections + verdicts) 扫描行数，调规则看它。

## 3. 候选行 schema（`memory_candidates.jsonl`）

```json
{
  "record_type": "memory_candidate",
  "schema_version": "1.0",
  "id": "memcand-<sha16>",
  "ts": "<本轮 generated_at>",
  "rule": "repeated_correction | verdict_overturned",
  "kind": "user_preference | decision_lesson",
  "content": "…",
  "content_sha256": "<gate 决定书绑定的哈希>",
  "status": "accepted | rejected",
  "gate_reason": "explicit_user_correction | reviewed_checkpoint_lesson | <拒绝理由>",
  "gate_provenance": {"correction_ts|checkpoint_id": "…"},
  "attribution": {
    "source_record_ids": ["corrections:<ts>#<sha12>", "checkpoints:<id>", "verdicts:<checked_at>#<sha12>"],
    "rule": "…",
    "generated_at": "…"
  },
  "written_to": "corrections.jsonl | judgments.jsonl"
}
```

来源定位符：`<ledger>:<ts>#<sha256(canonical_json)[:12]>`；checkpoints 已有稳定 id 直接引用。
这是 Q3（记录级 id）落地前的过渡格式，S8 加上记录 id 后 v2 可改绑。

## 4. 幂等与恢复

- 候选 id 只由（规则, 规范化内容[, checkpoint id]）决定：**同一台账重跑两次，第二次零新候选**（单测钉住）。
- durable 写与候选行是两次追加：中间崩溃后重跑，凭 durable 晋升行里的
  `promotion.candidate_id` 识别「已写过」，跳过重写、只补候选行——不会重复落盘。
- 回滚/归因：给任一 accepted 经验（晋升行），
  `run_memory_candidate_loop.py trace <candidate_id | 晋升行 ts | content_sha 前缀>`
  一步返回来源记录 ids；退出走既有 `memory-status`（可回放的覆盖行，不删历史）。

## 5. 运行

```bash
# 手跑 / 夜间挂载（挂载 launchd/cron 留给用户；幂等，可任意频率）
.venv-workbench/bin/python scripts/run_memory_candidate_loop.py run
# 只看不写
.venv-workbench/bin/python scripts/run_memory_candidate_loop.py run --dry-run
# 归因反查
.venv-workbench/bin/python scripts/run_memory_candidate_loop.py trace memcand-xxxx
```

## 6. 边界（与其他缝的关系）

- 不改 `memory_gate.py` 判据、不改检索器、不做在线学习（第 8 章在线/离线分离）。
- 不动 `memory_status.py`（S8 的缝）；本环只经 loader 间接消费其状态过滤。
- 与 `forecast_learning_loop`（双盲复盘平面）同构不同平面：那边是 reflection→人工
  approve，这边是规则候选→memory_gate；两边各管各的台账，不合并。
