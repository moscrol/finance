# feat/substitute-probe-weekly-p1a

## 这个分支做什么

替补观察探针 P1-a（最后一片）：weekly 五日包**仅最新交易日袋**开
`substitute_probes=True`，`_render_day` 在四袋行后标签先行尾接替补池；
历史日行为逐字节不变。至此探针三片（盘面 P0 / 一般题 P1-b / 展望 weekly P1-a）全落。

## 已验证

- 红→绿：3 新测（仅最新日出探针 / detail 标签先于股名且历史日无块 / 覆盖时无块）。
- 存量回归 50 过（outlook weekly + 探针 P0/P1-b + market_watch component first）。
- ruff 0。
- live 真实库五日窗（08-18..08-24）：仅 08-24 出探针（医药→医药医疗→药明康德/沃森生物），
  历史日 probes 全空，detail 尾接形状正确。

## 未验证 / 已知边界

- 全量 pytest 结果以提交时后台跑为准（基线 6397P）。
- 展望题 episode 全链 live（模型引用替补池）未跑；生产自然样本未回读，台账保持 pending。

## 下一步

1. 合 PR（等用户确认）→ 切 8792。
2. 下一单：「假设×可验证时点×推翻条件」范式出圈设计稿（Knevo 差距第 2 项）。
