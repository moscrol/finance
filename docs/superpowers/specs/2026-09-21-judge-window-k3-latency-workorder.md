# 2026-09-21 判官窗与 K3 自审延迟工单

可独立分发。执行方无需读聊天记录，本单自带背景、证据路径、步骤、验收与红线。
上游：`2026-09-21-judge-reason-codes`（分支 `fix/8792-premise-market-contracts`，候选 `285c71972`，判官理由码分流）——本单不改它的路由，只解决「重题上判官根本回不来」；两单可并行，各开各的分支。
姊妹：#55 `2026-09-17-no-llm-judge-deterministic-gate-workorder.md`（确定性判官开关）与 #56（判官代码退役占位）——本单假设 LLM 判官仍在线（`judge_mode=llm`），#55 翻开关后本单失去对象，先看 INDEX 状态再开工。

## 背景与动机

- 2026-09-12 用户决策：撤独立 Grok 判官，生产写手 kimi-k3 兼自审（launcher `# ── 2026-09-12 用户决策` 段；收据 `correlated_judge=true`）。
- 2026-09-21 v21 live（K3 写手 + K3 自审，候选 `285c71972`，见 `docs/verification/2026-09-21-8792-premise-market/README.md`「v21 Live」节）量到两条硬读数：
  - market_cause 题：判官请求 **35,528 字符**，K3 返回工具调用 **71.84 s**，单次帽 **75 s**（`judge_attempt_seconds`，max 档）——贴帽通过。
  - 液冷四家排序题（stock_deep_dive，145 张证据卡，写手最大载荷 198k 字符）：判官**两发都撞 75 s 客户端超时**（shim stderr 两条 `BrokenPipeError`；`finish` 12:58:02.8 → `report.complete` 13:00:34 = 151 s），第三发 `timeout_asked=0.0` → `WINDOW_EXHAUSTED_ISSUE` → `judge_status=unavailable`、`degrade_class=judge_unavailable`，公开稿以「本次未完成独立复核（复核服务超时）」首句**照常发布**。
- 后果两条：(1) 重题的语义审核形同虚设——放行了但没人审；(2) 判官理由码里 `unsupported_ranking` 的改写路径（矩阵行「优先级」格加「（研判）」）在 K3 上**不可量**，因为排序答案天然是重题，判官从来没对它返回过一份报告。
- **已定的形态决策**（防重新设计）：不抬回合墙钟 `T=900`、不抬档位预算、不抬 `ASK_SEMANTIC_JUDGE_WINDOW`（launcher 2026-08-14 注释与 `LEFTOVER_WINDOW_ISSUE` 处「不要靠再抬窗口罩尾部」的约束保持）。解法只能在**单次帽**、**载荷**、**切分**三者里选，且先量再选。

## 目标

1. 一张读数表：K3 判官请求字符数 → 耗时（n ≥ 20，含成功与撞帽），数据来自生产 users 根的 LLM 调用台账（`purpose=judge`）与 `~/.finance-runtime/8792-premise-market-v21-users`；给出「多少字符以内 95% 在 75 s 内」这一个数。
2. 在 A / B / C 里选定一条并落地（可组合，但每条都要单独有读数依据）：
   - **A 抬单次帽**：只动 max 档 `judge_attempt_seconds` 的地板；代价是判官吃掉合成保留，要给出「合成保留还剩多少」的读数。
   - **B 载荷压缩**：`_judge_request` 的 `evidence_registry` 只送被正文引用的 E（`cited_evidence_ordinals` 全集）+ 未引用卡只送 id/title；`detail` 按现有 `MAX_EVIDENCE_TITLE_CHARS` 一族截断。`compact_judge_payload` 已有形状，在它后面加一层，不新发明序列化。
   - **C 分句送判**：按槽/段把 `sentences` 切成 ≤N 句一批，各批共用同一份压缩后的注册表，每批一次调用、各自 ≤ 帽；报告按句号并集合并（`_reconcile_issue_sentence_indexes` 之前合并），`judge_round` 记批次。
3. 验收基准题：`~/.finance-runtime/8792-premise-market-evidence/v21-live/8792-v21-extra-ranking.txt`（液冷四家排序）在 K3 写手 + K3 自审下 `judge_status ∈ {passed, repaired}`（不是 `unavailable`），`sentence_verdicts` 要么为空、要么至少一条带 `judge_reason_code`。

## 非目标（写死认领）

- ❌ 不改判官理由码路由与「无码走槽位规则」缺省——那是 `fix/8792-premise-market-contracts` 的事，收紧要看 census `judge_stage.coded_share`，另量另议。
- ❌ 不重开独立判官（Grok / sol 备链）——用户 2026-09-12 决策，要翻是配置决定，不在本单。
- ❌ 不动 `T=900` / 档位预算 / `ASK_SEMANTIC_JUDGE_WINDOW`——见形态决策。
- ❌ 不碰 V11 引导回检索（`_guided_retrieve_and_rejudge`）与「判官不可用 → 带披露放行」的释放语义——本单让判官回得来，不改回不来时怎么办。
- ❌ 不给 K3 网关剥 `temperature` 的 shim 转正——那是 v21 live 的测量条件（`v21-live/k3_shim.py`），生产写手今天是 glm；若生产切回 K3，网关 400 是另一张单。
- ❌ 不做 #55 的确定性判官切换。

## 证据路径

| 文件 | 看什么 |
|---|---|
| `docs/verification/2026-09-21-8792-premise-market/README.md`「v21 Live」 | 两条硬读数的出处、run id、偏差声明 |
| `~/.finance-runtime/8792-premise-market-evidence/v21-live/k3-shim.log` / `k3-shim.stderr` | 逐请求 `req_chars` / `seconds`；两条 BrokenPipe 即撞帽那两发（无时间戳） |
| `~/.finance-runtime/8792-premise-market-v21-users/probe-premise-market-v21-20260921/runs/run_20260921_125145_286054/continuous-episode.json` | `semantic_verifier.judge_attempt_index=2` / `timeout_asked=0.0` / `remaining_seconds_at_entry=372`；`outcome.evidence` 145 卡 |
| `intelligence/services/episode_semantic_verifier.py` `_run_judge` / `semantic_total_judge_window` / `semantic_attempts_for_window` / `judge_attempt_seconds` | 窗与帽怎么算；`window_left` 余额账；`_window_starved_issue` |
| 同文件 `_judge_request` / `compact_judge_payload` / `dumps_judge_request` | 载荷现状与已有的压缩点（B 在这里叠） |
| 同文件 `_reconcile_issue_sentence_indexes` / `_record_sentence_verdicts` | C 的报告合并与账本落点 |
| `intelligence/services/llm_refine.py` `call_purpose("judge")` 与 LLM 调用台账 | 目标 1 的数据源（读侧脚本自己写，复用台账字段，勿新建第二份账） |
| `scripts/offline_judge_verdict_census.py` | 验收 3 的读数口径（`judge_stage.coded_share`） |
| `~/.local/bin/start-finance-workbench` `# ── 2026-08-14 工具批次天花板` 段 | 「不抬窗口罩尾部」的原话与理由 |

## 步骤

1. 开工三连：`git status --short && git branch --show-current && git worktree list`；从最新 `gitea/main` 开 `fix/judge-window-k3-latency`，用主树 `.venv-workbench/bin/python`。
2. 读侧先行：写 `scripts/judge_latency_census.py`（只读台账，不调模型），输出字符数 × 耗时 × 成功/撞帽的表与 P95；把表落 `docs/verification/<日期>-judge-latency-census.md`。**量完发现 P95 已在帽内就停**，把停下写进收据，不改代码。
3. 按读数选 A/B/C；每条改动带一条能红的测试（B：同一份 145 卡 outcome 送判字符数下降且引用的 E 全在；C：切批后报告句号并集与单批一致、`judge_round` 递增；A：合成保留读数不低于现值）。
4. K3 上重跑验收基准题（旁路实例，用户根独立，端口避开 8780–8830；启动脚本可抄 `~/.finance-runtime/8792-premise-market-evidence/v21-sidecar-launch.sh`，含 `temperature` shim 的声明）。
5. 交接：inflight ≤3K；INDEX 本行改状态。

## 验收

- [ ] 读数表落盘，n ≥ 20，给出「95% 在帽内」的字符阈值；若阈值已覆盖 P95 载荷，本单以「不改代码」收口并写明。
- [ ] 所选方案的单测能红：把改动回退一处，对应测试恰好红一条。
- [ ] 验收基准题在 K3 写手 + K3 自审下 `judge_status ∈ {passed, repaired}`，`continuous-episode.json` 落盘，用户根哈希清单在 evidence 目录。
- [ ] `offline_judge_verdict_census.py --runs-root <该用户根>` 的 `judge_stage.count ≥ 1`。
- [ ] 全仓等价 CI 四叶在分支尖上绿（python / frontend / e2e / registry-check），收据 revision == 分支尖。
- [ ] `docs/agent-product-door.md` 判官段随 runtime 改动同一提交更新。

## 红线

- 只用 pathspec 提交（`git add -- <文件>`），不 `git add -A` / `git add .`；合并回 main 必须等用户确认，不强推。
- pytest / ruff 一律 `.venv-workbench/bin/python -m …`。
- 不在生产 8792 上做实验；旁路实例用户根放 `~/.finance-runtime/<task>/`，不写生产 users 根；不重启共享网关。
- 台账号一律 `python3 scripts/claim_ledger_id.py claim --branch <分支>`，不手工取号。
- 不写明文密钥；网关钥匙只从 launcher 读的同一 `client-keys.env` 取，不进任何文件。
