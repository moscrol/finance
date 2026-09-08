# 观察剧本 + 合规硬门（G-03 / G-12a）验收收据

> 日期：2026-09-06
> 分支：`feat/observation-script`（**基线不是 main**：从 `feat/river-slice-v0@8e3383c8` 起，因为 G-03 依赖尚未合并的 `river.slice`）
> 上游 spec：`docs/superpowers/specs/2026-09-06-personal-research-calibration-endstate-design.md` §3.2 / §10；
> 路线图：`2026-09-05-time-river-gap-roadmap.md` G-03、G-12a
> 状态：**未合并、未切 8792**。

## 0. 一句话

终局 spec 的 V1 里，`river.slice` 与双时钟 / `pit_grade` 已在 `feat/river-slice-v0` 落地；本刀补上
**观察剧本对象 + 合规硬门 + 带读管线 + T+1 回检登记**，即 spec §10 V1 第三、五两项与最小验收集第 4 条。
G-01 授课框架母本仍待创始人写，**因此对外只能说「带读管线跑通」，不能说「授课框架带读」**。

## 1. 改了什么

| 文件 | 性质 | 内容 |
|---|---|---|
| `intelligence/services/compliance_gate.py` | 新增 | 合规词表 + 扫描器；7 个错误码；观察剧本硬门与营销 lint **共用同一份词表** |
| `intelligence/services/observation_script.py` | 新增 | `ObservationScript` 对象、硬门 `validate/ensure_valid`、`late` 判定、登记（jsonl + checkpoint）、状态机、`expire_stale` |
| `intelligence/services/guided_reading.py` | 新增 | 带读：河切片 → 事实 / 限制 / 缺口 + 剧本骨架；「新用户开、老用户关」开关；输出用词 lint |
| `intelligence/services/checkpoints.py` | 改 | 加 `object_type`（三类判断轨对象）+ `object_type_of` 读取器 |
| `intelligence/userspace.py` | 改 | `observation_scripts_path`（property，不加构造字段） |
| `intelligence/services/river.py` | 改 | `to_dict()` 补 `alias_applied`——限定语必须活过序列化 |
| `intelligence/cli.py` | 改 | `observation read/confirm/skip/list` 四个子命令 |
| `scripts/validate_marketing_contracts.py` | 改 | 接 `compliance_gate`，对 `docs/marketing/*.yaml` 与 `generated/*.md` 查「策略」单独出现 /「第二天的方向」 |
| `intelligence/tests/test_{compliance_gate,observation_script,guided_reading}.py` | 新增 | 74 条 |

## 2. 验收判据逐条

spec §10「最小验收集」与 roadmap G-03 验收的对应读数：

| 判据 | 出处 | 读数 |
|---|---|---|
| 含推荐 / 买卖时点 / 目标价 / 概率承诺的剧本被拒绝并给出错误码 | spec §10.4 | ✅ `HardGateTests` 11 条；真机 CLI 退出码 **2**（区别于 1=运行错误） |
| 硬门测试：含个股实体 / 方向词 / 时点词被拒并有错误码 | G-03 (a) | ✅ `E_STOCK_SCOPE` / `E_DIRECTION` / `E_TIMING` 各有用例；scope 填 `theme` 但正文写个股代码同样拦下 |
| day-1：零历史新用户在 T 日收盘后拿到带读 + 至少一条可登记剧本 | G-03 (b) | ✅ 真库实测（见 §3） |
| 登记后 T+1 自动回检并写 verdict，verdict 带 `object_type=observation_script` | G-03 (c) | ✅ 及时确认写出 `ck-2026-09-06-d36595`，`object_type=observation_script`、`metric.type=market_daily`、`due=2026-09-07`，`checkpoint due --date 2026-09-08` 能读到。**回检执行走既有 `checkpoint recheck` + resolver，本刀不另造引擎** |
| 关掉带读 = 现有行为逐字节不变 | G-03 (d) | ⚠ **当前平凡成立**：带读尚未接进每日复盘，没人调用它。已钉住的是「关闭时 `run()` 返回 None 且用户目录零变化」。接线那一刀要自带 diff 收据，别把这条绿灯当接线后的保证 |
| 「策略」「第二天的方向」在带读输出里被 lint 拒绝 | G-03 (e) | ✅ `lint_output` 覆盖两词；`validate_marketing_contracts.py` 对外物料同一份词表，现存物料 exit 0 |
| 营销契约禁词报错 | G-12a (a) | ✅ 同上 |
| 判官「不得出现概率数字」 | G-12a (b) | ❌ **未做**：判官接入留给 G-07 / G-08，`compliance_gate.scan(codes=...)` 已备好接口 |

## 3. 真库端到端（隔离 users 目录，未污染真台账）

`FORESIGHT_USERS_DIR=$(mktemp -d)`、`as_of=2026-09-02`、`entity=算力租赁`：

1. `observation read` → 带读渲染成功，六轨里 capital/market/opinion/stock/theme 有事实、judgment 报缺口，`pit_grade=strict`，产出 5 条变量 + 4 条放弃条件的骨架。
2. `observation confirm --from-slice` → `status=late`（09-02 的剧本 09-06 才确认，晚于 09-03 开盘），**不登记 checkpoint、不进校准**。
3. 硬门反例两条：`--variable "明天低吸算力租赁"` → `E_DIRECTION`；`--entity 600519.SH --variable "目标价 2000 元，胜率 70%"` → `E_STOCK_SCOPE` + `E_TARGET_PRICE` + `E_PROBABILITY`，逐条带改法。
4. 及时路径：`as_of=2026-09-04`（周五）于周日确认 → `status=confirmed`（周末规则生效）→ 落 checkpoint 并进回检队列。

## 4. 实测发现的两个真问题（都不是测试能先发现的）

### 4.1 带读会把个股节点渲染成名单

真库第一次跑，带读被自己的用词 lint 拦下 22 处 `E_STOCK_SCOPE`。追下去发现**两条轨**都在发个股级对象：
`_stock_track`（成分股行情，按成交额降序取 10 条）与 `_theme_track`（`fact_theme_limit_stock_daily` 涨停节点）。

数据层管它们叫「节点，不是推荐名单」——**在 river 那个查询面上这话成立**，那是给操作者的数据出口。
但带读是小白产品面：十条按成交额降序、带涨幅的个股行渲染出来，读者看到的就是一张名单，无论我们管它叫什么。

处置：带读把**个股级对象折叠成计数 + 标签**（`个股级节点 10 条（20日新高×2）；明细见 river 切片`）。
判据按**对象形状**（payload 有 `stock_ts_code` / ref 含个股代码），不按轨名——按轨名收边界，下一个 provider 接进来就漏。
这条边界现在由整篇 lint 兜底：新 provider 一旦把个股代码漏进带读，`observation read` 直接 exit 1。

### 4.2 按自然日判 late 会把周末补课判成迟到

`late` 的判据是「晚于次日开盘」。初版按自然日 +1 算，于是**周五的剧本周六补做 = late**，一条及时的判断被
挡在校准之外。周五收盘到周一开盘之间没有交易，用户看不到任何后续行情——放到周一才是「次日开盘」的本义。

处置：`default_next_open` 跳周末；`default_due` 用同一条规则（回检日落周六会让 resolver 查无当日行，
读数上像「判不了」，其实是问错了日子）。节假日仍按从严处理——本库**没有交易日历表**（实测 `dim_*` 只有板块维度），
`next_trading_open` 只能解历史日期（库里最新一天 = 已收盘的交易日，所以「今天登记今天」这条主路径必然回落）。

## 5. 变异测试（证明门禁不是假门禁）

| 变异 | 期望 | 实测 |
|---|---|---|
| `validate()` 直接 `return []` | 硬门用例大面积红 | 13 failed / 24 passed |
| `is_late()` 恒 `False` | late 三条红 | 3 failed / 34 passed |
| 骨架模板塞进方向词「明天低吸的买点」 | 自检两条红 | 2 failed / 16 passed |

## 6. 门禁读数

- 三份新测试：74 passed。
- checkpoint 消费方（`test_checkpoints` / `user_memory` / `track_contract` / `foresight` / `memory_candidate_loop` / `judgment_adjudicate`）：146 passed。
- river 三份：37 passed。
- `ruff check` 全部改动文件：All checks passed。
- `scripts/validate_marketing_contracts.py`：exit 0。
- 全量：见 §7。

## 7. 全量读数与四条红的归因

主工作树（`umask 022` + `env -i PATH` 隔离壳，`.venv-workbench`）：

```
4 failed, 7866 passed, 8 skipped, 1 xfailed in 326.51s
```

四条红**全部是存量红，与本刀零交集**。归因证据（不是「看着不像我的」）：

| 红 | 归因证据 |
|---|---|
| `test_double_red_single_source::test_no_new_hardcoded_double_red_predicate` | 棘轮点名的是 `intelligence/services/river_window.py`（**基线分支的文件，本刀未碰**）。在 `8e3383c8` 的干净 worktree 里同样红——见下 |
| `test_conversation_orchestrator::test_completed_stream_persists_human_readable_answer` | 基线 worktree 同环境同样红；且 INDEX #21 已登记为存量红（有真库时 `market_watch_pack` 前置「## 指定日盘面组件包」，断言按无库环境写死） |
| `test_codex_headless_runtime::test_installed_codex_sandbox_denies_network_and_unix_socket` | 基线 worktree 同样红（sandbox 环境项） |
| `tests/test_code_map::test_structure_probe_daily_full` | 它读的是**预建** `.code-review-graph/graph.db`：构建于 09-06 **04:25 @8e3383c8**，而本刀第一个文件写于 **10:35**——图里不含本刀任何字节，不可能由它引起。`code_map status` 自报 `ready n=21581 @8e3383c` |

基线复现方式（已清理）：`git worktree add --detach /tmp/fwp-baseline-g03 8e3383c8` + 软链真库 `db/`，
同一隔离壳跑那四条 → `3 failed, 1 skipped`（第四条因 worktree 里 `_graph_searchable()` 为假而跳过，
故改用上面的时间戳 / revision 证据归因）。

⚠ 读数是在**主工作树**跑的，不是干净 detached 树。合并前按 acceptance-workflow 还要在干净树上重跑一次
并出 `check_test_receipt --expect-revision`——主树带着 BP 分支的未提交改动，收据不能直接采信为「对某个 revision 成立」。

## 8. 明确没做

- **G-01 授课框架母本**：人写，agent 不代笔。带读的「判读」段**故意留空并写明原因**。
- **带读接进每日复盘 / `market_watch_pack`**：要改产物，单独一刀带 diff 收据。
- **判官概率数字检查**（G-12a 后半）：等 G-07 / G-08。
- **G-09 胜率面板按 `object_type` 分列**：本刀只保证字段在登记时写下（事后从 `category` 反推是猜），面板本身待 #24。
- **存量 checkpoint 的对象类型**：无 `object_type` 的老记录只从确定的 `source` 反推，其余进 `unknown_legacy` 单独一格，
  **不折进 `judgment`**——一个默认值把三种来源合成一种，面板就再也分不开了。
