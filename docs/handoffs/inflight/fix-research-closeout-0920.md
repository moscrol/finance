# 未闭环工作推进 · 2026-09-20

## 任务与约束
用户要求核工作树、判断未闭环设计并推进。设计源 `docs/superpowers/specs/2026-09-20-research-closeout-design-review.md`，具体实施片在同日期 plans。遵守 subagent-driven-development：单实施者，Spec通过后Quality，通过再下一片。禁止动原脏树、生产、真实模型/付费外审；main合并等用户确认。

## 已交付
- #789 最终62bbc4ec包含main4ace5ec2，全叶通过：Python11825P/85S/2X、前端110P、E2E34P/2S、Ruff/registry；严格base-drift=0，独立双轴与合流增量复核通过。已推，异步合main确认问题待用户答复，未获授权不能合。
- 财务别名/单位：代码26fadf33，独立Spec与Quality在d2fc872b通过；b345975f仅更新交接，已推。PR797以R6 d8d6196b为基座，未合main。q保邻句、保稿/E2拒句回路尚未合流。
- 运行恢复：代码7199db11/7c3b36b4/11216c81，日期残项已修；独立Spec原12格及守卫、Quality另16P均在clean d197450d通过。12d0ea13仅回写交接，已推。PR798以原runtime分支a7为底；与main实测8冲突，尚无合流全叶。

## 后续队列
1. 历史返修e0f2a5c7已推且clean：78P历史/42P3S地图、原结构1P；独立Spec四组行为/12P通过，Quality进行。旧四题失败属fbd8；未重跑自然验收。
2. 运行恢复与财务修复已独立评审，后续按原分支合流约束补当前main门禁。跨进程driver仍未开放。
3. 金融RAG消费者：固定受管版本，状态在换版后首次查询前就非ready；legacy/缺绑定/回滚对照，计划已写尚未实施。
4. 302132：独立65P但发现同步换code仍PASS与巨大int导致无FAIL JSON；按既有CODE绑定并可靠失败，计划已写尚未实施。
5. 夜跑6356：独立36P，但显式刷新跳过借旧success认证；仅此缺口先修。跨午夜涉及业务日/写入时刻/即时市值，另定完整合同；main可选Hithink skip为集成条件。计划已写。
q正文增量接R6计划已写，不能整文件覆盖已修单位守卫。
#791：两套相似算法已排序；缺显式成员并集总量及distance_definition投影。#790已有诊断送达与脚本纠参23P，不能重造。其余研究工单、夜跑合流、自然质量及部署仍待各自验收。

## 证据与现场
外部根 `/Users/a77/.finance-runtime/reviews/research-closeout-20260920/`；入仓原件 `docs/verification/2026-09-20-research-closeout/manifest.json`，.py/.log加.txt保存原字节，README本身也进清单。旧失败不覆盖。
本树只协调文档，主树detached且有他人修改。指定解释器为主树`.venv-workbench/bin/python`。生产8792/双索引/L2未动。工作树未删除；“推送/定向通过/整合/业务通过/生产生效”分开记。
