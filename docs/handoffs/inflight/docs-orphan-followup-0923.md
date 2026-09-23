# docs/orphan-followup-0923 · 盘点遗留四件事：代拍五问三合同 + #874 接手 + #868 不合 + 工单 #62/#66/#68 派工

## 这个分支做什么
收口 09-23 盘点第三节「停在拍板」的事：决策记录 `docs/handoffs/2026-09-23-market-recovery-decisions.md`；INDEX #62/#66/#68 改进行中、#73 改有 owner。

## 决策与被否方案
- 五问三合同由本会话受托代拍（用户「这些你来做」），逐条带依据；否了「等用户逐题给字母」。1=B→D、2=A、3=A；a 按 5565、b NULL、c frozen_identity、d 缺行+仲裁、e 停采。
- #874 接手合入（持有 Pi 会话 17:43 起不动它，生产 3b7e47357 不含）；否了 SendMessage（Pi 终端到不了）、否了只留言等它（它只在用户敲字时动）。
- #868 不合（自述未达条件、head 无收据、L6 未过）；否了跑联合树硬合。
- #73 不接（协调者 Pi 会话在跑新候选 7ec9d022b，用户已选 B）；否了重复推分支 / 开 PR。
- 全量门禁串行、按 load1<12 且 pytest≤2 准入；否了子代理各跑全量（机器 load 56–110、5 套 pytest 并跑）。

## 当前状态
- PR 评论已落：#861 6463、#871 6468、#874 6470；#868 首次 POST 客户端超时未落，重贴中。
- 预览树（main 626d8a508 + #871 + #861 + #874 + 本枝）在 `~/fwp-preview-orphan2-0923`，tip 见 `~/.finance-runtime/reviews/orphan-followup-0923/preview-tip.txt`；python 叶排队（`python-gate.log`），frontend/e2e 叶随后。
- 合并脚本同目录 `run-merge-batch.sh batch`（871→861→874），本枝 PR 用 `one`。
- 三个子代理：#66 `fix/financial-ttl-baseline-fwd-0923` + 量具前向；#68 `fix/history-completion-fwd-0923`；#62 前向 #844 + 启动器补丁草稿（不应用）。

## 已验证
四枝对 main merge-tree clean；预览树 dirty=0、非 docs 22 文件、webapp 0 文件；#874 修复不在 8792（is-ancestor 否）。

## 未验证 / 已知边界
预览树四叶未出；子代理定向读数未回；#868 评论待回读。合同 1=B 对 #871 桥的名称回填是合入后跟进项。工单 PR 的合入按各工单原文等用户确认。

## 下一步
1. `python-gate.log` 出 `GATE_EXIT=0` 且 `frontend-e2e.log` 各 exit=0 → 读数贴 PR → `run-merge-batch.sh batch` → `one <本枝PR> docs/orphan-followup-0923 <head12>`。
2. 子代理 PR 各自四叶（预览树串行）→ 用户确认后合入。
3. 合完删 `fwp-preview-orphan2-0923` 与本树。

## 踩过的坑
Gitea API 在 load>50 时 POST 30s 客户端超时但服务端已落（评论 / 开 PR 都会），重试前先回读；用户级 hook 把命令里的「pushed」也当 push 拦，避开 push 与 main 同句。
