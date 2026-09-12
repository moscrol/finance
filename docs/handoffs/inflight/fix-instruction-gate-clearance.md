# fix/instruction-gate-clearance

## 这个分支做什么
指令迁移＋清障＋质检 P2 收尾的候选。基线 gitea/main@883e3d36（变基时点；计数会漂，不写）。
背景与被否方案：docs/handoffs/2026-09-12-instruction-gate-clearance.md；
本轮 P2 收尾：docs/handoffs/2026-09-12-instruction-gate-qc-p2-closeout.md。

## 当前状态
已推 gitea，PR #742 已开未合并（合并等用户明确确认）。完整门禁跑在 31d82c39，
此后仅本文件状态行更新（docs-only）。逐叶证据：
~/.finance-runtime/gates/instruction-clearance-r4-20260912/matrix.md。

## 决策压缩表
- 撤出三个技能的删除：全文档源 0 命中，无退役依据。
- 公共联网入口恢复为 AGENTS.md 全局指令。
- Codex 钩子选根：cwd 的 git 仓根优先于环境变量。
- build_registry 仓名→仓根走单一入口 _repo_dir()；ws 恒绑 REPO_ROOT（脚本就住该仓），
  否了按 git common-dir 父目录名猜：clone 改名即读写别树（本轮 P2）。
- scan 缺仓 fail closed，逃生口 --allow-missing-repos。

## 未验证 / 已知边界
- repos.present 记的是扫描时本地磁盘状态，跨机器可漂；两种树形已绿，未拆设计。
- generate-views --check 测不到缺失的视图软链（删软链仍 exit 0）；存在性从提交对象取证。
- watchdog（test_conversation_orchestrator.py:6274）间歇根因未定论，全量绿≠已修。
- FWP_TEST_RECEIPT_DIR 只被 run_main_gate.sh 读；其 :82 在 bash 3.2 下自身崩溃，本轮未修。

## 下一步
等用户对 PR #742 的合并确认；合并后在 main tip 复跑批次门禁四件套＋收据校验。

## 踩过的坑
新判据先在缺陷在场时跑红（旧代码扫到 ws/decoy-skill）再修。
zsh 不分词：for s in "a --check" 整串喂 argparse 得假红。
