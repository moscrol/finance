# 2026-09-16 L2 夜跑定向部署与实测

## 结论

用户授权「部署，测试」后，已把每日 20:40 finalize 绑定到独立干净快照
`~/.finance-runtime/finance-l2-d433b90788c0`，revision
`d433b90788c0727d71043a992e69c20f34203257`（PR #773 已验收版本）。

**部署已生效，回归通过；2026-09-16 生产业务仍被当日日线缺失阻塞，不能报全链路通过。**

证据目录：[`../verification/l2-deploy-20260916/`](../verification/l2-deploy-20260916/)。
本机备份与原始证据：`~/.finance-runtime/l2-deploy-20260916/`。

## 背景与发现顺序

1. 主检出树 detached 在 `b4a35fa2`，存在其他 agent 的改动。本轮没有编辑、清理或切换它。
2. 在线问答服务 8792 使用共享链接 `~/finance-workspace-runtime`，实际指向
   `~/.finance-runtime/finance-workspace-db2963d4fbaa`。不应为了升级夜跑顺带切换它。
3. 原装机 `~/.local/bin/nightly_full_review.sh` 虽打印 runtime 版本，实际却从
   `$DATA_ROOT/scripts/moneyflow` 执行 L2 与失败回写。该生产覆盖层是本次迁移对象。
4. 通用 `scripts/install_eval_launchd.sh` 安装六个任务，超出本次边界。
5. 创建独立 detached worktree，验证完整测试收据 revision、解释器、依赖指纹一致。
6. 在 finalize 未运行、锁不存在的前提下，备份装机脚本和 plist，仅替换该脚本、
   修改 finalize 的 `FINANCE_CODE_ROOT`，再 bootout/bootstrap 该任务。未立即自动启动。
7. 从实际部署目录运行七组定向测试：115 passed，12.21 秒，0 failed/error，收据 dirty=false。
8. 23:05:33 手动 kickstart 真实 finalize，23:06:29 结束。启动日志与异常栈均来自
   `finance-l2-d433b90788c0`，不是主树或旧共享 runtime。
9. 百度分享查询成功，发现当日包 5,097,702,316 字节，复用已有缓存；随后在候选预检
   报 `incomplete candidates: limitup=33 top100=0/100`。未到解压、新榜写入或日报生成。
10. L2 段 exit 1，L2 门 exit 2，当日数据门 exit 2；launchd 最终 exit 2、not running。
    前后 L2 质量检查输出逐字一致：旧 limitup 33 行仍 complete，top100/quant 仍 failed。
    没有把旧 33 行重新认定为本轮已验证的完整结果，也没有把当天标成成功。
11. 当日日线缺口早于部署：18:30 S7 同步预检报 CDP 代理未连 Chrome、复盘会未登录或
    标签页未就绪，子流程 rc=3，staging 未发布。该日志是历史诊断，不代表现时登录状态。
12. 23:36 复核 CDP health 为 connected=true；这只说明代理连接恢复，不证明复盘会登录有效，
    也不证明当天数据已补入。8792 仍 healthy、`db2963d4fbaa`、代码与目录一致。

## 方案取舍

| 方案 | 评价 | 结果 |
| --- | --- | --- |
| 切共享 runtime 链接 | 会同时影响在线服务与其他任务，超出授权目标 | 否 |
| 从脏主树继续运行 L2 | 无法把实际执行代码对应到验收提交 | 否 |
| 运行通用安装脚本 | 会覆盖六个定时任务和配套脚本 | 否 |
| 独立快照 + 仅 finalize 配置 | 保持代码可追溯、变更范围可核对，后续升级需单独维护这个绑定 | 采用 |
| 绕过同步预检或用昨日名单 | 会把上游缺数变成假完成 | 否 |
| 顺带补跑全量行情同步 | 属于另一条会写生产库的任务，本轮没有扩展执行 | 未做 |

保持不变：20:40 时间、解释器、数据根、数据库、输出目录、18:30 sync plist、
8792 plist、共享 runtime 链接。`ops_python.sh` 与候选版本逐字一致，不替换。

## 验证与成立条件

- 合并前完整回归：11,185 passed / 81 skipped / 2 xfailed，以及前端、E2E、registry 四片，
  见 `fix/l2-file-source-qc@8bcb88e3` 的原验收交接。本次没有重跑全仓。
- 部署目录定向回归：`targeted-receipt.json`，revision `d433b907`、Python 3.12.13、
  依赖指纹 `3328bed61f3e21ea`、dirty=false、115 passed。
- 配置前后摘要：`deployment.json`；这是切换当刻、尚未 kickstart 的历史收据。
- 实测后状态：`verification.json`；业务状态明确为 `blocked_missing_daily_facts`。
- 真实运行：`live-finalize.txt`、`live-finalize-errors.txt`。
- 数据门：`l2-after.txt`、`data-before.txt`。
- 共享服务的配置摘要和链接未变；没有重启在线问答服务。
- 测试及手动触发任务均已结束，锁与解压临时目录不存在，缓存包仍保留供后续重试。

未验证：生产完整成功路径、当日包完整性、重新下载、生产解压与三榜发布、回滚执行。
当日包仅按大小命中缓存，不是完整性证明；同大小坏缓存需要隔离后重新取得完整包。
磁盘检查时仅余约 16 GiB；后续完整解压或补数据前须重新检查空间。

## 恢复顺序

1. 通过原同步流程的预检确认 Chrome、CDP、复盘会登录与标签页就绪；不要使用 skip-preflight。
2. 沿既有 `daily-full` / S7 staging 正门补齐 2026-09-16 数据并通过当日数据门，禁止 inline SQL 补假行。
3. 通过已安装 finalize 重跑指定交易日，再验三步骤统计、结果覆盖与非空值。
   `kickstart` 默认按当前日期运行；跨日恢复必须显式传 `2026-09-16`，同时沿用 plist 环境。
4. 三榜真实完成、数据门通过后，才能更新业务验收结论。当前不卸载这次已验收版本。
5. 不恢复退役写入链，不删除主树运营覆盖层的源文件；它们不再由本次 finalize 作为 L2 代码执行。

## 回滚

仅在新版代码或配置确需回退时操作，先确认 finalize 未运行且无生产写入冲突。
备份在 `~/.finance-runtime/l2-deploy-20260916/backup/`。回滚会恢复原先从脏主树执行 L2 的
启动器，不是恢复数据，也不是解决当日日线缺失，因此本次没有回滚。

```sh
launchctl bootout "gui/$(id -u)/com.financeworkspace.daily-full-review-finalize"
cp -p "$HOME/.finance-runtime/l2-deploy-20260916/backup/nightly_full_review.sh" "$HOME/.local/bin/nightly_full_review.sh"
cp -p "$HOME/.finance-runtime/l2-deploy-20260916/backup/com.financeworkspace.daily-full-review-finalize.plist" "$HOME/Library/LaunchAgents/com.financeworkspace.daily-full-review-finalize.plist"
launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.financeworkspace.daily-full-review-finalize.plist"
launchctl print "gui/$(id -u)/com.financeworkspace.daily-full-review-finalize"
```

不要改 8792 或共享 runtime 链接。复核备份哈希与 `deployment.json.before` 一致；
如果操作时配置已被他人更新，停止并按新状态重新评估，不能直接覆盖。

## 沉淀边界

本轮没有修改产品代码或新增通用部署器；受指定 revision、任务名与本机旧状态约束的
一次性部署脚本保存在原始证据目录。重复核对用 `verify.py` 执行并产出机器收据。
不向面向端口服务的 deploy-ledger 写虚构 8792 切换，任务级证据以本次不可变收据归档。
现有质量门已正确拦截缺数，未发现需要本轮再补的代码缺陷。
