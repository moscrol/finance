# fix/instruction-gate-clearance

## 这个分支做什么
把冻结的指令迁移与四项清障组成一个可验证候选，再叠上质检复核提出的两项修复。
基线是 `gitea/main`。**领先/落后计数不写进本文**：它每次变基就漂，且上一版把自身那条
提交漏算成「领先 6」（实为 7）。要数就现算，基线 SHA 与矩阵指针见「当前状态」。

## 决策与被否方案
- 沙箱清障（源 6d709cfd）：取真实宿主解释器、记录失败输出；权限与四项 denied 不变，只新增「探针非零退出不得记为 proven」。
- 台账清障（源 7d193f1c）：恢复原行与两份历史依据，去横幅后与 `82439bca` 逐字节相同；编号与 pending 不变。
- **三个技能的删除已撤出**（公司画像页 / 潜意识模式 / 行业概览）。撤出而非事后补理由：git 历史里唯一删除它们的提交就是迁移本体，`docs/handoffs/`（在途+归档）、`docs/superpowers/`、`lessons_learned.md`、`~/agent-memory/` 全部 0 命中。图谱未登记、无悬空引用只说明「删了不会立刻报错」，不作退役依据。表格触发词按基线原文还原。
- **公共联网入口恢复为 AGENTS.md 全局指令**。原规则未全文丢失（`runtime-and-pitfalls.md:21` 仍有），但从强制条款降级成了数据源参考；AGENTS.md 自称五个 harness 的唯一指令源，故在三个正门后恢复短指令 + 仓外规范源路径。两处并存。
- 变基重写了本分支 6 个 SHA；冻结件 `b2d40776` 由 `feat/instruction-migration-agents-md` 独立持有，对象原样可达。忠实性已验：相对各自 base 的总 diff 逐字节相同、6 个 patch-id 两两相同。
- **Codex 钩子选根顺序改为「cwd 的 git 仓根优先、环境变量其次」**，与 `.devin/config.json` 的 `_why_portable_hooks` 对齐。原顺序把 `CODEX_PROJECT_DIR` 排第一：sentinel 只问「该目录下有没有被委托脚本」，另一棵有效项目树完全满足它，于是继承来的变量赢过当前树，注入别人的分支且 exit 0。实测在本树启动、变量指 `agroup-build/finance-workspace-private`，注入的是 `feat/instruction-migration-agents-md`。
- **`build_registry.py` 的「仓名 → 仓根」收到单一入口 `_repo_dir()`**，本树那个名字恒解析成 `REPO_ROOT`。原来五处直写 `REPOS_DIR / name`，在附属 worktree 里全部指向主检出树——**写入侧 `backfill-tables` 会去改另一棵树的 `AGENTS.md`**，比读错更糟。守卫判据走 AST 而非文本扫描（注释里提到这个写法是正当的）。
- **`scan` 对「某仓条目整段消失」改为 fail closed**（逃生口 `--allow-missing-repos`）。`check` 早就对缺仓做子集比对，写入侧不能比校验侧松：在只 checkout 单仓的树里跑一次 `scan` 就能抹掉另外两仓全部 skill，退出码照样 0、diff 看起来像正常刷新。

## 当前状态
未推送、未开 PR、未合入。最终 SHA、命令、退出码与日志索引：
`~/.finance-runtime/gates/instruction-clearance-r3-20260912/matrix.md`（r2 那份留作对照，
它的基线是已被超越的 `694584df`，且 registry ② 的 exit 0 不承重——原因见 r3 矩阵同名小节）。
**可否合并以该文件为准，本文不作全绿声明。**

## 已知边界
- **注册表此前只在「树不完整」时才是绿的。** `cmd_check` 仅在三仓全在场时比对 `repos` 字段，而门禁检出树没有同级仓 → 该字段被跳过。committed 里 `finance-research-site.present` 记着 `false`（在某个没有同级仓的位置扫出来的），于是完整检出树里 `check` 是 exit 1，门禁树里是 exit 0。已在完整树重扫改回 `true`；两种树形现在都绿，但**这个字段本质上记录的是扫描时的本地磁盘状态**，跨机器仍可能漂，是后续该拆掉的设计。
- `generate-views --check` **检测不到缺失的视图软链**（标定：删软链仍 exit 0），它只校验已存在条目是否规范。视图存在性要从提交对象取证（mode=120000 + 目标可达）。
- watchdog（`test_conversation_orchestrator.py:6274`，注入阻塞函数 + 线程事件）间歇根因未定论，全量绿不等于已修，沙箱探针新字段与它无关。历史性能工单仍 pending。

## 踩过的坑
`FWP_TEST_RECEIPT_DIR` 只被 `run_main_gate.sh` 读、写入方不认，收据仍落默认目录并覆写 `latest.json`——按 revision 取时间戳收据。`run_main_gate.sh:82` 缺收据的诊断在 bash 3.2 下自身崩溃（`$LATEST` 紧跟全角括号被吞进变量名），表现为 ruff/pytest 全绿而脚本退出码 1。zsh 不对未加引号的变量展开分词，`for s in "a --check"` 整串喂给 argparse 得假红。
判一个新测试有没有洞，最干净的做法是**让它在缺陷在场时跑一遍**：本轮两个新判据都先在修前代码上验证为红（钩子那条的失败输出恰好就是生产里那种「看起来正常、只是属于另一棵树」的形状），再修。
