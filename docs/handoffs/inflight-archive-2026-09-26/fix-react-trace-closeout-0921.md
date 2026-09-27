# ReAct trace 最小修复

## 这个分支做什么
在 PR #809 上维护 ReAct trace 工程修复，并修补真实历史研究分页的原件行身份；不是 #790-#794 全完成。
2026-09-21 本轮新增第六项修复（条件计数接缝）并完成前向合并，PR 已出 WIP。

## 决策与被否方案
- 条件一致性：只在本轮确实删掉升级/降级定义时清理悬空“满足条件中的 N 条”，保留观察；不放宽数字门、不重写整段。
- 历史分页：`sample` 使用不可变原件的绝对行号，并返回 `offset/next_offset`；不按页重置、不把分页卡数当完整分母。
- 否决自动补绑未引用数字、全局改 ranking_intent、重发同题自然 run；这些会混淆证据绑定、题型合同和质量验收。
- **孤儿 WIP 不并进本 PR**：工作树里那片 #793/#794 历史证据绑定（9 文件约 300 行 + 265 行新测试）
  已封存为独立分支 `feat/history-evidence-binding-0921` @ `9fabd688f`，本分支树随后清空。
  理由是本分支的审查范围守在六项最小修复上；那片改动未复核、无收据、无归属。
  封存前逐文件 `cmp` 过字节一致，自带 4 条测试在封存树里通过。
- 前向合并两处冲突按双方意图解，不二选一（见下）。
- 合 main 仍需用户确认；不部署 8792、不新增付费外审、不删生产原件。
- 背景见 `docs/handoffs/2026-09-21-condition-coherence-repair.md`、`docs/handoffs/2026-09-21-history-page-identity.md`。

## 当前状态
HEAD `f53004a57640b570107fb3cb7a23d207cf58c84c`，已推送 `gitea/fix/react-trace-closeout-0921`，树 clean。
PR #809 open，标题已去 WIP，**10 ahead / 0 behind**，净 diff 63 文件（13 代码 + 50 文档）+2681/−20。
生产 8792 仍 `bf662e93`。PR #818（kb/rag-query 注册表重扫）已合入 main，本分支已含。

## 已验证
- 全量 pytest @ 准确 SHA `f53004a57`：**12519 passed / 0 failed / 0 error / 85 skipped**；
  收据 `/Users/a77/.finance-runtime/test-receipts/20260921T075402Z-f53004a5.json`，
  `dirty:false`、revision 精确匹配、未绕依赖门。
- `ruff check .` 通过；pre-commit 11–12 道全通过；registry 四道全部 exit 0。
- 接缝修复先红后绿：六种真实句式的探针在 `99c607671` 上 **6 红**、在 `f53004a57` 上 **6 绿**。
  包括最普通的中段形式——`0729692a4` 会把「该股放量上攻，满足升级条件中的2条，值得跟踪。」
  变成「该股放量上攻，，值得跟踪。」，所以那不是边界问题，主路径就坏。
- 变异测试：拆掉五个机制中的任意一个，红集与预测**逐一吻合**，无一个机制「红零条」。
- 证据归档 `docs/verification/2026-09-21-condition-seam-repair/`（探针 + 变异脚本 + 前后日志 +
  收据 + SHA256SUMS，可独立复算）。
- `3765af67b` 的 `next_offset` 算术复核过：`query.py:665` 把 `total_matched` 设为 `len(rows)`，
  所以它不会指向一个空页。

## 未验证 / 已知边界
- **K3 独立复核是阻塞，不是「无发现」**：`pi auth check --provider mirasim-kimi` 报 ready，
  但同一条 20 分钟前成功的最小探针随后持续超时，900 秒的正式复核输出 0 字节。
  输入与调用都没变，变的是 provider。下一个 agent 要重跑，别把空输出当通过。
- 真实金融质量仍 `not_passed`：未绑定 225/25、AI手机PC/MiniLED 数值及相关定性仍需 #794；
  `ranking_intent=false`、#793 比较合同/假设槽未完成。
- 未跑自然模型验收。要证明修复路径真的触发，得看 `sentence_verdicts` 与 binding 事件，
  不是重发同题求绿。
- 前端 / e2e 叶子未跑：本 PR 改动 0 个前端文件，该工作树无 `node_modules`，新树上跑只会得到
  「无结论」。main 自身结果仍成立。

## 下一步
1. 等用户确认后合 #809。
2. `feat/history-evidence-binding-0921` 单独走复核与门禁，别整包塞回 #809。
3. provider 恢复后补 K3 独立复核（输入已备：`git show 3765af67b` + `git show 1b8707c94`）。
4. 继续 #793 比较合同/假设槽与 #794 历史结果证据绑定。

## 踩过的坑
- **贴来的总结会落后于分支尖，也会落后于 main。** 本轮开工时 main 是 `728f32716`，干到一半变成
  `adcda94b5`（别人合了 #825/#826），分支从「0 behind」变成「106 behind」，
  `git diff` 一度显示 12388 行删除——那是拿陈旧分支对移动后的 main 比出来的假象。
  下判断前重测 `merge-base` / ahead / behind，别信十分钟前的读数。
- **收据别读 `latest.json`**：多棵树并发时它会被别人覆盖。本轮 `check_test_receipt.py` 读到的是
  另一棵树的 `d5d212a1` 并据此报「需重跑」，而真正对应的时间戳收据就在同一目录。按 revision 取。
- **zsh 不做单词拆分**：`for f in $FILES` 会把整串换行连起来的文件名当成一个路径，
  `cp`/`cmp` 报 "No such file or directory" 却像是文件真的不存在。用 `while IFS= read -r`。
- **`$?` 要在任何别的命令之前存下来**：`cmd | tail -6` 之后的 `$?` 是 `tail` 的退出码，
  四道 registry 检查一度全报 0，其中一道其实是 1。
- **金标样本会编码缺陷**：`0729692a4` 自带两条测试并且通过，因为它测的形状正好是唯一被处理对的
  那个。拿产物自己的「好样本」量产物，量不出来；要另铺一组它没想过的形状。
