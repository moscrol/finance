# fix/deploy-ledger-single-home

## 这个分支做什么
工单 #44：部署账本两个家收成一个。写入只认 `~/.finance-runtime/deploy-ledger.jsonl`；读取过渡期仍看旧家、取末次 switch 最新；`audit_deploy_ledger.py homes`（旧家有行 exit 1）/ `migrate-homes`（默认 dry-run）。基线 `gitea/main@5eb24515`。

## 决策与被否方案
- 选：唯一家 `~/.finance-runtime`，`$FINANCE_WS/state` 与 `<repo_root>/state` 两级删掉、降为读取候选。否：以 `state/` 为家——快照没有 `state/`，仍要靠环境变量指回主树，正是病根。
- 选：`repo_root` 参数保留签名、不参与解析。否：删参数——要动 `create_app` 那一行与两条 CLI，多碰在途 PR 常改的 `app.py`。
- 选：迁移并集去重按 `unix`（缺则 `ts`）排序、原子覆写、旧文件改名保留；目标在读与替换之间被写就放弃。否：直接 append 旧行到新家——`last_relevant_row` 按文件顺序取尾行，顺序错就报错 rev。
- 选：`--apply` 不在合入前跑。否：现在就并——8792 旧代码切流前每次重启再生旧家，白并；迁移幂等，切流后一条命令。
- 先量推翻了占位稿「dev server vs 快照」的推断：真相是带不带 FINANCE_WS / --ledger。

## 当前状态
`0aea8a19`（代码）+ `0accea02`（工单 / INDEX）+ 本交接已提交。**PR #688 已开，等用户确认合入。** 树干净。

## 已验证
- 干净树全量 8308P / 0F / 77 skip / 1 xfail（收据 `20260909T064405Z-0aea8a19.json`）；ruff 0；pre-commit 11 道过。
- 新测 6 + 2 条，`test_worktree_board` 一条合同变更（旧家优先 → 唯一家优先）。
- 真机干跑：`homes` exit 1（旧家 282 行，末次 switch b594a5e7 停在 09-07 08:42）；`migrate-homes` 计划 24 + 282 → 306、0 重复；未动文件。
- `merge-tree`：代码文件与所有在途分支不相交；INDEX 老冲突；#572 在 `acceptance-workflow.md` 的冲突对 main 本来就有。

## 未验证 / 已知边界
- 未跑 `--apply`；未切流。切流后旧代码写的 startup 行留在主树 `state/`，`migrate-homes --apply` 再并一次即可（幂等）。
- 迁移的并发保护只看「读 → 替换」窗口的 stat 变化，替换一瞬仍有极小窗口。
- `homes` 的 git common-dir 探测在非 git 目录回 None，只看 `$FINANCE_WS/state` 与本仓 `state`。

## 下一步
- 用户确认 #688；合入后 8792 切到含它的 rev（工单 #38 规程）→ `migrate-homes --apply` → `homes` exit 0 → 把 `acceptance-workflow.md` 命令里的 `--ledger` 去掉（已在注释里说明为何暂留）。
- 另立单：episode store 的 `$FINANCE_WS/state/episodes` 一级同构，生产 episodes 现落主树 `state/episodes`，搬家要连数据。

## 踩过的坑
- 夹具时刻要用真实 epoch：`unix=5.0` 与 `ts` 解析出的 2026 年 epoch 混排，排序看起来「错」，其实是数据不自洽。
