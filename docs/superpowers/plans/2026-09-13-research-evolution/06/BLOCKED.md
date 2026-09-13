# 06 · 阻塞、跨轨缺口与未做项

更新：2026-09-13。分支 `feat/research-evolution-06-workbench`。

## 1. 阻塞 engineering 的项

**无。** 四个端点、单 writer、两个受控入口、前端内容区都已真实计算并有测试。

## 2. 跨轨缺口（需对应 owner 决定，06 已 fail closed）

| # | 缺口 | 现状 | 责任 | 最小复现 |
|---|---|---|---|---|
| 1 | **04 的 `outcome_identity` 是不透明字符串，03 的曝光台账要结构化身份**（`entity_type / entity_id / as_of / outcome_due / horizon`） | 06 约定可解析写法 `<entity_type>:<entity_id>:<as_of>:<outcome_due>:<horizon>`；解析不出就**拒绝揭示答案**（不能凭空编实体区间去登记曝光，也不能跳过登记直接给答案） | 04 与 03 共同拍：要么 04 的 `ExerciseCase.outcome_identity` 升成结构化对象，要么把这条写法写进 04 的题包合同 | `test_research_evolution_falsification.py::test_reveal_is_refused_when_the_outcome_identity_cannot_be_parsed` |
| 2 | **04 的 `Gap` 没有 `checked_at`**，01/02 的有 | 投影层按封套口径补上本次报告的 `knowledge_cutoff`，不改两边语义 | 02 的 BLOCKED §「命名分歧留给 06」已记同一件事；要统一就统一字段名，别改语义 | `facade._diagnostics` 里那段注释 |
| 3 | **03 的生产结果源没定** | `study_io settle` 没有已授权 `OutcomeSource` 时 fail closed 并打印提示，不猜一个 | 03 BLOCKED「结果源」一条；执行人决定生产用哪个已授权源 | `test_research_evolution_io.py::test_study_io_settle_without_an_authorised_outcome_serve_fails_closed` |
| 4 | **02 的 `effort_estimates` / `request_bindings` 没有生产来源** | 不传就是 `effort=unknown`、补数请求 `legacy_unbound`——如实状态，不是缺陷 | 前者待 05 的观测耗时或用户估时；后者待绑定建立后按 `request_id` 映射 | 02 BLOCKED §2 |
| 5 | **生产诊断策略与题包由谁签** | 06 提供登记入口（`pilot_io register --kind diagnostics_policy/exercise_pack`）；没登记时 `diagnostics` 段是 `unknown(policy_not_registered)`，合成策略会在 `module_status.synthetic` 标出来 | 规则真实生效日归方法 owner | `test_research_evolution_api.py::test_i09_diagnostics_needs_a_registered_policy_and_marks_synthetic` |

## 3. 本轨未做（明确留下，不假装做了）

| 项 | 为什么没做 | 下一步 |
|---|---|---|
| **I13 完整配对试点 E2E**（冻结分配 → 无 run 原流程 → 辅助失败重试 → 人工盲审 → 汇总） | 需要真人参与者与真实凭据；本轮只验证了**机制**（同一 writer、整批拒收、rebuild 同内容 id、synthetic 不升级），没有任何真人数据 | 用户授权后按 05 的 `docs/research-pilots/research-evolution/` 四周表执行；付款只在实际发生后按凭据导入 |
| **I14 后台暂停与端到端耗时** | 05 的 `measure_pair` 已实现「隐藏标签页只暂停应用内活跃时间」的口径并有自己的测试；06 侧要在浏览器里造可见性事件才算验到，本轮 e2e 没做 | 前端补 `visibilitychange` 上报 + e2e 断言端到端耗时不因离开页面变短 |
| **I15 真实前向实验走完一轮** | 没有冻结任何真实协议；`study_io` 的 freeze/register 路径只有 dry-run 与拒收侧测试 | 接结果源后按 03 §9 冻结首个合格日；R 号走 `scripts/claim_ledger_id.py` |
| **绑定条件的 UI 选择器** | 01 只能编译四个标签（`dual_red_strict / volume_surge / market_stage / limit_heat_rank`），其它标签会被拒；本轮 UI 只展示条件结果，不让用户在界面里编条件 | 要做就把标签白名单从 `adapters.SLICE_EVALUABLE_LABELS` 读出来渲染，别在前端再写一份 |
| ~~**`GET evidence-catalog` 的 UI**~~（返修已做） | — | 面板「从现在开始跟踪」表单：选实体/站立日 → 拉受控目录 → 勾版本 → 建绑定（R4） |

## 4. 已知环境事实（不是缺陷）

- 隔离 E2E 的服务**没有市场库**，所以 `RiverEvidenceSource` 一定读不到——e2e 验的正是「读不到就如实说还判不了」。带市场库的完整绑定链路由 `test_research_evolution_api.py` 在固定证据源上覆盖。
- 本工作树此前没装 Playwright 浏览器（既有 e2e 也一起红）；已 `pnpm exec playwright install chromium`。
- `.inspector-toggle` 只在 ≤1179px 露出，所以浏览器用例固定视口 1024×768，不依赖 project 几何。
