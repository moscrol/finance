# 行情恢复 QC 在途

## 这个分支做什么
修复并独立验证 #871/#861 的 F1/F2/F3；当前整体 HOLD，不是生产恢复批准。

## 决策与被否方案
| 选了什么 | 否了什么 / 原因 |
|---|---|
| 按较新授权改 GLM，复用智谱直连 | 不再等 K3；Pi 本地端口失败不等于所有 GLM 路线不可用 |
| 固定候选独审，主线漂移另账 | 不将旧报告或收据移签最新 main |
| 原 F3 报告保留，另出澄清版 | 不直接改 reviewer 原文；模拟/静态/动态证据强度不同 |
| 全仓红保持红 | 隔离 1P 不能覆盖完整 1F |
展开：`docs/handoffs/2026-09-23-market-recovery-glm.md`。

## 当前状态
业务修复已提交于 4fa70046f/981c4d629/3abb7a4d3；本轮只增证据和交接。
候选 `50330cf4f`，基座 `b59d6eed0`，ref `refs/verification/market-recovery-glm-b59-20260923`。
三项 GLM 报告已交付且均 PASS_WITH_LIMITS；F3 选澄清版。全仓 1F，零漂移检查也拒绝；收尾观察 main 已到 `e926157d9`。
本轮进程全部结束，候选和 refs 保留。无合并、推送、部署或生产写入。

## 已验证
最终报告对应探针 5/16/6P（F1 重用），作者 28/75/28P；新探针历史回退检出 31 个行为失败，零 API/收集错误。旧探针 20P 与旧回退独立列账。
完整 Python 14874P/1F/85S/2X，14962 collected；解释器/依赖/干净树/完整范围对账通过。Ruff、注册表、接入及交付门自测通过。390 个机器归档文件、417 个原件哈希已复核。
证据：`docs/verification/2026-09-23-market-recovery-glm/README.md`。

## 未验证 / 已知边界
全仓失败：`intelligence/tests/test_finance_query.py::test_timeout_interrupts_connection`，约 1.105s 超过 0.5s；单次隔离 1P，原因未证。
F1 无真实子进程/日志落盘；F2 只证最终 SQL 行，不证无中间写；F3 无双连接并发、完整输入指纹或部分写后回滚。无 frontend/E2E、真实 nightly、恢复 CLI、staging 或换库验收。
五问 (a)-(e)、三合同、5553/5565 和 53 只公司行动处置仍待确认。

## 下一步
先分诊耗时断言；需准入时重新组合当时最新 main 并跑完整门禁，不能移签本轮。业务拍板题见 `2026-09-22-market-recovery-decision-page.md`，未确认不进入生产。

## 踩过的坑
现有智谱路线见项目记忆 Runtime 必读段；Keychain 凭据只读内存，勿复制。Pi 简写配置与扩展注册对象不是同一合同。F3 最终报告是 `zhipu-v1/F3-report-clarified/`，不是原报告。旧 pytest-1830 收尾已不存在，删除者未证，别记作本轮主动清理。
