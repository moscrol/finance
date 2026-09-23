# 2026-09-23 晨汇消费修复（PR #847）收口工单（#87）

可独立分发。执行方无需读聊天记录，本单自带背景、证据路径、步骤、验收与红线。
来源：`docs/handoffs/2026-09-23-orphan-inventory.md`。前置：**live 验收依赖 #61**（行情恢复到当日）；工程合入不依赖。配套知识库仓 PR **#157** 需同步判定。

## 背景与动机

PR **#847**（`fix/briefing-consumption-qc-0921`）修 IMA 缺队列时的假成功（缺输入 exit 2）、新增只读晨汇消费验收 `scripts/verify_briefing_consumption.py`（只读行情 + 独立标签库；错标签 / NULL 变零 / 重复版本 / 回填时间过早 / 缺行均拒绝；缺行情记 BLOCKED 不造行）。候选 `338db9114`（main `e82717d9a` + head `68b622b76`）全量 12520P / 85S / 2X、前端 110P、E2E 34P/2S、registry 通过。

停下来的原因：独立复审三轮都没有可放行结论——K3 首轮 429 `credit_exhausted_5h` 无报告；改走 `18790/v1 -> 8080` 桥后 97 次请求无模型错误，但 finance 侧 CHANGES_REQUIRED 的主要反例被协调者复核为**审查者自己弄错**（候选正确拒绝了早于来源录入的标签，审查者却把预期改成 PASS），KB 侧引用了改前文本；接纳状态 `REVIEW_EVIDENCE_DISPUTED_NO_APPROVAL`。另外 09-18 起行情截至 09-18，live 消费验收一直 BLOCKED。之后无人接手。

今天核对 [实测]：4 个非文档文件（`intelligence/cli.py`、验收脚本、2 个测试），对当前 main **1 处冲突**（`.claude/lessons_learned.md`，追加式）。

## 目标

1. 前向到当前 main（union 解 lessons），四叶收据绑定新 head。
2. 独立复审重做一次，**修正提示词两处混层**（事件布尔 vs 教学汇总 NULL；正向 fixture 缺列），审查探针与作者测试分开记账（#75 纪律）；结论四值之一，不许 disputed 状态再当终态。
3. 与知识库仓 PR #157 的耦合写清：谁先合、合一半会不会坏（本仓脚本读 KB 的标签库路径）。
4. 合入等用户确认；live 消费验收在 #61 把 `fact_market_daily` 补到当日后另行授权跑一次，只读。

## 非目标

- ❌ 造行情行、放宽「缺行情 = BLOCKED」。
- ❌ 借复审结论改业务代码（协调者已判反例是审查错，别按误报改）。
- ❌ 写 IMA 队列 / 触发真实 IMA 抓取。
- ❌ 处理 #61 的行情恢复本身。

## 证据路径表

| 文件 | 看什么 |
|---|---|
| `python3 scripts/gitea_pr.py show 847` 及评论（09-22 02:45、03:41） | 候选身份、K3 三轮经过、争议点 |
| `gitea/fix/briefing-consumption-qc-0921:docs/handoffs/inflight/fix-briefing-consumption-qc-0921.md` | 当前状态、送审 SHA |
| `gitea/fix/briefing-consumption-qc-0921:docs/handoffs/2026-09-22-briefing-k3-bridge-qc.md`、`docs/verification/2026-09-22-briefing-k3/` | 桥接实测、`coordinator-qc.json`、原报告与异议分开封存 |
| `git diff gitea/main...gitea/fix/briefing-consumption-qc-0921 -- intelligence scripts tests` | 净 diff |
| 知识库仓 PR #157（`<知识库>/…`，用 `git -C ~/knowledge-base-private remote get-url gitea` 找地址） | 配套改动与合入顺序 |
| `docs/learning/ledger-map.md` | 晨汇台账 canonical 路径与唯一写入者，验收脚本只能读 |
| `docs/superpowers/specs/2026-09-22-market-recovery-bridge-and-contracts-workorder.md`（#61） | live 验收的前置状态 |

## 步骤

1. 开工三连 + `git fetch gitea`；`git worktree add /Users/a77/fwp-wt-briefing-0923 gitea/fix/briefing-consumption-qc-0921`；`git merge gitea/main`，lessons union。
2. `.venv-workbench/bin/python -m pytest -q tests/test_ima_gap_report.py tests/test_verify_briefing_consumption.py`；四叶。
3. 写耦合说明（本仓 ↔ KB #157）贴两张 PR。
4. 复审：改提示词两处后走 K3 桥一次（批前探网关，memory `probe-shared-llm-gateway-before-a-batch`）；结论与探针分开落 `docs/verification/2026-09-23-briefing-k3-r2/`。
5. 贴读数；QUEUE.md 一行；inflight ≤3K；INDEX #87 状态行。

## 验收

- [ ] `merge-tree` 干净；四叶收据 revision == head、`dirty=false`、failed=0。
- [ ] 阳性对照：给验收脚本喂一份标签录入时间早于来源的样本，必须拒绝；喂缺行情样本，必须 BLOCKED 且不产生任何写入。
- [ ] 复审结论是四值之一，报告 + 探针 + 异议三者路径贴 PR。
- [ ] 耦合说明写明合入顺序与「合一半」的行为。
- [ ] INDEX #87 行已改。

## 红线

- pathspec 提交；合 main 等用户确认；不强推。
- `.venv-workbench/bin/python`；KB 测试需 `FINANCE_WS` + workbench venv（memory）。
- 只读行情与台账；不写 IMA 通道；不打飞书。
