# 发布准备结果与逐次合并门 — 2026-10-07

接续 [10:25 恢复原任务快照](2026-10-07-release-resume.md)。本页记录后续实测结果；
先前的“正在跑”“尚未推送”是历史观察，当前状态看本分支 inflight 与平台回读。

## 1. 准确候选的全量 Python 已完成

#51 固定 `a8fe098a83ddb6cd7e99004d24dbb20c6693c933`，本会话独占 detached 树
`~/.finance-runtime/reviews/release-resume-20261007/gate-pr51`，10:14–10:42 +08：

- `run_main_gate.sh`：完整 `ruff check .` 通过；pytest **20712 passed / 75 skipped / 2 xfailed**，
  17 warnings，1665.70s；零 failed/error，runner 和 pytest 退出均为 0。
- 生产解释器 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`，Python 3.12.13，
  依赖指纹 `e1c50cb821a30f00`；本机 httpx 0.25.2，与 CI 0.28.1 分开验。
- 收集 20789，读数合计 20789。target 为准确仓根，scope 无位置参数/ignore/-k/-m 等收窄。
- 树前后 revision 相同且干净。用该候选自带 checker，显式 `--require-full-scope`
  `--expect-revision <完整SHA>` `--base-drift-max 0` 校验通过。
- warnings 包含 toy market-stage 测试的矩阵运算 RuntimeWarning 和旧 `datetime.utcnow`
  弃用提示，完整日志保留；不是“零警告”。跳过/预期失败不写成执行通过。

证据根 `~/.finance-runtime/reviews/release-resume-20261007/`：
`pr51-full-summary.json`、`pr51-full-gate.log`、`pr51-full-scope-validation.txt`、
`pr51-full-receipts/gate-hihTN9bw/{pytest.json,pytest.log.txt}`。

**边界**：这是 #51 候选的全量 Python，不是未来合并 main 的结果；没有本机重跑完整前端/
端到端，没有自然模型回答质量结论或部署完成结论。其余 PR 不借用这张收据。
测试临时区保留，runner PID 85023 已结束；未删除任何旧目录。

## 2. 公开队列与时点

10:50 回读（全部 SHA 及检查 URL 在私有 `open-prs-1052.json`；文件名不作为时间真值）：

| PR | 当前 head（缩写） | 远程观察 | 接手判断 |
|---|---|---|---|
| #50 | 570142a2498a | 五项成功，CLEAN | 仅3份文档增量；本机registry/crosswalk过，**首个待用户确认的合并候选** |
| #51 | a8fe098a83dd | 五项成功，CLEAN | 上述生产解释器全量通过；#50合后须同步最新main并重验 |
| #49 | a136e41e62bc | 五项成功，CLEAN | 本机定向90P；不是本机全量 |
| #53 | 4594192cc5ba | 重复workflow一组成功、另一组Python仍跑 | 不能择优挑绿；仍堆叠#49，后续改基main |
| #61 | ca185cca5965 | 五项成功，CLEAN | 他人owner更新的证据文档；不移签原旧head |
| #62 | 8d61a715468e | Python仍跑，其余三叶绿 | 部署补偿修复；继续等当前head结果，不代推owner分支 |
| #63 | 597f2ad18b77 | 五项成功，CLEAN | hook事实/实时保护来源订正；与#67有AGENTS邻接冲突 |
| #64 | 60df36839bc0 | 五项成功，CLEAN | 核验器月/范围误报修复；工程通过不证明金融内容质量 |
| #65 | 0575fad6de86 | 五项成功，CLEAN | 新外盘取数；不代表夜跑已接线或时点可知性已验 |
| #66 | d7294e3e470c | Python仍跑，Draft | 单owner继续；离线投影不等于真实修订完成，暂不进合并队列 |
| #67 | 9d431e6f6cc4 | Python仍跑，其余三叶绿 | 本会话核查/凭据内容闸PR；本次后续文档提交会产生新head，必须重看新CI |

#67：<https://github.com/moscrol/finance/pull/67>。已于10:43–10:44普通推送并回读，main未改变；
原始推送证据 `push-review-summary.json`。该head定向30P/11.24s，收据身份通过，独立#51
checker明确判为收窄；原checker的“未被收窄”字样不能采信。新增提交默认扫描0命中，仅限增量。

本轮无合并、部署、可见性修改、生产写库、删枝或真实模型请求。用户任务完成后自行私有化；
事件仍另记私有处，不上传定位/原件，也不把未完成撤销伪称已完成。

## 3. 组合接缝及选择

只做 `merge-tree` 的 pairwise 文本预演，没有检出或合并组合到main：
#49/#51、#49/#53、#61/#62、#62/#63、#64/#65、#64/#66、#65/#66均文本可合；
#63与#67初始9d431e6在 `AGENTS.md` 冲突。原件 `pairwise-preparation.json` 与逐对日志。
两两文本可合不保证整个批次可合，更不证明运行时语义正确。

| 选择 | 未采用 | 理由 |
|---|---|---|
| #67保护段对齐#63，详细配置留流程文档 | 两段各维护一份会漂的保护/hook时点 | 减少同源事实重复；仍有邻接凭据段冲突，不能宣称已全消冲突 |
| #63合入后在自有#67同步时保留双方意图 | 改他人活动树或直接套ours/theirs | #63的断言纪律/CLAUDE来源与#67的index内容闸/退役口径都要保留 |
| #50先请求确认，再逐张推进 | 见当前五绿就整批自动合并 | main保护strict要求包含最新main；每张head、检查与授权都需重新绑定 |
| #30保留草稿并给出接替表 | 据#54关闭或只解测试冲突就整枝合入 | 多片能力未被替代，历史语义反例仍在；[详细证据](../verification/2026-10-07-pr30-capability-disposition.md) |

建议顺序：#50 → #51 → #49 → #53改基main → #61/#62/#63 → #67 → #64/#65。
这只是依赖顺序，不是批量合并授权。#67是工具/文档线，不替代#64/#65的产品验收。
#66不自动加入；#30去留仍待用户裁决。FINANCEWORKS-1/14及#50/#51/#63已评论对应证据。

## 4. 发布仍缺什么

1. 用户逐次确认合并；首张为 **#50@570142a2498a**。每次前回读完整SHA、适用检查和保护。
2. 后续候选包含最新main后重跑检查；新最终main用生产解释器完整Python及本机前端/端到端验收。
3. 真实问答仍须Workbench conversation入口、模型身份、用户态/存储隔离和内容真值；
   新留出/预算未冻结不发实验，旧取消批次不重开。隔夜美股可知时点和换手率单列验。
4. 最终部署另获授权；按已验收脚本切换后核readiness、health版本/干净/指纹、真实答卷及备份。
   此处无提前保证10-08发布完成；目标时限不能替代这些门。

工具盘点：复用现有gate/checker、Git文本预演和平台API；未另建重复验收平台。
当前追加仅文档与同源口径整理，不新增答案规则、不修改他人核验器。
