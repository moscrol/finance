# vidio → finance：交付树质检与公开迁移

## 结论与适用范围

代码迁入独立候选分支，已修本轮可复现的边界问题。**尚非全仓验收、生产部署或日常 agent 能力验收**。
源包不是 finance main 的一部分；审交付必须检出补丁树，干净 main 只作回归对照。

- 来源：vidio `arena/0ee406fa-vidio@7d47cc7`，`archive/finance-transfer/ALL-TWENTY-merged.patch`（20 连）；另有同目录导出与诊断脚本。
- finance 基线：`82de3fb730a4175170b4e6ba472e130e5ef87ab7`。原作者使用的 `148a09ec` 与本次基线不同。
- 原样导入：本地 `feat/vidio-finance-transfer-qc@0889c8c9f`，20 个提交无冲突应用；本轮在其上留存反例与修复。
- 公开候选：`feat/vidio-finance-transfer-public`，直接基于上述 main，迁入源代码净差异与 QC 修复，**不继承原补丁提交历史**。
- 两份私人画像候选不进入公开分支：`perspective-boundary/2026-10-07-strategy-scope-candidate.json`、`perspective-split/2026-10-07-sptfei-lens-split-candidate.json`。完整导入仍在本地，未改生产画像。
- `kol_fengyuan` 映射对应 main 已有内置视角，保留；脚本示例的真实用户标识已替换。画像边界与拆分测试改用合成数据，新增源码/测试注释中的私人原话已改为工程契约描述。

## 交付的业务增量

1. 切片表达与情景树编译：把已经注册的标签接到读数路径；布尔连续段拒绝分类值，文本谓词检查归一形式/合法值。
2. 教学桥：把市场周期、板块角色和结构事件带到判定路径。教学 `tf.*` 与供应商标签命名空间分离，不并库。
3. PIT（时点可知性）：`first_known_at` 与重算时间分开，标签组合对象取成分的最晚可知时间；旧旁路库缺列给出重建提示，`reset-teaching` 只重建教学表。
4. 多维镜头：展示逐维均值/趋势差、相关组和候选距离分布；环境剧本纯函数完成训练簇、留出诊断、历史后续事实和匹配。
5. 离线工具：视角映射/拆分/字段投影、教学数据包导出/还原及只读诊断。

这些是可调用积木，不等于金融问答已自动消费新镜头与环境剧本。

## 本轮反例 → 修复

| 位置 | 原行为 | 修复与证人 |
|---|---|---|
| `regime_script.evaluate_gate` | NaN/±Inf 可过闸；39/1 分组满足总数门；有限大数溢出 | 非有限数拒绝、每簇门、同尺度归一避免平方溢出；`test_river_transfer_qc.py` |
| `mint_scripts/build_scripts` | 训练与留出同 ID、未知训练簇、重复 order 被接受；未获留出支持的训练簇仍可命名 | 分区/ID 验证；每个铸造簇须有足够留出实例；训练后续事实也拒 NaN |
| `match_script` | 只有一个候选或全体都远时，仍可宣称归属明确 | 单候选不确认；相对领先还须在训练成员距离范围内。经验匹配不称概率置信度 |
| `river_lens` | 均值相同、趋势相反仍称对齐；10 个零距候选称无候选；相对排名冒充绝对相似 | 判读复用原距离的均值+趋势贡献；零分母明确不可区分；相关组数不称独立证据 |
| `lens_from_db` | as_of 早于 cutoff 时，候选与标准化仍混入目标窗之后行情 | 全部输入截到 as_of；拒绝非正窗口及晚于 cutoff 的目标日 |
| `pit_identity` | 带时区的构建时间直接去 tzinfo，真实时刻偏移 | 先转 UTC 再存无时区 TIMESTAMP |
| 教学导出 | market 范围仍整表带出个股；cutoff 没约束事件日期且其他表未过滤 | 默认只导市场标签；有 cutoff 时同时约束日期/可知时刻，无证据表省略 |
| 教学还原 | 先删已有目标；不验清单；路径单引号破 SQL；旧包可混入新包 | 全新输出；校验 SHA256/列/行数；按 DDL 临时建库，原子且不覆盖发布 |
| 教学诊断 | 查 legacy `history_build_meta` 推断教学未构建，或无条件称空表被删 | 查 `history_teaching_receipts`、列集合、实际行数及 first_known_at；未知历史保持未知 |
| 画像字段投影 | 顶层白名单内的嵌套 raw/excerpt 可泄露；忽略外置 userspace | 子字段白名单并报告丢弃项；走 `userspace/profile_path`；仍需人工审阅正文 |
| 映射审计 | 来源缺失/空画像可隐藏覆盖差；临时库不清理 | 来源缺失中止、空源列出过期映射；临时目录自动清理 |

源作者已修的缺列读守卫、`max(first_known_at)` 消费约束、手写 fixture 更新不是本轮新发现。

## 验证收据

解释器：锁定 Python 3.12.13 workbench 环境，未用 `FWP_ALLOW_ANY_PYTHON`。
本地原始日志目录：`~/.finance-runtime/reviews/vidio-transfer-20261008/`。

| 检查 | 结果 | 日志 |
|---|---|---|
| 原始交付定向回归（两个 tests 根） | 812 passed / 61 skipped | `candidate-initial.log/xml` |
| 同范围干净 main | 676 passed / 44 skipped | `baseline.log/xml` |
| 第一批独立边界反例 | 修前 14 failed | `qc-before.log/xml` |
| 扩展边界反例 | 原 14 通过、新 5 failed | `qc-extra-before.log/xml` |
| 两个伴随工具 | 修前 7 failed；修后 7 passed | `tools-before.*` / `tools-after.*` |
| 画像嵌套字段/外置根反例 | 修前 2 failed（原 7 通过） | `profile-before.*` |
| 原模型/镜头测试 + QC/工具测试 | 49 passed | `qc-final.*` |
| 公开候选扩大回归 | 1089 passed / 48 skipped / 19888 deselected | `public-final.*` |
| 同范围干净 main | 912 passed / 44 skipped | `baseline-final.*` |
| 全仓 Ruff | exit 0 | `public-ruff-final.log` |
| CLI 冒烟 | lens/export/diagnose `--help`，映射审计 `--all --json` exit 0 | `*-cli-help.txt`、`public-perspective-audit.json` |

扩大回归（定向，非全仓）：

```bash
.venv-workbench/bin/python -m pytest -q intelligence/tests/ tests/ \
  -k 'river or teaching or lens or analog or regime or perspective_river or perspective_export or split_monolithic or profile_boundary or verify_briefing_consumption or label_binding or scenario_tree or methodology or judgment_maintenance or research_evolution'
.venv-workbench/bin/python -m ruff check .
```

以上实现期候选日志来自未提交的独占树，且早于最后一次公开内容复查，不能用日志文件名中的基线 SHA 冒充最终版本。固定提交后的复验另记于分支交接；拆分测试不再依赖私人快照，因此最终通过/跳过数量会变化。

## 未验证 / 不成立的结论

- 未跑完整 pytest、前端、E2E、注册表集成门；不能称四叶验收齐绿或可合并。
- 未连生产库做教学 build/reset/export，未发布任何数据包，未重启服务、切换部署或运行真实模型问题。
- `regime_script` 是探索性函数：检查同 ID 隔离不等于日期区间/后续事实区间无重叠；标准化拟合范围、时间顺序、PIT、序列自相关仍要调用方提供证据。逐窗口置换不是时序预测有效性证明，不能把过闸写成“已找到行情规律”。
- 镜头已有独立 CLI，现有问答仍调用 `regime_block_for_llm`。新环境剧本尚无日常问答消费链；不自动改变产品入口。
- `guided_reading.py`/CLI 的观察剧本入口原本存在，缺的是每日产物接线，不再报成“观察剧本未落地”。
- `KNOWABLE_AT_CLOSE` 与 `SLICE_EVALUABLE_LABELS` 含义不同，本次保留两套集合；标签数不是质量指标。
- `first_known_at` 保留依赖旧值/文本相同，不构成多版本历史库，也不证明供应商后续修订在历史当日已经可知。
- 画像字段投影不能证明正文无隐私/原文；结构化 `output_policy` 也不是身份授权实现。拆分 ID 只保证同输入稳定，插入条目后序号会变；还原校验忽略空白，对英文/连续/末尾分号目前会拒绝而不是默默丢字。

## 后续

1. 固定候选提交后复跑并回读收据，再走草稿 PR；合并须用户确认及完整工程验收。
2. 另做只读真库研究与用户题对照，验证 agent 是否真正利用时间演变、多维分歧与后续事实。
3. 环境剧本接线前补日期区间、标准化/结果可知性的输入合同及时间相关零假设；保留“不命名”的合法空结果。
