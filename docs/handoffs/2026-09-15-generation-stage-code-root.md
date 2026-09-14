# #50：日报生成代码根与持久化根分离

## 冻结对象与状态

- 分支 `fix/generation-stage-code-root`，开发树 `/Users/a77/fwp-wt-generation-stage-code-root`。
- 基线 `gitea/main@1fef3d276d0e251158803fc09d5a81e60d79241b`（2026-09-15 再 fetch 未变）。
- 包含计划修复 `4fbc8c42`、交接 `07d42891`、第一版启动修复 `2f82d4d3`。
- 本轮完整代码提交 **`0f6c28101b92d654338e705c357778cf1d818a85`**。
- 干净 detached 验收树 `/Users/a77/fwp-wt-generation-root-validation-0f6c2810`。检查前后 tracked 状态干净；前端构建有 ignored 产物。
- 未 push、合并、部署；未登录/请求复盘会，未生产回填、补跑或改资金口径。接线作者验收通过，不等于生产日报恢复。

## 发现顺序与方案取舍

1. 计划一致并不保证运行版本一致。原 `cd "$WORKSPACE"; python -m intelligence.cli daily` 会先加载数据检出树的包，甚至越过 `PYTHONPATH=CODE_ROOT`。
2. 第一版 `2f82d4d3` 添加 `-P`、安全搜索环境和 import 探针；夹具只伪造 import 路径并断言 argv。随后确认：子步骤仍用相对脚本，`__file__` 又同时承担代码根与输出根，第一版不能独立完成 #50。
3. 改为代码根绝对路径的薄启动器 `scripts/run_daily_generation.py`。验证根和实际 import 后，仍调用原 `intelligence.cli daily`，不另造工作流。缺根/包、关键包文件软链逃出根、写入根指入代码树均拒绝。
4. `daily_review` 子步骤使用本进程解释器、`-P`、固定 `PYTHONPATH`；直接脚本用代码根绝对路径，cwd 保持数据根。`runner` 新增可选 `env`，其他调用方默认不变。
5. 报告显式传 output/chart；导出显式传 DB/snapshot 根。主题队列、HTML、策略矩阵、workbench/cockpit 的数据路径改用既有 `intelligence.paths`。策略一临时行从全局 `/tmp` 改到数据 exports。报告指定 output 后不再额外创建代码树 exports。
6. 生成段安全搜索环境不扩散给独立 L2。生成门放在 L2 与同步守卫之后；最终门和方法飞轮的顺序不变。收尾通知、接收包装器和知识库保鲜检查也改取代码根文件。

| 方案 | 取舍 / 结果 |
|---|---|
| 只设置 PYTHONPATH | 否：裸 `-m` 仍把 cwd 放首位，已有真实反例 |
| 只加 -P 与 import 路径断言 | 否：不改变相对脚本的执行文件；只能证明外层 |
| 全流程 cd 到代码根 | 否：历史相对数据参数、脚本默认输出会漂；最终保留数据 cwd |
| scripts 全部改 `-m scripts.*` | 否：scripts 是 namespace package；采用绝对脚本文件，缺文件直接失败 |
| 重写 daily 或新增另一条生产链 | 否：启动器只管装载，原计划/门/副作用仍由既有 daily 执行 |
| 把所有用户态迁入 DATA_ROOT | 否：会切断既有外置用户大脑；显式外置根保留，未配置才用数据根缺省 |
| 全局安全搜索环境 | 否：会扩散到独立 L2/运维步骤；只给生成及其孩子 |

## 持久化合同

- `FINANCE_DATA_ROOT` 规范化后成为 `FINANCE_WS` 和生成 cwd；代码根必须单独存在。
- 已配置的 `MARKET_FEATURE_STORE_DB`、`FORESIGHT_USERS_DIR`、`FORESIGHT_EPISODE_STORE`、`DUCKDB_SNAPSHOT_OUT_ROOT` 不迁移；相对值按数据根解释，空值使用数据根缺省。
- 日报 exports、复盘 daily/matrices、用户态、episode、snapshot 和 summary 指向代码树时拒绝。测试包括配置软链/相对值和代码根软链。
- 这不是 OS 写入沙箱：可信代码快照内未来新增的任意副作用、运行期间换软链以及未枚举输出不由启动器全面隔离。代码根零新增结论只覆盖实际运行的隔离夹具链。
- 原外置用户目录保持连续，不声称“生产用户态已经迁入数据检出树”。

## 行为证据与明确边界

`tests/test_generation_code_root.py` 新增 **22 项**：

- 真 Python → 启动器 → 真 CLI/runner → 真子进程；代码副本路径含空格，数据树放 poison 包及旧脚本，误加载会显式失败。
- 数据 cwd 与无关 cwd、缺配置/缺目录/错根/缺 CLI、代码根软链、包文件逃出根、状态根指入代码树、缺直接脚本均覆盖。
- 临时 DuckDB 仅有测试 probe 表；质量门/SQL report collector 用夹具结果替换。真实 report writer、增量归档、HTML、主题回填队列、workbench/cockpit 落盘，前后按文件内容哈希检查代码树零新增/零修改。
- 用真实 UserSpace/JsonlEpisodeStore 写夹具记录，并检查 workflow metrics。**这些是存储接口归属探针，不是实际模型回合产生 episode 的证明。**
- 策略 1/3/4 与旧题材简报只验证全部计划执行文件存在于代码根、默认 DB/矩阵/exports 指向数据根；未执行其业务 SQL。模型环境中的无密钥哨兵值可传到子进程，不证明网关可用。
- 真 nightly 调用点变异在**独立夹具副本**执行：正常成功 → 去掉安全路径并改回裸 `-m` → `DATA_TREE_CODE_EXECUTED` 非零 → 还原成功。L2、通知、方法飞轮在该测试内替换；另有 wiring 测试锁顺序，不是上游数据验收。
- 前期两次在同一开发树并行变异/正常测试造成竞争，原失败收据保留。不能当业务回归，也不能隐藏。后续变异只发生于 pytest 临时副本，没有再修改正常测试正在读的开发树。

## 冻结版本检查收据

解释器统一 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`；pnpm 10.12.1。下列代码检查均绑定 `0f6c2810`，不是借用 local-plan 的结果。

| 检查 | 实际结果 | 证据 |
|---|---|---|
| Python Ruff / shell / diff | 通过 | `/private/tmp/generation-root-0f6c2810-ruff.log`；提交钩子通过 |
| Python 全量（干净 detached） | **9679 passed / 77 skipped / 2 xfailed / 17 warnings**，359.07s | `~/.finance-runtime/test-receipts/20260914T181625Z-0f6c2810.json`；`/private/tmp/generation-root-0f6c2810-pytest.log` |
| 收据校验 | revision、解释器、依赖指纹、干净树、未绕依赖门全部一致 | `scripts/check_test_receipt.py <上行收据> --expect-revision 0f6c2810` 已执行 |
| 前端 | lint/typecheck/build 通过；76 tests passed | `/private/tmp/generation-root-0f6c2810-frontend-{install,lint,typecheck,test,build}.log` |
| E2E | 15 passed，46.2s，desktop/tablet/mobile | `/private/tmp/generation-root-0f6c2810-e2e.log`；临时 fixture 后端、端口18873、无模型密钥 |
| registry | 四条命令 exit 0；60 SKILL frontmatter 可解析；无缺仓跳过 | `/private/tmp/generation-root-0f6c2810-registry.log` |
| ledger crosswalk | exit 0；保留96条反向 warning | `/private/tmp/generation-root-0f6c2810-crosswalk.log` |

警告没有消除：Python 有矩阵计算 RuntimeWarning 与 utcnow 弃用提示；pnpm 忽略 esbuild 安装脚本但实际 build 通过；E2E Node 有 module.register 弃用提示。

**跨仓 registry 条件**：ws 精确为验收树；另两仓按脚本同级发现，读取其当时工作树，非冻结 revision：知识库 `87fabcc07`（状态105条），研究站 `e63f048`（状态1条）。未改其内容，不把它们的工作树检查冒充干净跨仓提交验收。

提交前针对性最终 133P/8 warnings：`20260914T180503Z-2f82d4d3.json`（有补丁，不能冒充冻结提交收据）。此前新增测试因夹具依赖/输入未齐出现红灯，逐项补齐，记录在 `/private/tmp/generation-root-*.log`；未改生产质量结果凑绿。

## local-plan 历史红门的补充解释

`4fbc8c42` 在 `/private/tmp` 全量9654P/2F，收据 `20260914T160652Z-4fbc8c42.json` 保留。Codex minimal 沙箱允许读取 `/tmp`，故 live-root-read 探针为 unexpected_success；三项网络/套接字探针实际均 denied，不是网络隔离 flaky。

同提交代码移至 `/Users` 后沙箱两项通过；`07d42891` 全量9656P/0F，收据 `20260914T163249Z-07d42891.json`。旧 E2E 完整日志 `/private/tmp/local-plan-alignment-e2e-07d42891.log` 已核对 **15 passed (47.2s)**。本轮 #50 用新的干净树重新独立验齐，未借用旧树结论。

旧 `/Users/a77/fwp-wt-local-plan-alignment-validation` 后来出现非预期疑似敏感内容，保留不动；未复制、使用或提交其内容。会话凭证撤销与污染来源未确认，不把此事件写成已解决。

## 下一步与不要做

1. 如需继续走验收，按 acceptance workflow 安排独立复核，用户明确确认后才推送/合并；本记录不是合并授权。
2. 部署前核实 runtime 包含完整的 intelligence、market_feature_store、scripts、被调用 skills，而非仅同步 intelligence 的旧半快照；缺项必须停，不能回退数据树。
3. 部署后先检查实际 import/数据/外置用户态/episode 根及真实同日、跨日、L2 门，再单独授权日报生成。矩阵/模型/知识库接收链需真实验收。
4. 不请求复盘会、不写题材资金兜底，不把板块篮子口径冒充题材面板；不操作原数据树 WIP，不碰旧污染副本。

工具沉淀：根探针和独立副本变异已落仓内测试，不另造一次性排查器；跨项目方法写回 `gate-covers-only-its-return-value`。`harness-reference` 当前有他人脏改动，未回写该仓；本轮没有新增通用 harness 安装件。
