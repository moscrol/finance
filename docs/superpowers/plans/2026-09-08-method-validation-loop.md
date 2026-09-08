# 第一条方法验证闭环 Implementation Plan

> **For agentic workers:** Use subagent-driven-development to implement this plan task-by-task. Steps use checkbox syntax for tracking. 用户已授权本会话实施，计划后直接执行。

**Goal:** 让现有连续三日严格双红规则可以登记、做三组历史对照、冻结当日前瞻样本、到期回检和反查失败。

**Architecture:** 新增独立的研究应用 `method_validation`，只读现有 methodology_backtest 旁路标签与结果，不改其规则编译、统计四态、生命周期，也不写市场主库。协议和每次收据不可覆盖，数值结果保留到板块日；CLI 是分析师入口，不注册到只读 Agent 工具，不动 runtime。

**Tech Stack:** Python 标准库、现有 DuckDB 只读连接、JSON 机器原件及 Markdown 报告；用户态沿用 userspace 路径解析。

---

## 与另一任务的边界

基础补强 spec 位于 `docs/research-foundation-optimization` 分支，由其他 Agent 实施。本任务复用现有标签口径，并为未来接严格时间点数据门留完整协议/输入证据；当前所有结果明确 `research_only`、`decision_eligible=false`、`promotion_eligible=false`。不把描述性均值写成通过统计验证，也不接旧 lifecycle 推广通道。L2、晚间卖方、晨汇只记录 `pending_sync` 占位，均非本规则输入。

历史三组：同日同市场阶段板块总体、当日严格双红、连续 ≥3 日严格双红。沿用现有 rule JSON 的主升/反弹条件与标签定义。三组是嵌套集合；连续第四、第五日仍命中。五日收益由现有 outcomes 提供，单位百分数，D+1…D+5，不含 D0。基准是同期板块等权的研究读数，不是可交易组合，也不表示净收益。

主要对照：每个 D0 先算各组均值；三组均有成员且整个基准成员结果完整时，才进入共同日期集合。日期间等权，报告 `streak3 - dual_red` 和 `streak3 - universe`（百分点）。保留所有未到期、缺数据、非适用阶段、无命中日期及原因。任何 missing/invalid 成员使该日主对照不可评估，不按幸存样本偷偷改变基准。副指标保留现成 `drawdown_after_peak` 的准确名称“峰值至第五日回撤”，不叫最大回撤。

## 文件边界与合同

| 文件 | 责任 |
|---|---|
| `intelligence/services/method_validation/__init__.py` | 包说明 |
| `intelligence/services/method_validation/protocol.py` | 读 seed，构造并校验固定三组协议/方法卡与内容哈希 |
| `intelligence/services/method_validation/study.py` | 只读旁路取数、固定成员选择、同日对照、前向登记时序门 |
| `intelligence/services/method_validation/store.py` | 不可覆盖的协议/观察/结果收据、完整性校验、目录路径 |
| `scripts/method_validation.py` | register/history/capture/recheck/report 五个命令与中文报告 |
| `intelligence/tests/test_method_validation.py` | 真实小 DuckDB 的数值、时序、成员冻结与坏数据测试 |
| `intelligence/tests/test_method_validation_cli.py` | CLI 完整闭环与退出码 |
| `docs/workflows/method-validation-loop.md` | 方法卡、入口、数据边界、下一轮修订方式 |
| `docs/learning/ledger-map.md` | 登记新研究台账唯一写入者 |

公共函数使用 JSON 可序列化 dict，禁止隐藏连接或全局可变状态：

```python
def build_protocol(rule_path, *, history_start, history_end, forward_start, now=None): ...
def protocol_id_for(rule_path, *, history_start, history_end, forward_start): ...
def validate_protocol(protocol, *, require_current=True): ...
def read_features(labels_db, protocol, *, start, end): ...
def read_outcomes(labels_db, protocol, features, *, now=None): ...
def compare(protocol, features, outcomes): ...
def validate_capture(protocol, features, *, now=None): ...
def register(root, protocol): ...
def load_protocol(study_dir): ...
def write_record(study_dir, kind, payload): ...
def read_record(path): ...
```

`features` 包含 `calendar`（截止 end 的日历前缀）、`rows`（trade_date/entity_id/stage/dual_red_strict/dual_red_streak）、`metadata`（标签版本、源路径、水位、构建时间）、`start/end`。不能读取未来标签参与选样。`outcomes` 包含这些固定键对应的 `status/fwd_return/drawdown_after_peak`，以及独立取数元数据和日历。回检不调用 `read_features`。读取行必须稳定排序，禁 NaN/Infinity 进入 JSON。

协议除 seed 规则全文/hash 外，冻结 label_version、label_spec、三组定义、五日口径、日等权方式、历史窗口、未来开始日、研究用途和 evaluator version。协议 id 来自内容 SHA-256，创建时间另存；输入或口径变动必须形成新协议。历史数据已经看过，不能改称留出测试集。

持久化约定：`userspace.user_space(user).root / method_validation / <protocol_id> / protocol.json`，记录分区 `<kind>/<local-date>/<content-id>.json`。`write_record` 用同目录临时文件完整写入、fsync、硬链接原子创建；相同内容幂等，已有文件内容不符报错；读时重算摘要。记录含 schema/kind/payload/content_sha256，观察中包含全部成员及排除原因，结果反链观察 hash；不写画像/经验/参数。CLI `--root` 仅供明确的离线实验/验收目录。

## Task 1：协议、数据读数与不可变存储

- [x] 在新包和 `test_method_validation.py` 先写有手算答案的小库测试：三板块 A/B/C，D0 双红分别 1/1/0、连续天数3/1/0，五日收益6/2/-2。预期总体2、双红4、连续6、增量2百分点；增加同日板块数不能增加日期数。

```python
assert result["daily"][0]["means"]["universe"] == 2.0
assert result["daily"][0]["means"]["dual_red"] == 4.0
assert result["summary"]["streak3_minus_dual_red_pp"] == 2.0
assert result["summary"]["paired_dates"] == 1
assert result["promotion_eligible"] is False
```

- [x] 运行本文件测试确认新增入口尚不存在；实现上表四个包文件。使用 `open_labels_db(..., read_only=True)`；每次读取在单个连接内取得元数据与行，校验双方 label_version、源路径、水位等；不声称这些等同严格 PIT 认证。所有 SQL 固定模板与参数绑定。

同日公式：

```python
from statistics import mean

means = {arm: mean(returns[e] for e in members) for arm, members in arms.items()}
increment = means["streak3"] - means["dual_red"]
relative = means["streak3"] - means["universe"]
```

- [x] 冻结方法卡：假设、适用环境、观察顺序、预期五日相对表现、弃用条件；正反例来自测试/未来观测并标来源，不冒充用户已经认可的实证经验。原 seed 的“绝对上涨成功”不被改写。
- [x] 前向门：未来开始日严格晚于协议登记本地日期；capture 的 D0 必须等于机器当前 Asia/Shanghai 日期、已过15:00、位于协议前向区间、等于源库水位和日历末日、有当天特征。构建时间不晚于当前时间，且为 D0 收盘后；生产 CLI 不暴露改时钟参数。历史只能 history，拒绝补登记。任何结果数据进入 capture 载荷都应被测试发现。
- [x] 覆盖坏数据/时序：pending、missing、NULL标签、不适用阶段、无命中、缺日历、标签版本不匹配、源路径不匹配、结果<=-100%、无穷数、伪造已到期但日历不足、登记后改标签不改变回检成员、协议篡改、同一内容重跑、写失败无半文件。
- [x] 运行 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q intelligence/tests/test_method_validation.py`；独立规格审查通过后再做质量审查，修完发现项。

## Task 2：CLI、台账与第一轮真实运行

- [x] 在台账地图登记 canonical 路径与唯一写入者，然后实现五个命令。`register` 读内置 seed/历史起止/forward-start；`history` 冻结特征+结果+比较收据；`capture` 只读特征并保存成员；`recheck --observation` 验 hash 后只读结果、保存新版本回检；`report` 从完整收据重新渲染，不重新选样。失败返回2；锁占用返回3，不吞错误。

```sh
python scripts/method_validation.py register --history-start 2025-01-01 --history-end 2026-09-07 --forward-start 2026-09-10
python scripts/method_validation.py history --study-dir "$STUDY_DIR" --labels-db "$LABELS_DB"
python scripts/method_validation.py capture --study-dir "$STUDY_DIR" --labels-db "$LABELS_DB"
python scripts/method_validation.py recheck --study-dir "$STUDY_DIR" --observation "$OBSERVATION" --labels-db "$LABELS_DB"
python scripts/method_validation.py report --record "$RECORD"
```

- [x] CLI 测试做 register→history→report，以及时钟注入测试内的 capture→先pending→后成熟recheck；进程公共入口不得允许 `--now`。为协议/收据篡改、跨实验观察、输出路径及用户隔离建立失败断言。
- [x] 用真实只读旁路库运行 history，先检查水位和 label_version；若需重建，用现有 build-labels/outcomes 写本实验临时旁路，不动共享旁路。主库锁占用时使用已有旁路历史并明示截止日。记录实际三组样本/日期、缺口和描述性差值，不能据此认定有效。
- [x] 文档给出实际产物位置和下一次 capture/recheck 的可执行命令；明确程序完成和市场样本尚待发生是两种状态。不安装计划任务，不自动交易，不修改基础 spec。
- [x] 跑新测试、既有 methodology/observation/checkpoint 相关回归、ruff与layer_audit；只在要合 main 前才扩大为等价全仓CI。独立规格、质量审查通过后 pathspec 提交。
- [x] 用 handoff 技能回写自己的分支交接与项目记忆索引。未授权合 main，不切运行时。

## 执行收据

代码 `e41ef60b`；干净代码树上240项相关测试通过，独立规格/质量审查通过。真实历史416日仅2个共同完整日期，不判方法有效或无效；前向起点2026-09-10，真实观察未发生。完整验证、原件位置与成立边界见 [交付说明](../../verification/2026-09-08-method-validation-loop.md)。
