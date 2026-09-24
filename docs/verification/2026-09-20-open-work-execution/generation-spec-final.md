# 最终合流候选 f2342fda · Spec 复审

**结论：原直接 launcher 的 ALERT_LOG 反例已关闭；完整 nightly 入口仍有 2 类 P2，因此 f2342fda 不通过此轮 Spec 验收。** 这两类均是入口组合没有传递已作出的拒绝决定，不是需要新增 OS 沙箱能力。

## 固定对象与边界

- 被审代码：`f2342fda0d0ae9fb842cbcd0bdd6ee4cf5069bd1`，比较基线 `ec92b31b5300bbbb4abc64e41f96854f1438aea0`。提交链含 `cc47484e` 告警预检、`a86374d1` 新 main 合流、`227ca68c` hithink 合流、`f2342fda` 部署接线合流。
- 初始候选树 `/Users/a77/fwp-wt-generation-alert-guard-0920` 为 f2342fda 且 clean；审查中作者推进至 `4172f547`，已核该提交相对 f234 只改 `docs/agent-product-door.md`。早期完整入口探针据实记录了 4172，没有冒充冻结收据。
- 为固定反例，在 `/Users/a77/.finance-runtime/open-work-execution-20260920/generation-spec-final-f234` 新建 f234 的干净 detached 树；下文最终四例全部在这棵树的临时副本上重跑，开始/结束 HEAD 同为 f234、status 空。
- 旧 `generation-spec.md` 与原 387028b8 失败证据原样保留。未改候选、生产、原探针或原失败判据；未运行模型、生产 L2/DB/KB 接收、pytest 全量或部署。使用主仓 `.venv-workbench/bin/python`。

## 旧 P2 关闭的精确边界

`intelligence/workflows/generation_paths.py:73–76` 在启用告警时调用实际 `scripts.notify_ops.ALERT_LOG` 并执行 `_outside_code`。从 `cc47484e` 到 f234，这段及 launcher 未因合流改变。

原 `generation-spec/probe_alert_boundary.py` 未改，仅通过 import 将 REPO/OUT 指向新候选/新证据目录：旧软链配置变为 exit **2**、root-invalid、无告警文件、代码树零变化；安全外置对照仍 exit **1** 并正常记录业务失败。五类新增 CLI 回归的源码也保留文件链接、父目录链接、HOME 在 CODE 下、正常外置、`--no-alert` 语义；其作者测试读数不冒充本轮独立测试。

原 7 项 `scripts/probe_generation_code_root.py` 从未修改的 387 冻结树启动，`--repo` 指向 f234，结果 **7 passed / 0 failed**，各项 exit 2、无旧码哨兵/代码变化。证据：`generation-spec-final/original-probe.{json,log}`、`generation-spec-final/alert-boundary.json`。

## F1 · P2 · 外层告警绕过 launcher 已作出的路径拒绝

**规格原句**：#50 §4.3 **“全在数据根，代码根下零新增文件”**；f234 门页 `docs/agent-product-door.md:44` **“缺代码根/包、写入位置落进代码根时拒绝生成”**。

**代码**：`skills/daily-full-review/scripts/nightly_full_review.sh:280–283` 在 launcher 非零后再调用 `notify`；`:213–215` 用操作/L2 根的 `scripts/notify_ops.py` 写日志。共同 writer `scripts/notify_ops.py:29,34–36` 未校验最终 ALERT_LOG。L2 失败更早在 nightly `:240` 调同一个 `notify`，此时生成预检尚未运行。

**固定反例 1**：CODE_ROOT 与 FINANCE_GENERATION_CODE_ROOT 分开配置，HOME 告警文件预先软链到生成根 `qc-outer-alert.log`。launcher 正确 root-invalid、未 import；完整 wrapper 返回 2，却因补告警新增生成代码文件。

**固定反例 2**：同样双根和告警软链，假 L2 返回 3。wrapper 返回 1，launcher 从未启动，生成树仍新增 `qc-outer-alert.log`。这证明只改生成失败分支不够。

**合法对照**：同一真实 wrapper + 临时业务质量门返回 3，告警位于安全外置 HOME 时 exit 1、告警正常记录、两个代码根零变化。

**有界修正**：launcher 非零先返回，错误只走 stderr/不落盘桌面通知；共同 writer 在 `mkdir/open` 前规范化最终 ALERT_LOG，排除非空 `FINANCE_CODE_ROOT` 与 `FINANCE_GENERATION_CODE_ROOT` 两个配置根，拒绝时不另写回退日志。保留安全外置日志与既有失败退出码；不改变 L2 的执行顺序/资金口径。

## F2 · P2 · launcher 拒绝代码面软链后，wrapper 仍执行该 receiver

**规格原句**：原 R3 返修要求（`docs/verification/2026-09-15-generation-root-0f6c2810-qc.md`）：**“副作用前验证所选计划的实际执行文件 resolve(strict=True) 位于同一固定代码根，拒绝外逃软链；嵌套脚本遵守相同规则。”** f234 门页 `docs/agent-product-door.md:48` 也声明先核验代码面及嵌套脚本软链的真实归属。

**代码**：nightly `:274–277` 在检查 `rc`（`:280`）之前，先对 GENERATION_ROOT 下的 `receive_kb_ingest_queue.sh` 做 `[ -f ]` 并执行 `/bin/zsh`。`-f` 跟随软链。launcher 的快照预检能拒绝它，却不能约束父 shell 后续动作。

**固定反例**：预置 `<GENERATION>/skills/daily-full-review/scripts/receive_kb_ingest_queue.sh → <DATA>/poison-receive.sh`；poison 仅打印哨兵并创建临时 marker。完整 wrapper 返回 2、launcher root-invalid 且未 import，但 `receiver_executed=true`，临时 marker 确实创建。

**有界修正**：在 `local rc=$?` 后立即处理失败并返回，成功以后才进入 receiver。该反例中的脚本是本仓生成代码面，不是已声明排除的外部知识库接收器，也没有运行期换链。仅在 receiver 自身返回非零后报错不能撤销已经执行的数据树代码。

## 可复跑证据与结果分母

固定完整入口探针为 `generation-spec-final/probe_final_entry_boundaries.py`；以真实 shell、launcher、CLI、notify_ops 组合执行。操作/L2根和生成根彼此独立；L2/外层质检/方法命令由临时分派器替代，生成内部质量门固定失败防止进入模型步骤；osascript 为临时无操作 stub。receiver 仅为临时哨兵脚本，不跑真实 KB 接收。

```bash
env -i PATH="$PATH" HOME="$HOME" PYTHONDONTWRITEBYTECODE=1 \
  /Users/a77/finance-workspace-private/.venv-workbench/bin/python \
  /Users/a77/.finance-runtime/open-work-execution-20260920/generation-spec-final/probe_final_entry_boundaries.py \
  --repo /Users/a77/.finance-runtime/open-work-execution-20260920/generation-spec-final-f234 \
  --output-dir /Users/a77/.finance-runtime/open-work-execution-20260920/generation-spec-final/f234-entry-probe
```

| 用例 | 实际结果 | 合同 |
|---|---|---|
| safe_external_alert | exit 1，正常日志，双代码根零变化 | PASS |
| generation_rejected_alert | exit 2，launcher 拒绝，outer 写生成根 | FAIL，F1 |
| l2_failed_alert | exit 1，launcher 未运行，outer 写生成根 | FAIL，F1 |
| receive_escape | exit 2，launcher 拒绝，receiver marker 出现 | FAIL，F2 |

完整入口 **1P/3F，exit 1**，归属 **2 类 P2**；与原 7 项及旧直接告警 2 项分别计数。原始结果 `generation-spec-final/f234-entry-probe/entry-boundaries.json`，每例 stdout/stderr 在同目录，执行总日志 `generation-spec-final/f234-entry-probe.log`。后续修复可只替换 `--repo/--output-dir` 原样复验。

## 合流语义审阅与未认证范围

- `a86374d1` 的跨日质检冲突解决保留了新版 quoteless_sectors 输出/空壳检查，并将本线计划解析置于裁剪前；未见把新检查整段丢失的解决方式。
- `227ca68c` 的同步器冲突解决保留 hithink 四步骤及“无 key = skip、不冒充更新”的实现，复用 PLAN_CHOICES/resolve_plan；没有重新引入第二份本地 parser。
- 最终 daily 工作流与 387 版本无差异，显式计划/固定解释器/数据根环境仍在；部署 wrapper 局部设置 GENERATION_CODE_ROOT，没有全局替换 L2 的 CODE_ROOT。
- f234 门页一处旧 CODE_ROOT 文字已由作者文档提交 4172 修正，不再重复列为待修代码问题。
- 上述合流检查是静态审阅；作者正在运行的定向/全量与其发现的质量夹具问题由父任务记账，本轮没有拿这些未完成测试作准入结论。本报告只裁定上面有实际证据的生成边界。
