# MACD 候选计分接线

- 材料身份：代码摘录
- 本机正文核验：2026-10-07；未在线重新核验。
- 来源：`intelligence/services/teaching_framework/stage_rules.py`
- 定位与指纹：见 `sources/index.json` 中 `code/structure-score-source.md`。
- 下方为连续原文摘录；其中的历史统计、agent 落法与用户引语保留原身份，不是本次实测或新增指令。

<!-- BEGIN VERBATIM EXCERPT -->
    if trend_up and (params or {}).get("upgrade_process_continuing"):
        hits.append(("主流主升2.0", "H:share_and_volume_trend_up"))
    # 第十九段：成交占比与量能的 n 日均都在升（过程，不是单日）。从共建主线来算进入；已在主升里算持续。
    if trend_up and origin == MAIN_RISE_ORIGIN:
        hits.append(("主流主升", "E:share_and_volume_trend_up"))
    if trend_up:
        hits.append(("主流主升", "H:share_and_volume_trend_up"))
    # 第六段流程：回踩下穿之后（周期仍在）、放量突破之前的缩量日 = 缩量右底的「缩量的过程」。
    if v("below_ma_cycle_retest_seen") is True and v("volume_band") == "shrink":
        hits.append(("缩量右底", "H:shrink_after_retest"))
    # 第二十三段：上证日线 MACD 底背离的观察 / 确认日，给缩量右底与共建主线各记一分（事件日才有，稀）。
    if (params or {}).get("structure_evidence", True) and (v("macd_bottom_div_observe") is True or v("macd_bottom_div_confirm") is True):
        hits.append(("缩量右底", "H:macd_bottom_div"))
        hits.append(("共建主线", "H:macd_bottom_div"))
    # 持续证据：视角值落在该段的共性区间内（区间从平台参照标注的校准期算出，见参数文件）。
    for stage, bands in stage_bands(params).items():
        for view, (lo, hi) in bands.items():
<!-- END VERBATIM EXCERPT -->
