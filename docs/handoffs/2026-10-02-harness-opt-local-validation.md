# 2026-10-02 · harness-opt 本地验证回报

按 `docs/handoffs/2026-10-01-local-agent-spec.md` 第 2 节起执行。时区 Asia/Taipei。本轮验证结束；补丁尚不能签收：路由一致率未达 0.85，数值门禁有 3 条确认异常。本轮没有修改实现、题集、生产数据或预测台账，没有推送、合并、部署或调用真实模型。

## 0–1. ✅ 代码身份与已完成的补丁

```text
worktree=/private/tmp/harness-opt
branch=feat/harness-opt-1001
tested_revision=fb03e8e37fb845e86a84fed4939d3e331143b9d1
tested_tree=d94cedf89ba915c649ef045a19be6a808c6a3554
baseline=3a2718c6c7dbf5af8ddad249b50835d09deef8a4
patch_commits=19
initial_status=?? 30
```

指纹与云端要求完全一致。`30` 是原有空文件，本轮保留。仅在验证后增加本报告和 inflight 文档；测试与 A/B 结论始终归属于上面的代码提交。

```text
fb03e8e37 fix(routing): no-retrieval lane audit — market wording, look-at-X subjects, 什么叫/怎么计算
5c892d966 docs(handoff): local-agent task spec for commits 7-17 (apply, macOS tests, KB probe, gate replay A/B, merge order, user decisions)
e28615d4d fix(routing): analysis questions are not definitions; theme after grammar words; reordered market_watch
699dcdd84 fix(routing): in-question antecedents no longer bounce self-contained questions; colloquial market wording routes to research
76aa57e43 fix(verifier): bind units carried in evidence field names (家数/估值倍数/指数收盘/涨幅/净买入)
d279a4ba8 fix(verifier): leading list-label strip no longer truncates decimals and ranges
b244bb8b3 fix(verifier): short-date mask no longer swallows quantities with a unit
09aafe885 feat(eval): unit/dimension class for the content-correctness set (+5 cases)
b34a65e98 fix(routing): two named companies without a comparison cue still route to comparison
6cd34de5c feat(eval): deterministic content-correctness set for the three 09-29 error classes
465c0bb63 test: skip macOS-only tests precisely on Linux (zsh / clonefile / py3.12)
64eca9ee6 feat(probe): measure the decide_turn route (lane/question_type), clarify and llm_fallback counts
97934e6a9 fix(scripts): probe/report scripts put repo root on sys.path (run as python3 scripts/x.py)
ac09d0e88 docs(handoff): 2026-10-01 harness optimization notes + ledger drafts
9c89b288a feat(routing): paraphrase stability probe + colloquial market_watch predicates
84c91c8d4 feat(scripts): read-only prediction ledger status (expiry + silence gate)
a761071a5 perf(finance_query): drop union field enums from the provider schema (-32% tool surface)
5837a5687 fix(market_feature_store): swap lock uses OFD locks on Linux + per-process self-check
7dc4f1050 fix(qc-p0): skill 视图改正 + 429 有界退避 + 模型准入闸
```

## 2. ✅ Mac 相关测试；可选全量未跑

严格使用 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`，Python 3.12.13，Darwin arm64。执行任务书列出的全部 17 个文件，额外加 `-rs` 输出跳过原因，并用独立 `--basetemp` 隔离临时数据。

```text
.....................................................s.................. [ 15%]
........................................................................ [ 31%]
........................................................................ [ 46%]
........................................................................ [ 62%]
........................................................................ [ 78%]
........................................................................ [ 93%]
............................                                             [100%]读数收据: /Users/a77/.finance-runtime/test-receipts/20261001T172229Z-fb03e8e3-449cecb2088d.json

=========================== short test summary info ============================
SKIPPED [1] tests/test_market_feature_store_staging_swap.py:1434: flock 与 DuckDB 锁互斥只在 Linux 上失效
459 passed, 1 skipped in 11.46s
```

唯一跳过用例：`tests/test_market_feature_store_staging_swap.py::test_plain_flock_fails_the_self_check_on_linux`。它验证 Linux 上原始 flock 无法排斥 DuckDB 写者的故障，macOS 按代码设计跳过；已如实列出这条平台差异。其他 macOS 换库/克隆相关用例通过。无失败用例，因此无需追加 `-x --tb=short` 失败复跑。

**环境边界**：`workspace.py doctor` 报 `httpx` 实装 0.25.2、锁定 0.28.1，未修改共享环境。本轮仅报告指定测试集，未开展可选全仓测试，不宣称全量绿、依赖合同通过或合入门禁通过。原有空文件使树状态为 dirty，收据也不能冒充干净 revision 的全量收据。

## 3. ❌ 真实知识库路由探针未达门槛

知识库为 `/Users/a77/knowledge-base-private/wiki`；两臂 `anchor_hits=16>0`，读数有效。基线由 `git merge-base HEAD origin/main` 得到；临时基线树只复制候选的同一探针和改写题集，使两臂都量 `decide_turn` 的实际车道。基线树放在本工作树的忽略目录下，验证后已安全移除。知识库 aliases/entity_exposures 的 SHA-256 在核对前后未变化，摘要保存在 data-manifest.json。

| 指标 | 基线 | 修后 |
|---|---:|---:|
| `anchor_hits` | `16` | `16` |
| `consistency` | `0.622` | `0.822` |
| `consistency_by_style` | `{"colloquial": 0.667, "reordered": 0.667, "terse": 0.533}` | `{"colloquial": 0.867, "reordered": 0.933, "terse": 0.667}` |
| `clarify_count` | `3` | `0` |
| `llm_fallback_count` | `0` | `0` |
| `seed_fallback_rate` | `0.067` | `0.0` |

一致率从 28/45 提升到 37/45（0.622 → 0.822），高于 Mac v1 的 0.733，**但仍低于 0.85，不能验收通过**。clarify 3→0、llm_fallback 0→0 满足其余两条门槛。

修后全部 8 条 mismatches（原始 JSON）：

```json
[
  {
    "seed": "uq15-q01",
    "style": "colloquial",
    "seed_type": "research/quick_fact",
    "paraphrase_type": "knowledge/quick_fact"
  },
  {
    "seed": "uq15-q01",
    "style": "terse",
    "seed_type": "research/quick_fact",
    "paraphrase_type": "workflow/general_finance_qa"
  },
  {
    "seed": "uq15-q03",
    "style": "terse",
    "seed_type": "workflow/general_finance_qa",
    "paraphrase_type": "workflow/dated_market_review"
  },
  {
    "seed": "uq15-q06",
    "style": "terse",
    "seed_type": "workflow/stock_deep_dive",
    "paraphrase_type": "research/stock_deep_dive"
  },
  {
    "seed": "uq15-q07",
    "style": "colloquial",
    "seed_type": "research/theme_analysis",
    "paraphrase_type": "research/general_finance_qa"
  },
  {
    "seed": "uq15-q07",
    "style": "terse",
    "seed_type": "research/theme_analysis",
    "paraphrase_type": "research/market_cause"
  },
  {
    "seed": "uq15-q09",
    "style": "reordered",
    "seed_type": "research/theme_analysis",
    "paraphrase_type": "research/general_finance_qa"
  },
  {
    "seed": "uq15-q14",
    "style": "terse",
    "seed_type": "workflow/market_watch",
    "paraphrase_type": "research/general_finance_qa"
  }
]
```

对应题面：

- `uq15-q01/colloquial`：8月14号那个周五，沪深两市一共成交了多少钱？比前一天多还是少？上证收盘多少点？ → `knowledge/quick_fact`；needs_retrieval=True。
- `uq15-q01/terse`：2026-08-14 两市成交额和上证收盘 → `workflow/general_finance_qa`；needs_retrieval=True。
- `uq15-q03/terse`：2026-08-13 复盘：领涨方向 量能 最高板 → `workflow/dated_market_review`；needs_retrieval=True。
- `uq15-q06/terse`：亨通光电涨停逻辑和基本面 → `research/stock_deep_dive`；needs_retrieval=True。
- `uq15-q07/colloquial`：8月14号稀有金属涨了两个多点，在炒什么？哪些票是代表？ → `research/general_finance_qa`；needs_retrieval=True。
- `uq15-q07/terse`：稀有金属 8/14 上涨原因 代表股 → `research/market_cause`；needs_retrieval=True。
- `uq15-q09/reordered`：A股医疗服务有哪些代表公司？它和医疗器械的边界在哪？上中下游分别是什么？ → `research/general_finance_qa`；needs_retrieval=True。
- `uq15-q14/terse`：今日大盘 成交额 → `research/general_finance_qa`；needs_retrieval=True。

重点核对：q04 原题及 3 种改写均为 comparison；q05 光纤光缆和 q10 空芯光纤均为 theme_analysis；真实词表含“空芯光纤”。q07 口语版丢主体、落 general_finance_qa，极简版为 market_cause；q09 调序版丢主体、落 general_finance_qa。q14 调序版为 market_watch，极简版仍为 general_finance_qa。

额外核对“茅台咋样”：无实体锚点，禁用控制器模型的确定性探针输出 `chat/general_finance_qa, needs_retrieval=false`。这是额外 1 题，不混入上述 60 题统计；它反映确定性识别仍依赖别名，不能据此断言真实控制器模型运行后必然走聊天车道。

## 4. ❌ 数值门禁 A/B 未通过

扫描真实用户态 `/Users/a77/.local/share/finance-workbench/users` 下的全部存证。两臂成功集合完全一致，955 个 run 导出的 evidence 内容逐一相同，run ID 无碰撞。

```text
code-root=/tmp/harness-opt/tmp/local-agent-validation-1002/base runs=966 restored=955 failed=11 runs_with_flags=159
  restore-failure x7: TypeError: 'NoneType' object is not iterable
  restore-failure x4: KeyError: 'structural_verifier'
code-root=. runs=966 restored=955 failed=11 runs_with_flags=156
  restore-failure x7: TypeError: 'NoneType' object is not iterable
  restore-failure x4: KeyError: 'structural_verifier'
```

11 份失败存证中，7 份 `structural_verifier=null`，4 份缺少该字段。未改存证、未补默认值、未绕过还原器；结论只覆盖成功还原的 955 份。失败原文及 run：

```text
run_20260812_210333_302094: TypeError: 'NoneType' object is not iterable
run_20260812_231941_685779: TypeError: 'NoneType' object is not iterable
run_20260812_232845_389464: TypeError: 'NoneType' object is not iterable
run_20260812_235054_369717: TypeError: 'NoneType' object is not iterable
run_20260813_020348_316467: TypeError: 'NoneType' object is not iterable
run_20260813_091911_126816: TypeError: 'NoneType' object is not iterable
run_20260813_100853_570273: KeyError: 'structural_verifier'
run_20260813_102820_830513: KeyError: 'structural_verifier'
run_20260814_023028_065274: KeyError: 'structural_verifier'
run_20260814_030002_744434: KeyError: 'structural_verifier'
run_20260917_202956_828111: TypeError: 'NoneType' object is not iterable
```

`gate_ab.txt` 前 5 行原始输出：

```text
common runs=955 (only A=0, only B=0)
flagged tokens: A=380 B=371  disappeared=11 appeared=2
== 只在 A 挂（B 放行）——应全是正确复述
  [58家] 若量比继续走低且涨停家数降至前低（8月11日58家）附近，则需警惕底部横盘转向缩量阴跌。
      run=run_20260813_031355_149276
```

两栏原始输出如下。消失栏共 11 条，全部保留（超过要求的抽 10 条）；新增栏 2 条全部保留。脚本的证据片段只按数字子串取前 4 条，有日期/无关字段噪声；下方人工复核另回到完整绑定卡。

```text
common runs=955 (only A=0, only B=0)
flagged tokens: A=380 B=371  disappeared=11 appeared=2
== 只在 A 挂（B 放行）——应全是正确复述
  [58家] 若量比继续走低且涨停家数降至前低（8月11日58家）附近，则需警惕底部横盘转向缩量阴跌。
      run=run_20260813_031355_149276
      证据: 1日净流入=-358781783
      证据: 2026-08-12 20:58:00 证券日报
      证据: 涨停家数=58
  [21家] ④跌停家数不超过21日的21家。
      run=run_20260813_031522_760743
      证据: 全市场成交额：21522.76 亿元
      证据: 成交额 25286.07 → 21522.76 亿元
      证据: 成交 21522.76 亿
      证据: 交易日=2026-07-21
  [24家] 若用前一交易日7月24日作参照，市场整体偏弱：上证指数收跌1.61%，成交额较前一日下降约11.83%，上涨家数明显少于下跌家数，涨停40家、跌停24家，盘面属于缩量下跌和风险偏好走弱。
      run=run_20260815_035158_446415
      证据: 交易日=2026-07-24
      证据: 跌停家数=24
      证据: 交易日=2026-07-24
      证据: 交易日=2026-07-24
  [3814.198点] 若用前一交易日7月24日作参考，市场偏弱：上证指数收于3814.198点，下跌1.6142%；
      run=run_20260815_112806_561627
      证据: 上证收盘=3814.198
  [23家] 条件化：后续若重新双红、成交额回6000亿以上、涨停家数突破23家前高，升级为主升；
      run=run_20260822_015527_733974
      证据: 成交额亿=7123.3
      证据: 交易日=2026-07-23
      证据: 边际量=2.23
      证据: 边际量=-23.55
  [37家] 指数若继续缩量，科技抱团存在拥挤后补跌风险，如8-19指数-2.4%时涨停数骤降至37家所示（E3）。
      run=run_20260824_014134_796997
      证据: 强势股成交占比=16.37
      证据: 涨停家数=37
      证据: 成交额亿=3773806.592
      证据: 1日净流入=3703716918
  [14家] 分支一：若周一芯片/电子涨停热度维持或回升（8-21芯片涨停14家、热度第3，E17；
      run=run_20260824_014139_633829
      证据: 涨停家数=14
      证据: 市场占比=14.81
      证据: 市场占比=14.81
      证据: 市场占比=14.81
  [+21.23%] 分支三：若医药龙头恒瑞医药、药明康德继续走弱（8-21分别-3.56%、-3.00%，E44、E33）而题材端沃森生物（+6.48%、5日+21.23%，E36）独强，则医药主线进入高位分歧，likelihood中低（龙头弱于题材的背离已现）。
      run=run_20260824_014139_633829
      证据: 5日涨幅=21.23
  [42 家] 条件化判断：若后续几日成交额回升且涨停家数放大至明显多于 42 家，可视为企稳信号；
      run=run_20260827_153436_514397
      证据: 涨停家数=42
  [1530家] 依据是：7月22日市场虽被标记为反弹阶段，但上证仅涨0.069%，上涨1530家，成交额26531.66亿元、环比缩量10.27%，低于20日均额30114.45亿元，暂不支持全面进攻；
      run=run_20260907_013435_437219
      证据: 上涨家数=1530
  [2家] 若热度跌回1–2家、排名百名外则降级。
      run=run_20260907_194929_923052
      证据: 交易日=2026-09-07
      证据: 交易日=2026-09-03
      证据: 涨停家数=2
      证据: 交易日=2026-09-02
== 只在 B 挂（A 放行）——应全是自拟阈值
  [6.49→12.11] 3) 累计涨幅巨大（6.49→12.11 元，E9→E1），获利盘丰厚，缺乏公司一手公告核验的催化支撑，新闻归因（迎峰度夏用电负荷、电力板块涨停潮、立新能源6连板）仅为新闻二手表述（E25、E28），未经公告确认。
      run=run_20260820_131240_381743
      证据: 收盘价=6.49
  [10.27%] 依据是：7月22日市场虽被标记为反弹阶段，但上证仅涨0.069%，上涨1530家，成交额26531.66亿元、环比缩量10.27%，低于20日均额30114.45亿元，暂不支持全面进攻；
      run=run_20260907_013435_437219
      证据: 成交额环比=-10.27
```

### 全部差异的人工复核

| 方向 | run | 数量 | 判断 |
|---|---|---|---|
| disappeared | `run_20260813_031355_149276` | `58家` | 数值复述有对应指标证据 |
| disappeared | `run_20260813_031522_760743` | `21家` | 数值复述有对应指标证据 |
| disappeared | `run_20260815_035158_446415` | `24家` | 数值复述有对应指标证据 |
| disappeared | `run_20260815_112806_561627` | `3814.198点` | 数值复述有对应指标证据 |
| disappeared | `run_20260822_015527_733974` | `23家` | 条件阈值边界项：数值来自同指标历史基准，但预测判据由模型提出，不能计作纯事实复述通过 |
| disappeared | `run_20260824_014134_796997` | `37家` | 数值复述有对应指标证据 |
| disappeared | `run_20260824_014139_633829` | `14家` | 数值复述有对应指标证据 |
| disappeared | `run_20260824_014139_633829` | `+21.23%` | 数值复述有对应指标证据 |
| disappeared | `run_20260827_153436_514397` | `42 家` | 条件阈值边界项：数值来自同指标历史基准，但预测判据由模型提出，不能计作纯事实复述通过 |
| disappeared | `run_20260907_013435_437219` | `1530家` | 数值复述有对应指标证据 |
| disappeared | `run_20260907_194929_923052` | `2家` | 确认异常：题材涨停热度被全市场跌停家数同值错误放行 |
| appeared | `run_20260820_131240_381743` | `6.49→12.11` | 确认误报：绑定证据已有对应价格端点 |
| appeared | `run_20260907_013435_437219` | `10.27%` | 确认误报：缩量 10.27% 对应成交额环比 -10.27 |

**确认异常 1：跨指标放行 `2家`。** 原句：

> 若热度跌回1–2家、排名百名外则降级。

`run_20260907_194929_923052` 的已绑定“涨停家数”取值集合不含 2；唯一 `(2, 家, true)` 来自市场日频卡 `交易日=2026-09-07；涨停家数=93；跌停家数=2；上涨家数=3167`。完整证据列表里虽有未绑定的题材涨停=2，不能替代绑定合同。只在内存中移除该匹配池项后，`_quantity_supported_by_evidence` 从 True 变 False；没有改代码或存证。因此是“家”单位抹掉涨停/跌停指标身份后造成的漏报，新增的字段唯一性保护不足。

```json
{
  "run": "/Users/a77/.local/share/finance-workbench/users/probe-glm-smoke-0907/runs/run_20260907_194929_923052",
  "sentence": "若热度跌回1–2家、排名百名外则降级。",
  "candidate": "2家",
  "unit_fields_matching_2": [
    [
      2.0,
      "家",
      true
    ]
  ],
  "supported_original": true,
  "supported_without_2_household_unit_value": false,
  "note": "只在内存中去除匹配池的一项作因果定位，未修改代码、存证、证据或生产状态。"
}
```

**确认异常 2、3：新增的两条都是有依据的复述。**

- `run_20260820_131240_381743` / `6.49→12.11`：

  > 3) 累计涨幅巨大（6.49→12.11 元，E9→E1），获利盘丰厚，缺乏公司一手公告核验的催化支撑，新闻归因（迎峰度夏用电负荷、电力板块涨停潮、立新能源6连板）仅为新闻二手表述（E25、E28），未经公告确认。

  - 已绑定 `E1`：交易日=2026-07-23；股票代码=001258.SZ；股票名称=立新能源；收盘价=12.11；涨跌幅=9.99；成交额=12.7057；换手率=未知
  - 已绑定 `E9`：交易日=2026-07-13；股票代码=001258.SZ；股票名称=立新能源；收盘价=6.49；涨跌幅=-2.84；成交额=0.6949；换手率=未知
- `run_20260907_013435_437219` / `10.27%`：

  > 依据是：7月22日市场虽被标记为反弹阶段，但上证仅涨0.069%，上涨1530家，成交额26531.66亿元、环比缩量10.27%，低于20日均额30114.45亿元，暂不支持全面进攻；

  - 已绑定 `E1`：交易日=2026-07-22；市场阶段=反弹阶段；阶段天数=2；量能状态=正常量能；行业集中状态=集中；成交第一行业=电子；成交第二行业=通信；成交第三行业=计算机；上证涨跌幅=0.069；市场成交额亿=26531.66；成交额环比=-10.27；20日平均成交额=30114.45；量比=88.1；上涨家数=1530；涨停家数=47；跌停家数=8；强势股加权涨幅=7.64；强势股成交占比=15.03；前三行业成交占比=48.4

额外两条条件阈值边界项按任务书严格口径原样回报，不将其自动归为“纯复述全过”：

- `run_20260827_153436_514397`：条件化判断：若后续几日成交额回升且涨停家数放大至明显多于 42 家，可视为企稳信号；
  - 数值来源：市场日频总览（2026-07-16）；交易日=2026-07-16；量能状态=缩量观望；市场阶段=下跌阶段；行业集中状态=集中；市场成交额亿=24033.87；涨停家数=42；跌停家数=34；上证涨跌幅=-1.8497；上涨家数=2499；量比=76.26
- `run_20260822_015527_733974`：条件化：后续若重新双红、成交额回6000亿以上、涨停家数突破23家前高，升级为主升；
  - 数值来源：题材涨停热度日频（2026-08-17）；交易日=2026-08-17；板块名称=机器人概念；涨停家数=23；涨停占比=1.9；市场占比=21.7；热度排名=2；题材家数=1209；全市场涨停家数=106

以上两条引用历史基准的数字确有出处；“突破前高升级”“高于基准企稳”是模型条件推断，数字同值不能证明该预测判据本身经过验证。其余 8 条消失项核到同指标数值。

### 文本侧 date_mask_ab

任务书的 `R` 是 users 父目录，但该脚本只扫描 `R/*/answer.md`。原命令得到 0，不能引用为无影响：

```text
扫描 0 个 run；受影响 0 个；新受审 token 0 个（条件句 0 个）；按类：{'date': 0, 'list_label': 0}
```

随后调用原脚本的 `scan()` 遍历每个实际 `users/<user>/runs` 叶目录，保留用户及 run 身份后汇总；不改正则或扫描器。文本答卷覆盖比含 continuous-episode 的存证更多，因此分母与 A/B 不同。

```json
{
  "runs_scanned": 1375,
  "runs_affected": 117,
  "released_tokens": 174,
  "released_in_condition_sentences": 6,
  "by_kind": {
    "date": 107,
    "list_label": 67
  }
}
```

6 条粗筛条件句全部原样如下：

```text
[date] fourarm0827-8792/run_20260827_152056_987406 [07-22] - 情景一（延续放量，可能性：中）：07-22 成交额站上 30000 亿且量比≥100，指数不破 3830 上行，涨停 ≥100 家、跌停 <30——反弹升级为量价共振，AI 算力/半导体主线继续吃独食（依据 E7 涨停结构 + E12–
[date] fourarm0827-8792/run_20260827_152056_987406 [07-22] **延续条件（可核验）**：① 07-22 成交额 ≥29569 亿且量比不回落到 85 以下
[list_label] linxiaoqi5111/run_20260820_155347_650140 [7-20] 7-20起企稳+0.84%/466.2亿，7-21加速+2.17%/463.91亿（环比缩量约-0.5%），7-22盘中回踩-0.93%/356.59亿（缩量约-23%），7-23放量大涨+5.88%/565.53亿（环比放量约+58.6%
[date] maxshape0907-8792/run_20260907_005106_056606 [10.27] 成交额2.65万亿元，环比减少10.27%，且低于20日均额3.01万亿元，反弹并没有得到增量资金确认
[date] maxshape0907-8792/run_20260907_013435_437219 [10.27] 依据是：7月22日市场虽被标记为反弹阶段，但上证仅涨0.069%，上涨1530家，成交额26531.66亿元、环比缩量10.27%，低于20日均额30114.45亿元，暂不支持全面进攻
[date] probe-v6-0821/run_20260822_033214_856198 [8/21] - 第9句将零星交易日成交额概括为「长期维持2000-3600亿」：证据中8/21成交额为1975.56亿，已低于2000，且样本仅为7/22至8/21若干日，不能支撑「长期维持」该区间的事实断言
```

其中 4 条是实际日期（07-22 两条、7-20、8/21），另 2 条为 10.27% 的事实表述。174 是文本正则差异候选数量，不是 174 个真实漏审或新增待核；最终判断以含绑定证据的重放为准。前 50 条原始形状保存在 `tmp/local-agent-validation-1002/date_mask_all.txt`，全部 174 条在同名 JSON。

## 5. ✅ 内容正确性自检；模型评测跳过

```text
selftest 通过
```

未收到用户确认 2×2 实验收口，故没有导出答卷后调用模型，也未跑弱模型+harness、强模型 ReAct 完整评测。本轮无真实模型调用。

## 6. 跳过合入（用户明确禁止，且验证有红项）

没有推送、创建 PR、合并 main 或部署；在工作分支只增加验证交接文档。第 11、13–17、19 号及第 3 号 schema 均待实验结束。未来顺序仍按任务书：7/8/9/10/12 → schema → 11 → 13/14/15 → 16/17/19；每步合入后重跑相关测试。核验器先修复本报告异常并重跑同一存证集，路由先达到原门槛；第 17 号还需 A7 决定。

本轮 Gitea 只读实时检查：

```json
{
  "checked_at": "2026-10-02T01:29:51.930419+08:00",
  "gitea_push_mirror_count": 0,
  "kb_relations_unchanged": {
    "aliases": true,
    "entity_exposures": true
  }
}
```

## 7. 待用户决定（均未处理）

1. A7-mainline：补丁当前已将 `direct_definition` 改为 `direct_answer` 并带 amendment。本轮测试的是此版本；通过不代表批准量具修订。是否保留或还原仍待决定。
2. `feat/tool-usage-differential-p0-0929` 是否合并：未合。
3. `gitea-branch-cleanup.sh`：在本机已检索的可读文件范围未定位到该脚本，未生成 dry-run 预览，未删枝。拿到脚本后先审阅与 dry-run，再由用户决定执行。
4. 聊天中已曝光凭据的吊销/重建：建议用户处理；本轮未输出、复制或吊销 token。
5. 预测台账草案及第 13–17 号条目是否写入：未领号、未写入，待实验后决定。

## 8. 原件与后续接手

原始材料根：`/tmp/harness-opt/tmp/local-agent-validation-1002/`（被 Git 忽略，仅本机；约 12 MiB）。本报告嵌入了关键原始输出，云端可直接读取文档回报；完整本机存证没有推送。

- `related-tests.log`、`doctor.json`、`commits.txt`、`revisions.txt`
- `route_probe_before.json`、`route_probe_after.json`、`route_details_after.json`、`data-manifest.json`
- `gate_before/after.jsonl`、`gate_before/after.log`、`gate_ab.txt`
- `gate-reviewed-source.json`（全部 13 条原句、完整匹配卡、绑定标记、原稿）
- `restore-failures.json`（11 条完整异常轨迹）、`ab-input-consistency.json`
- `date_mask_all.json/txt`、`content-selftest.log`、`a7-amendment.diff`

本轮决策：保留指定共享解释器并披露依赖漂移，未擅自升级；基线另建在本树忽略目录，未执行任务书示例中可能删除他人 `/tmp/fwp-base` 的 `--force`；验证后清理本轮基线与 pytest 临时数据。数字片段不足以判断正确性，回查完整卡的指标、日期、绑定身份；未以同数字命中签收。

工具沉淀盘点：复用仓内探针、A/B、文本扫描、自检工具。临时整理代码只用于生成本报告，不新增产品工具；发现的门禁缺陷按本任务“回报失败、保持待验补丁”边界交回修正，未自行改实现、追加补丁或改外部共享记忆/工具仓。

