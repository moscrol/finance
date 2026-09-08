# 上下文投影契约 + `projection_hash` 台账门禁——工单 #34（G-14）验收收据

> 日期：2026-09-08 · 分支 `feat/river-context-projection` · 基线 `gitea/main@8e452e72`
> 工单：`docs/superpowers/specs/2026-09-08-river-context-projection-workorder.md`（PR #666 分支）；契约 09-06 spec §4.5

## 改了什么

| 文件 | 内容 |
|---|---|
| `intelligence/services/river_projection.py`（新） | `project(source, framework_version, task, budget, rules)` → `ContextProjection{projection_version, framework_version, task, source_ref, blocks[], omitted, omitted_refs, limits, gaps, budget, label_version}`；哈希 = `cp:` + sha256(有序 blocks 的 (ref, source_hash) + framework_version + projection_version + budget + source_ref + label_version)[:16]，`rendered_text` 不进哈希；默认序 轨按 `river.TRACKS`、轨内 硬度降序 → `recorded_at` 升序 → `ref`；块 = `(track, object_type, derivation)`，`frozen_llm` 排 `deterministic` 之后；个股级对象折叠成 `stock_node` 计数块（不出名单）；预算按块整体省略进 `omitted`；`SelectionRule` 协议 + `DefaultRule` / 测试用 `TopNRule`；`render()` 段序 限制 → 缺口 → 事实块 → 省略 |
| `intelligence/services/guided_reading.py` | 改为投影消费方：`build()` 先 `project_slice()`（`task="guided_reading"`，`budget=None`），`facts` 从块渲染、`limits / gaps` 取投影、`GuidedReading` 加 `projection_hash / omitted`；骨架 `evidence_refs` = 投影 `selected_refs`，并带 `projection_hash` 与 `model_id="deterministic"`；`render()` 段序改为 限制 → 缺口 → 事实 → 判读 → 明天要看什么，头部第二行带 `projection=cp:…`；**关闭路径一行未动**（`run()` / `merge_into_daily_review` 的 `is` 等价保留）。删除了 `_PAYLOAD_KEYS` 字母序截断与三个私有渲染函数（逻辑移到投影层的 `render_object / render_collapsed`，键按 provider 序显示、被省键数写进文案） |
| `intelligence/services/observation_script.py` | `ObservationScript` 加 `projection_hash / model_id`；`make()` 透传；`register(..., user_authored=False)` 与 `repoint` 把两字段与 `user_authored` 传给台账；用户手写无投影的记录写 `projection_hash_missing=user_authored` |
| `intelligence/services/checkpoints.py` | `register_checkpoint(..., projection_hash, model_id, user_authored)`：`agent_judgment` 缺哈希或 `model_id` → `ValueError`；`observation_script` 缺哈希且未声明 `user_authored` → `ValueError`；`judgment` 可空。记录落 `projection_hash`（有就记）、`model_id`、`projection_hash_missing`。`CategoryStat.with_projection_hash` 与 `Calibration.projection_hash_missing` 两个计数（不进任何率），`render_report` 各加一行 |
| `intelligence/cli.py` `observation confirm` | `--from-slice` 的确认带草稿的 `projection_hash / model_id`；没有 `--from-slice` 的手写剧本以 `user_authored=True` 登记 |
| `scripts/river_projection.py`（新） | `replay --as-of --entity [--cutoff] [--task] [--budget] [--framework-version] [--expect cp:…] [--from-json] [--json]`；`--expect` 不等退出码 1 |
| 测试 | 新 `intelligence/tests/test_river_projection.py` 22 条；`test_observation_script.py` / `test_observation_review_fixes.py` 夹具剧本补 `projection_hash`（它们是「从切片派生」的语义） |

## 验收逐条（工单 §3）

| # | 判据 | 结果 |
|---|---|---|
| 1 | 同 `(source, framework_version, task, budget)` 两次哈希相等，路径无 LLM | ✅ `test_same_input_same_hash_and_no_side_effects`；真库 `半导体@2026-09-07` 两次 `cp:7b032c7bf5a758c1` |
| 2 | 源里每个 gap 都在投影里；gaps / limits 排事实前 | ✅ `test_gaps_and_limits_present_and_before_facts`（含 `stock：empty` 与 `judgment` 缺口） |
| 3 | 改 `source_hash` 哈希变；改文案 / 显示键数哈希不变 | ✅ `test_hash_changes_when_source_hash_changes_not_when_rendering_changes` |
| 4 | 四块强制；`budget=1` 只省块不截对象 | ✅ `test_mandatory_blocks_cannot_be_none`、`test_budget_omits_whole_blocks_never_truncates`（被省 ref 全部可见） |
| 5 | 默认序 = `TRACKS`；轨内硬度 → recorded_at → ref；`frozen_llm` 后置；`selected_by=default` | ✅ `test_default_order_is_domain_order_not_alphabetical`（字母序会把 opinion 排 theme 前）、`test_within_track_hardness_desc_then_recorded_at_then_ref`、`test_frozen_llm_after_deterministic` |
| 6 | 带读每条事实 ref 在投影里；骨架 `evidence_refs ⊆` 投影 ref | ✅ `test_facts_come_from_projection_blocks`、`test_draft_evidence_refs_subset_of_projection` |
| 7 | 关闭带读逐字节不变 | ✅ 既有 `test_guided_reading_daily_seam.py` 续绿；新 `test_disabled_path_untouched`（关闭时 `project` 被调用即失败） |
| 8 | `observation_script` 缺哈希拒收；`agent_judgment` 缺 `model_id` 拒收；`judgment` 可空；错误信息点名字段 | ✅ `LedgerGateTests` 四条 |
| 9 | `replay --expect` 命中 / 不命中退出码 0 / 1 | ✅ `test_replay_from_json_match_and_mismatch_exit_codes` |
| 10 | 真库冒烟两次哈希相等 | ✅ `半导体@2026-09-07`：6 块（market label / market stage / opinion event×3 / opinion label / capital label / stock_node×10 折叠）、gaps theme / judgment（`no_data`）、`pit_grade=strict`，两次 `cp:7b032c7bf5a758c1`。「上证指数」六轨 `entity_unresolved`——`river.slice` 是板块宇宙口径，指数不在里面，**是读取面的既有边界不是本单回归**，工单 §3 第 10 条的实体改成板块 |
| 11 | 干净树全量 ruff 0 + 红集 ≤ 基线；`check_test_receipt` | 见下 |

## 门禁

干净树 `~/fwp-wt-river-projection`、`.venv-workbench`、`env -u MARKET_FEATURE_STORE_DB`：

| 分支尖 | ruff | pytest | `check_test_receipt` |
|---|---|---|---|
| 第一轮 `be558d7d` | 0 | 11F / 8174P——11 红全部是「从切片派生的确认剧本没带 `projection_hash`」（`test_hindsight_excluded` 2、`test_personal_export_and_isolation` 9），门禁按设计拒收，夹具补哈希 | — |
| 第二轮（夹具修后） | 0 | **8185P / 0F / 76S / 1xfail**（306s） | `--expect-revision HEAD` 可采信 |

对照 main 基线 8183P（#620 树同日读数）：+2 = 本单净增测试数减去被删的私有渲染函数测试。

**新基线（main ，含 #653 授课框架读数 + #665）**：前向合并  后干净树全量 **8211P / 0F / 77S / 1xfail**（361s）， 可采信； 冲突按「teaching_* 对象不进投影块、单独一段渲染」解。

## 未做 / 边界

- 授课框架选择规则未写（G-01 后）；今天所有块 `selected_by=default`。
- `RiverObject` v0 没有 `hardness / derivation` 字段，投影从 `payload` 读；真库对象今天全部 `n/a` / `deterministic`，硬度序在真库上暂时全平局。
- 不追溯拒收存量无哈希记录；`calibrate` 只多两个计数列。
- `UBIQUITOUS_LANGUAGE.md` 四条词与路线图 G-14 回写放在 PR #666 分支（该文件的「产品终局」节只在那边），本 PR 不碰以免冲突。
