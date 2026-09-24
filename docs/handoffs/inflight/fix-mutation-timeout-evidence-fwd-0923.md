# 在途 · fix/mutation-timeout-evidence-fwd-0923 · 变异量具超时留证前向到 main

接替 `fix/mutation-timeout-evidence-0922`（`94eddad18`，已推无 PR）；那份 inflight `fix-mutation-timeout-evidence-0922.md` 保留为历史记录，其中「未 push、未提 PR」说的是旧分支。

## 这个分支做什么
`git merge gitea/main` 进量具分支，唯一冲突 `scripts/review_probes/run_extraction_mutations.py`，按意图解：保留 main 的骨架（`SUITES` 多套件、`_parse_args` 与 `custom` 套件标签、`run_tests(root, out, label, tests, targets)`、LANG/TMPDIR/KNOWLEDGE_WIKI 透传），把量具的超时留证叠上去（`save_json`、`_run_logged_command` Popen + `start_new_session` + `killpg`、`-u -vv --capture=tee-sys faulthandler_timeout=45`、缺 JUnit 记 `executed=None`、`check_result` 进程状态门、`execute()` 逐步落盘 results.json、先验红再跑绿）。冲突标记之外有一处静默接缝：`execute()` 闭包要把新的 `tests` 参数转发给 `run_tests`。只改评审工具，不碰产品代码，180 秒帽不动。

`tests/test_extraction_mutation_runner.py` 适配 `tests` 参数；`_mini_repo` 夹具只给被测阶段 2 秒预算，围绕它的真实 pytest 起跑给 20 秒——负载 55–75 时 baseline 起跑 >2 秒被误读成被测失败（同参数在负载 27–45 时 0.39 秒起跑通过，对照见 PR）。

## 当前状态
已 push gitea、已开 PR（base main）。**未合、未部署。** 四叶由主会话在预览树串行跑；本分支自跑量具自检 + 选择器测试见 PR 正文。

## 归因结论（照录，不翻旧案）
09-18 那次 180 秒超时现场不存在，本分支不解释它，只保证下次可归因。09-22 用移植量具重建现场：publication 套件里 `test_skill_timeout_degrades_one_module_and_continues` 真 fork 知识库 RAG 子进程（`kb_rag.py` 三个调用点，`ask_types.py` `use_wiki_rag` 默认 True），全线程采样 88.4% 在 `selectors.select`；空载 51 秒占帽 28%，负载 133 秒占 74%。八条 publication 变异 **7 杀 1 存活**，存活的 `sse-drains-between-read-commit` 由 `test/sse-drain-mutation-guard-0923` 处置（既有见证未登记，非无人看守）。

## 下一步
1. 主会话：预览树四叶 → 用户确认 → 合入；INDEX #66 行。
2. 让不考检索的测试别走真检索（`TurnOrchestrator` 传 `use_wiki_rag=False` 或夹具注入桩）——另立单，不在本分支。
