# eb4 候选独立回放与发布边界

## 身份与结论

- 验收对象：`eb4ec08f0680f9ba8cdaf5f3e8a95be34861b12a`。
- 执行树：`/Users/a77/fwp-wt-workbench-release-ready-0924`，验收及封存时干净，分支 `test/workbench-release-eb4-0924`。后续交接文档提交不是新的运行时验收对象。
- 解释器：主树 `.venv-workbench/bin/python`，Python 3.12.13；测试收据算法的依赖指纹 `3328bed61f3e21ea`。HTTP health 自带的完整依赖指纹另存原件，不混用两套算法。
- 发布结论：**HOLD**。自然入口与定向边界通过，不等于数据准入通过。owner 全仓 Python 在本次封存时仍无完成收据。
- 证据根：`/Users/a77/.finance-runtime/reviews/workbench-release-20260924-independent/`；本候选完整旁路证据在 `eb4-live/`，入口是 `sealed-evidence.json`。

## 发现顺序

1. `2ddd43f8` 只保护当日名称。历史 `NULL` 经 `bool()` 变成断板，空字符串却可能变成普通股票。原始九例为 6F/3P，留在 `history-name-2ddd-red-v2.xml`，Gitea #900 评论 6701/6703。
2. 在独立树补出四消费入口的 28 个异常用例及四个不误拦控制，旧代码 28F/4P，均为预期未抛异常，无 collection error。覆盖 daily、recovery、high、core-leader，并对六张已有派生表做异常前后等值检查。
3. 自有最小提案先通过统计/恢复定向 137P。随后 owner 评论 6705 冻结等价修复 eb4，本地提案以 `96adae797c2316506e8d2c1b11d2b86fb269c486` 归档，提交说明明确 superseded，不推送或合入第二套运行时。137P 只属于该提案，不能移签。
4. QA 树切到干净 eb4，原始九例加归档测试文件原样回放，共 118P。测试来源和运行时代码分别绑定，不能把测试来源 SHA 冒充运行时 SHA。
5. 复用仓内 `run_extraction_mutations.py` 的检查与运行器，在独占临时树做名称、sidecar、启动恢复、传输、交付状态变异。每次确认唯一锚点、可编译、真实断言失败而非收集错误、逐字节恢复。
6. 沿用 R7 的只读沙箱、同用户/画像/问题与原超时，重新执行 eb4 的真实 RAG 和 Workbench conversation API。全部自有进程已结束，临时变异树已移除。

## 定向结果

| 边界 | 结果 | 收据 |
| --- | --- | --- |
| 名称与既有统计旁路回放 | 118P | `history-name-eb4-green.xml` |
| 历史未知误转布尔 | 28F，恢复 28P | `eb4-live/history-mutations/results.json` |
| 新高吞身份异常 | 7F，恢复 28P | 同上 |
| 不消费的历史被扩大拦截 | 4F，恢复 4P；最终恢复 109P | 同上 |
| sidecar 用户/Episode 隔离 | 2 项变异，最终恢复 2P | `eb4-live/sidecar-mutations/results.json` |
| RAG 启动恢复 | 16 项变异，最终恢复 33P | `eb4-live/startup-mutations/results.json` |
| RAG 传输 | 12 项变异，最终恢复 83P | `eb4-live/transport-mutations/results.json` |
| 交付状态接线 | 2 项变异，分别 1F/2F，最终恢复 3P | `eb4-live/delivery-status-mutations/results.json` |

共 35 项变异。不同回放有重复用例，不能相加当作全仓通过数量；它们也不是金融真实数据覆盖率证明。

## 自然入口证据

`eb4-live/live-rag.json`：真实 BGE-m3 冷启动 46.958s；两次非缓存 hybrid 查询分别 2.175s、1.156s，各 6 条 fresh；模型加载次数始终 1，关闭后 active=0。CLI 必需协议检查在原 5 秒预算内完成。旧 CLI 缺可选 `--receipt` 等参数，telemetry 如实保留 `legacy_cli_missing_receipt`；索引 `source_dirty=true`，没有重建或降低新鲜度规则。

`eb4-live/live-workbench-smoke.json`：`run_20260924_033645_080673`，模型 zhipu/glm-5.3-flash，conversation API 完成，语义检查通过，内容降级/密钥扫描/公开泄漏均为 0。

`eb4-live/natural-acceptance-corroboration.json` 进一步核对同用户、同问题、同 conversation/run/Episode，20 个事件序列连续，未对账副作用为 0，RAG served 从 1 增至 7。不能仅依赖 smoke 中为空的 retrieval 摘要字段。

readiness 前后均 **503**，唯一 critical 是 `market_data_consistency`。`acceptance-summary.json` 因而明确 `passed=false`。相关判官不等于独立金融质量审查；一次运行不用于快慢、质量提升或策略有效性的结论。

## 版本与负证据校正

- `final-candidate/full-receipts/gate-ZXv7BpbL/pytest.json` 本次直接读取为 **2ddd**，15060P/85S/2X，15147 collected；解释器、完整目标、零基座漂移校验通过。它不是 eb4 的收据，也不能沿用旧摘要对该路径的 62d 归属。
- eb4 前端六项均 exit 0，dirty=false、identity_stable=true；registry 五项 exit 0。正式目录是 owner 的 `workbench-release-20260924/history-candidate/`。封存时 `owner_python_exit=null`。
- 旧摘要称 0e66b 状态接线仍未进入候选，已由 blob 比较纠正：两个文件已随 2ddd 纳入 eb4，内容相同。
- `delivery-status-eb4.xml` 的 1F/2P 来自早期夹具把 business_status 与 research_status 混淆，不是运行时回归。提交版测试明确研究 complete 时，交付不完整仍把业务降成 partial。
- `delivery-status-eb4-0e66.xml` 是外置测试从主树 cwd 启动造成的收集错误，不是有效红例；正确 cwd 的 `delivery-status-eb4-0e66-correct-cwd.xml` 为 3P。所有原件保留，封存清单单列其用途。
- 本审查者写过未选用的并行实现，因此不宣称盲审；选用的 eb4 源码由 owner 提交。

## 方案取舍

| 选择 | 被否方案 | 理由 |
| --- | --- | --- |
| 历史身份用未知态保留，到消费点拒绝 | `bool(NULL)` 或默认普通名称 | 缺失不是否定，也不等于普通股票 |
| 保留有效断板的短路行为 | 扫描窗口内任意坏名都阻塞 | 不消费的历史不应扩大阻塞 |
| 沿用 owner 的 eb4 | 合入本地等价实现 | 避免两条发布线与重复修复 |
| 数据准入独立判定 | 用自然答案成功盖过 readiness | 文本能生成不代表生产事实完整 |
| 原失败单独留证 | 覆盖旧 XML 只保留绿结果 | 区分真缺陷、夹具错误、执行环境错误 |

名称格式检查仅检出空白和控制字符，不认证历史名称来源。所查 HiThink 官方 commit `3bca7805a4127ece8d81961917e740d2effac6ec` 的 meta list/search 是当前代码表，historical K 线没有名称字段；这些端点不能认证 09-22 全市场名称，不外推为所有可能来源都不存在。问财样本 HTTP 401 保留在 `name-source-iwencai-auth-boundary.json`，不解释为历史数据不存在。未重新开启已停抓的复盘会。

## 接续与工具归位

正式 staging、数据恢复、三道数据门、换库、合并和部署仍归发布 owner。需要继续闭合日期化名称、四缺行、停牌分区、零成交身份和派生字段，并核验两只现金事件裁决的正式采纳。没有这些证据，不发布旧副本，不用当前名称回标历史。

本轮复用了已提交的变异运行器、自然入口 smoke、前端门；扩展测试与变异定义可从归档提交 96adae797 重放。固定候选编排脚本及其哈希留在持久证据根，不把它们冒充通用发布工具，也未修改共享 harness。三态/消费边界的方法论另存 agent-memory `consumed-evidence-validation-boundary.md`。

生产 DB 在完整旁路期间 inode=216161353、size=3855626240、mtime_ns=1790168645608937291，启动器前后哈希相同。所有自有控制器、sidecar、worker 已退出；不停止 owner 正在执行的全仓门。后续仅文档提交不会使上述收据自动改签新 HEAD。
