# 历史发现研究：接手入口

## 这个分支做什么
事后发现特征→假设→历史同类/失败/条件全集比较；接既有Workbench，不另造loop。

## 当前状态
用户要求先交接，所有agent已停。树 `/Users/a77/fwp-wt-historical-discovery`，分支 `codex/feat-historical-discovery`；代码固定 `5c980d79`，含7d49c9d8/b28d7331。本次只续存文档，没有两项待修问题的代码半成品。测试8809/8810已停，生产8792未动。

## 下一步
先读 `docs/handoffs/2026-09-09-historical-discovery-implementation.md`，里面有run/原件/重启命令和可复制启动prompt。
1. 修应用空池回退孤儿tool响应：M3第3/4轮400；应用发起调用缺assistant.tool_calls声明。应有durable应用事件并同源派生，保一次执行/重放/原E号；尚未实施。
2. 修history finish只认query误拒合法case：UI已存v2，但引用case触发history_unknown_result，正文变缺口模板。允许受控产物引用但case不能冒充计算/比较；补定义ID提示。
3. 降低并发复跑同六题+原UI追问，再独立复算/评回答；M5/M6本次429，不能当能力结论。

## 决策与被否方案
受限typed算子，未用任意SQL/新runtime；原件只经RunStore。修订用patch保留旧记录，否决模型全文重写。领域发布上限，保普通deadline豁免；恢复仍12条帽，原E号不重排。详见日期快照。

## 未验证 / 已知边界
端到端未通过。最新M1已成答但未独评；M2/M4与UI有history_unknown_result；M3恢复partial；M5/M6限流失败。`run_status=completed`只表示运行结束。S3仅纯候选桥，未正式评价/认证/S4记忆；strict PIT/独立性不冒充已建。L2/晚间卖方/晨汇pending_sync未排期。未合main、未跑全仓等价CI。

## 已验证
代码相关1101P，Ruff/提交门禁通过；收据 `20260908T191227Z-b28d7331.json`（target列全命令，随后固定5c980d）。UI确实保存同一case v2并保留旧反证，公开答案未成功。独立审计旧22原件2215检查0错/1198跳过，不能代替新轮验收。

## 踩过的坑
解释器用主树 `.venv-workbench/bin/python`。外部收据根 `/Users/a77/.finance-runtime/historical-discovery-20260909`；先看 `handoff-run-index.json` 和 `verified-ui-revision-preservation.json`。`verified-*`文件名不代表通过。冻结库只读勿重造，勿动主树他人改动；case/raw模型/DB不进Git。生产切换/合main需用户确认。
