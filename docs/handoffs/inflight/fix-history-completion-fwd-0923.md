# fix/history-completion-fwd-0923 · 历史 completion 分支前向（#68 代码与 PR 部分）

树 `/Users/a77/fwp-wt-history-fwd-0923`，基座 `fix/history-completion-0922@807a75d88` + 合并 `gitea/main@626d8a508`（`2d7a5d91f`，
merge-tree clean）+ 修复 `907f7e90b` + 本文档提交。全量四叶、合并、INDEX #68 行都归主会话，本分支不自跑全量。

## 状态（2026-09-23）
- 相对 main：30 文件（非 docs 29），不含 #814 门禁移植（`42784d27e` 经 #863 已在 main，合并前的 `807a75d88` 不含它）。
- **语义冲突已解**：main `episode_evidence.py` 的显式原子白名单 vs 本线 `AgentEvidence.history_provenance`，合并后 26 条
  定向测试红（`evidence atom fields are incomplete or unknown`）。按 main 引入 v3 的方式加 **快照 v4**（严格持久化完整
  provenance 或 None；v1–v3 保原字节、不推断；带 provenance 的卡不可降级）。详见
  `docs/verification/2026-09-23-history-completion-fwd/README.md` §1。
- 定向集 42 文件：修复前 26F/844P → 修复后 **870P/0F**（干净树，收据 `20260923T142302Z-907f7e90-d4c6a48cbcca.json`）。
- 阳性对照：规则型启动判据改回按结果筛 → `test_history_launch_control.py` 3F/7P；还原 → 10P。
- `test_code_map::test_structure_probe_daily_full`：本树无图被 skipif 跳过；拷主树图会被 `code-review-graph` 以「仓根不符」
  拒绝（三次 FAILED 是拷贝图读数，作废）。低负载有图读数**未取得**，`scripts/code_map.py`/`tests/test_code_map.py` 对 main
  diff 0 字节。

## 下一步（接手先做）
1. 主会话：预览树四叶（含 e2e）；`test_code_map` 在有本树构建图、load ≤ 4、磁盘 ≥ 8G 时三次复跑。
2. 合入后：#845（`8da96fdac`，442476f7d 是祖先，多出 2 个 docs 提交）与 #833（`7edfe24e7`，祖先）`close --pointer-file`；
   #841（open，71% 内容命中，2 个测试文件本树没有）是活载体，不关。
3. 若 main 再动 `episode_evidence.py`/`AgentEvidence` 字段，先重跑 `intelligence/tests/test_runtime_forward_seams.py`。

## 踩过的坑
- zsh 不给 `$FILES` 分词、bash 3.2 无 `mapfile`：测试清单用 `grep . file | xargs pytest`。
- `.code-review-graph/graph.db` 按仓根绑定，不能跨 worktree 拷用。
