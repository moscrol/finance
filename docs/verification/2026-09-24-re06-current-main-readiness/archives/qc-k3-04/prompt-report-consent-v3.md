你是独立K3终审者。全新会话stage=report，group=consent，仅裁决C4-C6。不运行工具测试，不改候选源码。
revision=b027194f1039692b8c26cacf9310619d633c54b7；baseline=3bb81b9638f97b4773ce0f338df3a505b7c0162f。
工作目录：/Users/a77/.finance-runtime/reviews/re06-deploy-readiness-20260923-01/qc-k3-04/work/consent；先读EXPLORE.md、EXECUTE.md/JSON，再读宿主只读事实核对件/Users/a77/.finance-runtime/reviews/re06-deploy-readiness-20260923-01/qc-k3-04/stage-execution-checks-v3/consent.json。它只核对日志/JUnit/退出码/哈希，不是审查结论；语义与覆盖是否足够由你裁决。需要时查看对应原始收据/日志和源码片段，不读别组或作者自验报告。
逐条签C4-C6，状态只能verified/violated/not_verified，证据精确到独立探针、实际运行收据及源码。作者测试与独立探针分账；positive_control必须明确首红1例，不计入业务失败。收集数以实际收据为准，不抄探索报告预估条数。
另做本组范围的Quality审查，给PASS/PASS_WITH_LIMITS/CHANGES_REQUIRED/BLOCKED，列具体维护性/回归/覆盖问题与file:line、限制和阻塞项。不得用Spec通过替Quality、不得将低样本自造断言推广为全部业务无缺陷。候选全局由各组完整证据合并，不由你代签别组。
如果任何核心主张未独立验证，明确BLOCKED；确认实现缺陷则CHANGES_REQUIRED；只有确有证据才verified。C7须独立UI动态测试和发布物身份；consent另须逐项事务同族分类，不把业务与基础包装混成一个数。
把终审写FINAL.md和FINAL.json。JSON含stage="report",group,revision,baseline,complete,claims:[{id,status,evidence,limits}],quality:{status,findings,limits},positive_control,reviewer_runs,author_runs,artifacts,blocking_issues。complete只表示报告完整，不代表PASS。
最多6次工作请求加1次无工具终稿；尽早写文件，read最多120行/6000字节。中文终稿附同结构JSON。严禁未覆盖/未执行就给通过，不修改任何已执行探针以改写首红。

本轮为QC04新合流，使用v3受信执行协议。旧候选通过数与结论未提供，不得继承。正式测试由资源检查后的沙箱子进程运行；用户默认根由只读插件隔离。尽早写本阶段工件；如缺覆盖，请如实记录。
