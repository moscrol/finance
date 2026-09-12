# 7f9d7ce1 独立复审：收据可信，④ 失败未停，合并门禁未齐

## 范围与结论

只复核 `779b6ee2 → 7f9d7ce1` 的收尾改动及当前放行条件，不重新宣称审完本分支全部历史修复。被审树 `/Users/a77/fwp-wt-closed-loop` 干净；审查在 `/private/tmp/method-review-7f9d7ce1-pi` 隔离检出。没有修改源分支、推送、合入、迁移或修改生产配置。

接受：§4.1 重复探针已删除、唯一实现指向 §4.3；CLI 帮助和封存后 rc=3 的文字已订正；验 history 原件的方向正确；整树 9450P/0F/0E/77S 收据成立。

暂不建议合并：④ 失败不能机械停住，新增回归没钉住声称的拒绝行为；registry-check 最后一项已实测红，frontend/e2e 未验。

## 发现 1（P2）：④ 文档命令块打印错误但继续，末条成功掩盖失败

位置：`docs/superpowers/specs/2026-09-12-label-version-migration-plan.md:216–220`。

`[ "$rc" -eq 0 ] || { echo ...; echo "$out"; }` 没有退出；JSON 解析和 `report` 的非零也未传播，最后 `prot_ ... label_version` 成功使整个块退出 0。

独立复现：临时注册真实协议、建立空 history 日期目录、labels DB 指向临时目录中不存在的文件，使用文档原块在 `zsh -f` 执行（真实 CLI，不是假返回值）：

- history rc=2（旁路库不存在）；
- JSON 解析失败，report 报 invalid record path；
- history JSON 收据数=0；
- 最后仍打印 v5，命令块 rc=0；
- 追加只打印、不做副作用的 `STEP_5_REACHED` 标记，确实到达。

边界：文档末尾的自然语言“别往下走”可让细读的人停住；本发现否定的是复制执行能自动拒绝，以及“已钉入回归”的声明。没有证据表明真实 history CLI 发生假成功。

最小修法：将这段放入子 shell / 函数，对 history 失败、record 解析失败/缺失、report 失败逐个明确非零退出；执行⑤也须以④成功为前提。不要只追加 `set -e` 依赖调用上下文，不另造第二份验收逻辑。

原始证据：`/private/tmp/method-review-7f9d7ce1-evidence/history-acceptance.json`；复现脚本同目录 `probe_history_acceptance.py`（仅临时 fixture，未访问生产库）。

## 发现 2（P2）：新测试的负例没有调用被验对象，四项契约只断言了三项

位置：`intelligence/tests/test_method_validation.py:778–813`。

“反例”只 assert 空日期目录确实没有 JSON，随即删掉目录后跑成功路径。没有运行验收块、没有断言拒绝返回码、没有断言后续步骤不执行，所以发现 1 完整存在时测试照样绿。

正例检查了协议名、history 字符串、两个日期，没有检查三组收益和共同可评估日期数。隔离变异：仅将 `render_report` 的 `comparison = payload.get("comparison")` 改为 `comparison = None`，让真实 CLI 报告不再输出全部对照读数，新加这条测试依然 **1 passed / exit 0**。恢复后再跑 **1 passed**；变异已撤销，源分支未动。

最小修法：负例真正执行同一验收入口，断言非零且⑤哨兵未到达；正例核对明确的 history 类型、协议 id、协议窗口、三组读数和共同日期数。变异后应该红，恢复后绿。这里不要求扩展生产能力。

变异日志：`/private/tmp/method-review-7f9d7ce1-evidence/missing-comparison-mutant.log`（脏树变异收据不得冒充正常绿单）。

## 合并门禁：已知红，不再只是“未验”

在被审尖逐项执行 `.github/workflows/registry-check.yml` 的五条，不串联短路：

| 命令 | exit |
|---|---:|
| build_registry.py check-parseability | 0 |
| build_registry.py check | 0 |
| build_registry.py backfill-tables --check | 0 |
| build_registry.py generate-views --check | 0 |
| audit_ledger_spec_crosswalk.py | **2** |

红项：`R-20260831-02` 在 spec 有引用，台账无行，首个引用 `docs/superpowers/specs/2026-09-04-rag-worker-resident-memory-workorder.md:23`。反向 warning 不是本次 exit 2 的原因。

在已有干净基线检出 `/private/tmp/mgate-base-62381@6382c13b` 运行同一脚本，也 exit 2、同一个缺号。因此不归因本分支，但不能据“基线也红”带红合入。应交台账/门禁收口人追原始证据修引用或补真实缺件，不能为变绿编造一条台账。

日志：证据目录的 `registry-results.json`、`registry-{1..5}.log`、`registry-5-base.log`。

frontend 和 e2e 本轮未跑。下一轮在最终候选补 `pnpm install --frozen-lockfile` 后的 lint/typecheck/test/build，以及 `WORKBENCH_PYTHON=/Users/a77/finance-workspace-private/.venv-workbench/bin/python pnpm test:e2e`（按 workflow 配 Chromium）。各项独立留原始输出与退出码。

## 远端与交接漂移

2026-09-12 19:41 CST 左右的只读核对：`git ls-remote gitea` 与 Gitea GET PR #738 都显示 head=`7f9d7ce14215`、open、merged=false。PR updated_at=`2026-09-12T19:36:43+08:00`。所以贴来的“尚未推送、远端仍 2f5c7a03”已过时；本审查未推送，不推断具体是谁推的。

但 PR 正文未同步：仍写“同日同段重跑覆盖”、9408、以及把 gap_policy 的 skip 说成排除成员（旧纠偏已明确是天维度）；不能拿旧正文放行。源分支 inflight 仍写未推送、779b6ee2 的 9449 绿单，且 **6659 字节**，超过 ≤3K 约定。请同一收口人更新 PR 正文和压缩交接，历史细节移日期快照。

## 可采信的验证

- 原件 `~/.finance-runtime/test-receipts/20260912T113052Z-7f9d7ce1.json`：target 精确为 `.`、revision 7f9d7ce1、dirty=false/0、依赖门未绕过、9450P/0F/0E/77S、exit 0。
- `check_test_receipt.py ... --expect-revision 7f9d7ce1 --require-target . --base-drift-max 0` exit0；解释器与依赖指纹一致。无需为了怀疑原件再重跑当前尖整树。
- 独立全仓 Ruff exit0。
- `test_method_validation.py + test_method_flywheel.py` **78 passed**，收据 `20260912T114040Z-7f9d7ce1.json`（target 是这两个文件，不是整树）。
- main=`6382c13b`；`merge-tree --write-tree` exit0，tree=`54601903c06461f17096f5f0407597ce1243c9b5` 与被审尖 tree 一致。说明当前合流没有额外内容差异，不等于各门禁通过。
- 后续定向/变异测试又更新了共享 latest；始终按原件路径引用整树收据。

## 下一步与授权边界

1. 用户指定唯一收口人；其他会话不再写源树。
2. 最小补齐发现 1/2，更新 PR 过时正文及交接，冻结新尖。
3. 门禁缺号有独立归因但没有豁免：协调清障，在最终候选上获取所有叶子绿单；若 main 变动，验新合流树，不拿旧尖绿单替代。
4. 再请用户批准合并。更新 PR/推送和合并是不同动作；目前无新增授权。
5. 迁移另行逐步授权。执行前重新查待回检数量，非0即停止“直接封存”方案；验实际夜跑代码根/用户根/环境覆盖，再验真实 history 原件、夜跑选择和 capture 结果。顺序唯一来源仍是迁移方案 §4。

本轮临时脚本属单次审查复现，不注册为通用工具；生产回归交拥有分支承接，以免再造一份会漂的验收实现。
