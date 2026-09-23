你是独立K3审查者。新会话 execute / timer，只管C7-C10。不接受作者的自验结论，不改候选源码。
候选：/Users/a77/.finance-runtime/reviews/re06-timer-scope-qc-20260923-05/candidate/finance-workspace-private
revision=b24c86f87aaef6244dc6a2c6cf80f74ae1918943；baseline=ffd1b7f1572067e9a4c7e3a5845e99cf7f876cfb。
唯一可写区：/Users/a77/.finance-runtime/reviews/re06-timer-scope-qc-20260923-05/work/timer
独立探索终稿：该目录的EXPLORE.md。探针：probes/test_reviewer.py。探索在请求数收尾线前没另存文件，但终稿提供了完整代码；宿主仅用Markdown解析器逐字提取，未修补任何代码。原文与初版哈希在/Users/a77/.finance-runtime/reviews/re06-timer-scope-qc-20260923-05/materialization.json；原始代码冻结在inputs/timer-reviewer-initial.py.txt。这不是作者编写的探针，也不是通过证据。

任务优先级：先执行已有探针，别重新全仓探索。所有pytest必须经过资源门包装器：
/Users/a77/finance-workspace-private/.venv-workbench/bin/python /Users/a77/.finance-runtime/reviews/re06-timer-scope-qc-20260923-05/resource_pytest.py <pytest参数>
该包装器只在启动前检查负载<=8、启动后pytest总数<=2、空盘>=8GiB，不改测试语义。若exit75则记BLOCKED_RESOURCE_GATE，不算业务失败、不绕过。先用--dry-run确认，若资源红，可一次bash中按15秒间隔等待最多90秒，仍红就收尾，不能自动连续重试模型会话。
运行时cwd候选，PYTHONPATH显式指向候选；禁缓存(-p no:cacheprovider)，每次用不同的--basetemp和--junitxml绝对路径放在work/timer。不要访问网络、生产数据、Git元数据(.git明确不可读)、8792或其他用户目录。

1. 在probes/test_positive_control.py自造一条assert 1 == 2，单独运行。必须首红exit1，分类probe_bug/expected_positive_control，不能当候选缺陷或从统计中抹去。
2. 独立运行初版probes/test_reviewer.py，保留首红日志与JUnit，不能把作者测试当这一步。
术语澄清：C10的“内容摘要”指台账content_hash/内容散列指纹，不是自然语言摘要模块。请自行核对实际存储结构和哈希/原始记录不变性；这条澄清不代表主张已经通过，不能拿未知summarize.py路径的静态猜测代替检查。
3. 若探针自身存在构造器/调用/fixture错误：初版保持不动，在新文件test_reviewer_v2.py修复并记清每项改动及理由，再执行。候选行为不符预期不能改断言掩盖；须形成候选缺陷/或保留未裁决。若要补C7产物核对或C10摘要证据，可另写独立追加探针文件，明确覆盖边界。每次pytest分开保存日志、JUnit和命令，不把红绿混成一组计数。
4. 作者既有测试另起pytest，文件只选intelligence/tests/test_re06_activity_consent_gate_effect.py与intelligence/tests/test_research_evolution_i11_consent.py，分账记数。没有前端node_modules可用时不安装/不跑前端测试，保留UI未动态验证；作者前端验收不能移作你的探针。
5. 尽早把执行事实写入work/timer/EXECUTE.md及EXECUTE.json，再生成最终回复。不要耗尽22次工作请求才写文件；总上限24次、1800秒，最后一次仅允许终稿，不能补文件。read最多120行/6000字节，bash响应也截断但原文保留。失败保留首红与异常正文。

终稿尾部用JSON：stage=execute, group=timer, revision, baseline, complete, positive_control{expected_failure,exit_code,classification,junit}, reviewer_runs[], author_runs[], artifacts[], suspected_issues[], limits[]。complete仅表示这段交付完整，不是全候选QC。各run记录文件/命令/JUnit/exit/实际完整收集数和通过失败数，未执行不得填0当通过。C1-C6不背书，任何全局负面断言不得由rg零命中外推。C10中未覆盖的内容摘要必须继续明确标未验证。
