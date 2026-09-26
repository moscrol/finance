Spec PASS。固定范围 `c9bd82ff2e25fe2727347329706f7aeb98444ee8` → `e0f2a5c77e5b7d41eb4dcfe4d964d01b826b17e7`；首尾 HEAD 相同、候选树干净。未发现本片规格缺失、实现错误或越界扩展，可进入独立 Quality 审查。

批准规格要求“稳定键 root_query_id/root_sample_id/ranking_start/ranking_end，再保留观察终点一致”。[窗口实现](/Users/a77/fwp-wt-history-closeout-0920/intelligence/services/historical_research/window_binding.py:119)符合；真实 Session/Registry/RunStore 中，排名窗 1/17–1/22 扩到 1/29 后，个股经扩窗原件、原排名父件、同一父件续查均成功；两种父件并发均成功。不同合法根、伪造根/排名窗、不同观察终点、未交付父件、未授权扩窗及超授权终点均拒绝；读取父件后重试成功。直接父件血缘仍逐条校验，原件与合成库字节不变。

批准规格要求“保留原词搜索……查询数量及总命中有界……普通查询不额外外呼”。[查询实现](/Users/a77/fwp-wt-history-closeout-0920/scripts/code_map.py:517)经独立受控后端验证：原词优先、至多一次别名补查、来源+符号去重、总上限 20、普通词一次查询。[状态分型](/Users/a77/fwp-wt-history-closeout-0920/scripts/code_map.py:737)将缺 uvx、失败/畸形响应与合法零命中区分，入口和叙述仍独立。真实既有图的 `daily-full` 查询命中 `cmd_daily_full`/`run_daily_full`，原失败测试实际运行通过。

独立证据：四组行为探针 PASS；必要既有测试 **12 passed、0 failed、0 skipped**。见[行为结果](/Users/a77/.finance-runtime/reviews/research-closeout-20260920/history-closeout-review/spec/independent-results.json)、[探针源码](/Users/a77/.finance-runtime/reviews/research-closeout-20260920/history-closeout-review/spec/probe_review.py)、[命令索引](/Users/a77/.finance-runtime/reviews/research-closeout-20260920/history-closeout-review/spec/commands.jsonl)。作者大批测试收据仅作导航，没有冒充本轮重跑。

初轮量具错误及两次误写全局测试收据已如实保留，详见[校准记录](/Users/a77/.finance-runtime/reviews/research-closeout-20260920/history-closeout-review/spec/CALIBRATION.md)；不计候选缺陷。未改候选、原历史树或生产数据，未重建地图、跑整仓/前端/真实模型。#791 成员并集/相似定义、原四题自然模型验收及 main 全叶仍在本片之外。
