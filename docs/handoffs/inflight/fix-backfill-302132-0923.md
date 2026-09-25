# #83 / PR813

## 这个分支做什么
302132固定范围回填整合。文档树代码旧，不从本树验收或生产。

## 当前状态
**ENGINEERING_PASS_QC_PASS_WITH_LIMITS_PENDING_PUBLICATION**，尚未合入。PR813远端仍为ae3，继续WIP/open/unmerged；未写生产、未动8792/launchd。
- 最新本地候选 `4f12e65e44600ae2627c0f9e7ab206a14fd6dd13`，树 `/Users/a77/fwp-wt-backfill-ready-main-e159-0925`，已合入 `gitea/main=e159c564440c69abe17f106ae721fd25348a1865`。
- 新候选工程：Python16349P/0F/72S/2X，收集16423；定向118P；前端/E2E完整通过；registry5；完整副本演练37检查通过，生产不变、回滚哈希匹配。收据根 `~/.finance-runtime/reviews/pr813-ready-main-e159-0925/`。
- PR远端head仍 `ae3f812e1c1e142953b657ba41f30fce23e7c14a`；新候选未推送、未冒充PR收据。QC批22 `pr813-glm-qc-20260925-22/` 已接受 `PASS_WITH_LIMITS`，11请求无自动重试。

## 决策与被否方案
保留旧f650结果，main变动后重跑ae3；否决旧绿移签。保留全部失败批次，否决放宽硬门、失败补签及用宿主诊断冲销独审失败。工具是本单证据，不注册成通用产品能力。

## 已验证
ae3干净树：Python16259P/0F/93S/2X；定向118P；前端123P、E2E34P/2S；registry5项与full-scope通过。宿主完整库副本父发布/verify/37检查/错误输入及amount负控/父备份恢复通过，生产演练前后不变。

## 未验证 / 已知边界
批13在f650取得的结果不转签；ae3批14/16-19无合格终稿；批20实际23P/2F，身份失败根因仍未证实，均保留为历史失败。批22绑定4f12/main e159，C1-C7均 `verified`、整体 `PASS_WITH_LIMITS`；25P/0F/0E/0S，C6为六次嵌入作者函数体调用，standalone作者pytest为0。供应探针非模型新写。

## 下一步
批20身份失败诊断仍不可重现，不改guard、不补签；批21的交付拒绝不转签。批22 schema最大4932、16负例通过，报告序列化3620、provenance407。下一步是把4f12候选及QC证据发布到PR并回读就绪状态；在此之前合入/生产均false。生产还需重新冻结、逐字授权、本轮backup与无WAL确认，WAL即停。#802留6446。

## 踩过的坑
16-18首拒收实际是6000字符限额，不是最初判断的claim格式。19来源说明超字段长度；20仍有真实失败。运行根ready-only脚本未执行，不是就绪证据。原全量XML含JWT形内容，只保留本机原件和归档哈希。

## 交接与证据
详情 `docs/handoffs/2026-09-25-backfill-302132-main1751-continuation.md`；归档 `docs/verification/2026-09-25-backfill-302132-main1751-continuation/`（2738份；批11-20共138请求）。动态 `~/.finance-runtime/reviews/backfill-302132-0923/CURRENT.json`；文档提交/远端SHA以该指针最终核对为准。
