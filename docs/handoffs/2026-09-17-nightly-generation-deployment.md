# 2026-09-17：夜跑生成段正式部署与真实 launchd 验证

## 结论与授权边界

用户在两日复盘恢复收尾后说「执行」，本轮执行生成代码根的正式部署，不合 main、不替换整个 runtime、不迁移方法协议、不做知识库 apply。

**已部署并从真实 launchd 入口主动触发一轮成功**，不是只在终端补跑：2026-09-17 23:44:01–23:45:44，PID 45350，退出码 0，任务结束且目录锁释放。生成 19 步全 PASS，数据/跨日/L2/报告门通过。只是对当日已修复数据的真实入口验收，**下一次 20:40 自动调度尚未发生**。

- 接线代码：`fix/nightly-generation-deploy-0917@2fa28a4f8c1d51d40fdd499ec82df2f0e024e7c9`。
- 生成完整冻结树：`~/.finance-runtime/finance-generation-387028b846a2`，HEAD `387028b846a21a1327d964af8c4b428367f88fcf`；检验后仍干净。
- L2 / 外层质检 / 方法：原 `~/.finance-runtime/finance-l2-d433b90788c0`，不动。
- 数据：`~/finance-workspace-private`；users：`~/.local/share/finance-workbench/users`；episodes：数据根 `state/episodes`，不迁移。
- 全部本轮收据：`~/.finance-runtime/generation-deploy-20260917/`（下称 RUN）。源码与部署状态分开：本枝及生成返修枝未合 main；本枝未 push。

## 背景与发现顺序

09-16/17 恢复任务此前已经完成数据、L2、报告和快照，并用 `387028b8` launcher 一次性生成成功。但装机 `~/.local/bin/nightly_full_review.sh` 仍在数据 cwd 裸跑 `python -m intelligence.cli daily`，下一夜会重新加载旧数据树代码。

1. canonical 树有其他人的 WIP；本轮从 fetch 后的 `gitea/main@0a1cb8c4` 开独立树 `~/fwp-wt-nightly-generation-deploy-0917`，没有整理共享树。
2. 装机 wrapper 与该 main 完全相同；两个 launchd 任务当时均未运行，无复盘目录锁。
3. 生成返修树的整份夜跑 wrapper 比当前装机旧，含旧 L2 暂停逻辑；直接覆盖或全局换 CODE_ROOT 会回退 L2。
4. 新增 `FINANCE_GENERATION_CODE_ROOT`，只对生成子进程设置 `FINANCE_CODE_ROOT` / `PYTHONPATH`，通过 `-P` 启动绝对路径 launcher。没有另建 daily 流程，仍调用原 CLI；显式传 local 和数据根 summary。缺 launcher 返回 2，不用数据树顶替。KB receive 兜底和 freshness 脚本也从生成根取；只 receive、不 apply。
5. 完整固定生成 revision 建为 detached runtime worktree，没有单摘返修提交到未知基线。装机 plist 只新增生成根键；仓内模板同步固定 L2/生成两个根。sync plist、S7、8792 runtime 链、ops_python.sh 均未改。
6. 备份脚本/配置并记录 SHA256；bootout → 原子替换 → syntax/plist 检验 → bootstrap。装机配置与仓内模板语义相等，生效环境逐键核验。部署失败路径恢复旧副本；实际没有触发回滚。
7. `launchctl kickstart -p gui/501/com.financeworkspace.daily-full-review-finalize`（没有 `-k`，没有杀任务）触发装机命令。主管按启动前日志字节偏移提取本次日志，结束即冻结摘要，避免以后共享文件被覆盖后冒认。

## 选型

| 方案 | 判定 | 理由 |
|---|---|---|
| 继续一次性调用验证树 | 否 | 不改变明晚定时任务的入口 |
| 全局把 FINANCE_CODE_ROOT 换成旧生成树 | 否 | L2 / 方法 / 闸门会随之回退 |
| 整份覆盖生成分支的旧 wrapper | 否 | 会恢复已退役 L2 暂停分支 |
| 把生成源码复制进数据树 | 否 | 继续与共享 WIP 耦合，不能证明运行代码来自固定 revision |
| 当前 wrapper 最小改动 + 单独冻结生成根 | 采用 | 子进程范围切换；保留数据位置与已验证 L2，可单独回滚 |
| 新建通用部署框架 | 否 | 本轮是特定两文件发布；机械不变量已落正式测试，一次性发布/取证编排留 RUN |

可迁移点：多组件异步升级时，**组件级代码根优于全局换根**；代码根/数据根分离还不够，环境变量的作用域也必须测试。

## 验证及证据

### 边界 / 测试

- 原独立探针判据未改，本轮独立重跑 `scripts/probe_generation_code_root.py`：7/7。`RUN/generation-probe.json`；不是另一个独立模型审查。
- 实际新冻结 runtime 的 `tests/test_generation_code_root.py`：47 passed；收据 `~/.finance-runtime/test-receipts/20260917T153826Z-387028b8.json`。
- 接线 revision `2fa28a4f` 的四文件定向：87 passed / 8 个既有 utcnow 弃用告警；收据 `~/.finance-runtime/test-receipts/20260917T154229Z-2fa28a4f.json`，日志 `RUN/wrapper-tests-2fa28a4f.log`。收据代码 dirty=false，另有本轮 skill 文档 WIP，不冒称整棵工作树全干净。
- 测试覆盖 L2 先于 data 门、任一门失败挡生成、缺 launcher 不回退、生成失败传播、独立生成根不泄漏到最终 all 门，以及保留现行 L2 路径。
- 内存变异删除生成子进程 `FINANCE_CODE_ROOT` 赋值，正式回归按预期红；恢复实现通过。`RUN/wrapper-mutation.log`；未改磁盘源码或生产。
- 全仓 Ruff、zsh syntax、plutil、diff check 通过。本枝未跑全仓 pytest / 前端 / E2E / registry 四叶，不具备合 main 结论。旧生成枝作者的全量四叶不冒充本枝合流准入。
- 生产环境 dry-run 成功，计划明确从生成快照加载、以 venv 执行：`RUN/production-dryrun-summary.json`。dry-run 的 SKIP 不是执行成功，真实结果另见下项。

### 已安装的真实入口

`RUN/launchd-result.json`、`launchd-stdout.log`、`launchd-stderr.log`、`ops-health.log`：

- 装机任务运行一次，exit 0，not running，锁不存在；`generation_import` / CLI 指向新冻结根；L2 日志仍 `d433b90788c0`。
- L2 走原正式入口，本日已 complete 因而跳过重新下载/扫描，重新渲染与质检通过。**本轮不是新包实扫验收**；之前两日真实扫描及输入对账见恢复交接。
- 外层 local data 为 19/20 表；L2 / all COMPLETE。生成内质量门及跨日门、报告、框架解释、checkpoint、题材、研究队列、KB receive、三套矩阵、workbench、cockpit 共 19 步 PASS，23:44:04–23:45:40。
- `RUN/generation-summary-frozen.json` SHA256 `48456eb2dcefe840c6aceb274738963f36340556344171a2a0fb81955677d5c8`。摘要只含两个正常选步提示，无 errors；不要读未来覆盖的 canonical summary 代替它。
- KB 本次归档 `wiki/raw/cross-repo-ingest-queue/2026-09-17/2026-09-17-kb-ingest-queue-4.json`，9 tasks；兜底重复 receive 按 payload hash 去重，不 apply、不处理他人 UU。
- 日报 JSON 目标日正确、warnings 空；HTML 日期、MA5 PNG 签名及矩阵/队列/工作台等 12 个实物的哈希在 `RUN/post-deploy-verification.json`。未做真人浏览器视觉验收。
- 快照仍是前次恢复 22:03:23 发布的 09-17 `duckdb_exact` / complete / fresh；**本次没有重写快照**。23:48:15 的 8792 readiness 为 ready，DB/snapshot 均 09-17、一致。`RUN/readiness-final.json`；这不是 Workbench 模型回合验收，RAG legacy query 协议 warning 保留。

### 未解决的旁支

`RUN/method-daily.log` 如实显示：水位一致故 rebuild skipped；capture **refused**（`unsupported protocol contract or label version/spec`）；recheck nothing_due。方法命令 rc=0 仅代表日步执行完成，**不代表前向观察登记成功**。旧 v3 协议 / 当前 v6 标签问题留下一单，不编辑旧协议或回拨时钟。

静态路径预检不是 OS 沙箱，不防运行期换链与未知写点；真实生成不是模型网关、Workbench episode 或知识 apply 验收；20:40 定时器下一次自动触发尚待观察。18:30 同步、行情快照既有调度链未由本轮重跑或改写。

## 回滚与接手

1. 先确认 sync/finalize 均 not running、无复盘/L2写进程及目录锁，不能 kill 正在发布的任务。
2. 查 `RUN/deployment-receipt.json` 的 after 哈希与当前脚本/配置相符；若不符，说明又有人改过，先协调，不能拿整份备份覆盖新改动。
3. bootout finalize，恢复 `RUN/nightly_full_review.before.sh` 与 `RUN/finalize.before.plist`（保留执行权限），分别 `zsh -n`、`plutil -lint`，再 bootstrap。只回滚 finalize 两文件；不碰 sync plist、L2 根、runtime 链、数据与用户态。
4. 回滚会恢复已知旧生成入口，仅用于撤回本次接线，不等于修复成功。冻结生成树保留供重验，不删以免引用悬空。

下一步：观察下一夜真实自动触发；方法另登记兼容新协议并显式 active 切换；源码合并前需固定候选的四叶与用户确认。`FINANCE_GENERATION_CODE_ROOT` 必须随正式模板安装保留，不能从旧 main 模板重装后静默丢失。
