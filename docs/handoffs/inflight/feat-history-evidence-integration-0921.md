# 历史来源绑定与缓存授权 · WIP #841

## 这个分支做什么
接替#829，基于#832；完成历史证据来源绑定、缓存授权加固及固定版本工程验收，当前补做独立审查收口。

## 决策与被否方案
缓存非授权：同run锁内重载、重授权、校验后仅读一次；refresh替换集合并保旧错误合同。否中断日志/作者回归代独立签字，否自动重试/加购/重开旧K3。审查壳不能用外层here-doc或嵌套sandbox；先修设施再重跑，不为终稿放宽隔离。

## 当前状态
业务头仍`f73d2133968d51d3c782d3e12ee9aa4d0618ef45`；本分支头`fedce252330dce1065238f58e6c914417219ec53`，之后仅文档。当前新增未提交归档`docs/verification/2026-09-22-history-k3-access/`及本交接/日期快照，待校验提交。详情见`docs/handoffs/2026-09-22-history-k3-access.md`。

## 已验证
- Spec/Quality各一次：固定fedce，1.338s/1.466s，exit70，模型请求0，无终稿；均`BLOCKED_BOOTSTRAP_NO_MODEL_DISPATCH`，原件保留。
- `/usr/bin/true`替身保留原shell resolver，复现相同here-doc临时文件错误哈希；指定TMPDIR仍失败。直接Python正文SQLite/HTTP四分支夹具通过，不等于真实修复。
- 外层controller嵌tools sandbox的echo exit71（`sandbox_apply: Operation not permitted`），不再盲重跑。
- fedce定向599 passed、0 failed/error/skipped；收据`20260921T180311Z-fedce252.json`精确checker exit0。作者回归不代独立签字。
- 候选/作者树首尾稳定；无自然金融探针、生产配置/服务/业务代码改动。

## 未验证 / 已知边界
无独立终稿；自然金融仍`not_passed`，225/25分母、自然数字引用、判官消费未验。生产写手/判官模型须真实运行收据，旧注释不算。main tip组合、#793/#794、#833/#845联合树未验。claims未签名验证；hash只证明字节。本轮定向磁盘最低31.25GB；下次重新采样，原全量6GiB线不变。

## 下一步
1. 提交归档后用`check_evidence_archive.py`按归档提交校验；599收据仍绑定fedce，不移签。
2. 修审查设施：凭证初始化去掉受限shell here-doc；工具隔离改为可验证单层策略；补完整终稿收口和请求收据。先做无网络离线验证，不能只改草稿后跑模型。
3. 获明确授权后，以新目录/准确SHA各启动一次有界独立审查；终稿缺失仍BLOCKED。通过后才冻结自然题、写手/判官、provider硬上限和服务端墙钟。
4. 最后验实际main组合；合入/部署另获确认。不切生产写手、不接管或关闭其他PR。

## 踩过的坑
个人Codex宿主软链恢复读取，但Codex额度中断仍无终稿；不要混称K3不可用。controller允许默认但禁写，不能据此断言禁网。`workbench_probe --timeout`只等客户端，不取消服务端。失败后改过Spec草稿，已与执行原件分包；旧包不可改。
