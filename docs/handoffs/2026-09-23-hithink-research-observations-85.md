# #85 同花顺研究观察值：429 离线候选

## 状态与身份

工程实现已提交，验收未收口，不能合入或部署。WIP **PR #894**，分支 `fix/hithink-research-85`，承接 #810，不修改其原分支或关闭原 PR。

- 前向基线 `gitea/main@626d8a508c1c988ff094110b371987e6afdcdd15`；#810 远端尖 `7596751d82e2` 是本候选祖先。
- `86a2ce463` 前向合并，仅 lessons 追加式冲突，保留双方；主检出树 L2 未提交覆盖层没有带入。
- `659ce1a1e` 带入既有 `dd2fae334` 退避实现；`8354703c9` 补局部 partial；复核后 `1b3ee2a3b` 修复重试边界并保留原 4001 语义；`0f0231553acf788e7d42440ce54d3d101fdca187` 补齐 partial 发布保护，是最终冻结代码身份。
- 冻结独占树：`/Users/a77/.finance-runtime/reviews/hithink-research-85-20260923/candidate-final`。代码基座固定，后续文档提交不是该收据的 revision。
- 证据根：`/Users/a77/.finance-runtime/reviews/hithink-research-85-20260923/`。

## 发现与决定

先确认研究请求已经逐次落 pending/failed，缺口在外层：一个估值请求限流会导致后续热度请求完全不发出。随后复核带入的客户端，发现睡眠累计被称作墙钟预算、Retry-After=0 没有次数边界，以及 4001 被转入新预算。新增 7 条边界测试先红，再修复。

| 方案 | 裁定与原因 |
|---|---|
| 捕获全部异常后继续 | 否。日期、格式、数据范围和写入错误必须继续失败关闭，不能用 partial 掩盖数据契约错误。 |
| 429 耗尽用类型化异常 | 采用。`HithinkRateLimitError` 是 `HithinkAPIError` 子类，研究编排只对它局部降级；请求表保留 failed，结果 missing 记录 kind/request_id，原参数可按 request_id 追溯。 |
| 429 与 4001 共用新预算 | 否。#85 要求不改 4001；恢复其 retries 次数和等待阶梯，4001 耗尽仍抛普通 API 错误。 |
| 只累计 sleep / 只设秒数 | 否。请求本身耗时漏算，零等待可以无界循环。使用 monotonic 截止与 MAX_RATE_LIMIT_RETRIES 双界；无效/非正 Retry-After 回退指数等待。 |
| 宣称硬网络截止 | 否。预算约束重试准入，剩余时间传给 socket timeout，不强制中断在途响应读取。每个逻辑请求独立预算，不是整个采集轮的总时限。 |

收尾追踪调用链又发现 CLI 输出 partial 却返回0、旧单体包装无条件 ok=true，夜跑会把缺口当作成功。先以 `partial-exit-red.log` 两红、`partial-monolith-red.log` 一红复现，再补上契约：CLI 部分完成返回3，夜跑仅对研究命令把3映射为 partial；其他命令非零仍失败。三类研究请求仍全部尝试，夜跑重试后仍有缺口时按原规则阻止导出/换库。旧单体在采集全部尝试完成后转失败并保留 missing 请求ID。不是允许残缺结果发布。

HTTP 429 先于 JSON 解析识别；HTTP/业务码两形态均退避，支持 Retry-After 秒数/日期，单次等待封顶。非有限/负预算在外呼前拒绝。异动、估值、逐股热度任一 429 耗尽后继续其他请求；即使全限流，partial 也不表示取得数据，必须看 requests/missing。空集、缺值仍为 complete_with_gaps，不伪造数据。通用 API 错误不再拼入上游 message。

## 验证与限制

| 范围 | 结果与证据 |
|---|---|
| 最终代码定向门禁 | **130P / 0F / 0E**，全仓 Ruff 通过；`targeted-final-gate.log`，原生收据 `final-receipts/gate-3GXIgpu2/pytest.json`，dirty=false。`check_test_receipt --expect-revision 0f0231553 --base-drift-max 5 --require-target tests/test_hithink_research.py` exit0。仅八个测试文件，不是全量。旧1b3ee2a3b的118P收据保留，不移签。 |
| 429 阳性对照 | 仅进程内 MAX_RATE_LIMIT_RETRIES=0：HTTP 两次429再成功、业务429再成功两针 **2F**，恢复正常进程 **2P**；`final-positive-control-red.log` / `final-positive-control-restored.log`。不改磁盘源码。 |
| 注册五项 | `final-registry-*.log` 全部 exit0；冻结树只有本仓在场，跨仓项按工具规则跳过。作者树同代码另跑含邻仓五项通过；台账反向 98 条 warning 保留，不冒充零警告。 |
| 提交钩子 | ruff、layer、path、unread-fields、dataset-registration、tool-reachability 通过；dataset 不含生产空表审计。 |
| 合并预演 | 对上述 main 无冲突；不是合入授权。 |
| 生产只读对照 | `production-stat-before/after.txt` 与 `health-before/after.json` 相同：数据库 size/mtime/inode、plist、runtime 链接不变；8792 source_revision=3b7e473575b0，code_matches_repo=true。仅证明这段定向验收窗口，不补造开工前证据。 |
| 全量 Python / 前端 / E2E | **未执行本候选完整门禁**。21:21 load86、磁盘约10GiB，其他两套全量及两套前端在跑；21:33 load60仍有两套全量，证据 `load.txt` / `disk.txt` / `concurrent-gates.txt`。不继续叠加重型任务，不动他人进程。 |
| 独立 Spec/Quality | **未执行**，交 #75 队列；作者测试不是独审，没有用户豁免。 |

较早的扩大范围测试在工具120秒截止时中止，无完整结论；之后118P完整重跑通过。接线补丁阶段曾把导出测试文件名写错，pytest exit4/no tests，纠正为实际 `test_review_sync_export_release.py` 后70P，最终冻结树再跑130P。先红的7针收据 `~/.finance-runtime/test-receipts/20260923T131751Z-8354703c-28c6ffef2d99.json` 保留。旧164b02e4全量不移签。

代码地图 query 的结构层 refused_empty、叙事 missing，只用具体源码定位，不作全仓架构结论。没有新增通用审查工具，复用原生门禁/收据；边界测试归仓，不把一次性日志当产品能力。

## 后续与部署草稿

1. Gitea创建接口30秒/90秒超时后，按head回读最终确认PR #894已打开，代码头0f0231553。网络超时不等于远端动作未发生，先回读再重试。待资源允许，在最终 PR head 的干净独占树跑完整 `bash scripts/run_main_gate.sh`、`scripts/run_frontend_gate.py`（含 E2E）及 registry；收据绑定同一 head，再交 #75 独审。
2. 用户确认后才能合 main。保持 #810 和本候选 WIP，接替关闭另留指针。
3. 部署另立单。当前 installer 只复制模板，**不会自动按 HEAD 改 FINANCE_SYNC_CODE_ROOT**。先准备包含已合 SHA 的 sync 快照、审过的 plist 发布源，并确认生成根/L2 根及现役覆盖层不回退，才能使用以下命令。本轮一条也没执行：

```bash
# DEPLOYMENT_SOURCE 必须由后续部署单明确，不是当前开发树。
FINANCE_OPS_REPO="$DEPLOYMENT_SOURCE" /bin/zsh "$DEPLOYMENT_SOURCE/scripts/install_eval_launchd.sh" --nightly-only --dry-run
# 预览通过且再次获用户授权后才可去掉 --dry-run；不得加 --kickstart。
FINANCE_OPS_REPO="$DEPLOYMENT_SOURCE" /bin/zsh "$DEPLOYMENT_SOURCE/scripts/install_eval_launchd.sh" --nightly-only
```

不做 live sync、不写生产库、不重载 launchd、不切8792、不删数据或他人树。默认预算不保证覆盖实测7至9分钟限流窗口，也不宣称恢复夜跑效果。
