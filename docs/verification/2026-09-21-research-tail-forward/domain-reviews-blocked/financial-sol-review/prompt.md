独立审核 PR #835 固定新组合，不改任何源码，不合并/部署/写生产，不联网查金融数据，不转委派。使用现有ChatGPT订阅，同一session先规格后质量两节，不冒称两位审核者。作者/旧#797审核不移签。覆盖不足如实NOT_REVIEWED/BLOCKED，真缺陷给最小反例。

独占检出 /Users/a77/fwp-wt-financial-forward-review-0921
固定 HEAD d82cb16b5ef31d23339a1bef7084a0dcb8221e15
直接基座 ea5c3a94618a15e37f914c8b1a13e271875e4337，主干基座 f783f19c8a01fbe8d0ed70d851df7ed14598c051。
先后核HEAD/status，源码应clean；只允许忽略的测试缓存。额外探针/日志/最终 report.md 仅放 /Users/a77/.finance-runtime/reviews/research-tail-integration-20260921/financial-sol-review 。最终答复完整报告。不写handoff/记忆/全局配置，不读凭证，不装包、不删除文件。

组合包含 #797财务比例 + R6/保稿/发布边界/研究交付/RAG父实现。先diff路径，聚焦实际运行代码，不批量通读旧docs/verification。合同导览：docs/agent-product-door.md，docs/handoffs/2026-09-20-financial-ratio-units.md、2026-09-19-8792-financial-publication-integration.md；验主张须跟源码和真实消费者。
优先合同：
1. 比例与单位核验同时保留股票代码分区、短日期标题及引文编号排除；坏差值删除不清metric补修债；关闭工具预算不能把证据义务自动optional。查financial_claim_checks/research_delivery_checks/mandatory_satisfiability/episode_semantic_verifier的调用实线，按实际文件名定位。
2. 保稿/修稿/再核：可信公开稿、修订稿与公开投影不串；判官拒句不得用保稿偷偷恢复；partial正文应保合法引用与补修债。main的材料grounding/题设日期/unknown_stock_code仍成立。
3. publication身份精确匹配并且delivery_pending清除才允许UI收尾；消息已published但writer仍活动窗口要pending；API/SSE前后和恢复路径不能跳过。迟到旧轮trace不得覆盖同会话新追问，保加载代际。
4. RAG worker保主干RSS观察，父实现字节分帧、缓冲/abandoned与连续超时清理不互斥；替身隔离真实PID不能造成生产保护失效。若范围太大只签已动态压到的合同，不装成全域PASS。

测试入口：intelligence/tests/test_financial_forward_seams.py、test_financial_publication_integration.py、test_financial_contracts_r5.py、test_financial_r6_regressions.py、test_judge_reason_codes.py、test_rag_worker_transport.py；前端是intelligence/webapp/src/components/components.test.tsx（不存在App.test.tsx），可静态审；不要在新树装node依赖，不跑全量/E2E。自行补至少一个独立正负对照压真实消费者，不只重跑作者测试。所有金融数据/模型替身必须离线，禁生产库/真实模型。
固定测试 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest；umask022，env -i PATH=/Users/a77/.local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin HOME=/Users/a77 FWP_TEST_RECEIPT=0 PYTHONDONTWRITEBYTECODE=1。每测试命令最多120秒，阻塞保原件报未完成，不无限重试。总审核约15分钟内收口，不转委派/换付费通道。

输出：准确HEAD/基线；Spec/Quality分节裁决和每合同覆盖；严重度/路径行/触发条件；实际命令、原始输出文件与结果，静态/现有测试/独立动态分列；首红保留；未验证边界。旧R6/R3自然题0/4未翻案，离线脚本不等于真实同会话纠错或金融答案质量。不要签新main#830、历史/运行时联合组合、8792部署。
