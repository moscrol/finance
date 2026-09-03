# 工具饥饿汇总

扫描 1218 个 run，事件 12 条。

| 类型 | 请求名 | 次数 | 样本 run_id |
| --- | --- | ---: | --- |
| finance_query_rejected | theme_limit_heat_daily | 4 | run_20260828_013535_597659, run_20260828_013634_297886, run_20260828_002209_616295, run_20260828_010136_666196 |
| finance_query_rejected | market_daily | 2 | run_20260828_015506_501373, run_20260828_190919_296971 |
| finance_query_rejected | sector_daily | 2 | run_20260828_013634_297886, run_20260828_010136_666196 |
| finance_query_rejected | stock_daily | 2 | run_20260830_015207_802388 |
| finance_query_rejected | leader_height_daily | 1 | run_20260827_203359_346648 |
| finance_query_rejected | sector_stock_daily | 1 | run_20260828_214035_764162 |

建议每周扫一次 runs 目录，把 count 最高的 dataset/工具名推进决策队列；节奏最终由用户定。
