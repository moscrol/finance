# 2026-09-27 晚：#877 Knevo 收口、判官默认关上线、记忆缺口绑定回归修复

写完不改。执行者：Claude Code 桌面会话 `claude/unclosed-session-stats-838ac4`。前文：`2026-09-27-takeover-closeout.md`、`2026-09-27-takeover-round3.md`。

授权（逐字）：「877按你建议的三处都改，继续推进。但是判官现在先默认off」；此前 09:58「……按照最佳方案，我给你授权，也可以真实测」。

## #877 合入（`4c111aa1d`）

| 提交 | 内容 |
|---|---|
| `5e366ea5e` | 判官默认关（`ASK_SEMANTIC_JUDGE` 未设 / 空串 / 拼错 = off，只有 llm/on/1/true/yes/enabled 开）；max 档判官单次 75→120 s、窗 150→240 s（GLM-5.3 在 47 条材料上实测 93 s；75 s 原按已停用的 grok-4.6 标定）；修复窗按重写长度抬地板（15 s + 字数/120，封顶 200 s）；材料题写手规则前置三条硬格式 |
| `cfe81ce24` | 编号材料题包单次模型调用上限与修复窗地板 150 s（flash 首字前思考 61.7 s） |
| `6067d08d4` | 编号材料题包在 GLM-5.3 部署上换 glm-5.3 写手（`MATERIAL_PACK_WRITER_MODEL` 可指定或 off） |
| `e270cf598` | 全量暴露的测试余波（max 档用例按 120 s 重算；链路用例夹具显式开判官） |

live（旁路 8852，K260917-pack1，判官关）：flash 写手 r3 超时、r4 q6「库存回归健康」不过；glm-5.3 写手 r5、r6 过题库硬规则（r6 q7「被证伪」偏强）。验收 PASS_WITH_LIMITS（n=2、无运行时语义复核、作者即复核者）。证据 `~/.finance-runtime/reviews/unclosed-inventory-20260926/takeover/L8/ROUND-0927-SUMMARY.md`。四叶：Python 17937P/0F（首跑 2 条 `test_cleanup_gate_trees` 满载 `lsof` 超时，单跑 12P，同 head 重跑干净）、前端 125P、E2E 34P。

## 8792 切到 `4c111aa1d9de`（09-27 21:55）

快照四叶全绿、readiness 13/13、health 三读、账本对账；一次 bootstrap，停机约 5 秒。记录 `~/.finance-runtime/reviews/unclosed-inventory-20260926/takeover/deploy-4c111aa1d9de/`。

**开判官**：设 `ASK_SEMANTIC_JUDGE=llm`，再配 `LLM_JUDGE_MODEL=glm-5.3`。注意后者也会把仍开着的证据判官（`ASK_EVIDENCE_JUDGE=auto`，同读 `llm_refine.judge_provider()`）换成 glm-5.3，所以本次没有写进生产启动器。

## 切前切后探针暴露的两件事

1. **记忆缺口绑定回归（本 PR 修复）**：#941 的开场记忆预取对有主体的研究题注入咨询槽 `prior_recall`；记忆空命中时合同要求写 `binding.gap`，flash 写手却把「用户记忆缺口」条目本身当 `user_premise` 绑上，`evidence_type_floor` 整稿拒收、收尾兜底再拒一次 → 降级。生产探针 2/2（`run_20260927_211317_791596` 旧版、`run_20260927_215652_267095` 新版）。修法：只引用缺口条目的 `prior_recall` 按合同本意改写成披露缺口（不留证据引用，缺口不变先验）；其他格子与混有真实记忆的引用照旧整稿拒收。撤保护 1F。
2. **传输层截止失效（另立任务，未修）**：旧版探针第 3 轮模型调用 `timeout_asked=75`，21:13:33 发出、21:52:13 才报 `LLMDeadlineExceeded`（2320 s）。与本次改动无关，新版同样可能遇到。
