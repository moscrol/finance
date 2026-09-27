# 风远原料恢复与画像现状复核（不写画像）

旧 [09-16去重对账](fengyuan94-corpus-dedup-2026-09-16.md) 引用的
`/tmp/fengyuan94-new-cards-2026-09-16.md` 已丢失。本轮恢复**它依赖的原料与定位索引**，
不声称逐字找回当时临时筛选稿，也不重复灌入已经更新过的画像。

## 恢复收据

| 原件 | SHA-256 | 本轮产物 |
|---|---|---|
| `~/Downloads/fengyuan_knevo_archive_2026-07-12.zip` | `018798fb3482f1b97661d9cefb60c7ee90f26cc583494fdbcfb55d98ee07cc16` | 原ZIP未改 |
| ZIP成员 `fengyuan_knevo_archive/fengyuan_66_industry_rule_cards.txt` | `e5f6ec0ddf83f81f0e5492864ff6b79d48a9313fbd3b01a4ccf8fdfcf705c90c` | 原文94,679字节，按R01–R66标题分出66段位置/哈希 |
| 08-08的44轮原文，第40–44轮 | 源文件及切片位置在下述manifest | B侧原文恢复，未重新把119条全量做成熟度终审 |

产物位于 `~/.finance-runtime/knevo-absorption-20260923/source-recovery/`：
`manifest.json`、`fengyuan_66_industry_rule_cards.txt`、`rounds40-44.txt`、`profile-audit.json`。
原文/长摘留本机，不入Git；仓内只保留索引和短摘。旧“18已有/25部分/22新增/1不吸收”
是**当时画像**的分母，不可以照抄成今日待灌清单。

## 当前画像：内容核对，不按R编号猜

只读定位：`~/.local/share/finance-workbench/users/linxiaoqi5111/perspectives/profiles/fengyuan.json`。
读取SHA-256 `9600cc38038ec64aef8ccb975f51668c90c6f293ef582d2e15a12853fc21eba9`；
`confidence.article_count=24`、`patch_history`105项。这个路径是本轮读到的原件，
**不是对当前UI用户/生产挂载的确认**；以后写入必须重新通过userspace/launcher确认身份。

以下是按规则内容人工抽核后的JSON Pointer（零基索引），不是规则ID命中即算吸收：

| 原卡 | 当前字段位置 | 内容交集（短摘/概括） | 边界 |
|---|---|---|---|
| R61 | `/anti_patterns/26` | 不用同比增速定性财报超预期 | 一致预期存在与可比性仍须运行时取证 |
| R12 | `/anti_patterns/27` | 设备、调试、良率共同决定供给 | 内容已在，不能重复提patch |
| R65 | `/anti_patterns/28` | 比率先定口径 | 是研究纪律，不保证每次模型遵从 |
| R28 | `/anti_patterns/29` | 数字回财报原件复核 | 已抽成通用句，不搬单次事实 |
| R27 | `/opportunity_preferences/26` | 合同负债与毛利率联看 | 仍有强因果/布局措辞，存在不等于安全或效果全验 |
| R30 | `/risk_triggers/35` | 现金流与利润比率检验 | 阈值留Q-002，不能反向判财务造假 |
| R35 | `/risk_triggers/36` | 龙头与二线背离 | 定性已在，领先时长未标定 |
| R02 | `/market_lenses/0/description` | 扩产周期判别持久性 | 三档月数未采硬门 |

`known_gaps`还记录了09-16后续批次、手编镜头和终审自述；这些记录解释了为什么旧表失效，
但**不是本轮重做全部105项审查的证据**。未改画像、未更新article_count、未改approved状态。

## 本轮决定

- 原料恢复及“旧待办已被后续写入替代”的抽核完成，不再因临时稿丢失重灌66卡。
- 其余卡保留旧对账与当前字段供后续内容级复核；成熟度必须检查跨语境复现、生成力与独占性，
  模板里的适用/不适用/失效条件齐全不算效果验证。
- 事实/事件不进入认知画像；机构观点本体仍登记不立项，二手转述不升级为公司事实或机构战绩。
- 画像里既有交易措辞/强因果句如需收窄，走独立画像修订与审批；本轮不借编码收尾写生产个人状态。
