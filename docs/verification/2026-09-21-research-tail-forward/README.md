# 研究尾单前向候选封档索引

封档固定提交 **c47b2751f29e08ee6ff0848603adf3c3c4d03ffe** 已推，文档 WIP **#838**（创建POST超时后按head回读唯一PR，无重复POST）。两包Git提交字节核验281/281与28/28通过；[发布收据](publication-check.json)另记源码/PR身份、回贴和记忆，不追加到已冻结包、不改原清单。

- [作者工程与#831独立审核](author-and-small-review/README.md)：四候选固定源码的工程收据；#831独立报告与操作员收窄裁决；c35门禁诊断/主动中止原件。
- [三领域容量中断](domain-reviews-blocked/README.md)：#833/#834/#835三份session原事件、首尾身份、exit1及无报告事实，不能用部分定向绿代签终审。
- [有界续接01](domain-review-resume-01/README.md)：用户“执行”后历史原thread续审103P，随后再capacity无终审；操作员typed消费者确认三种受保护引文错误继承历史任务/未保local_only，**#833 CHANGES_REQUIRED**。runtime/财务按串行容量失败即停约定本轮未启动。旧两包不改。
- [续接决策快照](../../handoffs/2026-09-21-research-tail-review-resume-01.md)记录根因、首错与为何停止后两条，不把操作员核证当独立report。新封档 **c4e7bea4c74932000149c2392b38c3afa2cdb03c** 已推，38/38提交字节通过；[续接发布回执](resume-01-publication-check.json)在冻结包外，记录四PR回贴5407–5410/正文回读与记忆54ab8dfb，不改旧manifest。
- [日期决策快照](../../handoffs/2026-09-21-research-tail-forward-integration.md)与[协调交接](../../handoffs/inflight/docs-research-tail-closeout-0921.md)。冻结源码没有追加本轮交接，需在`docs/research-tail-closeout-0921`读取对应inflight。

## H-01/H-02 接替

- [H-01 控制隔离](history-boundary-repair-01/README.md)：固定d91aff9d8，530定向通过，五变异有效；当时H-02两红例保留。证据3a1c8289b的45成员已核，[发布回执](history-boundary-repair-01-publication-check.json)在包外。
- **最新：[H-02 可信读取继承](history-permission-repair-02/README.md)**：#845固定7c99f389e，770定向通过（含41旧+49新边界例），十变异有效。两条原H-02转绿，但新相邻短材料/未闭合引号反例正常版仍2红，读取上限保持local_only。整体CHANGES_REQUIRED，不替完整门禁或独立/自然验收。
- [H-02 决策快照](../../handoffs/2026-09-21-history-permission-inheritance-repair.md)与集中inflight给出接手边界。新包58成员封存，旧四包不动，提交字节/PR发布核验另记包外回执。

## 验证方法与范围

每包`sha256-manifest.txt`对包内除自身外的全部文件逐字节绑定。提交后运行仓内既有`check_evidence_archive.py`核**提交对象**；`sources.json`另外保留原来源文件路径、长度、哈希和`.txt`重命名映射。两个包不互相替代：作者工程全叶绿与独立审核未完成同时成立。

封档前第一次对全部暂存文件跑`git diff --cached --check`返回2：原始pytest日志和patch含行末空白及末尾空行。该检查衡量文本格式，不衡量证据正确性；**不为格式绿修改原件**。后续只对本轮新写的交接、说明及教训跑格式检查，原件走来源哈希和Git blob核验。完整首报保留在外部证据根`docs-first-commit.txt`；不声称全档无空白警告。不改仓库全局门禁、不跳过pre-commit。

本提交仅封档，不是四源码新组合，不对文档tip宣称作者全量重跑。记忆三文件由既有auto-sync提交94fb8acf后逐字节核对；图谱审计exit0但含其他节点UNVERIFIED，且MERGED只是同名符号出现，不等于行为/合入通过，所以本轮在途后缀保留。没有合main、部署、生产写入或删除操作。前轮因共享磁盘紧张停止新增大测试；本轮恢复时重新观测约19GiB可用，只做授权的有界续审与本地核证，没有全量重跑。第三包单独清单/提交字节核验，不重签前两包，也不把约束修复写进冻结源码。
