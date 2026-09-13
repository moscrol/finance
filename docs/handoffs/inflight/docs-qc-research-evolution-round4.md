# 四轨返修第四轮 · 独立复核

## 这个分支做什么
只审 01 `2c372331` / 02 `e27b3352` / 04 `fcc7838c` / 05 `cb892d93`，不代修、不审签 03/06。详报 `docs/handoffs/2026-09-13-research-evolution-round4-qc.md`。

## 决策与被否方案
- 固定 SHA 隔离树；否了在脏主检出跑业务测试。
- 固定反例通过≠缺陷族关闭；新增反例独立计，不否认真实绿色收据。
- 否了计时等同费用覆盖、展示排序等同业务先后；保留合法人工计时与明确时序对照。

## 当前状态
详报和三个探针已提交 `2013d994`，本分支仅审查产物；未 push/合并/部署。整包暂不签收：**4 个安全断言红（2 P1、2 P2）**。
- J6[P1]/01：day_of 截文本日期，09-11T16:30Z 与 09-12T00:30+08 在 09-11 cutoff 得 open=1/0，均 strict。
- PV8[P1]/05：辅助任务只有开始/放弃时间，无 run/费用，20分钟计时仍把 full_cost unknown→known，金额仍 CNY 0.46。
- J5-补充[P2]/01：同刻 h1/h0、基线 h1 排最大，unchanged 早退吞歧义；h1/h2 才可见。
- J7[P2]/01：naive h1 与 aware h2 不可比，UTC与原文混排序选 h1，待办消失且无 gap；补时区两向得相反业务结局。
02/04 本轮无新增实现发现。

## 已验证
隔离干净树模块 **101+65+74+112=352 passed**、模块 Ruff 通过。原 QC 五断言 **5 passed**；归档八例保持。三份全量收据确实 dirty=false、绑定修复 SHA（9641/9614/9652），本轮仅核实未重跑。
证据 `~/.finance-runtime/reviews/research-evolution-round4-qc-20260913/manifest.json`。新增四边界均有修前对照；J7 修前也缺 gap，但此补丁改变了业务选中者。D5 新增两测试对修前实现为 1红1绿，不能声称全6条先红后绿。

## 未验证 / 已知边界
未跑完整候选全仓/前端/端到端/注册表或四轨组合；未验证 06 接线与真人试点。不从瞬时树扫描证明历史上无其他 agent。

## 下一步
01 修 J6/J5-补充/J7；05 修 PV8，再跑原八例+原五例+新四例与合法对照。06 最终组合另跑集成门禁。04 推远程评审与整包通过分开授权。

## 踩过的坑
探针 `docs/verification/research-evolution-round4/`；设 `RESEARCH_EVOLUTION_QC_ROOT=/private/tmp/research-evolution-r4-qc-xD9oMm` 后跑 test_adjacent.py，当前刻意 4 failed。D5 修前脚本是内存替换单模块，不是父提交全量收据。已将临时反例落仓，不动脏 harness-reference。
