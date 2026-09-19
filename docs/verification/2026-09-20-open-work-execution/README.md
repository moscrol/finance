# 在途收尾执行证据

这些是 2026-09-20 本轮执行的原件小包。`manifest.json` 记录每个归档文件的原路径、字节数和 SHA-256；原始失败与修复后结果分开保留。运行根为 `~/.finance-runtime/open-work-execution-20260920/`。完整清理 JSON 含逐树全部文档引用，超过 5120 KiB，只在 manifest 的 external_files 记哈希、保留外部原件；可读清理表与忽略产物清单入仓。

## 已完成的源码合并

| 分支 / 合并记录 | 被测且进入 main 的提交 | Python 全量 | 前端 / E2E / registry |
|---|---|---:|---|
| #788 零计数收据守卫 | `becb68c0dd3105abbbcc1f92a917dbde224de24b` | 11488P / 0F / 85S | 前端四项通过；E2E 修环境后 34P / 2S；注册表五项全 0 |
| #795 同花顺接线 | `ec92b31b5300bbbb4abc64e41f96854f1438aea0` | 11707P / 0F / 85S | 前端四项通过；E2E 34P / 2S；注册表五项全 0 |
| #796 生成根守卫与部署接线 | `4ace5ec2e9b7735d90eb15bc2351fa193c1120b8` | 11815P / 0F / 85S | 前端四项通过；E2E 34P / 2S；注册表五项全 0 |

三份 Python 收据均来自无生产库的干净固定检出，revision 校验与基座漂移 0 检查通过；ruff 均通过。跨仓 registry 统一固定 KB `1254224be89e2c4974350b7f3e985dbedb5dc043`、研究站 `f606583867fe1cad8de96b06be1dd6cfe2b57e51`。全量日志另有 2 xfailed，不记为通过条数。

#788 代码采用正常 Git 快进进入 main，Gitea 未自动识别为已合并；仓库禁用 manually-merged。没有修改仓库选项：PR 留下替代提交和验收指针后关闭，不能描述为 API `merged=true`。#795、#796 使用 Gitea fast-forward-only，API 和远端回读均确认被测 SHA，源分支保留。

## 必须一起读的失败记录

- #788 的 `gate-788/frontend.json` **保留第一次 E2E exit 1**。原因是设置 `RE06_E2E_PORT=18984` 后遗漏配套 URL，测试访问了 8794。测试源码未改，外部环境补 `RE06_E2E_URL=http://127.0.0.1:18984` 后整片 E2E 通过。最终组合结论见 `gate-788/frontend-final-verdict.json`；新结果及完整日志均在同目录，原浏览器 trace 留运行根。
- 原 `387028b8` 七项探针通过，但独立新增反例发现告警日志软链接能写回代码根。修复后，部署合流又暴露父 shell 在启动器拒绝后继续执行 receiver/补发告警。旧独立报告保留；`generation-spec-dca1bd6e.md` 与 `generation-standards-dca1bd6e.md` 给出关闭依据。
- 原完整入口四例在 `f2342fda` 为 1P/3F；同输入同断言在 `dca1bd6e` 为 4P/0F，最终 `4ace5ec2` 的入仓探针再验 4P/0F。同时保留原七项及合法外置告警对照，不靠关闭全部告警求绿。
- 合流定向测试曾有三条质量夹具 BinderException：新主线的空壳行情查询需要真实行情列。夹具补列与正常值，另加 local 全 NULL 拒绝例；生产质量规则保留。
- `dca1bd6e` 的 registry 发现 wrapper 指纹未更新；Python 在 59.70 秒主动中断并保留 exit 2。使用冻结跨仓根重新生成注册表，仅时间戳及本 skill 的 computedHash 变化，随后最终提交完整重跑。不能把中断窗口算作全量通过。

## 保全、发布与工单

- 校验旧 52 棵金融脏树保全，补采 52 棵可读脏树，允许的未跟踪文件 166 份逐字节复制；16 棵注册路径的 Git 元数据不可用，保留待查。完整 status、二进制 diff 和副本留运行根，不能凭已 push 就删原树。
- 金融 55 条、harness 5 条以及 KB `baseline/ashare-coverage-gap` 均按显式名和固定 SHA 正常推送、回读核验。KB 分支的 748 个未跟踪文件先另做保全；不把未提交内容当作已推送。
- ReAct 允许原件在 `docs/react-components-comparison-0918@87c719f8`：44 个入仓文件、42 条归档记录、5 条外部记录。SQLite、pyc、锁与两份超 5120 KiB 的 JSON 保留外部原件，由该包 manifest 记录身份。
- 研究站 `9f60bef` 校验后推入其 Gitea main，真实公众号 `00_preflight.sh` 通过；金融 main 快进单独记作工作区维护，不把两个仓混为一因。
- 研究深度五单见 `research-depth-issues.json`（#790–#794）。旧工单 #23/#24/#25 已实现进入 main，不重复立单；七条 vault 陈旧行标 superseded，旧文字仍在。

## KB 维护链候选

KB [#155](http://127.0.0.1:3300/a77/knowledge-base-private/pulls/155) 已实现并推送最终文档提交 `3a210103`，受审代码 `7e07addb`；未合 KB main、未部署。两次固定身份均 911P/0F/0skip，词表/体积/质量门全 exit 0；质量仍有历史债务，词表仍有两条警告。最终收据、完整门禁日志、各轮独立报告和首红均在 `kb-maintenance/`。

独立动态 Spec 只签 `1bd5e1dc` 及更早；后续成功控制写入缺口修复由作者正式回归 80P 和最终全量验证，最终 Spec 增量/Quality 是独立静态复核。平台曾中断 Quality 动态审查，原中断留证，原动态未在最终 SHA 重跑。`success-control-boundaries-green.log` 实际为历史 1F77P；最终80P是 `success-control-final-focused.log`，不能凭文件名判绿。实际远端资产上传、生产索引构建/解防写和整机重启未执行。

## 证据和运行边界

合源码没有更新生产 8792、生成快照或索引防写标志。完整入口探针在两棵临时根都使用新通知器；装机 L2 根 `d433b90788c0` 仍带旧版，正式部署必须单独核验通知器版本并保留 L2 业务代码，不能外推为生产已修复。

清理清单只是逐树审查输入；未认领、不可重建、脏树、生产/回滚或文档证据引用者均保留。追加检查发现 28 棵初筛候选中 9 棵含被忽略的 SQLite、台账或本地配置，路径/大小/哈希另记 `cleanup-ignored-artifacts.json`，原件保留；不能把 SHA 可重建当成全部工作区可重建。本轮删除数为 0。

领域回归工具已入正式源码 `scripts/review_probes/check_generation_finalize_boundaries.py`。`replay-sources/` 的 `.txt` 是本轮限定路径/分支名单的审计脚本原件，保留不同版本；它们不是新建的跨项目命令接口。二进制 diff、未跟踪原件、大 ReAct JSON 和浏览器 trace 均在外部保留，不因这个小包已入 Git 就获得删除授权。
