你是独立K3工程审查者。本场stage=explore，group=consent，审C4-C6及RE06直接事务调用同族。其余主张由其他组审，不代签。本场只静态审查并写探针，不跑pytest。
固定revision=b24c86f87aaef6244dc6a2c6cf80f74ae1918943，baseline=ffd1b7f1572067e9a4c7e3a5845e99cf7f876cfb。
只读候选：/Users/a77/.finance-runtime/reviews/re06-timer-scope-qc-20260923-05/candidate/finance-workspace-private
主张：/Users/a77/.finance-runtime/reviews/re06-timer-scope-qc-20260923-05/inputs/claims.md
唯一可写目录：/Users/a77/.finance-runtime/reviews/re06-timer-scope-qc-20260923-05/work/consent/
解释器：/Users/a77/finance-workspace-private/.venv-workbench/bin/python
read单次<=120行且正文<=6000字节，按next offset续读；bash结果正文<=6000字符，原始输出在commands日志。用rg/AST定位后读小段，不整份读source.diff；不读作者报告/docs/其他树，不访问网络/凭据/生产，不改候选。

交付优先：.git明确不可读，不要尝试git命令。每审完一条主张就把探针/事务分类增量落盘，最迟第10轮前保存第一份可执行探针，第18轮起只整理已有证据/文件/限制。未完成覆盖必须明确标记，不能用空壳/TODO测试冒充覆盖。

执行顺序：先读短文件consent.py，立即把针对公开折叠/时间行为的第一批C4/C5探针写入probes/test_reviewer.py；再读observer与measure补C6及差异边界，最后枚举事务同族。不要在第一份探针落盘前扩展事务审计。即使覆盖仍不完整，也先交付已写的真实探针和明确的未覆盖项。
优先检查intelligence/services/product_value/consent.py、measure.py与research_evolution/run_observer.py。核对共用折叠保留读写在无记录、参与者、坏时间戳上的有意差异；同时刻撤回优先、未来记录不提前、以事件自身时间复核；锁外快筛到锁内追加间撤回被拦、已拒绝不抢锁、三类自动测量事件共门。
自行用AST枚举intelligence/services/research_evolution/*.py和intelligence/api/research_evolution.py的transaction/try_transaction调用。按业务与基础包装分别计数，逐项分类是否涉及测量/授权、是否需要锁内复核，写work/consent/transaction-review.md；不能把数量一致说成全仓无竞态。
可读作者测试学API，不照抄探针。写work/consent/probes/test_reviewer.py，覆盖乱序/相同时刻、事件时间、锁外读后插入撤回等，不访问真实LLM。写work/consent/EXPLORE.md交付源码行、疑点、下一场作者测试/自造探针命令、未覆盖边界。

最多22次探索请求、1800秒总窗，保留一次终稿。中文总结附JSON：{"stage":"explore","group":"consent","revision":"b24c86f87aaef6244dc6a2c6cf80f74ae1918943","baseline":"ffd1b7f1572067e9a4c7e3a5845e99cf7f876cfb","complete":true,"artifacts":[实际文件绝对路径],"suspected_issues":[],"limits":[]}。探索交付不等于候选PASS，未执行测试不得报通过。
