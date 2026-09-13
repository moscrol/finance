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
| 台账登记 | 本轨新对象（协议 / 预测 / 观察 / 收据 / 曝光）全在私有根下的 `research_validation/` 目录，唯一 writer 是 `Repository` | 06 在 `docs/learning/ledger-map.md` 登记格式、唯一写入者、派生视图、用户态路径后启用 | 本文件 + PROGRESS.md「对象布局」 |
| 曝光台账完整性 | `analysis_policy.exposure_ledger_complete` 缺省 False → 一律 exploratory | 06 确认该 owner 的历史访问已全部经 `record_exposure` 登记后，冻结时显式置 True | `contracts.validate_analysis_policy` |
| 首例真实 D0 | 未冻结任何真实协议；无真实前向样本 | 06 接线后按 §9 以有效 D0 输入冻结；非交易日 / 源不鲜则预建下个合格日协议、保持 pending | `freeze_study` → `register_forecasts`（D0 盘后）→ `settle_outcomes`（到期）→ `evaluate_study` |
| R-号 | 未领取 | 03 产生真实实验时走 `scripts/claim_ledger_id.py claim --branch feat/research-validation-03`，不手工编号 | — |

## 已知边界（有意为之，非缺口）

- 曝光匹配按「同实体 + 结果区间相交」的保守口径：看过 S1@D0 的 D+1..D+5 收益，S1@D1 / S1@D2 的 case 也视为已暴露。
- 任何**不是本 study 自己写的**曝光都算外来（含同谱系同框架的新 study）；同方法重试请重评同一 study_id。
- v1 拒绝修订预测：同 (study, case, arm) 改 p 一律 `conflict`；要改基准 / 时间 / recipe 请另开 study。
- 期末未到（或仍有未到期预测）时确认检验封存：收据只有 pending 数与单项，不给平均差 / verdict。
- 历史规则模式的重建标签不是严格 PIT：收据固定带 `unverified_pit` gap，eligible 不因此为 false，但也不得声明「严格时点可知」。
