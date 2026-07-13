import json

import duckdb

from intelligence.services.workbench_overview import build_workbench_overview


def _prepare_market_db(path) -> None:
    con = duckdb.connect(str(path))
    con.execute(
        """
        CREATE TABLE fact_market_daily (
            trade_date DATE,
            market_stage TEXT,
            advancers INTEGER,
            limit_up INTEGER,
            limit_down INTEGER,
            total_amount DOUBLE,
            amount_vs_yesterday_pct DOUBLE,
            amount_ma20 DOUBLE,
            top3_industry_ratio DOUBLE,
            concentration_state TEXT,
            strength_marginal_pct DOUBLE,
            strength_status TEXT
        );
        INSERT INTO fact_market_daily VALUES (
            '2026-07-10', '轮动', 3210, 67, 4, 15000, 8.2, 14200,
            38.0, '中等集中', 3.5, '增强'
        );
        CREATE TABLE fact_mainline_theme_daily (
            trade_date DATE,
            theme_code TEXT,
            theme_name TEXT,
            sector_count INTEGER,
            min_sort INTEGER
        );
        INSERT INTO fact_mainline_theme_daily VALUES
            ('2026-07-10', 'T1', '半导体', 3, 1),
            ('2026-07-10', 'T2', 'AI算力', 2, 2);
        CREATE TABLE fact_mainline_sector_daily (
            trade_date DATE,
            theme_code TEXT,
            sector_name TEXT,
            cycle_status TEXT,
            sort_no INTEGER
        );
        INSERT INTO fact_mainline_sector_daily
        VALUES ('2026-06-30', 'T1', '旧板块', '主升', 1);
        CREATE TABLE fact_mainline_stock_daily (
            trade_date DATE,
            theme_code TEXT,
            stock_ts_code TEXT
        );
        INSERT INTO fact_mainline_stock_daily
        VALUES ('2026-07-10', 'T1', '000001.SZ');
        CREATE TABLE fact_sector_daily (trade_date DATE);
        INSERT INTO fact_sector_daily VALUES ('2026-07-10');
        CREATE TABLE feature_market_window (
            as_of_date DATE,
            start_date DATE,
            end_date DATE,
            advancers_ma5 DOUBLE,
            breadth_trend TEXT
        );
        INSERT INTO feature_market_window
        VALUES ('2026-07-10', '2026-07-04', '2026-07-10', 2800, '向上');
        CREATE TABLE feature_l2_capital_flow_daily (
            trade_date DATE,
            scan_type TEXT,
            stock_code TEXT,
            stock_name TEXT,
            main_buy_net_wan DOUBLE,
            total_buy_net_wan DOUBLE,
            score DOUBLE,
            rank INTEGER,
            pct_change DOUBLE
        );
        INSERT INTO feature_l2_capital_flow_daily VALUES
            ('2026-07-10', 'top100', '000001', '平安银行', 900, 700, 1.2, 2, -1.0),
            ('2026-07-09', 'top100', '000001', '平安银行', 500, 400, 0.8, 5, 1.2);
        CREATE TABLE feature_l2_quant_orders_daily (
            trade_date DATE,
            stock_code TEXT,
            stock_name TEXT,
            quant_amount_wan DOUBLE,
            quant_pct_of_big_buy DOUBLE,
            cluster_count INTEGER,
            biggest_cluster TEXT,
            rank INTEGER
        );
        """
    )
    con.close()


def test_overview_keeps_each_data_granularity_fail_closed(tmp_path) -> None:
    repo = tmp_path / "repo"
    wiki = tmp_path / "wiki"
    (repo / "db").mkdir(parents=True)
    wiki.mkdir()
    _prepare_market_db(repo / "db" / "market_feature_store.duckdb")
    exports = repo / "market_feature_store" / "exports"
    exports.mkdir(parents=True)
    (exports / "2026-07-01-daily-agent.json").write_text(
        json.dumps(
            {
                "date": "2026-07-01",
                "decision": {
                    "new_logic_candidate": [
                        {
                            "matched_theme": "半导体",
                            "logic_lifecycle": {"生命周期阶段": "催化共振"},
                        }
                    ]
                },
                "research_queue": {
                    "today_wait_market_validation": [
                        {
                            "目标": "半导体",
                            "理由": "已有 L1/L2 材料，等待 L3 事实",
                            "建议动作": "补 L2 基线，再做 L3 验证，不重复 IMA",
                        }
                    ]
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    overview = build_workbench_overview(repo, wiki)

    assert overview["as_of_date"] == "2026-07-10"
    assert overview["market"]["mainlines"] == ["半导体", "AI算力"]
    assert overview["market"]["breadth_trend"] == "向上"
    assert overview["themes"][0]["knowledge_stage"] == "催化共振"
    assert overview["themes"][0]["knowledge_date"] == "2026-07-01"
    assert overview["themes"][0]["market_stage"] == "未确认"
    assert overview["themes"][0]["detail_status"] == "stale"
    assert overview["themes"][0]["sectors"] == []
    assert overview["moneyflow_trends"][0]["stock_name"] == "平安银行"
    assert overview["moneyflow_trends"][0]["consecutive_inflow_days"] == 2
    assert overview["moneyflow_trends"][0]["rank_change"] == 3
    assert overview["moneyflow_trends"][0]["divergence"] == "价格跌 / 资金流入"
    statuses = {item["key"]: item for item in overview["data_status"]}
    assert statuses["market"]["status"] == "complete"
    assert statuses["mainline_sector"]["status"] == "stale"
    assert statuses["mainline_stock"]["status"] == "partial"
    assert statuses["mainline_stock"]["coverage"] == {
        "covered": 1,
        "total": 2,
        "missing": 1,
    }
    assert statuses["knowledge"]["status"] == "stale"
    signal = overview["signals"]["pending"][0]
    assert signal["source_type"] == "晨汇 / 研究队列"
    assert signal["summary"] == "已有研究叙事与基础资料，等待官方披露事实"
    assert signal["next_validation"] == "补公司基础资料，再做官方披露验证，不重复研究队列"


def test_overview_returns_explicit_missing_state_without_database(tmp_path) -> None:
    overview = build_workbench_overview(tmp_path / "repo", tmp_path / "wiki")

    assert overview["as_of_date"] is None
    assert overview["market"]["stage"] == "数据缺失"
    assert overview["data_status"][0]["status"] == "missing"
