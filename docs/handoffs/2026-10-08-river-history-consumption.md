# river 镜头日常消费：接线与模型输入边界

## 背景与状态

[迁移快照](2026-10-08-vidio-finance-transfer-public.md) 固定了完整交付审查与公开历史隔离。当时新镜头只有独立入口，日常历史比较仍走旧 D10。继续推进的目标是让比较读数、来源、时间限制和缺口一起到达模型，而不是增加另一份 CLI 输出。

接线代码 `7389549bcd20ada12f1f78f0ea4a91a178df551e` 已推 [草稿 PR #75](https://github.com/moscrol/finance/pull/75)。工作树 `~/fwp-wt-vidio-finance-public`；基线 `82de3fb730a4175170b4e6ba472e130e5ef87ab7`。本轮没有合并、部署、服务重启、生产数据写入、用户画像修改或真实/付费模型调用。

验收分层：组件存在 → 接线正确 → 模型接口收到 → 模型实际利用 → 研究效果 → 生产运行。**本轮推进到第三层；只读真库另证可计算，后面三层没有被替身测试证明。**

## 发现顺序

1. 回读产品门、A/B 消费链和已有观察剧本。`guided_reading.py`/CLI 骨架原本存在，不再以“完全没落地”概括；缺的是新比较结果与日常观察/回检的连接。
2. 新建七张表的合成 DuckDB，包含截止后的极值和故意晚于截止的记录时间。夹具路径、API 与权限输入修正后，真实修前结果为 6F/3P，暴露镜头缺席、缺口不完整、来源/PIT 元数据缺失和账本不送达。原夹具错误与语义反例分开保存。
3. 新增 `market_history_context.market_history_blocks()`，由 A 预取和 B 的 D10 共用。默认库只解析一次，调用者显式提供站立日；保留旧类比后续事实，另外生成 river 镜头，两块独立失败。
4. 镜头增加实际拟合范围、当前窗、上游 PIT 日行计数、表/列与聚合规则、暂停维、缺维和逐维水平/趋势/贡献。未知标记不升 strict，相关组不称独立证据。
5. B 的历史问句日期要在规划/快照读取前冻结；仅给 D10 加旧日期仍会让同一输入的市场上下文声称库尾日期。明确日期优先于问句日期和快照日期。
6. 读数进入 D10 后又在 AnswerSpec 丢失：通用拆行只保留部分等级；展示清洗还会抹掉表/列名。改为原始、整块 `data:D10:context`，继续标 `INFERRED`。未来复核日曾被测试误报成未来行情，断言改为检查事实块，保留合法复核日。
7. 只读核验正式行情与教学库。行情两块可以出数，但教学缺数/旧 schema 与历史版本不足没有被接线消除。river 的 strict 相对单次 cutoff，和历史日逐日时间戳审计不是同一口径；把这层差异写入模型实际收到的镜头。
8. 补父截止透传：D10 启动前及镜头启动前检查同一 deadline；前块耗尽预算后不再起后块。材料限制在预取 IO 前判断；空签名/空候选仍送来源/PIT，不因 gap 抹掉元数据。
9. 验 prepared 输入还不够。默认 grounded 合成只认 summary/verified 支持，D10-only 根本不发模型请求；有其他支持时又可能被长资料挤出 12K registry。修正夹具缺字段后保留真实反例，再分别修准入和预算。
10. 有 D10 来源的短推断摘要只概括共同边界；完整表继续放在 context。新增显式 `required_claim_ids` 原子占位，初次合成和缺项修订共用，装不下便拒发并确定性降级。
11. A 运行真实 `ContinuousAgentEpisode.run()`，在首次 `complete()` 截获后停止；B 捕获默认/旧合成模型接口，覆盖拥挤/不拥挤、D10-only、超限拒发。没有生成或评分金融答案。
12. 固定代码、实际提交门通过后，在干净 SHA 上重新跑扩大定向回归、Ruff、收据校验和代码地图，再显式推公开分支。dirty 树日志保留，不移签。

## 决策与被否方案

| 议题 | 选用方案 | 被否方案与理由 |
|---|---|---|
| 旧后续事实 | D10 与 river 并列、候选独立 | 用镜头替换 D10 会丢后续事实；按同名次嫁接会把不同窗口的收益混用 |
| 读取接缝 | 共用库路径、日期和父截止 | 两条引擎各实现一份会漂；另开预算会绕过父约束 |
| 时间语义 | 日期截断、单 cutoff PIT、逐日 strict 分开表述 | 交易日不晚于 cutoff 不能证明当时知道，也不能证明修订前的值仍在 |
| 逐维解释 | 显示实际数值、贡献、覆盖分母和缺维 | 只送“像/不像”阈值标签会隐藏中间维与缺数 |
| AnswerSpec | 整块原始 Claim，等级 INFERRED | 逐行切碎会丢共同限制；展示清洗会抹来源；升 VERIFIED 是人为提高证据等级 |
| 默认合成准入 | 有来源的短边界摘要 | 全局放宽 candidate 支持会影响其他任务；在摘要再放全表重复烧预算 |
| 模型上下文预算 | 必需完整行先占位，原 12K 不变 | 单纯加大预算只是推迟故障；送残表会让读数脱离限制；无条件静默丢弃不合合同 |
| 材料与权限 | 自动预取在 IO 前守卫，已授权工具维持原合同 | 先读取再丢弃已经越界；停自动播种不等于禁用所有本地工具 |
| 消费验收 | 截获实际模型调用边界 | formatter/prepared 文本存在不证明默认分支发过请求；离线收到也不证明模型利用 |
| 数据不足 | 显式缺口、停止升档 | 补零、前填或调阈值凑命名会改变领域含义；生产升级/构建需另授权 |

## 验证身份与收据

解释器：本树 `.venv-workbench/bin/python` → `~/.finance-runtime/venvs/workbench-locked-20261007`，Python **3.12.13**；未绕依赖门。本机 Node 26，不称与 CI 的 Node 22 完全相同。

本轮原件只留 `~/.finance-runtime/reviews/river-consumption-20261008/`：

| 阶段 | 原件 | 结论 |
|---|---|---|
| 初始反例 | `before-corrected.*` | 修正夹具后 6F/3P |
| prepared 送达 | `delivery-before.*`、`delivery-after.*`、`delivery-fixed.*`、`delivery-final.*` | 最终 18P；中间来源清洗缺陷与未来复核日误断言分别记录 |
| 父截止/材料 | `deadline-before.log` | API 缺席与受限范围入口反例，不全部称语义失败 |
| 默认合成 | `grounded-before.*`、`grounded-corrected-before.*`、`grounded-after.*` | 原版未发请求/拥挤遗失；修后相关 89P，含既有 AnswerModel/截断告知 |
| 实际接口 | `sink-final.*` | 当时 31P；后来新增两例纳入扩大测试，不能把这份收据改称 33P |
| 最后 dirty 扩大 | `expanded-final.*` | 1785P/44S/19229未选，绑定 `545fb854b` dirty 树 |
| 干净代码 `7389549bc` | `fixed-code.log/xml`、`fixed-code-receipt.json` | **1785P/44S/19229未选**，1 条 TestClient 弃用 warning；选择串见[质检报告](../verification/2026-10-08-vidio-finance-transfer-qc.md) |
| 身份核验 | `fixed-code-receipt-check.log` | revision/解释器/依赖/净树/基座漂移0通过；收集面明确收窄，非全仓 |
| 静态/提交 | `fixed-code-ruff.log`、`code-commit.log` | 全仓 Ruff、实际 pre-commit 通过；不代替运行/效果验证 |
| 地图 | `fixed-code-map-*` | structure ready；vault unavailable、doors/narrative missing、语义召回未验 |

新文件 `intelligence/tests/test_river_history_consumption.py` 收集 **33 个实例**。包括：日期/未来行扰动、缺库不建库、缺 schema 局部 gap、异常路径不泄漏、无能力/过期/受限 scope 不启动、同一 deadline 透传、默认库一致、逐维与来源送达、空结果仍有元数据、证据 hash/E 序号、A 首次模型调用、B 两种合成×拥挤矩阵、D10-only 不升事实、原子预算边界及超预算拒发。

代码 CI：workbench [37689283789](https://github.com/moscrol/finance/actions/runs/37689283789)，registry [37689283765](https://github.com/moscrol/finance/actions/runs/37689283765)。2026-10-08 05:37 CST 阶段观察：registry/frontend 成功，python/e2e 仍在运行；不是最终结论。旧 `545fb854b` 全绿仅属旧版本。后续文档 HEAD 的检查需按实际 SHA 从 PR 回读，不在本快照预填成功。

## 真库探针的界限

只读原件为 `teaching-current-readonly.json`、`market-current-readonly.json`、`live-readonly-probe.json`，不随公开仓上传。核验解除“尚不知能否读到正式数据”的缺口，但只支持确定性读取与计算；单次耗时不是性能基准，mtime/size 未变也不认证历史版本完整性。

教学缺数和旧 schema 仍是后续工作的实际阻碍，无收据不证明从未构建、空表不证明被谁清空。历史日逐日 strict 交集与 river 相对单一 cutoff 的日行计数不可互换；当前维度覆盖完整也不表示教学与用户判断维已接入。

## 未覆盖路径与下一步

- A 没有跑完整 Workbench `TurnOrchestrator.run_turn`、真实模型回答与公开答案检查；B generic owner 早退分支不走 D10。
- 教学 `tf.*` 和用户判断台账尚未加入镜头特征空间；未改用户定义或未决阈值。
- `regime_script` 仍为探索性纯函数，未连自动生成/人审命名/版本保存/召回/回检/修订淘汰。ID 不同不证明窗口或后续区间独立；标准化和自相关合同仍待定。
- deadline 是启动守卫，不是 DuckDB 查询硬取消；历史权限检查不是所有预取和工具的统一权限修复。
- 本机完整 pytest/前端/E2E/注册表组合门未跑；定向绿不取得合并许可。先回读新 HEAD CI，再按范围补齐验收。
- 保持 Draft。真实/付费模型、生产 schema/数据操作、部署分别确认授权；只推公开分支，不推本地完整导入和清理前历史。

## 工具与方法沉淀

接线反例已进入正式测试；原子预算是现有 registry 的显式参数，不另造上下文框架。重复测试/收据/地图/审计复用现有脚本；真库探针是一次性只读核验，不推广为性能或质量基准。

可迁移方法：验收要越过 prepared 到实际调用边界；数据与解释其有效范围的限制应共同预算；准入资格不能靠伪造事实等级获得。选择哪些内容不可拆仍需领域合同，因此没有把它包装成自动语义筛选器。私有能力图谱与项目索引只记录本候选范围，不追认 main 或生产已具备。

私有 memory 三文件增量已由自动同步提交 `0a7bae37d299cf64b0172001a817b980de3ef54f` 收走，本地与 Gitea 同版本；未借本任务推 GitHub 上落后的全部记忆历史。`graph_audit.py` 前后 exit 0，两个新增接缝符号标为分支 PENDING；vault lint 前后 exit 1，48 条相同存量 ERROR，新增/移除均为 0。这不表示整库 lint 绿，未修改其他任务的历史错误。
