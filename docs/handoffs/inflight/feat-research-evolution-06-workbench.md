# feat/research-evolution-06-workbench · 2026-09-14 · 研究进化 06：第四轮 U1–U4 返修完，等复审

## 这个分支做什么

01–05 接进既有 Workbench 会话，06 只组装不改域算法，单 writer `EvolutionStore`。第四轮 QC 的 U1–U4（退修清单：`docs/verification/re06-957e83f4/REVIEW.md`）已全部返修完，等复审放行。第三轮 T1–T5 背景见 `docs/handoffs/2026-09-14-re06-round3-t1-t5.md`。

## 决策与被否方案

- U1/U2（接受侧绑定）：`bind_pending_rejudge_run` 不再看「唯一待复核」，改按**请求身份**登记——continuation 维护项坐标（核验当前代+本会话动作记录）/ full_prompt 逐字 / label 的 ≥4 字符前缀复述；零命中、多命中都不登记，普通聊天零 run_links 零迁移。关键张力：U3 setup 的裸「继续核查」必须绑（= label 前缀），U1 的「先不处理…市盈率」必须不绑——唯一判别面是内容串对 rejudge 动作记录持久化的 label/full_prompt。
- U2（补偿登记）：`_compensate_terminal_link`——显式 link_run 时 run 的用户消息确在本会话（非 RunStore 旁路）即补登当前代关联并折回。**不做墙钟时间窗**：消息/run 是真实时钟、requested_at 是注入时钟，跨域比较在验收环境恒假。
- U3：终态重放加会话匹配（重放不免授权，仍站版本闸前——QC 否决退回闸后）；run 会话闸前置到视图计算前（别会话无绑定会先 503 掩盖越界，探针只收 400/404/409）。
- U4：auto-pick 判断仅当 `attempts<=1` 且无 `last_failure`（无先前代际，时间窗不可能撞车）；多代际必须显式 `new_judgment_ref`。否了改 judgments writer 加归属字段（越 06 边界，留作登记依赖）。

## 当前状态

- 代码 HEAD = `ecd90a3c`（已提交，工作树干净）。等第四轮复审；未合并、未部署。
- 前端本轮零改动。非显然决策完整背景：`docs/handoffs/2026-09-14-re06-round4-u1-u4.md`。

## 已验证

- 第四轮探针 4/4 连续两次绿；QC 原 110 条命令 + 新仓内 5 条 = 115 绿；全仓 10043 passed / 0 failed（收据 `~/.finance-runtime/test-receipts/20260913T201520Z-b481804c.json`）；e2e 全套 31 绿 2 跳过（端口 19791/19794）；ruff 干净。

## 未验证 / 已知边界

- 「继续核查」遇两条待复核：label 相同 → 多命中不登记（落补偿路径），形状安全未专测。
- 内联折回后换基键+过期版本的重试得 409（语义正确；`:terminal` 派生键只有观察器路径写）。
- 前端四件套沿用候选结论（本轮无 diff）；最终组合门禁归复审跑。

## 下一步

复审者重跑新四针 + 原 110 命令 + 组合门禁；放行后按原顺序合并（规格分支先进 main），用户确认前不合。

## 踩过的坑

- `git commit -- <paths> -m` 不行：`-m` 在 `--` 后被当 pathspec；消息放 `--` 前或用 `-F`。
- 全仓 pytest 会收集 `docs/verification/` 下的探针——探针进仓即进全量。
