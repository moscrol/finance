# 09-21 两条历史缺行的受保护准备与 09-22 原件复核

## 背景与授权

承接 #913、`2026-09-25-dated-recovery-forward.md` 及 authorized-data-08/09。已有恢复、合并、部署授权继续有效，不重问、不增加真实模型额度；授权不豁免数据与发布门。声明范围未经官方历史全集认证仍是已接受的证据边界，不另设授权门。

独立树 `~/fwp-wt-dated-recovery-forward-0925`。先将 main `72402839075e3eefdee7b185db015a0545096b22` 合入恢复分支，组合提交 `66156a9fc`；实现提交及受测版本为 `b17adc06007dbbc4cfe7b8de1f18423073c13a62`。本快照及 inflight 的文档后继不继承该版本的全量收据。

本轮证据根：`~/.finance-runtime/reviews/agent-foundation-0924/deploy/authorized-data-10/`。下文证据文件名均相对此目录。

## 按发现顺序

1. 原 quote preparation 会拒绝已有交易日，不能直接用它补 09-21 两行。保留该默认行为，在同一个 `scripts/recover_local_review.py` 中增加 `--candidate-manifest` 与 `--candidate-manifest-sha256`，且强制 `--prepare-dir`。没有新增独立写库入口。
2. `scripts/historical_candidate_recovery.py` 重建固定的 `CANDIDATE_20260921`，核对已封存的输入及候选指纹。还要求目标整日的所有 canonical 列符合固定前像，已有行的八个数值字段与候选一致，缺行集合恰为 `600301.SH`、`600825.SH`。只向既有事务写入这两行，原 5551 行包括名称、换手率、来源和更新时间全部保留。
3. 初次定向运行 59P/36 个 setup error，原因是 JSON 把 provenance 时间变成字符串。补严格反序列化后相关四组测试 183P，初次失败日志保留在 `initial-targeted-failure.log`。新用例覆盖全部列的前像、数值冲突、日期与身份、重复执行、混用参数及不可发布状态。
4. 重新执行原 09-21 校验器的验证前缀，核验主 manifest 中 278 份原件，重建候选与旧 `candidate-final.json` 完全一致。固定解释器没有可选 akshare 包，首个审计适配脚本失败原件保留；v2 用 AST 仅移除可选的当前新浪名称报告及其 import，未移除原件、历史 witness、raw/stored 或候选验证，也未改依赖环境。详见 `capture_candidate_inputs_v2.py`、`data-preflight.json`。
5. 在断网沙箱内通过真实父子入口，从 03/final-replay 封存输入派生全新副本。原 5551 行逐字段回读一致，两行新增成功；其他 43 张事实表的行指纹及其他股票交易日不变。重复执行因前像变化拒绝。父子均返回 rc2、`ok=false`、不发布；两行换手率为 NULL，没有填零或外推。
6. 对新副本运行四日只读 QA，仍为 84 FAIL / 8 PASS / 4 WARN / 6 INFO，各日 21 FAIL。完整派生与 same-day/cross-day/L2 发布条件未完成。补行并没有解除这些门。
7. 扩查本地封存目录，发现 09-22 三股历史 raw 及两份 IPO 页面。用已安装 AKShare 的纯 JS 解码器常量，在 Node 隔离上下文重新解码，不安装包、不外呼；HTML 用标准解析器按 GB18030 解码。原始哈希、旧解析收据及重解码结果一致。见 `historical-0922-witness-audit.json`。
8. 固定 b17adc0 和已建好的地图后执行所有工程叶子。测试期间 main 又合入 #933，故精确零漂移收据拒收，未追签新组合。

## 09-22 新证据的准确边界

| 股票 | 已复核的原件事实 | 尚不能得出的结论 |
| --- | --- | --- |
| 300803.SZ | 新浪 09-22 raw 明确 `prevclose=56.86`；同花顺记录每股送转比例 0.45；两源 OHLC、量一致，金额差约 0.16 元 | 尚未实现并验收非现金行动的日期化修复契约，不复用 09-21 复牌例外 |
| 301686.SZ | 新浪 raw 明确 `prevclose=55.28`；IPO 页面列上市日 2026-09-22、发行价 55.28；OHLC、量一致，金额差约 0.40 元 | 不是凭缺前 bar 推断 IPO；供应商页面仍不等于交易所公告或同日显示名称证明 |
| 920229.BJ | IPO 页面列上市日 2026-09-22、发行价 15.67；历史 raw 的 OHLC、量与同花顺一致，金额差约 0.08 元 | 历史 raw 没有 `prevclose`；未把发行价直接代入参考前收 |

新浪 `postVol/postAmt` 字段另行保留。本次量本来已与同花顺一致，不能再把盘后字段加一次。以上三股未在本轮写入数据库，不能把“找到原件”写成“恢复完成”。

## 方案取舍

| 方案 | 评价 | 结果 |
| --- | --- | --- |
| 放宽普通 quote 模式，覆盖已有日期 | 会扩大所有日期的覆盖权限，并可能改掉历史名称或来源 | 否 |
| 用旧 09-11 专用修复 spec | 日期、名单和例外不同 | 否 |
| 固定候选指纹、整日前像及两条复牌身份，只准备新副本 | 缩小写入面，已有数据可逐字段证明保留，复用原锁和发布拒绝路径 | 采用 |
| 用缺前 bar 或 IPO 发行价直接补 09-22 | 缺 bar 不是 IPO 证明，发行价也不是已捕获的当日参考字段 | 否；先补仲裁契约 |
| 把成功的输入副本手工替换生产或 03 原件 | 跳过派生与发布门，并破坏来源链 | 否 |
| 新 main 前移后沿用绿收据 | #933 包含运行码，受测组合已经不同 | 否 |

## 验证与收据

- Python 固定为 `~/fwp-wt-agent-foundation-closeout/.venv-workbench/bin/python`，3.12.13，依赖指纹 `66726d345bf37ce5`。
- 全量 Python：16321P / 0F / 0E / 75S / 2X，收集 16398；未缩收集面。收据 `python/gate-GE6ExhhH/pytest.json`。
- 前端：lint/typecheck/build 通过，123P；E2E 34P/2S。两测试服务写隔离账本，未混入生产启动账本。
- registry 六项、全仓 Ruff、doctor、workspace smoke、地图查询通过。工作树和地图指纹在各叶子前后稳定。
- `receipt-check.log`：版本、解释器、依赖、完整收集、干净树均通过；仅因 main 合入 #933、基座落后 1 张合并而拒收，上限 0，exit1。
- 观察 main `12d91dc733e1a29ceb54668fb934513bd10da4e9`，未合入 #913。`acceptance-result.json` 分开记录工程与数据结果。
- `offline-gap-replay-result.json`、正负例真实入口日志、`prepared-gap-qa-summary.json` 分别证明补行、重复拒绝和仍未通过的数据门。
- 生产只读采样：runtime `3b7e473575b0ff2dea3c1088ba7b5e330e95c8e4`，health200/readiness503，整库哈希与前次采样一致。未开生产 DuckDB 连接，未生产写入、换库、部署或模型调用；不能扩张成对所有中间时刻的证明。

## 来源链与接续

原件仍是 `authorized-data-03/final-replay/isolated-inputs/market_feature_store.duckdb.staging`，SHA256 `bb68713763af50c2eb701e0160384dbcd0d05d9be3295ffbeeccaa8f47317cba`。

本轮已准备子副本是 `authorized-data-10/offline-positive/prepared/market_feature_store.duckdb.staging`，SHA256 `d0e46e4c128890d078295f610a66272619fdc211d52b21599faf87acbbdbcb78`。它有来源链但不可发布；后续只能经既有受保护 owner 在全新 staging 中推进，不能手工晋升，也不能替换 03 原件。08 副本仍只作回归夹具。

最新待办使用 `remaining-evidence-packet-v3.json`，不覆盖 v2。80/403 个板块缺 113 个冻结成员身份仍未解决，禁止凭数量或当前名单填补，禁止重试/绕过 HTTP401。待这些证据及所有数据门闭合，再固定实际合入组合与 main 窗口完整重验；不再为追逐移动 main 转签收据。

日期专用保护已入仓，原件审计适配只留在证据目录，不创建第二套生产写入器。本轮未改变 Agent 能力图或通用 Harness。一次地图刷新误落默认检出树的 ignored 缓存，后续正确绑定独立树；没有据此宣称默认树所有缓存未动，执行边界详见 `execution-notes.json`。
