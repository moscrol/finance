# 2026-09-30 GitHub 主协作与本地备份安装记录

用户计划主要在 GitHub 操作，以 Gitea 本地备份应对源账号不可用。前一轮已停止强制镜像与每八小时自动推送；本轮获得“先把基础的环境搭好”的执行授权。

## 实际安装

金融仓主协作入口为 `https://github.com/moscrol/finance.git`。本机金融 Git 配置选 `remote.pushDefault=origin`、`push.default=simple`、`fetch.prune=true`；原 Gitea 分支跟踪入口改为 origin。提交指针和原业务工作树内容保留。GitHub 已删分支没有重新建立。

GitHub main 的保护通过 API 设置并读回：要求 `workbench-check`、`registry-check`，要求 PR 与解决评审讨论，管理员同样遵守；禁止 main 强推和删除。已有“main 合并等用户确认”规则仍适用。

本机当前使用的 AGENTS、workspace doctor、工作树盘点、收据漂移检查、台账取号及清理入口已切到 GitHub 主干。破坏性批量清理缺少 origin/main 时停止；旧仓必须显式给基线。工作树归档工具的 Gitea 备份目标继续保留。其他私有配套仓须单独核实 GitHub 可见性与入口，本轮没有将其内容发布到金融公开仓。

备份安装副本为 `~/.finance-runtime/github-backup/finance/runner.py`，配置与成功/失败收据在同目录。LaunchAgent `com.a77.finance-github-local-backup` 使用系统 Python 3.14，每 3600 秒运行，登录时启动。源 GitHub push URL 指向禁用路径；运行前与发布前校验目标的全部实际 push URLs。凭据使用既有 gh 登录与 Keychain，不写 token 到配置和日志。

备份数据为 `~/backups/github-finance/<日期>/`，每日最新代码 bundle 与版本 manifest/API 元数据。失败保留上次成功文件，完整成功后回收同一天旧尝试，旧日期保留。恢复操作见 `docs/workflows/dual-remote-collaboration.md`。

## 发现顺序与决定

先检查当前检出与双端引用，发现现用主树停在旧提交且有业务在途内容，因此从已同步的 `origin/main@7569327143a9a40ff44da32d723865b062d856e6` 建独立实现树。随后读取平台权限、停镜像状态、现有门禁，配置主干保护和单向备份。

| 方案 | 评价 | 决定 |
|---|---|---|
| 强制双端镜像并传播删除 | 会覆盖历史或把用户清理的源分支补回；违背已有停镜像决定 | 否决 |
| GitHub 普通快进，分叉另存 backup/github 引用 | 保留目标旧历史，同时能找到源端固定 SHA | 采用 |
| 仅确认 main 相等 | 不证明其他分支、标签、平台记录或独立恢复 | 否决 |
| Git 对象 + 独立 bundle + API 元数据 | 可离线恢复源码；平台记录留人工恢复参考 | 采用 |
| 从开发工作树长期运行脚本 | 工作树移除或依赖改动会影响任务 | 否决 |
| 独立运行副本、系统 Python、launchd | 与临时工作树和共享 venv 分离；Mac 离线期间仍有明确边界 | 采用 |

首次真实备份成功后做了 Standards 与 Spec 两轴复核。复核发现仅校验 fetch URL 不足以约束推送目的地、失败重试会覆盖旧成功 bundle、清理默认基线仍为备份主干。固定实现 `6259d11f9` 已修复，并补真 Git 回归。独立复核还验证首次检查后 push URL 改变、元数据部分写入后失败、真正旧版收据升级后连续失败的保全行为。

## 验证事实

- 固定实现提交 `6259d11f9068a4d3598bcd325fa6975055cb3613`：196 条相关测试通过，Ruff、diff 检查与提交门禁通过；code-map 全量重建成功，35,966 nodes。
- 2026-09-30 05:47:50 UTC（13:47:50 台北）实际备份成功：37 个分支、276 个标签，313 个源引用；普通推送更新 1 个引用，无新增分叉归档。Gitea 留存 556 个源端不存在的历史引用。
- main 固定为 `7569327143a9a40ff44da32d723865b062d856e6`，实现分支固定为 `6259d11f9068a4d3598bcd325fa6975055cb3613`；同期其他 agent 的提交按该次观察值冻结，之后推进由下一轮备份接收。
- bundle 106,505,745 bytes，SHA-256 `61ef97697572421d3918bb4edb03707dbb614a53313e3f3c23f86a43034bada4`；从该文件离线 bare clone、fsck 与全部 313 个源引用 SHA 核对通过。
- API 导出：5 个 Issue/PR 条目、5 个 PR、0 条 Issue 评论、0 条 PR 行评论、0 个 Release、10 个 label、0 个 milestone；另有逐 PR 评审与旧 Gitea 开放 PR 索引。
- 配置回读确认管理员保护、两个 required checks、PR 要求、禁止强推与 main 删除。实际备份已通过反向 push mirror 为空的检查。

测试收据：`~/.finance-runtime/test-receipts/20260930T054715Z-6259d11f-eb63649ad6fa.json`。这是本次相关路径验证，不是整个仓库的全量通过结论。

## 在途集成与边界

[GitHub PR #5](https://github.com/moscrol/finance/pull/5) 已发布并附到本聊天，尚未合入。初轮前端、E2E、注册表检查通过；Python 全量测试在 15 分钟上限被取消，取消前存在 6 个失败标记，未产生完整失败清单。基座 [main 的 CI](https://github.com/moscrol/finance/actions/runs/36659055037) 同样有连续六失败片段，后续还有更多失败并超时；不能将现有红灯外推为本轮改动导致，也不能宣布已解决。修复提交已触发新轮检查。

现用共享 venv 存在既有 httpx 0.25.2 / lock 0.28.1 差异，workspace doctor 如实阻止把该环境称为锁定环境。本轮没有修改共享运行依赖；独立备份运行已实际验证。

本地每小时任务需要 Mac 运行并登录；关机或睡眠不会执行。bundle 不包含生产数据库、会话、外部附件、LFS 实体或 Wiki。API JSON 不等于自动重建 GitHub/Gitea 所有功能。旧 Gitea PR 编号不能当成同号 GitHub PR，既有在途成果按任务迁移。

下一步先完成既有测试隔离验收与本 PR 必需检查，取得用户确认后合入环境规程；生产业务部署另按原验收处理。日常源端删枝与备份历史保留分别记账，避免为了清单相等破坏备份。
