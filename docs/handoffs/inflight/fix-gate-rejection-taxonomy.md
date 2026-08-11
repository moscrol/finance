# 在途交接 · fix/gate-rejection-taxonomy
更新：2026-08-11 · Claude Code

## 这个分支做什么
为 `validate_episode_finish` 添加 `RejectionKind`（FORMAT / SUBSTANCE / INTEGRITY）分类层，
让 INTEGRITY 错误（伪造证据哈希）直接拒绝不重试，FORMAT/SUBSTANCE 保留原有重试逻辑。
同期做环境可靠性修缮：注入收窄、解释器门禁、路径门禁、依赖锁文件、**在途交接机制**。

## 当前状态
**全部已提交，工作区无本分支相关的未提交改动。** 分支未合 main、未推送。

| commit | 内容 |
|---|---|
| `715fc5bd` | 新增 handoff skill（说"handoff/交接"即触发回写本文件） |
| `dd77c316` | 尾部预留改为实测（手写 1000 实际 986） |
| `fc19bc47` | 在途交接改为提交后更新（文档时序 bug） |
| `86b11a55` | 记忆注入收窄 189K→11K + 在途交接机制 |
| `399d29e6` | SessionStart 投递工作区事实（Devin/Claude 共用） |

agent-memory 仓已落库：`80aa8cf4`（交接记录一行索引）、`d83bb323`（devin-writeback 新约定）、
`7b5b2673`（`10_knowledge/evidence-hygiene-three-failure-shapes.md`）。

## 已验证
- `bash .claude/hooks/load-memory.sh` → 退出码 0、约 11.5K 字节（预算 12,000）、四段齐全、UTF-8 合法
- `bash scripts/session_facts.sh` → JSON 合法、六段事实齐全、984 字符（预算 2,000）
- 变异验证：正常命中 / 本分支无 inflight / inflight 超预算 32KB → 均退出码 0、JSON 合法、截断有声明
- handoff skill：`skill search handoff` 可发现，来源指向 `.claude/skills/handoff/SKILL.md`
- registry 确定性：排除 `generated_at` 时间戳后重跑无 diff
- pre-commit 门禁（密钥、大文件、工作区事实、层级审计、路径字面量）全过

## 未验证 / 已知边界
- **本轮没跑 pytest**。测试读数一律看 `~/.finance-runtime/test-receipts/latest.json`，
  先跑 `scripts/check_test_receipt.py` 确认收据条件是否与当前 HEAD 一致，不一致就重跑。
- 这棵树（主检出树）有大量他人未提交改动（forecast-review-ledger、moneyflow、
  daily-full-review 等）。**不要在这棵树跑全量测试对账**——那个退出码不对你的 revision 成立。
- 分支未合 main（按约定等用户确认）。

## 下一步
分支本身的任务已完成并提交。若要继续：
1. 合 main 前需用户确认
2. handoff skill 是新入口——用户说"handoff/交接"即触发回写本文件，
   其他 agent 收尾时用它即可，不必再手写格式

## 踩过的坑（本轮特有，都是「静默失真」形状）
- `head -c` 按字节切中文 → 非法 UTF-8 → `grep/rg/cut` 把输出当二进制 →
  **量具被自己污染的输出骗了**，此后每次测量都指向错误方向，连续误判 5 次根因
- shell 字符串末尾 `Read $note。**` → shell 试图展开 `$note。**` → `line 107: note`
  → 脚本**提前终止**，后面两段一个字没输出，而前面 8K 已正常输出，看着只像「少了两段」
- BSD awk（macOS 自带）不支持 `[0-9]{4}` 区间量词 → 退出码 2 → `section` 为空 →
  项目笔记一个字没注入，而总字节数看起来正常
- 笔记标题实际是 `## 任**务**看**板**`（中文字符间夹 markdown 粗体）→ `/任务看板/` 匹配不上
  → 折叠静默不生效，字节数一字不变。`od -c` 才看得出
- **本文件自己也犯过一次**：先写"未提交"再提交，提交动作让文档当场失效。
  活文档必须在动作**之后**更新，否则注入给接手者的是假状态。
