# #60: 固定版本通过，但并发 main 使发布范围成为阻塞

## 背景与本次边界

用户要求继续推进到可部署。本轮已按固定head/base授权合入#887，实际merge为 `0525e780e0435d44d0f47455ef604325e1a65258`；安装、服务重载、kickstart、8792切换及生产写库仍未授权。较早的 `2026-09-23-eastmoney-deployment-ready.md` 是0525通过时的历史快照，不是本轮最新放行结论。

本文件只记后续发现与裁决。证据根为 `~/.finance-runtime/reviews/eastmoney-cb-deploy-20260922/`，滚动入口是其中 `candidate.json` 与 `deploy-steps.md`。

## 发现顺序

1. #887实际merge完成完整四叶、native/JUnit对账、最终dry-run及只读加载状态回查。0525收据是14620P/0F/0E/85S/2X，collected14707，前端120P、E2E34P/2S、registry五项。最终封存检查发现main已由#888推进到b59，停止旧身份放行。
2. 审#888有效增量：一份测试、两份交接。未改生产代码或模板，但测试增加一个参数化case。独立检出b59跑完整四叶，18:59:41结束：14621P/0F/0E/85S/2X、collected14708；前端/registry通过。native收据与JUnit复核覆盖相关96项及两态timeout。没有把0525收据改签。
3. b59执行期间，18:48:32 #886合入，main变为f47。六份文档变化，生产代码/测试/模板零差。核查#886记录及在跑验证的实际revision，未找到可复用的f47精确完整收据。规程明确要求当前main SHA全等，base-drift上限不是身份豁免，故独立跑f47。
4. f47于19:07启动，19:39:40全量结束：14621P/0F/0E/85S/2X、collected14708，Ruff/exit0；frontend六步、E2E、registry均过。没有缩收集面或放宽时间容差。
5. 19:33起其他批次连续合入#853/#857/#804/#840/#849/#836/#891，main先到e926；19:46又有#889合入，核验时main为 `626d8a508c1c988ff094110b371987e6afdcdd15`。增量含报表读取逻辑和新的pre-commit门禁，不再是纯文档。没有自动纳入这些新代码，也没有为新tip启动另一轮追逐式全量。
6. 继续完成固定f47源的只读预演及独立收据核验，19:46:43生成 `fixed-revision-verification.json`。该结果同时记录固定版通过、当前main准入exit1、需要发布范围确认。没有生成冒称当前main通过的 `verification.json`。

## 当前已验证对象

| 对象 | 身份与结果 |
| --- | --- |
| 固定装机源 | `~/.finance-runtime/finance-nightly-installer-f47d464eb7af`；SHA `f47d464eb7af32157c331bf2a6bf1b337acbb43f`；tree `3830a3dcff8571e6133efe53bd3b2fb7b38c7ca8` |
| 同步运行根 | `~/.finance-runtime/finance-sync-2edbe4c46595`；SHA `2edbe4c46595cbea3eb3abe04fe84a7bd5afd55e`，模板仍旧，不能从它安装 |
| Python环境 | 主树 `.venv-workbench/bin/python`，3.12.13，依赖指纹 `3328bed61f3e21ea`，无绕过 |
| full receipt | `current-main-f47d464e-20260923/postmerge/python/gate-R7ypefYy/pytest.json`，仅签f47 |
| 相关覆盖 | wiring33、installer20、breaker18、transport19、snapshot6，共96；另含timeout两态2项 |
| 前端 | 六步全部exit0，120单测，E2E34P/2S；revision、首尾clean/stable、六日志hash复核 |
| Registry | 五项exit0，保留98条既有非阻断反向引用warning |
| dry-run | 固定f47源，两个任务、四个目标，无复制、无服务变更 |
| loaded回读 | 19:44:05任务参数/选定环境与磁盘一致；仍旧同步根，两任务当时idle、锁不存在 |
| 文件不变 | 三轮准备快照到最终预演，六个已安装小文件hash/mode相同 |

安装器、两plist、两launcher与共享helper的文件差分从f47到626仍为零，但这只证明指定文件无差，不等于新main全量通过。后续批次未完整审查。fixed版本检查与当前main准入分开报告，后者仍拒绝。

## 裁决与被否方案

| 方案 | 评价 | 结果 |
| --- | --- | --- |
| 把旧收据移签到新的main | 版本不同，完整范围证明不成立 | 否 |
| 因文档零生产差分、或扩大base-drift数而跳过SHA全等 | 基座漂移与revision一致是两个不同条件 | 否 |
| 继续自动追每一个main并反复全量 | 已多次改变对象，新批次又包含运行代码；本会话不能控制其他合入者 | 暂停，请用户定发布范围/窗口 |
| 明确固定f47为#60本次发布版 | 全套代码验证与只读预演齐全，部署目标仍是固定2ed运行根；不冒称最新main绿 | 建议，待用户确认 |
| 暂停并发合入后验选定的新main | 保持原最新主干准入含义，但需要协调稳定窗口 | 可选，待协调 |

## 后续与禁止事项

先让用户明确选择固定f47发布，或协调稳定窗口后验证新main。版本冻结确认不等于安装授权；不得把本记录当作现行current-main规则的隐式豁免。

正式安装还需单独授权，重新核源码/运行根身份、解释器/依赖及hash，检查两个任务、锁与其他写者，在远离18:30/20:40的空闲窗口建立逐目标新备份。准备快照不是回滚点；共享helper不得静默升级；禁止旧Plan B、热补、自动kickstart。运行根不能充当装机源，失败按本次逐文件备份处理。

本会话没有安装、重载、切8792或写生产DB。真实请求时序、跨进程预算、实际行情恢复未验证，#61未捆绑；#60不可提前标生产验收完成。传输计数包含连接失败，不包括熔断跳过、DNS、自动重定向，不是抓包请求数。

## 留存与工具盘点

0525阶段92个证据文件、b59阶段74个证据文件已分别SHA256封存并验证；原始红和环境失败材料不改写。已完成的本会话Python/frontend验收树、绿色basetemp清理，固定源与运行根保留；复放native工具需恢复对应revision/环境，不能改原收据。

f47的原始日志、独立复核、预演和漂移证据在 `current-main-f47d464e-20260923/`；封存清单为该目录的 `SHA256SUMS`。本地文档提交不推送，远端已验收候选身份不变。

复核复用既有 `check_test_receipt.py`、`run_main_gate.sh`、前端门禁与gitea_pr；本次固定路径/批准差异的证据适配脚本长期保存在树外证据目录。没有另建发布框架或放宽门禁。缺的是跨会话发布范围/窗口决策，不能靠再加一层自动校验替代授权；资源观察只记事实，不作性能趋势判断。
