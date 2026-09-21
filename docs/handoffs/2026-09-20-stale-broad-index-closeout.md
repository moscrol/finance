# 2026-09-20 旧工作推进：宽基指数

## 身份与授权边界

用户在只读遗留盘点后要求“你来推进执行”。本轮认领代码收尾、作者离线验证、提交/推送/PR与接替记录；不合main、不删除旧目录、不采真实行情、不回补数据库、不切8792、不调模型/付费外审。

从gitea/main `728f327160bbd2485cb635e7ef09d040d718d7b5` 隔离开 `fix/broad-index-closeout-0920`，代码 `d4d944cb67f9a91380949e18c33d28e22c3a0c00`，PR #806。主检出及旧树的他人改动均不触碰。

## 发现顺序与选择

1. 保全 `/Users/a77/fwp-wt-broad-index` 三个未提交文件差异，随后按当前实现前向编写，不复制旧交接的验收结论。
2. 旧代码新增两个宽基指数，但也把供应商Unknown thscode异常当空返回。后者会混淆“供应商拒绝”与“确无数据”，不接受。
3. 增加full/incremental请求、实际落行与指标值断言、维表名称保留/刷新，以及Unknown/429/401传播断言。未修实现3F4P；根因是两模式缺指数及NULL覆盖维表名。
4. 增加000688.SH科创50、000016.SH上证50和名字映射；维表upsert使用COALESCE保留旧名。不添加899050.BJ，不改变异常语义。
5. 五文件回归139P，提交后同环境重复139P；Ruff全仓、提交门禁与精确SHA收据校验通过。

| 方案 | 处理 | 理由 |
|---|---|---|
| 整枝或原补丁直接合入 | 否决 | 旧实现包含吞异常，旧收据也不属于当前基底 |
| 仅保留代码清单、不验落行 | 否决 | 不能证明请求、维表和行情值真正接通 |
| 两指数+保名+异常反例的窄修复 | 采用 | 不改采集链/供应商权限，能独立核验 |
| 立即回补旧交接窗口 | 否决 | 未获生产操作授权，今日数据状态未查 |

## 证据

根目录 `/Users/a77/.finance-runtime/reviews/stale-work-closeout-20260920/`。

- `source-backup/broad-index.patch` SHA-256 `2e56e2e20a8844c3204ab3b6e8504e8f0e674a3336370f0e45e3eb3ba773b3d4`。
- `results/broad-index/red/` 为反例，`green/` 有一次不存在文件路径导致exit4/零执行，不算通过；`green-corrected/` 为修正后的139P。
- `results/broad-index/fixed/` 为上述代码SHA的139P。前后完整HEAD相同、status为空；receipt严格校验通过。
- 仓内原字节日志、收据、运行器副本见 `docs/verification/2026-09-20-stale-broad-index/`。文档提交不继承代码SHA签字；PR评论承接后续tip的实际复跑。
- 白名单环境 `env -i`、umask022、主树`.venv-workbench/bin/python`；用户/episode/临时目录隔离，DB指向不存在的测试路径。复用既有receipt_redirect只改收据落点，不改测试/断言。首轮red收据曾写共享目录，未声称全程收据隔离。

## 其他旧工作的明确去向

| 旧工作 | 本轮处置 | 尚未完成 |
|---|---|---|
| capability-wiring三个尾提交 | 413b7a07的生成降级净增量由#805承接 | 6c7bea6e材料证据/重算与两参表格另列；e8a63007历史交接保留，不当已吸收 |
| 旧ResearchJourney前端 | 保留19处脏状态，不整枝合，不冒认负责人已接受 | 需对照当前UI认领净增量和构建产物；不是持续研究项目后端 |
| fupanhui-session-hygiene | 保留旧方案；不切默认CDP、不改launchd | 核当前采集策略/429保护后决定前向移植或封存 |
| capability-benchmark-00 | 保留历史HOLD，不恢复真实评测 | 当前版本/账户/预算重新preflight，人工评审及after未完成 |
| technical-daily / wiki-hybrid-25s | 沿22:44只读报告记录“已有接替形状” | 尚未逐尾提交证明完全吸收，不能删树 |

这不是清理白名单。16个无效Git登记与其他干净/脏旧树本轮均未删除。旧资料、ignored内容、活动引用、恢复锚和reflog仍须逐项审计。

## 后续验收

本轮139P是窄回归，不是全量Python/前端/E2E/跨仓registry或独立QC。合main前对最终tip补适用准入并取得用户确认。实际供应商字段、20日跨源差值、今日生产覆盖与回补需另获授权；采集写入只走daily-full，不依据09-08历史996行结论自动执行。

工具沉淀：复用现有receipt checker、Gitea PR工具及receipt重定向器；本轮runner仅为固定环境和原始证据留存，不另造生产写链、定时任务或通用框架。没有修改harness-reference的必要。
