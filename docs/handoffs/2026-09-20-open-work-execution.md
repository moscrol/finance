# 2026-09-20 在途工作收尾执行

本轮执行用户附件中的修正意见。金融源码三批已进入 main，保全、显式推送、ReAct 归档、研究站预检修复和研究切片立单已完成。KB 维护链的最终身份与独立验收见下文。未删除工作树，未切换 8792、生成生产快照或索引防写。

执行文档枝：`docs/open-work-consolidation-0920`，审阅入口 [#789](http://127.0.0.1:3300/a77/finance-workspace-private/pulls/789)。实际动作和失败原件的小包在 [执行证据](../verification/2026-09-20-open-work-execution/README.md)，完整外部运行根为 `/Users/a77/.finance-runtime/open-work-execution-20260920/`。表中的数量均属于记录中的采样时刻，不能用于当前批量操作。

## 先保全，再处理已提交成果

最初 52 棵金融脏树的旧保全目录已存在，但 push 无法保存其中未提交的改动。先核旧保全，再补采 52 棵可读脏树的 status、暂存/未暂存二进制 diff、未跟踪清单和允许原件；166 个允许文件复制并核哈希。16 个已登记路径的 Git 元数据不可用，保持原状。大文件、数据库、敏感配置等只记身份，不把它们当作已有 Git 副本。

固定显式名单后，55 条金融分支逐条正常推送并回读远端 SHA；改用 Python 参数数组，消除 zsh 将 `$b:refs/...` 的 `:r` 误作修饰符的问题。harness 的 5 条分支同样推送核验。KB `baseline/ashare-coverage-gap@472d87b7` 在推送前另保全其 748 个允许未跟踪文件。所有原脏树都保留，没有把未提交原件写进别人的提交。

ReAct 归档枝 `docs/react-components-comparison-0918@87c719f8` 已提交推送：44 个 Git 文件、42 条归档记录和 5 条外部记录。SQLite、pyc、锁、两份超 5120 KiB 的 history JSON 留在原运行目录，由 manifest 保存原路径、大小和 SHA256；没有拆分大文件绕过门禁。已归档原件逐字节一致。

## 纠正发布预检的因果

金融仓 `/Users/a77/fwp-wt-main-docs` 的 main 原先落后，快进后最终与远端 `4ace5ec2` 一致。这是工作区维护。

实际公众号预检在研究站 `/Users/a77/finance-research-site` 执行，那里 main 原先领先 1 个提交 `9f60bef`。既有稿件通过站点 validate 和文章 lint 后正常推至 Gitea main；真实 `/Users/a77/公众号/pipeline/steps/00_preflight.sh` 返回成功。没有把金融仓快进当作该修复的原因，也未继续执行后续内容发布。收尾时研究站另出现 `.workbuddy/` 未跟踪目录，属于其他工作的现场，本轮未改动。

## 生成根先独立复核，再串行合流

守卫枝包含共同基础 `0f6c2810` 和生产守卫 `387028b8`；stage 枝与它互不为祖先，独有两提交只是交接文档。因此只采用守卫源码线，stage 标 superseded，部署枝随后接入。

原七项探针通过，独立审查仍发现 `ALERT_LOG` 软链可把告警写进代码根。修复启动器后，合流部署代码的真实 shell 又暴露另一层：子进程拒绝后，父 shell 继续调用 receiver 或补发告警，仍能写入代码根。完整入口四例在 `f2342fda` 为 1P/3F，修复后为 4P/0F；合法外置告警对照仍通过。原失败报告与输入完整保留。

最终修复在通知器 mkdir/open 前检查两个代码根，并让 nightly 父 shell 在启动器非零时立即结束后续接收/告警写入。回归入口 `scripts/review_probes/check_generation_finalize_boundaries.py` 已进入正式代码；它使用临时小根和固定代入步骤，不写真实生产库。

## 实际合并与固定提交收据

| 内容 | main 中被测提交 | Python 全量 | 其他叶子 |
|---|---|---:|---|
| #788 零计数收据守卫 | `becb68c0dd3105abbbcc1f92a917dbde224de24b` | 11488P / 0F / 85S，另 2 xfail | ruff、前端四项、E2E 34P/2S、registry 五项通过 |
| [#795 同花顺](http://127.0.0.1:3300/a77/finance-workspace-private/pulls/795) | `ec92b31b5300bbbb4abc64e41f96854f1438aea0` | 11707P / 0F / 85S，另 2 xfail | 同上 |
| [#796 生成根及部署接线](http://127.0.0.1:3300/a77/finance-workspace-private/pulls/796) | `4ace5ec2e9b7735d90eb15bc2351fa193c1120b8` | 11815P / 0F / 85S，另 2 xfail | 同上；完整入口额外 4/4 |

全部来自独立、无生产库、干净的固定检出，收据 revision 与基座漂移校验通过。同花顺术语冲突逐节保留双方有效内容，pathspec 只约束提交范围。跨仓 registry 固定 KB `1254224be` 和研究站 `f606583`，没有借用当时会变动的姊妹仓工作树。

#788 首次 E2E 因只改端口、漏改配套 URL 而失败；仅修外部测试环境后重跑整片通过，`frontend.json` 中的原 exit 1 没有改写，最终组合结论单独留档。代码正常快进进入 main 后 Gitea 没有自动标 merged，仓库也禁用 manually-merged；留下替代提交和收据指针后关闭 PR，没有改仓库选项。#795/#796 均为 API fast-forward-only 且远端 SHA 回读一致。

生成合流曾有质量夹具缺行情列，补夹具并增加真实全 NULL 拒绝例，生产规则未放松。`dca1bd6e` 的注册表指纹未刷新，第一次 Python 全量主动中断 exit 2；修正注册表后在最终 `4ace5ec2` 完整重跑，未将中断结果算绿。

## KB 维护链

[KB PR #155](http://127.0.0.1:3300/a77/knowledge-base-private/pulls/155) 已交付实现，最终提交 `3a21010323eababb54ce8519093fd60dbacb9451` 已推送、工作树干净；相对受审代码 `7e07addb466385085e21ccaf3d06bf23c6e4b0a1` 只涉及四份文档。该新增 PR 保留待合，知识库 AGENTS.md 要求合回 main 另经用户确认；现有生产保护保持不变。

维护入口 `scripts/ingest.py rag-maintenance` 将 hook/ingest 刷新改为请求，使用内核单写者锁；每代冻结代码、资料、普通和全文两份索引。允许源文件集合独立形成分母，核全部向量、证据字段及精确隔离名单；批准后只切一个 current 指针。消费者一次绑定同一清单，真实金融 PersistentRagWorker 用例覆盖双份热查询、旧进程退役拒绝、关闭及新进程查询。`launch` 也清掉金融侧优先级更高的旧 `VECTOR_INDEX_DIR`，避免传了新根却仍读旧根。

安全整代 publisher 已实现：只接受批准清单、显式匹配仓库和绑定标签，不触发旧构建、不覆盖已有资产；上传后回读整包 SHA 和最终 tag SHA 才生成成功收据。实际网络上传没有执行，远端导入仍关闭。本轮工程测试使用临时小索引、确定性 hash 编码器和传输替身。

验收及其边界：

- 受审代码 `7e07addb` 和最终文档提交 `3a210103` 均完成 911P/0F/0skip，以及 strict-vocab、文件大小和质量门禁；固定金融消费者为干净 `4ace5ec2`。最终全量 55.65 秒。词表仍有 2 个存量警告，质量门含义为 `no_regression_with_debt`，没有宣称历史债务已清零。
- 独立 Spec 动态验收归属 `1bd5e1dc` 及更早：61 项定向、原无绑定未批准/退役查询、save 默认写入、根重叠及五个控制边界反例关闭；该组金融副本为 `dca1bd6e`，不混称作者的 `4ace5ec2`。最终 `7e07addb` 的 Spec 增量、Quality 均为独立静态复核，引用作者正式回归和完整收据。
- Quality 首次确认 activate 在根/锁身份变化后仍写 current。平台随后以可能网络安全风险中断该独立审查；中断记录保留、未记绿。后续只读源码/既有证据复核，作者补正式 pytest 回归及各成功控制写入前的身份检查。原独立动态探针没有在最终新 SHA 重跑。
- 原失败未覆盖：37437 的未绑定消费/默认保存，ea7 的控制清单软链、失锁异常写与上传中改标签；成功控制写入首红 8F2P、首修 1F77P。名称带 `green` 的历史日志仍是 1F77P，真正最终定向 80P 见 `success-control-final-focused.log`。

[KB 日期交接](/Users/a77/kb-wt-guarded-maintenance-0920/docs/handoffs/2026-09-20-kb-guarded-maintenance-acceptance.md) 和本包 `kb-maintenance/acceptance-3a21010323eababb54ce8519093fd60dbacb9451.json` 保存源码/文档身份、四命令退出码、日志哈希及审查范围。没有新建真实大索引、解除 uchg、恢复已安装旧 hook 或重启 8792；整个 Workbench Episode、结果缓存清退、真实 BGE 检索相关性及回答质量仍需生产切换阶段单独验收。

## 研究工单与陈旧看板

五个研究深度切片已按优先级建立：[查询报错闭环 #790](http://127.0.0.1:3300/a77/finance-workspace-private/issues/790)、[集合与排序忠实 #791](http://127.0.0.1:3300/a77/finance-workspace-private/issues/791)、[方法论/观测卡 #792](http://127.0.0.1:3300/a77/finance-workspace-private/issues/792)、[板块比较合同 #793](http://127.0.0.1:3300/a77/finance-workspace-private/issues/793)、[预览按需展开 #794](http://127.0.0.1:3300/a77/finance-workspace-private/issues/794)。各单有范围和验收条件。

#23 判官 token 记账、#24 checkpoint rule_id、#25 历史重放实际已有实现，不重复立单。#25 原 PR #597 留下 main 替代指针后关闭；#23 的生产样本和成本观察边界仍保留。vault 的七条陈旧记录逐行标 superseded，并保留旧文字和替代指针。

## 清理结论与剩余授权边界

清理快照覆盖 322 棵金融工作树，51 棵脏树、16 棵元数据不可用、9 棵 SHA 不可重建；这些数只属 01:57–02:01 的采样。核了 launchctl 实际引用、进程参数、运行链接、部署台账、远端可达性、PR 以及文档/收据/manifest 路径。初筛 28 棵干净 detached 候选仍待逐树认领，其中 9 棵又查到被忽略的 SQLite、台账或本地配置。可重建 SHA 不能证明这些产物可重建。

[清理表](../verification/2026-09-20-open-work-execution/cleanup-review.md)和[认领表](../verification/2026-09-20-open-work-execution/cleanup-owner-review.md)已交付；没有收到认领结果，全部保留，本轮删除数 0。完整引用 JSON 超过文件门限，留外部并记录哈希。即使以后认领，也须重新核现场和处理被忽略产物，不能直接使用这次快照执行删除。

q/research-data-readiness、#783 和 #770 没有因工程绿合入。q 仍缺有效 T3 外审窗口、预算和独占根；本轮未启动付费模型外审。

生产仍为 8792 的 `bf662e93`、生成根 `387028b8`、L2 根 `d433b907`；双索引目录及各 12 个文件的 uchg 保留。探针临时 L2/生成根都用了新通知器，而装机 L2 仍是旧版，因此本轮源码通过不能宣称生产告警边界已修复。正式部署须核两个根的通知器版本并保留 L2 业务代码，连同备份、启动、health/readiness、双索引、热 worker、真实 Workbench Episode 和回滚单独验收。

## 关键选择与被否方案

| 选择 | 被否方案 | 原因 |
|---|---|---|
| 未提交原件先独立保全，提交分支后推送 | 把 push 当作整个工作区备份 | Git 不包含未提交和被忽略文件 |
| ReAct 大文件/禁类留外部、记身份 | 整包提交或拆分超大 JSON | 保存来源同时遵守仓库文件门 |
| 守卫源码唯一候选，随后接部署 | 连续机械合并两条等价生成线 | stage 没有独有业务代码，额外合并增加误判 |
| 父 shell 同样执行失败终止 | 只修 Python 启动器 | 子进程的拒绝不约束父进程的副作用 |
| 新双索引整代验收、批准后单指针消费 | 原地顺序更新两份或只依赖 hook 锁 | 读者可能遇到混代，直接 writer 还可绕过 hook |
| 保留清理候选并逐树认领 | 按干净数量批量删树 | 引用和 Git 外产物都可能是唯一副本 |

可迁移的父/子进程门禁教训已补入 `agent-memory/10_knowledge/gate-covers-only-its-return-value.md`；能力状态更新原能力图，没有建立第二份清单。领域完整入口探针已入源码；本轮显式名单/限定路径的审计脚本以原文和哈希封存，不将一次性执行名单提升为新的跨项目接口。

能力图最终静态审计 exit 0：84 行、216 条断言无漂移，另 165 条在途/未校验，不能据此宣称全部能力已部署。项目索引与方法论已推送到 agent-memory，最终记忆提交 `26d9e34f`。
