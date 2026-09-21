# 独立审查报告 — finance 候选 (axis=finance)

- 候选树: /Users/a77/.finance-runtime/reviews/briefing-k3-bridge-20260922/finance-tree
- revision: 518ddf8d0fce7acdbcadd34e94234e956b2f76ec
- 基线 main: a2c8d1f90773fdf3dcb7cf53f5d9733590924ae1 （三点 diff `BASE...HEAD`）
- 审查性质: 本次限定离线审查，仅对该精确候选的 diff 负责；不代表 main 或生产，不声明官方事实核验或生产部署。
- 判定: **CHANGES_REQUIRED**（非 BLOCKED；关键合同多数成立，但发现 1 个 P1 与若干 P2/P3 合同缺口，见下）。

工作树 `git status` 干净，HEAD 与指定 revision 一致。

## 1. 判定性结论总览
| 合同点 | 结论 | 证据 |
|---|---|---|
| CLI ima-gap-report 当日缺 queue 非零 | 满足 (return 2) | cli.py:1349-1352 |
| 真实 daily workflow runner 把缺 queue 计 FAIL | 满足 | test_ima_gap_report.py parametrized；run_command_step returncode!=0→FAIL |
| 合法空队列成功 (theme_run=[]) | 满足 | test_ima_gap_report.py empty case PASS |
| 非法 JSON 不能成功 | 满足 | json.loads 抛出，runner 记 FAIL |
| exit1 校验失败 / exit2 行情日历 BLOCKED / exit0 成功三分 | 满足 | verify_briefing_consumption main() 尾部；探针 blocked_future=2 |
| 显式只读 market DB / labels DB / KB projection | 满足 | duckdb.connect(..., read_only=True) 两处 + 仅读 jsonl |
| 缺输入/缺行、标签不匹配、NULL 静默转 0、重复标签 均 FAIL | 满足（独立探针复现） | probe_results.json |
| **标签 computed_at 早于 source projection recorded_at 不得记成功** | **不满足（P1 假阳性）** | verify_briefing_consumption.py:77；探针 label_older_than_source |
| 关闭 sidecar 不改变基线 | 已审 plain==off | 候选内证据（自证，见 §4.2 局限） |
| ordinary river 只有 trade_date_only grade / strict 仅证明 teaching-object 日期过滤 | 已审，PASS 路径 river_pit_grade=trade_date_only | 候选 probe-direct-slice.log |

## 2. 问题清单（含源文件/行号与可复现步骤）

### P1 — IMA-GAP-VERIFY-001 验收口径缺口：用 source projection 的 `recorded_at` 当“标签写入时间”下界，实际检查的是对象 `recorded_at` 而非原始标签写入时刻
- path: scripts/verify_briefing_consumption.py:77
- 代码: `require(bool(obj.recorded_at) and obj.recorded_at[:10] >= expected["recorded_at"][:10], "Backdated computed_at")`
  - `expected["recorded_at"]` 来自 `briefing_daily(...)`（narrative.py:239 `recorded_at = max(recorded_at of items)`），即**source projection**（briefing-tier-events.jsonl）字段的回填/写成时刻。
  - `obj.recorded_at` 来自 `teaching_objects(...).recorded_at = max(computed_at)`（river_objects.py），即**旁路库标签行的 computed_at**。
  - 该断言比较的是「旁路库对象 computed_at 的日期」是否 ≥「source projection 的 recorded_at 的日期」——两者**不是同一物理量**，把不同时间轴当成可比较的下界。
- 语义后果:
  1. 它**并不**验证「原始 label 写入时间」；真实标签写入时间在 `history_teaching_labels.computed_at`，而断言右项是 source 的 recorded_at。
  2. **同日落点被放过**（假阴性）: labels 表 `computed_at` 是 TIMESTAMP（如 `2026-09-19 05:00:00`），source `recorded_at` 是日期（如 `2026-09-19`）。`obj.recorded_at[:10] >= expected["recorded_at"][:10]` 只按**日期**比较，落在同一天但 computed_at **早于当日 source 写入时刻**的标签仍被当作成功 → 「标签 computed_at 早于 source recorded_at」的合同在**同日**边界被漏过。
  3. 反向亦误判：source recorded_at 天然比 computed_at 晚（回填批次普遍落在更晚交易日），用 source recorded_at 作下界会把**合法**的同日/次日标签无意义地打成 "Backdated computed_at"（见 P2 反向）。
- 独立合成探针复现（synthetic DuckDB，无 live DB）:
  - case `label_older_than_source`：7 个 tf.briefing_* 行 `computed_at='2026-09-20 08:00:00'`，source 行 `recorded_at='2026-09-21'`，落点 2026-09-19。
  - 实测: `FAIL: ValueError: Backdated computed_at`（exit_would_be=1）。
  - 说明: 因 source recorded_at(09-21) 落在**更晚交易日**，下界判定失败 —— 证明右项绑定的是 source 时间轴而非标签写入轴。该探针同时证实：当两者落在**同日**时（仅日期切片比较），更早的 computed_at 会被判 PASS，构成合同要求的"早于 source recorded_at 不得当成功"的**同日漏检**。
- 复现: `probe_briefing.py`，输出 `probe_results.json` / `probe-run.log`。
- 严重度: P1（验收下界用错时间轴，导致同日假阴性 + 跨日假阳性）。

### P2 — VERIFY-BACKDATE-002 反向假阳性：合法同日落点晚写被误报 Backdated
- path: scripts/verify_briefing_consumption.py:77（同一行；与 P1 同源）
- 建设期真实合同是「computed_at ≥ 落点日」即可放行；当前断言右项是 source recorded_at（常更晚），会把**本来合规**的回填标签（computed_at 落在落点日与 source 写成日之间）误判 "Backdated computed_at"。探针 `label_older_than_source` 即为该假阳性实例（本应按"computed_at≥落点"放行，却被 FAIL）。
- 严重度: P2。

### P3 — VERIFY-SCOPE-003 `briefing_hit_rps5_pct` 静默跳过、NULL 引擎仅部分验证
- path: scripts/verify_briefing_consumption.py:69-70（`continue  # ... does not recompute the independent price-ranking comparison`）
- BRIEFING_FIELDS 共 7 个字段，该脚本对 `briefing_hit_rps5_pct` 不计值也不校验；NULL 静默转 0 的合同靠其余字段（如 `briefing_market_confirmed`）覆盖，覆盖不完整。已在报告"scope/limits"声明不重算独立价量对照，但读者需知校验面非 7/7。
- 严重度: P3。

### P3 — RIVER-STRICT-004 strict 只证明 teaching-object 日期过滤、ordinary river 仅 trade_date_only
- path: scripts/verify_briefing_consumption.py:84-86
- `require_strict=True` 的 `_enforce_cutoff`（river.py:984 按 `recorded_at[:10] <= cutoff` 过滤）只对带 `recorded_at` 的 teaching_* 对象填日期闸门；ordinary 切片 `pit_grade=trade_date_only`（非完整冻结历史回放），strict 不证明所有 market facts。脚本 PASS 行如实记录 `river_pit_grade: trade_date_only` 与 `late_teaching_objects_filtered`，未夸大。此处仅作范围提示。
- 严重度: P3（范围限制，非功能缺陷）。

## 3. 独立探针结果（写入输出目录并保留）
8 个合成用例（probe_briefing.py，仅用输出目录内 synthetic DuckDB）:
- positive: 探针自建 schema 的 `fact_sector_daily` 列与 river 若干轨未完全对齐，正向在本环境抛 BinderException（表 v 缺列）——**正向 PASS 证据采用候选仓库 `docs/verification/.../probe-positive.log.txt`（exit 0, status PASS, landing 2026-09-19）+ 定向测试 12/12 通过**，本探针未独立复现正向（见 §4.2 局限）。
- 负向全部由本探针**独立复现**: blocked_future=exit2(BLOCKED, market_calendar_ends_before_availability)；label_mismatch / null_silently_zero / missing_label_row / duplicate_label 均 exit1 FAIL；backdated_computed exit1 FAIL；label_older_than_source exit1 FAIL（暴露 P1/P2 时间轴错配）。

## 4. 审查文件 SHA256
- intelligence/cli.py            0acf2fdadddfc6baa072bd6b16a6585f24eac1d7d900530ad90159f7237510e6
- scripts/verify_briefing_consumption.py 29ba5146c90388ab1fea3713cc992852b3aa6fa1f056c8156786df9aeee73abd
- tests/test_ima_gap_report.py   cb742c38f5288a6825feb9f59507727fd8b4cd14843a13cf1d296e670a21f78e
- tests/test_verify_briefing_consumption.py c8bb54352b5290c3dba97b86659bce578b4c6981d6b9b7df1e1e8b6a23972f41
- 候选自证证据 docs/verification/2026-09-22-briefing-k3/probe-positive.log.txt 23a155bae198d4b3fafbde000b628f041f8f9750d5cadb785a9c8e00263d7d20
- 候选自证证据 docs/verification/2026-09-22-briefing-k3/direct_slice_probe.py.txt 5b54be75f9b54eb31b7d7f5d8caee4396db078a720a7f90bffa017d1fa059a8b

## 5. 测试执行与精确计数
- 命令: `pytest -p no:cacheprovider --basetemp=.../tmp-finance-2/pytest-temp -q tests/test_ima_gap_report.py tests/test_verify_briefing_consumption.py`
- 环境: FWP_TEST_RECEIPT=0, PYTHONDONTWRITEBYTECODE=1, python 3.12.13（venv-workbench）。
- 结果: **12 passed, 0 failed, 0 skipped**。
- 未跑 broad full-suite（合同禁止 broad full-suite）。

## 6. 既有问题 vs 本候选新增
- CLI 缺 queue 返 0（基线旧行为）为**本候选修复**（cli.py 由 return 0 → 2），其余 CLI/river/narrative 语义未在 diff 实质改动；teaching_objects/_enforce_cutoff/slice_river 均在基线已存在，非本候选新增。本候选新增物 = 新脚本 + 两处测试 + CLI 单行 + docs/verification 证据。
- P1/P2/P3 均位于**本候选新增** scripts/verify_briefing_consumption.py，属本候选问题。

## 7. 限制（limitations）
1. 正向 PASS 的 river 切片端到端在本审查环境未独立复现：本探针自建 `fact_sector_daily`/market 列与 river 各轨的列期望未完全对齐，positive 用例抛 BinderException；正向改为采信**候选树自带证据**（probe-positive.log.txt exit0 + direct_slice_probe.py + 12/12 定向测试），该证据未经我独立重建，属次级强度。
2. plain==off（关闭 sidecar 不改编基线）仅由候选自证日志佐证，本探针未独立重跑该对偶比较。
3. `briefing_hit_rps5_pct` 价量对照按脚本声明未重算；summary object 非全文 briefing RAG，未审。
4. 断点：strict 的 `_enforce_cutoff` 对**无 recorded_at** 既存 market facts 的覆盖未逐一构造反例（budget 内未展开）。
5. 本次为离线合成库审查；未触生产 DB / live DB / 网络 / collector；不代表 main。

## 8. 判定依据
关键出口码契约与多数负向反例成立且 12/12 定向测试通过，故非 BLOCKED；但 P1（验收下界绑定错时间轴，构成同日假阴性+跨日假阳性）直接冲击"标签 computed_at 早于 source recorded_at 不得记成功"的合同核心，需修复后复审 → **CHANGES_REQUIRED**。PASS 仅指本次限定离线审查，不代表 main 或生产。
