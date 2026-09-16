# L2 定向部署

## 这个分支做什么
归档 #773 已验收版本的生产部署与实测；不改产品代码。正文见 `docs/handoffs/2026-09-16-l2-scoped-deployment.md`。

## 决策与被否方案
- finalize 独立绑定干净快照 `~/.finance-runtime/finance-l2-d433b90788c0`；否决切共享 runtime、运行六任务安装器，避免影响 8792 和其他任务。
- 保持真实缺数失败，不绕过预检、不以昨日名单代替今日；未顺带执行行情补库。
- 备份装机脚本与 plist，不删除主树脏代码；回滚说明在正文。

## 当前状态
部署已生效，115 条定向回归通过，真实 finalize 已运行结束；2026-09-16 业务仍因日线缺失阻塞。本分支归档证据，不推进 main。
20:40 任务代码为 `d433b907`；8792 仍为 `db2963d4fbaa` 且 healthy。
备份与原始日志：`~/.finance-runtime/l2-deploy-20260916/`。
09-17 根因更正：另一会话 09-15 22:29 看旧主树误判 local 不存在，将装机两档改 auto。14/15 日 local 曾成功；不是应恢复复盘会登录。证据与恢复方向见 `docs/handoffs/2026-09-17-review-plan-regression-diagnosis.md`。本轮未改生产配置/补数。

## 已验证
23:05:33 至 23:06:29 真实 launchd 入口加载新快照，分享查询成功、复用 5,097,702,316 字节缓存；候选检查报 `limitup=33 top100=0/100`，新榜写入未执行。L2 段 exit 1、质量门 exit 2、finalize exit 2。
前后结果行数与步骤状态一致，旧 limitup 33 行 complete，top100/quant failed。没有重新证明旧结果完整。任务已结束、锁释放、快照干净、无遗留测试进程。
收据 `docs/verification/l2-deploy-20260916/`：deployment.json 是切换瞬间，verification.json 是真实运行后；targeted-receipt.json=115P/0F。

## 未验证 / 已知边界
未验证生产三榜成功、缓存包完整性、重新下载、生产解压与发布、回滚执行。
18:30 S7 被误设 auto（当天解析 cheap）后才依赖 CDP/登录并失败。当前装机两份仍 auto，仓内两份 local。空间检查约余 16 GiB。

## 下一步
先将 sync/finalize 有效档位同时恢复 local，保留 L2 独立代码根，再经 daily-full/S7 staging 正门补 09-16，按 local 过门后重跑该日 finalize。跨日不能冒用今日快照。生成段若仍不传计划须修接线，不得改 auto 掩盖。上述未执行。
跨日不要直接 kickstart（默认当前日期），须显式指定 2026-09-16 并沿用 plist 环境。

## 踩过的坑
装机旧脚本打印 runtime 版本但实际从 DATA_ROOT 执行；验收要看真实入口与异常栈。缓存仅按大小复用，不代表完整；同大小坏包须隔离重取。通用安装器会覆盖本次独立绑定，后续升级必须先核实任务配置。
