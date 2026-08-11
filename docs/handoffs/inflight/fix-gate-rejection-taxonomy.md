# 在途交接 · fix/gate-rejection-taxonomy
更新：2026-08-11 · Claude Code

## 这个分支做什么
为 `validate_episode_finish` 添加 `RejectionKind`（FORMAT / SUBSTANCE / INTEGRITY）分类层，
让 INTEGRITY 错误（伪造证据哈希）直接拒绝不重试，FORMAT/SUBSTANCE 保留原有重试逻辑。
同期做了环境可靠性修缮（解释器门禁、SessionStart 注入、路径门禁、依赖锁文件）。

## 当前状态
**代码改动已全部提交**（最新 commit `399d29e6`）。本轮只剩配置/工具改动未提交（见下）。

## 未提交改动（接手前必看）
| 文件 | 性质 | 说明 |
|------|------|------|
| `.claude/hooks/load-memory.sh` | 修缮 | 收窄注入：189K→12K 字节；修 `head -c` 非法 UTF-8、`$note。**` 终止脚本两处 bug |
| `scripts/session_facts.sh` | 新增 | 加 §6 在途交接注入逻辑（当前分支 inflight 文件） |
| `docs/handoffs/inflight/fix-gate-rejection-taxonomy.md` | 新增 | 本文件 |
| `~/agent-memory/40_playbooks/devin-writeback.md` | 修缮 | 交接记录改为一行索引 + 新增 inflight 规范 |
| `~/agent-memory/10_knowledge/evidence-hygiene-three-failure-shapes.md` | 新增 | 三个失败形状沉淀 |

## 已验证
- `bash .claude/hooks/load-memory.sh` → 退出码 0，11,264 字节（≤12,000），四段齐全，UTF-8 合法
- `bash -n scripts/session_facts.sh` → 语法 ✓
- 变异验证 3 种情况：正常命中 / 无 inflight 文件 / 超预算截断，JSON 均合法、退出码 0
- 测试套件最近读数：见 `~/.finance-runtime/test-receipts/latest.json`（跑 `scripts/check_test_receipt.py` 确认是否与 HEAD 一致）

## 未验证 / 遗留
- 上面表格里的文件**都还没提交**
- `~/agent-memory/` 两个文件需要推到 `linxiaoqi5111-del/agent-memory` 仓的 `main`

## 下一步（接手者）
1. 把表格里的文件按 pathspec 提交（`git commit -- <明确文件列表>`，**禁 `git add .`**）
2. 推 agent-memory 两个文件到 vault 仓
3. 更新 `~/agent-memory/20_projects/finance-workspace-private.md` 交接记录（一行）

## 踩过的坑（本轮特有）
- `head -c` 按字节切中文 → 非法 UTF-8 → `grep/rg/cut` 把输出当二进制 → **量具被污染的输出骗了自己**，此后每次测量都指向错误方向，连续误判 5 次根因
- shell 字符串末尾 `$note。**` → shell 把 `**` 当变量展开 → `line 107: note` → 脚本提前终止，后续两段没输出
- BSD awk 不支持 `[0-9]{4}` 区间量词 → 退出码 2 → 静默失真（section 为空而字节数看起来正常）
- 笔记标题 `## 任**务**看**板**` 含 markdown 粗体标记 → `/任务看板/` 匹配不上 → 折叠静默不生效
