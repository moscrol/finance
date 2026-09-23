# RAG 组合验收、持久化隔离与会话恢复去重

## 结论与身份

截至 2026-09-24 凌晨，本分支代码候选 `2ac97e68c480d5c419290b18f3fdc0529c46b40c` 的工程门通过，固定真实 Workbench 自然会话完成。**发布仍 HOLD**：候选及生产 readiness 均为 503，唯一关键红项是行情库 2026-09-22 与快照 2026-09-23 不一致。这里不替代发布线其他组合、金融 QC 或授权检查。

- 分支/作者树：`fix/rag-recovery-state-0923`，`/Users/a77/fwp-wt-rag-recovery-state-0923`。
- 已测代码候选父提交：`8f4a88ddad8492a6b590536d63d7942d70e5e9ac` 与主干 `c9dd71dfd678855b61662100ec74625b92ad1f1b`。
- `E=/Users/a77/.finance-runtime/reviews/rag-recovery-state-0923/`；本轮 `R7=$E/merge-readiness-20260923-07/`，R1 至 R6 同前缀换序号。
- 所有测试数只绑定各自 SHA。本文与 inflight 是后续文档，不把 `2ac97e68c` 收据移签给文档后继提交。
- 本任务未 push 金融分支、未合 main、未部署、未改生产配置/数据/索引。生产只读复核仍为 `3b7e473575b0ff2dea3c1088ba7b5e330e95c8e4`。
- 前序决定和原失败见 `2026-09-23-rag-glm-review-and-stderr-close.md`；该快照保留，不改成今日状态。

## 按发现顺序

1. stderr 关闭竞争修复后，补得 GLM 增量终稿；真实 Python 3.12.13 `KqueueSelector` 探针确认关闭的 stderr 正常注销，最终是类型化 `WorkerExecutionError/exited_without_response`。不把这项复现当作历史 2/3 秒超时的原因。
2. R1 固定 `34dd93f26` 完整工程测试通过，但主干漂移超过既有阈值。前向合流后 R2 固定 `06c82bfd0` 再验，不放宽 `--base-drift-max 5`。
3. R2 真实冷/热 RAG 可用，自然入口却在模型之前失败：沙箱拒绝向生产 `state/episodes` 写入，provider/tool 调用都为 0。这是验收侧车未隔离 Episode 持久化根，不是模型或行情错误。
4. `a71cbf20a` 在 source 生产 launcher exports 之后，强制设置 `FORESIGHT_EPISODE_STORE="$USERS/.episodes"`；保留 `FINANCE_WS`，让事实读取仍与生产同形。不取消沙箱拒写。
5. R3 独审要求修改：变异 runner 把 shell 当 Python compile，且假 Python 只展示环境，没有消费实际 resolver。原 SyntaxError、报告与取消收据保留，未把中止当全仓完成。
6. `9a299454f` 让 `.sh` 仅按六种明确 sh/bash/zsh shebang 做非执行式语法检查；其他文件保留 Python compile，未知 shebang 拒绝。侧车测试真实调用 `resolve_episode_store_root` 与 `JsonlEpisodeStore.writer`，核对落盘、锁及生产目录不变；增加两项撤保护。
7. R4 前端 E2E 为 33P/2S/1F：移动端 reload 后消息可见性 5000ms 断言超时。trace 中 bootstrap 为 3.648551 秒并有重复 artifact listing；41.5 秒是整例耗时。不能由此断言全部历史时序故障已归因。
8. `422def450` 在每次 `loadConversationData` 中建立局部、惰性的 artifact Promise；该轮各 run 共享一次请求。单独打开 run 仍独立读取，保留 related_run_id、publication 与 generation 检查。新增三项回归，旧实现 2F/1P，新实现 3P；未改超时断言。
9. R5 六个前端命令均 exit 0，但 build 改了被 Git 跟踪的静态包，整份收据 dirty/identity_stable=false，不能采信为固定提交门。把已测构建产物逐文件哈希核对后纳入 `8f4a88dda`，R6 对新 SHA 重建，静态包不再漂移。
10. R6 GLM 首次会话第五请求 502，CLI exit 0 但无终稿。原件保留，一次有界机械接续完成 `STATIC_PASS`。旧报告一处误称共享前后失败范围相同：宿主明确新实现会耦合本轮所有 bundle 的 listing 失败，这是有限可用性取舍，不跨恢复轮次缓存。
11. R6 工程及自然入口通过，但主干已前进到 c9。既有检查器按 `git rev-list --count --merges merge-base..main` 计数为 7，不能用首父链的 4，也不能数所有提交。原漂移 0 收据保留，固定新主干复核 exit 1；再合出 R7 `2ac97e68c`。#874 改动了交付状态接线，因此新组合重新跑真实入口与完整工程门。
12. R7 独审完成，仅覆盖相对 8f 的三处 Python 增量：共享状态排序、runtime 接线及新测试。前端源码实际提供了 48 文件，报告“没有前端源码”不准确；旁注纠正，不改原报告。helper 已覆盖 gap/missing 双向平局，不把报告解读成全部平局测试缺失。仍有一项非阻塞缺口：实际 runtime 的 blocked 业务态遇 incomplete 交付门，没有专门防止覆盖式接线复发的回归。
13. 收尾逐行读 `registry-check.yml`，发现四个 `build_registry.py` 命令之外还有 `audit_ledger_spec_crosswalk.py`。此前“完整 registry 叶”措辞过宽。对 R6、R7 各自在干净固定树补跑第五项，均 exit 0，另存带时间的收据；不冒称旧四项收据已包含它。默认 warning 仍保留，exit 0 不是零发现。

## 逐轮收据

| 轮次 / 候选 | 当轮事实 | 使用边界 |
| --- | --- | --- |
| R1 / 34dd93f26 | Python 14659P/85S/2X；前端/四项registry/撤保护通过 | 后续漂移 10>5，失去当时合入适用性 |
| R2 / 06c82bfd0 | Python 14677P/85S/2X；真实 RAG 可用；自然入口 PermissionError | Episode 根未隔离，不能签自然入口 |
| R3 / a71cbf20a | 独审 CHANGES_REQUIRED，runner 真实 SyntaxError；主动取消 | 没有完成全仓或 live |
| R4 / 9a299454f | 侧车修复独审通过；E2E 33P/2S/1F | 后续 Python/live/其余变异未执行 |
| R5 / 422def450 | 六个前端命令全 0，E2E 34P/2S | build 后树 dirty，整体 exit 2；后续未执行 |
| R6 / 8f4a88dda | Python 14686P/85S/2X；前端 123P、E2E 34P/2S；30 撤保护；真实自然入口完成 | readiness 503；后续主干漂移 7>5，严格复核 exit 1；第五 registry 步是收尾追加执行 |
| R7 / 2ac97e68c | Python 14895P/85S/2X；前端 123P、E2E 34P/2S；30 撤保护；registry 四命令加台账审计均 0；真实自然入口完成 | 工程门通过，readiness 503；并非其他未合市场 QC 补丁的组合收据 |

R7 Python 1722.88 秒，collected 14982，与所有结果计数对账一致。收据 `python/gate-V2JjH6EM/pytest.json`；Python 3.12.13、依赖指纹 `3328bed61f3e21ea`、dirty=false。从隔离树运行：

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python scripts/check_test_receipt.py \
  /Users/a77/.finance-runtime/reviews/rag-recovery-state-0923/merge-readiness-20260923-07/python/gate-V2JjH6EM/pytest.json \
  --expect-revision 2ac97e68c480d5c419290b18f3fdc0529c46b40c \
  --require-full-scope --base-drift-max 5 \
  --main-ref c9dd71dfd678855b61662100ec74625b92ad1f1b
```

结果 exit 0、漂移 0。收尾 fetch 后主干新增文档 PR #901 到 `5bf47a5ae9aa16768c0ef2df614177253764aeb6`，固定该 SHA 再检查为 exit 0、漂移 1≤5，另存 `python-receipt-recheck-final.{json,log}`，不覆盖原 c9/0 收据。合入前仍需 fetch 并固定那时的新主干，不能拿此历史检查替代后来的漂移检查。三组变异为侧车 2、启动 16、管道 12：逐项真实失败、无 collection error、还原后通过、基线/最终非空、源码哈希恢复。

发布线旧候选 `5213e9344b77e4094221734722b478705611a865` 的四个失败 ID，在 R7 完整 JUnit 中均通过：冷却、自愈、坏查询不退役、关闭 keepalive 线程。见 `release-failure-crosscheck.json`。两个候选不同，不能改签其 14903P/4F 或把本次成功当作旧失败原因；测试总数不同也不以总数大小判断覆盖，R7 已经全范围与 collected 对账校验。

## 真实入口与数据边界

- 固定同一用户、同一画像、同一长电科技先进封装问题；问题 SHA256 为 `f7ee0d82f064eeb0d15e569bad3fd41c2ad2492200d33f2047b8a4b260139fe0`。不把生产用户的问答正文复制进交接。
- R7 直接 BGE-m3 冷 hybrid 预热 43.419 秒；两次非缓存热查询 1.865/1.209 秒，各 6 个 `fresh` 命中，同一 worker model_load_count=1。cold/热预算仍为 360/90 秒。
- 实际 CLI 不支持可选 `--receipt`：首热 `persistent_worker_legacy`，次热 `persistent_worker`，两次均 `degraded=true`、`fallback_reason=legacy_cli_missing_receipt`。这是协议观测降级，不能拿自然答案的 content_degraded_count=0 覆盖它。
- 索引 source_dirty=true、built_at 2026-09-18，元数据前后哈希不变。`fresh` 是索引命中的状态，不等于今天的业务事实；未运行 `rag update`。
- R7 自然 run `run_20260923_232821_043591`，156.758 秒，真实 `glm-5.3-flash/zhipu`，provider_attempts=7、tool_calls=4、duplicate_queries=0。completed、答案非空、语义检查通过，内容降级/判官不可用/两类泄漏计数为 0。
- 隔离目录真实产生一个 Episode、29 个事件、writer lock，phase=done、序列完整、unreconciled_effects=0。用户、问题、run、会话身份逐项一致；sidecar worker queries_served 由 1 到 6。不是只看环境变量自述。
- 判官 correlated_judge=true。R6 是 repaired，R7 是 passed；两者都不是独立金融 QC，不证明普遍性能或金融质量提升。R6 指定修复标记消失也不等于完整语义审计。
- 新沙箱同时禁止写生产代码/事实根、KB/索引根、生产用户根、冻结运行根和生产 launcher。自有 live 进程已停止，launcher 哈希前后相同；没有给生产发模型题、重启、改配置或写数据。
- 生产只读 health/readiness 复核仍为 `3b7e473575b0`、503、market_data_consistency，库 09-22/快照 09-23。自然知识问答完成不能覆盖这条业务准入失败。

## 方案取舍

| 选择 | 否决 | 理由 |
| --- | --- | --- |
| source 生产 exports 后隔离所有已知写根，实际 resolver/writer 验证 | 改 FINANCE_WS、放开沙箱、假解释器只 echo env | 前两者改变事实读取或暴露生产写入，后者未触达真正落点 |
| 目标语言的语法检查，加真实撤保护失败 | shell 送 Python compile，把语法/collection 错当行为红 | 验证器必须真的执行被保护行为 |
| 单次恢复内惰性共享 artifact 请求 | 全局缓存或延长 E2E 断言 | 限制跨用户/会话陈旧风险，减少可证实重复工作；接受同轮失败耦合 |
| 构建产物入新候选，再重建验证零漂移 | 六条命令全 0 就签旧 dirty 树 | 收据必须描述实际构建后的整棵树 |
| 原报告与宿主裁决分文件，终稿有界接续 | 覆盖旧错误或 CLI exit 0 当完整独审 | 中断、错误依据、真实覆盖范围都可回溯 |
| 用既有检查器的 --merges 定义 | 首父链、全部提交数、临时放宽阈值 | 同名“漂移”不同分母会给相反准入结论 |
| 逐条读完整 CI 作业 | 按“四个注册表命令”标题替代叶子清单 | 同作业后来新增台账门，标题不足以描述实际执行要求 |

## 证据与工具归位

R7 的 `gate-summary.json` 汇总工程、live/readiness 和边界；`frontend/frontend.json`、`python-receipt-check.{json,log}`、三个 `*-mutations/results.json`、`registry-receipt.json`、`ledger-crosswalk-receipt.json` 各保留原身份。R4/R5 的 `gate-closeout.json` 明确后续步骤未执行。R6 `gate-summary.json` 同时保留旧成功与后续漂移失效，不能改签。

`static-review-coverage.json` 索引六份分别绑定版本的 GLM 静态报告；8f 到 2ac 的比较范围有 1286 个不变 blob、三处已审 Python 增量。它不是新签一份全仓审查。压缩浏览器 bundle 没有独立源码审查，使用新 SHA 干净可复现构建单独证明；相关旁注在两轮 `static-review-host-adjudication.json`。

可复用的诊断插件、shell-aware 变异 runner、侧车测试与变异定义均已进本仓。复用既有 `run_main_gate.sh`、`run_frontend_gate.py`、`smoke_workbench_self_use.py`，不复制另一套正式门禁。私有 live/GLM 封套固定本机生产形状、用户与沙箱，只作为可重放的受限证据案例保存，不在没有跨环境验证时升格为通用工具。

持久化隔离的通用经验已落 harness 独立分支 `docs/sidecar-persistence-0923`，提交 `65c3b43`，BUILD/KIT 同步并已推 Gitea；未合 main，未改其主脏树。

## 授权、交接与下一步

1. 发布线负责人为 `fwp-wt-workbench-release-0923`，恢复负责人为 `fwp-wt-market-recovery-qc-fix-0923`。提供本地代码候选和上述收据，由其与尚未合入的市场 QC 补丁组成最终候选再验；不直接拿 2ac 代替对方完整组合。
2. 已读发布线交接及保存的 PR #861 评论 6463 原文：五问三合同已经受用户委托裁定，不应重问这些业务口径。但该评论明确不包含生产恢复/换库，指向工单 #61 第 5 步起的另一次发布授权。发布负责人应核对其已有“执行”授权的具体范围，不能从口径裁决推导任意生产写入许可，也不宣称别的授权不存在。
3. 行情恢复走正式 staging、逐日/逐列及下游门，不从此 RAG 分支补跑同步、改日期、造平盘 bar 或发布旧 staging。原 21:05 same-day-gate/finalize exit 2 留存。
4. 最终组合各叶、readiness、适用自然/金融验收与授权都满足后，才按验收规程可回滚部署。本文档后继提交与任何后来的主干/数据变化，均须用届时的真实收据核对。
5. 历史 d29 的 430P/1F、80P/3F、2/3 秒超时及生产 CLI 偶发探测超时仍独立保留；资源压力或今天的绿不能替它们作因果解释。原件、他人树、生产数据与索引不得覆盖。
