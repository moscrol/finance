# 2026-08-27 · code map 夜间刷新 + 宏观理解路由表（docs/macro-map-and-code-map-refresh 合并快照）

分支两提交 + 一条顺手修，经用户确认合入 main。背景：元资产盘点 Phase A 的仓内落点，
路线图全文在 agent-memory `00_inbox/2026-08-27-meta-asset-inventory-and-bootstrap-roadmap.md`。

## 做了什么（按发现顺序）

1. `AGENTS.md` 代码地图节加「宏观理解路由（五层地图）」表：问题形状 → 哪张图 → 保鲜方式。
   只加 AGENTS.md 一处，CLAUDE.md 不复制（两份清单必漂，BUILD 模式 6）。
2. 新增 `scripts/install_code_map_refresh.py`：launchd 夜间刷新（每日 04:25）安装器 +
   无人值守运行器。已在本机挂载生效（`com.a77.finance-code-map-refresh`）。
3. 合并前 registry-check 发现 `ws/perspective-distill` computedHash 漂移——**基线
   fea0633e 已有的存量**（detached 干净树复核同红，本分支不含 skill 改动）。修法：
   干净临时树跑 `scan`（避免把主树他人在途的 `skills/duckdb-backfill/SKILL.md` 烤进
   注册表），diff 核实仅一条哈希 + 时间戳，四道检查全绿后带回主树提交。

## 决策与被否方案

- 选 launchd 夜跑（04:25）／否 commit 钩子——build 走 uvx，全量分钟级拖慢提交；
  否 SessionStart 懒重建——拖慢开工且并发会话可能同时写 graph.db。实测增量 update
  仅 11s，但首次/全量仍慢，夜跑口径不变。
- `run` 在 status exit=3 时不 build、退出 3／否「无脑重建」——错误状态上重建会掩盖
  真问题（fail closed）。
- plist 用 stdlib plistlib 生成 + plutil -lint／否 sed 模板——多字节路径不可靠
  （沿用 checkpoint-recheck-mac-setup 既有结论）。
- registry 漂移在干净临时树修／否在主树直接 scan——scan 读工作树，主树有他人未提交
  的 SKILL.md 编辑，直接扫会把未合内容的哈希写进注册表（假一致）。

## 验证与收据

- `run` 两分支实测 [2026-08-27]：stale→build exit 0（n=19771 @fea0633、增量 11s）；
  fresh→skip。install 过 plutil -lint、launchctl bootstrap gui 域成功。
- 合并等价检查 [2026-08-27]：前端叶四连绿（lint / typecheck / 70 tests / build，主树
  重装 node_modules 后）；registry 四检查绿（含本分支顺手修的存量漂移）；python 叶
  主树全量 6829P/**1F**——该红经 A/B 归因为**环境耦合非本分支回归**（见下），
  干净树基线 fea0633e 与分支尖单测均绿；最终读数以分支尖**干净树全量**为准
  （收据落 `~/.finance-runtime/test-receipts/`）。e2e 未跑：本分支零 webapp/runtime
  代码路径（AGENTS.md / scripts 新独立文件 / docs / skills.registry.json），此为
  成立条件而非豁免先例。

## 顺手发现的存量 bug（不在本分支修，待立工单）

`test_conversation_orchestrator.py::test_completed_stream_persists_human_readable_answer`
在**带真实生产库的树**上必红：market_watch 盘面组件包 + 替补观察经 repo 根相对路径
读到真实 `db/market_feature_store.duckdb`，把当日（2026-08-27）真数据注入答案
（「## 指定日盘面组件包」块），与钉死的期望文案不符；干净 worktree 无 db/ 文件故绿。
这是 #310/#312「出生即红环境依赖」的同形复发（BUILD「新数据源接入第一问」），
修法同款：给组件包数据源加显式关闭开关并在 conftest 钉死为关。当日 daily-full
一跑完、库里有当日 published 快照，此测试就会在主树红——**不是负载抖动，别当抖动记**。

## 坑（接手要知道的）

- launchd 域 PATH 不含 homebrew：安装器生成 plist 时注入 `dirname(uvx)`；
  **换机/换 python 后要重跑 install**。plist 钉住安装时的树与解释器路径，
  只在主检出树上安装。
- 夜跑日志在 `~/Library/Logs/com.a77.finance-code-map-refresh.log`；回滚
  `python3 scripts/install_code_map_refresh.py uninstall`。

## 后续（不在本分支）

- harness-reference KIT/BUILD 回写「code map 夜间刷新」一行（其本地树有他人在途
  改动，等收口或另开干净树）。
- `agent-run-review` 迁共享 skill 仓。
- Phase B 第二领域移植试点（候选对比见路线图）。
