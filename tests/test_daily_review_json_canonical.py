"""台账的真本源是 JSON，Markdown 是它的渲染物。

此前 build_daily_review 在内存里算完全部结构化数据后只序列化成 md，三个下游
（Workbench 投影 / 聊天 skill / 框架解读）只能各自反解 Markdown，都只解了
核心看板那张两列表——正式日报 93% 的内容进不了 Workbench。这里锁住三件事：

- 渲染规则可复现：每种 block 的空行/前缀写法固定，md 与旧版逐行一致；
- 目录由 sections 生成：编号与正文同源（旧模板手写目录漏了 §7，7–14 锚点错位一节）；
- 同计数排序稳定：矩阵行 / 分布表两次生成行序一致（旧版靠 Counter.most_common 平局随机）。
"""
from __future__ import annotations

import json

from market_feature_store.reports.daily_review import (
    DAILY_REVIEW_SCHEMA,
    _anchor,
    _count_matrix_rows,
    _table_block,
    render_daily_review_markdown,
)


def _report() -> dict:
    return {
        "schema": DAILY_REVIEW_SCHEMA,
        "trade_date": "2026-09-02",
        "prev_trade_date": "2026-09-01",
        "generated_at": "2026-09-02 20:40:05",
        "warnings": ["申万一级实时源当日缺数。"],
        "core_board": [
            {"dimension": "市场性质", "conclusion": "普通交易日 / 底部横盘阶段 第26天"},
        ],
        "facts": {"nature": "普通交易日"},
        "sections": [
            {
                "id": "market",
                "index": 1,
                "title": "指数 / 量能 / 偏离度 / 市场阶段",
                "blocks": [
                    _table_block(["项目", "数值"], [["市场阶段", "底部横盘阶段 第26天"]]),
                    {"kind": "conclusion", "text": "今日为 **普通交易日**。"},
                ],
            },
            {
                "id": "sentiment",
                "index": 2,
                "title": "市场情绪",
                "blocks": [
                    _table_block(["项目", "今日", "昨日"], [["涨家数", 1541, 3387]]),
                    {"kind": "chart", "path": "2026-09-02-advancers-ma5.png", "uri": "file:///x/2026-09-02-advancers-ma5.png"},
                    _table_block(["区间", "状态"], [["波谷→波峰", "上升"]], title="涨家数 MA5 波段区间"),
                    {"kind": "note", "text": "**MA5位置**：当前处于 **震荡区间**。"},
                    {"kind": "conclusion", "text": "涨家数 1541。"},
                ],
            },
            {
                "id": "limit_up",
                "index": 3,
                "title": "涨停题材",
                "blocks": [
                    {"kind": "heading", "text": "近15日子板块涨停矩阵"},
                    {"kind": "note", "text": "单元格为涨停个股数。"},
                    {"kind": "heading", "text": "通信"},
                    {"kind": "text", "text": "近15个交易日暂无涨停映射。"},
                    {"kind": "conclusion", "text": "涨停题材核心集中在 储能。"},
                ],
            },
            {
                "id": "coverage",
                "index": 4,
                "title": "数据覆盖检查",
                "blocks": [_table_block(["表", "状态"], [["fact_market_daily", "OK"]])],
            },
            {
                "id": "assessment",
                "index": 5,
                "title": "市场环境总评",
                "blocks": [{"kind": "note", "text": "2026-09-02 市场性质为 **普通交易日**。"}],
            },
        ],
        "assessment": "2026-09-02 市场性质为 **普通交易日**。",
        "chart_path": "/x/2026-09-02-advancers-ma5.png",
    }


def test_markdown_rendering_follows_the_legacy_layout_exactly() -> None:
    expected = """# 2026-09-02 每日市场复盘

> 自动生成自 `market_feature_store` 本地 DuckDB。报告只读取已入库数据，不临时编造缺失项。
> ⚠️ 数据降级：申万一级实时源当日缺数。

## 核心看板
| 维度 | 结论 |
|---|---|
| 市场性质 | 普通交易日 / 底部横盘阶段 第26天 |

## 目录
- [1. 指数 / 量能 / 偏离度 / 市场阶段](#1-指数--量能--偏离度--市场阶段)
- [2. 市场情绪](#2-市场情绪)
- [3. 涨停题材](#3-涨停题材)
- [4. 数据覆盖检查](#4-数据覆盖检查)
- [5. 市场环境总评](#5-市场环境总评)

---

## 1. 指数 / 量能 / 偏离度 / 市场阶段
| 项目 | 数值 |
|---|---|
| 市场阶段 | 底部横盘阶段 第26天 |

> **结论**：今日为 **普通交易日**。

---

## 2. 市场情绪
| 项目 | 今日 | 昨日 |
|---|---|---|
| 涨家数 | 1541 | 3387 |

[![涨家数MA5](2026-09-02-advancers-ma5.png)](file:///x/2026-09-02-advancers-ma5.png)

> [点击打开涨家数 MA5 图](file:///x/2026-09-02-advancers-ma5.png)

### 涨家数 MA5 波段区间
| 区间 | 状态 |
|---|---|
| 波谷→波峰 | 上升 |

> **MA5位置**：当前处于 **震荡区间**。

> **结论**：涨家数 1541。

---

## 3. 涨停题材
### 近15日子板块涨停矩阵
> 单元格为涨停个股数。

### 通信
近15个交易日暂无涨停映射。

> **结论**：涨停题材核心集中在 储能。

---

## 4. 数据覆盖检查
| 表 | 状态 |
|---|---|
| fact_market_daily | OK |

---

## 5. 市场环境总评
> 2026-09-02 市场性质为 **普通交易日**。

生成时间：2026-09-02 20:40:05"""
    assert render_daily_review_markdown(_report()) == expected


def test_markdown_survives_a_json_round_trip() -> None:
    report = _report()
    round_tripped = json.loads(json.dumps(report, ensure_ascii=False, default=str))
    assert render_daily_review_markdown(round_tripped) == render_daily_review_markdown(report)


def test_toc_anchors_match_github_slugs_for_real_headings() -> None:
    assert _anchor("1. 指数 / 量能 / 偏离度 / 市场阶段") == "1-指数--量能--偏离度--市场阶段"
    assert _anchor("4. 1/3/5/10 日板块涨幅前五") == "4-13510-日板块涨幅前五"
    assert _anchor("7. 申万一级行业个股发动机：成交占比前三行业") == "7-申万一级行业个股发动机成交占比前三行业"
    assert _anchor("13. 近五日加权涨幅 Top10") == "13-近五日加权涨幅-top10"


def test_table_block_keeps_numbers_and_stringifies_dates() -> None:
    from datetime import date

    block = _table_block(["股票", "连板数", "首板日期"], [["国芳集团", 4, date(2026, 8, 28)]])
    assert block["rows"] == [["国芳集团", 4, "2026-08-28"]]


def test_count_matrix_rows_break_ties_by_name() -> None:
    dates = ["2026-09-01", "2026-09-02"]
    data = [
        ("2026-09-01", "芯片", 2),
        ("2026-09-02", "MCU芯片", 1),
        ("2026-09-02", "先进封装", 1),
        ("2026-09-01", "AI眼镜", 3),
    ]
    rows = _count_matrix_rows(data, dates, top=3)
    assert [row[0] for row in rows] == ["AI眼镜", "芯片", "MCU芯片"]
    assert rows[0] == ["AI眼镜", 3, "-"]
    assert _count_matrix_rows(list(reversed(data)), dates, top=3) == rows
