你是K3写手，不是独立审查者。用户明确授权写手并刚说“继续推进”。立即写测试并执行，不要重新审全栈。

只读candidate=/Users/a77/.finance-runtime/reviews/runtime-contract-followup-20260923/candidate
revision=5f35da1723f74663a4803c4d1490c402a1d6db40 baseline=da761024ed54c46b8e650d1b86076e1f9d261ed2
唯一可写根=/Users/a77/.finance-runtime/reviews/runtime-probe-k3-writer-20260923-03/k3/work
Python=/Users/a77/finance-workspace-private/.venv-workbench/bin/python
禁网、禁生产写入、禁改candidate、禁安装、禁模型嵌套调用。只用合成输入和tmp_path。

任务仅Inbox/spool(C6)的补测：阅读candidate下 intelligence/services/episode_inbox.py 和 intelligence/tests/test_episode_persistence_failure.py 的相关片段。然后在work/inbox_checks.py编写独立pytest测试：
1. 保存insert失败时不删spool文件、不claim消息，磁盘原件字节保持。
2. 正常落账才删文件，claim只有一次；正文通过derive_messages匹配。
3. 关箱后late spool保留且不写账。
4. 崩溃窗口（insert已落而unlink失败）允许at-least-once，不冒称exactly-once；同spool_id可对账。
5. 损坏JSON隔离、不凭空造消息。
用最小记录EpisodeEvent的ledger，故障标志在add时设置；不要粗暴mock返回PASS。
在work生成fixture加载副本 shadow，仅精确撤掉ingest_spool中storage_failed保留文件保护，模块先登记sys.modules；正常对照仍通过。pytest前sys.path放测试目录，PYTHONPATH已指candidate。每次pytest给独立basetemp和junitxml，-p no:cacheprovider，禁写缓存；先跑基线，再变异预期只指定保存失败用例断言红，再还原绿，实际执行。保留每轮日志和退出码，collection error不得计有效红。最多前5次请求开始执行基线。

最终报告首行“写手自检，宿主待验”，Spec/Quality两节，含文件列表、真实计数、失败证人、限制。fenced JSON含revision/baseline/role:"writer"/verdict/complete:true/checks，C1-C8依次表示上面5个用例、变异有效、还原绿、候选未改。这里只评价交付小片，不能签全局runtime PASS。完成立即交报告；无需用完32请求。
