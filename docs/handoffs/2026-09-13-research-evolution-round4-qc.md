# 研究进化四轨返修 · 第四轮独立复核

## 结论与范围

**原五个固定反例通过；不接受“相关边界已封堵”的扩大解释，整包暂不签收。** 新增四个安全断言均红：01 的 J5 另一哈希顺序、J6 跨午夜 cutoff、J7 不可比时间，以及 05 的 PV8 有计时无费用覆盖。02/04 本轮未新增实现发现，不代表集成验收通过。

候选固定为 01 `2c372331`、02 `e27b3352`、04 `fcc7838c`、05 `cb892d93`。各自与修复提交 `dbf4d357` / `a869028e` / `8db4bbd9` / `2f0d3410` 之间只改 inflight、PROGRESS 文档。主检出有他人未提交改动，未在那里跑被测业务。四轨均另开 detached worktree；未修改候选、未 push、未合并、未部署。

本轮为离线合成输入的服务复核，不是实际用户事故、Workbench/06 联测或真人试点证据。

## 1. 接手与原修复核实

- 原四轨 SHA 与汇报吻合，检查开始/结束均干净。
- `git ls-remote --heads gitea` 核实：01/02/05 无对应分支；04 为 `b5cee17a`，是本地祖先。未推新修复的口径正确。没有从本轮瞬时扫描外推“历史上没有其他 agent 工作”。
- 原 QC `test_new_boundaries.py` **原文不改**，只设 `RESEARCH_EVOLUTION_QC_ROOT` 指向本轮检出：**5 passed**。
- 原 J4 的同日时区换写逐字段相等；原 J5 的 h1/h2 歧义可见；D5 unknown、补早 issue、补晚 context；PV6 两种放弃源成本仍 unknown；PV7 六人分母/0.5/unknown 保持。
- 归档探针只改路径和锁定 SHA，保留原脚本 sha256：J2 过期保持 source_expired/open；J3 自指拒绝；S5 三时刻 selected；P2 到期/发布两组均 selected=1、blocked=1；S4 synthetic 天花板和未知枚举拒绝；D3 context/issue 对照、D4 unknown；PV4 空壳仍 unknown；PV5 分母 6、比率 0.3333、fail 前后不变。

## 2. 新发现（按风险排序）

### J6 [P1] 01：跨午夜换写，仍可提前引入截止日之后的更正版

位置：`intelligence/services/judgment_maintenance/assess.py:88`（版本放置）；`contracts.py:241-242`（`day_of` 直接截前十字符）。

同一 ref，基线 h1 已知；h2 的登记时刻为：

- `2026-09-11T16:30:00Z`
- 等价表示 `2026-09-12T00:30:00+08:00`

固定 `as_of=knowledge_cutoff=2026-09-11`，其余输入不变。前者得到 h2 `content_changed/open`、`items_open=1`；后者无待办、`items_open=0`；**两者都标 strict**。

J4 改了退休比较和排序，但进入比较之前的 `known_day` 仍按文本日期。日频不意味着可以按供应商时区分别定义“同一天”；若按 A 股市场日截止，UTC 写法把次日才知信息带进前一天。

建议：明确统一市场日边界，将可解析绝对时刻转换后再取知识日；cutoff 过滤、默认有效期及 expired_at 的日期放置一起检查。不能仅修 `_sort_key`。修前 `7c50645a` 同样复现，属于 J4 缺陷族遗漏，不是这次新引入。

### PV8 [P1] 05：辅助任务只有开始/放弃时间，仍把未知费用核销

位置：`intelligence/services/product_value/summarize.py:138-149,695-701`；计时来源 `measure.py:324-395`。

保留一组完整配对，已知费用 CNY 0.46。第二组中，原流程保留真实人工计时/产物路径；辅助流程只保留同意、分配、开始和服务端放弃事件，无 run/attempt、费用条目或费用覆盖声明。`measure_pair` 生成：

- 辅助任务 `attempts=[]`、`cost_items=[]`、`unknown_cost_components=[]`；
- 开始 14:00、放弃 14:20，所以 `timing.end_to_end_minutes=20`、`reason=None`；
- 收据 incomplete，但原因只剩质量未审。

并入前完整成本 unknown、缺口 2；并入后 **known、缺口 0、金额仍 CNY 0.46**。原流程费用缺口可被人工计时路径合法覆盖，但辅助任务没有运行/用量记录不能由经过 20 分钟推出零模型费。

根因：PV6 去掉了“终态即覆盖”，却把通用耗时当成费用覆盖；未区分原流程人工测量和辅助服务费用。规格 05 §3 明写“未观察到调用不作零费用依据”。

建议：按任务条件/费用适用范围确认覆盖，辅助流程需运行/用量事实或可审计的明确零费用证明；计时只覆盖时间维度。保留原流程合法人工计时通路，不将所有无 run 任务一刀切。修前 `19e6176f` 同样复现，是原缺陷族遗漏。

### J5-补充 [P2] 01：基线哈希排序靠后时，同刻歧义仍被 unchanged 早退吞掉

位置：`intelligence/services/judgment_maintenance/assess.py:215-219,322-323,402-405`。

固定相同 ref、生效日、精确登记时刻，基线 h1；另一个版本哈希 h0。当前算法确实没有相互退休，但哈希兜底选中 h1，判 unchanged 后直接跳过项构造，而歧义 gap 只在项构造时写。

结果：`items_open=0 / gaps=[] / pit_grade=strict`。仅把非基线哈希从 h0 改为 h2，就出现 `ambiguous_version_order`。哈希字典序无业务含义，不应决定用户能否看到歧义。

建议：歧义应在报告层独立传播，不能依赖 `emit_unchanged` 或被选中的版本是否等于基线。新增测试遍历基线在 tie 集合中排序靠前/靠后两种情况。修前也无 gap；原 J5 固定 h1/h2 例通过，不等于 J5 已全封堵。

### J7 [P2] 01：不可比时间仍参与业务取最大值，未保留歧义

位置：`intelligence/services/judgment_maintenance/assess.py:147-151,215-219`。

基线 h1 登记 `2026-09-10T10:00:00`（无时区）；h2 登记 `2026-09-10T10:00:00+08:00`，同 ref/生效日。前者文本保留 10:00，后者归一到 UTC 02:00，`max(live, key=_sort_key)` 选 h1：`items_open=0, gaps=[]`。

把 h1 缺失时区补成 +09:00，真实时间早于 h2，得到 h2/open；补成 +07:00 则相反、无待办。这证明缺信息时有两个不同业务结局，不能静默决定“没变”。

退休分支虽不使用不可比时间，**选择 current 仍在使用**；歧义判据又只认排序键前两分量完全相等。`trade_date_only` 降档不是歧义提示，且不阻止待办消失。

建议：将“用于稳定展示的总排序”与“可证明的业务先后”彻底分离；不可比且有冲突的候选保留 gap。修前也漏歧义，但当前补丁将此例从 h2/open 改成 h1/无待办；不把修前错误选择当正确基线。

## 3. 测试证据与汇报口径

### 本轮实际重跑

| 固定候选 | 模块 pytest | 模块 Ruff |
|---|---:|---|
| 01 `2c372331` | 101 passed | 通过 |
| 02 `e27b3352` | 65 passed | 通过 |
| 04 `fcc7838c` | 74 passed | 通过 |
| 05 `cb892d93` | 112 passed | 通过 |

合计 **352 passed**；原 QC 安全断言另 **5 passed**；本轮新增安全断言 **4 failed**，不是产品回归集全量红灯。01 日志有 pytest 清理共享临时目录告警，不影响上述 exit=0；不能把其清理噪声说成业务失败。

### 全量收据核实（不是本轮重跑）

目录 `~/.finance-runtime/test-receipts/`：

- `20260913T105610Z-dbf4d357.json`：9641 passed / 77 skipped / exit 0。
- `20260913T110715Z-8db4bbd9.json`：9614 passed / 77 skipped / exit 0。
- `20260913T111723Z-2f0d3410.json`：9652 passed / 77 skipped / exit 0。

三者解释器均主树 venv、`dirty=false`、`worktree_dirty_total=0`、没有绕过依赖门。汇报这次确实解决了此前父提交+脏文件收据问题。收据插件不列 xfailed 数，本轮不独立确认口头的 2 xfailed。最终交付头只多文档提交，不将该事实虚构成代码未测；但 06 合成候选仍需自己的完整门禁。

“新增 6 条全部先红后绿”不准确：用候选新增 D5 两条测试、只在内存换回修前 rules 实现，结果 **1 failed / 1 passed**。`test_d5_filling_missing_record_time_still_decides_both_ways` 是合法路径负控，修前本就通过。应写“6 条新增回归/负控，其中主反例先红后绿”，不把对照测试冒充缺陷检出测试。脚本 `d5_before_control.py` 明确不是父提交全量测试。

### 重放与产物

- 原始证据：`~/.finance-runtime/reviews/research-evolution-round4-qc-20260913/`，入口 `manifest.json`。
- 隔离树：`/private/tmp/research-evolution-r4-qc-xD9oMm/{01,02,04,05}`。
- 本分支探针：`docs/verification/research-evolution-round4/{probe_adjacent.py,test_adjacent.py,d5_before_control.py}`。

```bash
export RESEARCH_EVOLUTION_QC_ROOT=/private/tmp/research-evolution-r4-qc-xD9oMm
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  docs/verification/research-evolution-round4/test_adjacent.py -p no:cacheprovider
# 当前候选预期：4 failed（刻意揭露未修问题）
```

## 4. 决策与下一步

| 方案 | 判断 |
|---|---|
| 原五例绿、全量绿即直接签收 | 否；上述四条相邻反例仍可复现，测试数量不覆盖未编码的安全性质 |
| 仅修文字，忽略新边界 | 否；涉及历史知识泄漏、费用缺口核销和待办消失 |
| QC 直接代修业务实现 | 否；用户本轮只要求审查，保留作者与审查者分工 |
| 留可重放反例，作者修复后复验，再交 06 组合验收 | 采用；固定反例/缺陷族/集成验收三层分开 |

01 先修 J6、J5-补充/J7；05 修 PV8。新版本需重跑原八例+原五例+本轮四例，并保留合法人工计时、明确时序、同刻两种哈希顺序对照。02/04 无需因为其他轨有新发现而重写实现。

未重跑全仓、前端、端到端或注册表；未做 01/02/04/05 组合、03/06 接线/真人试点；不据此签 main 合并或部署。04 推送可单独授权用于远程评审，和整包 QC 通过是两回事。

方法沉淀沿用上一轮的“表示不变性、缺口不被无关观测核销”；本轮把业务反例落成可运行脚本，不重复造通用框架。`harness-reference` 已有他人脏改，未动。
