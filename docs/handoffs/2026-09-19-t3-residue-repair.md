# T3 残余反例修复 · ARL-0005 五类线索（2026-09-19 晚）

## 结论与身份

**工程全绿，仍 hold：没有新的有效独立裁决，真实金融会话与市场取数仍为 0。** 上一窗留红的五类线索已在原 q 线修复并转成回归，同一份量具从 d46 的 4P/10F 变为 14P/0F。

- 业务提交 `6fb37a6e191185daef832369677af15b0d56afb2`，父为文档 tip `81cbbec7`；上一业务 `d46c2c3b`。改动 3 个文件、184 行增 11 行删：`intelligence/services/research_delivery_checks.py`、`intelligence/tests/test_research_delivery_ratio_boundaries.py`、`scripts/review_probes/research_delivery_mutations.json`。
- 只读量具 `scripts/review_probes/check_ratio_review_residue.py` **未改**（SHA `34ea6608…`），所以红绿对照共用一份探针字节：d46 4P/10F/exit1 → 6fb37a6e 14P/0F/exit0。
- 冻结候选 `candidate-6fb37a6e` 18 项检查全部 exit 0，前后树状态与三仓 registry 状态一致：ruff、全量 pytest（12259P/0F/87S，日志另有 2 xfailed，收据 `20260919T144656Z-6fb37a6e.json` 干净树、drift 0）、前端 lint/typecheck/test/build、e2e、固定三仓 registry 五项（kb `1254224b`、finance-research-site `f6065838` 钉住）、旧三探针 6/4/16、新量具 14/0、52 组撤保护（新增 6 组各自独立红，基线与还原各 687）。
- 未开 PR、未合 main、未部署；8792 仍 `bf662e93`；夜跑、KB 防写、他人树、shim 封存未动；0 次模型调用。

## 五类修复（输入 → d46 行为 → 6fb37a6e 行为）

| 输入 | 来源 | d46 | 6fb37a6e | 规则改动 |
|---|---|---|---|---|
| `2026中报含金量为1.588，同比增长12%。` | 外审原句 | 12% 被残余扫描当未定位比率，误降 partial 并续修 | 无 finding、completed、正文不变 | 带增减词的 `%` / `bp` 是变化率，不是比率水平 |
| `2026中报含金量为1.588，样本量120。` | 外审省略前缀，作者补全 | 120 误报 | 无 finding | 带计数标签（样本量/家数/N=…）的数是独立事实 |
| `2026中报含金量实际为158.7bp。` | 外审原句 | `bp` 落在「非比率后缀」表里，静默 completed | mismatch，158.7bp 换成待核对，partial + 续修 | `bp/基点` 进值槽单位表，与「个百分点」同为差值量纲，任何标量都不认证；表格同口径 |
| `收入可核[E1]，2026中报含金量待核对；该比率为1.587。` | 外审原句 | 分号后「该比率为」不在连接词表，1.587 漏检 | mismatch，1.587 换成待核对，[E1] 保留，partial + 续修 | `该比率为` 进有限连接词表；值前缀改为从同一表推导，避免「拼上了却没消费」 |
| `〔比率对应关系**待核对**〕2026中报含金量为1.588。` | 外审只给标记片段，作者补匹配期别值 | 去格式视图认出旧标记，raw 视图再插一个普通标记 | 零宽 finding，第一次局部编辑不改字节，去格式后恰一个标记，仍 partial + 续修 | raw 视图判「已标记」时先去掉 Markdown |

成对控制同批入库：未标注的 `另有120 / 另有12% / 另有15bp` 仍报未定位；`该比率为1.588` 正确值不误报；`待核对。该比率为1.587` 跨句号不继承；`同比增加15bp[E1]` 独立保留；表格 `1.588bp` 单元格报错。

## 明确不覆盖

- 跨句号的指代（`待核对。该比率为1.587`）不继承，与既有「不跨句号猜归属」一致。
- 未带增减词或计数标签的邻数仍是未知，不做全豁免。
- `含金量同比增长12%` 没有值槽也没有残余水平，不出 finding，交原语义核验。
- 表头里的 `bp` 不解析为单位（单元格仍按裸数比较，因而照旧 mismatch）；`2025中报该比率为0.288` 中「该比率」不是比率名，不检查（既有边界）。
- 工程绿不等于外审批准或自然回答质量；judge=llm 仍是确定性成功替身。

## 决策对比

| 方案 | 评价 | 结果 |
|---|---|---|
| 相邻数字全豁免 | 会放过 `另有1.587` 这类真错值 | 否；只豁免带增减词的 %/bp 与带计数标签的数 |
| bp 按 1/10000 换算后比较 | 158.7bp≠1.588 也能抓到，但 15880bp 会被认证成正确 | 否；bp 与个百分点同为差值量纲，一律不认证 |
| 通用指代解析「该…为」 | 会猜主体 | 否；只把 `该比率为` 加进有限表，前缀与连接词共用一处定义 |
| 重写编辑视图统一去格式 | 改动面大，坐标映射已有测试 | 否；只改「已标记」判定那一处 |
| 修完立刻再发外审 | 期限/预算/独占根须用户明确 | 否；本窗只做工程与留证 |

## 证据与复跑

运行时根 `~/.finance-runtime/convergence-20260919/retention-repair/`：`candidate-6fb37a6e/result.json`（总表）、`candidate-6fb37a6e/mutations/results.json`、`residue-repair-01/probe-6fb37a6e-*.json`、`residue-repair-closeout-outcome.json`（本窗总账）。逐字节归档 `docs/verification/2026-09-19-t3-residue-repair/`（manifest 303 件 / 2,507,608 字节，历史五份归档 2594 件核对未变）。

```bash
umask 022
cd /Users/a77/fwp-q-research-data-readiness   # 需干净且恰为 6fb37a6e
PY=/Users/a77/finance-workspace-private/.venv-workbench/bin/python
for f in check_delivery_fact_retention check_ratio_hedge_delivery check_ratio_scope_boundaries check_ratio_review_residue; do
  env -i HOME="$HOME" PATH="$PATH" LANG=en_US.UTF-8 FORESIGHT_LLM_KEYCHAIN=0 \
    $PY scripts/review_probes/$f.py --code-root "$PWD" --expect-revision 6fb37a6e191185daef832369677af15b0d56afb2
done   # 预期 6P / 4P / 16P / 14P，exit 0
$PY scripts/review_probes/run_extraction_mutations.py --suite research-delivery \
  --revision 6fb37a6e191185daef832369677af15b0d56afb2 --output <新目录>   # 52 组
```

## 质检顺手处理

- 上一窗交接与归档 README 补记：请求 SHA 不变，但提示 SHA `a002a150…→a087adcb…`、适配器 SHA `793012a0…→b3a8431e…`；「2 xfailed」只在日志行。
- 共享 `.git` 里 61 条指向已删目录的 worktree 登记已 `git worktree prune --expire now` 清掉，q 树与冻结候选登记不受影响。
- 空收据 `20260919T105310Z-d46c2c3b.json`（0/0、exit 0）保留不删（收据目录只追加）；`scripts/check_test_receipt.py` 不拒绝零计数收据，列为后续守卫，不在本分支改。
- `.claude/lessons_learned.md` 新增一条：清单比集合差不比计数、摘要须带身份字段、`git commit -- <paths> -m` 会静默失败。

## 下一步与禁止事项

1. 新外审窗口须用户明确期限、预算与独占根；请求需覆盖到 `6fb37a6e` 的累计 diff，必需清单加入新增测试函数与新量具名。旧 0001～0003 有效 CR、0004 无效 PASS、0005 超时与无效 CR 原件不改，不补造裁决。
2. 有效独立裁决之后，真实 conversations 才验：固定代码、原题、证据、GLM flash/5.3 兜底与预算单独验收；不拿机械绿改写旧 `not_passed`。
3. 合 main、部署、8792 切流、夜跑、KB 解锁、其他 T 线继续另授权。
4. 若再改业务，重冻工程全量、三仓、四探针与 52 组变异；旧收据不移签新提交。
