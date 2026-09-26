# gitea_pr 子命令：guard / close / merge 身份钉死与授权记录

## 这个分支做什么
把 2026-09-21 两参表格家族收口里五个 `/tmp` 合并脚本的能力收进已有的 `scripts/gitea_pr.py`，不另建脚本。

## 决策与被否方案
| 选了什么 | 否了什么 | 为什么 |
|---|---|---|
| 扩 `gitea_pr.py` 子命令 | 新建 `gitea_pr_merge.py` | 仓里已有 open/show/conflict-check/merge，第二份会漂 |
| `guard` 退码看回读 mergeable | 只看 PATCH 成功 | 守卫的全部意义是平台层拒合，回读仍 true 就是没守住 |
| `close` 无指针在任何 API 调用前拒绝 | 指针可选 / 事后补 | AGENTS.md 关闭必留指针；#789 静默关闭有案 |
| `merge` POST 报错不退出、先回读 | 报错即失败 | Gitea 500 之后 main 已前进有案 |
| `--record` 强制 `--authorized-by` + `--authorization-source` | 只记原话 | 脚本字面量冒充用户原话比没记录更误导 |
| 合后核合并树 == 预览树 | 只核 merged=true | 「main 就是验过的那棵树」要拿树 SHA 说 |

## 当前状态
代码与测试已提交推送，PR #823 open；代码尖 0373a5b5，本文件是其上的 docs-only 提交。合入待用户确认。

## 已验证
全量 Python 在 0373a5b5：11959P / 0F / 85S / 2 xfail，收据 `~/.finance-runtime/test-receipts/20260921T044459Z-0373a5b5.json`，`check_test_receipt.py --expect-revision 0373a5b5 --base-drift-max 5` 9/9 可采信（main 已到 945c04bd，漂移 4 张合并，merge-tree 干净且改动文件无交集）。`tests/test_gitea_pr.py` 15P；变异自检 6/6 每次恰好一个测试红；扫 scripts/ 的 20 个测试文件 242P/1S；pre-commit 11 道、ruff 全仓过。真 Gitea 只读冒烟：`merge 815 --expect-head 06f74ef1` 对已合 PR 中止 exit 2，`close 815 --pointer-file 空文件` 在任何 API 调用前拒绝 exit 1，`open` 二次调用报 already_open。

## 未验证 / 已知边界
`guard` / `close` / `merge --record` 未对真 Gitea 做写操作冒烟（会动真 PR）；`--do squash|rebase` 不核树（只核 base 指向 merge commit）；`_preview_merge` 会写 `refs/remotes/gitea-pr/<n>`；`--expect-*` 接受 ≥7 位前缀。前端 / E2E 叶未跑（无相关改动）。

## 下一步
合入后用它替代手敲 curl：`guard` 给待合 PR 与其被取代的兄弟 PR 逐张加守卫；`merge --record` 的 JSON 放到该次验收的树外目录。

## 踩过的坑
用户级 git 钩子按整条命令文本匹配，`git push` 与含「main」字样的 PR 正文写在同一条命令里会被拦；正文用文件，push 单独一条。
