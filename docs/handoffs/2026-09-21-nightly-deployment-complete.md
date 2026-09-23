# #827 夜跑窄发布完成（2026-09-21 18:43 CST）

## 结论与边界

用户再次明确「执行」后，#827 已以 fast-forward-only 合入，主干精确成为 **`c097d712f9acfdd258709c7d0de054f978e0159c`**；四叶工程收据签的是这个提交。18:43 完成两个夜跑任务的备份、配置安装和实际加载值检查，结果 **`CONFIG_DEPLOYED_NOT_EXECUTED`**：安装了下次定时执行会使用的配置，没有手动触发采集、生成或 L2。

这不是“同花顺生产数据恢复”。18:30 **旧配置**自然同步失败；8792 readiness 仍503，快照9/21与库9/18不一致。旧部署根、旧同步树本地补丁、失败staging均保留。8792由另一会话更新到 `f2c3e9e1a24f`，本轮没有改它。

原件：`~/.finance-runtime/reviews/nightly-deploy-resume-20260921/`。
仓内封存：`docs/verification/2026-09-21-nightly-deploy-resume/manifest.json`。
本文件所在文档尖不继承 c097 的全量签名；运行代码、PR合入与装机事实分别由原件证明。

## 按发现顺序

1. **17:18重入**：本枝 `b0cf04fb4` 干净，主干起初读到 `f783f19c8`，六装机文件仍旧；宿主多个全量同时运行、仅约8GiB。此前2ea6全量ENOSPC红、Quality无报告的原件完全保留。
2. **新Quality单次补审**：现有K3订阅路线，最多1200秒/40请求、不自动重试/换服务。24请求、897.662秒正常exit0，候选 `b0cf04fb4`、输入和作者树不变。53测试、独立62断言；结论PASS、两个low保留。共享记忆在会话中由其他写者前移，不能声称vault没变。审查者最初覆盖了一份自建rig日志，已披露；事件流保留，根会话另目录复跑。
3. **只回收自有临时产物**：将前一成功轮 `nightly-deploy-closeout-20260921/python/tmp` 的83,907项/3,177,397,510文件字节完整归档；逐项核内容、权限和软链后回收原临时目录，313,705,315字节压缩包留外部。没有删他人资产或真实worktree。不是重试失败用例以凑绿。
4. **纳入新main**：等待期间main合了#830，变为 `f2c3e9e1a24f`。无冲突合入本枝得到 **c097**，推回#827。#830是上游基线，不冒称本轮独立审过它；夜跑实际运行根继续固定adcda。
5. **串行重验**：registry、生成边界、hooks、前端先完成。自己的Python队列等到18:20无其他pytest才开跑（不是全机强制锁，随后其他会话又起跑）；8GiB入场门、运行期3GiB停止底线；`tmp_path_retention_policy=failed` 只保留失败夹具。全量19分18秒，首尾同SHA且整树干净，最低采样余量6,472,081,408字节。
6. **自然生产变化**：18:13另一会话切8792到f2c3，health/软链/部署账本一致；本轮重新固定“保持不动”的UI身份。18:30旧sync定时启动，尊重其锁、不bootout。18:36:35退出2：东财快照RemoteDisconnected，个股当日0行，派生层随之失败；S7拒绝换库。部署前复核主库inode/mtime/size与此前相同，不把staging里的指数/申万新行当生产成功。
7. **合入**：18:42所有叶子与收据交叉核对PASS，API再次检查head/main后移除WIP，以 `fast-forward-only`、精确head、`force_merge=false`、`delete_branch_after_merge=false` 合入。main==c097，fetch后 `check_test_receipt --expect-revision <main> --base-drift-max 0` exit0。
8. **发布**：任务均idle、旧锁已释放、生产库无打开句柄；六文件原哈希、三个候选根与旧补丁保全都过。先备份再获得自有锁；先卸载两个job，再调用原安装器 `--nightly-only`，不kickstart。核实际loaded值、文件/权限、runs=0、共享helper和S7 wrapper、其他四job/8792、旧根与主库不变。最终释放仅自己的锁。18:43及随后复读通过。

## 工程与独立审查签名

| 证据 | 精确对象与读数 | 不代表什么 |
|---|---|---|
| Python/Ruff | c097；12502P/0F/0error/85S/2X，JUnit12589项，Ruff0 | 不代表生产采集成功 |
| 前端 | c097；六命令0，110P；E2E34P/2S | 不代表真实金融问答全部通过 |
| registry/生成边界/hooks | c097；registry五项0，7+4边界、窄安装dry-run通过，hooks0 | 不代表生产完整副本/302132演练 |
| Spec | 原签名2ea6；33请求，21断言 | 未重开模型、未移签到c097 |
| Quality | 新签名b0cf；24请求，53P、62断言，两个low | 未审上游#830或真实数据恢复 |
| 适用性复核 | `review-applicability-final.json`：8个安装输入在2ea6/b0cf/c097逐字一致；c097根复跑Spec21、Quality62 | 有范围的代码审查，不是整个新提交独立认证 |

精确Python收据：`~/.finance-runtime/test-receipts/20260921T103924Z-c097d712.json`，SHA256 `d5029c71714dde74f8f62b34a9c7e0bf5765a23d8a2535c45a2b7ca1f85cd093`。没有读共享latest、没有用零项嵌套收据。

Quality-827-01：安装器只验语法/Label/RunAtLoad，不验根路径语义。由受测源哈希、根身份与loaded后检兜底。Quality-827-02：bootout错误会在后续bootstrap暴露，并可能留下盘面/loaded不一致；本次先卸载两job并准备人工回退，仍不承诺跨job事务。

根会话补充限制：Quality stub记录的是plist路径，不是launchd的loaded payload；模拟断言不能替代本次实际 `launchctl print` 检查。

## 装机身份与回退

| job/角色 | 新配置 |
|---|---|
| sync 18:30 | sync/code root均 `~/.finance-runtime/finance-sync-adcda94b5e40` |
| finalize 20:40 | sync同上；generation=`finance-generation-adcda94b5e40`；L2/code=`finance-l2-adcda94b5e40` |
| 三根版本 | `adcda94b5e401158f1c3aa51f210e1e8d0f0b713`，发布后干净 |
| 未变 | plan=local、日历、Python/数据路径；S7 substrate418515c0；共享helper、S7 Python wrapper；旧指数补丁与18个L2/method文件 |
| 8792 | 保持他会话的 `f2c3e9e1a24f`；本轮前后PID/runs/配置和源码身份不变 |

六份备份在 `~/.finance-runtime/reviews/nightly-deploy-resume-20260921/deployment/backups/`；其中四份是本次可恢复目标，两份只是未变helper/S7 wrapper的参照。模式、哈希、命令及loaded全文见 `deployment/result.json`。回退逻辑在假文件/假命令上测试，真实发布没有失败，因此**没有实际执行回退**。

回退也必须先确认idle/锁与日历安全窗口，卸载两个job、只恢复四目标、bootstrap并核loaded旧值；不要重新执行已消费的 `controlled-release.py`，它是一次性发布记录而非新的安装入口。

## 选择与否决

| 方案 | 评价/结果 |
|---|---|
| 等资源空档、串行门禁、限制成功夹具保留 | 采用；降低共享磁盘峰值，但不声称阻止他会话并发 |
| 杀他人pytest/删他人树或失败staging腾空间 | 否；无归属和删除授权 |
| 旧21/25项探针拼成全量绿 | 否；c097另起完整全量，旧红原样保留 |
| 每次文档增量都冒称独立审查新签名 | 否；保留Spec/Quality原签名，只做明确范围的逐字适用性证明 |
| 普通合并新造未测SHA | 否；fast-forward使main就是受测对象，漂移则拒绝 |
| 为切换赶18:30或打断自然同步 | 否；等旧任务结束、重新核锁/库/版本 |
| 切配置时顺手修生产采集、重新跑当天 | 否；数据恢复是另一个有外呼/写入的动作，不在本次手动执行范围 |

## 后续与工具沉淀

- **配置部署已完成**；接下来分别观察20:40 finalize和下次18:30 sync的真实收据，核数据日与关键值非空，不把正常定时触发冒称本会话手动采集。
- 今日旧链路采集失败与readiness503仍需单独处理；若要当天补采，先明确授权，走canonical daily-full入口，不直写生产库或把staging强制换上去。
- 旧根、旧树业务产物、失败staging、审查/测试原件一律保留，未获删树授权。
- 本轮外部脚本是固定SHA、目录白名单的一次性验收/操作记录，正文已按原字节封存为`.py.txt`/`.zsh.txt`，不是新增通用部署入口。已有#814/测试收据工作线负责通用门禁，不另造竞争入口；harness-reference当前存在他人改动，本轮未接管或写回它。
- 可迁移方法：资源入场检查不是资源预留，需运行期监测；独立审查签名与明确输入范围的适用性证明分开；定时任务部署必须同时读盘面与loaded。尚未实现跨会话资源调度器，不能把这轮排队脚本说成全机并发门。
