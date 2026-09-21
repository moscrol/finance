# 接手原收尾会话：刷新完成合同与回填验收归档

日期：2026-09-20。原会话 `01a0bca6-ab06-7d11-aa00-75cb22254403`（Codex日志 `~/.codex/sessions/2026/09/20/rollout-2026-09-20T10-30-34-01a0bca6-ab06-7d11-aa00-75cb22254403.jsonl`）。

## 背景与发现顺序

1. 用户要找到原先推进#801、回填与夜跑的session并接手未完部分。重新fetch并查PR：#801已merged、main=e51c5157；#789已关闭由它接替。此前授权只覆盖这次合并、不切生产，不能外推给新PR。
2. 主检出有他人改动，原协调 `~/fwp-wt-research-closeout-0920@b1bad144` 也留有未提交归档；均保留。新开 `~/fwp-wt-nightly-refresh-resume-0920`，吸收原夜跑6356ffd5与main。合流34f49ce1保留双方教训、main四个Hithink步骤及local指数的禁止复盘会回退。
3. 原计划 `fwp-wt-research-closeout-0920/docs/superpowers/plans/2026-09-20-nightly-refresh-completion.md` 已批准离线R1修复。小库复现：底价12、成员10、旧成功审计完整；180日内无基线，显式刷新跳过却rc0。
4. d95b706e用本轮候选/写入/跳过/失败/provider待补及审计共同判定refresh_complete；显式刷新不完整CLI返回rc2。旧审计不伪造，普通日更不变，dry-run只预览。真实child消费失败后不留本轮成功状态。
5. main集成先出现Hithink缺key的合法skip被恢复脚本当失败。仅对sync.HITHINK_STEPS允许skip并保留“未更新”收据；其他步骤skip/失败与质量失败仍阻断。相关160P，最终固定源码全叶通过。
6. 原回填验收Spec/Quality已PASS但未归档交付。本次核候选1fd34dc7、15清单hash和2报告hash，补建#802，base仍原回填分支，不将小片双审扩大成main/生产验收。
7. 本枝推送并建WIP #803。独立Spec新会话首轮因Codex额度耗尽而退出，0审查工具、无报告；未重试/未换服务、Quality未启动。保留失败原件，等待有界复核，不以作者测试替代。

## 方案取舍

| 决策 | 被否方案 | 理由 |
|---|---|---|
| 完成状态绑定本轮重算结果，旧审计照实保留 | 仅看旧audit、清掉旧审计、加第二套freshness台账 | 旧记录可能当时真实；要修的是本次请求完成语义，不是改写历史或造旁路 |
| 保持恢复基线180日 | 放宽365日让反例通过、随便找名单 | 365只作fixture正常对照；未经核实的名单不能拿来填“完成” |
| 仅豁免计划明确的可选skip | 所有skip都算成功、把skip改成ok | 可选未更新与必需步骤失败不能混为一个成功位 |
| R1/I1与R2拆开 | 删除跨午夜日期门、称历史回放已可用 | 合法业务日、真实写入时间、即时市值隔离需共同设计；现在保留安全拒绝 |
| 独占检出验固定代码；证据后续文档提交 | 在脏共享树签全量、把160P当全量、把文档tip继承旧SHA签字 | 测试结论属于具体代码与环境，文档身份另记 |
| WIP停在独立复核缺失 | 重试刷额度、改用未授权服务、拿作者测试冒充独立PASS | 无审核结论就是无结论，不因工程绿而升级 |

## 验证与边界

受测完整SHA：`d95b706edc6e44f3dfa54d7b8837dfdd36b16cf2`。Python11913P/85S/2X，Ruff和registry五项rc0；前端110P及lint/typecheck/build通过，E2E34P/2S；前后同SHA干净，严格收据基座漂移0。跨仓依赖固定KB1254224b、研究站f6065838。

两种撤保护变异分别红→绿：刷新判据2F→2P；扩大skip2F/7P→9P，同输入同断言。最终恢复树干净、11相关模块160P。原探针适配副本是作者复跑，不再称独立。完整命令/身份/哈希和原红日志见 `docs/verification/2026-09-20-nightly-refresh-resume/README.md`；外部根 `~/.finance-runtime/reviews/research-closeout-resume-20260920`。

本片不认证生产库、真实行情源、无人值守定时、Linux CI或自然模型回答。PR相对main还含原夜跑的受控恢复代码；新片有限复核不能替原整条恢复链签字。全量证据固定在代码SHA，不移签之后的文档tip。

## 剩余队列与下一步

- #803：独立Spec→Quality受阻；先完成有界复核，再核最新合流/最终SHA全叶，main合入单独等用户确认，生产另批。
- R2：先写业务日/写入时间/市值来源合同，再做跨午夜正反例；不要删除现有门。
- #802：双审只签小片；父回填链与main集成另验。原候选及协调树保持原样。
- #797：原独立小片不代替财务父枝、q正确邻句/保稿/E2拒句反馈合流；#798仍有与main的运行时冲突、没有跨进程driver整体验收。
- #800：原时点无文本冲突不等于全叶或原四题自然验收；#791成员并集总量与distance_definition投影待做，#790已有诊断/纠参测试勿重复。
- #799：只补评论接手指针，不改他人脏工作树或关闭PR。

## 同日接手 QC 与 K3 复跑（本地 17:00–18:00）

1. 接手 QC 先核原交接：全部数字与状态属实。另查出三件：#789 关闭时无接替指针（其头提交已是 main 祖先，内容确经 #801 进入）；共享收据目录有一份 d95b706e 的 0 计数收据（07:39:51Z，产生者不在归档，权威收据是重定向那份）；#803 的 Gitea mergeable=false 源于 WIP 前缀，`merge-tree` 对 main 干净。文档 tip be9e5db9 补跑 ruff、40 个全树扫描测试文件 927P、pre-commit 11 道全过；全量 Python / 前端仍只绑 d95b706e。
2. 用户告知 K3 恢复后，沿用原 Codex 编排、只换传输为 pi + kimi-k3 复跑：Spec PASS、Quality PASS（issues=[]）。细节、指纹与交叉核验见 `docs/verification/2026-09-20-nightly-refresh-resume/README.md`「K3 复跑」。Codex 失败原件未覆盖。
3. 取舍：换服务不算越权，`pi --provider mirasim-kimi` 是本仓已用过的独立 QC 路径且用户当场确认；没有 OS 沙箱就用四组指纹替代；审核者证据必须过「哈希对得上、复跑得出、变异咬得住」三关才采信，Quality 删掉的变异副本以事件流工具输出为证。
4. 踩坑：zsh 不对未加引号的 `$VAR` 分词，整串 `env -i …` 被当成命令名，两次复跑 rc=127；换显式 env 命令后才是真读数。rc=127 不是红，也不是绿。
5. 仍未做：main 合并等用户确认；#789 指针；337 棵工作树清理（看板：108 棵干净已合可拆、13 棵先认领、生产快照多留约 28 个），已向用户提出分三批清的方案。

## 工具沉淀盘点

防错保护已进 `tests/test_stitch_refresh_completion.py` 与 `tests/test_recovery_refresh_integration.py`，外部probe/变异日志只作本次证据。固定全叶编排只是调用现有pytest、registry、run_frontend_gate与check_test_receipt；封存脚本原文供复现，不建第二套生产执行框架。可迁移原则补入 `gate-covers-only-its-return-value`：要求刷新是意图，不是已刷新凭证。共享harness-reference树脏且领先远程，未擅改；本次无新增可独立迁移的搭建组件需要登记。
