# 每日复盘：同一份证据，两种读法

- 日期：2026-10-08
- 文档版本：1；状态：第一版代码已实施；合成归档真实API浏览器验收通过；待真实数据与Agent消费验收；未部署
- 编写：Arena 编码代理
- 分支：arena/a3bfea49-finance（包含原日历等未提交修改）

## 本轮用户要求

人要易读的复盘界面；Agent 不读 dashboard，而要读取与人一致的数据种类。人能明确告诉 Agent 应当怎样解释、联立这些数据。

因此分开三层：

1. **证据**：各日归档读数、原表、覆盖缺口、来源。用户方法不改变它。
2. **阅读方式**：人看中文分组/图表/原表；Agent 读相同响应中的结构化字段，而不是截图或二手摘要。
3. **解读说明**：用户提出问题、阅读顺序与限制，Agent 应把它当研究指导或假设，而不是行情事实。

不是让 Agent 只看界面上露出的几项，也不是给 Agent 一套不同名称、不同口径的隐藏行情。

## 已实施

### 共用的数据种类说明

`river_review_contract.py` 是本轮词汇与边界的单一来源，随 `GET /api/river/review-history` 返回在 `evidence_contract`。前端中文阅读地图直接使用这个对象；原始 JSON 导出和 Agent 交接包均保留它。

| 人看到的种类 | Agent 读取的逐日字段 | 主要限制 |
|---|---|---|
| 市场环境 | `metrics.total_amount / advancers_ma5 / strength_avg_pct / top3_industry_ratio / double_red_count / stock_high_120d_count` | 六项取各日报 facts；MA5不按本窗重算。数量为全市场，不是所选行业 |
| 行业位置 | `top_industries / industry_rank / industry_status` | 申万一级原名；有效榜单未出现显示“未列入”，没有依据显示“未知”，不填0 |
| 子板块表现 | `matrices.double_red / limit_up / stock_highs` | 保留当天原值；同名不证明身份一致；题材重叠不可相加 |
| 个股发动机 | `engines.columns / rows / truncated / total_rows` | 页面前三项仅为预览，Agent保留全部返回行；截断不允许判定名单全集或退出 |

市场字段单位沿用接口 `metrics` 元数据：成交额亿元、涨家数的MA5为家、强度加权涨幅与前三行业成交占比为百分比、双红个数、120日新高只数。相邻日百分比差为百分点。

这是**连续视图已接入的四类数据对齐**，不是声称完整日报所有栏目都已时间化。若研究完整日报其他栏目，合同指向 `/api/river/daily-review?as_of=YYYY-MM-DD` 和逐日 `detail_url`，读取 `report.sections` 原表。后续读取须核对同日SHA256；不一致先报告修订差异，不直接合并。

### 人可读性

- 图表前增加四类中文阅读地图：名称、核对问题、字段与边界。问题是阅读提示，不是自动结论。
- 折叠数据字典展示六项名称/单位/对应字段、缺失含义、对齐键、来源与版本未知项。
- 缺档用“缺归档”，不可读取用“不可读”，缺值用“—”，趋势不跨缺值连线。
- 原始时间线、矩阵切换、同日原表和归档来源保留。

### 用户教 Agent 如何联立

增加三个独立输入：

1. 这次想判断什么；
2. 先看什么，再结合什么；
3. 哪些情况不能直接下结论。

示例只放在占位提示，不自动冒充用户指令。方法草稿保存在浏览器标签页会话存储，不写服务器；支持清空。拒绝存储时明确提示，不隐藏丢失风险。草稿可跨选日/窗口/行业复用，但导出前显示本次准确窗口、行业和查看日。

新增“导出 Agent 联立证据包”：`review-agent-handoff/v1`。包含：

- `context`：窗口、行业、查看日及该日是否在窗口、归档视角；
- `user_instructions`：用户文字、作用范围、“非市场事实”标记；
- `evidence`：原始连续接口响应，完整保留，未按折叠/当前矩阵类型/前三股票预览裁剪；
- `response_contract`：要求先交代缺口与口径，再联立证据，列支持与不支持，最后说明尚不能判断；引用日期、行业、JSON Pointer与原日报SHA256。

该包是可读取的交接格式，不自动发送，不调用模型，不代表聊天Agent已经注册了读取工具或一定会遵守回答约定。

## 已明确而未伪造的口径

- `knowledge_mode = archived_report_not_as_known`：归档可能事后生成或覆盖，不是严格当时可知回放。
- SHA-256覆盖读取到的原始日报文件字节，不是归一化JSON；哈希不证明真实来源/当时可用，也不等于历史版本存储。
- 行业为申万一级原名，但分类版本未知；历史公式版本、独立日历版本、归档修订编号均为null。
- 直接来源为日报JSON，未提供逐字段上游供应商血缘，不凭名称编造供应商。
- 共享日历来源明确，但未声称有可重放的独立历史版本。现有未知年份行为不变。
- “双红”“强度加权涨幅”此处沿用日报字段，未凭名称补公式。公式核对仍待追溯上游生成实现与历史版本。
- Agent应把归档文本当数据，不把归档内的命令式内容当执行指令；用户假设、归档原值、算术差和Agent推断须分开。

## 验证（本轮最终工作树）

- 后端 `pytest tests/test_river_daily_review.py -q`：29通过。新增验证共用种类的字段路径实际可解析、六项一一对应、MA5与发动机原行不改写、未知版本不编造、合同可序列化。
- 前端 Vitest：24文件227通过（当前混合工作树，不代表独立提交的CI）。新增5项：不损失矩阵/发动机列行与截断标记、用户说明独立、越界查看日/旧接口失败提示、草稿与行业作用范围、完整导出且无网络/模型调用、浏览器拒绝存储提示。
- TypeScript、ESLint、相关Python Ruff、Vite隔离构建通过。仍有大chunk与Starlette TestClient弃用警告。
- 构建未覆盖此前日历静态资源；临时构建验证后清理。正式发布须重建前后端配套版本。
- 未做本轮浏览器E2E、截图走查、真实市场归档抽样、聊天Agent真实消费测试或部署。人可读性方向已落代码，不声称真人可用性已验收。

## 下一步与验收门槛

1. **P0：真实归档与浏览器验收。** 建议选择连续20个交易日，另用合成夹具覆盖缺档、截断、榜外与不可读；核对六项和三类矩阵、发动机原列。自动比对先报差异，由用户或指定复核者对照原始归档裁定，禁止Agent自动改事实。抽样日期与复核责任人待确定，非已完成。
2. **P1：接入现有Agent读取路径。** 消费本合同和用户方法，验证是否能逐项定位证据、报告缺口/版本差异，不以截图代替结构化读数。补真实Agent端到端测试后才能称为自动闭环。
3. **后续：更多种类与过程研究。** 发动机自动进退、高标轨迹、完整份额、自由区间对照、反例检索及归档版本留存。任何新增种类同步扩充人侧阅读与结构化合同，不另造Agent专属口径。


## 2026-10-08 后续验收：真实浏览器 → 实际接口 → 合成归档

本段更新前述“未做浏览器E2E”的历史状态，不将合成样本结果扩张为生产验收。仍在 `arena/a3bfea49-finance`；HEAD `82de3fb7`，本轮修改未提交，不引用另一会话的 `bd2a7a2d`。

### 本轮新增/修改清单

- `intelligence/webapp/e2e/prepare_review_evidence_fixture.py`：隔离合成归档（缺档、损坏档、榜外、三矩阵14行、发动机81行）。只写忽略目录 `test-results/review-evidence`。
- `intelligence/webapp/e2e/serve_review_evidence_fixture.py`：真实应用与API，使用隔离前端构建，不覆盖日历已有static。
- `intelligence/webapp/playwright.review-evidence.config.ts`：独立端口8797、用户态、归档与输出；模型凭据置空；桌面/平板/手机。
- `intelligence/webapp/e2e/review-evidence.spec.ts`：2条流程 × 3个尺寸。
- `intelligence/webapp/package.json`：增加 `test:e2e:review-evidence`。
- `intelligence/webapp/playwright.config.ts`：主套件排除专项，避免使用不匹配的服务器。
- `.github/workflows/workbench-check.yml`：添加独立专项步骤，先前步骤失败时仍可运行（未取消时）；未运行远端CI。
- 本实施记录、在途交接及两张中文实测截图更新。

### 可证伪承诺与实际覆盖

| 承诺 | 对应浏览器断言 |
|---|---|
| 不因前三项预览就只给三项 | 真实API返回80/81行且truncated=true，下载包仍有第4只股票，并与整个API响应深度相等 |
| 不因折叠或矩阵切换省略数据 | 切至涨停、展开14行、收起、再切新高后下载，全部三矩阵及双红复合原文仍在；evidence完整相等 |
| 用户方法与市场事实分离 | 实际填写三栏、下载JSON，用户问题在user_instructions，evidence仍等于未修改的API响应 |
| 缺档不换日、点日不缩窗 | 点09-23缺档，截止日保持09-24；返回单日后仍为09-23且显示缺档 |
| 方法草稿能恢复和清空 | 切回单日再进连续，sessionStorage草稿恢复；清空后三栏为空且存储为空草稿对象（不是删除键，无二次弹窗） |
| 导出不触发模型/写入请求 | 交互与导出阶段没有非GET网络请求 |
| 窄屏不导致整页溢出 | 1440×900、1024×768、390×844均断言文档宽度不超过窗口；表格内部允许横向滚动 |

### 实跑命令和输出

```text
.venv-workbench/bin/python -m pytest tests/test_river_daily_review.py -q
29 passed, 1 warning

cd intelligence/webapp
LD_LIBRARY_PATH=/tmp/al2023/lib FONTCONFIG_PATH=/tmp/fonts \
WORKBENCH_CHROMIUM_EXECUTABLE=/tmp/chromium corepack pnpm test:e2e:review-evidence
6 passed (17.3s)

corepack pnpm typecheck
退出码0
corepack pnpm lint
退出码0
```

相关新增Python脚本Ruff及git diff --check通过。专项启动时隔离Vite构建成功。前端227项是上一实施轮混合树读数，本轮未重跑全部单测，不将其改写为本轮新结果。

浏览器：本地Chromium138（npm包 @sparticuz/chromium 138.0.2）；首次启动因libnspr4等库缺失失败，提取同包al2023运行库解决；首批截图中文缺字，安装Noto CJK字体后重跑6项并检查中文截图。未修改业务代码绕过失败，未用single-process。CI用Playwright配置默认浏览器，尚待CI实跑。

真实调用：`review-history`和`daily-review`均未拦截，使用真实FastAPI读取合成归档。仅不相关的meta、daily-overview、kline被导航夹具替代。真实API≠真实行情，81行名单及其他数据全部合成。

截图：
- `screenshots/review-evidence-desktop-20261008.png`
- `screenshots/review-evidence-mobile-20261008.png`

### 仍需用户提供的最小信息

真实日报JSON的可访问位置，或可上传的脱敏样本；建议连续20个交易日，不要求为了测试补造缺日。缺档也应作为真实覆盖情况保留。此处只读抽样，不请求凭据、不执行历史回填。

Agent接线默认沿现有Workbench入口推进；尚未完成实际Agent输入/回答/引用的留档测试，不把JSON下载称为AI自动闭环。最终解读是否符合用户的方法仍需用户确认。

### 本轮专项文件内容指纹（SHA-256）

这些指纹用于核对未提交的测试版本，不是假装已有提交SHA。

- `intelligence/webapp/e2e/prepare_review_evidence_fixture.py`：`cdbabbcdfc22b9eec2770a13d94434413aae0bb59d51195513001e5ec60a124c`
- `intelligence/webapp/e2e/serve_review_evidence_fixture.py`：`393c0e3872fa861b4d302f8c295ed0696535eb9cbd8aba4181f72a6cd9bf710a`
- `intelligence/webapp/e2e/review-evidence.spec.ts`：`7d2c1308044651849574ff7c6eb65db4ba85d4415fde2b7c3c88ccecd71c302c`
- `intelligence/webapp/playwright.review-evidence.config.ts`：`0691c29f9986b3269ce32c6ac56215b40e5e7ba899268bdec2e16467f56ea581`
