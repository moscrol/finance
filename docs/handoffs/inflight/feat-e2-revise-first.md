# feat/e2-revise-first

## 这个分支做什么
轨道 C / E2：continuous 编排器「修订版在前，审查意见进输出质检附录」。不换 `output_review` 6 项，不做附录 A.1 ②③。

## 当前状态
从 `gitea/main@c163ca7b` 新开。主仓脏树未碰。尚未实现、未 live。

## 未验证 / 已知边界
- sidecar live 未跑。生产 8792 不切。
- W3 也改 `conversation_orchestrator`；后合方 rebase。

## 下一步
1. TDD：Engine A 附录；Engine B `compose_revise_on_warn=True` + 合成后回灌。
2. sidecar 一发 WARN 题（会话口，不是预测题）。
3. 读数 + 用户确认后才合。

## 踩过的坑
- 真跟踪/研究题走 `_complete_continuous_turn`，只翻 ask 的 flag 验不到生产路径。
- `live_probe ask` 没有 `theme_track`；会话口用 `POST /api/conversations`。
