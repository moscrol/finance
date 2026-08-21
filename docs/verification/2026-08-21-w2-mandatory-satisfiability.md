# W2 机制证明：必需项可满足性（2026-08-21）

> 对应 spec：`docs/superpowers/specs/2026-08-21-ceiling-shape-closeout-design.md` W2。
> 台账：`R-20260821-08`（`docs/prediction-ledger.md`）。
> 本单不跳过修复轮——2016-08-21 已回退过「整轮 skip」（`test_repair_carry_just_written_finish` 夹具正是 evidence 格 + 0 次调用 + 不重开工具）。

## 0. 一句话

契约必填与运行时供给对不上时，不再逼模型编造或挨 marker_loss。两级对账：生成前查 KB 暴露；修复轮 `unreachable && !reopen` 把不可达必填格降成结构化缺口。

## 1. 两级分别管什么

| 级 | 机械判据 | 处置 | 不做什么 |
|---|---|---|---|
| 静态 | `entity_exposures` 在场且 `get_exposure_matches(subject)` 零公司 | `chain_mapping.required=False`，预置「知识库暂无该题材产业链证据」 | 不猜工具会不会返回有用数据；relations 不在场 → 不定，保持 mandatory |
| 动态 | `unreachable_repair_goal` 非空且 `reopen_tools=False` | 那些 evidence 格 + 全部 mandatory capability 降级；模型侧 goal 去掉这些格 | 不跳过修复轮（salvage 仍要跑）；已兑现的格不缝缺口 |

钙钛矿案 `run_20260821_171744_929436` **不是**「KB 空库」：本机 wiki 钙钛矿有数十家暴露。它是动态形状——本轮只调了 `finance_query` / `news_search`，`repair_goal.unreachable_without_tools` 含 `chain_mapping` 且 `reopen_tools=False`，模型被逼编先导/杰普特/欧莱新材，判官删句后 marker_loss。静态预检对它保持 mandatory（KB 有货）；动态兜底才降级。

## 2. 离线判据

| # | 钉 | 结果 |
|---|---|---|
| ① | 无链路证据题材 → `chain_mapping` optional + 预置缺口 | `test_no_kb_chain_evidence_makes_chain_mapping_optional` |
| ② | 有暴露 → 仍 mandatory | `test_kb_chain_evidence_keeps_chain_mapping_mandatory` |
| ③ | `unreachable && !reopen` → 缺口声明、无「应重做」横幅、模型侧不再列出该格 | `test_unreachable_without_reopen_downgrades_to_gap_not_banner` |
| ④ | #296 `company_current_backdrop` + 市场主体 `ROUTED_FACTS` | `test_company_current_backdrop_still_demotes_market_mandates` / `test_seam_ladder_market_subject_keeps_mainline_mandates` |
| 重放 | 钙钛矿动态形状 after = 缺口、`lost_required_output_substance` 不含 chain_mapping | `test_perovskite_replay_unreachable_chain_mapping_leaves_gap_not_marker_loss` |

原始工件：`~/.local/share/finance-workbench/users/linxiaoqi5111/runs/run_20260821_171744_929436/`（before：`gap_output_ids=['chain_mapping']`，公开稿「结构缺口…应重做这些部分」）。

## 3. 变异

见同测试文件两条钉。实施先提交（`git checkout` 会冲掉未提交实现），再亲手反转：

1. 预检判定反转（空库仍 `required=True`）→ `test_precheck_inversion_would_keep_empty_theme_mandatory` 红。
2. 兜底拆除（unreachable 仍压 mandatory / 仍写入模型侧 `missing_answer_elements`）→ `test_unreachable_fallback_inversion_would_keep_pressure` 红。

离线全量（脏树、本单未提交时）：`5904 passed, 13 skipped, 0 failed` @ `0ed258b5` dirty，收据 `~/.finance-runtime/test-receipts/20260821T140928Z-0ed258b5.json`。干净树收据在提交后另跑。

## 4. 接缝与文件

- `intelligence/services/mandatory_satisfiability.py` — 裁决
- `episode_factory.build_episode_context(..., knowledge=)` — 静态预检
- `agent_episode.resume` — 观测仍投完整 goal；模型侧用降级后的 goal；不 skip
- `continuous_turn_adapter` — 修复后结构核验用降级契约；公开稿只给**仍未兑现**的预置缺口缝字

## 5. live 前瞻（本单离线交付，live 另拍）

部署后：KB 无暴露的新题材发酵题，或 `unreachable && !reopen` 的修复轮，`missing_mandatory_capability` 与 chain_mapping 类 marker_loss 归零；公开稿出现缺口声明。探针用户独立命名 `probe-w2-verify-<date>`。
