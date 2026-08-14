# FinHot Staging 与 KB Ingest Queue 身份串联设计

## 目标

把 FinHot Evidence Hunter staging 与上游 KB ingest queue 串成同一条可追踪链路：

```text
日报发现缺口
  -> kb_ingest_queue / research queue task
  -> Evidence Hunter 找证据
  -> FinHot staging
  -> approval manifest
  -> 正式 source note
```

第一版只改 FinHot staging/manifest 输出，不直接写知识库正式层，也不自动 apply。

## 核心身份字段

### candidate_id

任务级候选 ID。用于表示“某个任务命中了某条证据”。

生成口径保持：

```text
sha1(task_id + item_id + url + evidence_layer)
```

特点：

- 随 `task_id` 变化。
- 适合 approval manifest 的逐任务审核行。
- 不作为跨日期去重主键。

### source_fingerprint

证据源级指纹。用于跨日期、跨任务去重。

生成口径：

```text
sha1(normalized_url + item_id + evidence_layer + excerpt_hash)
```

其中：

- `source_fingerprint_version` 固定为 `v1`。
- `normalized_url` 去首尾空白、去 fragment、稳定排序 query 参数。
- `normalized_url` 在 `v1` 中将 `http` 与 `https` 视为同源，统一为 `https`。
- `normalized_url` 在 `v1` 中去掉非根路径末尾的 trailing slash，即 `/abc` 与 `/abc/` 视为同源。
- URL 为空时，指纹自然退化为 `item_id + evidence_layer + excerpt_hash`。
- `item_id` 使用 FinHot `item_id`。
- `evidence_layer` 保留，因为同一源在不同证据层下审查语义不同。
- `excerpt_hash` 来自正文摘要的归一化文本 hash，避免无 URL 或 URL 复用时碰撞。

## KB queue 串联字段

每条 manifest approval 行增加：

- `task_id`：Evidence Hunter 当前任务 ID。
- `origin_queue_task_id`：上游 queue/research task ID；默认等于 `task_id`，如果报告任务里有更原始 ID 则优先使用。
- `kb_task_id`：给后续 KB ingest/apply 使用的统一任务 ID；默认等于 `origin_queue_task_id`。
- `source_fingerprint`：证据源级去重主键。
- `source_fingerprint_version`：指纹生成规则版本，第一版固定为 `v1`。

从 task 中读取 ID 的优先级：

```text
origin_queue_task_id > kb_task_id > queue_task_id > task_id
```

## L3_candidate 防误升级字段

每条 approval 行固定带：

- `evidence_layer_original`
- `evidence_layer_proposed`
- `approval_cannot_upgrade_without_official_url`

规则：

- 对 `L3_candidate`，`evidence_layer_proposed` 默认为 `null`。
- 对 `L3_candidate`，`approval_cannot_upgrade_without_official_url` 固定为 `true`。
- 只有人工补充或确认官方 URL 后，后续 apply 才能升级为官方 L3。
- 对官方 L3/L2，`evidence_layer_proposed` 默认等于原始层。

## Approval 状态机

`decision` 固定为以下值之一：

- `pending`
- `approved`
- `rejected`
- `applied`

每条 approval 行增加审计字段：

- `reviewer`
- `reviewed_at`
- `decision_reason`
- `target_note_path`

第一版不自动写 `reviewer/reviewed_at`，只留空字段供人工或后续工具填写。

## Staging Markdown 展示

Markdown 表格和详情增加：

- `source_fingerprint`
- `candidate_id`
- `kb_task_id`
- `origin_queue_task_id`

人工确认清单以 `source_fingerprint` 辅助去重，以 `candidate_id` 区分任务命中。

## 非目标

- 不修改知识库仓的 `build_ima_concept_ingest_queue.py`。
- 不写正式 `sources/`。
- 不消费 approval manifest。
- 不迁移历史 staging 文件。

## 测试要求

- 同一 item/url/layer/text 在不同 `task_id` 下 `source_fingerprint` 相同。
- 同一 item/url/layer/text 在不同 `task_id` 下 `candidate_id` 不同。
- manifest approval 行包含 queue 串联字段。
- `L3_candidate` 默认不可升级，且 proposed layer 为 `null`。
- 官方 L3/L2 proposed layer 默认等于原始层。
- approval 状态机字段完整。
