# feat/theme-stage-vocab-g04 · 2026-09-15 · G-04 词表统一 + 验收集 9–16 对账

## 这个分支做什么
两件独立交付，都是 2026-09-15 缺口盘点（终局 spec + gap roadmap + 工单 INDEX + 能力升级包 + 研究进化批次五处对账）里排出的无主缺口，刻意避开四条在途线（extraction-first #53 / hithink 接线 / E2 边界 / river 区间投影）：
1. **G-04 题材生命周期两套词表统一**（L0 前置）：钦定 canonical = 七段时间线词（酝酿/首发/发酵/主升/分歧/退潮/回流，`tsv-v1`），新模块 `intelligence/services/theme_stage_vocab.py` 是唯一映射源；八阶段诊断细词经 `TO_CANONICAL` 映射同名（映射依据两模块判定条件，与旧 tsc-v0 粗序逐词兼容）；两模块 payload 加 `stage_canonical` + `vocab_version`（additive，细词与叙事 guidance 保留）；`opinion_stage.THEME_STAGE_COARSE` 手工双表退役为派生物（冻结对照锁逐字节不变）；词表进 `UBIQUITOUS_LANGUAGE.md`，「引用必须标模块」在数据层退出。
2. **09-06 spec 最小验收集第 9–16 条对账**：`docs/verification/2026-09-15-endstate-acceptance-9-16.md`。6 条测试钉死；12/15 两条实现在、行为实测过、但缺直接负例——本分支顺手补上（`test_river_anchor_contract.py` 10 条 + `test_checkpoints.py::AttributionGateTests` 3 条）。

## 已验证
- 提交 `c3770e0b`（G-04）+ `7a91ed25`（对账+补测）。ruff 全绿。
- 全量两跑：第一跑 9636P/1F（唯一红 `test_workbench_conversation_integration::test_real_conversation_round_trip_…`，**单跑绿**）；第二跑（含全部新测试）**9650 passed / 0 failed / 77 skipped / 2 xfailed**，exit 0，完整日志 `/tmp/g04-full-pytest-run2.log`。判定第一跑那条是全量语境 flaky，与本分支无关。
- anchor 测试承重性：变异硬规矩 2（`forward_end > knowledge_cutoff` 的 raise）→ 对应测试见红 → 还原全绿。
- 对照集脚本真库只读干跑：131 样本 / 12 题材（`docs/learning/theme-stage-concordance/concordance-set-2026-09-15.csv`），report 未标注时如实「样本不足」。
- `tsc-v0` 版本号无其它消费者、无落库对象引用 [实测 grep]。

## 刻意不做（等创始人对照集裁定，勿抢跑）
- prompt / 渲染层显示词切 canonical；
- canonical 阶段入旁路库 theme 标签 + `LABEL_VERSION` 升版 + 收据重跑（G-04 验收 c）；
- 诊断列历史回填——诊断输入是会话态证据文本，历史无按日落账，对照集标 `gap:no_recorded_diagnosis`，只随后续复盘积累。
- 样本分布偏斜（全在退潮/回流/主升，分歧段被 `MIN_PHASE_DAYS=3` 合并吃掉）已写进对照集 README——若裁定不可接受，改的是 timeline 口径不是词表。

## 下一步
1. 用户过目 → 合并（等确认，不自合）。**合并注意**：`UBIQUITOUS_LANGUAGE.md` 是研究进化批次 06 的「本批唯一修改者」文件，RE06 合流若撞该文件，本分支新增的是独立一节「题材生命周期钦定词表」，按节合并即可。
2. 创始人标注对照集（`docs/learning/theme-stage-concordance/README.md` 有标注规则），`report` 出一致率 → 裁定后开「渲染层切词 + 旁路库入库」下一单。
3. 盘点排出的其余无主缺口（按优先序）：G-11 重放接授课框架（依赖已全解除、零冲突）、#24 checkpoint rule_id+偏差目录（等 RE06 合流）、#23 判官 token 记账（等 judge-calibration 合流，锚点要重核）、G-07 三维并置盘面维（等本分支 G-04 合入）。

## 坑
- 全量读数别用 `pytest | tail` 存证——第一跑的 traceback 被 tail 吃掉，逼着重跑一次全量才能归因。
- `@dataclass` 的脚本经 `spec_from_file_location` 加载时必须先 `sys.modules[spec.name] = m` 再 exec，否则 dataclasses 反查模块拿到 None。
