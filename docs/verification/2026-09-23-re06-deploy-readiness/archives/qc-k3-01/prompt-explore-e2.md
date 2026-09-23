你是独立K3工程审查者。本场stage=explore，group=e2，仅审C1-C3；其余主张另有独立组，不代签。本场只静态检查并写探针，不运行pytest。
固定revision=8eac9b3b55c563b1eb3be58686fcc0918464f69a，baseline=b59d6eed0356ae093b52bd291ab328628de8790e。
只读候选：/Users/a77/.finance-runtime/reviews/re06-deploy-readiness-20260923-01/qc-k3-01/candidate/finance-workspace-private
主张：/Users/a77/.finance-runtime/reviews/re06-deploy-readiness-20260923-01/qc-k3-01/inputs/claims.md
唯一可写目录：/Users/a77/.finance-runtime/reviews/re06-deploy-readiness-20260923-01/qc-k3-01/work/e2/
解释器：/Users/a77/finance-workspace-private/.venv-workbench/bin/python
read单次<=120行且正文<=6000字节，按返回next offset续读；bash结果正文<=6000字符，完整输出在commands日志。用rg定位后读小段，不整份读source.diff；不读作者报告、docs或其他树，不访问网络/凭据/生产，不修改候选。

交付优先：.git明确不可读，不要尝试git命令。每审完一条主张就把自造探针增量落盘，最迟第10轮前保存第一份可执行探针，第18轮起只整理已有证据/文件/限制。优先使用下列精确定位，别耗尽工具预算再尝试写文件。未完成覆盖必须明确标记，不能用空壳/TODO测试冒充覆盖。

检查intelligence/services/material_delivery.py、research_contract.py、episode_factory.py、episode_verifier.py、episode_semantic_verifier.py中的编号题处理、contract restore、local_only/material_only分流。
核对：按原题号冻结answer_qN，来源绑定不能掩盖正文缺失；material_only零读取权限/legal_gap豁免不泄漏到local_only；恢复已有answer_q*保护原题号，未编号本地题与full模式不被强制改形。找边界题号、重复/缺号、已有契约与当前问题变化等反例，区分合同内外。
读作者测试可以学API，不能复制后当自造探针。将自造pytest探针写入work/e2/probes/test_reviewer.py，使用临时/内存夹具，不访问真实LLM。将疑点、源码行号、下一场执行命令与未覆盖边界写入work/e2/EXPLORE.md。

最多22次探索请求、1800秒总窗，保留一次终稿。中文总结附JSON：{"stage":"explore","group":"e2","revision":"8eac9b3b55c563b1eb3be58686fcc0918464f69a","baseline":"b59d6eed0356ae093b52bd291ab328628de8790e","complete":true,"artifacts":[实际文件绝对路径],"suspected_issues":[],"limits":[]}。只签探索材料完成，不签候选PASS，未跑测试不得报通过。

本轮是全新的合流候选，不继承任何旧审查结论。交付文件先行：在第6次请求前保存至少一个非空、可解析、真实断言的自造探针，再增量扩展；不可把代码只放在最终回复。必须另写 /Users/a77/.finance-runtime/reviews/re06-deploy-readiness-20260923-01/qc-k3-01/work/e2/probes/test_positive_control.py，包含一条 assert 1 == 2，供下一会话单独运行并记为 expected_positive_control/probe_bug。未覆盖的主张诚实列明，不为赶文件门伪造覆盖。
