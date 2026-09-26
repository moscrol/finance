# feat/verify-timepoint-forward-slot

## 这个分支做什么

「假设×可验证时点×推翻条件」范式出圈的收口两刀（Knevo 差距吸收第 2 项）：

- **B 刀**：新前瞻槽 `verification_timepoints`（verify_by=可观察指标×时间窗）进
  `FORWARD_HYPOTHESIS_OUTPUT_IDS`，登记面五处齐：集合真源（research_contract）/
  契约描述（episode_factory，缺则装配炸=R-20260825-04 同形）/ marker 词表
  （task_fulfillment，缺则瞎仪表）/ 提示词文案（episode_protocol forward_slot_rule）/
  挂载与豁免行为（集合驱动自动生效，钉 6 参数化自动覆盖）。
- **A 刀**：`_OUTLOOK_JUDGMENT_RE` 补「后续的?走势|后市」词形——SPT 有色题
  （theme_analysis「分析下…后续的走势」）此前不入闸，推翻条件/时点整组缺席
  （2026-08-25 生产契约冻结实测）。

## 侦察结论（本单为何这么小）

「范式出圈」的机制**早已存在**：`_with_forward_hypothesis_slots` 对任何题型的
前瞻信号问句挂可选三槽（optional-forward-slots，R-20260824-20 线）。真缺口只有
时点件缺槽 + theme 词形不入闸两处。冻结证据：`~/.finance-runtime/
substitute-probe-live-20260825/`（四题契约冻结，hotfix 后复跑）。

## 已验证

- 红→绿：7 新测（集合/描述/marker 可判/挂载/提示词/有色题入闸/事实题对照不误挂）。
- 存量钉 2 按语义更新为交集遍历（verification_timepoints 不在 market_forecast
  默认格，交集判据不补挂——钉的是「必选槽不降级」不是「全集在场」）。
- 探针族 + 前瞻槽族 + market_watch + outlook 65 过；ruff 0。

## 未验证 / 已知边界

- market_forecast 必选五件套未加时点槽（本单只做可选挂载；必选化需 outlook
  线自己的验收，另立）。
- 「后市」词形与 market_forecast 路由词族有重叠——原生前瞻题型交集判据兜住
  不重复挂，测试钉 2/3 锁定。
- live 模型是否真在时点格写「指标×时间窗」属质量观察，随自然样本回读。

## 下一步

合并切流后：自然样本回读 R-20260825-01…06；观察时点格 live 兑现率，
若模型常空绑再考虑 followup 角度联动（gap mirror 已有通道）。
