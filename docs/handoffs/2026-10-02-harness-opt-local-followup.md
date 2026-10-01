# harness-opt 本地续修与 GitHub 分支审查（2026-10-02）

本轮承接用户“继续推进，并检查 GitHub 新推分支”。原始验收留在 [上一轮完整报告](2026-10-02-harness-opt-local-validation.md)，本文件记录后续修复，不覆盖原失败证据。

## 1. ✅ 代码身份与分支

全部产品修改在 `/tmp/harness-opt` 的 `feat/harness-opt-1001`；解释器为 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`（Python 3.12.13）。原有空文件 `30` 保留。

GitHub 新出现的 `origin/feat/harness-opt-1001` 为 `fb03e8e37fb845e86a84fed4939d3e331143b9d1`，与本地原始 19 个补丁零差异。核对输出：

```text
git rev-parse origin/feat/harness-opt-1001^{tree}
d94cedf89ba915c649ef045a19be6a808c6a3554
```

续修提交：`2d1fb9cf882d9eb366bad2c7ebc64386e405f01e`，tree `35cccccf24d07a3f7d9bdad7bf709f5d504a7365`。本轮没有推送、创建 PR 或合入 main；2×2 实验仍按未确认收口处理。

发现与修复顺序：先复现两条数值误报和串指标漏报，再修复真实 KB 的日期/A股左边界和极简盘面词；独立审查发现箭头串指标、方向动词、倒装与从…到…的反例，全部先跑红再补修。最终新增 38 个确定性回归用例：数值 24、路由 14。冻结 A7 没有新增改动。

## 2. ✅ macOS 相关测试

在已提交的 `2d1fb9cf8` 上运行任务书 17 个文件，另加 6 个文件：两份本轮回归、`test_episode_semantic_verifier.py`、`test_numeric_condition_mark.py`、`test_episode_numeric_citations.py`、`test_query_understanding.py`。

```text
1103 passed, 1 skipped in 11.13s
SKIPPED [1] tests/test_market_feature_store_staging_swap.py:1434:
flock 与 DuckDB 锁互斥只在 Linux 上失效
```

收据：`/Users/a77/.finance-runtime/test-receipts/20261001T180325Z-2d1fb9cf-d14db84e0411.json`。`scripts/check_test_receipt.py` 校验：

```text
collected=1104 == 读数合计=1104
revision / 解释器 / Python版本 / 依赖指纹一致
收据来自干净代码树（全树另有原有文件 30）
可采信 —— 收据成立的条件与当前环境一致
```

`python -m ruff check .`、`git diff --check` 及提交钩子均通过。此收据只覆盖所列 23 个文件，**没有跑全仓测试，不代表完整合入 CI**。共享环境 httpx 0.25.2 与锁文件 0.28.1 的差异保持原样，没有为此次验证升级实验环境。

完整日志：`tmp/local-agent-validation-1002/related-tests-verified.log`；校验日志：`verified-receipt-check.log`（同目录）。

## 3. ✅ 真实 KB 路由探针达标

未改探针题集、预期或计数方法。使用同一真实知识库 `/Users/a77/knowledge-base-private/wiki`。再次核验关系文件 SHA256 与首轮相同：

```text
aliases.json           ed40899b25014fe45506a22ed14d7a39f51523c7666791ba63625ae8803cfed2
entity_exposures.json  8b7582e63e9175c93374440b28d2c85378d7c873e9369920876204c9ccaf4bd7
```

| 字段 | main 分叉基线 | 原始 19 补丁 | 本轮续修 |
|---|---:|---:|---:|
| anchor_hits | 16 | 16 | 16 |
| consistency | 0.622 | 0.822 | 0.889 |
| colloquial | 0.667 | 0.867 | 0.933 |
| reordered | 0.667 | 0.933 | 1.000 |
| terse | 0.533 | 0.667 | 0.733 |
| clarify_count | 3 | 0 | 0 |
| llm_fallback_count | 0 | 0 | 0 |
| seed_fallback_rate | 0.067 | 0 | 0 |
| paraphrase_fallback_rate | 0.089 | 0.067 | 0 |

变化对应实际题面：q07 口语版识别稀有金属，q09 调序版识别医疗服务，q14 极简版走 `market_watch`。q04 的公司比较、q05/q10 的题材识别保持；q07 极简版仍为 `market_cause`，但主体是稀有金属、需要检索。没有为了消灭所有不一致而统一所有车道。

修后全部 mismatches，原样：

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
    "style": "terse",
    "seed_type": "research/theme_analysis",
    "paraphrase_type": "research/market_cause"
  }
]
```

原始 JSON：`tmp/local-agent-validation-1002/route_probe_before.json`、`route_probe_after.json`、`route_probe_verified.json`。附加“茅台咋样”的别名缺失边界沿用首轮报告，没有改真实 KB，也没有调用模型控制器验证。

## 4. 部分通过：数值异常已修，严格人工口径仍有 2 处边界

同一 966 个 run，955 个可还原；原始 A/B 与本轮的 955 份导出证据逐份一致。

```text
原始基线: runs=966 restored=955 failed=11 runs_with_flags=159
19补丁:   runs=966 restored=955 failed=11 runs_with_flags=156
本轮续修: runs=966 restored=955 failed=11 runs_with_flags=155
restore-failure x7: TypeError: 'NoneType' object is not iterable
restore-failure x4: KeyError: 'structural_verifier'
```

11 条分别是 `structural_verifier=null` 或字段缺失，未绕过；路径和完整原因仍在首轮 `restore-failures.json`。

本轮相对原始 19 补丁的完整原始 diff：

```text
common runs=955 (only A=0, only B=0)
flagged tokens: A=371 B=365  disappeared=7 appeared=1
== 只在 A 挂（B 放行）——应全是正确复述
  [11.83%] 若用前一交易日7月24日作参照，市场整体偏弱：上证指数收跌1.61%，成交额较前一日下降约11.83%，上涨家数明显少于下跌家数，涨停40家、跌停24家，盘面属于缩量下跌和风险偏好走弱。
      run=run_20260815_035158_446415
      证据: 成交额环比=-11.83
  [6.49→12.11] 3) 累计涨幅巨大（6.49→12.11 元，E9→E1），获利盘丰厚，缺乏公司一手公告核验的催化支撑，新闻归因（迎峰度夏用电负荷、电力板块涨停潮、立新能源6连板）仅为新闻二手表述（E25、E28），未经公告确认。
      run=run_20260820_131240_381743
      证据: 收盘价=6.49
  [-17.27%] 但成交额21949.97亿元，环比-17.27%，且低于20日平均的29414.95亿元，量能状态标注为缩量观望，量比74.62（口径为数据标签）。
      run=run_20260824_061001_711585
      证据: 成交额环比=-17.27
  [-17.27%] 风险信号与验证条件：一是量价背离，指数上涨但成交额环比-17.27%且显著低于20日均值，缩量反弹持续性存疑；
      run=run_20260824_061001_711585
      证据: 成交额环比=-17.27
  [17.3%] 量能是主要瑕疵：成交额21950亿、环比缩量17.3%，低于20日均额29415亿，量能状态被标注为「缩量观望」（E13）——缩量下的普涨说明追高意愿有限，情绪属于修复性而非进攻性。
      run=run_20260824_061604_482978
  [10.27%] 依据是：7月22日市场虽被标记为反弹阶段，但上证仅涨0.069%，上涨1530家，成交额26531.66亿元、环比缩量10.27%，低于20日均额30114.45亿元，暂不支持全面进攻；
      run=run_20260907_013435_437219
      证据: 成交额环比=-10.27
  [17.2%] 两市成交约14090.7亿元，环比萎缩约17.2%，量比76.9%，即成交低于20日均值水平，属于缩量反弹（E1）。
      run=run_20260930_023655_895209
      证据: 成交额环比=-17.24
== 只在 B 挂（A 放行）——应全是自拟阈值
  [2家] 若热度跌回1–2家、排名百名外则降级。
      run=run_20260907_194929_923052
      证据: 交易日=2026-09-07
      证据: 交易日=2026-09-03
      证据: 涨停家数=2
      证据: 交易日=2026-09-02
```

人工核对以上 8 处（只使用已绑定证据，工具的字面搜索片段不能代替绑定校验）：

- `6.49→12.11`：E9/E1 的收盘价分别为 6.49/12.11，均已绑定；现在要求两个端点精确来自已绑定收盘价。换手率 12.11 不能支持收盘价终点 12.11，未绑定端点也不算。
- `10.27%`：已绑定 `33f8da4eb0f6595e` 的 `成交额环比=-10.27`，原句明确“缩量”，为正确复述。
- 额外 5 处释放的百分比也有已绑定出处：11.83%→`819547c670ad4ad5` 的 -11.83；两处 -17.27%→`1a67d5a7193e24b1` 的 -17.27；17.3%→`dd13ef01831b7d00` 的 -17.27（保留一位小数）；17.2%→`a1622e9ff53d1ef6` 的 -17.24。均为当前量能事实复述，裸名“量比”没有一起放宽。
- 重新标注的 `2家`：已绑定的 2 是**跌停家数**，不能为固态电池涨停热度背书；字面搜索展示的某些 `涨停家数=2` 来自未绑定卡。逐数量保留指标身份后不再串用。

相对最初 main 分叉基线的累计结果：

```text
common runs=955 (only A=0, only B=0)
flagged tokens: A=380 B=365  disappeared=15 appeared=0
```

15 处不再标注中，13 处可按证据复述解释；另 2 处仍按任务书严格口径单列，不宣告整个第 4 节全绿：

1. `run_20260822_015527_733974`，原句：“条件化：后续若重新双红、成交额回6000亿以上、涨停家数突破23家前高，升级为主升；”——23 家确为历史前高，但把突破它解释成升级条件是模型判断。
2. `run_20260827_153436_514397`，原句：“条件化判断：若后续几日成交额回升且涨停家数放大至明显多于 42 家，可视为企稳信号；”——42 家是已绑定历史事实，“明显多于”作为未来企稳条件不是纯事实复述。

现有测试和合同允许沿用证据数值表达条件；本轮没有暗中改成“所有条件阈值一律拒绝”。是否满足本次严格人工验收，须由用户/实验负责人明确口径后再签收。两句完整证据保存在首轮报告与 `gate-reviewed-source.json`。

原始重放：`gate_verified.jsonl`、`gate_verified.log`、`gate_verified_diff.txt`、`gate_verified_cumulative.txt`；本轮逐项证据：`followup-manual-evidence.json`，均在 `tmp/local-agent-validation-1002/`。文本侧日期扫描本轮未重复；首轮结果为 1375 答案、117 受影响、174 候选，见原报告；它们不能直接当作 174 个数值错误。

## 5. ✅ 内容题集自检；模型评测跳过

```text
selftest 通过
```

未运行两臂模型评测，未使用实验模型配额。实验收口后再执行完整答卷与评分。

## 6. GitHub 更新审查（固定 PR #10 的 3 个新增提交）

除了上文核对的 `feat/harness-opt-1001`，fetch 还发现 [PR #10](https://github.com/moscrol/finance/pull/10) 的 `arena/01a0f120-finance` 从 `983590438` 推进到 `0eb1af3628a8068e8923c9fc4495f8e76acfc497`。本次只审这一增量（15 个文件）：

```text
bcd8a470f fix(admission): 生效模型准入覆盖子分支，2×2 判定按产物自动重算
45d9a6e70 feat(scripts): 量纲用同日原值反算定案；Mac 侧只读核验一条命令跑完
0eb1af362 docs(verification): 按 10-01 审查更正质检报告五处
```

两位独立审查者分别检查规范与需求，以下均有离线复现。未运行它的生产串联脚本、未改 PR 分支或实验产物、未向 GitHub 发评论。相关现有测试为 75 passed，但未覆盖下面的缺陷。

### Standards：1 项

**[P2] APFS 主文件克隆遗漏已提交的 WAL 数据。** `scripts/mac_pr10_checks.py:81` 自行 `cp -c` 主文件，违反 `AGENTS.md` 要求整库快照走 `market_feature_store.db.clone_to_staging`。临时 DuckDB 建表、checkpoint 后提交 1 行并保持连接：原库 1 行，脚本副本 0 行；原库 WAL 存在、副本 WAL 缺失。共享入口会复制 WAL。应复用并验证快照完整性。[固定代码位置](https://github.com/moscrol/finance/blob/0eb1af3628a8068e8923c9fc4495f8e76acfc497/scripts/mac_pr10_checks.py#L81)

### Spec：3 项

1. **[P1] 子分支异常后仍会错误准入。** 预注册 §5 要求重算覆盖子分支；`model_admission.py:167–177` 遇 `llm_calls=0` 不追查引用，而实际 coordinator 在 worker 异常后统一记 0。离线复现：子分支先落盘 `glm-5.3` 再抛异常，父模型为期望的 `glm-5.3-flash`；即使提供正确 episode store，父产物仍 `admitted`，直接查子产物为 `mismatch`。应补查异常分支，而不是把计量归零当作从未调用。[固定代码位置](https://github.com/moscrol/finance/blob/0eb1af3628a8068e8923c9fc4495f8e76acfc497/intelligence/eval/model_admission.py#L167)
2. **[P2] 自报开关绕过冻结准入硬门。** 预注册要求没有 `artifact` 的运行无效。相同 240 条无产物夹具，默认判 `incomplete`，加 `--trust-self-reported-admission` 后判 `model_only`。如果保留诊断模式，应限制它输出正式效应结论。[固定代码位置](https://github.com/moscrol/finance/blob/0eb1af3628a8068e8923c9fc4495f8e76acfc497/intelligence/eval/model_harness_2x2.py#L512)
3. **[P2] Ruff 失败仍被汇总为 CI 步骤成功。** `step_full_tests` 只返回 pytest 状态。模拟 Ruff=1、pytest=0，步骤 exit 确为 0，而 PR 合入条件要求两者绿。应聚合两个退出状态。主函数始终返回 0 符合它收集报告的文档设计，不另报问题。[固定代码位置](https://github.com/moscrol/finance/blob/0eb1af3628a8068e8923c9fc4495f8e76acfc497/scripts/mac_pr10_checks.py#L157)

规范轴共 1 项，最重 P2；需求轴共 3 项，最重 P1。不能用这版准入报告代签 2×2 实验结果。复现脚本及结果已保留在 `tmp/local-agent-validation-1002/pr10-review/repro_spec.py`、`findings.json`；脚本应在上述固定 PR 提交的隔离树运行。

本分支自身续修的规范审查没有未解决项；需求审查发现的 7 条反例已写入正式回归并全通过。

## 7. 跳过：实验后的合入与用户决定

没有确认实验收口，故没有进入任务书合入步骤。仍待用户决定：冻结 A7、`feat/tool-usage-differential-p0-0929` 是否合入、Gitea 清枝执行、曝光凭据轮换、预测台账写入；本轮均未处理。Gitea 镜像仅有上一轮 `push_mirrors=0` 的检查结论，实际推送前仍需重新核对方向。`gitea-branch-cleanup.sh` 仍无已确认路径，未执行。

## 决策与被否方案

| 决策 | 采用 | 未采用及理由 |
|---|---|---|
| 指标身份 | 字段保留指标；逐数量短语识别指标与方向 | 只比数值/单位会把跌停数用于涨停，PE/PB 同理 |
| 价格箭头 | 仅后接元的价格箭头，两个端点精确来自绑定收盘价 | 全局裸数端点会拿换手率拼出价格；任意区间放行会放过自拟阈值 |
| 旧百分比标签 | 精确兼容已知 `成交额环比`，保留符号/精度检查 | 没有把裸名量比或任意比例字段解释成百分比 |
| 路由 | 复用日期解析，补 A 股前缀与极简当日盘面 | 没改题集或放宽公司后缀保护；剩余 5 个路由差异保留 |
| 两条条件边界 | 保留原句与证据，交人工验收 | 不靠扩大豁免或删掉条件能力刷绿 |
| PR #10 | 固定提交、独立审查、只读复现 | 用户要求检查且实验由另一 agent 管，不擅自改该分支或实验 |

工具沉淀：本轮复用仓内探针和 replay，没有新建产品脚本。手工语义判断不能由字面片段搜索替代；可确定的失败形状已进入正式回归。一次性审查复现留在明确的忽略目录，供固定提交复查，不写入共享台账或其他仓库。
