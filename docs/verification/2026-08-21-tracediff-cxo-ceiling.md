# Trace Diff：Cursor 直调组件 vs 生产 workbench 同题对照（2026-08-21）

> 题（反过拟合新题，未进任何 spec 正文）：`CXO概念这波是怎么发酵到 2026-08-20 的，涨幅、成交额和成交额环比怎么走`
> workbench 臂：生产 8792（`dfc25221` clean，episode A 引擎确认，产物含 `continuous-episode.json`），user `probe-tracediff-0821`，run `run_20260821_152044_472523`
> Cursor 臂：直调 `theme_lifecycle_timeline` / DuckDB canonical VIEW / `fact_theme_limit_heat_daily` / KB `query_relations.py`，答案在读 workbench 产物**之前**落盘锁定（sha256 `6f4a79d3…f302`）
> 产物归档：`~/.finance-runtime/live-probe-traceability/20260821-tracediff-cxo/`
> **结论：质量分叉不在模型、不在数据、不在工具——在判官投影层。判官把 1259 字草稿删成 437 字，删掉的 15 个数字逐条对库全真。**

## 逐层 diff

| 层 | workbench 实际发生 | Cursor 臂对照 | 分叉？ |
|---|---|---|---|
| 路由 | `decide_turn` 把「CXO概念」收短成 subject=`CXO` | 我直接用问句精确名 | **分叉1（入口）**。库里 `CXO` 仅 1 行孤儿（06-23 换代残留），`CXO概念` 42 行全序列 |
| 预取 | E1=`CXO 双红时间轴` **空**（「未锚定板块逐日行：CXO 在 07-10..08-20 无 fact_sector_daily 行」）；诚实报缺，未编造 | `load_theme_timeline_artifact('CXO概念')` 直接给出 发酵07-01~07-07/退潮/回流08-07~08-20 三段 + 缺口声明 | 分叉1 的代价显形：桌上零观察值。**下限守住了**（没编数），上限没供给 |
| 工具 | 模型自救成功：`finance_query` sector_daily 25 行（07-17~08-20，值=CXO概念口径）+ `mainline_context` 4 块 + `directional_news` 6 条（**抓到 mRNA 癌症疫苗 III 期真催化**）+ 成分股 10 行 | 同源 DuckDB + KB。KB 对 CXO 的证据停在 2026-04-17，7-8 月零覆盖 → 我如实声明缺口；workbench 的新闻工具反而补上了这块 | **无分叉，甚至 workbench 略优**（news 维度） |
| 草稿 | 1259 字：完整弧线（7-17 见顶 9.16%/530.96 → 7 月底缩至 ~300 亿 → 8-04/8-07 起爆 → 8-10 峰量 805.06 → 8-14/8-18 缩量 → 8-20 再双红）+ 产业链角色 + 情景树①②③ + 互斥假说 + 裁决 + 操作开关 | 我的答案：同样的弧线 + 阶段结构 + 涨停热度 + 领涨结构 + KB 缺口声明 | **无分叉。两臂草稿质量相当且互补**。模型引用（写手编号空间）逐条对得上证据表 |
| **判官** | `judge_status=repaired`，`evidence_alias_offset=29`。按错位后的投影判「E18/E19/E7/E35 不存在」「8-14 边际量为负未覆盖」→ **整句删**：正面回答弧线段、产业链段（契约必填 `chain_mapping`→`marker_loss`）、情景树全没了。1259→437 字 | 无此层 | **分叉2（主分叉）**。被删 15 个数字逐条对库全真（7-17 9.16/530.96 ✓、299.98/307.19/319.97 ✓、8-04 5.65 ✓、8-10 805.06 ✓、8-14 -22.43 ✓、药明 2.38/145.89 ✓、义翘 +17.55 ✓…） |
| repair | 1 轮，试图补 `chain_mapping` 失败，`marker_loss` 落账，`status=partial` | — | D3 无下限：删完必需输出救不回 |
| 公开稿 | 864 字，从半句「当日成交额环比+50.19%（E3）。」开始；题目要的序列只活下来 1 个数 | 全序列 + 阶段 + 结构 | 终态差距在这里定型 |

## 机制归因（2026-08-21 15:5x 更正：初版归因错了一层）

初版把主分叉归给 spec 的 **D2 双编号**——**不成立**。实查：`82a9fac6`（判官投影契约 C1–C4）**已合进 main 并 live 在 8792**，本 run `projection_ordinal_mismatch_count=0`，编号空间是对齐的。

真残余机制是 spec **刻意划出范围**的 A3 形状（§4「不把 A3 未绑定的日线补进判官 registry——那是写手 binding 缺口」+ §8 后续项）：

- **写手 binding 缺口**：模型正文引了 E7/E18/E19/E35，但没把这些卡绑进 `output_bindings`。`evidence_alias_offset=29` = 47 卡中 29 张未绑定。
- **未绑定卡不送判官**（INV-2 刻意保留的纪律）→ 判官 registry 里真没有 E7/E18/E19/E35 → 按它的入参「引用不存在」句句为真 → 整句删。判官和写手仍然都没错，这次错在**绑定步是模型依赖的、有损的**。
- **数字侧的解已经写好**：#289 第 4 刀明文「结构化观察值不受 binding 约束——模型写对了数却忘了绑，真话会被判成连坐删句」；本 doc 促成的第 10 刀（`f0ad6cfb`）把工具行也纳入观察值。两者合围后，数字不再依赖模型记得绑定。
- **仍无保护的残余类**：非数字散文引用未绑卡（叙事句、角色句）依旧会被删。候选修法：正文 E 引用经 `resolve_evidence_refs()`（已存在）自动 resolve 进 binding——是否破坏「only answer-bound evidence」纪律需单独论证，未实施。
  **【已结 2026-08-21 #298，`R-20260821-06`】** 实施形状与候选修法不同：不改写 bindings（draft 无结构分段，归属不可机械判定），改在**投影层**把「正文可反解引用」并进判官注册表选集——引用即答案对依赖的显式声明，未引用未绑定仍不送，纪律未放宽。上一行的函数名当时也写错了：`resolve_evidence_refs()` 是绑定数组的 E→hash 反解器，不做散文扫描；散文扫描是本次新增的 `cited_evidence_ordinals()`。
- **D3 侧**：`chain_mapping` 必填被删后 `marker_loss` 记账（repair_withheld 机制已 live 但本 run 未触发全灭闸——只灭了一格，不是全部）。契约层矛盾（evidence 模式禁权重知识 + 契约必填 chain_mapping + KB 无该题材链路证据）仍开放。

## 约束三筛判定（哪些封上限、哪些保下限）

| 约束 | 筛1 拦什么 | 筛3 模型变强会怎样 | 判 |
|---|---|---|---|
| 预取锚精确名 + 空表诚实报缺 | 输入 | 再强也需要本地口径 | **保下限**，留且加硬（#288 落地即修分叉1） |
| 工具层（finance_query/news） | 输入（供给事实） | 模型越强用得越好——本 run 模型靠它自救 | 下限的供给侧，纯增益 |
| 判官按错位投影做引用存在性否证 + 整句删 | **输出** | **写得越细、数字越多，被误删越多**（本 run 实测：最好的段落死得最惨） | **封上限主犯**。R-20260821-04 预测形状逐字复现 |
| evidence 模式禁权重知识写产业链角色，同时契约必填 chain_mapping，而 KB 无该题材链路证据 | 输出禁令 + 契约矛盾 | 模型知道的真角色越多删得越多 | **结构性不可满足**：要么补 KB 链路数据（输入侧修法），要么角色标签允许「常识声明」降级表述，要么该题型放掉必填。#289 第 6 刀已把「不可达必填格」投递进 trace，方向对 |
| repair 无必需输出下限（D3） | 输出 | 删格越深越失效 | 封上限帮凶，#287 INV-3 修 |

## 对在途工作的含义（随归因更正修订）

- **#287（判官投影契约）**：已合已 live，不是在途。本 run 证明它把 D1/D2 修干净了（mismatch=0），残余是它明文留下的 A3 binding 缺口。
- **#289（子单 B 槽位填数）**：方向被本 run 再次证实。本 run 被删的真数字来源是**工具行**而非预取行（预取空表）——第 10 刀 `f0ad6cfb` 已补：`finance_query` 的 sector_daily / sector_stock_daily 行级明细挂 StructuredObservation（矛盾格不产、聚合/无主体 fail closed），消费端零改动。spec §6.2「桌上的行 ∪ 有收据的工具行」右半边落地。
- **#288（预取精确名）**：分叉1 的现成解，未合。部署后预取行有数 → 槽有源。与 #289 仅 `asof_prefetch.py` 小幅重叠，后合方 rebase 即可。
- **未立项残余**：① 写手 binding 自动 resolve（散文真话保护）；② chain_mapping 契约矛盾（题材无链路证据时必填格结构性不可满足）；③ 路由 subject 收短（#288 刻意不改路由，只改预取锚）。
- **台账**：R-20260821-04 基线侧样本 +1（judge repaired + 段内含有据数字被整段删；本例数字来源为工具行、机制为 binding 缺口，标 adjacent shape）。n 仍不足 3，不结案。

## 两臂各自的短板（诚实记录）

- Cursor 臂：KB 7-8 月对 CXO 零覆盖且按约定不外呼 → 消息面只能声明缺口；workbench 的 `directional_news` 抓到了 mRNA III 期真催化。**检索面上 harness 不输**。
- workbench 臂：输给自己的出稿闸，不是输给检索或模型。

## 复算命令

```bash
# 两臂产物
ls ~/.finance-runtime/live-probe-traceability/20260821-tracediff-cxo/
# 判官前后草稿对照
python3 -c "import json;d=json.load(open('<run>/continuous-episode.json'));print(d['outcome']['draft']);print('----');print(d['semantic_verifier']['verified']['outcome']['draft'])"
# 被删数字验真
.venv-workbench/bin/python -c "import duckdb;con=duckdb.connect('db/market_feature_store.duckdb',read_only=True);print(con.execute(\"SELECT trade_date,pct_chg,amount,diff_ratio FROM fact_sector_daily WHERE sector_name='CXO概念' AND trade_date IN (DATE '2026-07-17',DATE '2026-08-10',DATE '2026-08-14')\").fetchall())"
```

---

## 合并、部署与同题 B 臂复验（2026-08-21 17:00 收口）

### 合并链（全部走 Gitea PR + 本机全量门禁，逐个绿了才合）

| PR | 内容 | 门禁收据 |
|---|---|---|
| #291 `fix/main-red-umask-registries` | 合并前置：干净 `dfc25221` 上全量本就有 **18 红**（Gitea 不跑 CI 的失守形状）。三根因：① 两个 ceiling 夹具 `_write_once` 的 mode 被进程 umask 削（agent shell 077 下 0o444→0o400，audit 严格比对即红；普通终端 022 全绿——同机两个读数），修法 `fchmod` 钉声明值；② `9d722a36` 加 `ledger.add("prefetch")` 未登记 `DURABLE_EVENT_KINDS`；③ `309cec07` 改名 `_emit_withheld_repair` 未跟 `_VIEW_CALLERS` 棘轮 | 5828 passed / 0 failed + ruff 绿 |
| #288 `fix/prefetch-evidence-id` | 预取行带 E 号 + 问句精确名优先（分叉1 的解） | 合新 main 后 5834 passed / 0 failed + ruff 绿 |
| #289 `fix/episode-slot-fill-numbers` | 十刀（含本 doc 促成的第 10 刀工具行观察值） | 合新 main 后 5877 passed / 0 failed + ruff 绿 + webapp lint/typecheck/test/build 四连绿 |

两条环境暗礁（跑全量的下一位注意）：**全量必须在 /Users 下的树跑**（codex 沙箱探针以 `__file__` 推 live root，树放 /tmp 会因沙箱可读 /tmp 而 unproven）；**`git worktree move` 后先清 `__pycache__`**（旧 .pyc 记旧绝对路径，`inspect.getsource` 炸）。

### 部署

沿用上次 switch 的真实流程（不是 rsync 原地覆盖）：`~/.finance-runtime/finance-workspace-6320b3bcbf82` 新建 worktree 快照 → `finance-workspace-runtime` symlink 切过去 → `launchctl kickstart` → 34s 就绪 → `audit_deploy_ledger.py record --action switch` 落账。health：rev `6320b3bcbf82`、dirty=False、matches=True。**回滚点**：symlink 指回 `finance-workspace-dfc25221b07b`（目录保留未删）再 kickstart。

### B 臂（同题异码）：`run_20260821_164659_624916`（user `probe-ab-0821-post`，75s）

| 层 | A 臂（8792@dfc25221，上午） | B 臂（8792@6320b3bc，部署后） |
|---|---|---|
| 预取 | E1 空（subject 收短成 `CXO`） | 锚到精确名：观察值 subject=`CXO概念`（timeline 卡带 obs），公开稿尾部预取事实 `2026-08-03 成交额亿=262.33` 对库 ✓ |
| 工具行 | 25 行真数据**零观察值** | `finance_query` 12/12 卡带观察值（第 10 刀），样例 药明康德 08-20 pct_chg=2.38 ✓ |
| 判官 | `repaired`，删 29/47 句（65%），被删 15 数全真 | `repaired`，**`rejected_claim_indexes=[]` 零删句**；唯一 issue 是**真实且正确的批评**（第 6 句「7-20至8-03 持续缩量」越界——库证实 7-27/7-29 有放量日），以「输出质检」段呈现而非删稿 |
| 投影 | mismatch=0（#287 已 live） | mismatch=0，alias_offset=0 |
| repair | 1 轮，chain_mapping 救不回 | **0 轮** |
| 公开稿 | 437 字，题目要的序列只活 1 个数 | 完整两波弧线 + 成分结构 + 链条 + 互斥假说 + 情景树；**31/31 实质数字全部有证据出处**（机械审计；唯一疑似 miss `-3.90` 是审计脚本尾零归一化盲区，库值 -3.9 在带收据时间轴上）；抽验 8 个交易日 17 个数值逐位对库 ✓ |

### ledger 臂（反过拟合新题）：`run_20260821_165210_889002`（减肥药，user `probe-ledger-0821`，120s）

- 判官 `repaired`、零删句、mismatch=0（alias_offset=17 但无错位——对齐机制在带偏移场景下也成立）。
- 七个关键节点（7-27/8-3/8-4/8-7/8-13/8-19/8-20）涨幅+成交额+环比逐位对库全真；环比口径「约35%/59%/91%」与库 35.45/59.38/90.92 一致。
- 16/16 实质数字有出处（2 个疑似 miss 是「跌0.23%」散文正负号 vs 观察值 -0.23 的审计脚本盲区，非出处缺失）。
- 消息面二手线索全部标「待验证/非一手公告」，缺口显式声明「缺公告级证据」——没有用散文圆过去。
- 判官又一条真实批评（第 10 句覆盖起点写 7-22，注册表最早 7-27）进质检段。

### 三筛判定的终态更新

「判官按投影做引用存在性否证 + 整句删」这条**封上限主犯**，在数字侧已被第 4+10 刀合围拆除：判官对槽内数字无删除权后，两个 live run 均零删句，且判官的产出转向**真实的措辞级批评**——下限（不编数）与上限（真话全量交付）第一次同时成立。散文侧 binding 缺口（叙事句引未绑卡）仍是已知残余，本轮未触发（两 run 引用全部可解析）。

---

## 反过拟合换形探针（2026-08-21 17:20，8792@`6320b3bc`）

收口章的两个 live run 与十刀甜区**同构**：同为板块发酵题形、同锚 08-20、同属医药链（CXO/减肥药）。为排除机制只在这一个形状上成立，加打两个换形探针（换板块族 + 换日期锚 + 白名单外数据集）。

**烧题状态（诚实声明）**：探针 1（钙钛矿电池→08-18）是**二手题**——上午 `-02` 的 live 臂尝试用过同一题文（见台账 `-02/-04` 脚注与 `2026-08-21-slot-fill-live-attempt.md`），但当时四臂全死在 `scenario_tree` 预检、未产出任何答案、修复代码也非按它调的，机制验证价值基本保留；离线侧当时已读出 08-18 的 `0.15/775.76` 两值，本探针与之一致。教训：烧题检查 `rg` 必须跑在 **gitea/main 树**，主检出树是特性分支、缺当天已合并文档，会漏检。探针 2（皇氏集团）全仓零提及，全新。

| | 探针 1 · 板块题换族换锚 | 探针 2 · 个股题（观察值白名单外） |
|---|---|---|
| 题目 | 钙钛矿电池到 2026-08-18 的发酵路径（新能源族；**库里 08-19 有 -6.13% 暴跌当泄漏陷阱**） | 皇氏集团 08-06..08-20 走势复盘（`stock_daily`/`dragon_tiger_daily` 均不在 `_OBSERVATION_SUBJECT_FIELDS`） |
| run | `run_20260821_171744_929436` | `run_20260821_171744_955225` |
| 判官 | `repaired`，mismatch=0 | `repaired`，mismatch=0 |

### 泛化成立的部分

- **数字全对**：两稿幸存数字 100% 逐位对库——板块 18+ 值（含 13 个工具行槽值在【主力个股】散文中原样幸存，第 10 刀的保护对象；5 个预取槽值经【预取事实】块送达），个股 9 交易日×2 指标 + 4 个龙虎榜净买入 + 区间收盘价。
- **as-of 干净**：预取时间轴与工具查询都切 08-18，08-19 暴跌零泄漏。
- **口径分歧 fail-closed 首次实战**：钙钛矿 07-08..07-24 库里真有双行脏数据（快照分代重叠），预取逐日标「不作为证据、禁合成」；模型仍合成「约千亿级降至 460-500 亿」→ 判官删——**合法删除**（合成值不是槽值，`numeric_unsupported` 打的是合成条件句）。
- **判官删除全部合法**：删的是合成区间、引未绑卡、无据链路角色、算术错句（3.15→3.51 被写成「基本回吐全部涨幅」「接近归零」）、发明阈值（「京东方维持 200 亿级」）。**零槽值被删**。个股题模型还主动抓出库里 08-06/08-07 双日同值的口径疑点并声明缺口——没编。

### 探针抓到的形状特有问题（均非本次合并的回归）

1. **残余①（散文引未绑卡）live 复现**：模型散文两处引 `E4`（反式钙钛矿产业化验证，**注册表里真有**）但忘写进 bindings → 判官按「未注册」删掉两句真因果。= `R-20260821-04` 判据的对偶面：槽内数字保住了，非数字散文的引用把手仍缺 binding 自动 resolve。**【已结 2026-08-21 #298，`R-20260821-06` confirmed：本 run 即机制证明工件（重放 after E4 入表）+ 冻结夹具 `pv-perovskite-e4.json`】**
2. **残余②（marker_loss）跨形状复现，机制看清了**：post-repair 的判官删除**没有第二次修复窗**（repair 已耗尽）。板块题 chain_mapping 因「行情行证明不了链路角色」被删（契约矛盾——必填格结构性不可满足）；个股题 direct_assessment 因直接判断句里有真算术错被删（**删对了，但整块强制输出跟着没了**）。两题都以道歉横幅收场。
3. **新发现（个股形状）**：`company_multi_layer_evidence` 契约把 `market_data`+`mainline_context` 定为 mandatory，但 90s 档预算 + 个股无预取覆盖 → `repair_goal.unreachable_without_tools` 且 `reopen_tools=False` → 注定 `missing_mandatory_capability`。→ 立案 `R-20260821-05`。
4. **预算观察**：两 run 主稿阶段都在第 3 轮 LLM `TimeoutError` → `deadline_exhausted`（`carried_draft_chars=0`），**全稿一发成于 40s 修复窗**。数字纪律在这条极限路径下仍全对，但它放大了 2 的暴露面：修复窗产的稿再被删就没有救场手段。

### 复算

```bash
ls ~/.local/share/finance-workbench/users/linxiaoqi5111/runs/run_20260821_171744_*
# 泄漏陷阱基准（08-19 = -6.13 不得出现在到-08-18 的叙事里）
.venv-workbench/bin/python -c "import duckdb;con=duckdb.connect('db/market_feature_store.duckdb',read_only=True);print(con.execute(\"SELECT trade_date,pct_chg,amount,diff_ratio FROM fact_sector_daily WHERE sector_name='钙钛矿电池' AND trade_date>=DATE '2026-08-12' ORDER BY trade_date\").fetchall())"
# 个股基准
.venv-workbench/bin/python -c "import duckdb;con=duckdb.connect('db/market_feature_store.duckdb',read_only=True);print(con.execute(\"SELECT trade_date,pct_chg,amount FROM fact_stock_daily WHERE stock_name='皇氏集团' AND trade_date>=DATE '2026-08-06' ORDER BY trade_date\").fetchall())"
```

> 操作注：两探针的会话落在主用户 `linxiaoqi5111` 名下（`POST /api/conversations` 的字段是 `user` 而非 `user_id`，传错键被 FastAPI 静默忽略、落回默认用户）——UI 会话列表里会看到两条 `antioverfit-*`，内容是真分析，可留可删。下次探针记得传 `user`。
