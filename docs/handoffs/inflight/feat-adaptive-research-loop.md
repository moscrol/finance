# feat/adaptive-research-loop 在途

## 这个分支做什么

研究回路取证、窗口收益、公开保真 + LLM 传输层绝对截止（`f514e6713`）。#72 收口已到「PR 开出、四叶全绿、等用户确认合入」。读数与 #76/#75 条件卡在 `docs/verification/2026-09-22-adaptive-deadline/README.md`；#75 队列行在 `docs/verification/2026-09-22-independent-qc-batch/QUEUE.md`。

## 决策与被否方案

- 验收变异（`deadline=` 不传）376 条全绿 → 补包装层用例 `c582d6755`；否了「作者四杀已够」：那四条只变传输层模块。
- 二次前向：#863 合入后 4 文件冲突在作者树解（`3020e42df`）；否了 rebase/重做：62 提交功能枝重做不现实。两处语义冲突收尾 `b7a479e6a`：E-token 免检改用 main 引用语法（产品行为改一处：E0/E027 不再免检，与 main 一致）；#863 传输测试改走本枝 `http_transport_override` 缝。
- INDEX #72 行不改（#858 分支热），行文本在 PR #868 描述末尾。
- `is_cancelled=` 转发变异存活但不补代码，配方在 README。

## 当前状态

本地功能分支已三次前向到 `7ad61a0d3`，父提交为 `24ada4f80` 与最新 `gitea/main@760248ece`；树干净。PR #868 远端仍指向旧 head `7deedffba`，且临时加了 WIP 守卫（只防误合，不是合入）。未部署、未碰 8792。推送新 head 前需再核 remote main 与本机 merge-tree；**合 main 等用户确认**。

## 已验证

`7ad61a0d3` 隔离树四叶全绿：ruff；pytest **14921P/85S/2X/0F**（收据可采信）；前端六步（120 单测、E2E 34P/2S）；registry×4 + crosswalk；严格探针 `deadline_violations=[]`；冲突相关定向 63P。实际 wrapper 调用点 5 处（1167/1219/1424/1546/2304），均带 deadline。收据根 `~/.finance-runtime/reviews/pr868-forward-20260923/gate-7ad61a0d3/`。

## 未验证 / 已知边界

真实模型改稿复核（#76 L6）未跑；第二方 Spec/Quality（#75）未做；`absence-live` 三个内容未过项仍成立；`is_cancelled=` 转发无人守（15 条 cancel 测试在变异下全绿）。新 head 尚未推送，PR body/QUEUE 已待同步；守卫不要在用户确认前解除。

## 下一步

1. 提交 README/QUEUE/交接 docs；2. 推送功能分支，跑 `gitea_pr.py conflict-check`；3. 回读 PR head 与 WIP 状态，门禁一致后保持 WIP 等用户拍合；4. #76/#75/内容层继续按条件卡处理；5. #858 合后再落 INDEX #72 行。

## 踩过的坑

`--basetemp=X/Y` 前先 `mkdir -p X`；zsh 里 `$a` 不分词、无匹配 glob 会中断 `&&` 链（两次伪红）；机器磁盘 <1G 时全量 pytest 会被 OOM 杀（83% 处），起跑前看 `df` 与 pytest 进程数；磁盘清理会连带删 `.code-review-graph/` 两个已跟踪文件，跑门禁前 `git status` 再看一眼。
