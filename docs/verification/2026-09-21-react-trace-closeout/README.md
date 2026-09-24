# PR #809: 三个最小修复的验证与独立复核

固定业务提交 `dda5895aafc88e5fa20632cf4aaefea973940164`，基线 `728f327160bbd2485cb635e7ef09d040d718d7b5`。本页是作者/接手说明，不冒充审核者报告。PR 仍 WIP，未合 main、未部署；8792 仍 `bf662e9310ff751a4c31763815ee78fb7d6d5122`。

## 范围与工程读数

- `fe9a626d`：移植 2841ce66 的 E 引用编号数量隔离。修前 18F/13P，冻结 9/17 原件风险句误拒索引 `[20] -> []`，真实阈值与未知引用门仍在。
- `b1345a7d`：结构化查询安全诊断；真实临时 DuckDB + Episode 脚本反馈测试。修前 3F/9P；两片定向 623P；干净全量 11962P/85S/2X。
- `dda5895a`：移植 365627fd 的 Mapping-only JSON 投影，处理工具错误后的进展记账崩溃。修前 8F/17P，相关 187P。最终干净全量 **11972P/85S/2X**，1511.07s、exit 0；严格收据校验通过。
- 同 dda5895a 前端六步通过，首尾身份稳定、dirty=false；E2E 为 **34P/2S**，不是36项全部通过。全仓 Ruff 通过。
- registry `check` 仍红，原因是跨仓 `kb/rag-query` 元数据漂移；基线和候选日志逐字节相同。parseability/tables/views/ledger crosswalk 通过。不以“存量”绕过合入门。

完整外部原件根：`~/.finance-runtime/reviews/react-trace-closeout-0921/`。本目录只封存精简证据；3份修前 pytest 日志与共享 refs 日志用 `.log.json` 的 `text` 字段逐字封装，解码哈希逐一校验，不修剪原件空白；`author/frontend.json` 内各日志路径仍指向外部原件，未重新签署路径或哈希。文档提交不把业务 SHA 的全量收据移签到文档 tip。

## 真实入口与业务边界

原题：这里的行情哪个板块更有机会，历史上有相似的阶段吗。

1. 8856/b1345a7d：`run_20260921_021153_300859` 在 history_query 参数错误后发生 mappingproxy 序列化异常。失败汇总 tool_calls=0，但事件已记录两次成功取证，不能按汇总推断零调用。其共享事件目录仅该测试 run 已迁至外部 `before-episode-native/`；原件保留。
2. 8857/dda5895a：`run_20260921_022024_613518` 完成交付。GLM-5.3-flash；11 provider attempts、2 judge；汇总 tool_calls=8，实际耐久事件为10次唯一调用请求、8次 tool_result、2次参数错误。两次 history_query 错误后继续补齐实体/截止日，再成功取历史结果和保存 research_only 草稿。
3. **金融质量仍 not_passed**：升级/降级条件被删，公开稿却保留“满足升级条件中的2条”；ranking_intent=false。225/25、AI手机PC 12.6%、MiniLED 16.5% 在原件中，但未绑定且无正文显式引用，因此没有进入核验视图。这是证据关联缺口，不能直接等同数值捏造，也不能关掉核验门。

这是一次自然历史工具恢复实例，不是 finance_query 自然纠参验收，也不证明总体质量改善。#790 未关闭，#791-#794 未完成。两个测试服务已停，生产版本未变。

## K3 独立复核

原报告：[independent/REPORT.md](independent/REPORT.md)。同一独立 K3 会话分 Spec/Quality 两章，均 PASS；不是两个互盲审核者，也不是生产放行。

- 既有 mirasim-kimi/kimi-k3 订阅通道，15分钟硬截止、无模型失败自动重发。首次进程在鉴权助手阶段失败，0审核工具；CLI exit 0 不算通过。原件在 `independent/bootstrap-blocked/`。
- 鉴权改由外层解析，只经内存环境传入隔离 pi 配置；未落 token。正式审查的 OS 沙箱只允许审查目录写入，源码/共享Git/生产只读，网络仅 localhost:18788。首次沙箱四项预检与规则保留；修正后只进一步收窄文件写权限。
- 正式会话26次工具调用；自建3组探针、实跑116P，4.78s。报告哈希与 execution.json 一致。两条低风险提示只涉及诊断具体性，没有要求降低安全门。
- `logs/probes.log.txt` 是首次红输出，不是最终绿日志。序号 E 前缀、正数 + 号是探针预期错误；修正及最终 S1 PASS 在事件流，提取在 `verified-tool-outputs.json`。未覆盖首红来制造全绿历史。
- 候选与作者树首尾干净同 SHA。共享 refs 哈希发生变化，不能称所有 refs 未变；同期其他分支提交见 `shared-ref-activity.log.json`。审核者事件只有只读 Git，OS 沙箱禁止共享 Git 写入。

原始事件流 SHA-256：`e62414c2a09fc8013657c9396fea285cba360e77e456ee9393ece8b561320cff`。仓内 compact 副本去掉流式增量、重复收尾消息和思考块，保留模型终消息及完整工具请求/结果。原始文件仍在外部 `independent/k3/events.jsonl`。

## 接手交叉核验

这是作者对独立证据的核实，不是第三次独立审核。

- 原报告与事件流哈希核对；116P 与探针修正结果均回溯到真实 tool_execution_end。
- 最终三个探针在固定只读候选上复跑，rc均0；116项直接执行复跑，rc0，6.72s。首个复跑遗漏 TMPDIR，pytest启动阶段找不到可写临时目录，未收集测试；失败日志与纠正后日志分开保留。
- 三个进程级撤保护均 rc1：S1 把协议和 verifier 的 strip_evidence_ordinals 改为恒等；S2 把 validation_diagnostic 改为原始 str(error)；S4 把 _mapping_for_json 改为总抛 TypeError。随后用 runpy 执行对应独立探针。分别检出 E27 数量泄漏、路径/任意散文回显、冻结参数崩溃。仅子进程内 monkeypatch，源码没改。
- 探针副本以 `.py.txt` 封存，避免被全仓 Python 扫描当应用源码；执行时使用原始外部 `.py`。runner 副本记录本次有界审查，不是新的应用入口。

`SHA256SUMS` 校验封存字节，不证明金融结论或覆盖率。合入仍须解决 registry 红项、在目标合流身份上验收并获得用户确认；部署另行授权。
