# 第一条方法验证闭环

这条入口把一个方法候选变成可核对的实验：先冻结比较口径，再保存当时看见的数据和分组，最后追加后续结果。当前候选来自仓内 `dual_red_streak3_continuation.v1.json`，不是已经验证过的个人方法。立案号 `R-20260908-05`。

## 方法卡

| 项目 | 本轮定义 |
|---|---|
| 假设 | 在主升/反弹阶段，双红持续性比只看当天双红提供额外的五日表现信息 |
| 观察顺序 | 当日市场阶段 → 当日板块全集 → 当日严格双红 → 截至当日连续天数 |
| 双红 | 沿用标签层：`pct_chg > 0 AND diff_ratio > 10 AND amount > 500`，单位和标签版本随协议留档 |
| 三组 | 同日板块总体；当日严格双红；连续至少三日严格双红。第四、第五日继续命中，分组互有包含关系 |
| 主要问题 | 连续组减当日组、连续组减总体，后五个交易日均值相差多少个百分点 |
| 失效/弃用条件 | 数据不可用时不作判断；没有相对增量时保留负结果，不继续沿用“持续更强”的假设；修改阈值/范围/目标须新开协议 |
| 例子 | 测试构造 A/B/C 五日收益 6%/2%/-2%，当日组 A+B，连续组 A，总体2%、当日4%、连续6%，持续性增量2个百分点；这是手算测试，不是历史实证 |
| 当前权限 | 研究读数；不自动写经验卡、画像、参数或方法晋升 |

五日收益由既有 `methodology_backtest.outcomes` 计算，从 D0 收盘之后 D+1 到 D+5 复利累计，不含信号当日。先在同一天按板块等权，再在共同可评估日期之间等权；不会把几十个相关板块当成几十个独立日期。

只要基准中有成员结果缺失或无效，当天主比较就不可评估；不会只保留能算出结果的板块。未知标签、无信号、非适用阶段、未到期、到期但缺数据分别记录。副指标 `drawdown_after_peak` 表示峰值至第五日的回撤，不能解释成最大回撤。

## 使用入口

所有命令在实施分支工作树运行，解释器用主树已有虚拟环境。下面的路径绑定的是这一轮真实研究；`STUDY_DIR` 从 register 输出复制，`OBSERVATION` 从 capture 输出复制。

```sh
cd /Users/a77/fwp-wt-method-validation-loop
PYTHON=/Users/a77/finance-workspace-private/.venv-workbench/bin/python
LABELS_DB=/Users/a77/finance-workspace-private/db/history_labels.duckdb
STUDY_DIR=/Users/a77/.finance-runtime/method-validation-first-cycle/475597e2e017a2eedd3886700cd41d394d3694eba3487e205b8ddc91723b5a2f

"$PYTHON" scripts/method_validation.py register \
  --history-start 2024-12-20 --history-end 2026-09-07 \
  --forward-start 2026-09-10 \
  --root /Users/a77/.finance-runtime/method-validation-first-cycle

"$PYTHON" scripts/method_validation.py history \
  --study-dir "$STUDY_DIR" --labels-db "$LABELS_DB"

"$PYTHON" scripts/method_validation.py capture \
  --study-dir "$STUDY_DIR" --labels-db "$LABELS_DB"

"$PYTHON" scripts/method_validation.py recheck \
  --study-dir "$STUDY_DIR" --labels-db "$LABELS_DB" --observation "$OBSERVATION"

"$PYTHON" scripts/method_validation.py report --record "$RECORD"
```

`register` 创建的是不可覆盖的协议，未来开始日必须晚于登记当天。后续再次创建实验，应把日期改成实际计划；不能用旧日期冒充提前登记。默认收据走 `userspace` 的用户目录解析，`--root` 只用于上述明确的离线研究位置。

已经登记过的同一协议，即使过了前向开始日，重跑 register 也返回原文件，保留原创建时间。它不会把新注册伪装成旧注册。

`capture` 只有当日收盘后可用：要求旁路源水位正好等于今天、今天有标签、标签在今天收盘后且登记之前完成构建。重跑当日 capture 返回原观察，不根据后来更新的数据重新分组。CLI 不提供改时钟选项。

`recheck` 只读取原观察中那些板块的五日结果。后来重新计算了双红标签，也不会改变原样本。尚未到第五个交易日时保存 pending 读数；之后重跑会新增结果收据，原观察和旧回检均保留。结果会反链原观察摘要，跨实验观察和摘要不符的文件会被拒绝。

未来或误标日期不能提前结算：结果水位必须已到实际收盘时刻，结果构建时间不得晚于当前时钟；同日盘中构建的结果不当作收盘结果。回检后的日历必须保留观察时的完整历史前缀，不能通过补删历史日期悄悄移动第五日。

当前应用按命令执行，没有安装日程或修改夜跑。要进行日常前向观察，先用现有 `build-labels` 更新本实验使用的旁路库；需要回检再用现有 `outcomes` 构建结果。旁路构建仍通过原有只读主库接口完成，不另建采集链。

## 结果能说明什么

本轮记录三组的描述性差值。它没有解决重叠持有期、共同市场风险、多次试验选择偏差，也没有替代基础补强任务的严格时间点数据认证。报告因此固定 `decision_eligible=false`、`promotion_eligible=false`，不输出“已验证有效”。同期板块均值也不是可直接交易的组合收益。

交易日历沿用既有 `fact_market_daily`，没有独立认证交易所日历完整性。输入原件留的是本次使用的标签、分组、结果和构建元数据，不是完整市场原库的历史版本；原始事实的严格可见时间仍由基础补强任务处理。

历史窗在首轮读数之前固定为 2024-12-20 至 2026-09-07。当前共享旁路标签版本为 v3，源水位 2026-09-07，标签 2026-09-08 重建：这些历史行只能作为重建研究输入，不能称作过去的实时前瞻。

L2、晚间卖方和晨汇均为 `pending_sync`，本轮不用这三类数据，也不启动同步。未来引入新维度，要先形成新方法协议，再与这一版作明确对照。

## 与基础补强任务衔接

本模块只新增研究应用文件，未改 `methodology_backtest` 的 runner/stats/lifecycle，也未改 runtime。下一层严格评估器可以读取本实验的协议、完整板块日、日历、输入元数据、原观察摘要、每次代码摘要与原始结果，再给出经过数据/统计门的正式结论；不能只消费一个平均差值或旧规则的绝对上涨成功率。

新协议是新轮次。修改协议文件会被摘要检查拒绝；需要改变假设时重新登记，并在立案台账记录修订理由。第一次的负结果和数据失败不因新版本成功而消失。

本版只支持这一个固定候选。扩展新的方法或阈值须增加对应版本实现并登记新协议，不能把修改过的任意 JSON 当成已支持的规则。标签或评估器代码升级后，旧原件仍能 report；旧协议重新计算会被版本门拒绝，避免混用口径。
