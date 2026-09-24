# docs/workorder-45-episode-store-home

## 这个分支做什么
#687 / #688 合入后的文档收尾：INDEX #44 与工单 #44 改已合并记「切流后 `migrate-homes --apply`」待办；归档 #688 的交接；新立 #45 占位单（episode store 的 `$FINANCE_WS/state/episodes` 一级与 #44 删掉的同构）。纯文档。基线 `gitea/main@dba3aa55`。

## 决策与被否方案
- 选：#45 只立占位、定 P3。否：直接做——现在只有一个家在用（主树 `state/episodes` 45 个 episode，`~/.finance-runtime/episodes` 不存在，09-09 实测），是潜在缺口不是事故，而且迁移要连 45 个目录一起、须与 8792 切流同窗。
- 选：#45 第一步写「核实生产 `FINANCE_WS` 来源」。否：照 #44 的推断直接拍——launchd plist 里没有 `FINANCE_WS`，45 个目录为什么落在主树说不清，#44 已经被这种推断坑过一次。
- 选：本单自己的交接留在 inflight，合入后由下次归档扫走。否：合入前先归档自己——文件还没合就进归档表，证据列填不出合并提交。

## 当前状态
已提交，PR 待开 / 已合见 INDEX 行。树干净。

## 已验证
- 纯文档：ruff 无对象；pre-commit 11 道；`tests/test_ledger_spec_crosswalk.py` + `tests/test_worktree_board.py` + `test_deploy_ledger.py::test_deploy_script_and_chain_cut_docs_call_record_cli` 绿（读文档的那几条）。
- 取号：#45 未被任何本地分支占用（扫全部分支 INDEX diff，最大 43，main 44）。

## 未验证 / 已知边界
- 没跑全量（纯文档；两张前序 PR 的合并树全量 8318P / 1F 负载假红已在工单 #44 头部记账）。

## 下一步
- 用户 / 运行面：8792 切流（工单 #38）→ `audit_deploy_ledger.py migrate-homes --apply` → `homes` exit 0；夜跑 `--plan local` 重启用；北交所轮询重拉。
- #45 待派，与切流同窗做迁移。
- 其他开放 PR：#684 P4 头 sha 有 8324P/0F 收据、只剩 INDEX 一处机械冲突，可合；余者见会话体检表。

## 踩过的坑
- 合并 API 在负载 76 下 30 s 超时但服务端已合成——重试前先 `show`，不然会对已合的 PR 再 POST 一次。
