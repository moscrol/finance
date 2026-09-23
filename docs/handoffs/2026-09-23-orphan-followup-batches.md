# 2026-09-23 盘点遗留四件事的收口收据：批次 1（已合）与批次 2（四叶绿，等确认）

写完不改。执行者 Claude Code（会话 `finance-workspace-private-fc`，session `6365388c-cda3-42cb-a667-14e46ff3ee2c`，20:5x–23:3x CST）。决策与依据在 `2026-09-23-market-recovery-decisions.md`，本文件只记「做了什么、读数在哪、还差什么」。原件根 `~/.finance-runtime/reviews/orphan-followup-0923/`。

## 批次 1：#871 → #861 → #874 → #893（已合入 main）

预览树 `d016844d8` = `gitea/main@626d8a508` + 四枝，四叶：

| 叶 | 读数 | 原件 |
|---|---|---|
| python | ruff 0；**14848P / 0F / 85S / 2X**，17m43s；收据 `receipts/gate-3KPoH1B6/pytest.json` revision `d016844d8526` dirty=False，`check_test_receipt.py` 可采信（collected 14935 对账平，基座漂移 0） | `python-gate.log` |
| registry | `build_registry.py` 四项 + crosswalk 五项 exit 0 | `frontend-e2e.log` |
| frontend | lint 0 / typecheck 0 / vitest **120P** / build 0，dirty=0（首跑四红是新树无 `node_modules`，环境红，`pnpm install` 后复跑） | `frontend-e2e-2.log` |
| e2e | **34P / 2S**，端口 8797/8798 | `frontend-e2e-2.log` |

| PR | 合并提交 | 落地文件 | record |
|---|---|---|---|
| #871 桥 + mootdx 熔断 | `a026544c5` | 9 ✓ | `merge-871.json` |
| #861 五项合同 + 离线审计 | `d3ff8219c` | 21 ✓ | `merge-861.json` |
| #874 交付门 answer_status 取更差（去 `WIP:` 后合） | `09da2ae03` | 3 ✓ | `merge-874.json` |
| #893 代拍记录 + INDEX | `c9dd71dfd` | 3 ✓ | `merge-893.json` |

合后核对：`git diff d016844d8 gitea/main` 非文档差异 0；文档差异只有 #893 自身两处尾提交（INDEX 行 / inflight）。授权原话与出处逐字在每份 record（用户 20:5x CST「这些你来做，包括工单」+ 常设授权），读数评论 #871 6574 / #861 6577 / #874 6580 / #893 6583。

## 批次 2：#844 → #896 → #897 → #898 → #899（四叶绿，**合入等用户确认**）

预览树 `d29d6f73f` = `gitea/main@c9dd71dfd` + 五枝（链式 merge-tree 全 clean，50 非文档文件，webapp 0），四叶：

| 叶 | 读数 | 原件（`batch2/`） |
|---|---|---|
| python | ruff 0；**15123P / 0F / 85S / 2X**，20m48s；收据 `receipts/gate-d4NAGBov/pytest.json` revision `d29d6f73f66f` dirty=False，可采信（基座漂移 0） | `python-gate.log` |
| registry | 五项 exit 0 | `frontend-e2e.log` |
| frontend | install 0；lint 0 / typecheck 0 / vitest **120P** / build 0，dirty=0 | `frontend-e2e.log` |
| e2e | **34P / 2S** | `frontend-e2e.log` |

| PR | 分支 @ head | 工单 | 来源 |
|---|---|---|---|
| #844 | `fix/rag-probe-diagnostics-0921@ac810f570`（前向 main，仍 `WIP:`，合时去） | #62 | 定向 205P，评论 6485 |
| #896 | `fix/financial-ttl-baseline-fwd-0923@faa87b2f9` | #66 | #855 两道门 + 混比拒句 cherry-pick 前向；定向 909P；阳性对照 1/8→0/8→1/8 |
| #897 | `fix/mutation-timeout-evidence-fwd-0923@244a7de8f` | #66 | 变异量具超时留证前向；定向 31P |
| #898 | `test/sse-drain-mutation-guard-0923@7fc9fc0c1` | #66 | 存活变异是既有见证未登记进 targets，登记后击杀 |
| #899 | `fix/history-completion-fwd-0923@bce35a1a8` | #68 | `807a75d88` + 前向 + 证据快照 v4（main `cb16cd463` 白名单拒 `history_provenance`，26F→0F）；定向 870P；阳性对照 3F→10P |

读数评论贴在五张 PR。确认后：`AUTH2="<用户原话>" SRC2="<出处>" bash ~/.finance-runtime/reviews/orphan-followup-0923/batch2/run-merge-batch2.sh batch`（预览树 `~/fwp-preview-orphan3-0923` 作执行树；每张合前 fetch + 漂移 0 + head 未动 + merge-tree clean）。合入后：#845 / #833 补指针评论 → #899；INDEX #62/#66/#68 改「已合 + SHA」。

## 其他动作

- #868：不合，评论 6483 列三条翻转条件（当前 head 完整四叶 + 联合树；#75 独审终稿；L6 出结果或用户放弃）。
- #855：关闭，指针评论 6551 → #896（分支保留，`~/fwp-wt-8792-ttl-baseline-0922` 有检出）。
- #73：未动（波次协调 Pi 会话持有，用户已选 B，四叶 PASS 待独审），INDEX 行改「有 owner」。
- 启动器 `RAG_BGE_MODEL` 补丁：`~/.finance-runtime/reviews/rag-readiness-0923/launcher.patch` + README，**未应用**；快照已完整，原「重启撞不完整快照」前提过期，反向对照应改为「指向不存在目录应拒启」。旁路对照 BLOCKED_RESOURCE（load1 70–95）。
- 记忆：`workorder-status-truth-lives-on-coordinator-local-branch`、`delegated-decisions-record-as-proxy-with-verbatim-quote`；Gitea POST 超时但已落、新树前端叶先 `pnpm install` 追加进既有条目。

## 等用户的三件事

1. 批次 2 五张 PR 合入确认（一句话即可，原话进 record）。
2. 启动器补丁是否应用（改前备份、不重启 8792）。
3. 09-21 行情恢复到「换库」那一步的发布授权（QC 会话 `fix/market-recovery-qc-0923` 按 #861 评论 6463 口径继续）。

## 树与清理

已删：`fwp-preview-orphan2-0923`、`fwp-wt-orphan-followup-0923`（分支 `docs/orphan-followup-0923` 本地已删、远端随合并删）。保留待批次 2 合入后删：`fwp-preview-orphan3-0923`（执行树）、子代理树 `fwp-wt-financial-fwd-0923` / `fwp-wt-mutation-gauge-fwd-0923` / `fwp-wt-sse-guard-0923` / `fwp-wt-history-fwd-0923`；作者树 `fwp-wt-rag-probe-diagnostics-0921` 是 #844 分支唯一检出，合入后再删。本枝 `docs/orphan-followup-0923-close` 树 `fwp-wt-orphan-close-0923`。
