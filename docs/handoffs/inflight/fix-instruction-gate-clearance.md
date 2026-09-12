# fix/instruction-gate-clearance

## 这个分支做什么
指令迁移＋清障＋三轮质检 P2 收尾的候选。基线 gitea/main@883e3d36。
背景与被否方案及三轮快照在 docs/handoffs/：2026-09-12-instruction-gate-clearance.md、
同日 -qc-p2-closeout.md、2026-09-13-pr742-memory-hook-p2.md。

## 当前状态
已推 gitea，PR #742 未合并（等用户确认）。第三轮 P2（记忆钩子身份）已修；
完整门禁跑在冻结 tip，SHA 与逐叶证据见
~/.finance-runtime/gates/instruction-clearance-r5-20260913/matrix.md。

## 决策压缩表
- 撤出三个技能的删除：全文档源 0 命中，无退役依据。
- 公共联网入口恢复为 AGENTS.md 全局指令。
- Codex 钩子选根：cwd 的 git 仓根优先于环境变量。
- build_registry 仓名→仓根走单一入口 _repo_dir()；ws 恒绑 REPO_ROOT（脚本就住该仓）。
- 记忆钩子身份恒绑 finance-workspace-private：clone 改名曾注入/回写别项目笔记（第三轮 P2）。
- scan 缺仓 fail closed，逃生口 --allow-missing-repos。
- 同一原则：目录名/common-dir/origin 是位置不是身份；脚本随哪个仓分发就绑哪个仓。

## 未验证 / 已知边界
- repos.present 记的是扫描时本地磁盘状态，跨机器可漂；两种树形已绿，未拆设计。
- generate-views --check 测不到缺失的视图软链（删软链仍 exit 0）；存在性从提交对象取证。
- watchdog（test_conversation_orchestrator.py:6274）间歇根因未定论，全量绿≠已修。
- FWP_TEST_RECEIPT_DIR 与 run_main_gate.sh:82 bash 3.2 崩溃本轮未修。

## 下一步
等用户确认合并 PR #742；合后在 main tip 复跑批次门禁＋收据校验。

## 踩过的坑
新判据先在缺陷在场时跑红（扫到 ws/decoy-skill、注入 WRONG_FINHOT_NOTE）再修。
