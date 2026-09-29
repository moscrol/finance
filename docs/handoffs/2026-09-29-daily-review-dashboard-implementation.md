# Daily 驱动的复盘工作区 — 2026-09-29 实施交接

## 已完成
用户确认“推进”后，延续原每日 dashboard + AIHOT 舆论层工作，在同一脏工作树做有界增量；不覆盖他人改动，不提交、合并、部署或重启。

1. 新只读接口 `GET /api/river/daily-review?as_of=YYYY-MM-DD`：读取 `default_paths().market_exports` 下同日 `daily-review/v1` JSON；与现有 `daily_reports.py` Workbench 投影共用同一真本源。新增的是行业／日期导航元数据，不是指标计算引擎。
2. 主视图新增“资金去向与持续性”：前三行业集中度及变动、行业成交占比和同名行业昨日占比、周均线偏离度、相对20日均量、涨家数 MA5。
3. 按申万一级切换近15日双红／120日新高／涨停矩阵。保留复合单元格、母行业和上证参照行；自动将当前日期滚入横向可见区域；展开全部行。数字0与原报告未列值分开显示。
4. 行业选择同步个股发动机（每行业 Top20），保留开根加权值、新高、双红交叉字段；可展开全部及个股明细。
5. 子板块仅在同日行情有唯一同名代码时开放六轨／舆论跳转；缺失或歧义不猜代码。日期仍与指数、原扫描面板和连板日历共享。
6. 可展开原日报15章节的全部表格及文字。原 MA5 图片不嵌入，页面明确提示；没有重写原分析结论。
7. 源归档交易日、生成时间与“归档不代表当时已知”分别显示；提供零双红结论、母行业占比缺失、新高映射缺失提示。

## 数据与边界
- 当前结构化归档共7份：2026-09-16、17、18、21、22、23、24；每份15节、3行业×20只发动机。
- 09-22 的新高矩阵可展示（3行业合计13行）；09-23/24归档的新高矩阵为空，保留全市场新高数并提示映射缺口，不补0、不补昨日。
- 无同日 JSON：200 + `status=missing`，列出可显式跳转的归档日期。不会偷偷用最近日报；旧日仅有 Markdown 的，不反向解析为交互数据。
- JSON版本/交易日/行宽/结构损坏：503；非法日期：422；限定文件大小5 MiB，拒绝越目录软链，响应不泄露异常绝对路径。
- 日期列只解析日期元数据，支持跨年；复合指标字符串从不拆回数字计算或重新排名。所有表格和facts与归档逐项相等。
- 只读归档，不调用 `build_daily_review`、不查询外网、不发模型请求、不生成或改写日报，不写市场库。
- 此次唯一运行期学习写入为用户要求方向的 `record-correction`，通过正式CLI写用户纠偏台账；没有写新闻台账、启动采集或付费调用。
- 上游旧日报的零双红文案、母行业占比来源差异和新高映射问题未修改生产者，只在新阅读层明确提示；不能把归档视图当严格历史回测。

## 代码
新增：
- `intelligence/services/river_daily_review.py`
- `intelligence/webapp/src/components/river/DailyReviewWorkspace.tsx`
- `intelligence/webapp/src/river/reviewTypes.ts`
- `intelligence/webapp/src/riverReview.css`
- `tests/test_river_daily_review.py`
- `intelligence/webapp/src/components/river/DailyReviewWorkspace.test.tsx`

有界修改：`intelligence/api/river_daily_routes.py`（注册新只读端点）、`intelligence/webapp/src/components/river/DailyRiverDashboard.tsx`（插入工作区、联动回调）。既有 API 与通用行情扫描／舆论保留。
备份：`.tmp/arena-river-opinion-0929/before-daily-review/`。共享文件写入前用 SHA-256 检查没有并发改动；新增文件以独占创建写入。

本地预览专用 `src/main.tsx`、`src/previewData.ts`、`preview/review-snapshots.json` 不覆盖远端生产入口；真实数据快照不导入生产 App。

## 验证（针对混合工作树的定向结果，非全仓验收）
- 后端 **106 passed in 5.96s**，含上一轮76项及新日报服务／既有日报投影测试。
  收据：`/Users/a77/.finance-runtime/test-receipts/20260929T061925Z-b4a35fa2.json`。
- 前端 **22 passed**：日报工作区10、每日视图7、历史连板3、ScanPanel2。
- 全项目 TypeScript 检查通过；改动前端 ESLint 通过；新增后端 Ruff 通过。
- 完整原前端 Vite 构建到隔离目录 `.tmp/arena-river-opinion-0929/review-web-build/`，未覆盖 `intelligence/api/static`。
- 真归档 API 冒烟：7个日期均200；每份 sections/facts 与原JSON完全相同；全部归档哈希前后相同；缺失日无回退；非法日期422。
- 浏览器桌面1440px／手机390px：行业切换、个股详情、三种矩阵、09-22新高矩阵、09-24映射缺失、日期跳转、完整日报、六轨回调和舆论状态；无页面溢出／pageerror。
- 最终单文件 `file://` 检查通过同上流程；07-06历史连板仍定位07-06；外部HTTP请求为0。

## 交付
- Arena 本地 `/home/user/time-river-preview.html`，2,017,689字节。
- Mac 同步 `.tmp/arena-river-opinion-0929/time-river-preview.html`。
- 本地验证记录 `river-upgrade/verification/review-*`；关键收据同步远端 `.tmp/arena-river-opinion-0929/verification/`。
- 使用 gzip/base64 小块传输最终HTML，避免 MCP 大文件502；组装后校验SHA-256。

## 后续
当前首批三块已落地。若继续扩展主视图，可迁移1/3/5/10日共振榜和MA5波段；先独立审计上游新高行业/题材映射，避免在展示层补口径。真实 AIHOT 来源接入与部署仍是独立事项，未在本轮执行。
