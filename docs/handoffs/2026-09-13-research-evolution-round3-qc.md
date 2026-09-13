# 研究进化四轨返修 · 第三轮独立审查

## 结论与范围

**暂不签收为「8 项缺陷族全部关闭」，不合 main。** 八项原固定反例在最新 SHA 均符合修复预期；四轨模块测试合计 346 passed，改动模块 Ruff 均通过。但扩大输入边界后确证 **5 项：3 个 P1、2 个 P2**。其中 J5 为本轮新回归，其余是本轮修复仍未封住的相邻路径。

只审查四轨最新修复，不审签 03/06、不改候选代码、不外呼模型、不访问生产用户数据或市场库。所有探针均为合成输入（字段刻意标 imported/observed 是为了压测来源边界，不是真人取证）。

| 轨道 | 固定 tip | 修复提交 | 独立模块测试 |
|---|---|---|---:|
| 01 | `7c50645a` | `d1a514ee` | 99 passed |
| 02 | `556efa2a` | `a869028e` | 65 passed |
| 04 | `fce5132c` | `1679d154` | 72 passed |
| 05 | `19e6176f` | `24bce5e8` | 110 passed |

主树脏且 detached，完全未动。测试在 `/tmp/research-evolution-round3-qc/{01,02,04,05}` 的固定 SHA 干净检出执行；结束仍干净。文档分支从 fetch 后 `gitea/main@e40f22b8` 建立。

## 发现（按影响）

### PV6 [P1] 放弃终态仍能冒充费用覆盖（05，PV4 相邻遗漏）

定位：`intelligence/services/product_value/summarize.py:136–151, 692–702`，特别是 `terminal_state != open` 就返回 True。

- 第一对完整任务已有 CNY 0.46；第二对只有分配/同意，没有 run、时间区间或费用证据。
- 给第二对加 `task_abandoned` 后，用真实 `measure_pair()` 产生收据：仍 `incomplete`，`timing_missing`，`cost_items=[]`、`unknown_cost_components=[]`。
- 只并入这张收据，完整成本 **unknown→known、缺口 2→0、金额仍 CNY 0.46**。前端放弃意图和服务端放弃终态两种输入都复现。
- 放弃证明任务状态，不证明费用已被测量；规格 05 §3/§4 要求「未观察到调用不作零费用依据」「缺项时完整成本 unknown」。这是缺账，不是要求原流程必须有模型费用。
- 修前 `7c7c388b` 同样错误；本轮只挡住 `open` 空壳，没有挡住带终态的空壳。

建议：分别表达任务状态测量与费用覆盖；核销费用缺口应有任务级成本事实或明确的无费用/不适用依据，不能拿终态、任意耗时的存在替代。保留原流程无 run 的合法通路。

### PV7 [P1] 已由 task_started 取得资格者仍被未来窗移出分母（05，PV5 相邻遗漏）

定位：`intelligence/services/product_value/summarize.py:493–506`，`participant not in declared_window_end` 阻断按激活时间推导完整周的通路。

- 六人 09-15 有服务端 `task_started`，截至 10-11 完整观察周已过；q1–q3 有首轮主动复用记录，q4–q6 没有复用观测。
- 原结果：分母 6、分子 3、rate=0.5；三条 `reuse_observation_missing`，判据 unknown。
- 仅给 q4–q6 追加 10-05 至 10-18 的未结束窗口，结果 **分母 6→3、rate 0.5→1.0、unknown→pass**。缺测成员被移出分母。
- 修复保存的是「已经显式出现完整 reuse_observed 窗」的资格，没有保存通过激活记录推导出来的资格。规格分母是激活后完整观察周者，不要求先拥有一条复用观测。
- 修前 `7c7c388b` 同样错误。现有 `p20` 控制是 10-09 才激活，10-11 本来就未满观察周；不能据其排除本例 09-15 已激活的人。

建议：队列资格独立于复用观测，用冻结观察协议与可信激活时刻确定；追加未来窗只增缺测标签，不撤销已成熟资格。缺首轮复用观测仍留 unknown。

### J4 [P1] 字符串顺序仍可让同 ref 旧哈希复活（01，J2 相邻遗漏）

定位：`intelligence/services/judgment_maintenance/assess.py:144–146, 176–181`，隐式替代用 `_sort_key(q) > _sort_key(p)` 判断更晚。

同 ref、同 valid_from：h1 登记 `09-10T10:00+08`；h2 登记 `09-10T03:00Z`（实际是北京时间 11:00，更晚），h2 于 09-11 过期。09-12 评估：h2 字符串反而更小，被当较旧，**h1 留在 live，items_open=0，无 validity_ended**。只把 h2 写成完全等价的 `09-10T11:00+08`，马上变成 **source_expired/open/unknown，items_open=1**。

修前两种写法都复活；修后只修好同偏移写法。需将记录先后按真实时刻比较，不能用 ISO 文本顺序推断事实先后。缺时区/日期粒度应保留不确定性，不造精确先后。

### D5 [P2] used_is_current 提前返回仍能盖掉时间缺口（04，D4 相邻遗漏）

定位：`intelligence/services/research_diagnostics/rules.py:435–438, 481–493`。新增 `time_unknown` 优先级位于 `used_is_current -> valid` 早退之后。

09-04 使用 ann:004@n1；before 中 n1 的失效日为 09-02，但 recorded_at 缺失。当前 D4 主例为 unknown。将后续 current 换成 09-06 才重新生效/登记的同 ref 同 hash n1 后，`used_is_current` 只看 hash/expired/valid_to、不看使用时刻的 valid_from/recorded_at，结果 **unknown→context，time_metadata_missing 清零**。

保持同一 current，分别把缺失 recorded_at 补为 09-01 / 09-07，结果为 issue / context。这证明未补齐时不能唯一确定，后来的恢复无法证明 09-04 当时有效。修前也错，本轮移动 `later` 优先级没覆盖早退。

建议：对使用时刻判断 current 的有效性与可知性；让时间缺口裁决不被未生效/后知 current 绕过，保留合法当前版本对照。

### J5 [P2] 哈希兜底顺序被误当成“更晚记录”，抹掉版本歧义（01，本轮新增回归）

定位：`intelligence/services/judgment_maintenance/assess.py:176–181`。

同 ref、同 valid_from、**完全相同 recorded_at**、不同 h1/h2：修前保留 `ambiguous_version_order` gap；本轮 `_sort_key` 的第三项含哈希，h2 > h1 被当成“更晚记录”，先退休 h1，再也检测不到歧义，gap 清零。

哈希排序只宜用于输出确定性，不是先后证据。退休条件应只看已证明的严格较晚记录；时间相同/不可比较时保留冲突提示。与 J4 可一起改，但两条反例不可互相替代。

## 对原 8 项固定反例的复核

- J2：同偏移、严格更晚记录的更正版过期后保持 source_expired/open/unknown。
- S5：市场日边界三个评估时刻均 selected；P2：不同 due/available 窗维持两任务，今日 selected、未来 blocked。
- S4：synthetic 父报告不能由 observed 子项升级；全 observed 正常保留；未知父枚举拒绝。
- D3：已公告未生效替代不追责，提前生效控制仍 issue；D4：原缺时间+后知更正固定例为 unknown，双向补全控制正确。
- PV4：纯 assignment 空壳并入后仍 unknown、CNY 0.46、缺口 2；PV5：原“显式首轮已完整”例仍分母 q1..q6、rate .3333、fail。

归档探针的 SHA 断言仍写旧候选；本轮复制执行，只替换检出路径与固定 SHA，保留原脚本 SHA256，不覆盖旧证据。S4 非法枚举按预期捕获异常。不是凭 exit=0 宣称转绿：额外逐字段断言原预期。

## 收据与复跑

持久证据目录：`~/.finance-runtime/reviews/research-evolution-round3-qc-20260913/`：

- `manifest.json`：固定 SHA、树洁净状态、逐文件 SHA256。
- `tests-{01,02,04,05}.log/.exit`、`ruff-*.log/.exit`：四轨 346 passed；Ruff 全通过。
- `original-{01,02,04}.json`、`rerun-*.json`：原反例复核。
- `updated-01.json / updated-01-before.json`、`new-{04,05}.json / before-{04,05}.json`：五个新边界及修前对照。
- `boundaries-test.log`：五条独立安全性质断言 **5 failed**，对应上述五项，失败是缺陷证据而非环境错误。

探针与断言同时入本审查文档分支：`docs/verification/research-evolution-round3/{probe_new_boundaries.py,test_new_boundaries.py}`。它们不属于产品回归测试集，刻意保留红灯供返修者定位；不要混入全仓绿灯统计。默认读 `/tmp/research-evolution-round3-qc/{01,04,05}`，可用 `RESEARCH_EVOLUTION_QC_ROOT` 指定其他父目录（需要同名轨道子目录）；单轨也可显式传 root。

```bash
PY=/Users/a77/finance-workspace-private/.venv-workbench/bin/python
$PY docs/verification/research-evolution-round3/probe_new_boundaries.py 05 /path/to/05-tree
$PY -m pytest -q docs/verification/research-evolution-round3/test_new_boundaries.py
```

没有重跑全仓或前端/端到端/注册表门禁，不给任何组合版本合并凭据。此次模块收据为 `~/.finance-runtime/test-receipts/20260913T101024Z-{7c50645a,556efa2a,fce5132c,19e6176f}.json`。

05 所报全量 9650P 的收据确实存在：`20260913T094959Z-7c7c388b.json`，exit 0、77 skipped；但 **revision 是父提交 7c7c388b，dirty=true，仅列 summarize.py 和对应测试两文件**，不是最终 24bce5e8/19e6176f 干净树凭据。它可说明提交前工作区跑过，不凭此断言虚假，也不外推最终 revision 或四轨组合已过门。

04 inflight 还写着“已提交并推 gitea，最新 1679d154”；本地远端跟踪 ref 仍在 `b5cee17a`，且不含新修复。与用户本次“新提交均未 push”的口述矛盾，建议改为“旧版曾推，新修复未推”。未为审查擅自 push。

## 决策与下一步

| 方案 | 结论 | 原因 |
|---|---|---|
| 只复跑八项原例后签收 | 否 | 固定样本通过不保证同类边界封闭 |
| 在四轨原树加测试/修代码 | 否 | 审查不占执行者工作区；固定检出可复现 |
| 修改候选让本轮探针绿后合并 | 否 | 用户只授权审查；保留独立证据给原轨返修 |
| 独立五条断言+修前对照，原测试另计 | 采用 | 区分新回归/残余遗漏，且不污染绿灯统计 |

01 修 J4/J5、04 修 D5、05 修 PV6/PV7；02 本轮未新增实现发现。各轨交新 SHA 后复跑原 8 例、这 5 例与合法路径对照。06 可以继续接线，但只能在最终组合候选上另跑集成验收与完整门禁。未 push、未合并、未部署。

可迁移方法：测试**表示不变性**（同一时刻换时区写法不改事实结论）、**追加信息不消灭未知**、**已取得队列资格不被后续缺测撤销**。本轮固化为针对本仓合同的探针，不把业务夹具塞进通用工具清单；`harness-reference` 当前脏且非同步基线，未改它。
