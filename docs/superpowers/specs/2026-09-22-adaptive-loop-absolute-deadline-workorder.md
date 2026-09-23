# 2026-09-22 自适应研究回路：传输层绝对截止收口工单

可独立分发。执行方无需读聊天记录，本单自带背景、证据路径、步骤、验收与红线。
姊妹：#75（两位终审）、#76（真实改稿复核）。顺序不可颠倒：修完 → 重跑严格探针 → 真实改稿复核 → 两位终审。本单只到「重跑严格探针」为止，后两步交姊妹单。

## 背景与动机

- 分支 `feat/adaptive-research-loop`（HEAD `aa0509d61`，领先 main 56 提交，**未推**；树 `~/finance-worktrees/adaptive-research-loop` 有 2 个未提交路径）。收口审计在隔离树 `~/fwp-wt-adaptive-research-closeout-0922`（钉 `a9ba35159`）完成：ruff、registry 四项、ledger-crosswalk 全 exit 0；前端六步 exit 0（单测 110、E2E 34P/2S）；完整 pytest 12840P/85S/2X exit 0；两个自写收益对抗探针均过。**裁决 CHANGES_REQUIRED，不予收口**：严格探针 `scripts/review_probes/diagnose_llm_timeout.py --assert-deadline` exit 1，**13 场景 7 个越窗**——`llm_refine.py` 把获批秒数交给 `urlopen(timeout=)`，那只是 socket 空闲上限；流式读循环无绝对截止，持续滴流可无限延长。最狠的 `judge_late_report`：批 0.8 秒、2.94 秒才回包，却记 `success` 被采纳。全绿不矛盾：`test_llm_timeout_diagnostic.py` 只断言探针自身，全仓没一条测试约束 `llm_refine` 墙钟——工具入库了，约束没入库。
- 之后作者已落传输层：`f514e6713`「enforce absolute deadlines on llm http calls」（20 文件，新模块 `intelligence/services/llm_http_transport.py`，`_open_deadline_http_response(req, timeout=, deadline=call_deadline)` 接入四处调用点，`_HTTP_TRANSPORT_OVERRIDE` 上下文变量供测试替身）、`a945c51ff`「修一条既有测试竞态」、`11f702f12` / `aa0509d61` 文档「record the all-green run on an idle machine」。`test_llm_timeout_diagnostic.py` 现含 `test_violation_uses_actual_wall_time_not_timeout_quote`、`test_real_slow_response_is_cancelled_without_accepting_late_payload[scenario]`、`test_real_late_judge_report_is_rejected_at_the_transport_boundary`、`test_zero_deadline_has_no_http_or_billing_attempt` 等。**本单从 09-22 22:20 的分支状态起接手；先核对上述提交是否已把 7 条越窗全部转绿，再决定还剩什么。**
- 独立审查**未完成**（新上下文 codex、只读沙箱、268 秒额度耗尽中断），不算外审；真实模型改稿复核未做；`adaptive-absence-live` 记的内容未过依然成立。三题真实冒烟曾暴露：数字门按单位错位误删 6 句有证据的数值条件（同族事故见 issue #852 与 `numeric-gate-unit-mismatch` 教训）。
- **已定的形态决策**：local_only 四只读能力、根 T900 / 单发帽 75 / 共享窗 150 不变，不开 derived_calculation；`finance_query` 受限提供已观测日逐日复利摘要，不用文本算术解析器；收口审计在隔离树跑不在本树跑（本树有未提交路径，混进去的绿说不清是哪份代码）；本轮不跑真实模型（超时不受控时失败分不清是内容差还是请求被拖断——修完才能跑）。

## 目标

1. 在隔离树（新钉 `aa0509d61` 或更新 HEAD）重跑 `diagnose_llm_timeout.py --assert-deadline`：13 场景全部在窗内则目标 1 完成；仍有越窗则逐条修，每条修法带一条会红的常规 pytest 用例（把 `--assert-deadline` 那 7 条转成回归）。
2. 判官迟到回包判不可用（不是 success），预算归因到「超时」而不是「成功」；`AgentUsage` 与调用台账对上。
3. 两个未提交路径处置（提交或登记不提交）；推送分支；开 PR（base main）；前向 main；低负度四叶。
4. 交 #76 真实改稿复核条件卡（三题冒烟原题、固定 SHA、预算）与 #75 两位终审需求。

## 非目标（写死认领）

- ❌ 不改 T900 / 75 / 150 三档预算；不开 derived_calculation。
- ❌ 不用文本算术解析器；不把 `river_query` 个股口径冒充板块。
- ❌ 不修数字门单位错位（issue #852 / `numeric-gate-unit-mismatch` 族，另一张单）；本单只保证传输层不拖断。
- ❌ 不跑真实模型（#76）。
- ❌ 不给 `--assert-deadline` 探针加「容忍」参数求绿。

## 证据路径

| 文件 | 看什么 |
|---|---|
| 分支 `feat/adaptive-research-loop`：`docs/handoffs/inflight/feat-adaptive-research-loop.md`、`docs/handoffs/2026-09-22-adaptive-closeout-audit.md` | 裁决、7 条越窗清单、传输层交接 |
| `~/.finance-runtime/adaptive-closeout-20260922/VERDICT.md` 与收据根 | 隔离树读数 |
| `intelligence/services/llm_http_transport.py`、`llm_refine.py`（`_open_deadline_http_response` 四处调用点、约 1167 / 1219 / 1425 / 1541 行） | 绝对截止怎么接的 |
| `scripts/review_probes/diagnose_llm_timeout.py`、`intelligence/tests/test_llm_timeout_diagnostic.py` | 严格探针与已有回归 |
| `~/agent-memory` 里 `collapsed-timeout-asked-means-clock-already-spent`、`granted-budget-fields-must-be-read-at-the-enforcement-point` | 同族原则：`timeout_asked` 不是实际耗时；授予的额度要在执行点读 |

## 步骤

1. 开工三连；隔离树 `git worktree add --detach ~/fwp-wt-adaptive-deadline-<日期> aa0509d61`（或当前 HEAD）；本树 2 个未提交路径先 `git diff` 落盘。
2. 跑严格探针；结果 JSON 落 `docs/verification/<日期>-adaptive-deadline/`。
3. 越窗逐条修：流式读循环内按单调时钟判，超时断连并归因；不靠对端配合。每条修法先写会红的用例。
4. 判官迟到回包：构造 0.8 秒批、2.94 秒回包的替身，断言 `judge_status=unavailable` 且预算记超时。
5. 推送、PR、前向、低负载四叶。
6. INDEX #72 行；inflight ≤3K。

## 验收

- [ ] `diagnose_llm_timeout.py --assert-deadline` exit 0，13 场景 0 越窗，JSON 落盘。
- [ ] 阳性对照：把 `_open_deadline_http_response` 的 `deadline` 参数改为不传，至少一条常规 pytest 用例红（不只是探针红）；还原后绿。
- [ ] `judge_late_report` 场景：`success=False`、原因码为超时、预算归因超时。
- [ ] PR head 四叶收据 revision == head；2 个未提交路径有处置记录。

## 红线

- 只用 pathspec 提交；合入 main 等用户确认；不强推。
- 不跑真实模型；不动生产 8792。
- pytest 用主树 `.venv-workbench/bin/python` 并建独占 `basetemp`；密封 fixture 只读，清理前 `chmod -R u+w`，一轮占 3.2G，先看磁盘。
- `timeout_asked` 不是实际耗时；核验轮数 / 实际调用数 / 零秒拒发要分账。
- 不写明文密钥。
