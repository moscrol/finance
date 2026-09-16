# 工单 #21 · P1 剩余：题材 `lifecycle_stage` 单一词表 + 旁路库标签 + 人工对照集（G-04）

> 日期：2026-09-08
> 编号：**不另立号**——路线图 G-04 原文「依赖：#21 剩余项（同一工单收口，不另立——spec §13.2 F3）」。本文件是 #21 的派单稿，INDEX #21 行追加一句指过来
> 上游：`2026-09-04-methodology-backtest-structured-history-design.md` §2 表（theme P1：`lifecycle_stage`「需先设计规则并用 `theme-fermentation-tracer` 的历史链路做人工标注对照」）、§10 路线图剩余项；`2026-09-05-time-river-gap-roadmap.md` G-04（缺 / 验收 / 对外）；INDEX #21 行「剩余 P1：`lifecycle_stage` 人工对照集、收据保鲜」
> 优先级：**L0 前置**（路线图原话「不做后面全是沙上建塔」）——G-06 错位标记的题材侧、G-07 三维并置、G-02a 题材轨阶段字段都等它
> 规模：中单（两到三天，两刀）；**人工对照集需要创始人或用户标 30–50 条**（见 §2.2，这是本单唯一的人力瓶颈）
> 分支：`feat/methodology-backtest-p1-lifecycle-stage`
> 并行冲突：改 `UBIQUITOUS_LANGUAGE.md`（新小节）、`methodology_backtest/labels.py`（`LABEL_VERSION` 升版）；与 #36 同样升 `LABEL_VERSION`——**后合入者 rebase 再升一版**，两单都要重建旁路库并重跑收据

---

## 0. 一句话

题材阶段今天有**三套词**：`theme_lifecycle.py` 的八阶段（新出现 / 旧逻辑唤醒 / 升温验证 / 加速定价 / 高位分歧 / 二阶段回流 / 衰退观察 / 证伪退出），`theme_lifecycle_timeline.py` 的七段（酝酿 / 首发 / 发酵 / 主升 / 分歧 / 退潮 / 回流），以及 #21 设计稿里给旁路库预留的五段（启动 / 发酵 / 高潮 / 分歧 / 退潮）——第三套还没落地。路线图 G-04 要的是：**一张映射表 + 一套钦定词表进 `UBIQUITOUS_LANGUAGE.md`**，旁路库 `lifecycle_stage` 标签按钦定词表从盘面逐日行确定性派生，再用 `theme-fermentation-tracer` 的历史链路做人工对照集量一致率，`LABEL_VERSION` 升版、现有收据重跑。

---

## 1. 现状 [实测 @ `gitea/main` `8e452e72`]

| 位置 | 现状 | 差距 |
|---|---|---|
| `intelligence/services/theme_lifecycle.py:30–38` | 八阶段常量（中文值）+ `STAGE_UNKNOWN="无法判定"`；`_STAGE_GUIDANCE` | 面向「当前快照诊断」，输入含消息面；不是逐日可重算的标签 |
| `intelligence/services/theme_lifecycle_timeline.py:63–69` | 七段常量；`is_double_red` 用 `_signals.DOUBLE_RED_*` 常量；`MAINUP_CONSECUTIVE=3 / EBB_BREAK_DAYS=5 / REFLOW_CONFIRM_DAYS=2 / MIN_PHASE_DAYS=3`；`StageSegment / ThemeTimelineArtifact`；docstring 明写每段触发条件与「酝酿」需消息面证据（无则显式缺口） | **已经是确定性状态机**，从盘面逐日行派生——是旁路库标签的现成实现；但词与八阶段不通，且是 artifact 不是标签 |
| `intelligence/services/methodology_backtest/labels.py:113 THEME_LABELS = ("limit_heat_rank", "limit_heat_rank_jump", "mainline_flag")` | 旁路库题材标签没有阶段 | `lifecycle_stage` 缺 |
| `2026-09-04-methodology-backtest-structured-history-design.md:88` | 预留五段「启动 / 发酵 / 高潮 / 分歧 / 退潮」 | 第三套词，未落地；本单要**废掉**它或把它并进钦定词表 |
| `intelligence/workbench_skills/daily_agent_contract.py:161 metric="lifecycle_stage"` | 每日复盘产物已有 `lifecycle_stage` 字段（消费八阶段词） | 词表切换后消费方要跟（映射，不重写） |
| `skills/theme-fermentation-tracer/scripts/trace.py` | 发酵链路回溯（历史链路） | 人工对照集的样本来源 |
| `UBIQUITOUS_LANGUAGE.md` | 无「题材生命周期」小节 | 词表要进来 |
| 路线图 G-04「引用必须标模块」的临时纪律 | 现行 | 词表统一后退出 |

---

## 2. 两刀

### 2.1 刀 1｜钦定词表 + 映射表 + 旁路库标签（`LABEL_VERSION` 升版）

**钦定原则**：选**能从盘面逐日行确定性重算**的那套作主词表——即七段时间线的词（酝酿 / 首发 / 发酵 / 主升 / 分歧 / 退潮 / 回流），因为它已经是状态机、每段有触发条件、能在历史上跑；八阶段是「当前快照 + 消息面」的诊断语言，保留为**读法层的别名**，通过映射表翻译，不再作为标签值出现。设计稿的五段预留**作废**（并进七段：启动→首发、高潮→主升，其余同名），在设计稿 §2 表上划掉并注明。

映射表 `THEME_STAGE_MAPPING`（进 `UBIQUITOUS_LANGUAGE.md` 新小节「题材生命周期」+ 代码常量同源，一处生成另一处校验）：

| 钦定（标签值） | 八阶段别名（读法层） | 备注 |
|---|---|---|
| 酝酿 | 新出现 / 旧逻辑唤醒 | 需消息面证据；无则 `gap`，不是「酝酿」 |
| 首发 | 升温验证（首板 / 首次双红） | |
| 发酵 | 升温验证（持续） | 八阶段一词对两段：映射带条件，写明 |
| 主升 | 加速定价 | |
| 分歧 | 高位分歧 | |
| 退潮 | 衰退观察 / 证伪退出 | 证伪退出要消息面证伪事件；无则只到「退潮」 |
| 回流 | 二阶段回流 | |
| `gap` | 无法判定 | 缺原料，不猜 |

旁路库标签：`labels.py` `THEME_LABELS` 加 `lifecycle_stage`（值 = 七段词或 NULL），派生逻辑**直接调用 `theme_lifecycle_timeline` 的状态机**（不复制阈值；`MAINUP_CONSECUTIVE` 等常量从它导入），按 `(trade_date, sector_ts_code)` 逐日落值；`LABEL_SPEC["lifecycle_stage"]` 写口径与阈值来源；`LABEL_VERSION` 升一版（v4，若 #36 先合则 v5）。重建 `db/history_labels.duckdb`（先备份到 `/tmp/history_labels.pre-<ver>.duckdb`），现有规则收据全部重跑，漂移逐条记录。

消费方跟进（映射，不重写）：`daily_agent_contract` 的 `lifecycle_stage` metric 与 `theme_lifecycle` 输出经 `THEME_STAGE_MAPPING` 归到钦定词后再渲染；`river.py` 题材轨（`_theme_track`）新增 `object_type="stage"` 对象，值取旁路库同一口径（或直接调状态机，两者必须一致——测试钉住）。

### 2.2 刀 2｜人工对照集 + 一致率报告

- 样本：从 `theme-fermentation-tracer` 历史链路里抽 **30–50 个 `(theme, as_of)`**，分层覆盖七段各 ≥ 4 条、跨 ≥ 3 个不同月份；样本清单由 agent 生成（`methodology/reference/theme_stage_reference_set.jsonl` 草稿，字段 `theme / as_of / evidence_refs / stage_manual=null`），**`stage_manual` 由创始人 / 用户填**——agent 不替填（08-19 §5 红线：判读内容人写）。
- 报告 `scripts/methodology_backtest.py stage-agreement --reference methodology/reference/theme_stage_reference_set.jsonl`：两模块（时间线状态机 → 标签值；八阶段诊断 → 映射后）对人工标注的一致率、混淆矩阵；不一致样本**逐条归因**（阈值 / 缺原料 / 映射歧义 / 人工标注存疑）。N < 30 已填时报告只出计数不出率。
- 结果进收据 `docs/verification/2026-09-08-theme-lifecycle-stage-agreement.md`；一致率**不进对外物料**（G-04 对外口径：做完后只可说「题材轴单一词表、历史可重算」）。

---

## 3. 验收（逐条可打勾，对应路线图 G-04 (a)(b)(c)）

1. `UBIQUITOUS_LANGUAGE.md` 新小节只有**一套**标签值（七词 + `gap`），八阶段以「别名」列出；`rg` 全树：五段预留词「启动 / 高潮」不再作为阶段值出现在代码里。【(a)】
2. `THEME_STAGE_MAPPING` 代码常量与文档表一致（测试从文档解析表格对比常量，或反向生成）。
3. 旁路库 `lifecycle_stage` 列存在，非 NULL 占比与「有双红原料的 `(date, sector)`」占比一致（缺原料日为 NULL，不为「酝酿」）；`LABEL_VERSION` 已升，`LABEL_SPEC` 有口径。
4. 两模块输出经映射后**同名**：对旁路库随机 30 个 `(date, sector)`，`river._theme_track` 的 `stage` 对象值 == 旁路库 `lifecycle_stage`（测试）。【(a)】
5. 人工对照集文件存在、样本分层达标、`stage_manual` 待填字段为 null（agent 不填）；`stage-agreement` 在 `stage_manual` 全 null 时只报「待标注 N 条」，不出率。【(b) 的可执行前半】
6. 创始人填完后重跑 `stage-agreement`：一致率、混淆矩阵、逐条归因进收据。【(b) 后半——**卡人**，写进交接的「等用户」项】
7. 旁路库重建后现有 `methodology/receipts/` 全部重跑，逐条「保持 / 漂移（原因）」进收据。【(c)】
8. 「引用必须标模块」纪律退出：路线图 G-04 条目与 `river_query.normalize_stage` 一类注释里的「模块标记」说明改为指向本词表。
9. `daily_agent` 每日复盘产物 `lifecycle_stage` 字段在词表切换前后对同一天的值经映射相等（回归测试用历史 exports 夹具）。
10. 干净树全量 `ruff 0` + 红集不大于基线；`check_test_receipt.py --expect-revision HEAD`。

---

## 4. 非目标 / 红线

- ❌ 不改 `theme_lifecycle_timeline` 的阈值（`DOUBLE_RED_* / MAINUP_CONSECUTIVE / EBB_BREAK_DAYS / REFLOW_CONFIRM_DAYS`）——本单统一**词**，不动**规则**；阈值改动是另一单，且要过统计门。
- ❌ 不删八阶段模块；它降为读法层别名，`_STAGE_GUIDANCE` 文案继续可用。
- ❌ agent 不填 `stage_manual`；不用模型标注代替人工。
- ❌ 一致率不进 BP / 对外物料。
- ❌ 不与 #36 的舆论词表混名（两小节各自的词逐一 `rg` 确认无重名）。

---

## 5. 教学注

- **为什么选「能重算的那套」当主词表**：词表要服务的是回测与回放，回测需要每一天都能从事实算出值；「当前快照诊断」那套依赖消息面与人判，历史上大多数日子算不出来。选主词表的判据不是哪套更像行话，而是哪套有确定性派生。别名机制让行话继续可用而不进入标签值——和数据库里「枚举存码、展示存翻译」是一回事。
- **一套词一对多映射怎么处理**：八阶段「升温验证」对应七段的首发与发酵两段，映射必须带条件（首次双红 vs 持续双红），否则反向翻译不唯一。凡是一对多的映射都要写条件而不是列两项——这是词表统一里最常被跳过的一步。
- **人工对照集为什么必须分层**：随机抽会被「发酵 / 退潮」这类高频段占满，低频段（回流、酝酿）零样本，一致率看着很高但对低频段一无所知。分层抽样保证每个类别都被量到；N < 30 不出率与 `DEFAULT_CALIBRATION_MIN_N=10` 同一条纪律。

---

## 6. 交接要求

- 在途交接沿用 `docs/handoffs/inflight/feat-methodology-backtest-p1-*.md` 命名：`feat-methodology-backtest-p1-lifecycle-stage.md`（≤ 3K）。
- INDEX #21 行追加：「P1 剩余派单稿 `2026-09-08-methodology-backtest-p1-lifecycle-stage-workorder.md`」；合入后 #21 行「剩余 P1」改为「lifecycle_stage 已落（词表 / 标签 / 对照集草稿），一致率等用户标注」。
- 路线图 G-04 回写；设计稿 `2026-09-04-methodology-backtest-structured-history-design.md:88` 那行五段预留划掉并注明改用七段。
