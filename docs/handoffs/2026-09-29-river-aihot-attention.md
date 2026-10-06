# 每日长河 × AIHOT 舆论接入：第一版实施交接

日期：2026-09-29。状态：**源码增量已写入原项目；定向验证和隔离构建通过；未提交、未合并、未部署/重启现有服务。**

## 1. 这一版交付了什么

### 每日市场全景

- 原 `App.tsx` 的长河入口转到 `RiverHome.tsx`；默认进入「每日全景」，原 `RiverWorkbench.tsx` 六轨研究完整保留。
- 统一日期：上证 K 线、MA5/MA20、全市场成交额、涨跌幅、上涨家数、涨跌停、市场阶段、板块排行、板块热力图、连板明细随同一交易日变化。
- 板块×日期矩阵：10/20/40/60日，搜索、成交额/领涨/领跌/近5日排序、24/60/全部板块、涨跌幅/成交额切换。
- 点击矩阵选择日期和板块；「展开板块六轨」带实体与日期回原研究工作台。
- 连板页支持历史 `end` 参数，外部选中日在当前窗口之外时重新定位，不再偷偷跳回最新一天；过期请求不再覆盖新窗口。
- 缺失格使用斜纹，不把 `null` 当作零。近5日累计收益使用连续5个交易日的日涨跌幅复合，任一天缺失就不算。
- 指数这版只接上证，不冒充已经覆盖其他 A 股宽基。板块有重叠，成交额不可汇总冒充全市场成交额。
- 板块身份按代码+名称保守分段，不把供应商换码/换名后的序列自动拼成同一口径。

### 舆论层（可导入、可回放的接入基础版）

- 新增公开消息观察台账，与卖方 `opinion-events.jsonl`、研报目录分开，**不重做或覆盖它们**。
- AIHOT 完整 `/api/v1/items` 条目导入；保留原文 URL、上游发布/发现时间、本地实际 `recorded_at`、版本链和撤回状态。
- 导入默认 dry-run，显式 `--apply` 才追加。整批有错误不写；来源映射和板块映射必须显式给出，不用标题子串猜「铜/铜缆」归属。
- 同 URL 归一、去跟踪参数、幂等追加、文件锁。修订/撤回/恢复都用新版本表达；按知识截止日读取最新可见版本。
- 已复核归组事件计算48小时、24小时半衰期的「已观察来源热度」。同来源最多一个贡献；明确同源转载使用 `origin_key` 归一。
- 未知来源、未归组文章、缺时区发布时间、缺转载血缘均保留缺口。没有连续采集覆盖证明时 `trend_pct=null`，不臆判升温/降温。
- `opinion_attention_bridge.py` 将有效公开消息作为 `public_news_attention` 子类加入 `river.slice_river` 的舆论轨。保留原研报覆盖；若原轨是缺口，在新对象中继续保留 `report_coverage_gap`。
- 未存在台账时，原六轨读取结果不变；有损坏台账时 fail-closed，而不是默默画成零。
- 公开消息始终标 `evidence_status=unreviewed`。官方来源身份、LLM的摘要、AIHOT的精选分/事实表都**不等于公司事实已核实**，不自动写入公司画像、观点胜率或产业链 ground truth。

## 2. AIHOT 的取舍与已核对边界

核对公开仓固定提交：`589f79eff09470b31ba8a7f1d9eb62d36ff2be6c`。

- 值得借用：信源身份归一、事件层而非文章层聚合、滚动衰减热度、采集覆盖缺口、原始/发现/版本时间分离。
- 不整套搬入：其 PostgreSQL / pg-boss / Fastify / SSR站点会与当前 Python + DuckDB + React 工作台形成两套部署。此版先通过适配层接入，保留以后将其独立 worker 作为采集服务的选择。
- 原版示范源是海外 AI 资讯，不是已经替我们配好的 A 股全市场信息源。
- 原版公开条目 v1 返回标题/摘要/来源名称/原文链接/时间等，**没有完整事件成员、来源血缘与板块映射**。因此基础导入不凭空补 `story_id`、机构独立性或事件归组；归组映射是显式审核输入。
- 原版热榜是精选展示面，不能只抓 Top10 就声称得到全市场舆论。拉取器使用 `mode=all&window=7d&by=published`，并明确它仍只是该站「公开 eligible 条目」，不是全网。
- 原版热度会回补/重算旧小时，热榜历史也有保留期限；不可直接拿当前热榜倒填我方历史观察。我们的真实本地入库时刻不从上游 `discoveredAt` 回填。
- 我方 `consensus_staging` 是累计证据支持的认同度下限，不是可涨可跌的日常注意力热度。此版不把新热度塞进那套阶段分，不覆盖90日研报覆盖分位。
- 基础条目适配已做离线协议/边界测试，**没有声称在线 AIHOT 实例联调成功，也没有把上游模型语义聚类器部署成我方自动聚类**。

参考：
- [AIHOT README](https://github.com/KKKKhazix/AIHOT/blob/589f79eff09470b31ba8a7f1d9eb62d36ff2be6c/README.md)
- [上游公开条目契约](https://github.com/KKKKhazix/AIHOT/blob/589f79eff09470b31ba8a7f1d9eb62d36ff2be6c/packages/backend/src/publication/publish.ts)
- [上游热度](https://github.com/KKKKhazix/AIHOT/blob/589f79eff09470b31ba8a7f1d9eb62d36ff2be6c/packages/backend/src/events/hot.ts)

未复制 AIHOT 的商标、Logo 或运营数据；本版为接口兼容与规则借鉴，没有携入其运行依赖。若后续直接复用上游代码，必须保留 MIT 版权声明并审查第三方素材权利。

## 3. 接口与文件

新增接口：

```text
GET /api/river/daily-overview?days=20&end=YYYY-MM-DD
GET /api/river/opinion-attention?as_of=YYYY-MM-DD&entity_id=<canonical-id>
GET /api/limitup/calendar?days=60&end=YYYY-MM-DD  # 原接口新增可选 end
```

新增后端：
- `intelligence/services/river_daily_overview.py`
- `intelligence/services/opinion_attention.py`
- `intelligence/services/opinion_attention_bridge.py`
- `intelligence/api/river_daily_routes.py`
- `scripts/import_aihot_attention.py`
- `scripts/pull_aihot_attention.py`

新增前端：
- `intelligence/webapp/src/components/river/DailyRiverDashboard.tsx`
- `intelligence/webapp/src/components/river/RiverHome.tsx`
- `intelligence/webapp/src/river/dailyTypes.ts`、`dailyMath.ts`
- `intelligence/webapp/src/riverDaily.css`

最小修改的现有文件：`App.tsx`、`RiverWorkbench.tsx`、`LimitUpDashboard.tsx`、`SliceDrawer.tsx`、`river/api.ts`、`intelligence/api/river_routes.py`、`intelligence/services/river.py`、台账登记文档。

## 4. 使用方法

先准备明确审核的映射。模板：`docs/examples/aihot-attention-mapping.example.json`。模板含占位符，不能直接导入生产。板块ID/名称需核对当前 canonical 表及别名映射；来源集团与转载链不能用新闻网站页面数冒充。

离线完整条目导出：

```bash
.venv-workbench/bin/python scripts/import_aihot_attention.py export.json --mapping mapping.json
# 确认 accepted / grouped / mapped / errors 后再写入：
.venv-workbench/bin/python scripts/import_aihot_attention.py export.json --mapping mapping.json --apply
```

显式拉取自己的 AIHOT 实例：

```bash
.venv-workbench/bin/python scripts/pull_aihot_attention.py \
  --base-url https://YOUR-AIHOT-HOST --mapping mapping.json
# 确认来源和预算之后才加 --apply；不默认安装定时任务。
```

拉取最多默认10页，每页100条，单页响应有大小上限；分页失败、游标重复或页数预算用尽都拒绝部分成功。只访问给定AIHOT站点，不继续爬原文、不发送私有研报、没有模型/公众号/X付费API调用。

台账默认落在 `data_repo_root()/state/opinion-attention/observations.jsonl`；可由 `OPINION_ATTENTION_LEDGER` 显式覆盖。源数据属于运行产物，不提交Git。两个CLI共享同一个 append 实现与锁，不建立两条不同写入口径。

## 5. 验证与交付状态

- 原项目指定 `.venv-workbench/bin/python` 的定向后端回归：**76 passed**（原项目混合工作树定向运行），包括新增导入、时点、修订/撤回/恢复、热度、分页、历史连板以及原 river/query/cutoff/recorded_at/route 注册用例。
- 前端新增每日视图、历史连板及原 ScanPanel 的定向测试 **12 passed**；完整前端 TypeScript 类型检查通过。
- 新增 Python 的 Ruff 与新增前端 ESLint 通过。
- **完整原前端构建**输出到 `.tmp/arena-river-opinion-0929/web-build/`，没有覆盖运行中的 `intelligence/api/static/`。
- 真库只读查询验证：60个交易日，2026-07-03～2026-09-24；跨窗口630个「代码+名称」身份，最新日403个板块；这不意味着630个当前活跃板块。一次实测读取约1.2秒，非压测结论。
- 浏览器验证：1536px桌面与390px手机、日期选择、矩阵选板块、舆论空态、切换连板、错误检查；手机页面宽度390px，无整页横向溢出。
- 独立HTML预览携带上述行情快照，不带私有研报/用户判断台账；无外部网络依赖，离线打开及日期交互通过。原工作台六轨入口仅在源码内接通，独立预览相应按钮会说明边界，不伪造其结果。
- **没有跑全仓测试、没有合并、没有部署重启。**当前主检出树是 detached HEAD，含大量他人未提交改动，不能把本次定向结果写成“整个项目全绿”。

## 6. 安全续做与剩余事项

1. 确定采用自己的 AIHOT 实例还是仅复用其 worker，并确认金融信源名单、独立来源注册表、板块映射。这些不能从示范18个海外AI源直接等同于A股全市场。
2. 需要自动事件聚类时，在采集侧加入/导出可追溯的事件成员与模型版本，再在我方保留“模型候选/人工复核”的区分；不是删除当前安全门。
3. 连续采集覆盖、同源转载识别、市场开闭市时点与历史订正收齐后，才可以发布“升温/降温/舆论阶段”，不单凭两次抽样下结论。
4. 想看多A股指数，需要补/确认相应历史源与口径，本版没有用空卡片假装覆盖。
5. 当前最新行情是09-24；没有擅自运行 daily-full 或写主DuckDB去“追到今天”。
6. 激活原工作台需按现有部署入口受控构建/重启。不要公开绑定这套未提供生产级认证的私有后端；当前在线预览是独立行情快照，并非把Mac工作台开放到公网。

备份与逐段补丁：`.tmp/arena-river-opinion-0929/base/`、`before-history-link/`、`*-patches.json`。回退只反向应用本轮唯一匹配的补丁；**不要** `git checkout .`、`git reset --hard` 或覆盖他人未提交修改。后续若其他agent改了同段，应人工合并。
