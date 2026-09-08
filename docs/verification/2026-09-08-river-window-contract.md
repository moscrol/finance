# 区间契约 `river.window` + 五类派生 + 区间 PIT——工单 #35（G-02c）验收收据

> 日期：2026-09-08 · 分支 `feat/river-window-contract` · 基线 `gitea/main@8e452e72`
> 工单：`docs/superpowers/specs/2026-09-08-river-window-contract-workorder.md`（PR #666 分支）；契约 09-06 spec §4.4 / §4.6 / §4.2

## 改了什么

| 文件 | 内容 |
|---|---|
| `intelligence/services/river_window_contract.py`（新） | `window(start, end, entity, knowledge_cutoff=C, require_strict, allow_hindsight, with_cumulative)` → `RiverWindow{slices[], derived[], coverage, pit_grade=min, hindsight, alias_applied}`；`C` 缺省 = `end`；`C < end` → `ValueError`；`C > end` 要 `allow_hindsight`；逐日调 `slice_river(day, C, allow_hindsight=True)` 后把 `hindsight` 改成**区间级**标记；`cumulative` 直接包 `range_aggregate(require_complete=True, knowledge_cutoff=C)`，不可信时 `status=unverifiable` **不给数**。⚠ 模块名不叫 `river/window.py`：`river.py` 是模块，同名目录会遮掉它 |
| `intelligence/services/river_derive.py`（新） | 标签绑定 `bind(label, slice)`：白名单 `SLICE_EVALUABLE_LABELS = {dual_red_strict, volume_surge, market_stage, limit_heat_rank}`（阈值 `from labels import` / `turning_points.VOLUME_SURGE_PCT`，不复制数字）；不在 `ALL_LABELS` 或需要历史 → `LabelNotSliceEvaluable`。派生：`derive_streak`（`unverifiable` / `break`，拒 `skip`）、`derive_transitions`（`unverifiable` / `break`，拒 `skip`）、`derive_first_event`（`unverifiable` / `skip`，拒 `break`）、`derive_signature`（包 `river_window.window_features`，向量含晚于 C 的行直接拒绝）。每条带 `derivation_rule / member_refs / gap_policy / gaps_applied / pit_grade / label_version`，`validity_kind=range` |
| `intelligence/services/river_anchor.py`（新） | `anchor_windows(entity, anchor_label, before, after | until_label, knowledge_cutoff, anchors=)` → `AnchorRecord{context, forward, lookback[], context_target, pit_grade=各段最差, gaps, status ∈ ok/unverifiable/open}`；`forward_end > C` 拒绝（§4.6 硬规矩 2）；事件到事件模式尾部无目标 → `open` 不进 N；`find_anchor_days` 扫描；`river_context_dict` 供教学侧挂上下文 |
| `intelligence/services/river.py` | `RiverObject` 加 `validity_kind ∈ point/state/range`、`derivation ∈ deterministic/frozen_llm`、`valid_to`；缺省按 `object_type` 映射（`stage / narrative_version / checkpoint / judgment / observation_script / verdict` → state，其余 point；`narrative_version` → frozen_llm）；**不进 `source_hash`** |
| `intelligence/services/river_window.py` | `build_daily_vectors(*, knowledge_cutoff: str)` **必填**；五个源全部 `trade_date <= C`；每行 `pit_grade` + `pit_evidence{源: True/False/None/"absent"}`——当天有行的源都在 C 前刷过才 strict，无行的源是维度缺口不参与判定；CLI `--cutoff` 必填 |
| `intelligence/services/market_regime_analogs.py` | `load_market_regime_vectors(con, as_of, *, knowledge_cutoff)`：有效时间截 `as_of`（原有），记录时间按 `fact_market_daily.updated_at <= C` 给每行 `pit_grade`（列不存在 → NULL → 判不了）；`window_pit_grade()`；每段类比窗带 `pit_grade`；`MarketRegimeArtifact` 加 `knowledge_cutoff / pit_grade`（`to_payload` 带出）；`load_market_regime_artifact(..., knowledge_cutoff=None)` 缺省 = `as_of`；`regime_block_for_llm` 非 strict 时**只加一行**限定语 |
| `intelligence/services/river_query.py` | `range_aggregate(..., knowledge_cutoff=None)`：None → 老路径逐字节不变（`pit_grade` / `knowledge_cutoff` 为 None）；显式传入按行 `updated_at <= C` 判段级 `pit_grade`；`_stock_rows / _sector_rows` 多取 `updated_at` |
| `intelligence/services/teaching_framework/leader_succession.py` | `build_succession(..., river_db_path=None, river_entity="上证指数")`：非空时把河切片（`river_context_dict`）**合并**进 `context_break / context_birth`，教学标签同名键优先；不传时逐字节同旧 |
| `scripts/river_window.py`（新） | `window --start --end --entity [--cutoff] [--streak L]* [--transition L]* [--first-event track:type]* [--gap-policy] [--json]`；`cluster ... --cutoff`（原 `river_window.main` 的薄壳） |
| 测试 | `intelligence/tests/test_river_window_contract.py` 14 条（契约 / 派生 / 向量 PIT / range_aggregate PIT / RiverObject 字段 / 前视棘轮） |

## 验收逐条（工单 §3）

| # | 判据 | 结果 |
|---|---|---|
| 1 | `window()` 同输入幂等；路径无 LLM | ✅ `test_idempotent_and_slices_match_slice_river`；真库 `半导体 2026-08-24→08-28` 两次全量 JSON 哈希 `f34d6ae04ac5` 相同 |
| 2 | 任一天 `trade_date_only` 整段降档；`C < end` 拒；`C > end` → hindsight | ✅ `test_any_trade_date_only_day_downgrades_window`、`test_c_before_end_rejected_c_after_end_needs_hindsight`；真库 `C=08-26 < end` 拒绝 |
| 3 | `slices[i]` 与 `slice_river(day_i, C)` 逐字节同 | ✅ 真库 5/5——口径：`slices[i].to_dict() == replace(slice_river(day_i, C, allow_hindsight=True), hindsight=window.hindsight).to_dict()`。差的只有 `hindsight` 标记（单点语义里 C > day 叫 hindsight，区间语义里是「站在 C 回看」），它连带决定 `pit_grade`；**除此之外对象逐字节相同** |
| 4 | 派生对象 `member_refs` 解析回切片；缺轨 → unverifiable 不是数字 | ✅ `test_member_refs_resolve_back_to_slice_objects`、`test_streak_unverifiable_vs_break`（缺天 `unverifiable` 写明 `missing:2026-09-02`；`break` 下 longest=1） |
| 5 | 五类各有用例；`gap_policy` 语义 | ✅ streak（unverifiable / break / 拒 skip）、transition（反弹→主升 跃迁日 09-03）、first_event（首见 09-02）、cumulative（真库 `range_aggregate` 五个 values）、signature（包 `window_features`，向量晚于 C 拒绝——代码路径，无单测夹具，见「未做」） |
| 6 | 谓词引用非注册标签 → 拒绝 | ✅ `bind("not_a_label")` / `bind("dual_red_streak")`（需历史）均 `LabelNotSliceEvaluable` |
| 7 | `build_daily_vectors()` 不带 C → `TypeError`；空 C → `ValueError`；带 C 真的截 | ✅ `test_knowledge_cutoff_required`、`test_cutoff_truncates_and_emits_pit_grade`（09-02 行 `updated_at` 晚于 C → trade_date_only）；真库 `C=2026-09-05`：415 行，**strict 381 / trade_date_only 34**，最后一行 09-04；降档原因 `fact_sector_daily 24 / fact_market_daily 11 / limit_heat 2`——07-31 之后的日子被 09-05 之后的日更（`sync-market-overview --days 60` 重写窗）刷过 |
| 8 | `find_regime_analogs` 带 `pit_grade`，两档分开报 | ✅ 每段类比窗 `pit_grade`；真库 `as_of=2026-09-05`：三段类比窗 strict、当前窗 trade_date_only → 整体 trade_date_only，`regime_block_for_llm` 多出一行「PIT 档位：trade_date_only（knowledge_cutoff=2026-09-05）」，其余文案不变 |
| 9 | `leader_succession` 接 river 上下文后旧读数不变 | ✅ 不传 `river_db_path` 时代码路径与旧完全相同（`_enrich` 直接返回）；`test_teaching_framework_succession / readouts / cli` 续绿。**接线是 opt-in**（`scripts/teaching_framework.py` 未改传参，见「未做」） |
| 10 | 前视门禁棘轮 | ✅ `ForwardLookingRatchetTests`：四个模块里裸 `FROM fact_market_daily ORDER BY trade_date`（无 WHERE）即红；`build_daily_vectors` / `load_market_regime_vectors` 缺 `knowledge_cutoff` 即红 |
| 11 | 干净树全量门禁 | 见下 |

## 门禁

（合入前在干净树补跑，读数回填到本节）

## 未做 / 边界

- `derive_signature` 无单测夹具（`window_features` 依赖全套向量形状），只有代码路径与真库 CLI；下一刀补。
- `anchor_windows` 只做定长 `after` + 事件到事件 `until_label` 两种前瞻；`lookback` 只对定长模式做 `before` 窗，事件到事件模式的「走出来之前的量价」留后续。
- `scripts/teaching_framework.py cmd_build_succession` **没有**传 `river_db_path`——接线是 opt-in，避免改动 handoff 收据；要开时传 `river_db_path=source_path`（`river_entity` 默认「上证指数」在 river 里 `entity_unresolved`——板块宇宙口径没有指数，需要改成某个板块或等 river 接指数实体）。
- 事件定价（#663）迁移是 #663 义务。`market_analogs.py` / `stock_analogs.py` 未加 cutoff，只受棘轮「不新增裸全历史扫描」约束。
- `fact_market_daily` 等表**没有 `recorded_at` 列**（#40 收据也记了），所有 PIT 判定用 `updated_at`（刷新时间）作「那时已存在」的充分证据——上界、保守方向。
