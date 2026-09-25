# 输入消费验证：第二轮

日期：2026-09-24。规格：`../../superpowers/specs/2026-09-24-architecture-input-foundation-audit-spec.md`，阶段 B 的离线前置证据，不是 B 完成。第一轮基线保留在 `../2026-09-24-architecture-audit/`。

## 结论

以下生产状态是本报告原采样时的历史结果。09-25续推对readiness探测15秒超时，当前状态UNKNOWN；没有把历史503沿用成当前结论。

| 对象 | 本轮结果 | 证据与边界 |
|---|---|---|
| 生产 readiness | FAIL | 首尾 GET 均 HTTP 503，`missing_critical=[market_data_consistency]`；health 200 不抵消此失败 |
| SPT 原文、批准记录与上下文 | PASS，仅限离线装配 | 50 篇原文；92 approved / 112 rejected；92 条引文逐字核对通过，92 条批准值进入上下文，指定问题召回 3 段原文 |
| 风远批准记录与当前画像一致性 | FAIL，待语义复核 | 24 篇原文；105 approved / 52 rejected；105 条引文均可追到原文，但 10 条批准值已不在当前画像，实际上下文只含 95 条；仍召回 3 段原文 |
| 风远四个可追加字段中的其他条目 | UNKNOWN | 机会偏好 17、风险 14、反模式 11、证伪 10 条没有对应的当前 approved patch 值；可能是种子或人工修改，不能直接认作未授权内容 |
| 生产绑定目录的 09-14 晨汇 | FAIL | 原文/投影存在，标准 sidecar（独立标签库）的标签集合不匹配；见 `briefing-live-0914-final.json` |
| 生产绑定目录的 09-18 晨汇 | FAIL | `No projection rows for 2026-09-18`；KB 已合版本与生产目录不一致 |
| 已合 KB 投影 + 隔离重建标签，09-14 晨汇 | PASS，仅限显式离线输入 | 10 条投影 -> 09-15 标签 -> 半导体长河对象；覆盖率 33.333333；关闭 sidecar 输出不变，严格截止过滤 4 个晚录入教学对象 |
| 同一隔离样本，09-18 晨汇 | FAIL，被市场缺口挡住 | 现有 `fact_market_daily` 日历将 09-19 可用材料落到 09-22；当天六个关键市场字段为空，无相应标签。该日历不是完整交易日历的认证 |
| 新模型消费、真实回答质量 | BLOCKED | 未调用模型，未伪造 Episode；仍按 #76 前置与预算授权执行 |

SPT 的 PASS 不证明人工审批权属、手工框架字段、方法卡生成过程、模型真正用对或金融效果。风远的差异也不证明之前审批违法：可能有人有意删除/改写，必须核对变更历史，禁止自动重新应用。

## 身份与无副作用边界

- 用户：启动器真实默认账户 `linxiaoqi5111`，用户根 `/Users/a77/.local/share/finance-workbench/users`。未写用户目录。
- 生产版本：`3b7e473575b0ff2dea3c1088ba7b5e330e95c8e4`，见 `health.json`；此轮三份视角读取模块与生产部署文件 SHA-256 相同，见 `perspective-code-hashes.txt`。相同代码不等于真实请求消费。
- 审计脚本在本分支执行。视角 JSON 的 `audit_revision` 是运行时分支 HEAD，不代表当时未提交的审计脚本已经在该提交；精确脚本身份以 `audit_script_sha256` 为准，读取模块另有 `code_sha256`。
- KB 隔离输入固定为 `a2cfb2b8d963eec91850499788225476e4fe1776` 的 `wiki/raw/theme-radar/opinion-store/briefing-tier-events.jsonl`，由 `git archive` 导出，未带入主工作区脏文件/冲突。该提交含 09-15/18 原文，生产绑定目录尚未发布；相关提交见 `briefing-unpublished-commits.txt`。
- 临时目录 `/tmp/architecture-consumption-0924-a2cfb2b8/`，只在其中新建 `history_labels.duckdb`。生产行情库连接全部 `read_only=True`，生产标签库也只读。`db-identities.txt` 是结束时文件身份，不声称有前后哈希封印。
- 隔离构建只带晨汇投影，未带卖方 `opinion-events.jsonl`，构建记录中的卖方 missing 是样本边界，不是本轮发现的生产故障。标签声明计算时间固定为 `2026-09-24T13:45:00Z`，不是原材料可知时间。
- 未补生产数据、换库、重启、部署、重建 RAG 索引、恢复采集或批准方法规则。没有全量发布门禁和跨日观察。

## 修复与反例

1. 新增 `scripts/verify_perspective_consumption.py`，只调用既有视角读取器。核对用户/视角路径、原文、批准历史、逐字引文、当前画像、上下文；保存计数、ID、哈希，不保存原文和完整提示词。逐条差异保留；未知人工条目明确排除在 PASS 范围之外。结束再次核对输入哈希与补丁集合，若期间被其他会话改动则失败。
2. 修复既有 `verify_briefing_consumption.py` 的两处验收偏差：漏读构建器使用的 RPS5（近五日涨幅排名）板块名；遗漏写入端保留六位小数的合同。复用原加载器与 `SCALAR_DECIMALS`，不用宽泛误差阈值。`33.333333` 通过、`33.333334` 拒绝，NULL 仍不等于零。
3. 旧验收器对真实隔离数据先报覆盖率错误。测试复现见 `briefing-verifier-red.txt`（漏输入）和 `briefing-rounding-red.txt`（精度）；写入/预期值见 `briefing-ranking-diagnostic.json`。
4. 初次重跑使用 `--entity market`，但长河只解析当日存在的板块实体，故出现 `Briefing missing from river slice`。这是本次探针参数错误，不记作运行时缺陷；最终使用确实存在的 `半导体`。保留此前输出，不用后来的 PASS 覆盖失败过程。
5. 定向回归 137P、Ruff/diff-check 通过。覆盖视角负例、晨汇有效/错误/缺失覆盖率、审批漂移、并发输入变化、用户隔离，以及第一轮 103 项回归。`targeted-regression.txt` 来自含本轮改动的树，不是干净提交的发布收据。

实现提交 `7863fa12583e9da3f106176fcb838c41a3dd6258` 后，在干净树再次运行同组测试：137P/0F/0S、exit 0、`dirty=false`。收据 `clean-targeted-receipt.json` 仅绑定该实现提交，不移签给后续交接/文档提交，不替代完整发布门禁。

## 下一步及归属

1. #61 / release owner：处理市场身份与范围、关键字段、日历缺口。09-22 缺 `sh_week_ma / sh_deviation_pct / total_amount / amount_ma20 / amount_vs_yesterday_pct / top3_industry_ratio`，不能只看日期有行。原诊断见 `briefing-isolated-gaps.json`。
2. KB / #87 owner：将固定且批准发布的正文、投影、索引部署为同一版本；用正确市场输入重新构建 sidecar，再跑本验收器。隔离成功不是直接把临时库拷到生产的授权。
3. Perspective owner：按 `perspective-fengyuan.json` 的十个 patch ID 查清删除/改写意图，另审无 patch 票据的人工条目与结构化框架。应保留的才重新审批；应撤回的补齐撤回/替代记录，审计分支不代批。
4. 生产和预算前置满足后，按规格执行六类输入及纠正/跨用户两例真入口消费。卖方、Knevo 仍沿原 owner 在途工单推进。本轮不声称它们的新生产验收已经完成。
5. 用户纠正台账 → `memory_lookup`、跨用户隔离与撤回的离线前置见 `docs/verification/2026-09-25-user-memory-consumption/README.md`。只证明当时已有台账读取链，后续写侧/自动预取另见下一项。
6. Workbench P0纠偏写侧与P1记忆开口读侧已在审计分支完成临时根验收（`9533417c3`，干净641P）；下一轮首请求可自动收到新写的相关纠偏，空/超时/失败分别为缺口。见 `docs/verification/2026-09-25-workbench-correction-ingest/README.md`。这是无模型装配/送达PASS，真实模型采用和金融质量UNKNOWN；未合main/部署。随后`3047cb1ee`补进程内HTTP入口三场景，干净794P；另开空会话排除历史回显，核对同用户/跨用户/撤回及Episode身份哈希，范围与主干漂移预检见同一纠偏报告，不签真实网络或浏览器UI。

## 精确重跑

在本工作树根执行；所有生成标签命令只能指向新建临时目录：

```bash
PY=/Users/a77/finance-workspace-private/.venv-workbench/bin/python
DB=/Users/a77/finance-workspace-private/db/market_feature_store.duckdb
TMP=$(mktemp -d /tmp/architecture-consumption.XXXXXX)
git -C /Users/a77/knowledge-base-private archive a2cfb2b8d963eec91850499788225476e4fe1776 wiki/raw/theme-radar/opinion-store/briefing-tier-events.jsonl | tar -x -C "$TMP"
"$PY" scripts/teaching_framework.py build-labels --db-path "$DB" --labels-db "$TMP/history_labels.duckdb" --kb-wiki "$TMP/wiki"
"$PY" scripts/verify_briefing_consumption.py --db-path "$DB" --labels-db "$TMP/history_labels.duckdb" --kb-wiki "$TMP/wiki" --briefing-date 2026-09-14 --entity 半导体
"$PY" scripts/verify_briefing_consumption.py --db-path "$DB" --labels-db "$TMP/history_labels.duckdb" --kb-wiki "$TMP/wiki" --briefing-date 2026-09-18 --entity 半导体
"$PY" scripts/verify_perspective_consumption.py --users-root /Users/a77/.local/share/finance-workbench/users --user linxiaoqi5111 --perspective sptfei --query 'SPT如何判断主线强度和分歧转一致，出现什么信号应证伪？'
"$PY" scripts/verify_perspective_consumption.py --users-root /Users/a77/.local/share/finance-workbench/users --user linxiaoqi5111 --perspective fengyuan --query '风远如何判断行情退潮和亏钱效应，什么条件下应降低仓位？'
"$PY" -m pytest -q tests/test_verify_briefing_consumption.py tests/test_verify_perspective_consumption.py tests/test_daily_ops_ledger.py intelligence/tests/test_rag_readiness.py intelligence/tests/test_perspective_lab.py intelligence/tests/test_perspective_learning.py intelligence/tests/test_userspace.py
```

视角脚本 PASS=exit 0、FAIL=exit 1；晨汇额外保留 BLOCKED=exit 2。临时库可消失，重建须按上述来源重新生成，不能依赖本机临时文件永久存在。重跑读取的是届时的生产行情，结果可能改变，不能移用本轮收据。
