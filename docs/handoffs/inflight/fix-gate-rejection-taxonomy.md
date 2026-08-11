# 在途交接 · fix/gate-rejection-taxonomy
更新：2026-08-11 · Devin（handoff skill 触发）

## 这个分支做什么
为 `validate_episode_finish` 添加 `RejectionKind`（FORMAT / SUBSTANCE / INTEGRITY）分类层，
INTEGRITY（伪造证据哈希）直接拒绝不重试，FORMAT/SUBSTANCE 保留原重试逻辑。
同期做环境可靠性修缮：注入收窄、解释器门禁、路径门禁、依赖锁文件、在途交接机制。

## 当前状态
**全部已提交，本分支相关工作区无未提交改动。** 分支未合 main、未推送。

提交（新→旧）：`22a49d6e` handoff 挂 .agents/skills · `2ff47db8` SessionEnd 写侧门禁 ·
`48bae647` 演练 handoff · `715fc5bd` 新增 handoff skill · `dd77c316` 尾部预留改实测 ·
`fc19bc47` 文档时序修复 · `86b11a55` 注入收窄 189K→11K + 交接机制 · `399d29e6` SessionStart 事实。

agent-memory 已落库：`80aa8cf4`（一行索引）、`d83bb323`（devin-writeback 新约定）、
`7b5b2673`（three-failure-shapes 知识沉淀）。

## 已验证
- load-memory.sh：退出码 0、约 11.5K 字节（预算 12,000）、四段齐全、UTF-8 合法
- session_facts.sh：JSON 合法、六段齐全、984 字符（预算 2,000）
- 变异三况全过（注入截断 / stale 门禁 / inflight 命中）
- handoff：`skill search` 可发现、`skill invoke` 可执行（本文件即产物）
- Codex：28 个新装 skill 软链 ~/.agents/skills，0 断链；Matt 版 handoff 改名 session-handoff
- pre-commit 五道门禁全过

## 未验证 / 已知边界
- **本轮没跑 pytest**。测试读数看 `~/.finance-runtime/test-receipts/latest.json`，
  先 `scripts/check_test_receipt.py` 核对收据条件再决定重跑。
- 主检出树混着他人未提交改动，**别在这棵树跑全量测试对账**（退出码不对你的 revision 成立）。
- SessionEnd hook 在真实会话的触发体验未验证（不同 harness 触发时机可能不同）。
- 交接记录 164K 历史未动（红线：不删别人记录）；历史处理（摘要化/门禁）待用户定。

## 下一步
1. 合 main 前需用户确认
2. 下个会话验证一次 SessionEnd hook 真实触发
3. 交接历史 164K 的处理方式等用户决定

## 踩过的坑（都属「静默失真」）
- `head -c` 按字节切中文 → 非法 UTF-8 → grep/rg/cut 全把输出当二进制 →
  量具被自己污染的输出骗了，连续误判 5 次根因
- `Read $note。**` → shell 试图展开 → `line 107: note` → 脚本提前终止，后两段没输出
- BSD awk 不支持 `[0-9]{4}` → 退出码 2 → section 空、笔记零注入而字节数正常
- 笔记标题 `## 任**务**看**板**` 夹粗体 → `/任务看板/` 匹配不上 → 折叠静默失效
- 活文档先写"未提交"再提交 → 提交动作让文档当场失效。**必须在动作之后写**
- Codex：`.codex/skills` 是 legacy 路径，现行标准 `.agents/skills`，装完要软链否则白装
