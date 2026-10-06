# 8798 原版工作台优化 — 已实现、待发布

2026-09-29。基于 `/Users/a77/finance-workspace-private` 原版 App、侧栏和组件；不是另起一套看板。没有提交、合并、替换生产静态资源或重启8798。

## 本轮完成

- 连板：上一／下一交易日、日期选择、历史截止日、最新窗口、同日复盘入口。点梯队格子过滤对应板数，点股票展示代码、首板日期、涨幅与原始题材标签；换日期清除旧筛选／明细。
- 共用时间轴：逐日阅读默认约42px／交易日，20／40／60／120日窗口可压缩总览；指数与下方梯队／六轨在同一滚动容器中，标签固定，选中日期自动显露。SVG固定显示高度，避免长画布把图表纵向拉大。
- 长河：每日复盘／板块六轨／公开消息三种阅读层次，保留原横扫、纵扫、区间、切片。与连板共享日期，公开消息沿用选中板块。
- 每日复盘直接使用既有 `DailyReviewWorkspace` 和原 daily 归档：集中度、15日行业矩阵、个股发动机、15章节；不重算原公式，不爬HTML，不把缺失值变成零。
- 研报份数、覆盖率、覆盖分位与公开消息传播分开命名；按钮明确为“同日公开消息”。没有接入真实 AIHOT 信源，因此公开消息明确显示待接入，不填模拟热度。
- 修正历史日期与迟到请求竞态、最新窗口重新锚定、切板块旧图残留、横扫旧行残留；补横扫日期可访问名称与表头scope。

## 验证（定向检查，不是全仓验收）

- Mac前端：7个测试文件 **37 passed**；TypeScript应用与Node配置检查通过；本轮17个文件中的全部TSX文件ESLint通过。
- Mac后端：11个相关测试文件 **127 passed in 5.71s**。收据 `/Users/a77/.finance-runtime/test-receipts/20260929T071413Z-b4a35fa2.json`。
- Mac隔离构建：`.tmp/arena-8798-opt/web-build/`，JS `index-CJbthfHq.js` 481.17kB，CSS `index-BR_O6gde.css` 139.34kB。不在生产static目录。
- 原版App浏览器验证：1440×1800与390×844；连板60/120日、两种密度、梯队→个股、09-23同日复盘、返回最新、09-04缺失日报不回退、六轨、横扫同步日期、纵扫、区间、同板块公开消息、同日返回连板、07-06历史窗口均通过。
- 指数／梯队／六轨选中列中心偏差约0.98–0.99px；无整页横向溢出、无页面脚本错误、无市场API错误。模型配置请求在只读预览中被有意403拒绝，不属于生产故障。
- 17个本轮改动文件本地／Mac SHA256一致。备份在 `.tmp/arena-8798-opt/before/`、`before-fix1/`、`before-fix2/`。

## 验证环境与正式服务不能混同

Arena只读验证版：原版 `App.tsx` + 本轮组件；启动时进入连板，增加“未发布”水印。它只允许市场读取，使用Mac当前源码的FastAPI TestClient读取真实DuckDB／归档／台账；原有只读纵扫仍使用POST查询。私人会话、模型凭据、问答、采集和写入均被禁止。相同查询缓存于验证环境，校验时最新行情仍为2026-09-24；没有刷新行情。

**不可把预览专用文件上传到生产：** Arena staging中的 `src/main.tsx`、`previewData.ts`、`preview.css`、`vite.config.ts`、`index.html`，以及只读桥接服务器。Mac生产main.tsx没有改动。

Mac8798复核仍使用 `index-BqIYiaO5.js` / `index-DLCJm1Ks.css`；`/api/river/daily-review`、`daily-overview`、`opinion-attention` 均404。源码已更新不等于运行中的Python已加载它们。发布必须同时处理后端加载与前端静态资源，不能只换JS。

## 发布前剩余事项

1. 取得用户对短暂停服、重启8798和发布前后端的明确确认。
2. 重查当前进程和运行参数：本轮8798监听PID92925、工作目录为主仓；`com.a77.finance-workbench` launchd任务的PID是另一个进程79816，不能直接假定该任务就是8798、不能误重启其他端口服务。
3. 再查并发源码修改、当前static哈希、活动任务；主仓为脏的detached HEAD b4a35fa2c，隔离构建含已有工作树内容，不是一个干净独立revision。不要覆盖他人的未提交修改，不要把本轮结果宣传为全仓合入通过。
4. 备份现有生产静态资源，确认目标8798的启动配置与回滚方式，然后配套发布。上线后检查三条新API、真实原版导航和历史联动。不要触发数据刷新、新闻导入、付费采集、模型调用或更改数据库。

## 文件与证据

本轮生产代码：`App.tsx`；`riverOriginal.css`；river组件 `TimelineViewport`、`OriginalDailyReview`、`RiverHome`、`RiverWorkbench`、`RiverTimeline`、`ShKline`、`ScanPanel`、`SliceDrawer`、`LimitUpDashboard`、`DailyRiverDashboard`、`DailyReviewWorkspace`。另有3个新测试文件与1个测试标签调整，共17个文件。

Arena：`original-preview/verification/browser-final.json`、`remote-frontend-final.json`、`backend-final.json`、`source-live-final.json`；截图同目录。`river-upgrade/intelligence/webapp/original-check.mjs` 为本轮浏览器回归脚本。Mac收据副本位于 `.tmp/arena-8798-opt/verification/`。

之前日报服务与AIHOT适配的背景见 `docs/handoffs/2026-09-29-daily-review-dashboard-implementation.md`。上一套独立设计的离线HTML保留为旧产物，不是本轮原版工作台的入口。

## 决策与经验

| 选择 | 否决 | 原因 |
|---|---|---|
| 原App与原组件增量优化 | 新侧栏／第二套产品入口 | 用户明确要求原8798 |
| 可读列宽与横向滚动，另保留压缩模式 | 所有长窗口都挤进一屏 | 120日仍需读清单日与联动股票 |
| 复用归档服务与原指标 | 通用报价指标替代日报 | 原数据口径与分组已经存在 |
| 真实API源码的只读隔离验证 | 直接换生产前端 | 8798当前缺少三个新API |
| 明确待接入与缺口 | 研报数冒充新闻热度 | 没有被授权或配置真实消息导入 |

浏览器断言必须等待业务状态，而不是只等networkidle；跨MCP只读验证有额外延迟，5秒默认断言超时不代表页面故障。Chromium将无scope的部分th识别成cell，而JSDOM测试可能仍识别为columnheader；本轮已在横扫表头补scope="col"并在真实浏览器验证。项目特定浏览器脚本及单元测试已留存；没有把绑定私有MCP桥的预览服务器推广成跨项目工具，也没有修改共享harness仓。
