# #83 / PR813

## 这个分支做什么
302132固定范围回填整合。文档树代码旧，不从本树验收或生产。

## 当前状态
**ENGINEERING_PASS_QC_BLOCKED_SANDBOX_IDENTITY_AND_DELIVERY**，未合入就绪。PR813远端仍为ae3，继续WIP/open/unmerged；未写生产、未动8792/launchd。
- 最新本地候选 `47061506f7de303a54e2f1c757c9ebb28f951da1`，树 `/Users/a77/fwp-wt-backfill-ready-main724-0925`，已合入 `gitea/main=72402839075e3eefdee7b185db015a0545096b22`。
- 新候选工程：Python16325P/0F/72S/2X，收集16399；定向118P；前端/E2E完整通过；registry5；完整副本演练37检查通过，生产不变、回滚哈希匹配。等价sandbox rehearsal也返回clean并通过。收据根 `~/.finance-runtime/reviews/pr813-ready-main724-0925/`。
- PR远端head仍 `ae3f812e1c1e142953b657ba41f30fce23e7c14a`；新候选未推送、未冒充PR收据。独审最后 `pr813-glm-qc-20260925-20/`，无新模型请求。

## 决策与被否方案
保留旧f650结果，main变动后重跑ae3；否决旧绿移签。保留全部失败批次，否决放宽硬门、失败补签及用宿主诊断冲销独审失败。工具是本单证据，不注册成通用产品能力。

## 已验证
ae3干净树：Python16259P/0F/93S/2X；定向118P；前端123P、E2E34P/2S；registry5项与full-scope通过。宿主完整库副本父发布/verify/37检查/错误输入及amount负控/父备份恢复通过，生产演练前后不变。

## 未验证 / 已知边界
批13在f650取得C1-C7 PASS_WITH_LIMITS，不转给ae3。ae3批14/16-19虽25P但无合格终稿；批20实际23P/2F，两例遇沙箱内clean-checkout守卫，事后宿主诊断干净，根因未证实。终稿又含额外claim，未交付。供应探针非模型新写；C6六次嵌入作者函数体调用，standalone作者pytest为0。

## 下一步
零外呼诊断已完成：旧候选同sandbox直接rehearsal clean；新main724候选以本地clone进入等价sandbox，`_code_revision=(4706,false)`，rehearsal通过。批20的dirty失败仍无法重现，不能宣称根因或修复，不重跑/补签批20。报告schema离线预检最大4932<6000，负例16项通过。此前独审失败前不追加付费请求；当前4706仍无独立QC。合入与生产授权均false，生产要重新冻结与逐字授权，WAL存在即停。#802已关闭留6446指针。

## 踩过的坑
16-18首拒收实际是6000字符限额，不是最初判断的claim格式。19来源说明超字段长度；20仍有真实失败。运行根ready-only脚本未执行，不是就绪证据。原全量XML含JWT形内容，只保留本机原件和归档哈希。

## 交接与证据
详情 `docs/handoffs/2026-09-25-backfill-302132-main1751-continuation.md`；归档 `docs/verification/2026-09-25-backfill-302132-main1751-continuation/`（2738份；批11-20共138请求）。动态 `~/.finance-runtime/reviews/backfill-302132-0923/CURRENT.json`；文档提交/远端SHA以该指针最终核对为准。
