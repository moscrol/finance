"""单次研究全口径成本报表（INDEX #23）：合成 run 目录 → 报表数值。

5 个 completed run：3 个新格式带 ``metrics.judge_usage``（其中 1 个估算），2 个旧格式
没有该键 → ``judge_unrecorded_runs == 2``、不崩。分位数与元/次全部手算对照。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from intelligence.eval import research_cost

PRICING = {
    "prices": [
        {
            "model_pattern": "glm-5.2*",
            "input_cny_per_m": 8,
            "output_cny_per_m": 28,
            "cache_hit_cny_per_m": 2,
            "source_url": "https://bigmodel.cn/pricing",
            "checked_at": "2026-09-04",
        },
        {
            "model_pattern": "test-judge",
            "input_cny_per_m": 10,
            "output_cny_per_m": 50,
            "cache_hit_cny_per_m": None,
            "source_url": "https://example.invalid",
            "checked_at": "2026-09-05",
        },
        {
            "model_pattern": "unpriced-judge",
            "input_cny_per_m": None,
            "output_cny_per_m": None,
            "cache_hit_cny_per_m": None,
            "source_url": None,
            "checked_at": None,
        },
    ]
}


def _write_run(
    root: Path,
    name: str,
    *,
    created_at: str,
    status: str = "completed",
    writer: tuple[int, int] | None = (40_000, 1_000),
    judge: dict | None = None,
    old_format: bool = False,
    episode: bool = True,
    model: str | None = "glm-5.2",
) -> Path:
    run_dir = root / name
    run_dir.mkdir(parents=True)
    (run_dir / "run.json").write_text(
        json.dumps({"run_id": name, "status": status, "created_at": created_at}),
        encoding="utf-8",
    )
    if model is not None:
        (run_dir / "report.json").write_text(
            json.dumps({"llm": {"used": True, "provider": "zhipu", "model": model}}),
            encoding="utf-8",
        )
    if not episode:
        return run_dir
    outcome: dict = {"status": "completed"}
    if writer is not None:
        outcome["usage"] = {
            "llm_calls": 3,
            "tool_calls": 2,
            "input_tokens": writer[0],
            "output_tokens": writer[1],
        }
    metrics: dict = {
        "provider_attempts": 3,
        "tool_calls": 2,
        "duplicate_queries": 0,
        "structural_status": "completed",
        "semantic_status": "passed",
    }
    if not old_format:
        metrics["judge_usage"] = judge or {
            "calls": 0,
            "input_tokens": None,
            "output_tokens": None,
            "usage_source": None,
        }
    (run_dir / "continuous-episode.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "execution_kind": "continuous_episode",
                "outcome": outcome,
                "metrics": metrics,
            }
        ),
        encoding="utf-8",
    )
    return run_dir


def _judge(calls: int, input_tokens: int, output_tokens: int, source: str) -> dict:
    return {
        "calls": calls,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "usage_source": source,
    }


@pytest.fixture
def synthetic_runs(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "runs"
    root.mkdir()
    day = "2026-09-0{}T10:00:00+08:00"
    _write_run(root, "run_20260901_100000_a", created_at=day.format(1), writer=(40_000, 1_000), judge=_judge(1, 20_000, 1_000, "cli"))
    _write_run(root, "run_20260902_100000_b", created_at=day.format(2), writer=(30_000, 1_500), judge=_judge(2, 40_000, 2_000, "cli"))
    _write_run(root, "run_20260903_100000_c", created_at=day.format(3), writer=(50_000, 2_000), judge=_judge(1, 1_000, 100, "estimated"))
    _write_run(root, "run_20260904_100000_d", created_at=day.format(4), writer=(20_000, 500), old_format=True)
    _write_run(root, "run_20260905_100000_e", created_at=day.format(5), writer=(60_000, 3_000), old_format=True)
    # 不进统计的三种：未完成 / 没有 episode 文件 / 写手 usage 为 0
    _write_run(root, "run_20260905_110000_f", created_at=day.format(5), status="failed", judge=_judge(1, 5, 5, "cli"))
    _write_run(root, "run_20260905_120000_g", created_at=day.format(5), episode=False)
    _write_run(root, "run_20260905_130000_h", created_at=day.format(5), writer=(0, 0), judge=_judge(1, 5, 5, "cli"))
    pricing = tmp_path / "prices.json"
    pricing.write_text(json.dumps(PRICING), encoding="utf-8")
    return root, pricing


def test_five_run_report_numbers(synthetic_runs) -> None:
    root, pricing = synthetic_runs
    report = research_cost.aggregate_research_cost(
        root, pricing_path=pricing, judge_model="test-judge"
    )
    counts = report["counts"]
    assert counts["runs_scanned"] == 8
    assert counts["runs_measured"] == 5
    assert counts["judge_unrecorded_runs"] == 2
    assert counts["judge_recorded_runs"] == 3
    assert counts["judge_estimated_runs"] == 1
    assert counts["runs_not_completed"] == 1
    assert counts["runs_no_episode"] == 1
    assert counts["writer_unrecorded_runs"] == 1
    assert report["estimated_share"] == pytest.approx(1 / 3, abs=1e-4)

    tokens = report["tokens"]
    # 写手 input [20k,30k,40k,50k,60k]：中位 40k、均值 40k、p90 线性插值 56k
    assert tokens["writer"]["input"] == {"n": 5, "median": 40_000, "mean": 40_000, "p90": 56_000}
    assert tokens["writer"]["output"] == {"n": 5, "median": 1_500, "mean": 1_600, "p90": 2_600}
    # 判官只含 3 个有记账 run：input [1k,20k,40k] → 20k / 20333.33 / 36k
    assert tokens["judge"]["input"] == {"n": 3, "median": 20_000, "mean": 20_333.33, "p90": 36_000}
    assert tokens["judge"]["output"] == {"n": 3, "median": 1_000, "mean": 1_033.33, "p90": 1_800}
    assert tokens["judge"]["calls"]["mean"] == pytest.approx(4 / 3, abs=0.01)
    # 合计只含判官有记账的 3 个：input [51k,60k,70k]、output [2000,2100,3500]
    assert tokens["total"]["input"] == {"n": 3, "median": 60_000, "mean": 60_333.33, "p90": 68_000}
    assert tokens["total"]["output"] == {"n": 3, "median": 2_100, "mean": 2_533.33, "p90": 3_220}

    cost = report["cost_cny_per_run"]
    # 写手 glm-5.2（8/28）：[0.174, 0.282, 0.348, 0.456, 0.564]
    assert cost["writer"] == {"n": 5, "median": 0.348, "mean": 0.3648, "p90": 0.5208}
    # 判官 test-judge（10/50）：[0.015, 0.25, 0.5]
    assert cost["judge"] == {"n": 3, "median": 0.25, "mean": 0.255, "p90": 0.45}
    # 合计：[0.471, 0.598, 0.782]
    assert cost["total"] == {"n": 3, "median": 0.598, "mean": 0.617, "p90": 0.7452}
    assert cost["contains_estimated"] is True
    assert report["unpriced_models"] == {}

    rows = {run["run_id"]: run for run in report["runs"]}
    assert rows["run_20260904_100000_d"]["judge_recorded"] is False
    assert rows["run_20260904_100000_d"]["total_cost_cny"] is None
    assert rows["run_20260903_100000_c"]["judge_usage_source"] == "estimated"
    assert rows["run_20260901_100000_a"]["total_cost_cny"] == 0.598


def test_markdown_has_conditions_block_and_estimated_marker(synthetic_runs, tmp_path) -> None:
    root, pricing = synthetic_runs
    report = research_cost.aggregate_research_cost(
        root, pricing_path=pricing, judge_model="test-judge"
    )
    paths = research_cost.write_research_cost_report(report, tmp_path / "out", stem="rc-test")
    md = paths["md"].read_text(encoding="utf-8")
    head = md.split("## 每次研究 token")[0]
    assert "## 成立条件" in head
    assert "checked_at = 2026-09-04, 2026-09-05" in head
    assert "完成且有写手 usage（进统计） 5" in head
    assert "判官未记账（旧格式）2" in head
    assert "2026-09-01T10:00:00+08:00 → 2026-09-05T10:00:00+08:00" in head
    assert "估算记录占比" in head and "33.3%" in head
    assert "树 / 解释器 / revision" in head
    assert "**（含估算）**" in md, "估算占比 > 0 时成本列必须标「含估算」"
    assert "判官侧为估算" in md
    assert "| 写手 | 5 | 40,000 / 40,000 / 56,000 | 1,500 / 1,600 / 2,600 |" in md
    assert "| 合计 | 3 | 0.5980 / 0.6170 / 0.7452 |" in md
    loaded = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert loaded["counts"]["judge_unrecorded_runs"] == 2


def test_no_estimate_means_no_marker(tmp_path) -> None:
    root = tmp_path / "runs"
    root.mkdir()
    _write_run(root, "run_20260901_100000_a", created_at="2026-09-01T10:00:00+08:00", judge=_judge(1, 20_000, 1_000, "cli"))
    pricing = tmp_path / "prices.json"
    pricing.write_text(json.dumps(PRICING), encoding="utf-8")
    report = research_cost.aggregate_research_cost(root, pricing_path=pricing, judge_model="test-judge")
    assert report["estimated_share"] == 0.0
    md = research_cost.render_research_cost_markdown(report)
    assert "含估算" not in md


def test_unpriced_judge_model_is_declared_not_guessed(synthetic_runs) -> None:
    root, pricing = synthetic_runs
    report = research_cost.aggregate_research_cost(
        root, pricing_path=pricing, judge_model="unpriced-judge"
    )
    assert report["cost_cny_per_run"]["judge"]["n"] == 0
    assert report["cost_cny_per_run"]["total"]["n"] == 0
    assert report["unpriced_models"] == {"unpriced-judge": 3}
    md = research_cost.render_research_cost_markdown(report)
    assert "| 判官 | 0 | 价目表未录（3 个 run 无法折算） |" in md
    assert "`unpriced-judge`：3 个 run" in md


def test_default_pricing_table_has_zhipu_rows_and_priced_rows_carry_sources() -> None:
    rows = research_cost.load_pricing()
    patterns = [row.model_pattern for row in rows]
    assert "glm-5.2*" in patterns and "glm-5.3*" in patterns and "glm-5" in patterns
    glm52 = research_cost.match_price("glm-5.2", rows)
    assert glm52 is not None and (glm52.input_cny_per_m, glm52.output_cny_per_m, glm52.cache_hit_cny_per_m) == (8.0, 28.0, 2.0)
    assert glm52.checked_at == "2026-09-04" and glm52.source_url == "https://bigmodel.cn/pricing"
    assert research_cost.match_price("GLM-5.3", rows) is not None, "忽略大小写"
    assert research_cost.match_price("gpt-5.6-terra", rows) is None
    for row in rows:
        if row.priced:
            assert row.checked_at and row.source_url, "有价的行必须带 checked_at 与来源"


def test_judge_default_resolves_to_cli_billed_row_not_api_list_price() -> None:
    """默认判官取价必须落在 CLI 实付那行。

    `grok-4.6*` 也能 fnmatch 上 `grok-4.6-build`——两行顺序反了就会静默按 API list 价算，
    判官侧读数直接放大 5.9 倍且报表看不出异常。这条钉的是顺序，不只是数值。
    """

    rows = research_cost.load_pricing()
    assert research_cost.DEFAULT_JUDGE_MODEL == "grok-4.6-build"
    build = research_cost.match_price(research_cost.DEFAULT_JUDGE_MODEL, rows)
    api = research_cost.match_price("grok-4.6", rows)
    assert build is not None and api is not None
    assert build.model_pattern == "grok-4.6-build*"
    assert api.model_pattern == "grok-4.6*"
    assert build.priced and api.priced
    # 两行同源同一天核对；build 档 = list × 0.17（由 CLI 自报 costUSD 反解，见价目表 note）。
    assert build.checked_at == api.checked_at == "2026-09-05"
    for got, want in (
        (build.input_cny_per_m, api.input_cny_per_m * 0.17),
        (build.output_cny_per_m, api.output_cny_per_m * 0.17),
        (build.cache_hit_cny_per_m, api.cache_hit_cny_per_m * 0.17),
    ):
        assert abs(got - want) < 1e-3, "build 档与 list 档必须保持 0.17 的换算关系，改一行必须改另一行"


def test_cli_selfreported_cost_reproduces_from_the_build_row() -> None:
    """价目表的 build 档要能复现 grok CLI 自己报的那次成本，否则这行是编的。

    探针 `~/.finance-runtime/judge-usage-probe-2026-09-05/raw.json`：
    19,326 input / 970 output / 128 cache_read → costUSD = 0.00757112。
    """

    rows = research_cost.load_pricing()
    fx = json.loads(research_cost.DEFAULT_PRICING_PATH.read_text(encoding="utf-8"))["fx"]["usd_cny"]
    build = research_cost.match_price("grok-4.6-build", rows)
    assert build is not None
    cny = (
        19_326 * build.input_cny_per_m + 970 * build.output_cny_per_m + 128 * build.cache_hit_cny_per_m
    ) / 1e6
    assert abs(cny / fx - 0.00757112) < 5e-7, "反解出的实付价必须与 CLI 自报 costUSD 对得上"


def _api_judge_root(tmp_path: Path, source: str) -> tuple[Path, Path]:
    root = tmp_path / "runs"
    root.mkdir()
    _write_run(
        root,
        "run_20260901_100000_a",
        created_at="2026-09-01T10:00:00+08:00",
        writer=(40_000, 1_000),
        judge=_judge(1, 20_000, 1_000, source),
    )
    pricing = tmp_path / "prices.json"
    pricing.write_text(json.dumps(PRICING), encoding="utf-8")
    return root, pricing


@pytest.mark.parametrize("source", ["api", "mixed"])
def test_judge_not_served_by_cli_is_left_unpriced_not_charged_at_the_cli_rate(
    tmp_path, source: str
) -> None:
    """备胎判官 / 主备混源的 run，判官成本必须留空而不是按 CLI 那档硬算。

    `judge_usage` 不落模型名，只有 `usage_source`。备胎判官的模型由
    `LLM_JUDGE_FALLBACK_MODEL` 决定（默认 gpt-4o-mini），与 grok 无关——按 `--judge-model`
    的 CLI 实付档给它定价，会得到一个既错又看不出错的数（CLI 档是 list 的 0.17）。
    """

    root, pricing = _api_judge_root(tmp_path, source)
    report = research_cost.aggregate_research_cost(
        root, pricing_path=pricing, judge_model="test-judge"
    )
    run = report["runs"][0]
    assert run["judge_usage_source"] == source
    assert run["judge_input_tokens"] == 20_000, "token 照记，不定价不等于不计量"
    assert run["judge_cost_cny"] is None
    assert run["total_cost_cny"] is None, "判官那截没价，合计不能只报写手那截"
    assert report["unpriced_models"] == {f"judge(usage_source={source})": 1}
    assert report["cost_cny_per_run"]["judge"]["n"] == 0
    # 写手侧不受影响
    assert run["writer_cost_cny"] == pytest.approx(0.348)


def test_api_sourced_judge_prices_from_judge_api_model_when_given(tmp_path) -> None:
    root, pricing = _api_judge_root(tmp_path, "api")
    report = research_cost.aggregate_research_cost(
        root, pricing_path=pricing, judge_model="test-judge", judge_api_model="glm-5.2"
    )
    run = report["runs"][0]
    assert run["judge_model"] == "glm-5.2", "备胎那条路要按备胎的模型取价"
    # 手算：20,000 × 8/1e6 + 1,000 × 28/1e6 = 0.16 + 0.028
    assert run["judge_cost_cny"] == pytest.approx(0.188)
    assert run["total_cost_cny"] == pytest.approx(0.536)
    assert report["unpriced_models"] == {}
    assert report["judge_api_model_assumed"] == "glm-5.2"


def test_judge_price_model_maps_source_to_row() -> None:
    """映射本身的真值表——estimated 估的是 token 数不是 SKU，仍走 CLI 那档。"""

    call = lambda src: research_cost.judge_price_model(  # noqa: E731
        src, judge_model="cli-row", judge_api_model="api-row"
    )
    assert call("cli") == "cli-row"
    assert call("estimated") == "cli-row"
    assert call("api") == "api-row"
    assert call("mixed") is None
    assert call(None) is None


def test_judge_no_call_run_counts_zero_judge_cost_in_total(tmp_path) -> None:
    root = tmp_path / "runs"
    root.mkdir()
    _write_run(root, "run_20260901_100000_a", created_at="2026-09-01T10:00:00+08:00", writer=(10_000, 1_000))
    pricing = tmp_path / "prices.json"
    pricing.write_text(json.dumps(PRICING), encoding="utf-8")
    report = research_cost.aggregate_research_cost(root, pricing_path=pricing, judge_model="test-judge")
    counts = report["counts"]
    assert counts["judge_recorded_runs"] == 1 and counts["judge_no_call_runs"] == 1
    assert report["tokens"]["judge"]["input"]["n"] == 0
    assert report["tokens"]["total"]["input"] == {"n": 1, "median": 10_000, "mean": 10_000, "p90": 10_000}
    # 10_000*8/1e6 + 1_000*28/1e6 = 0.108；判官未调用 → 合计 = 写手
    assert report["cost_cny_per_run"]["total"]["median"] == 0.108


def test_since_filters_by_created_at(synthetic_runs) -> None:
    root, pricing = synthetic_runs
    report = research_cost.aggregate_research_cost(
        root, since="2026-09-03T00:00:00+08:00", pricing_path=pricing, judge_model="test-judge"
    )
    assert report["counts"]["runs_before_since"] == 2
    assert report["counts"]["runs_measured"] == 3
    assert report["counts"]["judge_unrecorded_runs"] == 2


def test_writer_price_model_what_if_overrides_actual_model(tmp_path) -> None:
    root = tmp_path / "runs"
    root.mkdir()
    _write_run(root, "run_20260901_100000_a", created_at="2026-09-01T10:00:00+08:00", writer=(10_000, 1_000), model="gpt-5.6-terra", judge=_judge(1, 1_000, 100, "cli"))
    pricing = tmp_path / "prices.json"
    pricing.write_text(json.dumps(PRICING), encoding="utf-8")
    actual = research_cost.aggregate_research_cost(root, pricing_path=pricing, judge_model="test-judge")
    assert actual["cost_cny_per_run"]["writer"]["n"] == 0
    assert actual["unpriced_models"] == {"gpt-5.6-terra": 1}
    what_if = research_cost.aggregate_research_cost(
        root, pricing_path=pricing, judge_model="test-judge", writer_price_model="glm-5.2"
    )
    assert what_if["cost_cny_per_run"]["writer"]["median"] == 0.108
    assert what_if["runs"][0]["writer_model"] == "gpt-5.6-terra", "实际模型仍原样记录"
    assert "what-if" in research_cost.render_research_cost_markdown(what_if)


def test_cli_main_writes_dated_files(synthetic_runs, tmp_path, capsys) -> None:
    root, pricing = synthetic_runs
    out_dir = tmp_path / "measurements"
    code = research_cost.main(
        [
            "--runs-root",
            str(root),
            "--since",
            "all",
            "--out-dir",
            str(out_dir),
            "--pricing",
            str(pricing),
            "--judge-model",
            "test-judge",
            "--stem",
            "research-cost-2026-09-05",
        ]
    )
    assert code == 0
    assert (out_dir / "research-cost-2026-09-05.json").is_file()
    assert (out_dir / "research-cost-2026-09-05.md").is_file()
    printed = capsys.readouterr().out
    assert "research-cost-2026-09-05.json" in printed


@pytest.mark.parametrize(
    "values, q, expected",
    [
        ([1, 2, 3, 4, 5], 0.9, 4.6),
        ([10], 0.9, 10.0),
        ([1000, 20000, 40000], 0.9, 36000.0),
        ([], 0.9, None),
    ],
)
def test_percentile_linear_interpolation(values, q, expected) -> None:
    assert research_cost.percentile(values, q) == expected
