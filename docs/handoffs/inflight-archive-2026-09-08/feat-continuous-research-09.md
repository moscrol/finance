# feat/continuous-research-09 · 09 连续研究第一刀

## 这个分支做什么

同一题材研究跨轮/跨会话续接：把会话下已有对象（run 链、消息 turn_intent/followups/citations、判断轨裁决）只读投影成「研究项目状态」，研究车道开工前作先验块进模型；追问卡带 `kind` 与 `inherits`，点击随消息 POST `continuation`。任务书 `docs/superpowers/plans/2026-09-09-capability-upgrade/09-…-goal-brief.md`（在 `codex/docs-capability-upgrade-plan`）；进度 `…/progress/09.md`，范围外 `…/blocked/09.md`。

## 决策与被否方案（展开：`docs/handoffs/2026-09-09-continuous-research-09-decisions.md`）

- 只读投影 / 否新建台账 / 红线「不双写」
- 先验并进 `conversation_context` / 否新开字段、否改 stance_pack 门 / 不动 INV-R1；价格纪律会误伤研究题
- kind 由 angle/type 确定性映射 / 否 LLM 分类 / 「同义改写」要能被测试钉死
- 换题=两侧对象都识别且不同 / 否问句变就重置 / 追问不该被判换题
- 裁决只改卡片先后 / 否改文案或加权 / 09-06 spec §5.2
- 降级轮不当上轮结论 / 否照抄首句 / 真实 429 模板曾被当成判断
- 不改 `run_store.py` / 否 Run 加字段 / 历史发现分支正扩它

## 当前状态

树 `/Users/a77/fwp-wt-continuous-research-09`，基线 `gitea/main@5eb24515`，提交 `f2a48866` 已推；对 `gitea/main@db2052db` merge-tree 无冲突。**未合 main、未切 8792**。验收 sidecar 8847 跑本树最终代码（`~/.finance-runtime/continuous-research-09/start-sidecar.zsh`，用户 `cr09`）。

## 已验证

- Python 新增/改动 46 绿；触及面 240 绿；全量 8320 passed / 1 failed（`test_rag_worker` 时序，与本支无关，单跑见 progress §3）；pre-commit 11 道过；`ruff check .` 过。
- 前端 lint / typecheck / vitest 76 / build 绿（产物已还原不提交）。
- 真实门三轮：`continuation` 落用户消息、`parent_run_id` 链、先验块进 durable `prompt_assembled`、卡片去重与三分法 [实测]。

## 未验证 / 已知边界

- 研究差量未评：24 次模型调用全 429（9 个并发 sidecar 打满 cockpit 网关）；P2/P3 未跑；真实隔日需自然日。
- 跨会话续研只按 `turn_intent.primary_subject` 精确匹配、扫最近 40 会话；对象未识别时只在同会话续。
- 07 recheck / 08 补数 / S4 案例未接（blocked B1–B3）。

## 下一步

1. 网关空闲（先探 cooldown）后按 progress §3.1 重跑 P1，再 P2/P3；次日同会话续研记差量。
2. 浏览器人检「项目」页与卡片标签。
3. 用户确认后开 PR / 合并；合后重建前端。

## 踩过的坑

- 8813 起服务后监听者是别的树：`lsof -a -p <pid> -d cwd` 核归属再信 health。
- App 级 vitest 用固定 `apiMocks`，新增 api 调用不补表会让无关测试红。
- `git commit -- <路径> -F -`：选项必须在 `--` 之前。
- 「字段契约」门只扫 Python：只被 TS 读的字段登记 ALLOWED 或给 Python 读点。
