---
name: handoff
metadata:
  pattern: workflow
description: 会话收尾时把当前分支在途状态回写成交接文档（docs/handoffs/inflight/<分支>.md）。触发词：handoff、交接、写交接、回写 handoff、收尾交接、交给下一个 agent、另一个 agent 接手。你说"handoff"就执行本流程，不用等会话结束。
---

# 回写交接（handoff）

用户说 **handoff** / **交接** / **交给下一个 agent** 时，立即把当前分支的**在途状态**写进
`docs/handoffs/inflight/<当前分支，/ 换 ->.md`。这是 inflight 活文档的**写侧入口**——
读侧由 `scripts/session_facts.sh` 在每次 SessionStart 自动注入（前 12 行），
下一个 agent 一开工就能看到你的交接，不需要你额外提醒。

## 为什么是"在途状态"而不是"完工报告"

inflight 文档是给**接手干活的 agent** 读的，不是给事后追溯的人看的。它要回答的是
「我现在卡在哪、你接着往下做要踩什么」，不是「我做完了什么」。

- 写完就改 `## 当前状态`：改了什么、**还没改什么**、哪些已验证、哪些**没验证**。
- 分支**没完成**的卡点、下一步、踩过的坑，比"已完成"更值钱——接手者真正需要的是这些。
- 做完的、合并的、归档的事，从 inflight 里**删掉**，转成 `docs/handoffs/YYYY-MM-DD-*.md` 日期快照。

## 执行步骤

1. **定位文件**：`docs/handoffs/inflight/<当前分支名，/ 换 ->.md`。不存在就新建（用 `docs/handoffs/inflight/` 下任一现有文件作模板）。
2. **核对真实状态**（不凭记忆）：
   - `git branch --show-current` — 当前分支
   - `git status --porcelain` — 未提交改动，**逐条认领**：哪些是你改的、哪些是别人/ingest 产物
   - `git log --oneline -3` — 最近提交
3. **覆写**文档，只留五节：
   - `## 这个分支做什么` — 一句话目标
   - `## 当前状态` — 已提交 / 未提交 / 卡在哪（**写完就改，别让文档说过期的话**）
   - `## 已验证` — 你实际跑过的检查
   - `## 未验证 / 已知边界` — 没跑的测试、可疑点、环境限制
   - `## 下一步` — 接手者接着做什么
   - `## 踩过的坑` — 本分支特有的坑（可迁移的提炼进 `10_knowledge/`）
   ≤3K 字节（SessionStart 只注入前 12 行，超出会被截断）。
4. **提交**：`git add -- <该文件>` → `git commit`（禁 `git add .`，本仓多 agent 共索引）。
   如果分支有未提交代码改动且你不想提交它们，文档单独提交即可——它本来就该是**最新**的。

## 红线

- **不写密钥 / token / 密码**（PAT、CC_REMOTE_EXEC_TOKEN 等一律不进交接）。
- **不贴整段代码 diff** —— 记结论和决策，代码看 commit/PR。
- **不删别的 agent 的交接记录**；inflight 只覆写**你自己分支**的那份。
- **在动作完成之后写**——先写"未提交"再去提交，文档当场失效（2026-08-11 实测踩过）。

## 与项目笔记「交接记录」的分工

| | inflight/<分支>.md（本 skill 写） | 项目笔记「交接记录」 |
|---|---|---|
| 定位 | 在途状态 / 接手手册 | 一行索引 / 时间线 |
| 长度 | ≤3K，写完即覆写 | **一行**（日期·agent·做了什么·指向） |
| 谁读 | 接手 agent（SessionStart 自动注入） | 人翻历史、跨 agent 对账 |
| 提交 | 独立 commit，随时可写 | 完工后随其他回写一起 |

项目笔记那一行在 `devin-writeback.md` 里写，本 skill 只负责 inflight 正文。
