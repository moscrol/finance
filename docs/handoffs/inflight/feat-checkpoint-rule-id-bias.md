# feat/checkpoint-rule-id-bias（INDEX #24：可证伪点带 `rule_id` + 登记时回显四态 + 偏差目录 v1）

树 `/Users/a77/fwp-wt-checkpoint-bias`，基线 `gitea/main@c6e702a6`（2026-09-05 派单时核实），分支 `feat/checkpoint-rule-id-bias`。开 PR 时 `gitea/main` 已走到 `8af84269`（RAG worker 瘦身 #587 / knowhow #588 / 两份交接 / INDEX #21 行），与本支改动**零文件重叠**，`gitea_pr.py conflict-check` clean；本支未 merge 新 main，让门禁收据与分支尖一一对应，合并由 Gitea 做。
工单 `docs/superpowers/specs/2026-09-04-checkpoint-rule-id-bias-catalog-workorder.md`；设计稿 §10.2 第一条、§10.4 前两行。
解释器 `.venv-workbench/bin/python`。PR [#592](http://127.0.0.1:3300/a77/finance-workspace-private/pulls/592)（已开，未合；合并等用户确认）。前端零改动（没跑任何前端命令）。

## 这个分支做什么

用户理念「理性的决策要巩固，非理性的决策要 AI 帮我们规避」的机器形态，按**过程**而不是结果定义（设计稿 §10.2 第一条）。四个提交是加法、五个既有 `register_checkpoint` 调用方零改动：

1. `intelligence/services/checkpoints.py`（仍只用标准库）：`register_checkpoint` 新增可选 `rule_id / rule_verdict / rule_receipt / bias_flags`，空则不写出（旧记录形状不变）；`rule_id` 用与 `methodology_backtest.rules.RULE_ID_RE` 逐字相同的正则校验（那个包会拉进 duckdb，所以抄一份，测试断言两处一致），非法抛 `ValueError` 且不落盘；拆出纯函数 `build_checkpoint_record`（CLI 先对同一条记录跑扫描再落盘，id/ts 一致）；`calibrate` 新增 `Calibration.by_rule`（key = `rule_id`，无 `rule_id` 的判断不进），`render_report(cal, rule_receipts=)` 新增「按规则」段——每行 `rule_id / n / 命中率` 并列该规则最近收据的 `四态 N p p0 Wilson（日期）`（收据由调用方传入，`calibrate` 不读文件系统）；`render_calibration_for_prompt` 未动。
2. `intelligence/cli.py` `checkpoint register --rule-id / --receipts-dir`：与经验卡同源同口径地 `latest_receipt`，把 `verdict / _path` 写进记录并回显一行 `规则 <id> 最近收据：<四态中文>（<四态>） N= p= p0= Wilson[,]（日期）`；无收据回显 `尚无收据——先跑 scripts/methodology_backtest.py run`；**两种都登记成功、退出码 0**；非法 id 退出码 2 不落盘。`calibrate --receipts-dir` 与 `--json.by_rule[].receipt`。
3. 新模块 `intelligence/services/checkpoint_bias.py`：偏差目录 v1 四条纯函数 + `scan(checkpoint, *, checkpoints, verdicts, label_lookup, rule_fire_lookup, entity_lookup=None, calendar=None) -> list[BiasFlag]` + `classify / summarize / render_flag_lines` + 真库只读数据源 `LedgerDataSources`（三个 callable + 日历，任一源打不开只记 `notes`，对应条目 unverifiable）。`BiasFlag{code, severity∈{info,warn}, reason, evidence}`；数据不齐给 `<code>_unverifiable`（`severity=info`，`evidence.missing` 说缺什么）；不适用不产 flag。
4. `cli.py` 登记后立刻 `scan`，flags 打在回显块下（`⚠` = warn，`·` = unverifiable），`bias_flags`（只存 code 列表）写进记录；任何扫描异常只打一行 stderr、不写 `bias_flags` 键、登记照常。新子命令 `checkpoint bias-scan [--user] [--since] [--json] [--db-path/--labels-db/--rules-dir]`，只读。

## 四条目录项的口径（实现即定义，改了要同步设计稿 §10.2）

| code | 阳性条件 | unverifiable 条件 | 数据源 |
|---|---|---|---|
| `late_streak` | D0 上任一映射到的 `sector_ts_code` 的 `dual_red_streak >= 4`（`LATE_STREAK_GE`），或 `limit_heat_rank <= 3` 在 D0、D0-1、D0-2 三个交易日连续成立 | 无 `themes` / 无日历 / 映射不到 / 主库不可用 / D0 上映射到的代码没有任何标签行（含 NULL） | themes → `dim_sector.sector_name` 精确匹配 ∪ `config_theme_sector_link.theme`（真库该表为空）→ 旁路库标签 |
| `post_miss_streak` | 同 `category` 的其他判断，登记时刻**已知**（`checked_at <= ts`）的终态判定按 `checked_at` 排序，末尾连续 miss ≥ 2，且最后一次 miss 距本条 `ts` ≤ 3 个交易日 | 无 `category` | 只用台账；无日历退化为自然日（`evidence.calendar="natural_days"`） |
| `rule_not_firing` | 带 `rule_id`，规则在 D0 的事件集（编译器 `[D0, D0]`）不含任一映射到的代码 → `warn` | 无日历 / 规则文件不存在 / 旁路库不可用 / 个股规则（v1 不映射股票名 → `stock_ts_code`）/ `themes` 映射不到 | 规则文件（取最高版本）+ 旁路库 |
| `revenge_reentry` | 之前登记（`ts` 更早）且与本条共享 ≥ 1 个 `themes ∪ stocks`（去空白、小写）的判断里，取终态 `checked_at` 最近的一条：它是 miss 且距本条 `ts` ≤ 5 个交易日 | 无 `themes` 也无 `stocks` | 只用台账；无日历退化为自然日 |

- **D0**：`ts` 换成北京时间（无时区按 UTC 解释，`checkpoints._now()` 写的就是 UTC）；15:00 收盘后取当日、收盘前取前一日；再落到旁路库日历上 ≤ 该日的最近交易日。确认日语义：盘中登记看不到当日标签（测试 `test_late_streak_d0_uses_previous_day_before_close`）。
- **只用登记当时已知的结果**：`_terminal_before(verdicts, ts)` 过滤 `checked_at > ts` 的判定，再按 `_latest_terminal_verdicts` 口径「每 id 最后一条终态」。离线 `bias-scan` 对旧判断因此是**当时视角**的读数。
- `rule_not_firing` 直接跑编译出的事件查询取完整事件集（`runner.execute_compiled` 只留 12 条样例，拿不到全体实体）；SQL 与参数与 runner 完全同一份编译产物。

## 决策与被否方案

- **`RULE_ID_RE` 抄进 `checkpoints.py`** / 否 `from methodology_backtest.rules import RULE_ID_RE` / 那个包 `labels.py` 顶层 import duckdb 与 `market_feature_store.analysis`，会打破模块 docstring「只用标准库」的承诺；抄本由 `test_rule_id_regex_mirrors_methodology_backtest` 钉住。
- **先 `build_checkpoint_record` 再 `scan` 再 `register_checkpoint(ts=preview.ts, bias_flags=)`** / 否「登记后再改那一行」（append-only 台账不能回写）/ 否「flags 不入记录」（工单要 `bias_flags` 在记录里）。扫描异常 → 不写 `bias_flags` 键（= 没扫），空列表 `[]` = 扫了没命中，两者可区分。
- **`scan` 多两个可选 kwarg `entity_lookup` / `calendar`** / 否把映射与日历塞进 `label_lookup` / 工单签名只列四个注入点，但 themes → 代码映射与交易日日历是两种独立数据源，各自缺失的降级不同（映射缺 → 两条 unverifiable；日历缺 → 两条 unverifiable + 两条自然日）。
- **themes 只做精确名匹配** / 否 LIKE 模糊 / 工单红线「映射不到就 unverifiable，不要硬猜」；真台账 18/83 因此 unverifiable（CPO / CXO / 金刚石散热 / 医疗 / 电子元器件 / 液冷 / EDA… 不在 `dim_sector`）——这是正确输出，治它的是补 `config_theme_sector_link`（真库现为 0 行），不是放宽匹配。
- **一个题材名映射到多个代码时（`.TI` 旧代与 `.FP` 新代并存，如 人形机器人 → `886069.TI` + `990049.FP`）全部带上**，任一代码有标签行就能判；`.TI` 标签止于 2026-07-24、`.FP` 起于 2026-06-23，只映到 `.TI` 的题材在 8 月后就是「D0 上没有标签行」的 unverifiable（真台账 2 条：`886019.TI`）。
- **`post_miss_streak` 的「同类连错」用登记时刻已知的终态** / 否用今天全部 verdicts / 后者在离线扫描里会拿未来结果给过去的登记贴标签，正是结果偏差。
- **`revenge_reentry` 取共享标的判断里终态最近的一条**，不是登记最近的一条 / 后者若还没终态就永远不产 flag，而刚落空的那条才是「连错」的证据。
- **个股规则的实体对照 v1 不做**（unverifiable，`missing` 写明）/ 否用 `fact_stock_daily.stock_name` 反查 ts_code / 全表扫、且不在工单证据路径表里；待 P2 与自动 `rule_id` 映射一起做。
- **不做 `--no-bias-scan` 之外的任何拦截**：任何 flag、任何异常都不改退出码、不改 verdict。

## 真库读数（2026-09-05，全程只读；`/tmp/ck24/bias-scan-linxiaoqi5111.json`）

`checkpoint bias-scan --user linxiaoqi5111`（83 条，旁路库日历 413 日至 2026-09-02，`LABEL_VERSION` v2，主库 ✓，规则目录 ✓）：

| code | 命中 | unverifiable | 干净 | 不适用 |
|---|---:|---:|---:|---:|
| `late_streak` | 2 | 18 | 63 | 0 |
| `post_miss_streak` | 34 | 0 | 49 | 0 |
| `rule_not_firing` | 0 | 0 | 0 | 83 |
| `revenge_reentry` | 9 | 0 | 74 | 0 |

- `late_streak` 命中 2：`ck-2026-07-07-28ef9f` / `ck-2026-07-08-da8291`（机器人 `885517.TI` 热度前三连续 3 日）。18 条 unverifiable 里 16 条是题材名不在 `dim_sector`（CPO ×3、金刚石散热+第三代半导体散热 ×2、CXO ×2、医疗 ×2、电子元器件 ×2、有色冶炼装备、液冷、EDA（电子设计自动化）、化肥、IP 各 1），2 条是只映到旧代 `886019.TI` 而 D0 在 8 月后无标签行。
- `post_miss_streak` 命中 34：真台账 62 miss / 7 hit，「生命周期推演」一类从 08-13 起连错 21 → 50 条，之后每次登记同类都在 0–1 个交易日内——这条在真台账上主要是在说「`logic_lifecycle` 自动登记的判断整体在连错」。
- `rule_not_firing` 83 条全部不适用：旧判断没有 `rule_id`（工单预期）。
- `revenge_reentry` 命中 9：同题材（CXO / 创新药 / 医疗 / 通信 / 光通信 / 医药 / 算力租赁 / 中特估）上一条刚落空 0–3 个交易日又登记。
- 跑前跑后对账：主库 33 张 `fact_*` 行数与 `max(updated_at)` 全等、旁路库 `history_build_meta.computed_at`（labels 2026-09-04 14:21:47 / outcomes 14:22:00）不变（`/tmp/ck24_before.json` == `/tmp/ck24_after.json` == `/tmp/ck24_after2.json`）。

`replay-test` 用户登记回显（本树 `methodology/receipts/` 由 `scripts/methodology_backtest.py run` 只读生成，gitignore）：

```
已登记可证伪点 ck-2026-09-04-82502a（到期 2026-09-12｜人工判定）
  人形机器人板块连续双红后 5 个交易日仍上涨（INDEX #24 回显验收）
  规则 dual_red_streak3_continuation 最近收据：与基准不可区分（not_distinguishable） N=88 p=68.2% p0=58.0% Wilson[57.9%,77.0%]（2026-09-04）
  偏差目录（只提示不拦截）：1 条
    ⚠ rule_not_firing：偏离自己的规则：dual_red_streak3_continuation@v1 在 D0=2026-09-02 对 ['886069.TI', '990049.FP'] 未触发（当日事件集 0 个实体）——你引用了这条规则，但按它今天并不该出这个判断
  → 到期跑 `checkpoint recheck --user replay-test --apply`
```
记录：`~/.local/share/finance-workbench/users/replay-test/checkpoints.jsonl` 末行含 `rule_id / rule_verdict=not_distinguishable / rule_receipt / bias_flags=["rule_not_firing"]`。`--rule-id nope_rule` 回显「尚无收据」，两种退出码均 0。

## 已验证

- 定向测试（`test_checkpoints.py` / `test_checkpoint_bias.py` / `test_prime.py` / `test_user_memory.py` / `test_experience_cards.py` / `test_checkpoint_writeback.py` / `test_checkpoint_recall.py` / `test_checkpoint_cron.py`）：**168 passed / 0 failed**（新增 `test_checkpoints` 17 例、`test_checkpoint_bias` 35 例）。
- **变异测试**：把 `check_rule_not_firing` 的 `if fired_here: return None` 反成 `if not fired_here`，`test_checkpoint_bias.py` 4 红（`test_rule_not_firing_positive_when_entity_absent_from_event_set`、`test_rule_not_firing_negative_when_any_mapped_code_fired`、`test_rule_not_firing_real_compiler_on_mini_labels_db`、`test_scan_collects_all_four_and_classify_summarize_count`）/ 31 绿；恢复后 35/35 绿，模块 `git diff` 为空。
- 工单验收逐条：`register_checkpoint(rule_id=…)` 三字段 ✓ / 不给时无键 ✓ / `"Bad Id"` 抛且不落盘 ✓；五个调用方零改动、既有测试绿 ✓；合成台账 3+2+4 → `by_rule` 恰 2 项、`n=3, hit_rate≈0.667`、`by_category` 9 条不变 ✓（用 `rule_a / rule_b`：工单示意的 `r1` 不满足 `RULE_ID_RE` 的 3 字下限）；`render_report` 传收据行含 `p / p0 / N / 四态`、不传显示「无收据」✓；CLI 两种情形退出码 0 ✓；四条各三组夹具 ✓、无 `rule_id` 时 `rule_not_firing` 零 flag ✓；无旁路库时 `post_miss_streak` / `revenge_reentry` 自然日照算、另两条 unverifiable ✓；真库 `bias-scan` 83 条退出码 0 ✓；`ruff` 0 ✓、`layer_audit` ERROR 0 ✓、`check_unread_fields` 无新增 ✓；库只读对账 ✓；`ledger-map.md` 第 14 行 ✓、设计稿 §10.2 四个名字一致 + 实现指针 ✓。
- 全量主门禁 `bash scripts/run_main_gate.sh` @ `a8008e54`（干净树）：**7763 passed / 0 failed / 15 skipped / 1 xfailed**，ruff 0，pytest 317.8s；收据 `~/.finance-runtime/test-receipts/20260904T184329Z-a8008e54.json`（不是 `latest.json`），`python scripts/check_test_receipt.py <该文件> --expect-revision $(git rev-parse HEAD)` 退出码 0（revision / 解释器 / 依赖指纹 / 干净树全部 ✓）。`layer_audit.py` ERROR 0；`check_unread_fields.py` 无新增（当前 39 文件 / 96 字段 vs 基线 100）。分支尖之后只多本交接 + INDEX 的 docs 提交，不改代码（`tests/test_ledger_spec_crosswalk.py` 只查 R- 号引用，本单不取号）。

## 未验证 / 已知边界

- `config_theme_sector_link` 真库为空，题材映射目前全靠 `dim_sector` 精确名匹配；补这张表是让 `late_streak` / `rule_not_firing` 覆盖率上去的正道。
- 个股规则（`first_board_new_high_1y_5d`）的 `rule_not_firing` 一律 unverifiable（未做股票名 → `stock_ts_code`）。
- `late_streak` 的热度分支把「该日无 `limit_heat_rank` 行」当作「不在前三」（热度表只列有名次的题材）；若整日热度表缺失会低估而不是误报。
- `post_miss_streak` 在真台账上被「生命周期推演」一类的长连错主导（34/83），阈值 `≥ 2 / ≤ 3 日` 是工单写死的；要不要按 `source` 再分层（自动登记 vs 手工登记）留给读数出来之后决定，本单不动。
- `bias-scan --since` 按 `ts` 的 UTC 日期字符串比较（台账 ts 是 UTC）。
- 未对 `judgment_extract / framework_interpretation / track_contract / logic_lifecycle` 推断 `rule_id`（工单非目标）；Workbench UI / API 无登记入口（非目标）。
- 收据 `generated_at` 是 UTC、文件名是本地日期（`receipts.py` 既有行为），回显里的日期取 `generated_at[:10]`，跨零点会比文件名早一天——只是显示，不影响任何判定。

## 下一步

1. 用户确认后合入（不合 main 是本单红线；CI 绿等价检查见门禁读数）。
2. 补 `config_theme_sector_link`（或给 `dim_sector` 加别名表）→ 重跑 `bias-scan` 看 `late_streak` unverifiable 从 18 掉到多少。
3. P2「LLM 提议者」时给四个自动登记方带 `rule_id`，`rule_not_firing` 才会在真台账上有读数；同时做股票名 → `stock_ts_code` 映射。
4. 让 `checkpoint recheck` / `calibrate` 报告里按 `bias_flags` 分层看命中率（「带 flag 的判断命中率是否更低」是这套目录的自检）。

## 踩过的坑

- 用 `ps | rg -c 'python -m pytest'` 数其他 agent 的 pytest 会把 **zsh 包装进程**（命令文本里含 pytest，包括自己的轮询循环）也数进去，看起来永远非 0；要按 `^\S*[Pp]ython\S* -m pytest` 只数解释器进程。
- 工单验收文本里的 `r1 / r2` 不是合法 `rule_id`（正则要求 3–64 字），测试用 `rule_a / rule_b`。
- 本机 UTC 时钟 2026-09-04 18:xx 时本地已是 09-05，`_make_id` 用 UTC 日期，所以 replay-test 记录 id 是 `ck-2026-09-04-…`；`resolve_d0` 按北京时间算 D0，两者口径不同是刻意的（id 只要稳定，D0 要对齐交易日）。
- 在本树跑门禁期间不能改本树文件（收据会 dirty），交接先写在 `/tmp` 再拷回来提交。
