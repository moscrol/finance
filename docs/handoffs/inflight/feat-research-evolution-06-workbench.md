# feat/research-evolution-06-workbench 在途交接

最近更新：2026-09-14 · 06 HEAD `7abaa938`（含 X1/X2）· 合并候选 `0bd11ece`（分支 `merge/research-evolution-06-main`，树 `/Users/a77/fwp-wt-merge-re06`）

## 当前任务（等两项授权）

1. **Q2 过渡合同待用户明确接受**（X1 行为变更）：复核完成不再自动收尾；成果缺可信归属时保持待复核，面板「确认成果」显式点名后闭环。动机：普通聊天判断曾被错误自动认领（X1 反例）。
2. 工程合并放行：候选 `0bd11ece` = 06@`7abaa938` + main@`1fef3d27`，门禁全绿。

## 本轮改动（合并准备，业务代码零改动）

- 第七轮 X1/X2 返修由另一会话落 `7abaa938`：X1 移除自动认领（无身份成果一律待复核、显式确认闭环）；X2 接受侧登记前按 run 查既有归属，不双登记；运行中登记与终态折回共用消费侧核验。
- 独立树合并 main@`1fef3d27`：唯一冲突 `.claude/lessons_learned.md`（双侧追加），按意图合并（续段归位 + 新块全留、按时间序）。
- BLOCKED.md：I14 单列普通工程待验，不再与 I13/I15 的真人授权同因。

## 验证（全部在合并候选 `0bd11ece` 干净树）

- X1/X2 原探针原样回放 **2/2**；06 rework+api 套件 79 passed。
- ruff 干净；`build_registry.py check` 一致；`graph_audit` 106 断言无漂移。
- 前端 lint/typecheck/test(94)/build 全绿；e2e 31 passed / 2 skipped（隔离服务+临时用户态；绑定 spec desktop 绿）。
- 全仓 pytest **10211 passed / 77 skipped / 2 xfailed / exit=0**，收据
  `~/.finance-runtime/test-receipts/20260914T064917Z-0bd11ece.json`（dirty=false，无排除）。
  （06 组合收据 10137@`3d72b53a`；X1/X2 后 10141@`7abaa938`（审查方核实）——三份各绑各快照，不混用。）

## 未验证 / 已知边界

- product_verified **部分**：I13 真人试点、I15 真实前向实验缺授权（BLOCKED §3）；I14 为普通工程待验（已单列）。
- field_evidence 无。e2e 绑定 spec 的 tablet/mobile 按设计跳过。
- 旧动作是否继承到复现节点仍是产品决定（当前不继承，rejected + 界面反馈；I17 已钉）。

## 下一步

- 用户接受 Q2 过渡合同 + 放行后：合 main（候选 `0bd11ece`），push 另授权；部署与 /api/health 验收单独授权。
- I13/I15 需真人与授权结果源；I14 随时可做。

## 踩过的坑

- 新 worktree 无 venv 与 node_modules：pytest 用主树解释器；e2e 加 `WORKBENCH_PYTHON=<主树>/.venv-workbench/bin/python`；前端先 `pnpm install --frozen-lockfile`。
- `#recur:<day>` 只喂 id 派生（dedup_key 加 salt），公开 id 是哈希——断言独立身份用「id 异 + dedup_key 同 + 链形」。
- 动作错误体 `{code,message,detail}`：reason_code 在嵌套 `detail.detail`。磁盘满会让 merge 报 Unable to write index，先 `df -h`。
- 取版 HEAD ≠ 业务基线：01/05 docs tip 在基线之上，合并与收据口径两者并记（PROGRESS 末节）。
