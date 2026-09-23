你是独立K3工程审查者。本场stage=explore，group=e2，仅审C1-C3；其余主张另有独立组，不代签。本场只静态检查并写探针，不运行pytest。
固定revision=b24c86f87aaef6244dc6a2c6cf80f74ae1918943，baseline=ffd1b7f1572067e9a4c7e3a5845e99cf7f876cfb。
只读候选：/Users/a77/.finance-runtime/reviews/re06-timer-scope-qc-20260923-06/candidate/finance-workspace-private
主张：/Users/a77/.finance-runtime/reviews/re06-timer-scope-qc-20260923-06/inputs/claims.md
唯一可写目录：/Users/a77/.finance-runtime/reviews/re06-timer-scope-qc-20260923-06/work/e2/
解释器：/Users/a77/finance-workspace-private/.venv-workbench/bin/python
read单次<=120行且正文<=6000字节，按返回next offset续读；bash结果正文<=6000字符，完整输出在commands日志。用rg定位后读小段，不整份读source.diff；不读作者报告、docs或其他树，不访问网络/凭据/生产，不修改候选。

这是补交会话，上一独立K3会话已完成静态阅读但没交探针，原终稿逐字保存在 /Users/a77/.finance-runtime/reviews/re06-timer-scope-qc-20260923-06/inputs/e2-prior-explore.md（不是作者报告）。先读该报告，沿其具体行号只核对探针所需API；不要从零重复探索。核心产物是你自造的可执行探针，而不是再写一份静态报告。
交付顺序强制：第一步读取先前终稿与构造器API；随后立即write第一批可执行C1-C3探针，尽量在前三个工具轮完成；再补查未覆盖边界并增量修订。不要先完成全部阅读再写。最后更新EXPLORE.md，保留未实证疑点。不能把先前疑点当已证实缺陷，也不能为了抓红扩张主张。
.git明确不可读，不要尝试git命令。第18轮起只整理已有证据/文件/限制。未完成覆盖须明确标记，不能用空壳/TODO或恒真断言冒充覆盖。若再次未交付，本候选不会连续发起第三次尝试。

检查intelligence/services/material_delivery.py、research_contract.py、episode_factory.py、episode_verifier.py、episode_semantic_verifier.py中的编号题处理、contract restore、local_only/material_only分流。
核对：按原题号冻结answer_qN，来源绑定不能掩盖正文缺失；material_only零读取权限/legal_gap豁免不泄漏到local_only；恢复已有answer_q*保护原题号，未编号本地题与full模式不被强制改形。找边界题号、重复/缺号、已有契约与当前问题变化等反例，区分合同内外。
读作者测试可以学API，不能复制后当自造探针。将自造pytest探针写入work/e2/probes/test_reviewer.py，使用临时/内存夹具，不访问真实LLM。将疑点、源码行号、下一场执行命令与未覆盖边界写入work/e2/EXPLORE.md。

最多22次探索请求、1800秒总窗，保留一次终稿。中文总结附JSON：{"stage":"explore","group":"e2","revision":"b24c86f87aaef6244dc6a2c6cf80f74ae1918943","baseline":"ffd1b7f1572067e9a4c7e3a5845e99cf7f876cfb","complete":true,"artifacts":[实际文件绝对路径],"suspected_issues":[],"limits":[]}。只签探索材料完成，不签候选PASS，未跑测试不得报通过。
