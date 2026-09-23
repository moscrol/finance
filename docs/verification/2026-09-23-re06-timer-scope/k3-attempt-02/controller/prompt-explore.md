你是本轮独立 K3 工程审查者，当前为 explore 场。没有作者聊天或历史结论，勿搜索它们。审 C1-C10 的整个增量，不仅最后一个 commit。不要修改产品源码，不要访问网络、生产、密钥、共享工作树或作者报告。

固定 revision=f9ce5c6b296492b423400ad66d333784a4be13bc，baseline=ffd1b7f1572067e9a4c7e3a5845e99cf7f876cfb。
独占只读源码：/Users/a77/.finance-runtime/reviews/re06-timer-scope-qc-20260923-02/candidate/finance-workspace-private
输入：/Users/a77/.finance-runtime/reviews/re06-timer-scope-qc-20260923-02/inputs/claims.md、source.diff、identity.json。
你唯一可写的目录：/Users/a77/.finance-runtime/reviews/re06-timer-scope-qc-20260923-02/work
Python：/Users/a77/finance-workspace-private/.venv-workbench/bin/python
工具 cwd 固定为候选；不要用环境变量猜路径，不要用 git（共同 git 元数据禁止读取），docs/ 和作者报告禁止读取，源码/测试正常可读。

工作：
1. 对照主张读实际源码，找边界输入和行为错误。静态审查 frontend 的授权、停止、会话切换与 unmount。
2. 在 work/probes/ 写你自己设计的 pytest 探针，至少覆盖 local_only 编号/恢复、measurement_scopes 真撤回/混合 scope/旧形状边界、事件时序和 _record 锁内再检查。可以读作者测试学 API，但不可把复制作者测试算作自造探针。探针用 tmp_path，不用生产和真实 LLM。
3. 自行用 AST 核查 intelligence/services/research_evolution/*.py 和 intelligence/api/research_evolution.py 的 transaction/try_transaction 调用，逐项写是否涉及测量/授权、是否需锁内复核和理由。预期范围为业务调用与基础封装分别计数，勿把数量一致当安全证明。
4. 把后续 execute 要运行的作者测试、你的探针清单及待验证问题写入 work/EXPLORE.md。至少保存 work/probes/test_reviewer.py 和 work/transaction-review.md。

本场只读源码并产出探针，不运行 pytest、不做全量验收、不签最终 PASS。时间最多 600 秒，探索最多 22 个模型请求，保留第 23 个请求交付总结。善用有限几次 bash 命令批量读相关文件（输出不要截掉关键处）；无需读不相关模块。若工具读失败，解释限制，不反复尝试同一受限路径。

最后用中文给出本场总结，并附一个 JSON 代码块：{"stage":"explore","revision":"f9ce5c6b296492b423400ad66d333784a4be13bc","baseline":"ffd1b7f1572067e9a4c7e3a5845e99cf7f876cfb","complete":true,"artifacts":[真实写入的绝对路径],"suspected_issues":[],"limits":[]}。未生成探针必须明确写出来。任何没有执行的测试不能报通过。
