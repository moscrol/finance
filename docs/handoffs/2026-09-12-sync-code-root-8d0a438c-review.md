# fix/sync-code-root · 8d0a438c 独立复验

## 结论与范围

**推荐 S7 路径的暂存/发布边界、两个入口默认配置通过隔离复验；整个补跑安全边界仍未收住，暂不放行。** `nightly_full_review.sh sync|all` 仍绕过 S7。全量在审查期间结束，收据为 9412P/1F/77 skipped，exit 1，不能按后续单测绿改判。

- 冻结代码：`8d0a438c9bf0b1ab26d6ed759c0af98b4bbf3a61`，审查树 `/tmp/sync-qc-8d0a438c-review`，独立文档枝 `docs/qc-sync-8d0a438c`。
- 作者枝检查时为 `54804931`、干净；该笔相对 8d0a438c 只改 inflight 文档。本轮也读了该新版交接，不把它视为新增实现。
- 前次报告：`docs/qc-sync-fcf9cca9@919a4089` 的 `docs/handoffs/2026-09-12-sync-code-root-fcf9cca9-review.md`。
- 只审，无同步外呼、生产写库、方法日步、配置重载、安装覆盖、推送/合并。未停止任何别人的进程，未启动第二份全量。

## 发现（按优先级）

### P1，前轮未闭合：旧补跑入口仍直写目标库

`skills/daily-full-review/scripts/nightly_full_review.sh:153–155,278–280,328–330`：

```text
sync / all / 只传日期 / 不传参数
→ run_sync()
→ "$OPS_PYTHON" "$REVIEW_SYNC_SCRIPT" --date "$D"
→ 同步器继承 MARKET_FEATURE_STORE_DB
```

默认目标仍为 `$DATA_ROOT/db/market_feature_store.duckdb`。没有包装、也没有拒绝生产目标的守卫。新增默认 local 后，旧入口甚至不再因缺档位落 full 而较早停在登录检查。

本轮执行**完整**仓内及装机 Shell 的 sync 路径，隔离 HOME/ZDOTDIR/DATA_ROOT/锁与健康日志，用解释器 spy 截获子进程：两者均直接调用专用树的 `run_review_sync.py`，DB 为目标库本身，无 staging wrapper。

新 `SKILL.md` 已把推荐入口改成 S7，原“推荐直写生产”问题可以认可修正；但 `54804931` 交接的“补跑入口绕开 staging 已修”仍过宽，脚本头部还称 sync/all 为手动补跑。文档换推荐项不等于封住旧副作用入口。

另有测试反向固定旧旁路：`tests/test_eval_launchd_wiring.py:228` 仍断言必须包含上述直接同步器调用。需要改成行为回归，而不是只确认路径字符串。

建议二选一：

1. 最小范围：旧 sync/all 在任何写入前明确拒绝，报正确的 S7 命令；finalize 继续保留。
2. 保留兼容：同步阶段接入同一 S7 包装边界，并明确锁的唯一持有者。当前 nightly 自己已持有 daily-full-review.lock，**不能简单在锁内再调用同锁 S7 Shell**，否则二次抢锁退出 75。可在合适层调用共用 Python 包装或重排持锁层。

回归：所有公开同步入口均验证子进程只写 staging；中途失败/门失败目标哈希不变、无 swap。只改文档或只测“含 staging 字样”不足。

### P2，新推荐的两行命令没有“前一行成功才继续”控制流

`skills/daily-full-review/SKILL.md:89–90` 是两个独立 Shell 命令，无 `&&`、无显式退出码检查。

把这两条路径替换成无副作用 spy，第一条 exit 7、第二条成功，按原代码块执行的结果：

```text
sync failed rc7
finalize invoked finalize 2026-09-11
整体 shell rc=0
```

真实 finalize 有现存生产数据守卫；本条**不声称这个守卫会无条件通过**。问题是它不接收本次 S7 结果；已有该日数据、重跑失败时，数据在场不能证明本次发布成功。推荐入口明确要求“同步全绿后再生成”，控制流也应如此，建议 `S7 ... && finalize ...`，或可保留失败码的单一入口。若覆盖计划或代码根，两个阶段应显式共享相同环境。

### P2 遗留，已标注但尚无可执行接替指针：生成段仍读共用数据树代码

`nightly_full_review.sh:130–136` 注释和 `SKILL.md:110–114` 已承认现状，范围说明可认可。没有改 Python import 路径，不算修复。

本轮不要求把用户态/episode/模型网关顺手混改进本枝；但“另单”文字不是工单定位。作者交接只写另单，未给具体工单/分支/负责人及验收合同。建议补明确接替入口；不要写“整个 finalize 根已固定”。前轮对实际 import 来源的验证依然适用，此实现段未改变。

## 已独立验证的修复

### 1. S7 实际发布边界（临时合成库）

保存当前装机 `~/.local/bin/nightly-review-sync-staged.py` 到临时证据目录，SHA256：
`742c36c1e79c2e968c2a1d6088df5c022c6d4d5b23e53e486666ac3fab712375`。

使用其真实 clone、形状校验、写收据与 atomic swap，依赖 `~/.finance-runtime/finance-s7-sync` 的 S7 实现。把上游同步子进程替换成只写临时库的合成 worker；没有使用生产库作为 fixture。

| 用例 | 包装 rc | 目标库字节哈希 | staging | 目标数据 |
|---|---:|---|---|---|
| worker 写入后 exit 7 | 2 | 不变 | 保留 | 旧行 |
| 真实 run_release_steps 的 same-day 子命令注入 exit 2 | 2 | 不变 | 保留 | 旧行 |
| worker 删除表，形状门失败 | 2 | 不变 | 保留 | 旧行 |
| 合成成功 | 0 | 改变 | 已换名 | 旧行+新行 |

四例 worker 看到的 DB 都是 `target.duckdb.staging`。这证实该装机包装边界存在且这些失败路径拒绝发布；不等于真实 local 十六步、真实市场质量门、第三方写者竞态、进程强杀/断电模型均已验。

这个 Python 包装器不在 `install_eval_launchd.sh` 的七个脚本清单内，冻结枝 `git ls-files '*sync*staged*'` 无该文件。因此本证据明确绑定到装机文件摘要和依赖树；不能把固定 Git 提交的全量测试当作对这个外部文件本体的验证。本轮不要求借机重构部署，但应保留依赖定位。

### 2. 默认值与覆盖（真实完整 Shell，解释器 spy）

矩阵：仓内/装机 × nightly/S7 × 未设置/显式覆盖，共八例。

- 未设置 `FINANCE_SYNC_CODE_ROOT` / `REVIEW_SYNC_PLAN`：子进程收到专用 `finance-workspace-sync` + local。
- 显式设置为隔离代码树 + cheap：子进程保留设置，默认值没有覆盖它。
- S7 Shell 启动 `nightly-review-sync-staged.py`；普通 nightly sync 则仍直调同步器（P1）。

只替换解释器为 spy，锁、参数解析、导出环境、函数分流由真实 Shell 执行。HOME/ZDOTDIR 指临时空目录，不读取宿主 zshenv；数据根、锁、健康日志也全隔离。未在真实 cheap 档请求复盘会。

### 3. 定向检查

- 本轮冻结代码 `pytest -q tests/test_eval_launchd_wiring.py`：**21 passed / 0.40s**。
- 收据 `~/.finance-runtime/test-receipts/20260912T102127Z-8d0a438c.json`，dirty=false。
- 相关 Ruff、两个 Shell 的 `zsh -n` 通过。
- 作者新增的两个默认值测试确为源码字符串断言；作者说的变异试验本轮未重复执行，以上八例补的是独立行为证据。

## 装机差异与汇报口径

按安装脚本解析清单，不手数：七个脚本、六份 plist。

- 五个脚本字节相同；S7 Shell 仅注释不同；`nightly_full_review.sh` 有实质差异。
- 六份 plist **解析后的字段完全相同**；其中两份日复盘 plist 字节不同，因此应说“配置等价”，不是所有文件逐字一致。
- 两个 launchd 加载态均为 local、专用同步根、runs=0 / never exited。收窄成“重载/配置已加载”正确。
- nightly 的实质差异**不止 moneyflow 代码根**：装机还不再读取 l2-paused.flag、失败状态写入脚本也用 DATA_ROOT，且少了仓内三处提前失败时的 skip_method_flywheel 留痕。作者已明确此文件例外，不能将其解读为仅一行路径例外。
- 主检出树 L2 在途代码解释了为何不能覆盖安装；**WIP 在那里是临时依赖事实，不是它已获生产验收的证据**。冻结仓内全量也不覆盖该装机差异。不要在本轮覆盖它，后续交接需记录差异/所有者/接替验收。
- “两棵树没有其它裸相对路径”若指三道 nightly 检查器调用可以成立；若指整树字面无相对调用不成立，例如同步器 run_release_steps 仍用相对检查器路径，但其 run_step 明确 cwd=ROOT，**这处不是走错根的缺陷**。应按“调用路径+cwd”判断，而不是以相对/绝对形式本身判安全。
- 新 inflight 3311 字节仍超 ≤3KB，且沿用“active --help 两边0”的旧解释；该解释已在方法分支两次实测反证，旧快照 active help 是 rc2。日期事故快照还写固定 local 没做，需在当前交接注明后续决定已翻转，不必改写历史冒充当时已知。

## 全量收据：审查期间已出结果，不再是“在跑”

作者固定树 `/Users/a77/fwp-wt-verify-8d0a438c`，核对 dirty=false。

- `20260912T101816Z-8d0a438c.json`：**9412 passed / 1 failed / 77 skipped，exit 1**。
- 失败项：`intelligence/tests/test_workbench_conversation_integration.py::test_real_conversation_round_trip_persists_skills_sse_and_three_turns`。
- 随后七份同一用例的单测收据各 1P（101850、101854、101912、101913、101915、101916、101919 UTC）。它们支持间歇性失败假设，但不是新一轮全量，也不能单独证明负载是唯一原因。
- `20260912T101456Z-8d0a438c.json` 是 0P/0F/0 skipped，不能作为全量绿。
- 本轮观察到作者全量命令输出经 `tail -8`，未取得完整失败 traceback。建议下一次 `tee` 留全日志、开启 pipefail 保留 pytest 退出码；勿用管道尾命令的成功代表 pytest 成功。
- 上述均为核对已有收据，不是本轮抢跑全量。本轮定向测试开始时，该全量已经结束。

## 下一步与取舍

| 选择 | 否掉的方案 | 理由 |
|---|---|---|
| 认可新 S7 推荐路径，但保留旧旁路阻塞 | 因推荐命令已改就宣称全部入口修好 | 副作用仍可通过公开旧入口抵达生产目标 |
| 小范围拒绝旧 sync/all 或统一包装 | 锁内再套同锁 Shell | 避免修出必定 exit75 的自锁 |
| 生成段/L2 留明确接替任务，不本轮覆盖装机 | 用仓内源强制覆盖以求文件相同 | 会抹掉已识别的在途功能和行为差异 |
| 完整全量红单继续有效 | 用单测多次绿覆盖整树失败 | 只对实际执行目标出结论 |

由原分支唯一收口人先关闭旧同步旁路、串起推荐命令成功条件并补行为测试；给生成段和装机差异具体接替指针；更新测试状态。之后固定新头再复验/跑合入门禁。9-11 真库补跑、名单水位、同花顺水位及15日数字本轮都未执行/复算。

证据目录 `/tmp/sync-qc-8d0a438c-evidence/`：`probe.py`、`probe.log`、`results.json`、`sequence_probe.py`、`sequence-results.json`、`targeted-pytest.log`。本轮只审授权，临时探针没有写入实现枝变成回归门；报告已列清输入、故障点和断言供收口人落地。不修改共享知识仓或他人交接。
