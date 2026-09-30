# 8792 全部相关 agent 推进盘点（2026-09-30）

本盘点覆盖当前 PR、所有 8792 相关本地/远端分支、最近的 Codex/Claude/Pi 交接和生产实况。它把“已上线的数据与校验改进”和“尚未证明回答能力的实验”分开；不把工作树数量当作完成数量。

## 当前生产与主干

- 生产 `8792` 实测 `source_revision=2c3949786568e50945013aeeb46c168b7fe8bbf9`，`source_dirty=false`，代码与快照匹配；`/api/health` 与 `/api/health/ready` 均 200，13/13 就绪检查全绿。运行时实际模型是 `glm-5.3-flash`，没有本轮回答能力分支改模型配置。
- `gitea/main` 已连续合入 #986、#987、#988、#989。主干当前已经包含：带限定词金额字段的数值核验修复、百分数字段单位契约、缺字段/不完整聚合降级 `partial`、空新高标记改为“未核验”、夜跑桥缺口与名称补落、市场停更披露等。
- 这些改动改善了证据解释、数据完整性和输入新鲜度；它们没有证明模型在时点、现金流起点、估值口径上的正文推理已经解决。生产仍有 4 个旧 open episodes，属于运行现场记录，不是新一轮回答能力通过证据。

## 回答能力线

| 线 | 当前状态 | 结论 |
|---|---|---|
| #956 `fix/8792-answer-capability-0928` | open/WIP，远端 head `774cfbd1a941` | d9 的来源完整性拒收、同 H 有界恢复等窄修复可审；自然回答仍未签通过 |
| mainsync `fix/8792-answer-review-mainsync-0929` | 本地/远端 WIP，`c6ba28f0336f`，干净 | 合过旧 main 的整合树；旧全量收据不能替代最新 main 组合，也没有内容质量签字 |
| excerpt v2 `fix/8792-harness-takeover-0929` | 已撤回，远端仅 salvage 指针 `f3ec04253` | 新闻发生 D0→D3 时点外推，财务口径仍错；不接生产 |
| redraft ablation `fix/8792-glm-redraft-ablation-0929` | 本地/远端 salvage，`796ae1435`，干净 | 新闻删 H 没有相对 OFF 的独立收益；财务 ON 未完成估值计算；拒签 |
| material correction `fix/8792-material-correction-0929` | salvage，`847748044` | 原题/材料承接的工程修复较窄；实测模型身份不符预注册且正文仍错，不能签回答质量 |
| `agent-judge-mode` / `json-mode` | salvage 分支 `e86dc6af` / `97d54cc8` | 隔离实验，未合 main、未接默认运行时 |
| #966 工具授权差值审计 | open/WIP，4P/Ruff；远端 head `899450108` | 747-run 原始身份与 run→revision 映射仍不可证；不是回答质量改进，不能合并或开 P1 在线遥测 |

原四臂与重写对照的完整结论见 [回答能力收口快照](2026-09-30-8792-answer-capability-closeout.md)；#956 原 PR 仍保持 WIP。

## Knevo / Pi 相关线

- Knevo intake 已通过 #951 合入，长川现金流审读也已沉淀；它们提供了可吸收的研究方法：现金流桥逐项勾稽、订单到回款分段、局部证据更新、没有预期时不写“超预期”。没有同题 8792 配对答卷，不能登记胜负。
- 旧 Knevo judge cap（`exp/knevo-judge-cap-120-0927`）和 Knevo tool parity salvage 均未合 main；不能把试验或单侧审读写成对照通过。
- `codex/8792-interactive-readiness-0927` 已在主干，内容是记忆引用边界的窄修复；不是新一轮自然问答能力证明。

## 其他已落地、但需正确归类的 agent 工作

- #954/#960/#964/#986/#988：减少“证据里已有数字却被标待核”的误报，并将单位/百分比写入同一字段契约。
- #967/#977/#982：市场停更披露、夜跑桥缺口/两源补行、名称捕获与补名，改善数据输入与时点透明度。
- #989：缺字段和不完整聚合降级 `partial`，空新高标记保持未知，避免把缺失数据包装成确定事实。
- #965、#955、#961 等是变异审计、worktree/PR 收口和客户端回读基础设施；它们提高验证可追溯性，不等于回答质量提升。
- 老的 R4/R5/R6、boundary TTL、E2 material contract 分支仍在远端但不在主干；其交接明确保留 live 失败或仅有离线工程绿，不应整体搬回当前优化线。

## 工作树与会话现场

- 主 checkout `/Users/a77/finance-workspace-private` 有 128 项其他 agent 未提交改动，不能作为本轮基线；生产快照 `finance-workspace-2c3949786568` 干净并被锁定。
- 当前审查树 `fix/8792-answer-review-0929` 干净，仅有本盘点文档；`arena-8792-harness-takeover-0929` 干净；`answer-capability`、`answer-resume`、`answer-closeout` 仍有各自脏改动或归档材料，未认领前不要清理。
- Codex 侧目前只有本线程 active；Knevo 对照线程 idle，其余相关历史线程 notLoaded。Pi/Claude 的最近文件和 PR 回读没有发现新的、已合入 #956 的回答能力补丁。

## 最终判断

当前所有相关 agent 的推进已经收敛为：生产证据/数据质量链有实质进展；回答协议有一组可保留的窄修复；能直接改变正文质量的两组实验均未通过。下一轮不是继续堆限制，而是以 `2c3949786568` 为唯一基线，只审 d9/退役 v2/纠正连续性修复，再做有限、固定模型身份的正文验收。通过前不合 #956、不切生产；不通过就把该线明确结为“工程修复保留、语义候选撤回”。
