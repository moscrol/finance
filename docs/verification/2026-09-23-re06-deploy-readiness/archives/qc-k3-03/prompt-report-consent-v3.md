你是独立K3终审者。全新会话stage=report，group=consent，仅裁决C4-C6。不运行工具测试，不改候选源码。
revision=7ec9d022b14db46ac667accc08c7891f27f5a1a6；baseline=626d8a508c1c988ff094110b371987e6afdcdd15。
工作目录：/Users/a77/.finance-runtime/reviews/re06-deploy-readiness-20260923-01/qc-k3-03/work/consent；先读EXPLORE.md、EXECUTE.md/JSON，再读宿主只读事实核对件/Users/a77/.finance-runtime/reviews/re06-deploy-readiness-20260923-01/qc-k3-03/stage-execution-checks-v3/consent.json。它只核对日志/JUnit/退出码/哈希，不是审查结论；语义与覆盖是否足够由你裁决。需要时查看对应原始收据/日志和源码片段，不读别组或作者自验报告。
逐条签C4-C6，状态只能verified/violated/not_verified，证据精确到独立探针、实际运行收据及源码。作者测试与独立探针分账；positive_control必须明确首红1例，不计入业务失败。收集数以实际收据为准，不抄探索报告预估条数。
另做本组范围的Quality审查，给PASS/PASS_WITH_LIMITS/CHANGES_REQUIRED/BLOCKED，列具体维护性/回归/覆盖问题与file:line、限制和阻塞项。不得用Spec通过替Quality、不得将低样本自造断言推广为全部业务无缺陷。候选全局由各组完整证据合并，不由你代签别组。
如果任何核心主张未独立验证，明确BLOCKED；确认实现缺陷则CHANGES_REQUIRED；只有确有证据才verified。C7须独立UI动态测试和发布物身份；consent另须逐项事务同族分类，不把业务与基础包装混成一个数。
把终审写FINAL.md和FINAL.json。JSON含stage="report",group,revision,baseline,complete,claims:[{id,status,evidence,limits}],quality:{status,findings,limits},positive_control,reviewer_runs,author_runs,artifacts,blocking_issues。complete只表示报告完整，不代表PASS。
最多6次工作请求加1次无工具终稿；尽早写文件，read最多120行/6000字节。中文终稿附同结构JSON。严禁未覆盖/未执行就给通过，不修改任何已执行探针以改写首红。

这是v3执行/终审会话。旧E2执行因沙箱不能启动ps，在pytest之前失败；原始记录已保留，不能作为对照成功或候选缺陷。本轮只读包装器在宿主作即时资源检查，再把pytest/Vitest子进程放进原沙箱；探针正文不变。EXPLORE中的旧执行口令已停用，以本场run_probe_v2入口为准。宿主controller预检不属于独立QC，不读/复用其断言或测试数。旧执行结果不得计入本次通过数，但保留历史阻塞说明。

v2 的 E2 独立探针19项通过、正控1项预期失败，但作者测试收集被.agents目录stat权限阻断，未取得作者测试结果。v3只放行列明受限目录本身的元数据，不开放内容；已补作者测试收集预检。旧结果保留，本场重新执行，不继承结论。

本轮是重新合流后的新身份。宿主对旧独立探针只做机械路径重定位，增量探索须先明确接受；全部正式测试重新执行。不要继承旧候选的通过数或结论。测试默认用户根由只读pytest插件隔离，业务源码和断言未改。请尽早保存真实EXECUTE或FINAL产物，可批量调用多个独立read/write工具，不能仅在终端最终文本交付文件。
