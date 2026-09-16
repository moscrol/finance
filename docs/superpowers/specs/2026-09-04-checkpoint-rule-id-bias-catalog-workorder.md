# 2026-09-04 可证伪点带 `rule_id` + 登记时回显四态 + 偏差目录 v1 工单（P1，小到中单）

可独立分发。执行方无需读聊天记录，本单自带背景、证据路径、步骤、验收与红线。
INDEX #24。前置：无（方法论回测 P0 / P1 已在 `gitea/main`，PR #573 / #576 / #581）。与 #25 重放引擎互不依赖；#25 若先合，本单的 `rule_id` 字段名与之保持一致（都叫 `rule_id`）。预计一到两天。
设计稿：`docs/superpowers/specs/2026-09-04-methodology-backtest-structured-history-design.md` §10.2 第一条、§10.4 前两行。

## 1. 背景与动机

- 用户 2026-09-04 理念：「理性的决策要巩固，非理性的决策要 AI 帮我们规避。」设计稿 §10.2 把它定义成**过程**条件，不是结果条件：理性 = 决策时有规则可查 + 只用当时信息 + 结果前已登记；非理性 = 偏离自己登记的规则，或命中可从台账算出来的偏差目录。按结果贴标签就是结果偏差，正是统计门要治的病。
- 现状：可证伪点台账（`intelligence/services/checkpoints.py::register_checkpoint`，字段 `id / ts / claim / due / category / source / themes / stocks / metric / framework_version / source_judgment_ts / session_id`）**没有 `rule_id`**（`rg rule_id checkpoints.py` = 0 命中）。经验卡已有（`experience_cards.py:49` `rule_id`，PR #576 统计门 `gate_promotion`），两张台账对「方法论规则」的引用不对称：卡能说「我依据规则 X」，判断不能。
- 后果：`calibrate` 只能按 `category` / `source` 聚合胜率，答不出「你按规则 X 做的判断命中率多少、和规则 X 自己的历史命中率差多少」；也没有任何地方在登记时告诉用户「你引用的规则最近收据是 not_distinguishable」。
- 「AI 帮规避」的机器形态 = 登记判断时系统当场回显三样：对应哪条规则、该规则当前四态、命中偏差目录哪几条。**只提示，不拦截，不改判断**（与 `strategy-evolve` 的 `suggest` 同一原则）。
- **形态决策（写死）**：
  - `checkpoints.py` 保持**只用标准库**（模块 docstring 第 28 行是承诺）：只加字段与聚合维度，不 import duckdb。偏差目录需要旁路库与编译器，另开模块 `intelligence/services/checkpoint_bias.py`（可 import `methodology_backtest.*`，同在 services）。
  - 规则四态从 `methodology_backtest.receipts.latest_receipt` 读，与经验卡同源同口径（`intelligence/cli.py:885–899` 的写法照抄）。
  - 偏差目录只收**能从台账 + 旁路库确定性算出**的条目；算不出的不进目录。设计稿 §10.2 原列「锚定」在 v1 不可计算，替换为「规则未触发」（见 §2.4）。
  - 新字段必须同提交有读者（`scripts/check_unread_fields.py` 棘轮门禁）：`rule_id` 的读者 = `calibrate` 新增 `by_rule` 维度 + `render_report`。

## 2. 目标（每条可验收）

1. `register_checkpoint` 增加可选参数 `rule_id: str | None`、`rule_verdict: str | None`、`rule_receipt: str | None`；记录里三字段均为 None 时不写出（与 `session_id` 同样处理）。`rule_id` 校验用 `methodology_backtest.rules.RULE_ID_RE`（`^[a-z][a-z0-9_]{2,63}$`），不合法抛 `ValueError`。现有 5 个调用方（`cli.py:2958`、`judgment_extract.py:217`、`framework_interpretation.py:237`、`track_contract.py:508`、`logic_lifecycle.py:101`）零改动、行为不变。
2. `calibrate` 新增 `Calibration.by_rule: list[CategoryStat]`（key = `rule_id`，无 `rule_id` 的判断不进此维度）；`render_report` 增加「按规则」段，每行输出 `rule_id / n / 命中率`，并在同一行并列该规则**最近收据的 p / p0 / N / 四态**（收据由调用方传入 `dict[rule_id, receipt]`，`calibrate` 本身不读文件系统——保持纯函数）。`render_calibration_for_prompt` 不动（提示词注入维度不变，避免改 foresight 行为）。
3. CLI `checkpoint register` 增加 `--rule-id` 与 `--receipts-dir`（默认 `methodology/receipts`）：给了 `--rule-id` 就 `latest_receipt`，把 `verdict` / `_path` 写进记录，并**回显**一行：`规则 <id> 最近收据：<四态中文> N=<n> p=<p> p0=<p0> Wilson[<lo>,<hi>]（<收据日期>）`；无收据回显 `规则 <id> 尚无收据——先跑 scripts/methodology_backtest.py run`。**不拒绝登记**。`--json` 输出含 `rule_verdict` / `rule_receipt` / `bias_flags`。
4. 新模块 `intelligence/services/checkpoint_bias.py`，偏差目录 v1 四条，每条一个纯函数 + 一个总入口 `scan(checkpoint, *, checkpoints, verdicts, label_lookup, rule_fire_lookup) -> list[BiasFlag]`，`BiasFlag{code, severity∈{info,warn}, reason, evidence: dict}`。数据不齐时该条返回 `unverifiable` 型 flag（`code` 带 `_unverifiable` 后缀，`evidence.missing` 说缺什么），**绝不猜**：
   - `late_streak`（追高 / 末段登记）：判断关联的板块 / 题材（`themes` → `dim_sector` 名或 `config_theme_sector_link` 映射到 `sector_ts_code`；映射不到 → unverifiable）在登记日 D0（`ts` 所在日之前最近交易日）的 `dual_red_streak ≥ 4`（阈值常量 `LATE_STREAK_GE = 4`），或 `limit_heat_rank ≤ 3` 连续 ≥ 3 日。读旁路库 `history_labels`（只读）。
   - `post_miss_streak`（近因）：同 `category` 最近 ≥ 2 条终态判定均为 `miss`（按 `checked_at` 排序，`_latest_terminal_verdicts` 口径），且本条登记 `ts` 距最后一次 miss 的 `checked_at` ≤ 3 个交易日。只用台账，不触库。
   - `rule_not_firing`（偏离自己的规则）：本条带 `rule_id`，且规则在 D0 对判断关联实体**未触发**——用 `methodology_backtest.compiler` 编译该规则、`runner.execute_compiled` 以窗口 `[D0, D0]` 取事件集，实体不在事件集即触发本 flag（`severity=warn`）。无 `rule_id` → 不适用（不产 flag）；映射不到实体 → unverifiable。
   - `revenge_reentry`（连错再登记）：与本条共享至少一个 `stocks` / `themes` 项的上一条判断，其最新终态为 `miss` 且 `checked_at` 距本条 `ts` ≤ 5 个交易日。只用台账。
   - 交易日计数用旁路库 `history_calendar`；旁路库缺失时 `post_miss_streak` / `revenge_reentry` 退化为自然日（`evidence.calendar="natural_days"` 标明），`late_streak` / `rule_not_firing` 为 unverifiable。
5. `checkpoint register` 登记后立刻跑 `scan`，把 flags 打印在回显块下（`severity=warn` 用 `⚠`），并把 `bias_flags`（只存 `code` 列表）写进记录——**登记本身不因任何 flag 失败**。
6. 新 CLI `checkpoint bias-scan [--user] [--since YYYY-MM-DD] [--json]`：对已有台账全部（或起始日之后）判断离线跑 `scan`，输出每条 flag 计数与命中判断 id 列表；真库上对现有 83 个可证伪点跑一遍，读数写进交接（预期大多数为 unverifiable——旧判断多无 `themes` 映射、无 `rule_id`——这是正确输出）。
7. 测试 `intelligence/tests/test_checkpoints.py`（+：`rule_id` 校验、三字段 None 不写出、`by_rule` 聚合与排序、`render_report` 按规则段）与新增 `intelligence/tests/test_checkpoint_bias.py`（四条各阳性 / 阴性 / unverifiable 三组；`rule_not_firing` 用 `methodology_backtest_selftest` 同款最小旁路库夹具；`label_lookup` / `rule_fire_lookup` 以可注入 callable 形式，测试不连真库）。现有 `test_checkpoints.py` / `test_prime.py` / `test_user_memory.py` / `test_experience_cards.py` 全绿。
8. `docs/learning/ledger-map.md` 第 14 行「个人判断回检」的格式列补 `rule_id / rule_verdict / rule_receipt / bias_flags` 四个可选字段（不加新行——台账没变，字段变了）。
9. 设计稿 §10.2 第一条偏差目录四条的名字与本单 §2.4 对齐（`late_streak / post_miss_streak / rule_not_firing / revenge_reentry`），并注明「锚定」v1 不可计算已替换。
10. 在途交接 `docs/handoffs/inflight/feat-checkpoint-rule-id-bias.md`。

## 3. 非目标（写死认领）

- ❌ 拦截或拒绝任何登记；改判断内容；给 flag 自动打分或进 `verdicts.jsonl`。
- ❌ 改 `render_calibration_for_prompt` / foresight / prime / red_team / user_memory 的注入内容（四个消费者行为不变；`by_rule` 只进 `render_report` 与 `--json`）。
- ❌ 改 `DEFAULT_CALIBRATION_MIN_N`、`gate_promotion`、经验卡任何逻辑。
- ❌ 给 `judgment_extract` / `framework_interpretation` / `track_contract` / `logic_lifecycle` 四个自动登记方推断 `rule_id`——自动映射是 P2「LLM 提议者」的事，本单 `rule_id` 只由人在 CLI 上给。
- ❌ Workbench UI / API 的登记入口（现状只有 CLI 与四个 services 调用方，`rg register_checkpoint` 无 api 命中）。
- ❌ 「锚定」偏差（判断引用了 D0 之前 ≥ n 日的旧值）——claim 是自由文本，v1 算不出，不做。
- ❌ 新的偏差条目（密度爆发、过度自信等）——先让四条在真台账上跑出读数再说。
- ❌ 改 `checkpoints.py` 的标准库承诺（不 import duckdb / methodology_backtest）。
- ❌ 写主库、改 `schema.sql`、改旁路库 DDL。
- ❌ 写 `docs/prediction-ledger.md` / 取 R-号。

## 4. 证据路径表（先读这些，禁止臆测）

| 文件 | 看什么 |
|---|---|
| `intelligence/services/checkpoints.py` `:1–30` docstring、`:177–224` `register_checkpoint`、`:341–424` `CategoryStat / Calibration / calibrate`、`:427` `render_calibration_for_prompt`、`:447` `render_report` | 字段清单与「只用标准库」承诺；聚合形状；哪个渲染器不能动 |
| `intelligence/services/experience_cards.py` `:11–15, :36–101` | `rule_id` 字段命名与 `gate_promotion` 纯函数形状——本单**不设门**，但字段名、收据读法照抄 |
| `intelligence/cli.py` `:471–479` `--rule-id / --receipts-dir` 定义、`:885–899` `latest_receipt` 调用、`:2157–2176` `checkpoint register` 子命令、`:2938–2977` `cmd_checkpoint_register` | CLI 接线照抄；回显放在 `:2973–2976` 的打印块里 |
| `intelligence/services/methodology_backtest/receipts.py` `:248–276` `latest_receipt` | 返回值带 `verdict / stats / _path / generated_at`；跨版本取最近 |
| `intelligence/services/methodology_backtest/rules.py` `:91` `RULE_ID_RE`、`:266` `validate_rule`、`:148` `Rule`（PR #585 后行号；在途第四刀 `feat/methodology-backtest-p1-refuted` 合入后还会漂，以 `rg` 为准） | `rule_id` 合法性；编译前先 validate |
| `intelligence/services/methodology_backtest/compiler.py` + `runner.py` `:134` `resolve_window`、`:189` `execute_compiled` | `rule_not_firing` 用窗口 `[D0, D0]` 取事件集的入口 |
| `intelligence/services/methodology_backtest/store.py` `:28–85` DDL、`:91` `default_labels_db_path`、`:119` `open_labels_db(read_only=True)` | `history_labels`（`dual_red_streak` / `limit_heat_rank` 在 `value_num`）、`history_calendar`（交易日计数）；旁路库只读打开 |
| `intelligence/services/methodology_backtest/labels.py` `:103–113` | 标签名常量（PR #585 后含 `STOCK_LABELS`，`LABEL_VERSION` v2），`late_streak` 只引用 `dual_red_streak` / `limit_heat_rank`；旁路库若是 v1 旧库先 `build-labels` 重建 |
| `market_feature_store/schema.sql` `dim_sector`（:16）、`config_theme_sector_link` | `themes` 文本 → `sector_ts_code` 的映射来源；映射不到就 unverifiable |
| `intelligence/services/checkpoint_resolvers.py` `:66` `_unverifiable`、`:103` `_spec_gap` | 「缺数据 → unverifiable，绝不编造」的降级形状，flag 的 unverifiable 照它写 |
| `intelligence/userspace.py` `:93–98, :126–127` | `checkpoints_path / verdicts_path` 解析；台账在用户大脑目录（`FORESIGHT_USERS_DIR`），仓内 `intelligence/users/` 已冻结勿写死 |
| `scripts/check_unread_fields.py` | 新字段必须与读取点同提交 |
| `scripts/layer_audit.py` docstring | services 不得 import runtime；`checkpoint_bias.py` 可 import `methodology_backtest.*` |
| `skills/theme-fermentation-tracer/scripts/selftest.py`、`scripts/methodology_backtest_selftest.py` | 零凭证最小库夹具形状，`test_checkpoint_bias.py` 的 `rule_not_firing` 用同款 |
| `docs/learning/ledger-map.md` `:14` | 「个人判断回检」行，格式列补字段 |
| AGENTS.md「用户纠偏必落 correction」 | 执行中用户纠正判断即落 |

## 5. 步骤 + 验收

### 步骤

1. 开工三连 `git status --short && git branch --show-current && git worktree list`；从 `gitea/main` 新开树与分支 `feat/checkpoint-rule-id-bias`（`git worktree add /Users/a77/fwp-wt-checkpoint-bias -b feat/checkpoint-rule-id-bias gitea/main`）。解释器 `.venv-workbench/bin/python`。
2. `python3 scripts/code_map.py query "checkpoint register rule_id 偏差"` 确认无现成实现。
3. 实现顺序（每步一个提交，pathspec）：`checkpoints.py` 三字段 + `by_rule` + `render_report` 同提交（unread-fields 要求）→ `cli.py` `--rule-id / --receipts-dir` + 回显 → `checkpoint_bias.py` 四条 + `scan` → `cli.py` 登记后 scan + `bias-scan` 子命令 → 测试 → `ledger-map.md` 一行 → 设计稿 §10.2 名字对齐 → 交接。
4. 真库读数：在生产用户大脑目录上（只读 `checkpoints.jsonl` / `verdicts.jsonl`，旁路库只读）跑 `checkpoint bias-scan --json`，把四条 flag 的命中 / unverifiable / 不适用计数写进交接；再用 `--rule-id dual_red_streak3_continuation` 登记一条**测试用户**（`--user replay-test`，不污染真人台账）的判断，截图 / 粘贴回显块。
5. 变异测试至少一条：把 `rule_not_firing` 的「实体不在事件集」判断反过来 → `test_checkpoint_bias.py` 阳性用例必须变红；恢复后绿。记进交接。
6. 门禁：`ruff check .`、`python3 scripts/layer_audit.py`、`python3 scripts/check_unread_fields.py`、`pytest -q intelligence/tests/test_checkpoints.py intelligence/tests/test_checkpoint_bias.py intelligence/tests/test_prime.py intelligence/tests/test_user_memory.py intelligence/tests/test_experience_cards.py`；最后全量 `run_main_gate.sh`；push、开 PR、**不合 main**。

### 验收（机器可判或有明确观察面）

- [ ] `register_checkpoint(..., rule_id="dual_red_streak3_continuation")` 记录含三字段；不给 `rule_id` 时记录**无**这三个键（`assert "rule_id" not in record`）；`rule_id="Bad Id"` 抛 `ValueError` 且不落盘。
- [ ] 五个既有调用方的现有测试零改动全绿（`test_checkpoints.py` / `test_checkpoint_writeback.py` / `test_checkpoint_recall.py` 等）。
- [ ] 合成台账：3 条带 `rule_id=r1`（hit/hit/miss）、2 条带 `r2`、4 条无 `rule_id` → `by_rule` 恰有 2 项，`r1.n=3, hit_rate≈0.667`；`by_category` 计数不变（9 条全在）。
- [ ] `render_report` 按规则段：传入 `{r1: receipt}` 时该行含收据的 `p / p0 / N / 四态`；不传时该行显示「无收据」。
- [ ] CLI：`checkpoint register --rule-id <有收据的规则>` stdout 含「最近收据」行与 N / p / p0 / Wilson；`--rule-id nope_rule` 仍登记成功、stdout 含「尚无收据」；两种情况退出码均 0。
- [ ] 四条偏差各三组夹具：阳性产 flag、阴性不产、数据缺失产 `*_unverifiable`；`rule_not_firing` 在无 `rule_id` 时不产任何 flag（不适用 ≠ unverifiable）。
- [ ] `post_miss_streak` 与 `revenge_reentry` 在旁路库缺失时仍能算（`evidence.calendar="natural_days"`）；`late_streak` / `rule_not_firing` 此时为 unverifiable。
- [ ] `bias-scan` 在真库 83 个可证伪点上跑通，退出码 0，输出四条 flag 的三类计数；交接写明数字。
- [ ] `check_unread_fields.py` 无新增未读字段；`layer_audit.py` ERROR 0；`ruff` 0；变异测试记录在交接。
- [ ] 主库 `fact_*` 行数与 `max(updated_at)` 跑前跑后一致；旁路库 `history_build_meta.computed_at` 不变（全程只读）。
- [ ] `ledger-map.md` 第 14 行格式列已补四字段；设计稿 §10.2 第一条四个名字与本单一致。

## 6. 红线（抄 AGENTS.md，不新发明）

- 开工先 `git status --short && git branch --show-current && git worktree list`；主树有他人足迹**另开干净树**。
- 🚫 禁 `git add -A` / `git add .`；一律 `git commit -- <明确文件列表>`；不合 `main`、不强推、合并等用户确认。
- 🚫 禁提交 `.env*` / 密钥 / `*.duckdb` / `*.jsonl` 用户台账 / `.DS_Store` / 缓存与虚拟环境。真人台账只读；测试登记用 `--user replay-test` 或临时目录。
- 解释器 `.venv-workbench/bin/python`。
- `intelligence/services/` 不得 import `intelligence/runtime/`；`checkpoints.py` 不得 import duckdb。
- 主库与旁路库全程 `read_only=True`。
- 只提示不拦截：任何 flag 不得让登记失败、不得改 `verdict`。
- 台账号只用 `python3 scripts/claim_ledger_id.py claim` 取（本单不取）。
- 用户纠偏必落 correction（`python3 -m intelligence.cli record-correction ...`）。

## 7. 成立条件

- 树：`/Users/a77/fwp-wt-finance-agent-bp` @ `docs/finance-agent-bp`（本单在此起草）；实施基线取派单时的 `gitea/main`（起草时 `5c7fe2eb`）。
- 行号：2026-09-04 读自 `docs/finance-agent-bp` 合 `gitea/main@5c7fe2eb` 之后的树；实施时以 `rg` 重定位。
- `rg rule_id intelligence/services/checkpoints.py` = 0 命中；`rg register_checkpoint\(` 非测试命中 5 处（含定义）。
- 本文零运行时改动。

## 8. 可迁移知识点（教学备注）

- **过程条件 vs 结果条件。** 评价一个决策用「当时有没有依据、有没有提前登记、有没有只用当时的信息」，不用「后来赚没赚」——这是决策科学里「决策质量 ≠ 结果质量」的机器化。A/B 实验里的「预注册」是同一件事。
- **提示不拦截。** 系统知道的比用户少（它看不到用户没登记的信息），所以偏差 flag 是「你可能在……请再看一眼」而不是「不许」。产品里叫 nudge，工程里叫 warning not error。
- **unverifiable 与 not_applicable 是两种不同的「没结果」。** 前者是数据不够、以后能补；后者是规则不适用、永远不会有。混在一起会让「无 flag」失去含义——这和 `checkpoints` 里 `unverifiable` 是非终态、`hit/miss` 是终态是同一个区分。
- **同源同口径。** 判断与经验卡对规则的引用走同一个 `latest_receipt`，两张台账对同一条规则永远读到同一份收据；否则同一个规则在两处显示两个结论，用户第一次发现就不再信任任何一处。
