from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from intelligence.adapters import KnowledgeAdapter, MarketAdapter


@dataclass(frozen=True)
class ThemeRadarService:
    market_adapter: MarketAdapter | None = None
    knowledge_adapter: KnowledgeAdapter | None = None

    @property
    def market(self) -> MarketAdapter:
        return self.market_adapter or MarketAdapter()

    @property
    def knowledge(self) -> KnowledgeAdapter:
        return self.knowledge_adapter or KnowledgeAdapter()

    def build_market_triggered_candidates(self, date: str | None = None, top: int = 50) -> dict[str, Any]:
        market_daily = self.market.get_market_daily(date)
        capacity = self.market.get_capacity_sectors(date, top=3)
        double_red = self.market.get_double_red_themes(date, top=top)
        limit_heat = self.market.get_limit_heat_themes(date)
        advance = self.market.get_limit_advance_clusters(date)
        period_rank = self.market.get_period_rank_themes(date)
        new_high = self.market.get_new_high_directions(date)
        candidates_by_theme: dict[str, dict[str, Any]] = {}
        for row in double_red.get("themes", []):
            candidate = self._candidate_from_double_red(row, capacity.get("capacity_sectors", []))
            candidates_by_theme[str(candidate.get("market_theme") or "")] = candidate
        for row in limit_heat.get("themes", []):
            self._merge_limit_heat(candidates_by_theme, row)
        for row in advance.get("themes", []):
            self._merge_advance(candidates_by_theme, row)
        for row in period_rank.get("themes", []):
            self._merge_period_rank(candidates_by_theme, row)
        for row in new_high.get("themes", []):
            self._merge_new_high_direction(candidates_by_theme, row)
        stock_signals = self.market.get_theme_stock_signals(date, list(candidates_by_theme.keys()))
        self._merge_stock_signals(candidates_by_theme, stock_signals.get("signals", {}))
        self._merge_capacity_triggers(candidates_by_theme, capacity.get("capacity_sectors", []))
        candidates = [self._finalize_candidate(candidate) for candidate in candidates_by_theme.values()]
        candidates = sorted(candidates, key=lambda row: (-row["priority_score"], row["market_theme"]))[:top]
        candidates = [self._with_knowledge_status(candidate) for candidate in candidates]
        candidates = sorted(candidates, key=lambda row: (-row["priority_score"], row["market_theme"]))
        tiers = self._candidate_tiers(candidates)
        warnings = []
        warnings.extend(market_daily.get("warnings", []))
        warnings.extend(capacity.get("warnings", []))
        warnings.extend(double_red.get("warnings", []))
        warnings.extend(limit_heat.get("warnings", []))
        warnings.extend(advance.get("warnings", []))
        warnings.extend(period_rank.get("warnings", []))
        warnings.extend(new_high.get("warnings", []))
        warnings.extend(stock_signals.get("warnings", []))
        errors = []
        errors.extend(market_daily.get("errors", []))
        errors.extend(capacity.get("errors", []))
        errors.extend(double_red.get("errors", []))
        errors.extend(limit_heat.get("errors", []))
        errors.extend(advance.get("errors", []))
        errors.extend(period_rank.get("errors", []))
        errors.extend(new_high.get("errors", []))
        errors.extend(stock_signals.get("errors", []))
        return {
            "found": bool(candidates),
            "trade_date": self._resolve_trade_date(market_daily, capacity, double_red, limit_heat, advance, period_rank, new_high),
            "source": "market-triggered",
            "market_context": {
                "market_stage": market_daily.get("data", {}).get("market_stage") if market_daily.get("data") else None,
                "total_amount": market_daily.get("data", {}).get("total_amount") if market_daily.get("data") else None,
                "advancers": market_daily.get("data", {}).get("advancers") if market_daily.get("data") else None,
                "limit_up": market_daily.get("data", {}).get("limit_up") if market_daily.get("data") else None,
                "limit_down": market_daily.get("data", {}).get("limit_down") if market_daily.get("data") else None,
                "top3_industry_ratio": capacity.get("top3_industry_ratio"),
                "capacity_sectors": capacity.get("capacity_sectors", []),
            },
            "signal_summary": {
                "double_red_count": double_red.get("count", 0),
                "limit_heat_count": limit_heat.get("count", 0),
                "limit_advance_theme_count": advance.get("count", 0),
                "multi_period_row_count": period_rank.get("count", 0),
                "new_high_direction_count": new_high.get("count", 0),
                "candidate_theme_count": len(candidates_by_theme),
            },
            "candidate_count": len(candidates),
            "tier_summary": {
                "deep_count": len(tiers["deep_candidates"]),
                "watch_count": len(tiers["watch_candidates"]),
                "long_tail_count": len(tiers["long_tail_candidates"]),
            },
            "deep_candidates": tiers["deep_candidates"],
            "watch_candidates": tiers["watch_candidates"],
            "long_tail_candidates": tiers["long_tail_candidates"],
            "candidates": candidates,
            "warnings": warnings if warnings else ([] if candidates else ["market triggered candidates not found"]),
            "errors": errors,
        }

    @staticmethod
    def _candidate_from_double_red(row: dict[str, Any], capacity_sectors: list[dict[str, Any]]) -> dict[str, Any]:
        in_capacity = bool(row.get("in_capacity_top3"))
        capacity_match = next((item for item in capacity_sectors if item.get("name") == row.get("sw_l1")), None)
        candidate = ThemeRadarService._empty_candidate(row.get("sector_name"), row.get("sector_name"), row.get("sw_l1") or "")
        ThemeRadarService._add_score(
            candidate,
            "double_red",
            90,
            f"涨幅{row.get('pct_chg')}%，边际量{row.get('diff_ratio')}%，成交{row.get('amount')}亿",
            "MarketAdapter.get_double_red_themes",
        )
        if in_capacity:
            ThemeRadarService._add_score(
                candidate,
                "capacity_industry",
                10,
                f"所属申万一级 {row.get('sw_l1')} 位于容量前三",
                "MarketAdapter.get_capacity_sectors",
            )
        candidate["market_evidence"]["sector_metrics"] = {
            "sector_ts_code": row.get("sector_ts_code"),
            "pct_chg": row.get("pct_chg"),
            "diff_ratio": row.get("diff_ratio"),
            "amount": row.get("amount"),
            "in_capacity_top3": in_capacity,
        }
        candidate["market_evidence"]["capacity_sector"] = capacity_match or {}
        return candidate

    @staticmethod
    def _empty_candidate(theme: Any, canonical_concept: Any = None, sw_l1: str = "") -> dict[str, Any]:
        return {
            "market_theme": theme,
            "canonical_concept": canonical_concept or theme,
            "sw_l1": sw_l1 or "",
            "priority_score": 0,
            "score_detail": [],
            "trigger_types": [],
            "signal_sources": [],
            "market_evidence": {
                "sector_metrics": {},
                "capacity_sector": {},
                "limit_heat": {},
                "advance": {},
                "advance_stocks": [],
                "period_ranks": [],
                "new_high_direction": {},
                "strong_stocks": [],
                "new_high_stocks": [],
            },
            "knowledge_status": {
                "local_concept_found": None,
                "local_exposures_found": None,
                "local_evidence_found": None,
                "evidence_count": 0,
                "external_supplement_needed": None,
                "backfill_gaps": [],
            },
            "knowledge_evidence": [],
        }

    @staticmethod
    def _candidate(candidates_by_theme: dict[str, dict[str, Any]], theme: Any, sw_l1: str = "") -> dict[str, Any]:
        key = str(theme or "未命名题材")
        if key not in candidates_by_theme:
            candidates_by_theme[key] = ThemeRadarService._empty_candidate(key, key, sw_l1)
        candidate = candidates_by_theme[key]
        if sw_l1 and not candidate.get("sw_l1"):
            candidate["sw_l1"] = sw_l1
        return candidate

    @staticmethod
    def _add_score(candidate: dict[str, Any], signal: str, score: Any, reason: str, source: str) -> None:
        value = round(float(score or 0), 2)
        candidate["priority_score"] = round(float(candidate.get("priority_score") or 0) + value, 2)
        if signal not in candidate["trigger_types"]:
            candidate["trigger_types"].append(signal)
        if source not in candidate["signal_sources"]:
            candidate["signal_sources"].append(source)
        candidate.setdefault("score_detail", []).append({
            "signal": signal,
            "score": value,
            "reason": reason,
            "source": source,
        })

    @staticmethod
    def _merge_limit_heat(candidates_by_theme: dict[str, dict[str, Any]], row: dict[str, Any]) -> None:
        candidate = ThemeRadarService._candidate(candidates_by_theme, row.get("sector_name"))
        ThemeRadarService._add_score(
            candidate,
            "limit_heat",
            row.get("score"),
            f"涨停{row.get('limit_up_count')}只，市场占比{row.get('market_share')}，排名{row.get('rank')}",
            "MarketAdapter.get_limit_heat_themes",
        )
        candidate["market_evidence"]["limit_heat"] = {
            "limit_up_count": row.get("limit_up_count"),
            "total_count": row.get("total_count"),
            "market_share": row.get("market_share"),
            "fd_amount": row.get("fd_amount"),
            "rank": row.get("rank"),
        }

    @staticmethod
    def _merge_advance(candidates_by_theme: dict[str, dict[str, Any]], row: dict[str, Any]) -> None:
        candidate = ThemeRadarService._candidate(candidates_by_theme, row.get("theme") or "连板未映射", row.get("sw_l1") or "")
        ThemeRadarService._add_score(
            candidate,
            "limit_advance_cluster",
            row.get("score"),
            f"连板股{row.get('stock_count')}只，最高{row.get('max_boards')}板，容量前三={row.get('in_capacity_top3')}",
            "MarketAdapter.get_limit_advance_clusters",
        )
        candidate["market_evidence"]["advance"] = {
            "stock_count": row.get("stock_count"),
            "max_boards": row.get("max_boards"),
            "stock_names": row.get("stock_names"),
            "dominant_sw_l1": row.get("dominant_sw_l1"),
            "dominant_sw_l1_counts": row.get("dominant_sw_l1_counts", []),
            "in_capacity_top3": row.get("in_capacity_top3"),
        }
        candidate["market_evidence"]["advance_stocks"] = ThemeRadarService._merge_rows(
            candidate["market_evidence"].get("advance_stocks", []),
            row.get("advance_stocks", []),
            "stock_ts_code",
            10,
        )

    @staticmethod
    def _merge_period_rank(candidates_by_theme: dict[str, dict[str, Any]], row: dict[str, Any]) -> None:
        candidate = ThemeRadarService._candidate(candidates_by_theme, row.get("sector_name"))
        ThemeRadarService._add_score(
            candidate,
            "multi_period_rank",
            row.get("score"),
            f"{row.get('period_type')}排名第{row.get('rank')}，区间涨幅{row.get('change_pct')}%",
            "MarketAdapter.get_period_rank_themes",
        )
        candidate["market_evidence"]["period_ranks"] = ThemeRadarService._merge_rows(
            candidate["market_evidence"].get("period_ranks", []),
            [{
                "period_type": row.get("period_type"),
                "rank": row.get("rank"),
                "change_pct": row.get("change_pct"),
                "limit_up_count": row.get("limit_up_count"),
                "badge": row.get("badge"),
            }],
            "period_type",
            8,
        )

    @staticmethod
    def _merge_new_high_direction(candidates_by_theme: dict[str, dict[str, Any]], row: dict[str, Any]) -> None:
        candidate = ThemeRadarService._candidate(candidates_by_theme, row.get("sector_name"), row.get("sw_l1") or "")
        ThemeRadarService._add_score(
            candidate,
            "new_high_direction",
            row.get("score"),
            f"新高股{row.get('high_count')}只，新高成交{row.get('high_amount')}亿，容量前三={row.get('in_capacity_top3')}",
            "MarketAdapter.get_new_high_directions",
        )
        candidate["market_evidence"]["new_high_direction"] = {
            "high_count": row.get("high_count"),
            "high_amount": row.get("high_amount"),
            "in_capacity_top3": row.get("in_capacity_top3"),
        }

    @staticmethod
    def _merge_stock_signals(candidates_by_theme: dict[str, dict[str, Any]], signals: dict[str, dict[str, Any]]) -> None:
        for theme, signal in signals.items():
            if theme not in candidates_by_theme:
                continue
            candidate = candidates_by_theme[theme]
            candidate["market_evidence"]["strong_stocks"] = ThemeRadarService._merge_rows(
                candidate["market_evidence"].get("strong_stocks", []),
                signal.get("strong_stocks", []),
                "stock_ts_code",
                10,
            )
            candidate["market_evidence"]["new_high_stocks"] = ThemeRadarService._merge_rows(
                candidate["market_evidence"].get("new_high_stocks", []),
                signal.get("new_high_stocks", []),
                "stock_ts_code",
                10,
            )
            if signal.get("new_high_cluster_score"):
                ThemeRadarService._add_score(
                    candidate,
                    "new_high_cluster",
                    signal.get("new_high_cluster_score"),
                    f"题材内新高股{len(signal.get('new_high_stocks', []))}只",
                    "MarketAdapter.get_theme_stock_signals",
                )

    @staticmethod
    def _merge_capacity_triggers(candidates_by_theme: dict[str, dict[str, Any]], capacity_sectors: list[dict[str, Any]]) -> None:
        capacity_names = {item.get("name") for item in capacity_sectors}
        for candidate in candidates_by_theme.values():
            if candidate.get("sw_l1") in capacity_names and "capacity_industry" not in candidate["trigger_types"]:
                candidate["trigger_types"].append("capacity_industry")

    @staticmethod
    def _merge_rows(existing: list[dict[str, Any]], incoming: list[dict[str, Any]], key: str, limit: int) -> list[dict[str, Any]]:
        seen = {str(row.get(key) or row.get("stock_name") or row) for row in existing}
        out = list(existing)
        for row in incoming:
            marker = str(row.get(key) or row.get("stock_name") or row)
            if marker in seen:
                continue
            seen.add(marker)
            out.append(row)
            if len(out) >= limit:
                break
        return out

    @staticmethod
    def _finalize_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
        candidate["priority_score"] = round(float(candidate.get("priority_score") or 0), 2)
        candidate["score_detail"] = sorted(candidate.get("score_detail", []), key=lambda row: -float(row.get("score") or 0))
        return candidate

    @staticmethod
    def _candidate_tiers(candidates: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        for rank, candidate in enumerate(candidates, 1):
            candidate["rank"] = rank
            if rank <= 10:
                candidate["candidate_tier"] = "deep"
            elif rank <= 30:
                candidate["candidate_tier"] = "watch"
            else:
                candidate["candidate_tier"] = "long_tail"
        return {
            "deep_candidates": candidates[:10],
            "watch_candidates": candidates[10:30],
            "long_tail_candidates": candidates[30:],
        }

    def _with_knowledge_status(self, candidate: dict[str, Any]) -> dict[str, Any]:
        target = str(candidate.get("market_theme") or candidate.get("canonical_concept") or "")
        evidence = self.knowledge.get_evidence(target, limit=5)
        concept_matches = self._collect_matches("concept", [target, str(candidate.get("canonical_concept") or "")], 5)
        exposure_terms = [
            target,
            str(candidate.get("canonical_concept") or ""),
            *[row.get("concept", "") for row in concept_matches if int(row.get("score") or 0) >= 5],
        ]
        exposure_matches = self._collect_matches("exposure", exposure_terms, 12)
        items = evidence.get("items", [])
        evidence_found = bool(evidence.get("found"))
        concept_found = bool(concept_matches)
        exposures_found = bool(exposure_matches)
        status = dict(candidate.get("knowledge_status", {}))
        gaps = list(status.get("backfill_gaps", []))
        if not concept_found and "missing_concept" not in gaps:
            gaps.append("missing_concept")
        if not exposures_found and "missing_entity_exposures" not in gaps:
            gaps.append("missing_entity_exposures")
        if not evidence_found and "missing_evidence" not in gaps:
            gaps.append("missing_evidence")
        if concept_matches:
            candidate["canonical_concept"] = concept_matches[0]["concept"]
        status.update(
            {
                "local_concept_found": concept_found,
                "local_exposures_found": exposures_found,
                "local_evidence_found": evidence_found,
                "evidence_count": len(items),
                "concept_count": len(concept_matches),
                "exposure_count": len(exposure_matches),
                "external_supplement_needed": bool(gaps),
                "backfill_gaps": gaps,
            }
        )
        candidate["knowledge_status"] = status
        candidate["matched_concepts"] = concept_matches
        candidate["candidate_companies"] = exposure_matches
        candidate["knowledge_evidence"] = [self._evidence_ref(item) for item in items]
        return candidate

    def _collect_matches(self, match_type: str, terms: list[str], limit: int) -> list[dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {}
        for term in terms:
            if not term:
                continue
            if match_type == "concept":
                result = self.knowledge.get_concept_matches(term, limit=limit)
                key_field = "concept"
            else:
                result = self.knowledge.get_exposure_matches(term, limit=limit)
                key_field = "company"
            for item in result.get("items", []):
                key = str(item.get(key_field) or "")
                if not key:
                    continue
                if key not in merged or int(item.get("score") or 0) > int(merged[key].get("score") or 0):
                    merged[key] = item
        return sorted(merged.values(), key=lambda row: (-int(row.get("score") or 0), str(row.get("concept") or row.get("company") or "")))[:limit]

    @staticmethod
    def _evidence_ref(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": item.get("id"),
            "target": item.get("target"),
            "concept": item.get("concept") or item.get("theme") or item.get("term"),
            "evidence_layer": item.get("evidence_layer") or item.get("layer"),
            "source": item.get("source"),
            "quality": item.get("quality") or item.get("confidence"),
        }

    @staticmethod
    def _resolve_trade_date(*results: dict[str, Any]) -> str | None:
        for result in results:
            trade_date = result.get("trade_date")
            if trade_date:
                return str(trade_date)
        return None
