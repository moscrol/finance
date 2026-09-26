独立审核 PR #833 的固定新组合，不改任何源码，不合并/部署/写生产，不联网查询金融数据，不转委派。使用现有 ChatGPT 订阅，本会话先规格再质量两节，不冒称两个独立审核者。不要沿用作者/旧分支 PASS。发现真问题给最小反例与路径行；覆盖不全如实 NOT_REVIEWED/BLOCKED，不为了出 PASS 降低标准。

独占检出 /Users/a77/fwp-wt-history-forward-review-0921
固定 HEAD 7edfe24e76afbd5c365fbf97dd2414847b086f88
直接基座 ea5c3a94618a15e37f914c8b1a13e271875e4337，主干基座 f783f19c8a01fbe8d0ed70d851df7ed14598c051。
先后均核 HEAD/status。源码应clean；只允许忽略的测试缓存。独立探针/日志仅放 /Users/a77/.finance-runtime/reviews/research-tail-integration-20260921/history-sol-review 。无需写仓内handoff、记忆、全局配置，不读凭证。结论写上述目录 report.md 并在最终答复给完整报告。不能只报CLI退出码。

这是 #783/#800 历史研究链与主干材料/上一轮复核保护的组合。先看 git diff --name-only 基座..HEAD，聚焦实际运行代码，归档大量 docs/verification 非新实现，不批量通读历史日志。
规格来源：docs/agent-product-door.md 的历史研究条目；docs/handoffs/2026-09-17-history-market-anatomy.md、2026-09-18-history-succession-delivery.md、2026-09-20-history-closeout-fixes.md 是范围导览，关键主张必须对源码和消费者查证。
优先合同：
1. 历史授权窗/信息截止/观察窗分开；续问只从真实用户消息或可信合同恢复，助手旧答/摘要/引用文本不授予读取上限。晚授权终点不能抬信息截止。检查 finance_query/research_contract/user_task/material_contract 的相互作用。
2. 程序要求不得当作虚构市场假设；真实用户假设仍被识别。主干上一轮复核、材料 grounding、市场广度提示、缺输入规则不被前向整合吞掉。
3. 同根同排名窗的合法扩窗父件可以续查个股，但血缘/用户会话/窗口上限不可越界；看 historical_research/window_binding 与调用路径。
4. history_query/read_history_result 真消费者：local权限映射不变外呼权限，工具材料仍过日期范围门；可信 ToolDiagnostic 不生成事实E号、不授日期授权。
5. 历史用途 rank/trace 投影不误套前向优先级模板；遇不支持/缺类型/无数据如实诊断，不能成功空壳或暗推对象。

作者新增 tests/test_history_forward_seams.py 仅作测试入口，不当独立证明。自行设计至少一个跨边界正负对照，查真实消费者，补几个本增量最危险反例。测试可从 test_history_window_binding.py、test_history_date_scope.py、test_history_live_seams.py、test_history_expression_contract_boundary.py、test_history_forward_seams.py 按需选择。不要跑全量、不要真实模型或生产库。测试固定解释器 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest；umask022，env -i PATH=/Users/a77/.local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin HOME=/Users/a77 FWP_TEST_RECEIPT=0 PYTHONDONTWRITEBYTECODE=1。每条测试命令最多120秒，有阻塞保原件并报告，不无限重试。总审核约15分钟内收口，不转委派。不要装包/批量建图/删除任何文件。

输出：准确HEAD与基线；Spec/Quality分别PASS/FAIL/BLOCKED和分合同覆盖；缺陷严重度、路径行、触发条件；实际运行命令、结果和原始输出文件路径；独立探针与现有测试区分；未验证边界。未重跑历史原四道自然题，不能宣布历史回答质量已过；不签新main #830、三领域联合树或#829历史绑定孤儿片。
