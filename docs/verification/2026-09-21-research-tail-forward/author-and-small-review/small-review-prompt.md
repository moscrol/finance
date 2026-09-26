请独立审核固定候选，不改源码，不合并/部署/写生产、不联网金融查询，不再转委派。用现有 ChatGPT 订阅，不新增付费通道。

目标树 /Users/a77/fwp-wt-research-tail-integration-0921
固定 HEAD ea5c3a94618a15e37f914c8b1a13e271875e4337
基线 f783f19c8a01fbe8d0ed70d851df7ed14598c051
PR #831，增量仅7文件。先验证头与干净状态，若不同停止签字。

只审两份合同：
1. API测试夹具登记自己启动的Timer，任务完成从原表移除后仍等待该Timer；不扫描无关线程、不修改生产shutdown。归属登记须先于测试提交任务，退出时保留已触发回调的依赖生命周期。
2. code-map原始查询必须保留，最多多一次连字符到下划线别名查询；结果去重且总限额；原检索真失败不得冒称成功零命中，正常无匹配不应报后端不可用。别把别名改写成唯一问句。

请先做规格审核再做质量审核，可以同一独立session分两节但不得冒称两位审核者。查真实生产/测试消费者；设计少量正负例，测试一律 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest 。只跑定向，不跑全量；已有全量不替你的审核。写不了新探针文件时可用只读解释器内存探针或现有测试，诚实列覆盖限制。不要写仓内交接，最终报告即可。

证据可参考但勿把作者自述当结论：/Users/a77/.finance-runtime/reviews/research-tail-integration-20260921/small-pr.md 与 small-python-receipt.json、small-frontend-gates/frontend.json。最终报告含受审精确SHA/基线、发现按严重度及路径行、实际命令与结果、未验证边界、PASS/FAIL/BLOCKED。不因无模型自然验收而否这两项离线工具小片，也不扩大到 #798/#800 的领域代码。
