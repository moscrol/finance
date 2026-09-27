# Claim-Scope Runtime: #890

## 当前结论

[WIP #890](http://127.0.0.1:3300/a77/finance-workspace-private/pulls/890) 未合入、未部署。产品候选 `14f885e01f4a538492b54a27f67ab5d33b58f875`，Git tree `b17c772944ff20c9fe5b0c5a8b642cf3c8c20ed6`。工程完整门禁已绿；续办的 **GLM 独立工程审查 PASS_WITH_LIMITS**；K3 专项金融验收未完成；L5 因数据一致性阻塞，两原题仍各首发0/重发0/续问0。

原件根 `~/.finance-runtime/reviews/claim-scope-runtime-20260923/`。本轮只增加文档，不改产品代码；以下收据不覆盖后续文档提交或与新 main 的组合版本。旧 #883/#888、首轮红、返修绿、GLM 独审和真实金融质量分账。

| 批次 | 固定候选 | 结论 | 原件 |
|---|---|---|---|
| 首轮 | `2be85e64eeaffc6e37b66898ecc1a740acd6a7fd` | 工程RED；K3独审无终稿 | 根目录 `audit.json`、`qc/` |
| 返修 | `14f885e01f4a538492b54a27f67ab5d33b58f875` | 完整工程GREEN；当时独审未派 | `retry-01/audit.json` |
| 本次续办 | 同上 `14f885e01` | GLM独审PASS_WITH_LIMITS；L5 BLOCKED_MARKET_DATA_CONSISTENCY | `continue-01/audit.json`、`artifact-manifest.json` |

本目录 `continue-01/` 留审计与独立报告原样副本，完整事件流/JUnit/探针仍在树外原件根。历史两份 manifest 的39/33个成员已逐个复核不变，本次封存131成员。

## 工程验证

首轮完整门禁：14641 passed / 2 failed / 85 skipped / 2 xfailed；Ruff通过，前端120P、E2E34P/2S、registry5/5通过，整体验收RED。两红均为实际接入问题：B私有收据在终态认领前落盘；只读参数 `public_answer=` 被公开赋值棘轮抓到。

返修把私有落盘移到 `_claim_terminal_run` 成功之后，只读参数改为 `delivered_answer`，不放宽门禁。加强的真实Workbench顺序断言在旧冻结版恰好1红，返修7模块483P。这是作者回归控制，不是独审探针。

固定 `14f885e01` 完整工程：**14643 passed / 0 failed / 0 error / 85 skipped / 2 xfailed**，collected14730，无ignore/deselect、无last_failed、maxfail0；指定解释器与依赖指纹 `3328bed61f3e21ea`、clean身份通过。Ruff、前端install/lint/typecheck/test/build、Vitest120P、E2E34P/2S、registry5/5通过。本次用 `check_test_receipt.py --expect-revision ... --require-full-scope` 复核原收据，exit0，**没有重跑完整门禁**。

两份历史失败答卷在首冻和返修均完成CLI/runtime逐字段重放：材料1条、行情3条；census显式产物2/advisory2/命中2/degraded0。零模型，这不是新金融答案验收，也不是线上召回率。开发夹具最初漏 `task_frame_hash` 的失败原件保留。

## #75 独立审查

### 历史K3阻塞

首冻的K3 explore在第9次预占后 `Request timed out.`，208.492秒，无探针/终稿；execute/report未派，阳性对照NOT_EXERCISED，结论保留 **BLOCKED_REVIEW_NO_OUTPUT**。CLI exit0不改变结论；没有HTTP状态码，不猜429/504，也不移签到返修候选。

### 本次GLM替代审查

用户“继续”后另开 `continue-01/`。K3单次预探测HTTP200但32-token上限下正文为空，记BLOCKED_EMPTY_OUTPUT，**不能据此认定K3通道不可用**。依既有可用通道切换偏好改用 `zhipu/glm-5.3`，修订协议保留通道差异和总预算。GLM单次预探测READY；初版控制器import preflight失败，审查模型请求0，失败现场保留；第二版采用经验证沙箱并加入作者旧证据拒读自检。

| 独立会话 | 请求数 | 耗时 | 产物 |
|---|---:|---:|---|
| explore | 12 | 以execution.json为准 | 原创产品探针、故意失败对照、explore.md |
| execute | 17 | 208.67秒 | 三组分账日志、JUnit、execute.json/md |
| report | 27 | 347.67秒 | spec.md、quality.md、report.json |

三段共56请求；加K3/GLM各一次预探测共58，均未自动重试；总帽121，每阶段600秒及独立请求帽见协议/控制器原件。候选源码只读且前后未变，作者审计/交接与生产数据隔离。控制器从原始HTTP/请求事件计数，不靠模型自报。

- 独立探针：**15 passed**，只执行一次，修正0次。explore概述误写13，execute/report按XML纠正。
- 故意红对照：**1 failed / 0 error**，恰为 `assert 1 == 2`，分类probe_bug，证明装置会报红，不是产品失败。
- 作者测试：**22 passed**，不并入独立探针数。
- 独立裁决：**PASS_WITH_LIMITS**，本范围产品缺陷0；控制器采纳有限工程结论，不将它改签为K3审查或自然金融质量通过。

具体限制：C7只动态验证helper层文本hash，真实A恢复流未独立执行；C8只压到降级管道，B三个真实入口未独立跑全；C9终态落盘时序/败方不写仅独立静态复核，动态证据仍属作者测试。C2序列化条件键、C3零新增IO主要静态复核；C10只有合成产物探针。详细逐主张证据见独立spec报告。

非阻断观察：census遇mode=advisory但缺必需键的输入可能KeyError；独审仅静态推断、未动态触发，当前运行时恒产这些键。本次不改冻结候选。

## #76 L5 与生产

当前 **BLOCKED_MARKET_DATA_CONSISTENCY**，不再是“没有工程独审终稿”。`continue-01/readiness-input-precheck.json` 直接执行候选 `health_ready` 的一致性表达式，使用只读fact_market_daily最新日期和快照校验结果：市场汇总最新2026-09-22、快照2026-09-23，判据false；读取前后DB文件元数据与快照哈希相同。没有冻结数据、没有完整验收readiness，也没有触发候选服务的RAG预热。

两原题仍各首发0/重发0/续问0；未启动L5旁路、未获取L5锁、无judge/marker/new-answer收据。全集须按正式答案日期从冻结库查，不能沿用旧20；条件卡列名已是 `stock_ts_code / sector_ts_code`。

生产8792仍为 `3b7e473575b0ff2dea3c1088ba7b5e330e95c8e4`、clean、`code_matches_repo=true`、continuous_glm/glm-5.3-flash。health healthy，readiness not_ready，缺market_data_consistency；前后七项身份字段一致。本次未改配置/代码、未重启、未回填、未部署；这些观察不声称全系统零副作用。

## 接手顺序

先独立恢复并证明数据一致性，不能重贴日期或自行补生产事实。核对候选/依赖/主干变化；新组合版本须另冻另验，不能用本次14f收据移签。随后明确K3实际路由、凭证解析、temperature剥参路径与judge关闭证明，按L5条件卡两原题各首发1/重发0/续问0。工程、独审、自然质量、readiness、身份及回滚前置全部成立才合入和部署。

授权及早期设计见根 `protocol.json`；本次 `continue-01/protocol.json`、`amendment-glm.json`、`amendment-sandbox.json`。决策背景见 `docs/handoffs/2026-09-23-claim-scope-glm-review-readiness-block.md`。封存脚本使用排他创建，不覆盖重跑。
