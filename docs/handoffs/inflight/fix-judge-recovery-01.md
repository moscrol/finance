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
已提交 `b7bf0d94`，树干净。未合 main、未切 8792。基线 `gitea/main=5eb24515`。

## 已验证
直接测试文件 241 passed；V11 新测试 22 条；adapter/verifier/invariant 191；pre-commit 11 道过；`check_unread_fields` 无新增。全量安静跑 8330 passed / 0 failed（15.6 min；此前高负载跑 3 条超时看门狗测试红、单跑绿）。391 份真实存证：基线 vs 分支首个损失点 A/B 零差异，`extension_outputs` 出现 0 次。

## 未验证 / 已知边界
- **真实 Workbench 对照零草稿**：两臂 sidecar（8821 基线 / 8822 分支）五题全 HTTP 429，LLM 网关 `localhost:57244` 无监听；四类同题「升级前后」未展示，`v11_outcome` 只见 `skipped`。
- V11 lifted 用户不可见（V8 后公开稿无存疑标）；§8 A/B 与台账 `R-20260822-05` 未做。
- 缺陷一自然频率不可从存证读出（被拒修复轮不落事件）。

## 下一步
1. 网关回来后按 progress/01.md「续跑命令」串行两臂五题（先 `lsof -iTCP:57244`，再单发一题看 `draft_chars>0`），逐题读公开稿填「真实验收」。
2. 合并前以 `feat/judge-token-usage`（同改 `_run_judge`）为准重跑本单测试。
3. 用户确认后合 main；TOOLKIT 登记 `judge_loss_point_replay.py` / `launch_workbench_sidecar.sh`（harness-reference 树脏未动）。

## 踩过的坑
- `_judge()` 夹具第二次调用自动放行；issue 里「第N句」会被并回拒句集。
- 23 个 adapter 替身是严格签名，新 kwarg 按 `inspect.signature` 条件传。
- 两臂并发发题→全 429→网关端口消失；先探网关、单发、串行。
