# 03 · 阻塞与依赖（2026-09-13）

## 当前阻塞：无

engineering_complete 所需的白名单代码、反例测试、既有回归与门禁均在本轨内闭合，不依赖任何未合入分支。

## 交给 06 的接线依赖（不是本轨缺陷，是设计上的分工）

| 项 | 03 现状 | 解锁条件 / 06 动作 | 恢复入口 |
|---|---|---|---|
| 私有根 | `Repository(root, owner_user_id)` 显式注入，不读 `FORESIGHT_USERS_DIR`、不从 cwd 推断 | 06 用 `userspace.user_space(user).root / "research_validation"` 构造并核实环境变量 | `intelligence/services/research_validation/repository.py::Repository` |
| 可信时钟 | 六个函数都要求 tz-aware `now`；客户端输入里出现 `now/registered_at/eligible` 直接拒收 | 06 在服务端取 now 传入，输入包不得覆盖 | `service._guard` |
| PIT 收据校验 | `PitVerifier` 是端口（`verify(ref) -> {verified, pit_grade, knowledge_cutoff?}`）；无校验器一律 `unverified` + gap | 06 接现有 capture / replay 收据实现校验器 | `service.register_forecasts(pit_verifier=...)` |
| 结果源 | `OutcomeSource` 端口；eval 侧已有旁路库实现 `LabelsDbOutcomeSource` | 06 决定生产用哪个已授权源；版本 / 日历不一致会被 `settle_outcomes` 整批拒绝（不写） | `intelligence/eval/research_validation/outcome_source.py` |
| 投影契约对齐（§4.5） | `projection_hash` 接受两种形状：河 `ContextProjection.projection_hash`（`cp:`+16 hex，常量从 `river_projection` import）与规则臂字段投影 sha256。规则臂的「投影」= 实际读到的标签字段（`eval/research_validation/rule_two_bucket.evaluate_condition`），不是 ContextProjection | 人工 / LLM 臂由 06 用 `river_projection.project(...)` 生成投影，把 `projection_hash` 与 `input_refs.present_tracks` 一起传进 `register_forecasts`；删轨 = 从 `present_tracks` 去掉该轨。**待 06 拍**：UI 路径的 forward 人工预测是否必须带 `projection_hash`（§4.5 硬规矩 5「台账拒收没有它的对象」，03 v1 只校验形状、不强制存在） | `contracts.validate_projection_hash`；臂合同 `allowed_fields / removed_track{track_id, fields, derived_fields}` 已按「轨 → 字段」建模，可加 `allowed_tracks` 而不破旧对象 |
| 台账登记 | 本轨新对象（协议 / 预测 / 观察 / 收据 / 曝光）全在私有根下的 `research_validation/` 目录，唯一 writer 是 `Repository` | 06 在 `docs/learning/ledger-map.md` 登记格式、唯一写入者、派生视图、用户态路径后启用 | PROGRESS.md「对象布局」 |
| 曝光台账完整性 | `analysis_policy.exposure_ledger_complete` 缺省 False → 一律 exploratory | 06 确认该 owner 的历史访问已全部经 `record_exposure` 登记后，冻结时显式置 True | `contracts.validate_analysis_policy` |
| 首例真实 D0 | 未冻结任何真实协议；无真实前向样本 | 06 接线后按 §9 以有效 D0 输入冻结；非交易日 / 源不鲜则预建下个合格日协议、保持 pending | `freeze_study` → `register_forecasts`（D0 盘后）→ `settle_outcomes`（到期）→ `evaluate_study` |
| R-号 | 未领取 | 03 产生真实实验时走 `scripts/claim_ledger_id.py claim --branch feat/research-validation-03`，不手工编号 | — |

## 设计文本缺口（2026-09-13 补发说明第 1 条）

09-06 统一 spec 的 §2.3 / §3.3 情景树 / §4.4 区间契约 / §4.5 投影契约 / §4.6 事件锚点 / §5 飞轮，以及 09-05 spec §14、BP v1.2，在 `gitea/main` 上没有文本，只在主检出树里是未提交改动。03 本轮**只读**了主树的 §4.5（`/Users/a77/finance-workspace-private/docs/superpowers/specs/2026-09-06-personal-research-calibration-endstate-design.md` 第 253 行起），据此做了上面「投影契约对齐」这一刀；代码侧对齐的是 `gitea/main` 上已在的 `intelligence/services/river_projection.py`。这三份文件的提交由改它们的会话负责，03 不动。

## 「不荐股」与 03 的关系（补发说明第 2 条）

03 首版限板块（`contracts.DEFAULT_ENTITY_TYPE = "sector"`，规则臂强制）；forward 人工登记的 `entity_type` 不过滤个股。不荐股约束的是对外渲染输出，属渲染层，不在 03 范围；03 也不碰观察剧本硬门。

## 已知边界（有意为之，非缺口）

- 曝光匹配按「同实体 + 结果区间相交」的保守口径：看过 S1@D0 的 D+1..D+5 收益，S1@D1 / S1@D2 的 case 也视为已暴露。
- 任何**不是本 study 自己写的**曝光都算外来（含同谱系同框架的新 study）；同方法重试请重评同一 study_id。
- v1 拒绝修订预测：同 (study, case, arm) 改 p 一律 `conflict`；要改基准 / 时间 / recipe 请另开 study。
- 期末未到（或仍有未到期预测）时确认检验封存：收据只有 pending 数与单项，不给平均差 / verdict。
- 历史规则模式的重建标签不是严格 PIT：收据固定带 `unverified_pit` gap，eligible 不因此为 false，但也不得声明「严格时点可知」。
