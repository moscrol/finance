# 8792 公开交付与证据绑定验证

## 当前候选

v20 对应候选 `1d9e717d2922b00db002ae126d529ea11e9206d2`，分支为 `fix/8792-premise-market-contracts`。本轮修复的公开出口缺陷是：语义判官拒绝、且句子显式引用 E 证据的事实句，不得继续留在公开答案；无 E 引用的分析/情景争议仍可降级保留，机械的表外 E 序号仍删除。

候选代码提交为 `fix: remove rejected cited fact sentences`。完整 Python 收据为 `12044 passed, 85 skipped, 2 xfailed`；使用项目解释器 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`。候选 SHA 绑定的前端收据另跑并全部通过：lint、typecheck、110 个单测、build，以及 E2E `34 passed, 2 skipped`。不把父 SHA 的前端收据移签给 v20。

## v20 Live

sidecar 端口为 `18894`，用户根为 `/Users/a77/.finance-runtime/8792-premise-market-v20-users/probe-premise-market-v20-20260921/`。运行时健康身份为：

- `source_revision=1d9e717d2922b00db002ae126d529ea11e9206d2`
- `source_dirty=false`
- `code_matches_repo=true`
- loaded/repo tree fingerprint 均为 `137caf4abf18bc7a9aa683e4447343c197c97f1c2ea1a47c17008e680cc545d1`

原三题各执行一次且不自动重试。首题和追问共用会话 `conv_1c083ddc18964a4d88ee4f4dbf8626c2`；行情题使用新会话 `conv_92115c0ac7874659b5c57b78588093ac`。

- `run_20260921_065612_406744`：题设算术，公开表为 25%、12.5%、10%、9%、下降 1 个百分点、66.6667%、180 亿元、20 倍，并明确不能据此判断便宜/贵。
- `run_20260921_065630_642298`：24 元追问，公开表为 240 亿元、26.6667 倍、7.2 亿元、33.3333 倍；情景明确不是盈利预测。
- `run_20260921_065657_847324`：2026-09-18 行情，公开答案为 4234/1151/168、涨停 79/跌停 0，前三板块为功率半导体、集成电路设计、半导体设备，并带涨幅、成交额、日期和 `.FP` 口径。

三个 run 均 `completed`，公开 `answer.md` 均非空。v20 行情答案已删除 v19 中未绑定的括注“EDA、封测、存储、汽车芯片随后”；当前答案将 EDA、封测、存储芯片、芯片逐项写出数值，并分别绑定 `E18/E31/E35/E45`。

sidecar 已正常发送 `SIGTERM` 停止。停止前用户根 run 列表为 3 个 `completed`，`running=0`、`queued=0`。

## 公开交付与反事实

使用实际 `marked` 15.0.12 解析器执行：

```bash
node scripts/check_public_finance_delivery.cjs \
  --runs "$HOME/.finance-runtime/8792-premise-market-v20-users/probe-premise-market-v20-20260921/runs" \
  --webapp /Users/a77/fwp-wt-8792-premise-market/intelligence/webapp \
  --fixture docs/verification/2026-09-21-8792-premise-market/public-delivery-v20.json
```

正常 fixture 为 `3/3`。以下三个有效进程内变异均按预期失败，且变异确实生效：

- `wrong_pe`：exit 1
- `collapsed_boundaries`：exit 1
- `swapped_breadth`：exit 1

此前两次错误用户根路径造成的失败原件保留在 evidence 目录，但标记为操作错误，不计入反事实结论。

候选树的准入守卫为 `3 passed, 65 deselected`。在进程内禁用 admission 后为 `2 failed, 1 passed, 65 deselected`，失败不是 TypeError、导入错误或零测试；源文件哈希未变。

## 独立复核

代码 K3 分两轮保留原件：

1. 首轮只给 tiny diff，结论为 `INCOMPLETE`，提出两个 `needs_context`：引用解析器覆盖未展示、质量标记投影路径未展示。这不是确认缺陷。
2. 第二轮附上候选真实 helper 和投影路径上下文，结论为 `PASS`，确认带 E 引用的语义拒句进入删除 repair、无 E 引用的语义争议仍可 demote、机械表外引用仍删除，质量标记投影只更新控制面而不会重新插入删除句。

证据引用合同当前是 ASCII `E1..E999`；全角 E/数字不属于现有语法，本轮作为边界记录，没有擅自扩大合同。

独立财务 K3 供应商请求返回 `HTTP 400 invalid_request`，没有有效财务独立签字，必须记为 `INCOMPLETE`。确定性审计只核对题设算术表和列明的行情观察值；canonical 是同源口径对照，不是第二供应商，也不覆盖任意自由 prose 或因果解释。

## 生产与范围

生产 8792 仅做只读核对，仍为：

- revision `bf662e9310ff751a4c31763815ee78fb7d6d5122`
- `source_dirty=false`
- fingerprint `e5a2f94c4638392ace619606e1aa279ab81e3692e4e6d0a420a5f24fcfeb59e8`

本轮不合 main、不 push、不部署、不付费外审、不删除生产。普通非静态 PE 文字仍不进入专用程序计算器；未识别财务数字文字仍依赖语义审核。registry 外部 `kb/rag-query` 漂移继续单独记录。

完整运行时证据、manifest 和 SHA256 清单在：

- `~/.finance-runtime/8792-premise-market-evidence/v20-artifact-manifest.json`
- `~/.finance-runtime/8792-premise-market-evidence/v20-evidence-SHA256SUMS.tsv`
- `~/.finance-runtime/8792-premise-market-evidence/v20-user-root-SHA256SUMS.tsv`

## v21：撤回「引了 E 且被拒 → 删」，改为判官理由码分流

v20 候选 `1d9e717d2` 的规则「显式引用 E 且被语义判官拒绝的句子一律删除」被同一份账本
否掉：生产 113 个带 `sentence_verdicts` 的 run 里，「引了 E 且被拒」共 39 条，来源档
L4_structured（本地 DuckDB 结构化行情）占 25 条，判官原话里 7 条写明「其中数字本身有
证据，不是拒绝原因」，拒的是「优先级 1 凭什么」；另有 1 条拒的是「暴露『调用工具』」。
这一刀会把移远通信公司矩阵 8 行里的 7 行连判官背书的行情数字一起删。普查原件与命令：
`docs/verification/2026-09-21-judge-verdict-census-pre-reason-codes.md`。

v21 的处置（`intelligence/services/episode_semantic_verifier.py::_plan_repair_indexes`）：

| 判官理由码 | 动词 | 公开稿 |
|---|---|---|
| `fact_beyond_evidence` | 删 | 句子移除，连坐的有据数值按槽补回 |
| `unsupported_ranking` | 改写 | 矩阵行「优先级」格 `N` → `N（研判）`；不是矩阵行则退回槽位规则 |
| `internal_process_leak` | 改写 | 「调用工具」一族 → 「检索」；仍残留内部词则退回槽位规则 |
| `causal_or_role_overreach` / 无码 / 未知码 | 槽位规则 | 必答槽内降级为 issue（句子保留），槽外删 |

理由码是判官报告的**可选**字段（`reason_codes`，tool schema 与 JSON 两条路都收）；缺码、
未知码、畸形字段只影响路由，不作废报告；多出别的未知键仍作废。判官 prompt 增加四码释义。
新增机械探测器 `unknown_stock_code`：句内 A 股六位代码任一不在任何证据语料 → 该句从
「语义」划到「机械」（删）；只做分区，不做预检，删除权仍先归判官。排序题送判载荷增加
`ranking_contract` 块，告知判官「优先级」列属 model_reasoning。`_annotate_semantic_rejects`
（零调用点的死函数）删除。

v19 的 P3（「EDA、封测、存储、汽车芯片随后」未绑定所引 E）在 v21 下的处置取决于判官是否
给码：给 `fact_beyond_evidence` 则删；不给码则与 v18 及生产一致——降级保留、控制面记账。
**这是有意的缺省**：判官不吐码时宁可少删。吐码率用 census 的 `judge_stage.coded_share` 量，
上线前基线为 0.0%（字段刚有）。

v21 未做 live：本轮没有起 sidecar 重跑三题，生产判官（K3 自审链）是否稳定回 `reason_codes`
未验证；v20 的 live 结论不移签给 v21。
