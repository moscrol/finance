# GitHub 主协作 / 本地备份

## 这个分支做什么
金融仓以 GitHub origin/main 开发与提交 PR，Gitea 留历史备份；本机环境已安装。

## 决策与被否方案
| 采用 | 被否 | 理由 |
|---|---|---|
| 单向普通推送，分叉留归档引用 | 强制镜像 / 把旧枝补回源端 | 用户已清理源端；备份必须保留旧历史 |
| 独立 runtime 副本 + 每小时 launchd | 从临时开发树直接跑 | 清理工作树后备份仍可执行 |
| 固定 SHA、bundle、独立成功收据 | 只看两个 main 相等 | 需覆盖分支、标签与账号不可用恢复 |
详情：`docs/handoffs/2026-09-30-github-primary-local-backup.md`。

## 当前状态
实现 `6259d11f9` 已正常推到 GitHub PR #5；文档随该 PR 交付。
本机默认远端、现用入口文件、主干保护与备份服务已启用。
PR 未合入；远端后续 agent 应等本 PR 合入再从 main 读取新版规程。

## 已验证
固定实现提交 196 条相关测试通过；两轴复核通过。
05:47:50 UTC 实际备份成功：37 heads + 276 tags，Gitea 保留 556 个源端不存在的引用。
新 bundle 离线 bare clone、fsck 与全部 313 个源引用 SHA 核对通过。

## 未验证 / 已知边界
PR 全量 Python CI 旧轮超时且有失败片段；基座主干同样失败，修复后新轮尚未完成。
Mac 关机/睡眠期间本地任务不运行。数据库、会话、附件、LFS 实体、Wiki 不在本备份覆盖内。
共享开发 venv 的 httpx 为 0.25.2，锁文件为 0.28.1；doctor 不通过；备份用独立系统 Python。

## 下一步
先完成现有测试隔离验收与 PR 全量 CI，再取得用户确认合入 #5。
合入后继续看实际备份收据；历史 Gitea PR 按需搬迁，编号不沿用。

## 踩过的坑
校验 fetch URL 不能证明 push URL 安全；必须核对 --push --all，包含多地址和 pushInsteadOf。
失败的新尝试不能覆盖上次成功 bundle、manifest 或 metadata；成功记录指向独立版本文件。
