# OPC 临时 shim 原件封存（2026-09-19）

仅供恢复/审计，**本 salvage 分支不合 main、不部署、不作为修复候选**。

## 内容与验证

`manifest.json` 记录三个文件的原路径、原主树 HEAD、档案路径、字节数、SHA-256 和 Git blob。`files/` 下采用 `.py.txt` 后缀保留原字节，不导入或执行；复制前后已核原文件未变且副本一致。恢复时先读 manifest，在新的隔离目录还原原路径，核哈希后再审阅；不得直接覆盖现役文件。

封存来源是脏主检出树 `b4a35fa2` 的三个指定文件，不是整个工作树或 Codex 检查点。三份 blob 也存在于临时 `refs/codex/turn-diffs/checkpoints/…` 指向的树 `6abb7980`；工具临时引用不是长期备份，故建立具名 salvage 分支。

## 为什么不覆盖源码路径

最新 main 的检查器和生成流程已经前进；把旧 shim 放回源码路径会把档案误装成实现，并回退新代码。本次不修正其硬编码路径、未用 import 或旧注释，避免改变需要保全的原件。档案不通过运行时正确性认证，也不以改后源码冒充原件。

## 现役夜跑状态（独立于封存）

09-18 的 finalize 不依赖这三个文件：

- 生效 launchd 配置的 `FINANCE_GENERATION_CODE_ROOT` 为 `~/.finance-runtime/finance-generation-387028b846a2`。
- 主树 `logs/daily-full-review.out.log` 的 09-18 20:46:56 行记录 `generation_rev=387028b846a2`。
- `market_feature_store/exports/2026-09-18-daily-workflow-summary.json` 中质量门调用冻结生成根的绝对路径，跨日门是带 `--plan local` 的正式 CLI，并非 `check_daily_plan_local.py`。

这只撤销“昨夜靠三个 shim 运行”的判断，不授权清理脏主树，不证明其他入口没有遗留依赖。#50 源码合流与生产部署分别记账；本次不重装、不重跑夜跑、不改数据库或 8792。
