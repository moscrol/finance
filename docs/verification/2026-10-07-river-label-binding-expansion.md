# 河的可判标签词汇：4 → 7（已注册标签接线，口径不动）

日期：2026-10-07
前置：`docs/verification/2026-10-07-river-ci-contract-coverage.md`（本次测试跑在它引入的夹具库上）

---

## 1. 问题

`river_derive.SLICE_EVALUABLE_LABELS` 是**整条河的表达力上限**，不是一个内部实现细节：

| 下游 | 怎么用它 |
|---|---|
| `scenario_trees.compile_condition` | 分枝条件的 label 不在里面 → `E_LABEL_NOT_SLICE_EVALUABLE`，整棵树拒绝登记 |
| `judgment_maintenance.conditions` | 同一张白名单，谓词只能落在里面 |
| `research_evolution.adapters` | 可判观测目录只枚举它 |

扩张前它有 4 个词：`dual_red_strict` / `volume_surge` / `market_stage` / `limit_heat_rank`。
其中只有 `market_stage` 有段位语义。于是情景树能表达的 if/then 实际上只有
「大盘在某阶段 + 两三个布尔」，而 `ALL_LABELS` 里登记了 17 个标签、旁路库里躺着
174 万行标签值。**引擎是好的，能说的话太少。**

这件事此前不会让任何测试变红：白名单少一个词，只会让一种判读表达不出来。

## 2. 改了什么

接上三个**已经在 `ALL_LABELS` 里注册、切片里也已经算好、只是没接线**的标签：

| 标签 | 类型 | 取自 | 标签层同口径吗 |
|---|---|---|---|
| `multi_period_resonance` | sector / bool | 盘面轨量价行的同名列 | 是：两边都是布尔列的直接投影，无阈值 |
| `opinion_stage` | theme / text | 舆论轨的 `stage` 对象 | 是：两边都调 `opinion_stage.derive_stage(hits, day, knowledge_cutoff=day)` |
| `lifecycle_stage` | theme / text | 题材轨的 `stage` 对象 | 是：两边都是 `theme_lifecycle_timeline.derive_stages` 的 `daily=` 逐日态 |

**三件没有做的事**（这次扩张的边界）：

- 没有新造标签名 —— G-16 红线。新增测试 `test_白名单里的名字必须都是已注册标签` 把它钉死。
- 没有动任何阈值、没有升 `LABEL_VERSION` —— 口径一个字没改，只是河这边本来能判却没判。
- 没有重算 —— 绑定函数只从切片已有的对象上**取**值。重算等于把同一口径实现第三遍。

另外三处：

1. **`_sector_quote()`**：盘面轨同时发两个 `object_type="label"`（量价行、涨停热度行）。
   原来 `_first(..., "label")` 靠顺序取第一个，量价行缺而热度行在的那天会取到热度行——
   因为热度行没有 `pct_chg` 等键，`.get` 全返回 None，结果「碰巧」仍是「缺原料」。
   改为按 `sector_ts_code` 显式选行。**量价行存在时行为完全不变**，只是把巧合变成约定。
2. **`adapters.SLICE_EVALUABLE_LABELS` 去掉手抄副本**，改为 `tuple(river_derive.SLICE_EVALUABLE_LABELS)`。
   手抄件只会往一个方向出错：河扩了词、抄件没跟上 → 新标签在 01 的目录里不出现，
   **功能悄悄不生效，没有任何测试会红**。
3. **剩下 10 个标签为什么仍不绑定，逐条写进了代码注释**，省得下次有人重新判断一遍。
   其中 `limit_up / first_board / new_high_1y` 是真正的红线：河的实体是板块，
   在板块切片上「绑定」个股标签只能绑成某种聚合，而那是**另一个标签**，要新名字。

## 3. 夹具也补了

扩张前跑一遍发现：夹具库里 7 个标签有 4 个**恒为 None**
（`volume_surge` / `limit_heat_rank` / `multi_period_resonance` 整列空，`dual_red_strict` 恒 False）。
所有关于它们的断言都会通过而什么都没验到。

补了四条逐日序列（`DIFF_RATIO_BY_DAY` / `RESONANCE_BY_DAY` / `VOLUME_PCT_BY_DAY` / `HEAT_RANK_BY_DAY`），
让每个标签在 15 天里真 / 假 / 缺三种结局都出现过。`VOLUME_PCT_BY_DAY` 里刻意放了一个
**恰好等于阈值 10.0** 的日子：边界写成 `>=` 而不是 `>` 时，只有这一格会红。

这件事本身由 `test_夹具必须让每个可判标签都出现过非空值` 守住——以后再加标签，
忘了喂值会直接红，并把人指回 `*_BY_DAY`。

副作用（正面的）：`lifecycle_stage` 现在在夹具里真的走过 发酵 → 主升，
于是区间派生第一次有了 `market_stage` 之外的第二个跃迁源。

## 4. 读数

```
$ FWP_ALLOW_ANY_PYTHON=1 .venv-qc/bin/python -m pytest \
    tests/test_river_contract_on_fixture.py -q
37 passed in 17.00s                                    # 扩张前 26

$ ... -m pytest intelligence/tests/test_label_binding_parity.py -q
4 passed in 1.04s                                      # 扩张前 2

$ ... -m pytest <全部 import 了 river_derive / scenario_trees /
    research_evolution / SLICE_EVALUABLE 的测试> tests/test_river_*.py
    intelligence/tests/test_river*.py
    intelligence/tests/test_methodology_backtest.py -q
673 passed, 43 skipped, 15 subtests passed in 162.62s

$ ruff check <5 个改动文件>
All checks passed!
```

贯通验证：

```
adapters 可判标签: ('dual_red_strict', 'volume_surge', 'market_stage', 'limit_heat_rank',
                   'multi_period_resonance', 'opinion_stage', 'lifecycle_stage')
scenario_trees 看到: 同上
```

夹具区间上每个标签的实际取值分布（15 天）：

| 标签 | 非空 | 取值集合 |
|---|---|---|
| `dual_red_strict` | 13/15 | False, True |
| `volume_surge` | 13/15 | False, True |
| `market_stage` | 15/15 | 主升, 分歧, 退潮, 震荡 |
| `limit_heat_rank` | 13/15 | 1 … 15 |
| `multi_period_resonance` | 12/15 | False, True |
| `opinion_stage` | 15/15 | 萌芽, 扩散 |
| `lifecycle_stage` | 14/15 | 发酵, 主升 |

## 5. 新增的 11 条契约

| 测试 | 守什么 |
|---|---|
| `test_夹具必须让每个可判标签都出现过非空值` | 恒空列 = 假绿，直接红 |
| `test_新接线的标签在切片上真的出值并带_ref` ×3 | 出值 **且** 带 ref（只出值会让 member_refs 静默为空） |
| `test_白名单里的名字必须都是已注册标签` | G-16：河不新造标签名 |
| `test_下游看到的可判名单与河完全一致` | 杀掉手抄副本漂移 |
| `test_resonance_是布尔列的直接投影_不做任何解释` | 绑定层不得自作主张 |
| `test_lifecycle_取当天读数而不是段落表的事后视角` | PIT：不得取 `segment_hindsight.stage` |
| `test_opinion_stage_取舆论轨已算好的那个对象_不重算` | 不出现第三份实现 |
| `test_新标签立刻可以作为情景树的分枝条件` | **本次扩张的验收**；并反向验仍判不了的标签照旧被拒 |
| `test_lifecycle_跃迁可被_derive_transitions_抓出` | 新的线状对象；并钉住「缺一天 → unverifiable，不是没跃迁」 |
| `test_resonance_两层同判` + `test_resonance_夹具覆盖三种结局` | SQL ↔ 绑定层逐格 parity |

## 6. 一处已知且故意保留的不对称

`opinion_stage` 在两层的实体口径不同：

- 标签层按 `sector_ts_code` 归并该代码历史上的**全部曾用名**再取研报命中并集（实测 `990380.FP` 有两个名字）；
- 河这边只用当前切片的 `entity_name` **一个名字**匹配。

改过名的板块，在改名前后会有口径不同的日子。**没有在绑定层偷偷补**：
河的实体归一属于 `resolve_entity` / `config_sector_alias` 的职责，那才是该修的地方
（实测 `config_sector_alias` 0 行，见质检报告 P2）。此处只在 `_bind_opinion_stage`
的 docstring 里写明，避免下游以为两边恒等。

## 7. 没有解决的

- **词汇仍然不够。** 7 个词里只有 3 个有段位语义。母本 §1.4 的十个旗标（B 类阈值空白）
  才是真正的解锁点，那是创始人的判断不是工程量。这次只是把**已经造好但没接线**的部分接上。
- `amount_rank_top10` / `mainline_flag` 仍判不了：前者要当日 published 名单的横截面，
  后者要 `fact_mainline_sector_daily`，两者都不在六轨取数范围内。
- `window()` 仍只默认挂 `cumulative`，`cumulative.member_refs` 仍为空（质检 P2，未动）。

## 8. ⚠ 合并前必做

本文全部读数取自 **Python 3.11 + `.venv-qc` + `FWP_ALLOW_ANY_PYTHON=1`**，
不是契约规定的 3.12.13 `.venv-workbench`（该 venv 不在版本库里，干净 clone 中不存在）。
conftest 的不可比告警全程在打。

顺带记录一个与本改动无关、但在 3.11 下暴露的事实：
`skills/duckdb-backfill/scripts/qa_local_vs_fupanhui.py:172` 用了 3.12 才允许的
嵌套同引号 f-string，3.11 上 `tests/test_qa_local_vs_fupanhui.py` 直接收集失败。
这从侧面印证了解释器门禁的必要性。

---

# 附：agent 真实消费实验（同日追加）

扩张做完后的质疑是对的——「词汇变多」是不是只是个好听的数字。所以真跑了一次对照实验：
同一组操盘手问题，分别在**扩张前 4 词**与**扩张后 7 词**的白名单下走河的公开接口，
不碰内部表、不读 SQL。

⚠ 夹具是合成数据，所以**任何关于行情的结论都是假的**。实验测的是**消费力学**
（要几步、吞多少原始事实、哪些问题根本问不出来），这部分与数据真假无关。

## 1. 可表达性：5/9 → 9/9

| 问题 | 4 词 | 7 词 |
|---|---|---|
| 此刻这个板块在什么状态 | ✅ 4 个标签 | ✅ 7 个标签 |
| `market_stage` 什么时候换的段 | ✅ 6 次跃迁 | ✅ 6 次跃迁 |
| `lifecycle_stage` 什么时候换的段 | ❌ 白名单里没这个词 | ✅ `2026-08-20 发酵→主升` |
| `opinion_stage` 什么时候换的段 | ❌ 同上 | ✅ `2026-08-19 萌芽→扩散` |
| 连续双红几天 | ✅ longest=3 | ✅ longest=3 |
| 「题材主升 **且** 多周期共振」的日子 | ❌ 编译被拒 ×2 | ✅ 5 天 |
| 盘面/题材/舆论三口径此刻各自怎么说 | ❌ 只拿到 1/3 | ✅ 3/3 |
| 每个读数能不能拆回源行 | ✅ | ✅ |
| 无覆盖实体：报缺口还是编数 | ✅ 如实报 Gap | ✅ 如实报 Gap |

第 3、4、6、7 行是这次扩张的全部增量。其中第 7 行（三口径联立）是质检报告里
「联立 = 五段缺一不发」那条设计意图第一次真的能走通——扩张前三条里有两条问不出来。

## 2. 压缩率 88 : 1

```
15 天区间的原始切片    117,639 字符 / 204 个对象
同样信息的结构化答案     1,335 字符
压缩率                    88.1 : 1   （agent 少读 98.9% 的字符）
```

「同样信息」= 三条跃迁序列 + 一条 streak + 当日 7 个标签读数，每一项都带 `refs`。
这不是摘要——是**无损的**：每个结论都能拆回原始行，原始行随时可按 ref 取回。

## 3. 自描述：大部分可以，有一个洞

一个没读过源码的 agent 能自己发现：

- ✅ 可判词汇可枚举（`SLICE_EVALUABLE_LABELS`）
- ✅ 每个标签的类型与合法算子可查（`LABEL_KINDS` / `OPS_BY_KIND`）
- ✅ 问一个不存在的标签，报错 actionable：
  `'ma5_peak_confirmed' 需要历史或个股级原料，单日切片判不了；用 streak / transition 派生表达`

**洞**：text 标签的**取值**从哪来？

```
lifecycle_stage  value='主升段'   编译过  命中 0/15 天   ❗不在词表内
opinion_stage    value='过热'     编译过  命中 0/15 天   ❗不在词表内
market_stage     value='主升阶段'  编译过  命中 0/15 天   （根本查不到词表）
```

编译器此前只查字符白名单（不许有 SQL 味），**不查值在不在词表里**。写错一个字，
条件编译通过、运行零报错、永远命中 0 天——而「从未成立」与「今天没成立」在读数上
长得一模一样。**这和 derive_streak 对分类标签返回 longest=0 是同一个形状的错。**

`market_stage` 更糟：词表确实存在，但埋在
`method_validation/flywheel.py:1092` 的一个正则里 `(主升|反弹|横盘|顶部横盘|底部横盘|下跌|探底)`，
没有任何地方把它声明成词表。agent 唯一可靠的办法是先扫一遍历史统计取值分布再写条件——
「数据没有自带坐标系，消费方必须自己重建」的最小实例。

## 4. 据此追加的修复：文本谓词取值域检查

新增 `rules.text_domain_error(label, value)`，由规则 DSL 与情景树编译器**共用**（不抄第二份）。
两类标签分开处理，**不一刀切成有限枚举**：

- **本仓自己派生的**（`opinion_stage` / `lifecycle_stage`）→ 封闭词表，值不在里面直接拒。
  词表从各自 SSOT 现取（`opinion_stage.STAGES` / `theme_stage_vocab.CANONICAL_STAGES`），
  测试钉住不得抄副本。
- **上游供应商拥有取值的**（`market_stage`）→ `OPEN_TEXT_LABELS`，**不得声明有限词表**。
  `normalize_market_stage` 的 docstring 明写规则是 data-driven 而非有限别名表，
  硬编一张表会在供应商新增段位时把合法条件判成非法，比漏判更糟。
  但有一件与枚举无关、一定能查的事：**值必须已经是归一形式**（`normalize(v) == v`）。
  这正好逮住最可能犯的那个错，且不需要任何词表。

效果：

```
lifecycle_stage '主升段'   → 拒：不在词表里；合法取值：['酝酿','首发','发酵','主升','分歧','退潮','回流']
opinion_stage   '过热'     → 拒：不在词表里；合法取值：['萌芽','扩散','拥挤','退热','证伪','unverifiable']
market_stage    '主升阶段'  → 拒：不是归一形式，绑定层给出的是 '主升'，请写 '主升'
market_stage    '反弹'     → 放行（夹具里一次没出现，但它是上游合法段位）
```

报错把合法词表直接摊给调用方——agent 看完报错就能自我纠正，不用回去读源码。
最后一行是关键的**反向**验证：不能为了拦住错词而误杀合法的新段位。

读数：`1155 passed, 49 skipped, 30 subtests passed`（全部 import 了 river_derive /
scenario_trees / research_evolution / methodology_backtest / judgment_maintenance 的测试）；
契约测试 37 → 48；ruff 全绿。

## 5. 顺带更正质检报告里的一条结论

质检报告 P2 写「`window()` 的 `cumulative.member_refs` 为空」。夹具上实测
**45 条，不为空**。该结论要么是真库特有、要么是我当时读错了，在此更正。
`window()` 默认只挂 `cumulative` 一种派生（而非五种）这一条仍然成立。

## 6. 实验没能证明的

- **行情分析质量没有被证明。** 夹具是合成数据，9/9 可回答说明的是「问题接得住」，
  不是「答案对」。要证后者必须在真库上重跑。
- **`market_stage` 的词表仍未声明**，只是挡住了未归一的写法。真正的解法是 G-05
  （质检报告里标注为阻塞 G-07/08/09/15 的那条），这次没动。
