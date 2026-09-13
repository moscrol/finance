# 四轨第四轮返修 · 第五轮独立 QC（2026-09-13）

## 结论与范围

**固定旧反例确实修复，但整包仍暂不签收。** 本轮新增 4 个安全反例（3 P1、1 P2），另有 1 项失败收据归因错误。01/05 继续返修；02/04 保持候选，不等于 06 组合验收。

审查固定检出：01 `b886b796`、02 `e27b3352`、04 `fcc7838c`、05 `15da570f`。01 的 `cfd88c04..b886b796` 与 05 的 `197133f2..15da570f` 均只改交接/PROGRESS，因此可核对修复 SHA 的代码收据，但不把它称为最终文档 SHA 实跑。

主检出 detached HEAD 且大量他人未提交内容，不动；四轨在 `/private/tmp/research-evolution-r5-qc-Dmm5xA/{01,02,04,05}` 隔离检出，检查前后均 clean。本报告分支只放审查产物，不代修、不审签 03/06；未 push、合并或部署。

证据：`~/.finance-runtime/reviews/research-evolution-round5-qc-20260913/manifest.json`（固定 SHA、路径、脚本/输出 SHA256）。合成数据模拟 imported 来源以测试真实指标分支，**不是实际参与者读数**。

## 新发现

### J8 [P1] 条件观测仍按文本日期过知识截止，次日观测可提前触发条件

定位：01 `intelligence/services/judgment_maintenance/conditions.py:111-116`，仍调用 `day_of(obs.recorded_at)`；新 `market_day_of` 只接到了证据版本路径。

- 同一市场日 `as_of=knowledge_cutoff=2026-09-11`，观测 `market_stage=反弹`。
- `recorded_at=2026-09-11T16:30:00Z`（实际上海 09-12 00:30）→ `condition_true`、`epistemic=observed`、报告 `strict`、`items_open=1`。
- 仅换写法 `2026-09-12T00:30:00+08:00` → `condition_unknown`、`unverifiable`、`items_open=0`。
- 合法负控：`2026-09-11T15:30:00Z`（上海当日 23:30）仍正确触发 true。

影响：升级/降级/放弃条件可以吃到未来一天的观测，且标严格回放。J6 缺陷族尚未扫全；既有代码遗漏，不是新补丁改坏。

修复方向：把条件观测知识日也纳入同一市场时区合同；不以“一律 unknown”代替正确截止过滤。

### J9 [P2] 绑定创建日仍截 `created_at[:10]`，可在绑定成立前生成维护样本

定位：01 `intelligence/services/judgment_maintenance/contracts.py:427-429`；调用点 `assess.py:599-610` 与 `392`。

- 绑定真实创建时刻上海 09-12 00:30，回放 09-11。
- UTC 写法 `2026-09-11T16:30:00Z` → `objects_bound=1`、`dependencies_checked=1`、`items_open=1`、`strict`。
- 东八区写法 → `objects_bound=0`、`dependencies_checked=0`、`items_open=0`，有 `binding_not_yet_effective`。

影响：同一绑定只换时间戳表示，就违反“不在 created_at 之前生成维护样本”合同。与 J8 同族但独立调用位置，原代码已存在。

修复方向：`DependencyBinding.created_day` 也应统一市场日归一，不继续截文本日期。

### J10 [P1] 歧义进状态签名、却没进项身份，报告去重吃掉最终 open 项（本轮回归）

定位：01 `assess.py:140-144`、`256-292`、`420-425`、`630-633`。

构造三个版本（同 ref，基线 h1）：

| hash | valid_from | recorded_at |
|---|---|---|
| h1 | 09-01 | 09-10 09:00+08 |
| h2 | 09-02 | 09-10 20:00（naive） |
| h0 | 09-02 | 09-11 00:30+08 |

09-10 当前 h2、无歧义；09-11 得知 h0 后，h2/h0 时序不可比，显示排序胜出者仍 h2。

新补丁把 `ambiguous` 加入 `_State.signature()`，于是生成前后两个状态；但二者 `_dedup_key` 和 `item_version` 都相同（都是基线 h1→当前 h2，`hash_changed`）。前一项被标 `superseded`，后一项应当 `open`；末端 `unique_items.setdefault(it.id, it)` 留第一项丢最后项。

实测最终：**`items_open=0`、仅剩 09-10 的 superseded 项、报告 gaps=[]**。原修复前 `2c372331` 同输入仍有 `items_open=1`（虽原来缺歧义）。因此这是本轮新出现的待办丢失，而非仅剩一个旧提示缺口。

修复方向：让时间轴转折、项身份/版本、合并规则一致；不可只在中间态加标记。至少验证最终 open 留存、歧义留存、无自指 supersedes、下游动作版本可区分；不要仅把 `setdefault` 换成最后覆盖就宣称链路完整。

### PV9 [P1] 任意任务费用核销全部模型费用，工具费也能把完整成本洗成 known

定位：05 `intelligence/services/product_value/summarize.py:152-159`、`710-716`、`739-747`。

`_assisted_task_has_cost_facts` 只要看到 `selected + task_id 匹配` 就返回 True，完全不检查费用类别。后面 observed_components 又按整份试点而非具体任务汇总。

复现沿用 PV8 真实入口生成收据：

1. 配对一 writer/review 费用完整，CNY 0.46。
2. 配对二辅助任务只有 20 分钟计时，`attempts=[]`，无模型账。
3. 冻结协议要求 writer_model / review_model / tool，其余类别事前声明不适用。
4. 给配对二只补一笔 task-scope `tool=CNY 0.01`，不补 writer/review。

结果：

| 输入 | 完整成本 | 已知 CNY | unknown |
|---|---|---:|---|
| 未补费 | unknown | 0.46 | 辅助任务费用缺口 + tool 类别缺口 |
| 仅 tool 0.01 | **known（错误）** | 0.47 | [] |
| tool + writer 0.36，仍缺 review | **known（错误）** | 0.83 | [] |
| tool + writer + review 0.10 | known（合法对照） | 0.93 | [] |

所有输入经 `measure_pair → summarize`，费用事件 `rejected=[]`、`invalid_reasons=[]`；没有手改收据。辅助任务 attempts 始终空，已选账单确实直接挂该任务，不是输入造错。

影响：只给任务挂一笔无关费用，就从完整成本和毛利的未知缺口中消失。不能只把 helper 改成“任意 model 费用”：writer-only 对照还缺 review。应按任务与应覆盖费用类别/明确覆盖证明对账，保留合法不适用与真正补齐账单的通路。

## 汇报证据问题 [P2]

05 `docs/superpowers/plans/2026-09-13-research-evolution/05/PROGRESS.md:142` 与 inflight 写“首跑失败为 test_pipeline_p0，单跑与重跑均过”。机器收据不支持这个失败定位：

- `20260913T125455Z-197133f2.json`：9652 passed / **1 failed** / 77 skipped，failed_ids 唯一值是 `intelligence/tests/test_workbench_conversation_integration.py::test_real_conversation_round_trip_persists_skills_sse_and_three_turns`。
- `20260913T130359Z-197133f2.json`：9653 passed / 0 failed / 77 skipped，exit 0，干净树，确实为全量通过。
- `20260913T130418Z-197133f2.json`：单跑的是 `tests/test_pipeline_p0.py::test_mainline_empty_theme_list_is_failed_without_writing`，1 passed，**不是前面失败项**。

结论只收窄到：全量重跑通过是真；首跑失败名称、已对原失败项做单跑、以及“已知负载抖动”归因未被这组证据证明。须更正 PROGRESS/inflight，若另有原始日志，应附对应收据解释冲突，不凭后一次绿灯倒推根因。

## 已复验矩阵

| 层级 | 独立结果 |
|---|---|
| 本轮原 QC 四项 | 原脚本原断言：旧树 **4 failed**，本轮固定树 **4 passed** |
| 第三轮原五项 | 原脚本原断言 **5 passed**，J4/J5/D5/PV6/PV7 保持 |
| 第一/二轮归档 | spec 01/02/04、05 extra、02 timezone、04 boundary 共六组命令 exit 0；删 root/sha/生成时刻等身份字段后，与第四轮归档结果一致（原八例保持） |
| 合法负控 | J7 双向时区补齐、PV8 人工计时、D5 双向补齐保持；D5 新测试挂修前 rules 是 **1失败1通过**，与 QC 原收据一致 |
| 四轨模块 | 01=104、02=65、04=74、05=113，共 **356 passed** |
| Ruff | 四个固定 SHA 全仓 `ruff check .` 均通过 |
| 本轮新增边界 | **4 failed / 1 passed**；合法费用补齐独立通过 |
| 全量 pytest | **只审原收据，未自行重跑**：01 `20260913T124132Z-cfd88c04.json`=9644/0/77；05 通过收据见上。均 dirty=false，revision/tree/解释器对应 |

归档复跑没有使用开发者 `/tmp/rerun_r3_probes.py`：独立读取 QC 归档脚本，只改树路径和固定 revision 断言，输出原脚本 SHA256。04 未知枚举的预期异常被明确捕获、未吞其他异常。

## 决策与被否方案

| 选择 | 被否方案 | 理由 |
|---|---|---|
| 原反例修复认可、新边界独立阻签 | 用新红灯否认旧绿灯，或用旧绿灯宣布缺陷族关闭 | 分开历史修复事实与当前验收资格 |
| 合成输入走 `assess` / `measure_pair → summarize` | 手改收据伪造缺口 | 先确认输入被接受、合法对照成立 |
| 原始机器收据优先 | 相信“已知抖动”口头归因 | 一条全量绿不能替另一条红灯解释根因 |
| 四轨单独审查 | 临时拼分支冒充 06 验收 | 组合合同、前端和真实接线不在本轮范围 |

## 交回开发者与边界

1. 01 修 J8/J9，扫完同模块所有“时间戳→市场日”位置；修 J10 时连项身份、去重、supersedes 链和动作版本一起验。
2. 05 修 PV9，不能只过滤成任意 model 类别；分别测 tool-only、writer-only 缺 review、完整任务费用与合法原流程。
3. 更正失败收据归因。新增回归再跑本报告四层矩阵；每层给固定 SHA 与干净树证据。
4. 02/04 本轮无新增实现发现，保持候选；04 推远程评审仍另等用户授权。
5. 06 必须用后续修复后的最终四轨组合重新验收；本报告没有授予合并/部署权限，未运行组合全仓/前端/端到端/注册表门禁，也没验真人试点。

可复跑的新探针在 `docs/verification/research-evolution-round5/`：设置 `RESEARCH_EVOLUTION_QC_ROOT` 指向含 01/02/04/05 子树的根，再用主树 `.venv-workbench/bin/python -m pytest -q <本报告树>/docs/verification/research-evolution-round5/test_round5.py`。当前应为 4 failed / 1 passed，而不是期待绿色。
