# 在途交接 · feat/content-ops-copilot

## 这个分支做什么
核验 FOMO/Devin 两个 managed-instruction 槽位的持久化、备份、审计脱敏与运行时边界。

## 决策与被否方案
- 采用只读文件/进程核验；不重启服务、不改配置，避免把“等待下次启动/重载”误变成运行时动作。
- 以 `~/.fomo-flow/配置.json` 和实际监听端口为准；不以历史 handoff 或旧测试收据代替当前状态。

## 当前状态
外部配置核验完成，未改配置。当前分支原有大量他人/数据产物未跟踪文件，本轮未触碰、未暂存。仓库测试收据未重跑全量：现有收据不适用于当前 revision/脏状态。

## 已验证
- `配置.json` JSON 可解析；两个槽位分别为 `devin-glm-leila-v1`=`glm/glm-5.3-flash`、`devin-grok-leila-v1`=`grok-session/grok-4.6`。
- 两个正文均 6342 字符，SHA-256 均为 `97e2791cfa4558702bd051ee53662dec97feda50fe0016a84a8c0aff27adcfb0`。
- 2026-09-04 自动备份 10 份均可解析，均与当前配置逐字节一致。
- `.action-audit.jsonl` 854/854 行可解析；两个 `hotUpsertManagedInstruction` 成功记录仅有摘要字段，未含正文/预期正文哈希。请求历史未发现正文或正文哈希。
- 8955（Devin）和 18765（Python）监听；8889、11435 均未监听，HTTP 探测不可达。
- `.venv-workbench/bin/python scripts/check_test_receipt.py`：旧收据 `passed=9 failed=3` 不可采信，原因是 receipt revision `ebfe0864` != 当前 `f9664a4c`，且收据标记代码路径 dirty。

## 未验证 / 已知边界
- 尚未验证下一次 FOMO/Devin 启动或热重载后的真实请求是否加载新槽位；目标运行时当前不存在。
- 未读取或输出正文、凭据、请求体；未做 live 上游调用，因此不下模型可用性结论。
- 未在混杂他人产物的主树运行全量测试；如需当前 revision 收据，应使用干净 worktree 重跑。

## 下一步
下次 FOMO/Devin 路由进程启动或重载后，检查实际请求的 provider/model 与槽位 ID；继续保持审计只落摘要。若要仓库门禁结论，从当前 revision 建干净树后使用指定 venv 重跑收据。

## 踩过的坑
旧测试收据的解释器/依赖一致，不代表 revision 和脏状态一致；必须先跑 `check_test_receipt.py`。配置备份存在不等于运行时已加载，端口/真实请求才是运行时证据。
