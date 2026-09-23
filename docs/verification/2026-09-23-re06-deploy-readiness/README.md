# RE06 / E2 Deployment Readiness

## 当前结论

**NOT_READY / BLOCKED_RESOURCE_GATE，不可合入或部署。** 最新候选
`7ec9d022b14db46ac667accc08c7891f27f5a1a6`，base
`626d8a508c1c988ff094110b371987e6afdcdd15`，来源为 shipping 修复
`b24c86f87aaef6244dc6a2c6cf80f74ae1918943`。作者树
`/Users/a77/fwp-wt-re06-ready-refresh-0923`，分支 `baseline/re06-ready-refresh-0923`。
独审树在运行根目录 `qc-k3-03/candidate/finance-workspace-private`，detached 且锁定。

运行根目录 `R=~/.finance-runtime/reviews/re06-deploy-readiness-20260923-01`。
身份与原始状态见 [identity-02](archives/control/identity-02.json)、
[readiness-report](archives/control/readiness-report.json)、[closure](archives/control/closure.json)。
收尾 fetch 后观察到 main 仍为该 base，漂移 0；作者树与独审树干净。
B 的业务实现未再改动，无 push、PR、合 main、部署、生产写入/迁移、8792 修改或删树。

## 候选与证据分账

| 候选 | 工程证据 | 独立 QC 与限制 |
|---|---|---|
| b24，历史 shipping 修复 | 四叶 PASS，Python14673P/85S/2X | 早期探索/504 等见[历史包](../2026-09-23-re06-timer-assets/README.md)，不移签 |
| 8eac9b3b55，base b59d6eed03，已被替代 | acceptance-03：Python14726P/85S/2X，14813 collected；其余三叶 PASS；完整收据因 main 漂移15次合并、上限5，被判 NOT_PASS | QC02 v3 E2：审查者19P、作者20P分别统计，`assert 1 == 2` 正控1次预期失败；C1-C3 verified，Quality PASS_WITH_LIMITS；timer/consent未完成 |
| 7ec9d022b1，当前固定合流 | acceptance-04在任何测试/build之前资源阻断；恢复等待也用尽，acceptance-05未创建 | QC03只完成沙箱/命令边界宿主预检与事务点枚举；依赖安装、实际执行预检、gateway、三组模型阶段均未开始。C1-C10全not_verified，Quality未评估 |

旧 E2 [独立 FINAL](archives/qc-k3-02/work/e2/FINAL.json) 保留完整限制：材料模式正向
legal_gap 对照、语义裁决层、混绑、部分编号/恢复变体等未独立覆盖。
其中查重不对称仅为后续直接构造入口的回归风险，不是已证实当前可达缺陷。
旧 [工程收据](archives/acceptance-03/receipt.json) 的 Python 失败是收据基座门拒收，
不是 pytest 用例失败。真实失败与基础设施阻断均保留，不移签、不合并统计。

## 为什么仍阻断

- 两条有界等待均已结束。最后观察负载53.113、已有pytest4/预计5、空盘11.622GiB；门槛为负载<=8、预计pytest<=2、空盘>=8GiB。没有绕门或停止其他任务。
- 当前候选启动测试/build为0、模型请求为0。配置测试端口29801/29804/29901/29904均无监听，所属运行进程已结束，无自动续跑排程。
- acceptance-04旧runner资源超时分支未置`complete:true`；原件未改，独立`closure.json`记录其已终止且执行数0，不能把旧false误读为仍在运行。
- 8eac与7ec整个受跟踪`intelligence`子树同为`38563f3da4481ab2e17132f2b737c14191dd63ca`，只支持有界差分探索，不支持继承 verdict。旧探针原稿、重定位前后哈希与外部基座差分均冻结，待独审接受或拒绝。
- 18个直接事务点（17业务+1底层）只是指定文件集的AST枚举，不是独立语义分类，更不是全仓无竞态证明。
- data-quality工作流路径未触发，记`NOT_TRIGGERED`，不记PASS。

## 执行链修复与原件

旧执行先后遇到沙箱禁止`ps`、pytest读取目录元数据被拒、`conftest.py`清除环境后
API导入回退历史用户目录。v3把资源检查留在可信宿主wrapper，测试仍在沙箱；只放行指定
受限目录的元数据，不开放正文；隔离插件同时改写默认用户目录，封住环境变量回退。
QC02已实跑正控、独立探针、作者测试；QC03仍须自己重做实际执行预检。
探索期两次普通`python3`导入/冒烟为[协议偏离](archives/control/exploration-deviation.json)，
不作正式pytest证据。宿主预检、字节核验、结构终稿都不代独立语义批准。

本readiness运行根累计147/218请求，剩余71；QC03计划另69、累计216，包含gateway与收尾额度。
218是宿主设定的上限，不是用户原话数字；更早shipping批73另账，两包累计220。
各阶段明细和授权修正见[总账](archives/control/readiness-report.json)与
[authorization-amendment](archives/control/authorization-amendment.json)。K3/xhigh不变，自动重试0，未换账号/模型。

## 接下来

1. 资源恢复后先fetch并核当前候选/base与漂移；必要时另建固定合流，不能拿旧绿收据代签。已结束控制器不直接重跑覆写原件，续跑用新状态/输出路径。
2. 在剩余额度内，先冻结依赖、实际测试执行预检和新gateway，再逐组差分explore、控制/独立/作者/UI执行、证据核对、独立report；同时新目录四叶，Python全量身份/完整范围/base-drift-max5均须通过。
3. 三组C1-C10与Quality独立结论未齐，不申请合入。自然金融质量另闸：#76六行各自授权，不能充当E2 P7的A1-A17协议；新会话/原始题/跨轮真实模型验收需独立条件卡与授权。当前阶段仍禁正式T2→T3/Knevo对照。
4. 达到就绪后仍须用户另行确认push、PR、main合并与部署；生产迁移/重算及删树也不在本次授权内。

## 归档

[archive-verification](archive-verification.json) 给出生成脚本算出的文件数和字节数。
每个`archives/*/manifest.json`绑定原路径、原字节数和SHA256；非规范换行/日志可逆gzip+base64保存，
避免提交钩子改原件。脚本保存为`.txt`，是本机一次性证据，不是新增通用运行时。
不含数据库、浏览器缓存或实际凭据；唯一密钥样式豁免是按固定revision的AST原文与
`testsignature`假签名共同确认的负例JWT哈希。第一次归档检查拒绝与未完成组装仍保留在R。
