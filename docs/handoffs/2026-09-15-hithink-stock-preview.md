# 同花顺个股标准化预演 · 2026-09-15 交接

## 状态与范围

作者树 `/Users/a77/fwp-wt-hithink-review-wiring`，分支 `fix/hithink-review-wiring`。
本片已提交 `40317d780d71de03ca6884c4c437b9accece0b49`，父提交 `3bba5b4e` 是前三片的文档归档；业务前序为 `9621128a`、`dcee18f2`、`c85d0101`，任务基线 `gitea/main@1fef3d276d0e`。

用户要求继续最优路线，随后明确要求 handoff。本轮停在**个股标准化只读预演＋定向验证**，保存代码后完成交接，不在交接过程中继续扩功能。没有 push、合并、部署、获取行情 key、请求真实行情或写生产库；所有数据库验证均为合成数据和隔离 DuckDB。

- 活交接：[inflight/fix-hithink-review-wiring.md](inflight/fix-hithink-review-wiring.md)。
- 本片证据：[verification/2026-09-15-hithink-stock-preview/](../verification/2026-09-15-hithink-stock-preview/README.md)。
- 前三片状态/证据：[采集版本快照](2026-09-15-hithink-sector-capture-audit.md)；其全量、六类变异、前端/E2E已完成，不再作为旧片待办，也不能借给本片。

## 为什么先做预演

允许改用同花顺自己的板块/成员，不等于可以暗换涨幅、单位、复权或窗口。此前已完成并跑与板块版本预览，但 canonical 个股日更仍未接通，新池发布也未落地。直接用 raw dump 替换事实表会把元当亿元、股当手，或把现金除息误算成下跌；沿旧代码的 `LAG(close)` 跳过缺行情日，还会把“缺前日”误当成正常跨日收益。

检查了既有同步器、单日修复器、授课模块、schema、板块拼接器和 `SectorUniverseStore`，没有把“已有相似公式”当成可直接上线的合同：

- `repair_hithink_stock_day.py` 是 2026-09-11 特定白名单修复，含新增票、新股、停牌、金额漂移等逐票处置，不能泛化成日更。
- 授课模块已有现金/送转/配股公式，但其最近有行日、除权参考价舍入和覆盖范围不等于本片的正式事实输入要求。
- `SectorUniverseStore.publish_snapshot()` 目前按 provider 维持发布唯一性，而若干消费者按交易日要求唯一 published。未来切 provider 必须验证旧/新 provider 的退役与可见性合同，**不能只依次调用两次 publish 就认为全局只剩一版**；本片未修改这一机制。

## 按发现顺序的实施与错误

1. 代码地图 build 返回成功，但 query 仍为 `status=stale`、`vault=unavailable`、结构无命中、叙事 missing；定位依赖直接源码与测试，未用空图下架构结论。
2. 新增行为测试，夹具最初按第一个分号截 DDL，撞上注释内分号，导致5F/74E。改为 DuckDB `extract_statements()` 解析真实 schema。这是**测试夹具错误**，不算业务保护反证。
3. 夹具修好后79F来自新模块/CLI尚未实现；是测试先行状态，不是现有算法已经被独立证伪。
4. 实现 `hithink_stock_preview.py` 和 CLI；正则少右括号导致78F/1P。修正后79P。这是实现错误，不是供应商或依赖故障。
5. 扩充测试发现3F/90P：小数股未拒绝（今/前日各一项），以及 `localcontext()` 继承了外部 traps/指数范围。补正整数股约束，并显式构造完整 `Context`，不继承当前 context 或可变 `DefaultContext`。
6. 相关十文件回归275P；再补 `DefaultContext` 污染反例和20组独立整数有理数舍入对照，回归277P。
7. 口径/术语与 ADR 同代码提交为 `40317d78`。干净该提交再跑相同十文件277P，收据校验通过；之后只有交接/证据文档改动。**未运行本片全量或删保护变异**。

## 接口与合同

```python
preview_stock_calculation(con, trade_date, *, stock_codes: Sequence[str]) -> dict
```

命令 `python -m market_feature_store.cli hithink-stock-preview --trade-date YYYY-MM-DD --stock-code CODE [--stock-code CODE ...]`；数据库用 `MARKET_FEATURE_STORE_DB` 明确指向隔离库。入口仅 `connect(read_only=True)`，不初始化、不取 key、不建写库旁路，未接入 local 分步或已有板块预览。

详细参数/字段见 [运行口径](../data-sources/runtime-and-pitfalls.md#个股标准化只读预演本分支代码未部署)，难逆边界见 [ADR-0005](../adr/0005-stock-preview-is-not-daily-publication.md)。本片六个提交文件：

- `market_feature_store/hithink_stock_preview.py`
- `market_feature_store/cli.py`
- `tests/test_hithink_stock_preview.py`
- `docs/adr/0005-stock-preview-is-not-daily-publication.md`
- `docs/data-sources/runtime-and-pitfalls.md`
- `UBIQUITOUS_LANGUAGE.md`

### 方案取舍

| 问题 | 采用 | 被否方案及原因 |
|---|---|---|
| 验证分母 | 显式非空唯一股票范围；缺股不缩分母 | 只用拿到的股票，天然掩盖未到数据；代码形状验证也不能当上市名册 |
| 时间窗口 | 目标和前一计划交易日 | 最近有行日可能跨抓漏/停牌，新股发行价也不能从旧表暗借 |
| 读取一致性 | 两日行情＋当日事件一条SQL快照；校验和消费同一份行 | 分次读会混时点；先核验再另查可能拿到未核验版本 |
| 除息 | 纯现金：先减每股分红，再按分价舍入参考前收 | 非现金事件套通用公式会扩大未经验证的合同；NULL不能猜成零 |
| 计算 | DOUBLE十进制文本→固定精度50的Decimal；半进舍入 | 二进制 `round` 在边界可能差0.01；也不声称新算法等价于旧修复器混合算法 |
| 量额 | 元/1e8→亿元4位，股/100→整数手，保留原量额 | dump.turnover不是换手率；小量舍入零也不能标成原始零成交 |
| 字段缺口 | 名字/换手率为NULL；非现金/缺前日/零成交报缺口 | 从昨日或旧源偷偷补值，会隐去缺口与来源 |
| 可用性声明 | 可算、覆盖未知、生产未就绪分别报告 | 内部自洽或输入指纹不能证明供应商全集、事件无遗漏或发布资格 |

正常输出含合同 `hithink-stock-preview-v1`、声明/可算股票数、部分诊断行、缺口、范围/输入指纹和逐行来源。exit0只表示全部声明范围可算；缺口/非法参数/缺库缺表exit2。`production_ready=false`、`request_complete=null`、`provider_completeness=unverified`、`adjustment_coverage=unverified`。

## 已验证与收据适用范围

统一解释器 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`，Python3.12.13，依赖指纹 `3328bed61f3e21ea`。pytest壳为 `env -i PATH="$PATH" HOME="$HOME" KNOWLEDGE_WIKI="$KNOWLEDGE_WIKI"`、`umask 022`，未绕依赖门。

| 收据 | 状态 | 结果与性质 |
|---|---|---|
| `20260915T085754Z-3bba5b4e.json` | 开发dirty | 5F/74E，夹具DDL截断错误 |
| `20260915T085853Z-3bba5b4e.json` | 开发dirty | 79F，新模块/CLI尚未实现 |
| `20260915T090550Z-3bba5b4e.json` | 开发dirty | 78F/1P，正则编译错误 |
| `20260915T091033Z-3bba5b4e.json` | 开发dirty | 79P |
| `20260915T091227Z-3bba5b4e.json` | 开发dirty | 3F/90P，整数股与Decimal上下文边界 |
| `20260915T092601Z-3bba5b4e.json` | 开发dirty | 十文件275P |
| `20260915T093748Z-3bba5b4e.json` | 开发dirty | 十文件277P/7.70s |
| **`20260915T094612Z-40317d78.json`** | **干净固定代码** | **十文件277P/9.90s，exit0** |

最后一份的revision/解释器/Python/依赖/干净状态/未绕门核验exit0。两次耗时不是性能结论。前三片收据另见旧快照，不能将本片dirty结果重贴成父提交干净结果，也不能把固定40317d78结果称作后续归档提交的新测试。

覆盖包含：今/前日缺失与重复、周末/休市/未知年、源标签/复权标签、OHLC有限性/分价/区间、零/负/小数成交量、金额、事件字段/币种/非现金拒绝、正负半进边界、参考价先舍入、进程context及DefaultContext隔离、一条语句读取、范围/输入指纹、未知股票不缩分母、原始小量舍入、20组整数有理数oracle。真CLI子进程检查exit0/2与数据库SHA256不变，缺路径不创建；禁用key/网络/初始化入口的测试通过。**合成夹具没有验证供应商真实量额关系或原单位。**

三文件Ruff、`git diff --check` 与代码提交hooks通过；未宣称全仓Ruff。层级审计ERROR0，字段/路径/可达性门通过；dataset只核schema归属，未给可读DB，空表内容检查跳过。没有新表或业务台账，无需新增台账写者。

## 未验证与下一步

1. **先完成40317d78自己的作者验收**：全量pytest/全仓Ruff、删保护变异后恢复干净收据；本片前端/E2E与registry五命令未重新跑。旧c85d0101全量9739P/79S/2X、六类变异及前端/E2E只属于旧代码。
2. **独立复核仍缺**：历史Codex额度/Claude503均无有效报告；本片未重试、未取消该门。若续审，需针对新增 `3bba5b4e..40317d78` 提供新的固定范围，旧c85d0101任务不覆盖本片。不无限重试，不借另一个E2任务关闭QC的授权。
3. **跨仓/环境旧门未关闭**：上次KB七个注册指纹漂移；本机Node26/macOS不同于工作流Node22/Linux。当前未代修或刷新他仓指纹、未借其他枝收据，不称merge-ready。
4. **再设计通用投影**：补行情/事件采集覆盖、独立股票分母、目标日关键字段、送转/配股/新股/停复牌及名称/换手率来源。当前无事件行可能是遗漏，不能把可算抬成正确参考涨幅。
5. **最后接池与真实产物**：明确类别涨幅算法、成员版本与复权/收益窗口，再沿`SectorUniverseStore`既有接口处理候选/发布与provider迁移；不写公开VIEW。local仍skip-constituents，尚未接通canonical日更/新池投影，日报/队列/矩阵/snapshot真实当次产物未验。
6. 真实行情、补历史与产物验收另取授权；合并部署须用户确认，生产仍仅daily-full staging校验＋原子换库。不得拿单日修复器、异口径资金或复制昨日行改日期顶替。

时间和真实性边界：更新时间只验证是时间类型，未审鲜度/当时可见性；历史预演读取当前存储版本。只取当日事件、不生成复权历史序列/多日收益；输入指纹没有持久原件或外部签名。板块capture冻结的是名单，并未扩权认证个股行情或事件覆盖。

## 沉淀盘点

本片新增的自动能力已在产品CLI/模块和pytest内，不是临时通用运行器；不另造发布器、台账或测试框架。DDL解析用已有DuckDB解析器；固定数值环境和整数oracle可迁移到计费/金额计算，方法回写既有`source-switch-coverage-must-be-reconciled-first.md`，具体守卫已经落测试。删保护反证待补，不将先红后绿称作变异已完成。未触碰他人的`harness-reference/BUILD.md`修改。

能力图谱回写沿既有同花顺节点；graph audit仅检查路径/符号且包含主检出/KB脏树，不是运行或合流验收。证据归档的输入hash只证明字节未损，不证明业务正确。

---

## 批次 2 · 同日续跑补验（追加段，上文交接时状态保持原文）

用户指示「继续按最优路线推进」后同日完成，证据全部追加进 [verification/2026-09-15-hithink-stock-preview/](../verification/2026-09-15-hithink-stock-preview/README.md)：

1. **全量**：干净 `2ad19f35`（= `40317d78` + 纯文档归档提交，`git diff -- ':!docs'` 为空）全量 pytest **9834P/79S/2X、exit0、642s**，收据 `20260915T103043Z-2ad19f35.json` 七项条件核验通过。全仓 Ruff 通过。
2. **删保护变异 12/12 红**：隔离树基线 95P → M1 整数股、M2 非现金拒绝、M3 固定 Decimal Context、M4 参考价先舍入、M5 零成交、M6 缺/重行、M7 分母不缩、M8 production_ready、M9 元→亿元、M10 计划交易日、M11 来源标签、M12 分价，逐个落盘核验、逐个见红（1–56F，红的均为语义对应测试）、还原后 95P。驱动源码与逐项结果表在归档内。
3. **前端四叶**：lint/typecheck/build exit0、Vitest 76P（本片零前端改动；本机 Node26/macOS，非 CI 环境；Playwright E2E 未跑）。
4. **registry**：check-parseability 60/60、generate-views 跑后树干净；跨仓 check 仍红且 7 处漂移全在 kb/ 侧、finance 侧零漂移（与前三片时一致，非本片新增）。
5. **独立 QC 完成（本任务首次有报告）**：codex 配额探针已通但按用户指示改用 **k3（`pi --provider mirasim-kimi --model kimi-k3`）**，隔离 worktree 固定 `40317d78`，exit0。结论：**无 P0/P1/P2**；155 项独立探针 + CLI/类型边界全过；QC 自跑全量 9836P/0F/77S（与作者侧总数同为 9913、均 0 失败）。两条 P3：CLI 失败路径 fallback 报告缺 `contract_version`（与 sector-preview 同 pattern，建议两片一起补）；文档未写「休市表仅登记 2026 年 → 仅支持 2026 目标日」。两条观察项（全零事件行 basis 标签、`row` 变量初始化健壮性）见报告 §3。复核后作者树/分支 ref/QC 树零污染由作者对照事前指纹独立核验。
6. pi 无 codex 式 OS 沙箱，隔离改为「指令约束 + 事前指纹、事后归因」：全仓 refs 变化归因为其他并发会话分支，vault 三笔 auto-sync 归因为其他会话台账 + 本轮图谱/笔记回写。

**批次 2 后仍然不变的边界**：真实供应商数据未碰、覆盖完整性未验、`production_ready` 恒 false、未 push/合并/部署；Playwright E2E 与 kb 侧 registry 漂移是留给合并前的既存项，不属本片。
