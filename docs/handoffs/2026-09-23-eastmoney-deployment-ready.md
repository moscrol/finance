# #60 部署准备完成快照

## 背景与授权

上一轮#887候选已完整验收，明确询问了固定head/base的合入确认，排除真实安装。用户本轮回复「继续推进直到可以部署」，本轮据此合入#887并完成实际main验收和最终预演；没有扩大到安装、服务重载、热补或生产写库。授权原话与出处在树外 `authorization.json`、仓内工具生成的 `merge.json`。

## 按发现顺序

1. 独占分支 `fix/eastmoney-deploy-binding-0923` 起始本地HEAD为交接提交f3028739，干净；远端仍是已验收候选99bd31c97630，main仍2edbe4c46595。未动共享脏主检出。复核上一轮SHA256，恢复候选原验收路径，native完整收据与gate replay通过、base漂移0、merge-tree等于247f7951741f。
2. 解除WIP，用现有 `scripts/gitea_pr.py merge 887 --yes --do merge`，锁完整head/base，记录本轮真实授权。工具与独立回读均确认实际合并 `0525e780e0435d44d0f47455ef604325e1a65258`；父提交精确为2edbe4c46595、99bd31c97630，tree精确为 `247f7951741fc41b2be473fe712a0fab9454a9b2`。未删分支、未追加推送本地交接。
3. 从实际main分别建立两个独占验收树和固定装机源 `~/.finance-runtime/finance-nightly-installer-0525e780e043`。后者锁定保留；同步运行根仍是已准备的 `~/.finance-runtime/finance-sync-2edbe4c46595`，完整revision `2edbe4c46595cbea3eb3abe04fe84a7bd5afd55e`，含#856且保持干净。
4. 合后前端六命令通过：120单测，E2E34P/2S；首尾身份稳定/干净，六日志哈希通过。隔离registry五项通过，缺席外仓不算已验，98条反向台账warning保留。
5. 主机负载曾显著升高，未杀其他会话进程；等前端结束、负载回落后再启动Python。启动时load1=14.80、内存空闲53%、另有3个pytest进程，原始观察保留，不声称低负载或性能改善。实际merge上完整首轮14620P/0F/0E/85S/2X，collected14707，exit0，约27分27秒；Ruff通过。
6. 实际装机源模板在临时HOME、记录型launchctl下安装验证通过：四文件、两job、无kickstart、无真实服务调用。同步运行根离线探针通过：导入正确、两host各3次空回应后拒绝、重置计数不解熔断、一次snapshot后一次local fallback；没有真实请求/DB打开/采集子进程。
7. 全量完成后，从实际main装机源执行nightly-only dry-run，exit0，两job验证、零复制/零服务变化。审计前后源与生产小文件hash/权限一致，共享helper和S7包装不变。18:07只读回查已加载ProgramArguments和环境，与已安装plist完全匹配，仍是adcda旧根；两job未运行、夜跑锁不存在，旧last exit2不代表新代码结果。
8. Native收据、完整范围/依赖/身份/干净树/base漂移0与gate replay通过；JUnit独立解析对平，相关96项全部在完整集合且通过。`verification.json`生成时main仍精确为0525e780e043。前端/Python测试树及复原的候选验收树回收，绿色basetemp由runner清理；门禁进程退出，两个固定部署目录保留。

## 决策对比

| 方案 | 评价 | 决策 |
| --- | --- | --- |
| 复用候选收据作merge收据 | 文件树虽相同，却不能把旧revision记录换签 | 实际merge独立完整重跑 |
| 装机源和同步运行根分离 | 功能根先固定，后续绑定提交才能引用它；避免自身SHA循环 | 采用，两个目录各有完整身份 |
| 从运行根执行installer | 该根模板仍指旧根，实际会装错 | 禁止，只从指定真实main源安装 |
| 截止时间到就安装/热补 | 本轮未获安装授权，仍需检查写者与新回滚点 | 不执行；时钟不构成授权 |
| 复制当前旧运行树作干净回滚 | 旧根含历史热补与运行产物，不是干净Git副本 | 安装时备份每个真实目标文件及加载配置 |

## 验证与证据

证据根：`~/.finance-runtime/reviews/eastmoney-cb-deploy-20260922/binding-merge-20260923T0919/`。

- `merge.json` / `independent-readback.json`：实际操作与完整身份。
- `postmerge/python/gate-2lURxMRy/pytest.json` / `postmerge/python/junit.xml`：完整Python事实；`postmerge-receipt-check.log`、`postmerge-gate-replay.log`、`verification.json`：复核。
- `postmerge/frontend/frontend.json`、六份日志；`postmerge/registry/`：其余叶子。
- `installer-before-gates.json`、`installer-before-dry-run.json`、`installer-after-dry-run.json`、`final-dry-run.log` / `.exit`、`loaded-jobs-final.json`：实际main预演与生产未变回读。
- `runtime-offline-probe.json`、`installation-sandbox/record.json`、`installed-snapshot-preparation/record.json`：辅助证据。
- `install-runbook.md`：安装前条件、固定入口、目标清单、部分失败回滚、部署后业务验收。

只证明此固定版本具备部署准备条件；不证明已生效、不证明东财可用、不证明数据恢复。#61/#871在本轮最终回读仍open，没有捆绑。

## 后续与禁止项

状态为ready_for_install_authorization，不是installed。正式安装仍需新授权、重验固定身份和环境、空闲窗口及新备份。随后才从指定源安装两job，不kickstart；磁盘/加载配置都要回读，真实夜跑取数和非空字段另验。不要覆盖旧冻结收据，不用旧Plan B，不重置旧热补根，不把#60工单标为生产验收完成。

工具沉淀：复用既有PR、native/frontend门禁和准备期探针；新增的对账及loaded-state读取只服务这个固定发布的证据包，不新增第二套发布框架。既有装机源/运行根分离决策继续沿用，没有新跨项目机制；未改脏的harness-reference。
