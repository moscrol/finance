# 晨汇修复候选合流门禁

## 当前结论

工程门禁通过，独立审查未完成，生产消费仍未闭环。finance PR #847 与 KB PR #157 保持 WIP，未合 main，未发布。本记录接续 `2026-09-22-briefing-qc-closeout.md`，不以今天的结果改写上一轮观察。

## 固定身份

- finance 被验分支 tip：`68b622b7692690f5b1c78eb78a49baa032c3c536`。
- main 基线：`e82717d9a7c3dfa811a4538bd44985b61258355a`。
- 本地合流候选：`baseline/briefing-qc-0922@338db9114e52050362677a350059a8f9298848bd`，树 `b82b2fd853c1adfc836bbb2b9dce93f125dad61b`。
- 候选位于 `$HOME/fwp-wt-briefing-qc-gate-0922`，合流树与当时 merge-tree 预演一致；不是主干合并提交。
- KB 门禁对象：`e4cca95312ccb492cd3c4767858416ca49db00d0`，main=`d0caf31146a30e2cea05e6549652afb16fe70cb8`。
- 随后的交接/收据提交不在上述全量测试 SHA 内，不冒称新 tip 已经全量跑过。

## 实际检查

- Python：12520 passed / 85 skipped / 2 xfailed / 17 warnings，exit 0，约 25 分钟。原收据记录 failed=0、error=0、dirty=false、整树脏文件数0；xfailed来自同次stdout。`check_test_receipt --expect-revision <候选完整SHA> --base-drift-max 0` 通过。
- Ruff：全仓通过。
- 注册表：check-parseability、check、backfill-tables --check、generate-views --check及ledger-spec-crosswalk均通过。
- 前端：安装、lint、typecheck、110项组件测试、build全部通过；E2E 34 passed / 2 skipped。原收据 complete=true、identity_stable=true、dirty=false，首尾SHA均为候选。
- KB：改号提交上全量529 passed / 1 warning；严格词表完整性0错误/2告警；体积、质量基线、日志号与索引守卫通过。质量基线通过仅表示无新增退化，存量债务未清零。
- 两份来源QA通过；图谱按cascade:none跳过。抽取--check仍1338行；投影SHA256=`037655781b50e841d1991f5a27a8f5fba76e17cd6b5360447245c5d4a0d51d7a`。
- 候选代码重验已有final教学库：09-15 -> 09-16 PASS，0/6/6、二维NULL、lag5、strict过滤3个晚写教学对象；09-18仍因行情截至09-18 BLOCKED/exit2。没有重建或部署生产教学库。

## 独立审查与运行边界

Claude只读审查第一次超过10分钟无输出后手动终止；第二次由现有worker在420秒超时后清理进程组。两次均无结论，不等于无发现或PASS。未使用自查替代独立审查，也未授予发布权限。

Python测试使用清洁环境与固定finance候选，但显式KNOWLEDGE_WIKI指向KB修复树。期间KB从5b02f29f6改到e4cca9531，仅日志号及交接改动，scripts/tests/skills与事件投影均无差异；不能把整个跨仓输入描述成全程不可变。KB全量在e4cca9531提交完成后另跑通过。

首轮门禁漏切cwd，误落共享主检出：finance干净树门拒绝；所谓KB pytest实跑finance tests并出现4个收集错误。该次不是本候选证据。随后KB收集又因FINANCE_WS多候选拒绝；显式指定候选路径后完成全量。错误日志保留，不作为代码失败或成功结论。

## 后续与被否方案

- 保留WIP：工程门禁不能替代独立审查；外部审查恢复后，针对最终head/base重新审并核输入身份。
- 未改共享主检出、未复制大行情库：主树有他人改动，磁盘余量波动，禁止为验收扰动生产。
- 未合main：需用户明确确认且最终合流门禁成立。正式合入后仍需核实际main tip收据，候选收据不能冒充它。
- 未造09-21行情刷绿：补齐行情只能走既有daily-full，随后按真实构建时刻重建独立标签再验。
- KB并发#6893：本批纠偏记录改为#6894，保留原#6891/#6892；扫描非原子预占，合流前仍检查。

## 证据与工具

仓内小型收据：`docs/verification/2026-09-22-briefing-gates/`。原始运行目录：`$HOME/.finance-runtime/reviews/briefing-qc-gate-20260922/`；Python原收据：`$HOME/.finance-runtime/test-receipts/20260921T171617Z-338db911.json`。KB门禁正文在KB的同名verification目录。

复用现有run_frontend_gate、check_test_receipt、merge-tree、gitea_pr及只读verify_briefing_consumption，未另建临时业务脚本。cwd失误已有2026-09-13教训，不重复造方法论。两次审查进程、Python进程及19081/19084测试服务均已退出。
