# feat/research-evolution-06-workbench 在途交接

最近更新：2026-09-14 · HEAD 见 git（组合 + I17 = `3d72b53a`）· 基于 9266407f

## 当前任务（等用户确认合并）

最终四轨组合已重建并完成全部代码侧验收。四轨 QC 十一轮全部收口、三处 P3 文档修正完毕后的取版：

| 轨 | 取版 HEAD | 业务基线 | 合入 |
|---|---|---|---|
| 01 | `85c90b24` | `a3cf9d4b` | `eac41a64` |
| 02 | `e27b3352` | 同左 | `d432a67b` |
| 04 | `fcc7838c` | 同左 | `196cfdc1` |
| 05 | `2c278e07` | `ded78479` | `505d1747` |

01/05 取版与基线差仅文档。旧组合收据（d460b3aa 等）绑旧四轨，仅作历史。

## 本轮改动

- 四次 `--no-ff` 合并（零冲突）纳入四轨最终 HEAD；补登第六轮收口文档（`abb668cd`/`9266407f`）。
- 新增 I17：A→歧义B→复现A ×（旧 snooze / 旧 reviewed_no_change）——旧事件折归后逐条 rejected
  （terminal_state、归属历史节点）、复现节点独立 id 保持 open、链无环、歧义留审计、复现项进 02 排序、
  迟到动作 400/409。01 交接的 06 明确验收项就此关闭。
- 副产认知（非缺陷）：item_version 是证据/绑定/条件快照哈希——复现节点与历史节点同证据则内容版相同；「旧令牌 + 新 id」非真实旧页面可达，旧页面（旧 id）由 terminal_state 拒绝覆盖。

## 验证（全部在最终组合 `3d72b53a` 上）

- 06 套件 109 passed（I01–I12/I16 重跑 + I17）；四轨模块 110/139/125 passed。
- 前端 lint/typecheck/test(94)/build 全绿；e2e 31 passed / 2 skipped（隔离服务+临时用户态+独立端口；绑定 spec desktop 绿）。
- 全仓 ruff 干净；pytest **10137 passed / 77 skipped / exit=0**，收据 `~/.finance-runtime/test-receipts/20260914T052743Z-3d72b53a.json`（dirty=false，无排除）。
- `build_registry.py check` 一致；`graph_audit` 106 断言无漂移。

## 未验证 / 已知边界

- product_verified 仍**部分**：I13 真人试点、I14 visibilitychange、I15 真实前向实验未验（BLOCKED §3）；
  04 outcome_identity×03 结果身份合同、生产诊断策略/题包签署、02 生产 sources 未决。
- field_evidence 无。e2e 绑定 spec 的 tablet/mobile 按设计跳过。
- 旧动作是否继承到复现节点仍是产品决定（当前：不继承，rejected + 界面反馈）。

## 下一步

- 用户确认后才谈合并 main / push；部署与 /api/health revision 验收另授权。
- 真人试点（I13）与真实前向实验（I15）需另行授权结果源与参与者。

## 踩过的坑

- worktree 无 `.venv-workbench`：e2e 必须 `WORKBENCH_PYTHON=<主树>/.venv-workbench/bin/python pnpm test:e2e`，否则落宿主 3.14 缺 uvicorn。
- `#recur:<day>` 只喂 id 派生（dedup_key 加 salt），公开 id 是哈希——断言独立身份用「id 异 + dedup_key 同 + 链形」。
- 动作错误体是 `{code, message, detail}`——reason_code 在嵌套 `detail.detail`。磁盘满曾让 merge 报 Unable to write index，先 `df -h`。
