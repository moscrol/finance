# fix/judge-recovery-01 · 判官修复 01

## 这个分支做什么
让已查到、有证据的答案能交付：契约外绑定不连坐核心答案；修复进展按内容算、来源独立性另记；纯语义缺口做一次有界回检索（V11）。合同 `docs/superpowers/plans/2026-09-09-capability-upgrade/01-judge-recovery-goal-brief.md`，进度 `…/progress/01.md`，范围外登记 `…/blocked/01.md`，决策快照 `docs/handoffs/2026-09-09-judge-recovery-01.md`。

## 决策与被否方案
- 契约外绑定分两档：哈希可核验→扩展区 STRIP_OK，池外/重复→仍 BLOCK。否「一律放行」（编造引用）与「一律 BLOCK」（复现二连坐）。
- 进展=新 id 指向未覆盖输出；家族另记 `new_source_families`。否「保留家族门」（同源补锚被拒）与「新 hash 即进展」（ARL-0014 f5）。
- V11 默认开 + `FINANCE_V11_GUIDED_RETRIEVE=0` 回滚。否设计稿默认关：合同点名「不能只接永远不开的开关」。
- 回检索走注册表 `kb_search` + `bounded_stage` 子窗；否直连 `kb_rag`（第二条检索链）。
- lifted 只记账；否绑进台账（V11 §10.1）与模型改写（V8 决定）。

## 当前状态
已提交 `c83cd0bf`（含第四轮验收记录），树干净。未合 main、未切 8792。基线 `gitea/main=5eb24515`。PR #693 正文已 PATCH 为实测结果。基线 worktree `/Users/a77/fwp-wt-judge01-base` 已移除，sidecar 已停。
**token-usage 叠加兼容已验（2026-09-10）**：container merge-tree（无冲突，exit 0）物化后全量 **8379 passed / 0 failed**（5.6 min），定向三组 241+191+49 全过，pre-commit/ruff/字段契约全绿。详见 progress/01.md「任务 2」。

## 已验证
直接测试文件 241 passed；V11 新测试 22 条；adapter/verifier/invariant 191；pre-commit 11 道过；`check_unread_fields` 无新增。全量安静跑 8330 passed / 0 failed（15.6 min；此前高负载跑 3 条超时看门狗测试红、单跑绿）。391 份真实存证：基线 vs 分支首个损失点 A/B 零差异，`extension_outputs` 出现 0 次。

## 未验证 / 已知边界
- **真实 Workbench 对照已跑完（第四轮，sub2api 8080）**：5 题 × 2 臂全草稿。判官可达时三刀按预期（Q1 两臂同形、Q5 分支拒「必涨停」前提给条件性研判）；Q3 证据量差（基线 171 vs 分支 13）归因 OpenAI-family 上游池间歇 503（51 账号全 503 failover），非判官误挡；Q4 分支单发 HTTP 400 待归因。「冻结样本整体挡回减半」本轮无法判定（4/5 题至少一臂判官不可用），需上游池稳定后重跑。
- V11 lifted 用户不可见（V8 后公开稿无存疑标）；§8 A/B 与台账 `R-20260822-05` 未做。
- 缺陷一自然频率不可从存证读出（被拒修复轮不落事件）。

## 下一步
1. ~~合并前以 `feat/judge-token-usage` 为准重跑本单测试。~~ **已完成（2026-09-10）**：叠加树全量 8379P/0F，三组定向 + 门禁全绿，可合。
2. 用户确认后合 main；TOOLKIT 登记 `judge_loss_point_replay.py` / `launch_workbench_sidecar.sh`（harness-reference 树脏未动）。
3. （可选，不阻塞合并）上游池稳定后重跑一轮真实验收，给「挡回减半」一个判定。**2026-09-10 11:52–11:57 双出口探测（按 /tmp/k3-wrap-common.md 踢醒）**：8080 sol/terra 持续 `upstream_error` 503（Plus-first 已写入 Sub2API，是新会话才生效的优先级，不改变上游 503 事实）；57244 间歇 `auth_unavailable` / `server_is_overloaded`——两出口都未达「连续 2×200」，不发题、不起 sidecar。已排 12:17 会话内一次性唤醒续探；会话若死，接手者按 progress/01.md「续跑命令」手动跑，前置不变：最小 chat 有 `choices` 才发题，两臂串行。

## 踩过的坑
- `_judge()` 夹具第二次调用自动放行；issue 里「第N句」会被并回拒句集。
- 23 个 adapter 替身是严格签名，新 kwarg 按 `inspect.signature` 条件传。
- 两臂并发发题→全 429→网关端口消失；先探网关、单发、串行。
