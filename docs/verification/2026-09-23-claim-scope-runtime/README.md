# Claim-Scope Runtime: #890

## 身份与结论边界

- 固定候选：`2be85e64eeaffc6e37b66898ecc1a740acd6a7fd`。
- Git tree：`cd5ff0b865e823fd3cc5a26555cb25ce81d66ae0`。
- 基线：`f47d464eb7af32157c331bf2a6bf1b337acbb43f`。
- PR：[WIP #890](http://127.0.0.1:3300/a77/finance-workspace-private/pulls/890)。没有合入或部署。
- 原件根：`~/.finance-runtime/reviews/claim-scope-runtime-20260923/`。
- 授权：pi 会话 `01a0cbdf-8033-71c3-9314-9cf6c26bc033`，消息 `a7d8d0e6`；原话与此前有条件合并授权见原件 `protocol.json`。

**不能把文档后续提交、历史 #888 收据、作者工程测试、K3 独审、自然金融质量四者互相代签。** 以下完整门禁只绑定上述固定候选，不绑定本报告后续提交。

## 工程验证

首轮完整门禁 **RED**：Python 14641P/2F/85S/2X，Ruff通过；前端120P、E2E34P/2S、registry5/5与身份校验通过。原件为 `gates/`、`gate-runner.log`、`audit.json`、`artifact-manifest.json`，不覆盖。

两红均在本次接入面：`test_terminal_publish_paths_claim_before_public_artifacts` 抓到 B 私有收据在终态认领前落盘；`test_public_answer_assignments_all_go_through_view` 抓到只读观察参数也叫 `public_answer=`，与公开赋值门禁冲突。返修把落盘移至认领成功之后，只读参数改名 `delivered_answer`，没有放宽或白名单化门禁。增强后的真实 Workbench 测试在旧冻结代码上恰好1红，在返修相关7模块上483P，Ruff/diff通过。前者是作者回归阳性对照，不冒充 #75 独审阳性对照。

返修后的完整复验另起 `retry-01/`；其 revision、完整结果与依赖指纹只认该目录生成的收据，不借用首轮身份或预写通过。该目录的 `gate-runner.log`/`audit.json` 是本报告之后的活动检查落点。

开发期定向 110P、扩大相关模块 498P、专项 22P，只是作者开发读数，不替代当前 clean revision 完整门禁。

固定候选的 `frozen-parity/manifest.json` 记录两份旧答卷重放：材料1条、行情3条；typed runtime 映射与 CLI 全字段一致，四个已知越界仍被检出。`claim_scope_census.py` 实际读入这2个显式产物，advisory 2、命中2、degraded 0、四类各1，见 `census-frozen-controls.json`；分母是两个已知失败控制，不是线上覆盖率或召回率。没有模型调用；这不是新金融答案验收。首轮开发夹具漏传 `task_frame_hash` 的失败保留，不改写成产品缺陷。

## #75 独立审查

结论：`BLOCKED_REVIEW_NO_OUTPUT`，不是 PASS / 无发现 / CHANGES_REQUIRED。

| 阶段 | 状态 | 原件 |
|---|---|---|
| explore | 208.492秒，第9次预占请求报 `Request timed out.`；未交付探针和终稿 | `qc/k3/execution.json`、`events.jsonl`、`request-admissions.jsonl` |
| execute | 前置阻塞，未派发 | `qc/report.json` |
| report | 前置阻塞，未派发 | `qc/report.json` |

本轮上限600秒/40请求，未触总帽；未得到 HTTP 状态码，不猜测429/504。`pi exit=0` 与模型错误同时出现，以模型错误和缺少产物判阻塞。9次审查请求预占与1次网关小载荷探测分账；预探测200/READY约4.9秒不算审查通过。候选和输入前后未改。

作者测试与审查探针分账：审查探针执行 **0**，阳性对照 `assert 1 == 2` 未交付、未执行，`NOT_EXERCISED`。`qc/spec/`、`quality/`、`probes/` 内的 README 是控制器的缺失状态记录，不是假造的审查者报告。没有自动重试。

## #76 L5

结论：`BLOCKED_CANDIDATE_NOT_ACCEPTED`。两道原题各首发0、重发0、续问0；未启动旁路实例、未冻结数据、未取得 judge/marker/new-answer 收据。原件 `l5/audit.json`。

本轮已按 schema 修正条件卡的旧列名为 `stock_ts_code / sector_ts_code`。实际全集数仍须按答案实际日期查冻结库，本轮未查询，不沿用旧20。K3实际路由和凭证解析方式、候选已内置剥除 temperature 是否代替旧外置 shim，均须在首发前明确写入协议，不能事后补签。

## 生产

只读复查 `8792`：`source_revision=3b7e473575b0ff2dea3c1088ba7b5e330e95c8e4`、clean、`code_matches_repo=true`、`continuous_glm / glm-5.3-flash`。health healthy，但 readiness not_ready，唯一缺项 `market_data_consistency`：该接口报告主库日期2026-09-22、行情快照日期2026-09-23。快照自身合约PASS，不能替主库与快照日期一致性签字。

原件 `production-health-postcheck.json`、`production-readiness-postcheck.json`。本轮未改生产、未部署、未重启、未切模型、未改判官档位、未回填数据。这里只证明声明字段的观察，不声称全系统零副作用审计。数据一致性需独立恢复；不能靠换代码掩盖。

## 接手顺序

先确认 `retry-01/` 固定返修候选的完整门禁，再在新的明确预算下完成 #75 三段；候选或主干漂移时仍须重验；再按 L5 条件卡执行两个原题；只有全部通过且生产 readiness 恢复，才允许按授权部署。任何阶段阻塞均不得带红合入或部署。#883/#888 历史收据与失败现场保留。
