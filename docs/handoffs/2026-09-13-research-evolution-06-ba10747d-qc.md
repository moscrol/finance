# 研究进化 06 返修复审：ba10747d

## 结论与范围

**继续返修，不同意“13/13 已全部修复”，暂不签工程全链验收或合并部署。**

候选固定 `feat/research-evolution-06-workbench@ba10747d`；本轮差量 `4e95c20b..ba10747d`。主检出树存在他人改动，未动；候选执行树干净、未改。独立复审树位于 `/Users/a77/.finance-runtime/reviews/research-evolution-06-ba10747d/tree`，审查文档分支 `docs/qc-research-evolution-06-ba10747d`。不复审或重复归罪 01–05 的已有领域算法问题。

**先承认已修好的部分**：S1 的读判写事务、S2 已有台账冲突批零写入、S3 dry-run 无业务写入、R2 评分前曝光、R8 顺序重试的绑定/前端事件、R9 当前源读不到为 unknown、R10 维护动作跨会话重放冲突，均有本轮运行证据。独立双进程 S1 两种竞争都一胜一409且只落一行，不依据旧 barrier 死锁签字。

以下按用户风险排序，共九组具体发现。代码位置均相对于候选根，复审树与候选这些文件逐字节相同。

## Q1 · P1 · 跟踪表单实际请求仍是 422（R4）

- `intelligence/webapp/src/components/ResearchEvolutionPanel.tsx:460` 发送 `object_ref: trackable.object_ref.ref`，即字符串。
- `intelligence/webapp/src/api.ts:390` 原样 JSON 序列化；`intelligence/api/research_evolution.py:33` 要求 `dict[str, Any]`，`facade.py:570` 同样要求 Mapping。
- 将真实表单形状交给真实 bindings API，得到 **422 / dict_type / body.object_ref**，不能建立首条绑定。组件原测试恰好把这个错误字符串当成期望值，故能绿。
- 最小修复：表单提交完整的受控 object_ref，或在明确的边界统一适配；补“浏览器表单→实际 bindings→刷新”的非空态检查。

## Q2 · P1 · 初次登记后没有终态收尾路径（R1）

- `App.tsx:810–822` 只在消息202后调用一次 link_run；run 当时仍运行便在 `facade.py:763–765` 返回 registered，只写关联。
- `App.tsx:259–318` 的 finalizeRun 只重拉投影，不再次 link；`ResearchEvolutionPanel.tsx:164–221` 无挂接核查结果/取消按钮。06 run观察器只写05测量，不消费维护关联。
- 真实 ObservingRunStore 建 run→登记 link→原 writer 写新判断→run completed→刷新，维护项仍是 **rejudgment_requested**。失败/取消终态也没有界面收尾通路。
- 原合同测试手工调用第二次 link_run，因此绕过了待验接线。需终态协调或可恢复的显式确认控件（含重启后），不能让GET偷写，也不能仅靠测试脚本再POST。

## Q3 · P1 · 同会话无关 run 仍可假关闭/假退回（R7）

- `facade.py:889–897` 把 `association="session"` 当可接受的最低关联；不要求该run对应本次请求，也不检查run开始/结束时刻。`run_links` 只绑 item+run，没有 request_event_id/attempt 身份。
- 先在同会话完成一条无关run，再发起维护复核，原writer写一条请求后的**无关主题**新判断，将两者拼给link_run：**200 / rejudgment_linked / association=session，投影closed**。
- 另一反例：用同会话过去失败的run关联当前请求：**200 / rejudgment_failed，投影open**。
- 现有“非原判断+同会话+判断时间”是必要但不充分条件。应要求本次维护请求/版本/attempt的可信关联，判断与该run/对象有可核联系；不能把关联强度标签当放行闸。

## Q4 · P1 · 练习有按钮但无法按实际评分合同作答/看答案（R5）

- `ResearchEvolutionPanel.tsx:516–517` 固定提交 `selected_choices=[] / cited_refs=[]`；唯一输入是rationale。04 `evaluate_exercise_response` 只对结构化选择和引用做确定性评分，散文留manual_review。选项非空的题用户无法答对。
- 同组件 `:579–603` 只渲染顶层原始值，滤掉真正的 `checks[]`、`missing_evidence_refs[]`、`answer_key{...}`。
- 使用与真服务一致的反馈/揭示形状运行组件，两个正确合同断言均失败：揭示区只剩 exercise_id/exposure_id/answer_key_ref/limitation；评分区只剩状态/解释引用等，没有答案与评分明细。
- 需结构化作答、真实检查明细/答案渲染；若题包缺可展示选项则显式登记跨轨合同，而不是把空数组当用户回答。不能用假的 `status:"correct"` 回包代替04真实形状。

## Q5 · P2 · 新 link_run 分支没守幂等合同

- `facade.py:763–765` 在append_action前提前return，未记录或绑定 idempotency_key；`facade.py:883` 每次重新盖 registered_at，`store.py:289` 将它纳入摘要。
- 同key同payload运行中登记，推进时钟1秒重试：**200→409 idempotency_payload_mismatch**。
- 同key改为另一个运行中run：**两次200，两条关联**，异载荷不冲突。
- 关联自然键还缺本次复核请求身份，后续尝试可能捡回旧link。需独立保存登记动作原结果与请求作用域，重试复用首次时间；注册与终态结算若是不同操作，明确分开合同。

## Q6 · P2 · select_task 完全未消费幂等键

- `facade.py:1035–1090` 接收 idempotency_key，却既不查也不写操作记录；每次用now和nonce创建新task_selected事件。
- 同key同payload推进时钟后重试，两次 `replayed=false`，台账**2条task_selected**。前端每次成功又发消息，网络重试会扩大成重复研究。
- 应按owner+conversation+task+payload记录选择结果，并让前端重放不自动再启动一轮。与Q5同属幂等覆盖漏分支，但要分别补测试。

## Q7 · P2 · 下一任务的来源/版本在消息边界丢失（R6）

- `facade.py:1068–1084` 把source_refs/object_refs放在continuation.click_payload，但inherits只含task_id与scope字符串。
- `app.py:1499–1511` 的ContinuationRequest没有click_payload；默认额外字段被丢弃。整包POST获202，存到真实用户消息的continuation却没有维护项id、来源版本与object_refs。
- 本轮在已有完成轮次的场景实测，source_refs非空但源id/version均不在落盘continuation。无起源run时前端还会把continuation整体省略，task_id/scope一并消失。
- 应在受控消息合同允许的字段里完整运输并在消费端验证，或保存受控任务引用让执行端解析；只检查actions响应字典不够。

## Q8 · P2 · 05试点总结“查看原件”必报缺receipt_id（R5）

- `facade.py:432–440` 广告pilot_summary时仅给summary_id；`ResearchEvolutionPanel.tsx:702` 仅发送ref.receipt_id，没回退summary_id。
- 服务端 `facade.py:1302–1307` 明确要求receipt_id。真实总结原件存在，照组件构造动作仍 **400 invalid_request（缺少receipt_id）**；组件发送合同探针同样失败。
- 需统一内容id适配，并分别验证03收据、05测量收据、05总结三种，而非只测method_validation_receipt一类。

## Q9 · P2 · 测量文件锁同步阻塞真实 run（R3）

- `run_observer.py:57–60` 在create_run返回前同步落05事件，`:155` 使用EvolutionStore.transaction的无deadline阻塞锁。异常被捕获不代表等待不会阻塞。
- 另一线程持有同owner的EvolutionStore锁时，创建run不能返回，释放锁后才返回。本轮等待窗口300ms只用来确认锁依赖，不宣称性能趋势。
- S1把完整当前投影评估移入此锁，慢取数/试点批导入均可影响被测run的提交或终态回调。需限时/非阻塞观测与可追踪缺测，或异步有界队列；不能把测量失败降级写成“绝不阻塞”却保留无界等待。

## 独立证据与复跑

证据根：`/Users/a77/.finance-runtime/reviews/research-evolution-06-ba10747d/`。

| 证据 | 本轮结果 |
|---|---|
| `suite.log`，原06五文件 | **80 passed**，收据 `~/.finance-runtime/test-receipts/20260913T134637Z-ba10747d.json`，测试时固定候选/干净树 |
| `probe_cas.py` / `cas-result.json` | 真双进程、同步点位于事务之前：同expected_revision和同key异payload两种竞争均一200一409、1条动作 |
| `test_review_contracts.py` / `review-probes.log` | **9 failed / 1 passed**；9条均为正确合同失败，1条为“终态刷新仍pending”诊断反例复现成功，不代表产品通过 |
| `ResearchEvolutionReview.test.tsx` / `ui-review.log` | **3 failed**：真实嵌套答案、评分检查均不可见；summary id不下传 |
| 本轮定向Ruff | research_evolution服务/API及返修合同测试通过 |

Python复跑：在证据根/tree，`PYTHONPATH="$PWD" /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q -s ../test_review_contracts.py`。所有用户态为pytest临时根；模型执行器为确定性桩，原API、领域函数、run/判断writer均真实。CAS脚本直接用同一解释器执行。前端探针需复制到隔离树webapp/src/components/并安装/连接该树依赖，再运行vitest；本轮执行后已移回证据根，不把红探针塞进候选测试集。

## 收据审计与未验证边界

- 已读原件 `20260913T131404Z-297c47c3.json`：10014P/0F/77 skipped/exit0，dirty=false，解释器正确；`297c47c3..ba10747d` 确实只有四个文档文件变化。**不否定此数字真实性，也不把它冒充ba10747d全量或合流收据**。
- PROGRESS原文记录的命令是 `pytest -q --ignore=test_codex_sandbox.py`，不是毫无排除的全仓命令。最终合入需按现役规则核对豁免/skip及候选门禁，不因“基线红”自动豁免。
- 本轮没重跑全仓Python、完整前端/e2e/registry或真实浏览器全链；已有确定性阻断，不用全量绿覆盖功能反例。执行者e2e的15P是5条场景×3project，新增的是两条API拒绝针，并未经过有绑定/练习数据的完整UI链。
- R3写出自用run事件的局部接线成立，但05真实配对I13与停测I11仍不可由它推导：观察器全部写workbench自用pilot、task/case_pair为空；不拿“缺真人”替代本可合成的工程接线验收。本轮未另计此项缺口。
- 真实前向/真人效果/实际模型内容质量未验，未接触生产库、真实用户记录或8792。

## 决策与返修要求

| 选择 | 否决 | 理由 |
|---|---|---|
| 独立正确合同探针+真实边界payload | 旧反例失败/死锁一概当通过 | 失败可能是测试过时、首个断言中止或另一处缺陷 |
| 保留80P与原全仓收据成立范围 | 把局部反例读成全仓测试造假 | 它们测的是不同命题 |
| 先退回06补接线，不改01–05算法 | 继续加mock status或测试内手动第二次link掩盖缺口 | 最终要证明用户真实可达，而非模块存在 |

下一轮必须过：真实表单建绑定→变化→继续核查→消息202→run终态→可恢复新判断闭合；同会话无关run/过往失败run拒绝；运行中link与select的同key重放/异payload冲突；实际04反馈形状完整可见；三种收据原件分别打开；观察器争锁不拖住被测run。随后最终组合revision门禁，仍待用户授权合并与部署。
