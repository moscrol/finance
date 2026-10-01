# 2026-10-01 harness 优化（与 2×2 实验不冲突的部分）

基线：origin/main `3a2718c6` + `qc-p0-fixes.patch`（`259e9378`）。四个独立提交，可分别合入或回滚。

## 1. 换库锁在 Linux 上失效 → OFD 锁 + 自检（`market_feature_store/db.py`）

- 实测（duckdb 1.5.4，Linux）：DuckDB rw 写者在场时 `flock(LOCK_SH|LOCK_NB)` **照样拿到**——flock 与 DuckDB 的 fcntl 记录锁在 Linux 上互不可见，换库窗口形同虚设。macOS 上二者互斥，所以 Mac 生产一直是对的。
- 修法：Linux 用 `F_OFD_SETLK F_RDLCK`（与传统记录锁互斥、同进程也互斥、不因关别的 fd 丢锁；经典 `lockf` 恰恰会丢，故不用）；macOS 保持 flock；其他平台 `SwapLockUnsupportedError`（DatabaseLockedError 子类 → 编排 rc=2）。每进程首次拿锁前跑一次约 10ms 的进程内语义自检。
- 结果：基线里 6 条 Linux 专属 staging_swap 失败中 5 条转绿；第 6 条（克隆后窗口）依赖 APFS `cp -c`，与锁无关，改为非 macOS 跳过。变异测试：强制回 flock → 6 红。
- Mac 行为不变（同一 flock 路径，只多一次自检）。

## 2. finance_query schema 瘦身（工具面 −32%）

- 8 个工具菜单 35,939 字符，finance_query 占 89%。其中 10,742 字符的「全字段并集 enum」重复 5 次（metrics / dimensions / filters.field / group_by / order_by.field），而它从没拦住过错槽（rank 塞进 dimensions 就发生在 enum 在场时）。
- 改后：字段槽为普通 string，说明指向每张表的「可用字段」；校验仍由 `FinanceQuerySpec` / `_compile_query` + `validation_retry_hint` 负责。finance_query 31,927 → 20,477；合计 → 24,489。
- 守卫：`intelligence/tests/test_tool_surface_budget.py`（预算 finance_query ≤ 22.5K、合计 ≤ 27K；只允许 dataset / filters.op / order_by.direction 三处 enum）。度量：`PYTHONPATH=. python3 scripts/tool_surface_report.py [--json]`。
- **⚠ 与实验的关系**：这会改变所有臂看到的工具面。2×2 实验进行中请**不要**合入这一条，等实验收口后单独合并并单独测（见下方预测）。

## 3. 预测台账只读周报（`scripts/prediction_ledger_status.py`）

- 2026-10-01 实测：Open 表 162 条 = 证实 45 / 部分证实 2 / 证伪 3 / **过期 106**（pending 超 14 天，即全部 pending）/ 其他 6；最新编号 R-20260916，已 15 天没有新预测。
- `--max-silence-days N` 超期退出码 1，可挂 SessionStart / CI 提醒。不改台账；fix_type 冻结枚举未动（报告建议的 MODEL_FIX 需走 known-gaps 晋级线）。

## 4. 路由改写探针 + 口语 market_watch

- `intelligence/eval/cases/route_paraphrase_v1.jsonl`：uq15 每题 3 条改写（口语 / 调序 / 极简）。`scripts/route_paraphrase_probe.py` 走生产同款 `QueryResolver.resolve`，报一致率、兜底率、不一致明细。
- **必须在 Mac（有知识库）上跑**；沙箱锚点命中 0，数字不可引用。沙箱里只有不依赖实体的那组可信：「今天大盘咋样/怎样/走势如何」原先掉进 `general_finance_qa`，已修（谓词扩充，锚不变；题材题不被吞，有反向测试）。
- 仍未修、待 Mac 数据确认：调序（「今天成交额多少？大盘表现怎么样？」）与极简（「今日大盘 成交额」）仍落兜底；沙箱里原题兜底率 0.667，需看有知识库时是多少。

## 5. 内容正确性题集（质检 P1，后补）

- 动机：09-29 地图「格式和流程层的改进没有换来内容正确」；现有尺子只查形状。
- `intelligence/eval/content_correctness.py` + `intelligence/eval/cases/content_correctness_v1.jsonl`：15 题，三类各 5 题（后补第四类，见 5b）——
  `timepoint`（D0/D3、预计 vs 已发生）、`stock_flow`（净利润 vs 经营现金流承担资本开支）、`cfo_bridge`（间接法调整方向）。
- **标准答案与陷阱值都由代码按恒等式算**（`IDENTITIES` / `TRAPS`），不手填；加载时校验陷阱值与正确值、题面事实分得开。
- 判分以数值为主干：必须出现正确值；陷阱值（错误推理的指纹）一出现就判错。时点题用受控词表，现在时分强弱两档（「根据 9/1 公告，公司**目前**仍未获单」照样判错）。
- 题面自带材料（虚构公司），考推理不考检索——2×2 四个臂拿到逐字相同的输入：
  `python3 scripts/content_correctness_eval.py export --out prompts.jsonl` → 各臂作答 → `score --answers answers.jsonl`。
- 夹具：每题有金标答案（必须过）和坏答案（必须**因为标注的原因**被抓），含 10 份「结构齐全但内容错」的答卷；`selftest` 子命令 + `intelligence/tests/test_content_correctness.py`（15 条）。
- 局限：15 题是起步规模；文字检查只覆盖受控词表里的说法，换一种措辞的错误时点断言可能漏判（宁漏不误：金标全部通过）。题目扩充请沿用「事实 + 恒等式 + 陷阱」三件套。

| 草案 ID | fix_type | verification_prediction | 怎么验 |
|---|---|---|---|
| R-20261001-04 | EVAL_ONLY | 用本题集给 2×2 四格判分：若「强模型 + 薄循环」在 cfo_bridge / stock_flow 上显著高于「GLM + 8792」（≥ 3/5 题差距），内容错误主要是模型推理层，harness 加门禁救不回来；若 GLM 两格在数值题上相同、只在时点题上有差，harness 的价值集中在时点约束 | 四格各自导出题面作答，`score --json` 存档对比 |

### 5b. 第四类「单位与量纲」（+5 题，共 20 题）

| 题 | 考点 | 正确 | 陷阱 |
|---|---|---|---|
| cc-unit-01 | 行情库 `amount` 单位是千元（09-29 真实两日成交额） | 81.48 亿 | 当元 0.0815 / 当万元 814.8 |
| cc-unit-02 | 万元、亿元混算 FCF | −2.28 亿 | 不换算 18195.9 / 差一级 14.1 |
| cc-unit-03 | 毛利率 25% → 28% | 3 **个百分点** | 写成「3%」（只在 % 读数里找） |
| cc-unit-04 | 成交额环比 −17.24%（post986 证据行），较昨日减少多少亿 | 2935.28 | 用今日作基数 2429.24 / 把 % 读成亿 17.24 / 方向反 2072.02 |
| cc-unit-05 | 量比% 76.88，求 20 日均额 | 18328.19 | 当倍数 183.28 / 方向反 10832.94 |

- 判分支持三种读数：金额（换算到题目单位）、`%`、`个百分点`；陷阱按 `TRAP_KINDS` 在对应读数里找。撞车自检先把题面事实按各自单位换算，同量纲才比。
- 顺带修了抽取器两个**真实漏判**（旧三类题金额小，碰不到）：
  - 单位顺序：「1.41万亿元」先被「万」吃掉，读成 1.41 万元。
  - 日期正则 `\d{4}[-/.年]\d{1,2}` 把任何四位整数带小数的金额（2935.28、17025.99）当成「年.月」删掉。现在年份限 19xx/20xx、点号分隔须写全年.月.日。
- 出题时我自己把 14090.71 亿写成了 14,090,710,000 千元（应为 1,409,071,000）——被抽取器换算当场抓出。这正是本类题要量的错误，也是「答案由代码算」的理由。
- 生成器是一次性脚本，题目以 JSONL 为准；夹具 21 份坏答案 / 10 份金标，全部按标注原因判对。

## 6. 比较题丢失修复（Mac 改写探针 v1 的真 bug）——**实验结束前不合入**

- 现象（Mac 实测，可引用）：uq15-q04 原题「亨通光电和长飞光纤当天**分别**表现如何」→ comparison；三个改写（「亨通光电、长飞光纤那天咋样」「…**各自**涨跌如何」「亨通光电 **vs** 长飞光纤」）→ stock_deep_dive，第二家公司整个丢掉。
- 根因：比较判定只靠正则落点词；实体解析只取最长的一个名字。`QueryResolver._comparison_entities` 能找出全部点名公司，但只在历史意图下启用。
- 修法（3 个文件，小改）：
  - `query_resolution.py`：无条件找出点名公司，有锚点时传给信封。
  - `query_understanding.py`：`_names_company_pair`——≥2 家公司且不是关系 / 供货 / 映射题 → 加 comparison 算子；比较信封主体并成「甲、乙」（原来只认代称，真名时主体为 None）。
  - `research_contract.py`：追问的 `comparison_entities` 按「、」拆回逐个实体（修前 A16 只剩「高澜股份」，申菱环境丢失）。
- 验证：有词典的临时知识库下前后对比——4 道 q04、2 道双股题改判 comparison；单股 / 关系 / 供货 3 道负例与 A04 / A16 的 lane、owner、继承**一字不变**。新测 `test_comparison_named_pair.py` 10 条，修前 7 红 3 绿；全量 18629 passed、0 failed。
- 为什么暂不合入：改了路由，2×2 实验进行中合入会让 GLM + 8792 臂中途换规则。实验结束后合入，再在 Mac 上重跑改写探针 v2 看 q04 一致性。

## 7. 数值门禁漏审：短日期掩码吞掉带单位的数——**实验结束前不合入**

- 发现经过：给内容正确性题集修抽取器的日期 bug 后，回头查生产核验器有没有同类问题。
- 现象（沙箱可复现，`_dated` 夹具）：`_DATE_TOKEN_RE` 的无年份短写分支 `(0[1-9]|1[0-2])[-/.](0[1-9]|[12]\d|3[01])` 在抽数前把 `10.25元`、`12.15%`、`11.30亿`、`10-15倍` 当日期整段掩掉。
  | 条件句（证据里都没有该阈值） | 修前 | 修后 |
  |---|---|---|
  | 若跌破 9.25 元则止损 | 待核 | 待核 |
  | 若跌破 **10.25** 元则止损 | **放行** | 待核 |
  | 若涨幅超过 **12.15%** 才算突破 | **放行** | 待核 |
  | 若换手率升到 **11.30%** 则降级 | **放行** | 待核 |
  | 若市盈率落到 **10-15** 倍则降级 | **放行** | 待核 |
- 修法：短写分支加否定前瞻——后面紧跟数量单位（元 / % / 亿 / 倍 / 点 / 家…）的按数量审；跟日 / 月 / 年或不跟的照旧是日期。证据侧抽数本来就不掩日期，所以证据里真有的数修后照样对得上（专测覆盖）。
- 验证：新测 `test_short_date_quantity_mask.py` 19 条，修前 9 红；核验器相关 1696 条与全量 18668 passed、0 failed。
- **未完成：950 run A/B 只能在 Mac 上跑**（`runs/` 不进 Git；沙箱仅 2 个 run、0 命中）。`scripts/date_mask_ab.py --runs-dir <runs>` 列出「新受审」token 与所在句，条件句标 cond；逐条判断是复述还是自拟阈值。按 post986 纪律：新增待核全部是自拟阈值才合入。
- 为什么暂不合入：改的是判分门禁，2×2 实验中途合入会让 8792 臂换尺子。

## 8. 数值门禁掩码规则排查（26 种形状）与列表序号截断修复——**实验结束前不合入**

方法：造 26 句条件句（证据 ROW_0915 里都没有句中阈值），全部喂给真实的 `_novel_numeric_condition_tokens`，看哪些被放过。修 §7 后的结果：

| 形状 | 结果 | 结论 |
|---|---|---|
| 季度 / 型号 / MA20 / PE20 / E 号后的数、全角数字、U+2212 负号、千分位、万亿、成数、中文倍数、点位、% 区间、「3月内」「3个月内」 | 都挂出 | 正常 |
| `若跌破 10.25（E1）`（不带单位） | 放过 | 与日期「10.25」字面不可分；不带单位时维持现状 |
| `若跌破 10/25 低点` | 放过 | 确实是日期，正确 |
| **`10.37 元是关键支撑，若跌破…`（句首小数）** | **挂「37」** | **真 bug**：列表序号剥离把「10.」当序号剥掉。证据里有 10.37 也挂「37」（误报） |
| `- 3.85 元若失守…`、`20-30 倍估值若被突破…` | 放过 | 设计取舍：「若」前无比较词的数量按事实不按阈值（`trigger` 截断）；修完序号后仍放过，不动 |
| `若涨幅超过百分之八` | 放过 | 中文数量正则不认「百分之」；中文数字本来不与证据数值换算比对，补了只会多挂，不补 |

- 修法：`_LEADING_LIST_LABEL_RE` 的 `.` / `-` 后面紧跟数字时不算序号（`1.`、`3、`、`十、`、`2)`、`1- ` 照旧剥）。
- 验证：`test_short_date_quantity_mask.py` 增至 30 条（序号修复部分修前 4 红）；全量 18679 passed、0 failed。
- `scripts/date_mask_ab.py` 同时量两项修复（`kind=date / list_label`），按核验器同序（先掩日期再剥序号）模拟，避免把 `10-31日…` 误报成截断。

## 9. 证据侧：单位写在字段名里的证据值被误挂待核——**实验结束前不合入**

方法：用 finance_query 真实字段标签造证据行，条件句里正确复述证据值 37 句、自拟阈值 15 句，喂给 `_novel_numeric_condition_tokens`。修前 **16/37 句正确复述被挂待核**，根因同一个：单位住在字段名里，核验器只认了一部分（post986 修过 `量比%`，这次补齐同家族）。

| 证据字段 | 正确复述 | 修法 |
|---|---|---|
| `涨停家数=57` 等 `…家数` | 57 家 | 新 `_UNIT_NAMED_FIELD_RE` → 家 |
| `市盈率TTM` / `市净率MRQ` / 市销率 / 市现率 | 35.2 倍 | 同上 → 倍 |
| `上证收盘` / `指数收盘` | 3150.12 点 | 同上 → 点 |
| `竞价涨幅` / `5日涨幅` / `区间涨幅` | 2.3% | `_PERCENT_FIELD_RE` 加「涨幅」（auction_pct、gain_5d 均为 %） |
| `龙虎榜净买入亿` / `机构净买入亿` / 买入额 / 卖出额 / 资金流 | 1.23 亿元；`-0.56` → 净卖出 5600 万元 | 金额字段名单补齐；负数语境（新增「净卖出 / 净流出」）按绝对值认 |

修后 6/37 仍挂，均为刻意不放宽：`总市值`（各数据集口径不一：亿 / 原样美元）、「3150 点」（整数关口不算 3150.12 的复述）、「1.19 亿股」、由 `量比%` 换算的「1.36 倍」、「10 配 3」、「再跌 5.6%」对 −5.56。

**反方向（自拟阈值必须照挂）**：15/15 照挂，含贴近证据的整数（35 倍 vs 35.2、2% vs 2.3、1.2 亿 vs 1.23）和符号写反（证据净买入 −0.56，稿写「净买入超过 0.56 亿」）。

**多日撞车**（自己引入、自己堵上）：家数是整数，整数规则挡不住——绑着 30 天 `涨停家数`，自拟「低于 50 家」会撞上恰好是 50 的某一天。凑整写法（有效数字 < 2 位）只在该字段取值唯一时才算复述；「57 家」「3471 家」照认。

- 测试：`intelligence/tests/test_field_name_units.py` 36 条（修前 13 红）；全量 **18715 passed、0 failed**。
- **新工具 `scripts/numeric_gate_replay_ab.py`**：从 `continuous-episode.json` 按类型注解还原 `VerifiedEpisodeOutcome`（contract + structural_verifier），在两份代码上各跑门禁，`diff` 逐句列出「只在 A 挂 / 只在 B 挂」及该句证据原文。往返保真由 `test_numeric_gate_replay_ab.py` 锁住（按线上落盘同一 `to_dict()` 序列化，还原后门禁结论逐 token 不变）。合成 35 run 上 main → 分支：消失 12、新增 0。
- §7 / §8 / §9 三项修复都可以用它在 Mac 的真实 run 上验收（`date_mask_ab.py` 只能看文本、看不到证据）：

```bash
python scripts/numeric_gate_replay_ab.py run --runs-dir RUNS --code-root ~/finance-workspace-private --out /tmp/a.jsonl
python scripts/numeric_gate_replay_ab.py run --runs-dir RUNS --code-root /tmp/harness-opt --out /tmp/b.jsonl
python scripts/numeric_gate_replay_ab.py diff /tmp/a.jsonl /tmp/b.jsonl
```

验收口径：「只在 A 挂」应全是正确复述（每条附证据片段可目检），「只在 B 挂」应全是自拟阈值（§7/§8 的日期掩码、序号修复带来的）；`failed` 非零时先看还原失败原因。

## 建议台账条目（只给 ID 草案，未写入 `docs/prediction-ledger.md`，避免与实验 agent 冲突）

| 草案 ID | fix_type | verification_prediction | 怎么验 |
|---|---|---|---|
| R-20261001-01 | HARNESS_FIX | 实验收口后合入 §2：同模型同题集下，finance_query 空参数/畸形参数率下降，字段错槽率不升（≤ 基线 +1pp），单题 prompt token 下降 ≥ 8K | 合入前后各跑同一 uq15 臂，比 tool_call 校验失败分类 |
| R-20261001-02 | HARNESS_FIX | Linux 上 staging_swap 套件全绿（除 APFS 专属 1 条跳过）；Mac 生产换库行为不变 | CI + Mac 跑 `tests/test_market_feature_store_staging_swap.py` |
| R-20261001-03 | ROUTING_FIX | Mac 上 `route_paraphrase_probe.py` 改写一致率 ≥ 0.85；若兜底率 > 0.5，说明 8792 的改写失分主要在路由层而非模型层 | Mac 跑探针，`--json` 存档 |

## Mac 上验证

```bash
cd ~/finance-workspace-private && git fetch origin && git worktree add -b feat/harness-opt-1001 /tmp/harness-opt origin/main && cd /tmp/harness-opt && git am ~/Downloads/qc-p0-fixes.patch ~/Downloads/harness-opt-1001.patch && python3 -m pytest -q tests/test_market_feature_store_staging_swap.py tests/test_prediction_ledger_status.py intelligence/tests/test_tool_surface_budget.py intelligence/tests/test_market_watch_colloquial.py && python3 scripts/route_paraphrase_probe.py
```
