# docs/orphan-workorders-0923 · 无人接手工作的工单化 + #77 合并批代跑

## 这个分支做什么
把 09-23 盘点出的无 owner PR / 分支写成工单 #81–#87 + INDEX 续表；盘点、判据、合并批收据全文在 `docs/handoffs/2026-09-23-orphan-inventory.md`。

## 决策与被否方案
- 被接替 PR 关闭留指针，判据是「新增代码行在 main 可见比例」94–99%；否了 `is-ancestor`（squash 前向不成祖先，会误判成未落地）。
- 合并批只拼一棵 main+8 PR 预览树跑一次四叶；否了逐张各跑（7×40 分钟）。
- 前端 / e2e 另开同 commit 的树跑；否了排在 python 后（build 产物可能弄脏门禁树）。
- #807 分支被他人树检出，前向 union 另开 #891 合入再关 #807；否了 `update-ref` 改别人检出的分支、否了 refspec 推送（hook 拦）。
- #838 退回不关（#863 正文明写留 open）；#874 有活会话持有，不动。

## 当前状态
- 合并批 **7 张已全部合入 main**：#853 `098e5123d`、#857 `aaec54897`、#804 `0e9c452a7`、#840 `f66954200`、#849 `a2f845fff`、#836 `917e15a87`、#807→#891 `e926157d9`；record 在 `~/.finance-runtime/reviews/orphan-batch-0923/merge-*.json`。
- 18 棵已落地 QC 树已删（`cleanup.log`）；预览树 `fwp-preview-batch-0923` 与本树待 #889 合入后删。
- 本分支：工单 + 盘点 + 本文件已提交推送，PR #889 open，等合入（docs-only，内容已在预览树 `53c51cfdc` 上过四叶）。

## 已验证
预览树四叶：python 14639P / 0F / 85S / 2X（`receipts/gate-SFFAGzfL/pytest.json`，revision `53c51cfdc`、dirty=False）；前端 lint / typecheck 0、vitest 120P、build 0；e2e 34P / 2S；registry 五项 0。每张合后 main 文件集 == PR 文件集；合后 `git diff 53c51cfdc gitea/main` 非文档差异 0。

## 未验证 / 已知边界
#889 本身最后两次提交只是交接 / 盘点文档，未重跑四叶（docs-only）。`fwp-qc-853-current` / `857-current` 两棵 detached 树带未提交代码改动，来源未知，未动。#874 的合入授权那条活会话看不到。

## 下一步
1. 合 #889：`bash ~/.finance-runtime/reviews/orphan-batch-0923/run-merge-batch.sh one 889 docs/orphan-workorders-0923 <12 位 head>`；然后 `git worktree remove` 预览树与本树，`git branch -d docs/orphan-workorders-0923`。
2. 工单 #81–#87 待派；#62 / #66 / #68 / #73 待派无人。
3. #799（docs，仅 lessons 冲突）与 #838 退回项归 #77 后续。

## 踩过的坑
- 脚本里 head 比对用 12 位 SHA（9 位会被切成不等长）；日志别经 `sed` 管道（非法字节会 SIGPIPE 杀掉脚本），写文件再 `LC_ALL=C grep -a`。
- 漂移检查要按 blob 与预览树比，固定基座会把批内自己刚合的文件当外来漂移。
- e2e 成对设 `RE06_E2E_PORT` + `RE06_E2E_URL`；zsh 不分词；主树 `gitea_pr.py` 旧版无 `close`。
- 三个脚本（准入等待 / 合并执行 / 清理）留在收据目录，PR 号硬编码未进 `scripts/`；泛化留给 #77 收口。
