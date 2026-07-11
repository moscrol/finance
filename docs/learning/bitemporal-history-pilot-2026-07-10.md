# 双时态历史评测：10 日 Pilot

## 目标

同一日期生成两套物理隔离的档案：

- `final_history`：采用当前最佳事实回答“实际发生了什么”；截止后获知的行标记为 `ex-post`。
- `as_known_at`：只保留 `updated_at < D0+1日 00:00 Asia/Shanghai` 的行，以及截止前 Git commit 中已经存在的资料。

本轮只评估历史忠实度与 PIT 截止纪律，所有产物保持
`decision_eligible=false`，不证明预测有效。

## 执行口径

- 日期：`2026-03-06、04-23、06-02、06-11、06-22、06-23、06-24、07-01、07-02、07-03`
- 主库：a77 `/Users/a77/finance-workspace-private/db/market_feature_store.duckdb`
- 资料：finance 与 knowledge-base 两仓的截止前 Git 历史
- 输出：a77 `/Users/a77/fidelity-replay/bitemporal-history-v1/`
- 源库签名：device `16777231`，inode `10239282`，size `3208654848`，mtime_ns `1783682464761887419`
- `pilot.report.json` SHA-256：`3744edb2687af6ff68aeb2d584cea836489828d04b5ffa822fdc48be072036fb`
- `pilot.report.md` SHA-256：`18eeaddc0dadad942f0cf96e53c63d2b4c9b849705d90aa5368fead7f82889a2`

每个日期的 final/PIT 档案都从同一批已读取行派生，并绑定相同
`source_snapshot_sha256`。生成器同时拒绝运行期间发生文件签名变化的主库，
避免活库更新让两套视图读取到不同版本。

## 结果

| 日期 | final | final 行 | ex-post | PIT | PIT 行 | 字段覆盖 | 截止前资料 | 20 日成交额契约 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-03-06 | ready | 34,527 | 34,527 | pending | 0 | 0.00% | 0 | ineligible |
| 2026-04-23 | ready | 34,599 | 34,599 | pending | 0 | 0.00% | 0 | ineligible |
| 2026-06-02 | ready | 34,246 | 30,234 | partial | 4,012 | 4.97% | 5 | ineligible |
| 2026-06-11 | ready | 34,231 | 1,432 | partial | 32,799 | 98.20% | 6 | ineligible |
| 2026-06-22 | ready | 35,347 | 35,347 | partial | 0 | 0.00% | 24 | ineligible |
| 2026-06-23 | ready | 35,374 | 35,368 | partial | 6 | 0.01% | 3 | ineligible |
| 2026-06-24 | ready | 4,618 | 3,177 | partial | 1,441 | 39.57% | 1 | ineligible |
| 2026-07-01 | ready | 35,838 | 229 | partial | 35,609 | 99.73% | 8 | ineligible |
| 2026-07-02 | ready | 35,365 | 229 | partial | 35,136 | 99.72% | 3 | ineligible |
| 2026-07-03 | ready | 35,379 | 229 | partial | 35,150 | 99.72% | 10 | ineligible |

汇总：

- final：`10/10 ready`
- PIT：`8 partial`、`2 pending`
- 截止违规：`0`
- final/PIT 行分区错误：`0`
- 配对快照哈希一致：`10/10`
- 重大字段冲突：`0`
- 20 日 `fact_market_daily.total_amount` 连续窗口：`0/10 eligible`

## 关键发现

### 1. “最终事实完整”不等于“当时可重放”

10 日最终历史都有数据，但 03-06、04-23 的全部行都是事后获知；06-22
虽然有 24 份截止前资料，DuckDB 行仍全部属于 ex-post。资料存在只能证明
当时有部分材料，不能自动证明完整市场状态可重放。

### 2. 计划中的无资料对照已发生变化

原计划把 07-02、07-03 作为无资料对照；实际截止前 Git 历史分别找到
3、10 份资料，DuckDB 字段覆盖也达到约 99.72%。本轮没有为了符合预期而
强行标记 pending，仍按实际证据记为 partial。真正 pending 的日期变成
03-06、04-23。扩展样本前应重新选择两天无证据对照。

### 3. 连续窗口仍未达到规则计算资格

所有日期的 20 日成交额契约都不合格。07-01 缺 06-03、06-18；
07-02 与 07-03 均缺 06-18。即使单日 PIT 覆盖接近 100%，也不能据此
宣称 MA20 或 20 日放量规律当时可计算。

### 4. “冲突为 0”不是“没有发生过修订”

当前主库只保存最新行，没有完整旧版本值。系统可以可靠识别“整行在
cutoff 后才可见”，但无法比较同一行在 cutoff 前后的字段旧值与新值。
因此 `conflict_field_count=0` 只表示现有证据中没有可比较的版本冲突，
不代表历史上没有修订。若要识别字段级修订，下一阶段需要 append-only
revision log 或每日 PIT 快照序列。

## 产物

```text
/Users/a77/fidelity-replay/bitemporal-history-v1/
├── final_history/  # 10 个 *.final.json，约 322 MB
├── as_known_at/    # 10 个 *.known.json，约 145 MB
├── gold/           # 10 个人工金标准模板
├── pilot.report.json
└── pilot.report.md
```

代码入口：

```bash
python3 scripts/bitemporal_history_eval.py pilot \
  --db /path/to/market_feature_store.duckdb \
  --kb-root /path/to/knowledge-base-private \
  --finance-root /path/to/finance-workspace-private \
  --dates 2026-03-06,2026-04-23,2026-06-02,2026-06-11,2026-06-22,2026-06-23,2026-06-24,2026-07-01,2026-07-02,2026-07-03 \
  --out-dir /path/to/bitemporal-history-v1
```

## 下一闸门

不扩到 80 日、不恢复预测优化。先人工复核 10 份金标准模板，并决定：

1. 是否更换已失效的 07-02、07-03 无资料对照；
2. 是否把字段级 revision log 作为扩量前置条件；
3. 是否补齐 06-03、06-18 等连续窗口缺口后再评估 MA20 类规则。
