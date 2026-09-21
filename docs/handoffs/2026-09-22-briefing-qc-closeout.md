# 晨汇补档质检修复与旁路消费验收

## 身份与结论

用户授权推进 finance #837/#839/#842、KB #156 的审查发现；未授权合入 main 或覆盖生产。两仓主检出有其他会话改动，因此独立修复：

- finance `fix/briefing-consumption-qc-0921`，基线 `028a251a1`，代码提交 `a7288f503da5eb6c51eb7da3734512b3ab20767f`。
- KB `fix/briefing-evidence-qc-0921`，基线 `d0caf3114`，内容提交 `0ad67b928c78dd3fc3e344d48c4c311ff12a59f2`。
- 截至本次验收：证据表述修复、退出码修复已完成；09-15 旁路消费通过，09-18 因真实行情日期不足 BLOCKED。不是生产恢复结论。

## 发现顺序与处理

1. 原补档结构可重算：105 份晨汇、1338 行，目标两日新增 25 行。原文与按日归档一致，误名的 09-02 PDF 正文实际是 09-03。结构检查不验证材料所说的金融事实。
2. 两份晨汇将 L3-L4 AI 转述写成宏观决议落地、公司报表兑现或独立证伪。本轮将正文、来源页与索引改为待核归因；保留长鑫原数字但撤回低基数/并表等自行解释；MLCC 18% 分母未明，不与国内总产能 10% 直接比较。80% x 40% x 20% = 6.4% 仅是全球总产能口径的条件算术，不替代真实缺口。
3. 只改 wiki，原始 raw、时间字段及历史日志 #6891/#6892 不改；追加 #6893，页面 revision 2。两份 source 的 `cascade: none` 声明原批次与纠偏批次均不写实体/概念/relations。
4. `ima-gap-report` 原先缺队列打印 `ok:false` 却 exit 0，真实 workflow runner 判 PASS。最小修复为 exit 2；测试从 `build_daily_review_plan` 取实际命令，经 CLI 子进程与 `run_command_step` 验证缺失、合法空、有效队列、坏 JSON。合法空仍 PASS。
5. 新增 `scripts/verify_briefing_consumption.py`，只读显式输入，检查事件聚合、标签值、NULL、河对象、开关兼容性与事后标签的 cutoff 过滤；缺输入 FAIL/exit 1，行情日历不足 BLOCKED/exit 2。不是一套新的生产写入链，也不认证原始金融事实。

## 决策与被否方案

| 选择 | 被否方案 | 理由 |
| --- | --- | --- |
| 保留材料数字及待核状态 | 自行换成推测正确数字 | 没有一手来源，纠偏不能制造新事实 |
| 修 CLI 退出合同 | 泛化修改整个 runner | 缺陷已在具体命令定位，控制影响面 |
| 生产行情只读、独立旁路库 | 覆盖共享教学库或更新脏 KB | 避免扰动其他会话，部署需另授权 |
| 从页面重建 JSONL | 手改结构化事件 | 页面是唯一来源，保证确定性与可复算 |
| 保留未知值 NULL | 用 0 填无盘面 | 未验证不等于零个或已证伪 |
| 如实 BLOCKED | 补假行情行或提前可知时间 | 历史验收不得通过数据穿越刷绿 |

## 真实消费证据

由正式 `scripts/teaching_framework.py build-labels` 读取生产 `fact_*`，显式写入独立的 `history_labels_final.duckdb`；不传 `--computed-at`，实际构建时刻为 `2026-09-21T16:27:19`。425 个市场交易日，415 个可用日，63495 标签行、6997 缺口行；缺口总数不是失败数。

- 09-15 材料最早可知日 09-16，落在 09-16。T1/T2/T3 = 0/6/6，dimensions=2，market_confirmed=NULL，lag=5。
- 通过 `slice_river(..., entity="算力租赁", teaching_labels_db=...)` 读到 `history_teaching_labels:2026-09-16:market:briefing`。关闭旁路参数输出相同；`require_strict=True` 过滤 3 个晚写教学对象。
- 普通切片 `pit_grade=trade_date_only`。本轮未使用冻结行情快照；只证明晚写教学对象过滤，不证明所有盘面历史值未被后修订。
- 09-18 材料有 13 条、available_from=09-19，应落到下一交易日；但真实 market calendar 截至 09-18，故不能验收 09-21 标签或河对象。没有补造 09-21 行。
- 长河目前只读市场级统计，不把逐条风险说明/正文放进 `teaching_briefing`；全文检索与语义索引发布另算。

机器收据：`docs/verification/2026-09-22-briefing-consumption/river-acceptance.json`，命令 exit 2。运行产物在 `$HOME/.finance-runtime/reviews/briefing-consumption-qc-0921/`，最终库 `history_labels_final.duckdb`，构建输出 `build-labels-final.json`。首次试跑 `history_labels.duckdb` 使用手填时间，不作为正式时间证据；`history_labels_actual.duckdb` 是中途版本，最终以 final 为准。

投影 SHA-256：`037655781b50e841d1991f5a27a8f5fba76e17cd6b5360447245c5d4a0d51d7a`。

## 复跑

在 finance 候选工作树运行。`PY` 取主检出的 `.venv-workbench/bin/python`，`MARKET_DB` 指真实只读行情库，`KB_WIKI` 指已核修订的 wiki，`LABELS_DB` 必须是独立输出，不能指共享生产教学库。

```bash
"$PY" scripts/teaching_framework.py build-labels \
  --db-path "$MARKET_DB" --labels-db "$LABELS_DB" --kb-wiki "$KB_WIKI"
"$PY" scripts/verify_briefing_consumption.py \
  --db-path "$MARKET_DB" --labels-db "$LABELS_DB" --kb-wiki "$KB_WIKI" \
  --briefing-date 2026-09-15 --briefing-date 2026-09-18 --entity 算力租赁
```

构建日期不能倒填。行情补齐后必须重建标签，旧文件存在不能证明读过新输入。

## 门禁与边界

- finance 干净代码提交 a7288f503：80 passed / 7 skipped；完整命令、解释器及依赖指纹在同目录 `targeted-tests.json`，不是全量合并门禁。
- 7 skipped：河对象测试 1 项、cutoff guard 6 项检查工作树内 `db/market_feature_store.duckdb`；隔离树未放真实库，因此跳过。上面的独立脚本用显式真实路径验证了本次消费及过滤，不代签这 7 项。
- 定向 Ruff、两仓 diff check、提交钩子通过。KB 抽取/级联范围测试 16 项通过；抽取 --check 与 1338 行一致、warnings 空。两份 qa_ingest 通过、log hygiene 0 问题。全库 0 错误/2 告警，均为未修改图谱中 28 条链接缺 evidence_layer / fact_hardness；三图谱检查按 cascade:none 明确 SKIP。
- 未跑两仓全量合并门禁、前端/E2E、线上 IMA 搜索全集、生产自然问答或向量索引发布；官方金融事实仍未核验。
- 审查时生产 KB 仍是旧投影、共享 history_teaching_labels 为空，旧夜跑代码与入口未证明消费新晨汇。此处只保留当时观察，不代替部署前复查。#827 配置部署不等于执行，不能沿用旧失败或配置收据推断今日恢复。

## 下一步与工具沉淀

先做独立审核与候选合流后的全叶门禁；用户确认后才合 main。部署另核干净 KB 版本、实际运行代码、教学库绑定和行情新鲜度；数据更新只走既有 daily-full，再以真实时间构建标签并复跑验收。不要改别人的脏主树，不凭 PASS 更新生产成功位。

重复人工消费检查已落脚本及失败测试；跨项目方法复用现有 `gate-covers-only-its-return-value`，不新增第二套工具清单。harness-reference/BUILD.md 当前有其他会话改动，不在本轮改动该仓。
