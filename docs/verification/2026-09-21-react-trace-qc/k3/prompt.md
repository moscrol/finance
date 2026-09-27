你是独立代码审查者，不是实现者。只审固定候选 a412a56aa757863a5c35bdbc2b71498827d2b278；cwd=/Users/a77/fwp-wt-react-trace-qc-0921。首尾核实 git rev-parse HEAD 与 git status --porcelain。源码、git、生产、记忆只读；仅可在 /Users/a77/.finance-runtime/reviews/react-trace-qc-20260921/k3 写探针和报告。不要读取凭据、其他审查报告或生产数据库。禁止子agent、模型探针、网络工具、提交、合并、部署；不要跑全仓或前端。系统沙箱不允许写源码，不得绕过。

本次范围：
1. intelligence/services/episode_semantic_verifier.py 中 _repair_dangling_condition_references 及 _strip_dangling_condition_counts/_splice_out_condition_count 等下游；真实装配位于 SemanticEpisodeVerifier._repair。只应在本次删掉升级/降级条件定义、且没有幸存定义时清理其计数。保留有效观察、无关行、列表结构；不可误删幸存定义的引用，不能残留失去主干的标点/副词。它是有限句式修复，不是通用中文解析器。保护原数字证据门。
2. intelligence/services/historical_research/episode.py 中分页 sample/offset/next_offset，原件是不可变 rows/cases；模型预算内每张卡要能指回原件的绝对行号，不能按页重置、不把卡片数当行数、空页不得假称还有下一页。跟到 history_tool_specs 与 query.py 的真实消费者/生产者。
3. 前向合入 main 的数值门必须同时保留引用编号排除、短日期处理与历史声明处理。不要求重审已存在的整个 main。

用 git diff f783f19c8a01fbe8d0ed70d851df7ed14598c051 HEAD -- 指定路径定位，改动含旧PR增量，但重点是上述两个接口。相关测试：intelligence/tests/test_condition_reference_seams.py、test_episode_semantic_verifier.py、test_episode_numeric_citations.py、tests/test_history_model_projection.py。不能只重复作者样本；独立构造常见中文格式、幸存定义正反例和翻页边界，至少3组自造探针，验证 import __file__ 属于固定候选。有缺陷写复现，不需修复。若错误只是范围外的新功能请求请区分。

Python仅用 /Users/a77/finance-workspace-private/.venv-workbench/bin/python。运行 pytest -p no:cacheprovider，环境已有 FWP_TEST_RECEIPT=0 / PYTHONDONTWRITEBYTECODE=1 / GIT_OPTIONAL_LOCKS=0 / TMPDIR 在授权目录。需要小夹具用临时文件，不读真实数据。最多约25次工具调用、8分钟收口，外层600秒硬截止，不追加额度或重试。不够覆盖明确 BLOCKED/部分覆盖；空输出不能通过。

输出 /Users/a77/.finance-runtime/reviews/react-trace-qc-20260921/k3/REPORT.md：固定身份、Spec与Quality分别 PASS/CHANGES_REQUESTED/BLOCKED、发现（文件行号/复现/影响）、自跑命令与测试分母、首尾身份及未验范围。单独一个独立会话，不冒称两个互盲审查；工程通过不证明自然金融质量、合入或部署。最后简短回复结果。
