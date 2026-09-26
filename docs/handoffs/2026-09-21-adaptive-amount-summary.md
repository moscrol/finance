# 判官诊断与成交额均值窄修复（2026-09-21）

## 身份与裁决

- 工作树 `~/finance-worktrees/adaptive-research-loop`，分支 `feat/adaptive-research-loop`。
- 判官诊断：`00fb5be6335c21ce08f3229c11a71f862c9ab321`。
- 成交额汇总：`60a41f2faad1c92e5a500568eb47ca51dc9a4bbe`。
- 固定验证候选（含变异脚本）：`59464c4000affd1449146e11f4398568850feee8`，验证前后全树干净。
- 本轮只证明程序化统计和失败诊断路径；没有新自然模型会话，原真实研究仍未通过。未 push、开 PR、合 main、部署或操作生产 8792。

## 背景与发现顺序

上一轮干净 `72a2ac534` 的 K3 真实会话 `run_20260921_203845_282895` 已自然接受父 PLAN，启动子研究并取得量价/板块证据，但判官两发耗尽共享 150 秒窗口，公开 partial。原稿把 14 日成交额均值写成 6.55 亿，独立复算为 6.615335714 亿；另把“本地未收录涨停记录”写成“无涨停”。原件不改，详见 `2026-09-21-adaptive-k3-live-reverification.md`。

### 1. 先保留已发失败，不推断历史异常

原终态只剩窗口拒发原因，最后一个实际调用的失败身份被覆盖。`SemanticEpisodeOutcome` / `_JudgeCall` 增加可选 `last_dispatched_failure`：独立/相关判官均保存最近失败，在窗口耗尽或余量拒发时附脱敏收据。顶层仍描述零秒拒发，不把上一发 HTTP/TimeoutError 错塞到本发。

收据含零基 attempt、timeout_asked、remaining_seconds_at_entry、稳定 issue、exc_class、http_status。不保留 raw 错误、完整历史或未经测量的实际耗时；成功重试及首发前拒绝无旧失败。未改重试策略、75 秒单发帽、150 秒共享窗、根预算或公开降级。历史失败身份已经丢失，新字段不能补回旧工件，也不证明服务超时已解决。

### 2. 保持 local_only，复用只读 SQL

真实合同只有 finance_query / evidence_lookup / memory_lookup / mainline_context 四种本地只读能力；通用 derived_calculation 尚不在该审定面。本次简单统计由已有 DuckDB 查询完成，不开放沙箱、网络、子进程或新授权。

`stock_daily.amount` 原聚合仍是 SUM。新增 `amount_mean` + `amount_valid_count` 必须一起选择，AVG/COUNT 共用 `CASE WHEN isfinite(amount) THEN amount END`：零计入，NULL/NaN/正负无穷不计入。全空均值为未知、分母 0；无匹配行为零证据。统计在 LIMIT 之前完成，LIMIT 只限返回股票组数。

按名称分组会因历史尾部空字符把同一股票拆开。因此 dimensions/group_by 必须恰为 stock_code，明确 time_range.start/end，只允许代码筛选；名称与逐日详情另查。汇总别名即使未被 select，也不能作为行筛选，防止被误编译成 amount 原列过滤。截止日和交易所后缀校验不放宽。

### 3. 窗口、分母与证据一起交付

请求窗口及“已入库有限数值算术均值/零值计入/样本数不证明交易日齐全”放在证据前端并进入内容哈希。相同数值但不同请求窗口不能共享证据身份；汇总不伪造为某一天的结构化 amount 观察值。字段从现有 schema 自动暴露，校验错误给出可执行的重试形状。

分组结果的 source_date 是组内 MAX(date)，不是实际日期轴。非时间分组不能用它推定窗口前端缺数；空结果仍记缺口，有真实日期分组仍保留缺口遥测。截组提示不再暗示组内日期被 LIMIT 裁掉。

最初注册表测试 limit=1，而旧缺口逻辑本来就跳过撞上行帽的结果，不能保护新遥测条件。补 limit=25 的同一汇总查询后，撤去保护可稳定误报；另以日期分组缺前端数据验证不漏报。

## 方案比较

| 方案 | 结论与理由 |
|---|---|
| 在零秒拒发顶层填上一发异常 | 否；混淆实际发出与拒发，另设最近失败收据 |
| 增加判官窗口/根预算或放宽重试 | 否；没有证据证明能修服务稳定性，本轮仅诊断 |
| 开放通用计算沙箱 | 否；改变 local_only 的已审定权限面，简单统计无需它 |
| 从截断明细让模型心算 / 只给样本数 | 否；前者可能错分母，后者仍未提供正确均值 |
| 改 amount 为 AVG | 否；破坏原 SUM 合同，用新指标并绑定分母 |
| 按 stock_name 分组或允许行情值过滤 | 否；改名/空字符拆组，值筛选改变分母 |
| 把 MAX(source_date) 当覆盖起止 / 对所有分组禁缺口 | 均否；分别误报和漏报，用真实日期轴区分 |
| 人工改旧稿并改判通过 | 否；不能证明模型自然调用、引用及独立复核 |

## 验证与收据

1. 判官补丁提交前：9 模块 587 passed，固定收据 `~/.finance-runtime/test-receipts/20260921T140020Z-fe32e651.json`，dirty=true；六项进程内撤线均因缺 last_dispatched_failure 失败。这个脏树收据不冒签新干净版本。
2. 成交额专用测试 36 项：冻结真实 14 日数值、名称尾空字符、有限值和零、全空/空集、30 日超行帽、多股票排序限组、只读连接、窗口哈希、旧 SUM/明细、非法请求前置拒绝、预算后保留分母及窗口。
3. local_only 注册表真实装配执行：阻断 socket/DNS/subprocess、默认外呼工具构造和计算 loader；授权仍四种，只读证据可交付。不是自然模型策略验收。
4. 干净 `59464c400` 相关 22 模块：719 passed / 8 skipped / 0 failed / 0 error。8 个 contains 旧用例需该工作树本地行情库，本轮未挂生产库；新统计测试使用临时 DuckDB 全执行。全仓 Ruff、diff check 通过。
5. 固定收据 `~/.finance-runtime/test-receipts/20260921T145131Z-59464c40.json`，解释器 `.venv-workbench/bin/python`，Python 3.12.13、依赖指纹 `3328bed61f3e21ea`、dirty=false。`check_test_receipt.py <固定路径> --expect-revision 59464c4000affd1449146e11f4398568850feee8` 通过。旧 be660 全量和这些定向测试都不是新 revision 完整合入凭证。
6. 永久变异定义 `scripts/review_probes/stock_amount_mutations.json`，复用 `run_extraction_mutations.py --suite stock-amount`；独占临时树、精确锚点、源码可编译、失败必须为已执行测试断言、恢复字节指纹一致，禁止导入/收集错误冒充验红。
7. 五种变异：AVG 改 SUM 1F；非有限值计入分母 3F；丢请求窗 1F；聚合 MAX 冒日期范围 1F；隐藏所有分组缺口 1F。每项恢复绿，首尾 36P，临时树成功移除。窗口变异首先命中窗口文案断言；同值不同窗哈希断言在恢复后的完整用例中通过，不夸称本次红灯直接来自哈希断言。
8. 扩展了共用验证脚本，所以复跑原默认 extraction 的 35 种变异，每种均红后绿，首尾 165P，临时树移除。不是新增成交额业务覆盖。
9. 原件根 `~/.finance-runtime/adaptive-stock-amount-20260921/`，`mutations/results.json`、`extraction-compatibility/results.json` 保存日志/测试 XML/diff/hash 与精确 SHA。代码地图刷新到 59464c400。
10. 共享图谱审计 exit0，268 条路径/符号断言无漂移，新增三个符号均按本分支校验并标 PENDING；这只签日志自述的 checkout，不代表主线整树干净或能力已合入。日志 `graph-audit.log`。共享记忆由既有自动同步提交 `94b6a75f`，本轮未主动 push；同期另一会话的记忆改动未动。

## 下一步与边界

- 自然模型是否选用均值接口、正确引用分母/日期、独立判官通过及自然 repair/rejudge 仍待新隔离验收；原 n=1 partial 和错稿不改判，不追加请求追状态词。
- “未收录 => 未发生”的超证据否定另做窄修复，统计接口不解决此问题。
- 无工具改稿+self partial 重核格、正常长答无推理泄漏仍没有新增真实样本。
- 当前 revision 全量 Python/前端/E2E/跨仓 registry 叶子、独立 Spec/Quality 及主线前向整合尚未完成；未 fetch，不把本地 gitea/main 缓存当最新基线。
- 生产曾在旧复验前后健康、后来拒绝连接，两者分时记录；本轮不探测/重启生产。

## 沉淀

复用现有失败注入工具，不另造验证框架。永久业务测试与变异定义已入库。跨项目规则是“聚合身份按稳定实体键，统计证据同时绑定窗口/分母/算法；返回组上限不等于组内观测上限”，补入共享记忆 `aggregation-key-use-natural-primary-key.md`。harness-reference 当前脏且领先其远程，本轮不改其中的工具清单；这次只扩已有工具套件，不宣称建立新通用模式。
