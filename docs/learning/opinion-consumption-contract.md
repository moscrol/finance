# 卖方观点消费合同

状态：分支实现，未部署。核心读层 `intelligence/services/opinion_events.py::load_events`；唯一更正写入者 `scripts/review_opinion_events.py::publish`，台账位置已登记 `ledger-map.md`。本合同不改变长河研报目录。

## 三个时间

- `report_date`：材料标注的报告日期，不等同公开时间；推断日期标 `inferred_unconfirmed`，默认排除。
- `ingested_at`：原记录首次入库时间，缺失/非法不回退报告日。
- `recorded_at`：当前内容版本系统可得时刻；原版取入库时刻，更正版取写入者盖的带时区时间戳。

`as_of` 限制报告日期，`knowledge_cutoff` 限制系统知识；均为 Asia/Shanghai 日终。未来知识截止须显式 `allow_hindsight=True`。日期精度不能证明开盘或日内可得。只通过时间过滤不代表所有旧记录均已语义审核。

## 追加更正

`corrections/<batch_id>.json`，schema `opinion-corrections/v1`。每条绑定 `event_id`、原记录 canonical JSON 的 `base_sha256`、`supersedes` 和 `raw_ref`（原件路径/SHA-256/Python字符区间）。不是 UTF-8 字节偏移。

- `replace`：提供完整语义白名单；摘要、主张须为锚点内逐字摘录，只允许未核验 L3/L4、软推演及空硬证据。旧主营、共振等派生标签移除。
- `quarantine`：待逐条复核，不是断言内容为假。后续新批次可以显式接续释放。
- `retract`：撤回明确错误的抽取，不删除旧事件或原文。

发布整批校验、文件锁、临时文件 fsync + 不覆盖硬链接发布；同内容同批号重试无副作用，变更须新批号。修订时间必须递增且不早于原入库。完整链包括未来修订都要可验证；损坏链、原件或哈希不可读时，消费者显式缺口，不回退旧事件。原始缺失、非法、重复ID不进入聚合。

## 已接入的入口

| 入口 | 截止与订正 | 仍不证明什么 |
| --- | --- | --- |
| 催化归因 / 新鲜度 | 卖方使用市场日截止；隔离/时间缺口不被晨汇存在掩盖 | 晨汇完整PIT、文本命中即因果 |
| Workbench overview | 使用市场库最新交易日；无市场日不展示无截止卖方数据；警告走既有 data_status | 日内可得性、收益统计是严格历史回测 |
| 授课叙事 loader / 构建脚本 | 构建日终读取更正投影；过滤/损坏时聚合写缺口而非零；版本时间随订正 | 每个历史开盘的信息集、晨汇投影PIT |
| 事件定价日历 | `now` 的北京时间日终读取投影；缺口保留；订正版身份进入事件引用 | 报告日锚点在反应日已被系统知道；产物为事后研究 |

Workbench 的硬证据优先还要求非空证据、L1/L2、verified 三者同时成立。收益行须事件ID和revision_id吻合，且computed_at不晚于截止；未带新revision的旧收益不能验证订正版。收益写入器尚未迁移，所以这不是端到端回测验收。

## 未接入与禁区

- `river._opinion_track` 仍读 `fact_research_report_catalog`；不把本 JSONL 的分支投影称线上长河已接通。
- `skills/opinion-cross/scripts/consensus_staging.py`、`consensus_bridge.py`、`build_outcomes.py` 及榜单脚本仍用旧数据路径。不得用它们为本批订正签验收；未修改或运行这些写入任务。
- 471 条隔离须逐条重审。09-11 日期仍待用户确认，不能通过改为 confirmed 提前释放。
- 合并、部署、旁路库重建、生产库写入均另需授权；质量/体积基线不得抬高放绿。

## 复核入口

`prepare_miracle_review.py --wiki <wiki> --manifest <manifest>` 默认只生成动作摘要，`--apply` 才发布。

`audit_opinion_projection.py --wiki <wiki> --batch-id <batch> --as-of YYYY-MM-DD --out <新收据.json>` 只读探针，支持重复传 `--as-of`；收据不可覆盖。exit 0 只表示执行成功，verdict 不会给 READY。测试见 `intelligence/tests/test_opinion_events.py` 及各消费者测试。
