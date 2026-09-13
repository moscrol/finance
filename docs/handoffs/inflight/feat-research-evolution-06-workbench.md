# feat/research-evolution-06-workbench · 2026-09-14 · 研究进化 06：第三轮 T1–T5 返修完，等复审

## 这个分支做什么

01–05 接进既有 Workbench 会话，06 只组装不改域算法，单 writer `EvolutionStore`。第三轮 QC 的 T1–T5（退修清单：`docs/verification/re06-0c275716/REVIEW.md`）已全部返修完，等复审放行。

## 决策与被否方案

- T1：`create_message` 在启动执行器**前**调 `facade.bind_pending_rejudge_run` 登记可信 request→run 关联；否了「UI 加延时赌先后」「删 Q3 关联闸」。会话归属用「产生当前 request_event_id 的 rejudge 动作记录」回查（rejudgment 不存会话）；零/多候选不猜，等客户端显式 link_run。
- T1 配套：link_run 加终态折回全局幂等——派生键 `:terminal` 已录 → 版本闸**之前**重放（折回已推进 revision，迟到调用期望版本必过期；重放零迁移）。
- T2：run_links 带 `request_event_id` 代际；`find_run_link` 给代际就 fail closed（旧行无代际=不命中），否了通配豁免（造门禁看不见的旁路）。
- T3：服务端水合 `pending_task_continuation`（owner/会话/full_prompt 逐字匹配动作台账），否了改 App.tsx / 放开消息合同 run_id 非空——客户端自证不可信，台账才是核验源。
- T4：无 id 读总结按 `generated_at` 取最新；单份直取（兼容缺时间戳遗留行）；多链/并列/缺时间戳 → 400 要显式 id。否了 supersedes 链头——生产 `summarize()` 不写 supersedes。
- T5：`try_transaction` 外层 try/finally + fd/flock 双取得标志，os.open 抛错不再泄漏进程锁。

## 当前状态

- 代码 HEAD = `957e83f4`（已提交，工作树干净）。等第三轮复审；未合并、未部署。
- 前端本轮零改动（T3 由服务端解决）。
- 非显然决策的完整背景：`docs/handoffs/2026-09-14-re06-round3-t1-t5.md`。

## 已验证

- 第三轮探针 5/5 绿；仓内新 T1–T5 回归 7 例（rework 测试尾部）；研究进化套件+上轮探针 110 绿；消息热路径切片 354 绿；e2e 16 绿 2 跳过；ruff 定向干净。
- 全仓 10034 passed / 0 failed：收据 `~/.finance-runtime/test-receipts/20260913T181836Z-0c275716.json`（dirty_paths 恰为本次四代码文件，内容同提交）。

## 未验证 / 已知边界

- 前端 lint/vitest/build 本轮未重跑（无前端改动）；最终组合门禁归复审跑。
- T1「同会话两条待复核」歧义分支无测试——夹具世界只产一条维护项；该分支保守回退（不绑，等显式 link_run）。
- e2e 绑定真链路只覆盖 desktop（2 个跳过是非 desktop 项目）。

## 下一步

复审者重跑第三轮探针 + 组合门禁；放行后按原顺序合并（规格分支先进 main），用户确认前不合。

## 踩过的坑

- `git commit -- <paths> -m` 不行：`-m` 在 `--` 后被当 pathspec；消息放 `--` 前或用 `-F`。
- 全仓 pytest 会收集 `docs/verification/` 下的探针——探针进仓即进全量。
