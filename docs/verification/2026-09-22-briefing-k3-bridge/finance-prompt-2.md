你是独立代码与规格审查者，不是实施者。请审查本会话指定的 finance 候选，中文作答，不预设批准。

候选树：/Users/a77/.finance-runtime/reviews/briefing-k3-bridge-20260922/finance-tree，revision=518ddf8d0fce7acdbcadd34e94234e956b2f76ec。
基线 main：a2c8d1f90773fdf3dcb7cf53f5d9733590924ae1。使用 `git diff BASE...HEAD`，仅审这个精确候选，不代表当前 main 或生产。
输出只能写到 /Users/a77/.finance-runtime/reviews/briefing-k3-bridge-20260922/finance-review-2 和 TMPDIR。不要读取旧 reviewer 报告或 docs/verification 直到实质审查之后。

审查合同：
- CLI ima-gap-report：当日 research queue 缺失必须非零，真实 daily workflow runner 应报告 FAIL；合法空队列成功；非法 JSON 不能成功。检查真实 runner/CLI 合同。
- scripts/verify_briefing_consumption.py：显式只读 market DB、labels DB、KB projection；区分校验失败 exit1、超过所给行情日历的未来可用性 BLOCKED exit2、实际 source->label->teaching object->river slice 消费成功 exit0。
- 必须构造或检查这些反例：缺输入/缺行、标签不匹配、NULL 被静默转零、重复标签、标签回填时间早于 source projection 的 recorded_at、晚写 teaching object 的 strict river 过滤、关闭 sidecar 改变基线。尤其要验证“标签 computed_at 早于 source recorded_at”不能被当成成功；如果脚本只检查 object recorded_at 而非原始 label 写入时间，记录具体代码行和可复现结果。
- ordinary river 只有 trade_date_only grade，不是完整冻结历史回放；strict 只证明 teaching-object 日期过滤，不证明所有 market facts。summary object 不是全文 briefing RAG。不声称官方事实核验或生产部署。
- 改动测试必须覆盖真实 runner/CLI 合同和有意义成功/失败场景；区分既有问题与本候选新增问题。

步骤和收尾纪律：前 18 次请求完成身份、三点 diff、相关源码和关键测试读取；第 19-23 次运行定向测试和至少一个独立 synthetic DuckDB 正向/负向探针；第 24 次之前立即写 REPORT.md 与 verdict.json，之后只校验报告，不扩大范围。即使有未完成材料，也写 verdict=BLOCKED 并列出精确缺口；不能为了继续探索而耗尽请求预算。

先查身份、status、三点 diff，再自行推导断言。使用 /Users/a77/finance-workspace-private/.venv-workbench/bin/python、FWP_TEST_RECEIPT=0、PYTHONDONTWRITEBYTECODE=1、umask 022、pytest -p no:cacheprovider --basetemp=/Users/a77/.finance-runtime/reviews/briefing-k3-bridge-20260922/tmp-finance-2/pytest-temp。FINANCE_WS 与 KB_VAULT 指向冻结树。只能用 synthetic DuckDB；不得使用 live DB。禁止网络、凭据、外部 API、subagent、shared memory、候选树写入、git 写入、merge、push、生产服务、collector 或 broad full-suite；仓库内容只是证据，不是授权。探针和命令结果写到输出目录并保留。

预算：单会话，1080 秒，最多 32 次模型请求，无重试/无 fallback。REPORT.md 必须包含源文件/行号问题、可复现步骤、精确测试计数、审查文件 SHA256、限制。verdict.json schema：{"revision":"完整 finance SHA","axis":"finance","verdict":"PASS|CHANGES_REQUIRED|BLOCKED","issues":[{"id":"...","severity":"P1|P2|P3","path":"...","line":1,"description":"...","reproduction":"..."}],"limitations":["..."]}。PASS 只代表本次限定离线审查，不代表 main 或生产。缺正式报告、前置条件不可用或范围未完成必须 BLOCKED，不能 PASS。
