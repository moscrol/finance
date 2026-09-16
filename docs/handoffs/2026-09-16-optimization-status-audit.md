# 2026-09-16 优化落地状态审查

## 结论与边界

**不能认定所有优化都已落地。** 已有相当完整的研究能力与运行底座，但仍同时存在：代码在分支未合、主干有而生产未更新、功能已接线但完整验收未过、按设计关闭或等待真实样本的项目。

本次是状态审查，不是新增实施或生产验收。不按过期文档里的未勾选数量计算完成率，也不把方法尚未证实有效算成工程故障。没有改业务代码、生产配置、数据或他人工作树；仅新增本快照与本分支交接。

## 审查坐标

- 原工作树 `/Users/a77/finance-workspace-private` 是有其他任务改动的 detached `b4a35fa2`，不作为当前能力基准。
- 隔离树 `/Users/a77/fwp-audit-optimization-status` 固定源码 `3949a2ea3eecf63210728a60eb9b85a06acef862`，也是本轮 fetch 后的 `gitea/main`。测试时干净、detached；测试后建 `docs/optimization-status-audit-0916` 仅留文档。
- 2026-09-16 18:46:26 +08:00 GET `http://127.0.0.1:8792/api/health`：生产 `0758a423d6c82c2e25258f3fa33cd840c5ec97da`，healthy、source_dirty=false、code_matches_repo=true，加载根为该版本部署快照。
- 18:49:12 GET `/api/readiness`：13 项 true，但请求 09-16、服务 09-15，freshness=historical；RAG 仍警告 legacy query 协议，缺三个可选过滤参数。这证明可用与一致，不证明当天数据已到。
- 生产到主干相差 13 个 first-parent 提交，包含功能和文档。不能把每个提交都算成一个未上线功能。
- health 模型字段在审查期间发生变化，最后读到 `continuous_glm / glm-5.3-flash`；这是配置声明，不是每次真实调用的身份证明。本轮未发真实模型请求。

## 主要发现

### 1. 材料任务收尾仍未完成，主干可复现已知缺陷

P5 代码 `fc9a130b` 已推至 feature 分支，并出现在 `gitea-pr/759`；**未包含在 main，git cherry 仍为 +**。P6 `d17ebc27` 同样未包含在 main，仅发现本地分支。不是整个材料边界功能缺失，而是后续继承、来源绑定与正式验收尚未收尾。

本轮在固定主干直接调用真实 `classify_top_level_regions` 与 `compile_material_contract`：首轮声明“以下是完全虚构的研究案例，不对应现实公司”，下一轮“继续上一轮”并重复同句，前提标注从 1 条变 2 条，text_ref 与 scope 完全相同，只有 source_turn=1/2 不同。`tuple(dict.fromkeys(marks))` 把轮次也纳入身份，未做到同值重申幂等。另一个 P5 差异是模型可见的题号仍渲染为裸 q3，而非“轮次1的q3”。

- 主干位置：[material_contract.py](../../intelligence/services/material_contract.py)、[episode_factory.py](../../intelligence/services/episode_factory.py)。
- P5 交接：`/Users/a77/fwp-wt-e2-p5-inheritance/docs/handoffs/inflight/feat-e2-p5-cross-turn-inheritance.md`。其中“未推送”已过时，以本轮 Git 查询为准。
- P6 交接：`/Users/a77/fwp-wt-e2-p6-input/docs/handoffs/inflight/feat-e2-p6-conditioned-input.md`。材料锚点只证明原文身份，不证明语义蕴含；live 判官、独立 QC 未完成。
- P7 正式 A7/A14 验收仍要求全新会话、原始 T3、不重复贴禁令；P5/P6 离线测试不能代签。P6 还记载无编号 material_only 的 input-only rewrite、local_only 原题号槽、fictional×full 前提送达等边界未处理。

### 2. 多项新增能力已经合入，但尚不在 8792 的应用版本

生产 `0758a423` 之后主干新增：教学结构视角 #672、积分账本与真实 token 结算 #556、写作成本预算 #659、本地个股技术位和自选股 #730、教学配对检验 #660。应归类为“已合入、应用版本未部署”，不是“尚未开发”。

例外：#561 板块维度与库维护的提交明确记载已应用生产库；数据库副作用不能仅按应用 SHA 推断，不能笼统说该修复尚未生效。

证据：本轮 `git log --first-parent gitea/main`、生产 health；[切流收据](2026-09-16-8792-switch-0758a423.md)。本轮不批准合并或切流。

### 3. 研究进化工程已集成，任务级耗时和真实效果验证仍不完整

[06 进度](../superpowers/plans/2026-09-13-research-evolution/06/PROGRESS.md)明确区分 engineering_complete、product_verified 和 field_evidence。真实模块 01-05 已接 Workbench，不应报成“只有设计”。但 I13 真人配对、I14 任务级计时、I15 真实前瞻一轮尚未完整验收；[BLOCKED](../superpowers/plans/2026-09-13-research-evolution/06/BLOCKED.md)列有结果源、诊断策略和条件选择器等剩余边界。

I14 的 `a4ace074` 在 `fix/re06-visibility-timing`，本轮 git cherry 为 +。该实现仅做 `workbench:<session>` 自用计时、task_id=null；作者也明确未完成“可信冻结任务身份 -> 模型等待 -> 完成 -> 不可变收据”同链验收。I14 是工程项，不应一并说成只能等真人授权。主干 [run_observer.py](../../intelligence/services/research_evolution/run_observer.py) 的 task_id 也为 None。

I13/I15 及提取前置 #53 的真人实验则确实依赖参与者、协议或时间窗口。不能把未到期的验证硬写成失败，也不能给未发生的真人实验签通过。[#53 台账](../superpowers/specs/2026-09-01-workorders-INDEX.md)最新头部已合 #753，后面的“待合”是历史文字。

### 4. 上线健康不等于默认模型链已获得稳定作答证据

最新[切流追加收据](2026-09-16-8792-switch-0758a423.md)记录：17:15 有一个真实 grounded 成功样本，使用临时会话级 BYOK grok-4.6，独立判官停用，回答如实带未复核说明。旧的“切后一次都没成功”已不成立。

该样本也不能证明内建模型链稳定或跨题型可靠。会话级 BYOK 重启失效、n=1、未获独立判官通过均是收据边界。由于本轮观察到模型配置后来变化，**不把下午的 kimi/GLM 网关故障当作当前仍故障的确定结论**；需在最终模型配置固定后补正式真实入口探针。

### 5. 已实现的研究能力，部分效果证据仍不足

- [自适应研究 06](../superpowers/plans/2026-09-09-capability-upgrade/progress/06.md)：候选复杂题成果 27/32、基线 30/32；候选同时开启 STALL_FINALIZE=3，不是单变量实验。已证明存在建议与换路行为，未证明总体效果提升；默认硬收口保持关闭是有依据的决定。
- [连续研究 09](../superpowers/plans/2026-09-09-capability-upgrade/progress/09.md)：有跨轮投影和差量回答样本，但 P2/P3 补跑使用专用重试代理并修改过沙盒历史消息，不是完全自然续研收据。主干 [conversation_orchestrator.py](../../intelligence/runtime/conversation_orchestrator.py) 仍只给 research 车道注入 project prior；这不是整个连续研究缺失，而是覆盖与自然跨日验收不能扩张。
- [教学配对检验](../verification/2026-09-08-teaching-framework-mcnemar.md)：验证期改善的配对 p=0.13，不足以区分真实改善与噪声；验证集已被咨询至少 29 次，需要独立留出验证。全期一致率不能单独作为有效性结论。
- [E-009 最新复核](../superpowers/specs/2026-09-10-knevo-arch-delta-worklist.md)：记忆可靠性降权代码和接线已有，但 [user_memory.py](../../intelligence/services/user_memory.py) 的阈值为 None，按设计关闭等待回测与确认。不能报成没写，也不能声称生产已自动降权。

## 已落地基座与未核足范围

已核到主干和生产代码均包含：连续 Episode 运行底座、深读检索、关系地图、财务计算与沙箱产物、跨轮研究项目、受控补数、多对象排序、时间长河核心、方法验证及研究进化集成。它们的存在与历史收据，不为每条真实任务质量代签。

本轮足以否定“所有优化都完成”，但**没有逐项签收全仓所有工单**。#26 检索预算重填、#45 episode 唯一家等源码仍保留原形制；#32/#33/#46/#50/#51 等历史运行与补数状态需分别重查执行台账及值级数据，不能直接照 INDEX 的旧状态断言。J1/J2/J3 整包无污染终验收据本轮未核足，不把旧 PROGRESS 的“未开工”当现状。#54 消费侧新设计已随 #762 合入，文档是设计不是实现，剩余实现需按具体消费方复核。

## 本轮验证

固定干净 `3949a2ea`，使用主树 `.venv-workbench/bin/python`：

```sh
python -m pytest -q intelligence/tests/test_e2_material_contract.py intelligence/tests/test_e2_material_delivery.py intelligence/tests/test_e2_material_turn_delivery.py intelligence/tests/test_research_evolution_falsification.py intelligence/tests/test_research_evolution_i11_consent.py intelligence/tests/test_teaching_framework_paired.py
```

**164 passed / 0 failed / 0 skipped**，5.46s。收据：`/Users/a77/.finance-runtime/test-receipts/20260916T104742Z-3949a2ea.json`，target 为上述六文件，不是全量测试。另有前提重复累积的纯函数复现。没有新跑真实模型、完整前端、进程崩溃恢复、真人试点或生产写入。

## 建议顺序与维护边界

1. 先独立审完材料 P5/P6，并补正式 P7；不把已有修复重写一遍。
2. 对准备发布的固定候选跑完整门禁，经用户确认后更新 8792；固定模型链后做真实入口验收。
3. 收完 I14 任务级计时，把 I13/I15 与 #53 的真人/前瞻协议单独排期。
4. 用少量冻结任务验证研究质量和可靠性，再决定阈值、硬收口和方法晋升，不以完成率替代有效性。

本次没有创造新能力或新架构决定，不改 canonical 能力图谱、不新增第二份长期能力目录。此文是绑定版本与时刻的审查快照。重复使用的是既有 git/health/测试收据机制，未新增临时脚本，无需向 harness 工具库沉淀重复工具。
