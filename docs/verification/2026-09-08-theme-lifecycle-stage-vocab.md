# 题材生命周期单一词表 + 旁路库 `lifecycle_stage` + 人工对照集草稿——工单 #21 剩余 P1（G-04）验收收据

> 日期：2026-09-08 · 分支 `feat/methodology-backtest-p1-lifecycle-stage` · 基线 `gitea/main@368b7a66`（含 #665）
> 派单稿：`docs/superpowers/specs/2026-09-08-methodology-backtest-p1-lifecycle-stage-workorder.md`（PR #666 分支）；路线图 G-04；INDEX #21「剩余 P1」

## 改了什么

| 文件 | 内容 |
|---|---|
| `intelligence/services/theme_stage_vocab.py`（新） | **钦定七段为标签值**（`CANONICAL_STAGES` 直接引 `theme_lifecycle_timeline` 的常量）；八阶段 → 七段映射表 `EIGHT_TO_CANONICAL`（一对多的「升温验证」带条件 `first_signal`，不给则按发酵并标 `ambiguous`）；五段预留作废别名 `FIVE_LEGACY_TO_CANONICAL`（启动 → 首发、高潮 → 主升）；`canonical_of()` 接任一套词、不认识的抛错；`stage_on_day()`；`render_mapping_markdown()` 生成文档表（`tsm-v1`） |
| `intelligence/services/theme_lifecycle_timeline.py` | `derive_stages(..., daily=)`：循环里每天记下**机器当时所在的段**——「站在当天」的读数；起点回溯与 `merge_short_phases` 事后改段边界，不改它。阈值一个没动 |
| `intelligence/services/methodology_backtest/labels.py` | `THEME_LABELS` 加 `lifecycle_stage`（16 个）；**`LABEL_VERSION` v3 → v4**（`…-lifecycle_stage_tsm_v1`）；`lifecycle_stage_rows_by_code()`（板块逐日行 + 热度表 `limit_up_count` 按名精确匹配；连板高度不接——`fact_limit_advance_daily.theme LIKE` 是模糊匹配）；`_build_lifecycle_stage_labels()` 按 `daily` 落文本标签，段外不落行 |
| `intelligence/services/methodology_backtest/rules.py` | `LABEL_KINDS["lifecycle_stage"] = ("theme", "text")` |
| `intelligence/services/river.py` | `theme_lifecycle_stage_object()`：同一台状态机、同一份原料，读 `daily[as_of]`；`_theme_track` 新发 `object_type="stage"`（payload 带 `segment_hindsight` 说明事后段落，与站在当天的 stage 分开给）；当日无涨停成分但状态机在段内时不再整轨 gap |
| `intelligence/workbench_skills/daily_agent_contract.py` | 报告里的八阶段词保留为 `lifecycle_stage` 原子（读法层别名），旁边新增 `lifecycle_stage_canonical` 原子给七段钦定词；翻译不到不加 |
| `scripts/methodology_backtest.py` | `stage-reference`（分层 + 跨月轮转抽样，`stage_manual` 留 null）、`stage-agreement`（已填 < min_n 只出计数；人可用任一套词写，统一到七段再比；不一致逐条列出等人工归因） |
| `methodology/reference/theme_stage_reference_set.jsonl`（新，进 git） | 42 条草稿：六段各 7（酝酿需消息面证据，旁路库不读知识库，无样本），跨 21 个月；`stage_manual` 全 null——**由创始人填** |
| `UBIQUITOUS_LANGUAGE.md` | 新小节「题材生命周期」（插在「指数环境周期」之前，避开 #36 / #666 的插入点），映射表由 `render_mapping_markdown()` 生成，测试比对文档 == 代码 |
| `docs/superpowers/specs/2026-09-04-methodology-backtest-structured-history-design.md:88` | 五段预留行划掉、指向七段词表 |
| 测试 | `test_theme_stage_vocab.py` 9 条；`test_methodology_backtest.py` 标签数 15 → 16 + `test_lifecycle_stage_label_matches_state_machine_and_leaves_gaps_null` |

## 验收逐条（派单稿 §3）

| # | 判据 | 结果 |
|---|---|---|
| 1 | 词表里只剩一套标签值；八阶段为别名；五段词不再作阶段值 | ✅ `test_canonical_is_the_seven_stage_machine_words`、`test_five_legacy_words_are_aliases_not_values`；`rg` 代码里「启动 / 高潮」只出现在 `FIVE_LEGACY_TO_CANONICAL` |
| 2 | 映射表代码 == 文档 | ✅ `test_doc_table_equals_code_table`（文档表由代码生成） |
| 3 | 旁路库列存在、缺原料日不落行、`LABEL_VERSION` 升 | ✅ 临时库 `/tmp/history_labels.v4-theme.duckdb`：**95,927 行 / 620 板块**，分布 首发 46,000 / 退潮 40,724 / 回流 5,506 / 发酵 2,364 / 主升 1,244 / 分歧 89 / 酝酿 0；无行的板块日不落行 |
| 4 | 两模块同名：`river._theme_track` 的 `stage` == 旁路库 `lifecycle_stage` | ✅ 真库随机 30 格 **30/30**（第一版按事后段落表取值只有 28/30——两处差异正是起点回溯 / 短段合并的前视，改成 `daily` 后归零） |
| 5 | 对照集草稿分层达标、`stage_manual` 为 null、agent 不填 | ✅ 42 条、六段各 7、跨 21 个月；`stage-agreement` 在全 null 时输出 `insufficient_n`「待标注 42 条」 |
| 6 | 创始人填完后重跑出一致率与混淆矩阵 | ⏳ **卡人**——`stage-agreement` 已就绪，`min_n=30` |
| 7 | 旁路库重建后现有收据重跑 | ⚠️ 只建到临时库；共享 `db/history_labels.duckdb` 仍 v3（#36 同样只建临时库）。合入后验收 session 重建并重跑四条规则记漂移——`lifecycle_stage` 是新增列，不改任何既有标签值，预期零漂移 |
| 8 | 「引用必须标模块」纪律退出 | ✅ UBIQ 小节写明单一词表；`river_query.normalize_stage` 那类注释是 `market_stage` 的，不在本单 |
| 9 | `daily_agent` 产物词表切换前后经映射相等 | ✅ 原子 `lifecycle_stage` 原样保留（`test_daily_agent_grounded` 续绿：`旧逻辑唤醒`），新增 `lifecycle_stage_canonical=酝酿` 并排 |
| 10 | 干净树全量门禁 | 见下 |

## 门禁

干净树 `~/fwp-wt-theme-stage` @ `666abf5c`（基线 `368b7a66`，含 #665）、`.venv-workbench`、`env -u MARKET_FEATURE_STORE_DB`：ruff 0；pytest **8199P / 0F / 77S / 1xfail**（445s）；`check_test_receipt --expect-revision HEAD` 可采信。

## 已知边界

- **「首发」占 46,000 格**：状态机在首板 / 涨停后、首次双红前一直停在首发——这是机器语义，不是本单改的；创始人对照集会告诉我们这一段该不该这么长（阈值问题另立单）。
- **酝酿永远为 0**：要消息面事件日（知识库 `theme_signals.json`），旁路库只读主库。河切片同样。
- 连板高度 / 首板数不接（模糊匹配），主升判定按状态机声明「放宽为仅连续双红 ≥3」。
- 与 #36 同样把 `LABEL_VERSION` 升到 v4：后合入者 rebase 再升 v5，并把两个新标签都写进 v5 的版本说明。
- `segment_hindsight` 在 payload 里是**事后视角**的段落说明，读者不得拿它当当天读数——字段名已标明。
