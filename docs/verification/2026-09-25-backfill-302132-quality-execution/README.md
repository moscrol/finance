# #813：Quality执行证据与终稿拒收

后续有界批次04-06另见 [`2026-09-25-backfill-302132-quality-continuation/`](../2026-09-25-backfill-302132-quality-continuation/)，旧398份原件与本归档不改写。

状态 **SPEC_SCOPED_DELIVERED_QUALITY_FINAL_REJECTED**。固定3c5/base4cc，封存观测main033，PR评论6911发布时已前进至d21707ca6；新组合未验，不是全候选、合入或生产批准。

- 39模型请求（4+17+17+1），仅Quality轴，无自动重试，均已结束。
- 新审查会话复跑给定探针7P，给定断言源/宿主夹具修正来源明确，不算本轮新写七例。
- 新写套件1P/1F：窗后stock_name置NULL被正确拒绝；窗前行变异因fixture无对应行而失败，未验证产品路径。
- 真实deliver_stage终稿被原门拒收：对照不是第一条bash、positive_control.status缺失、未修失败仍报PASS_WITH_LIMITS。报告C3保持not_verified，计数未虚报，不能因其它字段正确而批准。
- 宿主补齐baseline/clone的合成窗前行及收据SHA后，先基线1P，再完整3P，原审查两个断言不变；不移签入独审。
- 来源计数正确。辅助检查器将supplied_xml路径后的注释误判为错误，保留原件并另留澄清；这不是审查者错误，不改变三项真实拒收理由。

原件 **398份 / 2,076,035字节**，逐项原字节SHA/编码在manifest。XML/日志等可逆Base64，脚本可逆文本，验收器输出JSON也保留。排除临时合成DB、用户目录、缓存、凭据存储和软链。旧批不改写。

入口（均在 `raw/pr813-glm-qc-20260925-03/`）：

1. `report.json`：宿主总账，非独立判词。
2. `quality/report/parsed.json`：被拒收的真实原终稿；`quality/host-evidence-audit.json`：三个原门理由。
3. `quality/execute/commands/004-bash/` 与 `011-bash/`：给定7P、新写1P/1F的原始命令/输出；XML在quality/work。
4. `provenance-audit.json` 与 `provenance-clarification.json`：给定和新写计数、源未修改、注释误报澄清。
5. `host-earlier/receipt.json` 与 `host-earlier/work/probes/test_earlier_fixture_adapter.py.txt`：修夹具后的独立宿主诊断，不是reviewer通过。
6. `acceptance-json/` 与 `host-earlier/acceptance-json/`：真实验收入口的结构化输出。

详见 `../../handoffs/2026-09-25-backfill-302132-quality-execution.md`。下一轮先离线验证工具入口约束，再继续有界独审；前置硬约束本轮未实施，不能称已修。
