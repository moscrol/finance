# H-01 局部修复与未解决的相邻缺口

## 身份与判定

- 源码分支 `fix/history-forward-boundary-0921`，固定提交 `d91aff9d8437fe903f3e643b65d4805aa4cf243c`，父件 #833 `7edfe24e76afbd5c365fbf97dd2414847b086f88`。
- 操作员结论：H-01 受测控制边界已修；历史整体仍 CHANGES_REQUIRED。不是独立 Spec/Quality 报告，不是完整 CI 或合并收据。
- 新测试通过真实 controller -> TaskFrame 序列化 -> control 投影 -> Episode 合同 -> history 工具登记；未执行这些工具。41 个案例为保护文本、合法显式续问、取消/新任务、未知边界与上游 context_dependent 反例。
- 原 #833、#834、#835 与此前三份证据包不覆盖。无合并、部署、生产回填或外审重试。

## 固定提交的验证

`frozen-*/result.json` 记录开始/结束时间、解释器、SHA、Git 状态、六个源码/测试/量具文件哈希、pytest 退出码、断言/夹具分类。每个冻结结果的前后身份一致且工作树干净。

| 检查 | 结果 |
|---|---|
| frozen-normal | 41 passed，exit 0 |
| frozen-partition | 24 failed / 17 passed，exit 1，0 fixture/collection errors |
| frozen-history-infer | 15 failed / 26 passed，exit 1，0 errors |
| frozen-follow-up | 6 failed / 35 passed，exit 1，0 errors |
| frozen-resolution-hint | 1 failed / 40 passed，exit 1，0 errors |
| frozen-cutoff | 4 failed / 37 passed，exit 1，0 errors |
| frozen-regressions/history-controller | 168 passed / 6.06s |
| frozen-regressions/material-honesty | 169 passed / 2.28s |
| frozen-regressions/history-assembly | 193 passed / 6.77s，已包含上述41例 |
| frozen-regressions/ruff | 全仓 Ruff exit 0 |
| frozen-regressions/diff-check | exit 0 |
| frozen-regressions/adjacent-unresolved | **2 failed / 0.48s，产品缺口未修** |

既有回归合计 530 passed（168+169+193），不要再加 41 造成重复计数。变异 exit 1 是量具的预期结果，不是修复正常版失败。相邻 2 failed 则是正常版真实失败，必须独立保留，不能被量具总 exit 0 掩盖。

H-01 夹具禁止并计数 socket.create_connection/socket.connect/DuckDB.connect 尝试；异常被吞仍在 teardown 失败。禁证券词典回退，知识关系路径与用户态指向临时目录，模型是离线替身。既有回归另有临时数据库测试，不宣称它们零 DB 调用；没有真实模型/生产数据测试。

## H-02 相邻反例（本包局部编号，不是工单号）

起始用户消息：`以2026年9月10日为信息截止日，只研究2026年1月1日至9月15日的本地历史数据，不联网补数；复盘这波农业怎么走出来的。`

以下两个真实续问均保存历史 Jan1-Sep15/截止 Sep10，history_query 被登记，但本地读取合同丢失：

1. `那它们见顶后谁接力？` -> material_scope=null；含 news_search/web_search/web_fetch 等。
2. `以前有没有类似，失败案例也看看` -> material_scope=null；含 web_search/web_fetch 等。

`test_adjacent_unresolved.py.txt` 是期望正确行为的失败测试原件；`adjacent-unresolved.txt` 保存观察值和两个 AssertionError。没有 xfail 转绿，也没把外部能力登记说成已经执行联网。

H-01 修的是受保护文本不授控制权；H-02 是合法继承时多份合同不同步，需沿可信用户材料恢复路径另修，不能从旧助手文字或无条件复制旧合同兜底。未解决前不接受整个历史候选。旧自然四题 not_passed、三领域独立报告缺失、联合树与新 main 均未重验。

## 过程失败与纠正

- 初次测试替身缺 relation_path，补成 tmp 下不存在路径；首次合法断言白名单过窄，正式 LOCAL_READ_CAPABILITIES 包含 mainline_context。均只修夹具，不为绿放开产品权限。
- 一次误编辑无 boundary 后缀的原候选路径已精确撤回自身改动；随后原 #833 树 clean。原始分区没有坏，路径初判已纠正。
- 手工撤保护过程：共享分区 23F/16P、infer 子集15F/12P，均恢复。首39例未抓住单独撤 resolution 标签保护，补2例后41例能够抓到1F。
- dirty-* 首版量具的 pytest 文本保留，但退出阶段 unittest.mock.patch.object 恢复 __code__ 抛 TypeError，缺 result.json，**不是有效变异收据**。runner-v1 原件保留；v2 用 try/finally 还原内存代码，未改磁盘源码，固定版重新验证。首错 traceback 只在会话工具记录，未假造其日志文件。
- dirty-* 与 dirty-v2-* 只签当时未提交树；正式结论看 frozen-*。两个失败的编辑调用没有改文件，不当产品回归。

## 复跑

在固定提交的干净源码树内，用项目 venv：

```sh
FWP_TEST_RECEIPT=0 PYTHONDONTWRITEBYTECODE=1 /opt/homebrew/bin/timeout 120 "$PY" scripts/probe_history_control_boundary.py normal --output <全新输出目录>
```

其他 mode：partition / history-infer / follow-up / resolution-hint / cutoff。一次 mode 一次新进程；输出目录不得复用。脚本在 `scripts/`，只替换进程内函数代码，finally 恢复，退出后不存在持久变异。
`record_frozen_checks.py.txt` 记录三组精确命令与相邻红测试，子命令各 timeout=120。其整体成功仅表示结果与记录预期一致，不能当全绿；逐项退出码在 receipt.json。

## 归档边界

归档只含校验所需源码量具原件、测试输出与收据。tmp/ 与缓存排除，不是工具执行工件；没有秘密或生产数据库。manifest 绑定全部归档成员，必须再用 docs 分支 `scripts/check_evidence_archive.py` 核 Git blob，不能只验工作区文件。通用教训已归入既有“门禁只覆盖自己的返回值”和“禁止 IO 要计数尝试”模式；本量具为 H-01 专用，不另造通用平台。
