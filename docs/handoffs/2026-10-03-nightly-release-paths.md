# 固定发布快照的夜跑落盘根修补

## 背景与发现顺序

2026-10-03 发布预检以冻结 UI `1be7500c` 和已安装的 S7/finalize 入口为输入。计划让 8792 和夜跑共同使用最终 main 快照及其独立 venv，数据根继续保留。只改代码根仍有两项实阻碍：

1. `run_review_sync.py` 从自身 `SKILL_DIR` 写 `state/runlog.md` 与 `quality-日期.json`；runlog 受 Git 跟踪。第一次夜跑会写脏发布快照。
2. 同步后调用的 `export_increment.py` 默认将备份写到代码根 `db/snapshots`，默认读库也没有跟随双根配置。generation 段已显式传数据根，18:30 sync 没有这些输出参数。

随后核对 local 计划的解释器依赖：开发锁没有 AkShare，指数/申万同步却在当前解释器直接导入它；日报图依赖 matplotlib，缺少时会返回 None 而静默少图。总控负责可选夜跑锁、独立环境验证及日期敏感的 credits 测试 fixture 修复，本实现者仅修改落盘根、相关测试与文档。

## 选择与被否方案

| 方案 | 评价 | 结果 |
|---|---|---|
| 复用 FINANCE_DATA_ROOT → FINANCE_WS → ROOT | 已存在的双根合同；保留手动单树执行与旧目录结构 | 采用：日志、质检结果、备份默认目录统一回数据根 |
| 新增多个日志/质检路径变量 | 把同一数据根拆成平行配置，容易再次漏切 | 不采用 |
| 把快照中的 state 软链到数据树，或忽略 Git dirty | 绕过发布身份问题，不能证明源码未被改变 | 不采用 |
| 复制现有共享 venv | 现有 mootdx 要求 httpx<0.26，已经导致共享环境偏离0.28.1锁 | 不采用；不修改共享环境 |
| 修改 dev/consumer 锁加入所有抓取库 | 会扩大消费侧基线，混淆开发与夜跑依赖 | 不采用；总控新增可选 requirements-nightly-macos.lock |

## 实现

同步入口将既有 `_DATA_ROOT` 路径初始化提前，`STATE_DIR`、`RUNLOG` 与跨日 quality JSON 使用它；报价封存与桥缺口证据继续复用这个根。导出默认数据库优先读 `MARKET_FEATURE_STORE_DB`，否则使用数据根数据库；备份默认使用数据根 `db/snapshots`。`--db`、`--out-root` 和 `DUCKDB_SNAPSHOT_OUT_ROOT` 继续覆盖默认值。local 步骤、日期、闸门及备份失败只告警的处置不变。

已查生成段的日报/矩阵/队列/用户运行态、L2 缓存/产物和同花顺中间文件的落点；它们已有数据根、显式参数或临时目录合同。本补丁不改变已部署 shell、外部 staged wrapper 或知识库接收器。

仍须准确描述既有边界：S7 失败通知执行 `$DATA_ROOT/scripts/notify_ops.py`；额外 KB receive shell 用 PATH python3 执行知识库脚本。这两项不属于“所有代码/解释器都已固定新快照”的证明。外部 staged wrapper 也不因 FINANCE_S7_ROOT 改变而自动获得 daily-full 整段新版锁编排。详细发布审查在仓外 `deployment-plan-review.md`。

## 验证

新增 12 项行为回归：临时代码副本执行真实 main，外部子同步在 subprocess 边界截断；实际运行导出 CLI 读取临时小 DuckDB，检查 tar manifest、覆盖参数和代码副本逐字节不变。覆盖双变量优先级、FINANCE_WS 后备、无配置旧行为、质量门失败落盘及显式库/输出覆盖。

红→绿证据位于 `/Users/a77/.finance-runtime/reviews/workspace-closeout-1003/`：`nightly-paths-red-state.log`、`nightly-paths-red-export.log`、`nightly-paths-red-export-input.log`，各对应独立真实失败；修复后相关 17 文件 **306 passed**，日志 `nightly-paths-targeted.log`，ruff 通过。未运行生产同步、联网抓取、真实模型或本分支全量测试。这是改动工作树定向测试，不冒充最终集成 SHA 的全量收据。

总控的隔离环境验证：`nightly-release-venv` 安装可选 `requirements-nightly-macos.lock`，pip check 通过、doctor ready/零 drift，保留 httpx0.28.1。禁止网络沙箱里成功导入 AkShare1.18.64、matplotlib3.11.0及必需依赖，真实图函数生成64,936字节合成PNG。证据同目录 `nightly-doctor.json`、`nightly-pip-check.log`、`nightly-env-probe/report.json`。Mac 的 mini-racer 分发包应 import `py_mini_racer`；探针初次拼错模块名的失败原件保留。

安装合同：新建独立 CPython3.12.13 venv 后使用 `python -m pip install -r requirements-nightly-macos.lock`；该锁同时引用/约束 dev 锁，绝不能安装回 Pi/共享 venv。正式发布还需检查实际 python_prefix，doctor 的解释器解析可能因 override 或缺本树环境而回退共享环境。

## 下一步与范围

由总控把本补丁、可选锁和 credits 测试时钟修复整合进最终候选，补独立审查并重跑精确提交完整门禁，再创建 final main 快照和执行发布。此文不证明最终 SHA 已全量通过、服务已切换、夜跑已成功。8792 启动会恢复持久 queued/running runs 并可能预热 RAG；上线前必须检查所有用户待恢复任务，任何烟测使用隔离部署账本。

本轮没有新增通用运维工具：路径反例已成为正式回归，复用既有启动/环境工具；仓外报告承担此次部署判断，不再创造一套平行发布入口。
