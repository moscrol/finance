# vidio → finance：交付树质检与公开迁移

## 结论与适用范围

代码迁入独立候选分支，已修可复现的边界问题；后续接线已验证到 A 首次模型请求及 B 默认/旧合成接口替身。**模型接口收到不等于模型实际利用、金融质量通过或生产已部署**。
源包不是 finance main 的一部分；审交付必须检出补丁树，干净 main 只作回归对照。

迁移代码 `31fc76f957412ee7f53ea709e4cff5eba8b878e2`；消费接线代码 `7389549bcd20ada12f1f78f0ea4a91a178df551e`，均已推草稿 [PR #75](https://github.com/moscrol/finance/pull/75)。公开隔离见[迁移快照](../handoffs/2026-10-08-vidio-finance-transfer-public.md)，接线决策/证据见[消费快照](../handoffs/2026-10-08-river-history-consumption.md)；接手看[本分支在途状态](../handoffs/inflight/feat-vidio-finance-transfer-public.md)。

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

迁移阶段只提供上述积木；`7389549bc` 另将镜头接入下述两条问答路径，环境剧本仍未自动消费。

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
| 实现期公开候选扩大回归 | 1089 passed / 48 skipped / 19888 deselected | `public-final.*` |
| 最终干净代码提交 `31fc76f95` | **1093 passed / 44 skipped / 19888 deselected** | `public-clean.log/xml` |
| 同提交全仓 Ruff / 收据校验 | exit 0 / exit 0（明确为定向） | `public-clean-ruff.log` / `public-clean-receipt-check.log` |
| 同范围干净 main | 912 passed / 44 skipped | `baseline-final.*` |
| 全仓 Ruff | exit 0 | `public-ruff-final.log` |
| CLI 冒烟 | lens/export/diagnose `--help`，映射审计 `--all --json` exit 0 | `*-cli-help.txt`、`public-perspective-audit.json` |

扩大回归（定向，非全仓）：

```bash
.venv-workbench/bin/python -m pytest -q intelligence/tests/ tests/ \
  -k 'river or teaching or lens or analog or regime or perspective_river or perspective_export or split_monolithic or profile_boundary or verify_briefing_consumption or label_binding or scenario_tree or methodology or judgment_maintenance or research_evolution'
.venv-workbench/bin/python -m ruff check .
```

实现期候选日志来自未提交的独占树，且早于最后一次公开内容复查，不能用日志文件名中的基线 SHA 冒充最终版本。最终 `public-clean` 绑定干净 `31fc76f95`：拆分测试的四个私人快照跳过项已由合成样本替代并实际执行，因此较实现期增加 4 passed、减少 4 skipped；不表示已测私人画像。收据为 `~/.finance-runtime/test-receipts/20261007T192253Z-31fc76f9-b43b863edf49.json`，revision、解释器、依赖及基座漂移 0 均核对通过；后续文档提交不自动继承此 revision 身份。

## 日常历史比较接线（`7389549bc`）

`market_history_context.market_history_blocks()` 统一只读库路径、显式站立日和父截止，分别保留旧 D10 后续事实与 river 多维镜头。单块失败局部降级，不泄漏私人路径；镜头缺候选时仍携带来源/PIT（时点可知性）与缺口。两套特征/候选独立，不能按名次嫁接后续收益。

- **A / Episode**：历史自动预取前检查市场能力、材料范围和剩余截止；实际 `ContinuousAgentEpisode.run()` 首次模型调用由离线替身截获，完整镜头、来源、日期、缺维和限制到达。证据账本另验 hash、日期与 E 序号。未跑完整 `TurnOrchestrator.run_turn`。
- **B / ask compose 的 D10 provider**：问句日期在规划/快照读取之前冻结，显式日期优先；保留整块 `data:D10:context` 为 `INFERRED`，不升已核验事实，直接构造 Claim 避免展示清洗抹掉表/列名。
- **默认 grounded 合成**：有来源的短推断摘要解决 D10-only 准入；完整上下文通过 `required_claim_ids` 原子占位，不能被其他长资料挤掉。既有 12K registry 装不下时不发模型请求，走确定性降级；缺项修订共用此规则。未指定必需行的调用保留原预算/排序行为。
- **边界随读数送达**：当前窗、实际标准化拟合范围、上游 PIT 日行标记、来源规则、逐维水平/趋势/贡献、共有维分母、暂停/缺失维均显示。上游 `strict` 相对本次 cutoff，不等于每个历史交易日收盘时已知；拟合含当前窗，不是训练/留出检验。

### 新收据与覆盖范围

解释器仍为本树 `.venv-workbench/bin/python`（锁定 Python 3.12.13）。新原件根 `~/.finance-runtime/reviews/river-consumption-20261008/`，仅本地保存。

| 证据 | 读数 / 支持的断言 |
|---|---|
| 修前 `before-corrected.*` | 6F/3P：预取/缺口/来源/PIT/账本送达断点；夹具初错另留 |
| `delivery-before.*`、`grounded-corrected-before.*` | prepared 之外再复现默认合成准入与拥挤 registry 遗失；夹具错误与产品错误分账 |
| 新消费测试文件 | 33 个参数化实例；A 实际循环首发截获，B 默认/旧合成 × 拥挤/不拥挤接口替身、D10-only、超预算拒发等 |
| 干净 `7389549bc` 的 `fixed-code.log/xml` | **1785 passed / 44 skipped / 19229 deselected**，1 条 TestClient 弃用 warning；不是全仓 pytest |
| `fixed-code-receipt.json` / `fixed-code-receipt-check.log` | revision、解释器、依赖、净树、基座漂移 0 对账；明确保留关键词收窄 |
| `fixed-code-ruff.log` / `code-commit.log` | 全仓 Ruff、实际提交门通过；不是前端/端到端验收 |
| `fixed-code-map-*` | 结构索引 ready，vault unavailable、doors/narrative missing、召回未验 |
| 只读真库探针 | 两块可出数，行情库 mtime/size 未变；详细输出和覆盖审计仅留私有原件，非性能或金融质量实验 |

```bash
FWP_TEST_RECEIPT_PATH=<本轮独占收据路径> \
.venv-workbench/bin/python -m pytest -q intelligence/tests/ tests/ \
  -k 'river or teaching or lens or analog or regime or perspective_river or perspective_export or split_monolithic or profile_boundary or verify_briefing_consumption or label_binding or scenario_tree or methodology or judgment_maintenance or research_evolution or ask_compose or ask_clarify_planner or ask_planner or episode_tools or prefetch or answer_model or ask_claim or registry_truncation or grounded or decision_brief or material_quote_recovery'
.venv-workbench/bin/python -m ruff check .
```

旧 `545fb854b` 的五项 GitHub 检查只覆盖旧接线前版本。05:37 CST 的运行中观察不是终态：后来回读确认 `7389549bc`（run `37689283789`）及 `1a055b87`（run `37691469323`）的全量 Python 都是 **9F/20971P/167S/2X**，九例均为补写测试裸 `object()` 不满足 `AnswerSpec` 合同；两版聚合均未通过。前者 E2E 安装阶段超时、未执行测试，后者 registry/frontend/E2E 成功，分别记账。

### 全量 CI 追补（测试提交 `0154b06d1`）

同一锁定环境：干净基线的补写组 16P，`1a055b87` 为 9F/7P。核定义与真实调用后，只将测试夹具改成合法最小 `AnswerSpec`，不在生产添加吞缺字段的兜底；新增两个真实 registry 补写实例，验证完整镜头/共同限制送达或超预算拒发，原重新过门禁断言保留。新消费文件由 33 增至 35 例；原 33 例收据不改签。

干净 `0154b06d1ed3adcdcc5236d6441155e44d4ab37c` 两文件 **51P**，独立收据 `fulfillment-fixed-code-receipt.json` 及校验日志均在新证据根；全仓 Ruff/提交门通过。进程内撤掉必需行占位，两例均红，还原后绿；首次错误量具留档，不当证据。这里只是定向追补，后续固定 HEAD 的完整门与 CI 尚待执行/回读。方案取舍、红集和完整原件指针见[CI 追补快照](../handoffs/2026-10-08-river-repair-ci-followup.md)。

## 未验证 / 不成立的结论

- 本机未跑本轮完整 pytest、前端/E2E 与注册表组合门；远端阶段观察不能改称完整本机验收或合并许可。
- 未连生产库做教学 build/reset/export，未发布任何数据包，未重启服务、切换部署或运行真实模型问题。
- `regime_script` 是探索性函数：检查同 ID 隔离不等于日期区间/后续事实区间无重叠；标准化拟合范围、时间顺序、PIT、序列自相关仍要调用方提供证据。逐窗口置换不是时序预测有效性证明，不能把过闸写成“已找到行情规律”。
- A 开场与 B compose 的 D10 已接镜头，但 B 的 generic owner 早退分支不走 D 块；不能称所有问答路径覆盖。教学 `tf.*`、用户判断台账、环境剧本自动命名/持久化及回检尚未接入新镜头。
- 只读核验不等于数据修复：教学缺数和旧 schema 仍在；历史日逐日 strict 交集与 river 单 cutoff 的 strict 日行计数不是同一分母。未执行教学升级/构建/回填，完整修订历史仍未验证。
- 截止仅在读取前及两块之间检查，不硬取消已运行 DuckDB 查询；这是历史预取局部权限门，不代表所有预取/工具统一受控。`local_only` 自动播种关闭不等于禁止已经授权的本地工具。
- `guided_reading.py`/CLI 的观察剧本入口原本存在，缺的是每日产物接线，不再报成“观察剧本未落地”。
- `KNOWABLE_AT_CLOSE` 与 `SLICE_EVALUABLE_LABELS` 含义不同，本次保留两套集合；标签数不是质量指标。
- `first_known_at` 保留依赖旧值/文本相同，不构成多版本历史库，也不证明供应商后续修订在历史当日已经可知。
- 画像字段投影不能证明正文无隐私/原文；结构化 `output_policy` 也不是身份授权实现。拆分 ID 只保证同输入稳定，插入条目后序号会变；还原校验忽略空白，对英文/连续/末尾分号目前会拒绝而不是默默丢字。

## 后续

1. 回读最新 PR head 的 Actions，另补本机完整工程验收；固定代码与文档收据不移签。草稿状态保留，合并须用户确认。
2. 在明确授权范围内验证完整 Workbench 入口及模型实际利用；本轮只读真库和接口替身不代替真实研究质量。
3. 先补教学特征版本/PIT、环境剧本时间合同与概念持久化，再接观察/回检；保留“不命名”的合法空结果。生产写入、部署和真实/付费模型验证分别授权。
