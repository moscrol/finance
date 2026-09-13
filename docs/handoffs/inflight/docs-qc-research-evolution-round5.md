# 四轨第四轮返修 · 第五轮独立 QC

## 这个分支做什么
只审 01 b886b796 / 02 e27b3352 / 04 fcc7838c / 05 15da570f。详报 `docs/handoffs/2026-09-13-research-evolution-round5-qc.md`，不代修、不签 03/06。

## 决策与被否方案
- 固定 SHA 隔离树，否了污染主检出的混合测试。
- 旧反例修复认可、新边界独立阻签；否了用旧绿灯宣称缺陷族关闭。
- 费用按任务及类别覆盖，否了任意费用等同完整模型费用。
- 机器收据优先，否了以全量重跑绿倒推首跑失败原因。

## 当前状态
详报和探针已提交 `d83a0c48`；仅审查产物，未 push/合并/部署。**仍暂不签收：4 个新安全断言红（3 P1、1 P2）**。
- J8[P1]/01 conditions.py:114 仍 day_of，次日观测 UTC 写法提前触发 true/strict；市场写法 unknown。
- J9[P2]/01 contracts.py:429 created_at[:10]，同刻 UTC 写法绑定提前一天成立。
- J10[P1]/01 signature 纳歧义、item id 未纳，末端 setdefault 留旧 superseded 丢新 open；修前 open=1，修后=0 且无 gap。
- PV9[P1]/05 任意 selected 任务账单解除模型缺口；只补 tool 0.01 完整成本 unknown→known（CNY 0.47）；仅再补 writer 仍错误 known；模型两类真补齐合法。
- 汇报[P2]：05 首跑失败机器收据是 workbench_conversation_integration，不是 pipeline_p0；后者单跑不是原失败项。全量重跑绿是真。

## 已验证
干净隔离树模块 **104+65+74+113=356 passed**；四轨全仓 Ruff 通过。原四例旧树4红/新树4绿；第三轮五例5绿；归档八例六组命令保持，归一身份字段后与原 QC 一致。D5 修前主例红、负控绿。
新边界4 failed/1 passed，封存脚本重跑一致。全量9644/9653收据 dirty=false 与修复 SHA 匹配，本轮只核实未重跑。
证据 `~/.finance-runtime/reviews/research-evolution-round5-qc-20260913/manifest.json`。

## 未验证 / 已知边界
未运行四轨组合、06接线、完整候选前端/端到端/注册表及真人试点。02/04保持候选，不等于集成通过。04推远程评审仍单独授权。

## 下一步
01修J8/J9并扫完时间取日族；J10连身份/版本/去重/替代链验。05修PV9，不只筛任意model费用。更正失败归因，复跑旧八+五+四与本轮四例及负控，06再对新组合验收。

## 踩过的坑
新探针在 `docs/verification/research-evolution-round5/`，设 RESEARCH_EVOLUTION_QC_ROOT=/private/tmp/research-evolution-r5-qc-Dmm5xA。原归档仅适配路径和 SHA 断言，输出原脚本 hash。方法沉淀 `~/agent-memory/10_knowledge/state-transition-identity-must-survive-dedup.md`；不动脏 harness-reference。
