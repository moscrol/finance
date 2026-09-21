# 研究尾单前向候选封档索引

- [作者工程与#831独立审核](author-and-small-review/README.md)：四候选固定源码的工程收据；#831独立报告与操作员收窄裁决；c35门禁诊断/主动中止原件。
- [三领域容量中断](domain-reviews-blocked/README.md)：#833/#834/#835三份session原事件、首尾身份、exit1及无报告事实，不能用部分定向绿代签终审。
- [日期决策快照](../../handoffs/2026-09-21-research-tail-forward-integration.md)与[协调交接](../../handoffs/inflight/docs-research-tail-closeout-0921.md)。冻结源码没有追加本轮交接，需在`docs/research-tail-closeout-0921`读取对应inflight。

## 验证方法与范围

每包`sha256-manifest.txt`对包内除自身外的全部文件逐字节绑定。提交后运行仓内既有`check_evidence_archive.py`核**提交对象**；`sources.json`另外保留原来源文件路径、长度、哈希和`.txt`重命名映射。两个包不互相替代：作者工程全叶绿与独立审核未完成同时成立。

封档前第一次对全部暂存文件跑`git diff --cached --check`返回2：原始pytest日志和patch含行末空白及末尾空行。该检查衡量文本格式，不衡量证据正确性；**不为格式绿修改原件**。后续只对本轮新写的交接、说明及教训跑格式检查，原件走来源哈希和Git blob核验。完整首报保留在外部证据根`docs-first-commit.txt`；不声称全档无空白警告。不改仓库全局门禁、不跳过pre-commit。

本提交仅封档，不是四源码新组合，不对文档tip宣称作者全量重跑。没有合main、部署、生产写入或删除操作。共享磁盘空间紧张，本轮停止新增大测试/审核，只做轻量校验和提交。
