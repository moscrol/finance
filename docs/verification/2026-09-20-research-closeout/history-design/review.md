# PR783 历史研究设计复核 · 2026-09-20

固定候选 `/Users/a77/fwp-wt-history-market-anatomy@c9bd82ff2e25fe2727347329706f7aeb98444ee8`，基线 `4ace5ec2e9b7735d90eb15bc2351fa193c1120b8`。源码树前后干净。本轮只读源码、旧原件和收据；合成事实、探针与测试临时目录仅在本报告目录。无真实模型、生产库、全量测试、推送、合并。

## 结论和版本边界

保留现有 Workbench → Episode → HistoryQuery → RunStore 架构；不新造研究引擎或事实库。`c9bd82ff` 已实现同窗绑定和原件消费确认，不应按陈旧 inflight 重做。这一实现仍有一个链式原件消费 P2，且各自启动特征/控制组及真实正文交付尚未闭环。

| 版本/证据 | 能确认的事实 | 不可外推 |
|---|---|---|
| `fbd8f2a6`，仓内 `docs/verification/history-market-anatomy/fbd8f2a6/acceptance.md` | 真模型原四题整组失败：市场类比漏实体类型；板块/股票异窗与成员路径误述；接力 immature 被说成失败；近期表现代替各自启动特征 | 不能把这些原答说成 c9 重新运行的失败 |
| `672abcc5`，同目录版本验收 | 历史用途消除前向模板冲突，四叶通过，Python 11579P/81S/2X；未重跑四题 | 不覆盖 c9 新增代码 |
| `c9bd82ff` | 新增 `window_binding.py`，工具消息送达确认、祖先范围重验、候选 sample_id 与排名窗/观察窗分离 | 无新四题真模型验收；正式全量有 1F |
| 本次定向 | `test_history_window_binding.py` + `test_history_market_anatomy.py`，65P/3.96s | 不是全量、不是模型业务验收 |

核心设计依据：`docs/superpowers/specs/2026-09-09-historical-discovery-research-design.md:259` 要求四格/不可判与冻结分母；`:270` 要求先冻结条件和基准后读结果；`:278` 要求同期环境匹配。过程研究的实际边界已在 `docs/agent-product-door.md:231`、`:233` 更新，inflight 未跟进 c9。

## 新增可复现缺陷：P2，同一参照的合法原件链被误拒

位置：`intelligence/services/historical_research/window_binding.py:118`，`WindowSelection.reserve()`。

真实调用链：原四题的 `decide_turn()` 形成可信历史续问 → `history_tool_specs()` → `ResearchToolRegistry.execute()` → `HistoryQuery.run()` → `HistorySession/RunStore` 保存 → 真实 harness 投影/消息确认（由现有测试 helper 显式执行）→ 下一次工具调用。没有模型替身替换计算器或持久化。

探针步骤：

1. 从已读类比候选取得 `2026-01-17..01-22` 排名窗，保存 sector rank。
2. 原第三题明确允许继续观察；从 rank 原件执行 sector trace 至 `01-29`，成功并保存扩窗原件。
3. 读取刚保存的 trace；以它为 `window_ref`，同轮查 stock trace `01-17..01-29`。
4. 返回 `history_window_selection_conflict`。仅将引用改回最初 rank 原件，同一个 stock 请求成功。

两请求 `root_query_id/root_sample_id`、`ranking_start/end`、请求起点和观察终点完全相同。`resolve_window_binding()` 在 `:39–47` 正确继承根身份与排名窗；`reserve()` 却在 `:118` 用直接父件的 `source_start/source_end` 做参照身份，父件由 rank 变成扩窗 trace 后错误判冲突。

最小修改：选择身份采用 canonical root identity + `ranking_start/ranking_end`；直接父件的日期/来源关系继续由 `resolve_window_binding()`、`validate_saved_window_binding()` 逐边验证；`:122` 独立观察终点一致性、授权扩窗、源消息送达、并发预占/失败释放全部保留。不能删掉 source/window 检查来消红。补同轮 rank→扩窗 trace→stock trace 链、同一根混合直接父引用、不同根拒绝、不同观察终点拒绝、并发兄弟调用和失败释放回归。

复跑：

```sh
cd /Users/a77/fwp-wt-history-market-anatomy
PYTHONDONTWRITEBYTECODE=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python /Users/a77/.finance-runtime/reviews/research-closeout-20260920/history-design/probe_history_design.py
```

原结果 `probe-results.json`；测试日志 `targeted-tests.txt`。原 65 项全过说明此链式别名场景尚未被覆盖。

## 可保留的实现与后续业务切片

- **同窗排名**：`query.py:885–896` 在完整输入上排名，缺数 `rank=null` 仍入分母，preview 只裁展示；`window_binding.py:51` 阻止观察扩窗后改排名区间。100000 输入行上限时明确缺口，不缩窗/挑赢家。保留这些规则；大窗全市场自动分片仍未实现，不能宣称任意窗口全集都能完成。
- **跨轮原件消费**：`episode.py:445–487` 只在工具消息内容包含原件身份和观察窗后标 `model_message`；`:631–654` 执行前检查同会话原件/祖先范围和送达，两个 runtime loop 已接线。该点从“待实现”改为“确定性已实现、修 P2 后待业务验收”；送达不证明模型理解，原四题仍须新固定版本、新隔离会话复验。
- **成员路径与独立启动**：`anatomy.py:340–374` 正确保留 `path_anchor=sector_signal_not_stock_launch`；`_first_signal()` 已可独立计算 stock 启动，不能重造。探针 S2 为板块成员 rank2、有完整峰值路径，但 stock `launch_signal` 为 `not_observed`。下一片应在选择代表后调用同窗 stock trace，并让公开交付绑定相应 `record_kind/anchor`；不能把成员 path 的日期改名为股票启动日期。保留启动日名单、缺数成员、同股多篮子非独立样本限制。
- **各自启动特征/控制组**：`anatomy.py:206` 已取各自信号前5日+信号日的同口径特征；未触发实体在 `:201–205` 只保留状态和空 features。探针把 B 改成未触发后，分母 A/B 都在，但 B 没有可对照的启动特征/结果行。这是已声明的能力边界，不是数据被删除。`query.py::_compare` (`:1209`，冻结在 `:1236`) 现有固定窗单特征四格，不能直接冒充“复合启动信号+各自启动日”的对照研究。最小路线是在现有 trace/compute/compare 内定义版本化锚点和群组合同：已启动用各自启动时点；未启动只能使用明确声明的同日参照锚，不能虚构启动日。先冻结全部代码、特征窗、结果窗与对照规则，再读后验；失败、未成熟、缺特征、缺结果分列。未实现前正文保持描述/假设，不升级为收益规律。

## c9 正式全量 1F 的原件

`/Users/a77/.finance-runtime/history-window-c9bd82ff-checks/receipt.json` 绑定 clean c9，Python 叶失败，其余三叶通过。`python.txt:168–178` 和 `:232–233`：

`tests/test_code_map.py::test_structure_probe_daily_full` (`tests/test_code_map.py:594`) 期望 structure hits 包含 `market_feature_store`，实际 `[]`；全量 **11612P/1F/83S/2X/17 warnings**。本轮未重跑全量。

同根 `code-map-diagnosis.json` 保存两层定位：固定 CI PATH 没有 uvx，结构 hits 为空；补 uvx 后 `daily-full` 只命中 `skills/daily-full-review`，改查源码符号 `daily_full` 才命中 `market_feature_store`。所以不能只补 PATH、不能吞掉断言，也不能拿 672 的旧绿为 c9 签字。修复应明确外部查询器可用性和命令名到源码符号的检索合同；环境失败需诊断，测试须用可控图验证语义、真实图探针另记适用条件。

## 与 #791 的边界

已读取外部保存的最新 #791 原文 `../research-issues.json`：它要求重叠题材成员取并集再算占比（32股样本并集15，不能10+9+7=26），以及相似度0.313排在0.370前、不得用后续收益倒灌相似排名，并覆盖乱序、并列、缺成员、重复、小样本和公开稿一致性。

**不重复**：PR783 是授权历史窗、行情收益排名、启动/峰值/接力与原件血缘；c9 P2 是同根扩窗原件身份错误。#791 的多题材成员并集、相似度固定排序及终稿一致性并未被本次65项测试或 c9窗口绑定覆盖。PR783 的 `find_analogues` 距离/排序独立复算缺口也仍在，不能用 rank_history 收益重算代替。

共同可复用的是完整分母、稳定对象身份/排序和投影来源合同；不要分别新增第二套聚合库、排名状态机或自由文本 judge。#791 可独立推进，若触达同一投影路径，应共享固定原件并保留两类排序的不同定义。
