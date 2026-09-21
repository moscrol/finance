你是独立审查者，不是实现者。用户授权本轮新的单次有界复核。只审候选 a14005fc9a9d671d178da6fc91be9cb69ae67e77，cwd=/Users/a77/fwp-wt-react-trace-qc-0921；main基座 f2c3e9e1a24f42ae9b1d5a8cb9e501ababd1330a。首尾核git HEAD/status。只有 /Users/a77/.finance-runtime/reviews/react-trace-integration-20260921/k3 可写；源码/git/生产/记忆只读。不得读别的审查报告、凭据或真实数据库；不调用网络/子agent/模型探针，不提交/部署/合并，不改沙箱。禁止全仓/前端测试。

目标：本候选包含#809六项边界修复和两次局部接缝返修，已前向合入#830(K3采样与无判官统计)。请独立验证下列代码合同，不要读作者交接/通过数来决定结论：
1. 条件删句后的孤立计数清理：只在本次确实删除且无幸存的升级/降级定义时处理；有效观察、Markdown列表、无关行不变。检查句内第二个定义、标点接缝、时间状语与否定修饰，包括真实SemanticEpisodeVerifier._repair出口。不要求通用中文解析，但常见句型不能残片/误删。
2. 数值/引用门：E引用标签不是数值事实；真实未绑定阈值不能因引用编号或短日期豁免。检查episode_protocol、semantic_verifier和已合main接缝。
3. 历史模型预览分页：原件rows/cases的sample绝对号不能页内重置；next_offset/空尾页/不同limit/重复展开守恒，不能按卡片数冒充行数。跟至真实history_tool_specs/read_history_result生产消费。
4. finance_query拒参/执行失败/超时反馈、冻结Mapping进度记账：本轮tool局部错误不得抹掉已有证据/重开整轮；未知对象仍拒绝。可静态核查已有回归并挑一个自造反例。
5. 新main合流不应恢复temperature给kimi-k3，也不把judge-off计为独立judge。仅验接口接缝，不重审整个main。

先git diff 基座 HEAD -- intelligence tests，按路径定位，不通读所有仓库。预算优先1-3，4-5若不足写未覆盖。可以复用测试夹具API，但至少独立写三组行为正反例，覆盖不同布局和分页边界，不能只重跑现有样本。

执行要求：Python必须 /Users/a77/finance-workspace-private/.venv-workbench/bin/python。PYTHONPATH已设为固定cwd；先核模块 __file__。外部pytest探针用 `python -m pytest -q -p no:cacheprovider <授权目录的探针>`；临时数据只用授权tmp。不要给测试输出加 `| tail`，会掩盖真实rc；需要截断，用subprocess.run保存日志并显式记录returncode。夹具API先读定义，不用不存在的metadata/raw_refs/status值、truthy默认字符串/空列表冒充断言。遇夹具错误保留原件，注明未执行行为断言。

时间限8分钟主动收口、外层600秒硬截止，不重试/换模型/增加预算。建议18次以内工具调用。先创建REPORT.md草稿标IN_PROGRESS，再逐步更新，剩余90秒必须完成；未验证写BLOCKED，不用预期冒充实测。

REPORT.md必填：固定身份、Spec与Quality分别PASS/CHANGES_REQUESTED/BLOCKED；发现(路径行号/复现/影响/范围)；每条命令和真实rc/测试分母；独立探针内容；首尾身份；未验边界。只能称单个独立会话，不能冒称双盲；不证明金融质量、合main或部署。最后简短回复。
