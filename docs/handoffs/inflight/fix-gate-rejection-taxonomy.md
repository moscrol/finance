# 在途交接 · fix/gate-rejection-taxonomy
更新：2026-08-11 · Claude（接手会话，hook 修缮）

## 这个分支做什么
为 `validate_episode_finish` 添加 `RejectionKind`（FORMAT / SUBSTANCE / INTEGRITY）分类层，
INTEGRITY（伪造证据哈希）直接拒绝不重试，FORMAT/SUBSTANCE 保留原重试逻辑。
同期做环境可靠性修缮：注入收窄、解释器门禁、路径门禁、依赖锁文件、在途交接机制。

## 当前状态
**本分支相关改动全部已提交。** 分支未合 main、未推送（合并需用户确认）。
提交（新→旧）：`5ac9b9d5` stale 门禁排除交接文档自身提交（消除自噬）·
`3418f7e2` 回写交接 · `9d0b5f17` stale 门禁改归属判定 + 注入保住风险面 ·
`48f2b168` hook 命令改绝对路径 + 仓根哨兵校验 · `0295542d` AGENTS.md 外部知识源 ·
`7a0f2afe` handoff 回写 · `22a49d6e` handoff 挂 .agents/skills · `2ff47db8` SessionEnd 写侧门禁 ·
`48bae647` 演练 handoff · `715fc5bd` 新增 handoff skill · 更早见 git log。

⚠ **工作区里另有 5 个不属于本分支的脏文件**（`scripts/moneyflow/*`、
`check_daily_review_data.py`、`trading_days.py`、`verify_l2_recovery_artifacts.py`）——
本分支所有提交一次都没碰过它们，是共树下别人的活。**别把它们一起提交、别 stash。**

## 未验证 / 已知边界
- **本轮没跑 pytest**。测试读数看 `~/.finance-runtime/test-receipts/latest.json`，
  先 `scripts/check_test_receipt.py` 核对收据条件再决定重跑。
- 主检出树混着他人未提交改动，**别在这棵树跑全量测试对账**（退出码不对你的 revision 成立）。
- SessionEnd hook 在真实会话的**触发时机**仍未实测（本轮只直接调脚本验证逻辑，
  没验 harness 何时真正调它）。
- 注入预算实测溢出到 ~2069 字符（BUDGET=2000）：组装循环是「先判超限、再追加声明」，
  声明本身不计预算。溢出约 3%，暂按可接受处理，未改。
- 交接记录 164K 历史未动（红线：不删别人记录）；历史处理（摘要化/门禁）待用户定。

## 下一步
1. 合 main 前需用户确认
2. 下个会话验证一次 SessionEnd hook 真实触发时机
3. 交接历史 164K 的处理方式等用户决定
4. 可选：BUDGET=2000 是否上调（现在风险面进来了，代价是「已验证」段常被砍）

## 踩过的坑（都属「静默失真」）
- **mtime ≠ 版本控制归属**：stale 门禁拿文件系统事实推断分支归属，共树下必然误报。
  更阴的是它这次**结论对、理由全错**（真实原因是分支又提交了 2 次，它却在看不相干的
  moneyflow 脏文件，两者 mtime 只差 2 秒）。验门禁要查它引用的证据，不能只看结论。
- **macOS 的 `sort`/`uniq` 在 UTF-8 locale 下会把不同的中文行判为相等**（CJK collation
  主权重相同）：6 个不同小节被 `uniq -c` 合成 1 个、计数报 5。中文文本统计一律 `LC_ALL=C`。
- **awk 未初始化变量作数组下标是空串不是 0**：`body[sec]` 写进 `body[""]`，
  END 里读 `body["0"]` → 没有 `## ` 小节的文档注入全空、退出码 0。要 `BEGIN{sec=0}`。
- **门禁自噬**：一级判据「提交晚于交接文档」上线后，写完交接去提交，这个提交本身就比
  文档 mtime 新 → 当场又报警，写了也没用。修法是把「只动交接文档的提交」排除掉。
  可迁移：**任何「产物必须跟上源」的门禁，都要把「更新产物」这个动作排除在「源变动」之外**
  （同类：lint 自动修复触发 lint、changelog 门禁、格式化 hook）。
- **限定语必须先于被限定内容到达**：stale 告警原本排在交接正文之后，正文一变长就把它
  挤出预算——「限定语没了、正文还在」比两者都不注入更坏。
- `head -c` 按字节切中文 → 非法 UTF-8 → grep/rg/cut 全把输出当二进制
- 笔记标题 `## 任**务**看**板**` 夹粗体 → `/任务看板/` 匹配不上 → 折叠静默失效
- 活文档先写"未提交"再提交 → 提交动作让文档当场失效。**必须在动作之后写**
- Codex：`.codex/skills` 是 legacy 路径，现行标准 `.agents/skills`，装完要软链否则白装

## 已验证
- load-memory.sh：退出码 0、约 11.5K 字节（预算 12,000）、四段齐全、UTF-8 合法
- session_facts.sh：JSON 合法、六段齐全、注入 2069 字符
- stale 门禁变异四况：旧报警/新静默的 A/B 对照、一级判据独立触发、降级声明、真实状态
- 注入回退三况：无 `##` 小节 / 陌生英文词表 / 真实文档，均不出空且保住标题行
- handoff：`skill search` 可发现、`skill invoke` 可执行
- Codex：28 个新装 skill 软链 ~/.agents/skills，0 断链
- pre-commit 8 道门禁全过（4 次提交实测）
- 门禁收敛闭环：交接跟上后 stale 转静默、交接落后时重新报警（双向都验过）
