# R-20260821-05 复现：个股形状 contract-预算失配（2026-08-21）

> 目的：`docs/prediction-ledger.md` R-20260821-05 立案时 n=1，交接（`docs/handoffs/inflight/main.md` 08-21 17:45 条）要求**先复现 ≥2 样本再归因**。本轮加打两个同形探针，判定「契约失配 vs 本题偶发」。
> 环境：生产 8792 @ `6320b3bc`（health 三项一致：dirty=false / code_matches_repo=true），readiness 12/13 缺 `market_data_consistency`（数据侧，DuckDB 停 08-20，预期今晚 daily-full 自愈——与交接注意事项③一致，不影响本探针）。模型 glm-5.2。
> 工具：`scripts/workbench_probe.py`（#294 沉淀后**首次实战**，`user` 字段隔离生效——两个 run 都落在探针用户自己的 `runs/` 目录，主用户会话列表零污染）。
> 收据：`~/.finance-runtime/live-probe-traceability/20260821-r05-stock-repro/summary.json`；run 工件在 `~/.local/share/finance-workbench/users/probe-r05{a,b}-0821/runs/`。

## 0. 一句话

**复现成立，3/3。偶发路径假设排除，归因定为契约失配。** 且 A 臂抓到一个立案时没有的新形状：修复轮被 mandatory 压着调了 `market_data`（它返回的是**市场总览快照**，不是个股行情），市场级数字混进个股公开稿——**满足契约反而污染答案**。

## 1. 方法

- 题面：沿用原案模板只换股名——「X最近两周（2026-08-06到2026-08-20）的走势复盘：几个关键转折日各自的涨跌幅和成交额是多少？」机制复现要同形，不要泛化变体。
- 选股：DuckDB 只读查询窗口内「有 ≥9.5% 涨停日 + 有 ≤-4% 回撤日 + 成交额 ≥8 亿」的活跃个股 20 只；排除当天已探过的题材族（CXO/减肥药/钙钛矿/PCB/DRAM 沾边的长鑫科技、康龙化成、胜宏/生益/景旺等）。
- 烧题检查按当日教训**跑 `gitea/main` 树**（`git grep <名> gitea/main -- docs intelligence`，主检出树是特性分支会漏当天已合并文档）：铜冠铜箔 6 处 / 网宿科技 5 处 / 利通电子 3 处 / 太极实业 3 处**弃用**；莲花控股 / 太辰光 / 行云科技 / 永鼎股份 0 命中，取前两只（光通信 + 食品跨算力，两个板块族）。

## 2. 读数（n=3，含原案）

| | 皇氏集团（原案） | 太辰光（探针 A） | 莲花控股（探针 B） |
|---|---|---|---|
| run | `run_20260821_171744_955225` | `run_20260821_185226_491046` | `run_20260821_185229_591768` |
| 路由 | stock_deep_dive → `company_multi_layer_evidence` | 同 | 同 |
| `missing_mandatory_capability` | **market_data, mainline_context** | **mainline_context** | **market_data, mainline_context** |
| `mainline_context` 调用 | 0 次 | 0 次 | 0 次 |
| `market_data` 调用 | 0 次 | **修复轮 1 次**（见 §3） | 0 次 |
| repair 路径 | `repair_goal`：`unreachable_without_tools=[direct_assessment, supporting_evidence, counterpoint]`，`reopen_tools=False`，`remaining_calls=0` | `repair_goal` ×2（`remaining_calls` 1→0，`reopen_tools=False`），repair_reentry granted 22.5s / 37.5s | **无 repair_goal**（`stop_reason=model_finish`） |
| 判官 | repaired | repaired | repaired |
| 公开稿终态 | 道歉横幅收场（原案已记） | **194 字残稿**：市场级数字混入 + marker_loss 横幅，题目要的转折日数值丢失 | **324 字完好**：转折日+E 引用+反证+数据疑点声明 |
| usage | — | llm_calls=5, tool_calls=2, draft 958→public 194 | llm_calls=2, tool_calls=1, draft 629→public 324 |

判定（对台账可证伪判据）：**复现 3/3**。`mainline_context` 三次全部未被调用；`market_data` 2/3 缺、1/3 在修复压力下才被调。「本题偶发路径」假设**排除**。

## 3. 新观察一：满足 mandatory 反而污染答案（A 臂）

A 臂修复轮里模型为满足契约调了 `market_data`，返回市场总览快照（`市场数据截至 2026-08-20…上涨 4096 家；涨停 79 家…强势股状态：沸点；平均涨幅 9.91%…`，`detail=market_overview`，L4）。这些**市场级**数字被逐字缝进**个股**复盘的公开稿：

> 「太辰光（300570.SZ）…区间自143.43元升至213.4元，累计涨幅约48.7%。上涨4096家、涨停79家、跌停14家；强势股状态沸点（平均涨幅9.91%、边际变化15.63%）；结构缺口：提供主要反证或竞争性解释在结构核验中已判达标，但本轮质检重写时删除了其表述。…」

三点：

1. `market_data` capability 对个股题**答非所问是结构性的**——它就是市场总览（`MARKET_DAILY`），不是个股行情；个股序列本来就该走 `finance_query`（三个 run 都第一时间调对了）。模型不调它不是懒，是对的。
2. 契约压力的实际效果是把背景当正文塞——这与用户既有原则「指数环境只作为背景放大器，不作为个股强势的决定性因素」直接冲突。
3. **A 臂同时是残余②（marker_loss 无第二修复窗）的又一 live 样本**：counterpoint 在质检重写中被删、无第二修复窗、道歉横幅收场，与钙钛矿/皇氏案同形。A 臂 draft 958 → public 194，题目要的转折日数值反而没活下来——**该 run 花了 5 次 LLM 调用，终态比只花 2 次的 B 臂差**。

## 4. 新观察二：issue 不依赖修复路径（B 臂）

原案机制链写的是「工具轮次耗尽 → `repair_goal.unreachable_without_tools` 且 `reopen_tools=False` → 注定 `missing_mandatory_capability`」。B 臂**没有走 repair_goal**（`model_finish` 直接收稿），同样的 issue 照记——说明记账点在**结构核验层**，修复路径只是常见触发场景不是必要条件。机制表述应更正为：**mandatory 清单与该题形的真实取证路径不匹配，凡此题形必记此 issue**，与预算档、修复路径均无必然绑定（预算只决定模型有没有机会像 A 臂那样被压着去补调）。

## 5. 对修复方向的证据倾向（不代拍板）

台账给的两个方向，本轮证据的倾斜：

| 方向 | 本轮证据 |
|---|---|
| 个股预取补 market_data + mainline_context 两路 | A 臂证明 market_data 的内容对个股题是背景不是答案——预取塞进来大概率重演「背景当正文」的污染，且 mainline_context（主线结构）对个股走势复盘同样是弱相关背景 |
| **契约按题形把 mandatory 降为 best-effort**（或给 stock_deep_dive 单独定 mandatory 清单） | 三个 run 里模型自主的取证路径（finance_query 为主）全部正确且数字全真；B 臂无契约干预时答案最好。**倾向此方向**，但 mandatory 清单动的是 `evidence_capabilities.py`/`episode_factory.py:353` 的契约层，需单独立项走测试（含变异），不在本轮做 |

## 6. 复算

```bash
# 判定字段
python3 -c "
import json
for u,r in (('probe-r05a-0821','run_20260821_185226_491046'),('probe-r05b-0821','run_20260821_185229_591768')):
    d=json.load(open(f'/Users/a77/.local/share/finance-workbench/users/{u}/runs/{r}/continuous-episode.json'))
    print(r, [str(i)[:90] for i in d['semantic_verifier']['issues'][:1]])
"
# A 臂 market_data 返回的是市场总览（非个股）
python3 -c "
import json
d=json.load(open('/Users/a77/.local/share/finance-workbench/users/probe-r05a-0821/runs/run_20260821_185226_491046/continuous-episode.json'))
print([e['payload']['observation'][:120] for e in d['events'] if e.get('kind')=='tool_result' and e['payload'].get('tool')=='market_data'])
"
```

探针会话落在 `probe-r05a-0821` / `probe-r05b-0821` 两个独立用户下，主用户会话列表无新增（`user` 字段修复的首次实战验证）。
