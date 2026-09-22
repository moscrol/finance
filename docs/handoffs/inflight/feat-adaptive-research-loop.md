# feat/adaptive-research-loop 在途

## 这个分支做什么

研究回路取证、窗口收益、公开保真 + LLM 传输层绝对截止（`f514e6713`）。#72 收口已到「PR 开出、四叶全绿、等用户确认合入」。读数与 #76/#75 条件卡在 `docs/verification/2026-09-22-adaptive-deadline/README.md`；#75 队列行在 `docs/verification/2026-09-22-independent-qc-batch/QUEUE.md`。

## 决策与被否方案

- 验收变异（`deadline=` 不传）376 条全绿 → 补包装层用例 `c582d6755`；否了「作者四杀已够」：那四条只变传输层模块。
- 二次前向：#863 合入后 4 文件冲突在作者树解（`3020e42df`）；否了 rebase/重做：62 提交功能枝重做不现实。两处语义冲突收尾 `b7a479e6a`：E-token 免检改用 main 引用语法（产品行为改一处：E0/E027 不再免检，与 main 一致）；#863 传输测试改走本枝 `http_transport_override` 缝。
- INDEX #72 行不改（#858 分支热），行文本在 PR #868 描述末尾。
- `is_cancelled=` 转发变异存活但不补代码，配方在 README。

## 当前状态

PR #868（base main）head = 代码尖 `b7a479e6a`，其上只允许 docs 提交。WIP 守卫按「二次前向 + 重门禁完成」去掉。**合 main 等用户确认；未部署、未碰 8792。** 作者树与隔离树 `~/fwp-wt-adaptive-deadline-0922` 均干净。

## 已验证

`b7a479e6a` 九项全绿：ruff；pytest **14616P/85S/2X**（收据 `--expect-revision` ✅）；前端六步（118 单测、E2E 34P/2S）；registry×4 + crosswalk；严格探针 0 越窗。变异 `deadline=None`：新用例 RED→GREEN，sha256 核。收据根 `~/.finance-runtime/adaptive-deadline-0922/gate-b7a479e6a/`。

## 未验证 / 已知边界

真实模型改稿复核（#76 L6）未跑；第二方 Spec/Quality（#75）未做；`absence-live` 三个内容未过项仍成立。`is_cancelled=` 转发无人守（15 条 cancel 测试在变异下全绿）。main 再动就要重 `conflict-check`（00:31 漂过一次）。

## 下一步

1 用户确认后合 #868（先 `gitea_pr.py conflict-check`，红了再前向）；2 #76 按条件卡跑三题；3 #75 消费 QUEUE 行；4 内容层三项；5 可选补 `is_cancelled` 用例；6 #858 合后把 INDEX #72 行落主干。

## 踩过的坑

`--basetemp=X/Y` 前先 `mkdir -p X`；zsh 里 `$a` 不分词、无匹配 glob 会中断 `&&` 链（两次伪红）；机器磁盘 <1G 时全量 pytest 会被 OOM 杀（83% 处），起跑前看 `df` 与 pytest 进程数；磁盘清理会连带删 `.code-review-graph/` 两个已跟踪文件，跑门禁前 `git status` 再看一眼。
