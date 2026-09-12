# fix/instruction-gate-clearance

## 这个分支做什么
把冻结的指令迁移与四项清障组成一个可验证候选。已变基到 `gitea/main`（694584df），0 落后 / 6 领先。

## 决策与被否方案
- 沙箱清障（源 6d709cfd）：取真实宿主解释器、记录失败输出；权限与四项 denied 不变，只新增「探针非零退出不得记为 proven」。
- 台账清障（源 7d193f1c）：恢复原行与两份历史依据，去横幅后与 `82439bca` 逐字节相同；编号与 pending 不变。
- **三个技能的删除已撤出**（公司画像页 / 潜意识模式 / 行业概览）。撤出而非事后补理由：git 历史里唯一删除它们的提交就是迁移本体，`docs/handoffs/`（在途+归档）、`docs/superpowers/`、`lessons_learned.md`、`~/agent-memory/` 全部 0 命中。图谱未登记、无悬空引用只说明「删了不会立刻报错」，不作退役依据。表格触发词按基线原文还原。
- **公共联网入口恢复为 AGENTS.md 全局指令**。原规则未全文丢失（`runtime-and-pitfalls.md:21` 仍有），但从强制条款降级成了数据源参考；AGENTS.md 自称五个 harness 的唯一指令源，故在三个正门后恢复短指令 + 仓外规范源路径。两处并存。
- 变基重写了本分支 6 个 SHA；冻结件 `b2d40776` 由 `feat/instruction-migration-agents-md` 独立持有，对象原样可达。忠实性已验：相对各自 base 的总 diff 逐字节相同、6 个 patch-id 两两相同。

## 当前状态
未推送、未开 PR、未合入。最终 SHA、命令、退出码与日志索引：
`~/.finance-runtime/gates/instruction-clearance-r2-20260912/matrix.md`。
**可否合并以该文件为准，本文不作全绿声明。**

## 已知边界
- 验证树必须是隔离父目录 + 真仓名（`~/.finance-runtime/gate-checkouts/<任务>/finance-workspace-private`）。`build_registry.py` 按仓名解析同级仓（`REPOS_DIR / name`），在 `~/fwp-wt-*` 里跑会解析到主检出树：实测 scan 漏收本树新增技能、反把主树脏 description 写进注册表。
- `generate-views --check` **检测不到缺失的视图软链**（标定：删软链仍 exit 0），它只校验已存在条目是否规范。视图存在性要从提交对象取证（mode=120000 + 目标可达）。
- watchdog（`test_conversation_orchestrator.py:6274`，注入阻塞函数 + 线程事件）间歇根因未定论，全量绿不等于已修，沙箱探针新字段与它无关。历史性能工单仍 pending。

## 踩过的坑
`FWP_TEST_RECEIPT_DIR` 只被 `run_main_gate.sh` 读、写入方不认，收据仍落默认目录并覆写 `latest.json`——按 revision 取时间戳收据。`run_main_gate.sh:82` 缺收据的诊断在 bash 3.2 下自身崩溃（`$LATEST` 紧跟全角括号被吞进变量名），表现为 ruff/pytest 全绿而脚本退出码 1。zsh 不对未加引号的变量展开分词，`for s in "a --check"` 整串喂给 argparse 得假红。
