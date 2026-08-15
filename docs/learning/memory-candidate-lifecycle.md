# user_memory 候选生命周期（S6 · 离线候选更新链）

> 日期：2026-08-15 · spec：`docs/superpowers/specs/2026-08-15-bookgap-s6-memory-offline-candidate-loop.md`
> 对照 agent book 第 8 章：在线只记录证据 → **离线生成候选** → 验证后发布 → 可回滚。
> 骨架抄自 `forecast_learning_loop`（候选与正式能力隔离、门禁批准、拒绝也留档），不另起炉灶。

## 生命周期

```
台账证据（corrections / checkpoints / verdicts）
        │  离线规则扫描（v1，宁缺勿滥）
        ▼
   produced ──────────────► users/<id>/memory_candidates.jsonl（append-only 留档）
        │  提交既有 memory_gate（fail-closed，判据一行未动）
        ▼
   gated(accepted) ────────► 经 gate 认证写入口落 durable 层：
        │                     - user_correction → corrections.jsonl（record_validated_preference）
        │                     - decision_lesson → judgments.jsonl（record_validated_judgment）
        │                     晋升行带 promotion{candidate_id, content_sha256, provenance}
   gated(rejected) ────────► 只留档，带 gate 拒绝理由（不落 durable 层）
        │
        ▼
   （既有）invalidated ─────► memory_status 追加状态覆盖行归档/撤销晋升行；
                              本回路不新增退出语义，回滚沿用既有机制
```

## v1 规则（触发即产候选，晋升仍由 gate 独立裁决）

| 规则 | 触发 | 候选 kind | 晋升锚点 |
|---|---|---|---|
| `repeated_correction_same_theme` | 同一主题 ≥2 条同向 correction（方向键 = 归一化 principle/correction，相等或包含） | `user_correction` | 簇内最新记录的 principle/correction 原文 + 其 ts |
| `verdict_overturned_by_user` | 同一 checkpoint 机判终态 verdict 被之后的人工终态 verdict 翻案 | `decision_lesson` | checkpoint id + 终态 verdict |

产不出候选是可接受的（宁缺勿滥）；产出率进交付报告，调规则是后续轮的事。

## 归因链（回答「这条经验从哪来」）

每条候选留档行含：

- `source_record_ids`：`correction:<ts>` / `checkpoint:<id>` / `verdict:<id>@<checked_at>`；
- `trigger_rule` / `generated_at`；
- `gate`：完整晋升决定（eligible / reason / content_sha256 / provenance）。

accepted 经验的晋升行自带 `promotion.candidate_id` 与 `promotion.content_sha256`，
任一都能一步反查来源记录：

```bash
python -m scripts.run_memory_candidate_loop trace --candidate-id mc-xxxx
python -m scripts.run_memory_candidate_loop trace --sha <content_sha256>
python -m scripts.run_memory_candidate_loop trace --content "经验原文"
```

## 运行（幂等；夜间挂载 launchd/cron 留给用户）

```bash
python -m scripts.run_memory_candidate_loop run [--user ID | --user-dir PATH] [--dry-run] [--json]
```

- 幂等：candidate_id 由「规则 + 晋升锚点 + 内容 SHA-256」稳定派生，已在档即跳过——同一台账重跑第二次零新候选；
- `--dry-run` 不写任何文件（不写候选档、不写晋升）；
- accepted 写回的晋升行带 `promotion` 字段，不再作为规则输入（防自增殖）；
- 无旁路直写：durable 层只经 `record_validated_preference` / `record_validated_judgment`
  （内部经 `promotion_metadata` 与 gate 决定绑死），单测
  `test_durable_writes_only_go_through_gate_api` / `test_gate_binding_failure_blocks_all_durable_writes` 钉住。

## 边界（非目标）

- 不改 `memory_gate.py` 判据；不改检索器；不做在线学习；候选不自动 accepted。
- interactions.jsonl 在扫描面内（summary 报条数），v1 规则暂不从中产候选。
