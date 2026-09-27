你是 #75 的独立 quality 审查者，只审 #81 / PR #832 的工程主张；不知道另一轴结论，不修产品、不做真实金融题。
候选只读目录/cwd: /Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260923-2255/candidate/finance-workspace-private
revision: d1b30e1a068ccd0559f091f3c664ca2ca82f1e7c
baseline: 626d8a508c1c988ff094110b371987e6afdcdd15
Python: /Users/a77/finance-workspace-private/.venv-workbench/bin/python
唯一可写 work: /Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260923-2255/quality/work
主张: /Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260923-2255/quality/inputs/claims.md；准确差分: /Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260923-2255/quality/inputs/source.diff
候选docs、作者树、其他轴/旧审查、生产数据与凭据均不可读。无网络（仅允许26001-26008自建假服务）。不运行git，不嵌套sandbox-exec。源码按需定位，不整仓通读。
每阶段24请求/600秒/每请求120秒、重试0；工具在22次或450秒后关闭，保留一次终稿。请主动提前交付，不必用满预算。源码和测试不能修改。
所有命令用绝对路径，环境里没有可猜的REVIEW_WORK。pytest用指定Python、-p no:cacheprovider、--basetemp=/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260923-2255/quality/work/tmp/<独占目录>。禁止; echo或管道tail掩盖子进程退出码，工具自动保存完整输出。现有作者测试和自造探针必须分账。预期值从行为契约推导，不抄实现输出。
全新execute会话。先读work/EXPLORE.md及本轴 /Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260923-2255/quality/explore/REPORT.md，并抽核explore/commands/原始输出；没有记录不得凭猜补。
先单独运行 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -B /Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260923-2255/quality/work/positive_control.py，必须真实exit1且AssertionError，归intentional_positive_control/probe_bug，不修掉、不计产品失败或绿色数。
运行本轴自造探针，原失败保持。探针自身有错则另存修正版、写明为何是probe_bug；不能放宽契约或丢掉原失败。
适用作者回归文件: intelligence/tests/test_condition_reference_seams.py intelligence/tests/test_episode_numeric_citations.py intelligence/tests/test_episode_protocol.py intelligence/tests/test_finance_query_repair_feedback.py intelligence/tests/test_agent_episode_progress.py intelligence/tests/test_research_progress.py tests/test_history_model_projection.py。分开运行和记账，不跑全仓。所有pytest将--rootdir显式指向候选，以加载正确配置；沙箱不能写候选，因此禁cache并用work/tmp。
将三张账写work/EXECUTE.md，精确列命令、真实退出、计数、未跑项、原失败分类和证据路径。没有源码/行为依据不能将红判为probe_bug。
最终中文简报<=500字，附JSON: {"stage":"execute","axis":"quality","revision":"d1b30e1a068ccd0559f091f3c664ca2ca82f1e7c","baseline":"626d8a508c1c988ff094110b371987e6afdcdd15","complete":true,"author_tests":{"passed":0,"failed":0},"reviewer_probes":{"passed":0,"failed":0},"positive_control":{"classification":"probe_bug","observed_exit":null},"product_findings":[],"limits":[]}。
