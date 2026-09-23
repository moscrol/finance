Candidate 1de68567e740a9a5d9c25bea91142741ad12aa10; base c9dd71dfd678855b61662100ec74625b92ad1f1b; source root /Users/a77/.finance-runtime/reviews/market-recovery-qc-20260923/suite-followup/candidate
Review FinanceQuery.run absolute query deadlines: setup and monitor scheduling must not renew the timeout; respect parent synthesis reserve; preserve cancellation vs timeout; reject late SQL/fetch/close success and clean up connections. Investigate regressions and uncovered deadline/cancellation edges. No claim of forcibly preempting connect/close or of hard real-time OS scheduling. Do not infer the root cause of historical wall-clock test failures.


SOURCE intelligence/services/finance_query.py sha256=1b5b3e529049f9e855b394591bed7749fa29b076027370a2ad8c8fe4958a4cd0

8: from __future__ import annotations
10: from collections.abc import Callable, Mapping, Sequence
11: from dataclasses import dataclass, replace
12: from datetime import date, datetime
13: import hashlib
14: import json
15: from pathlib import Path
16: import re
17: from threading import Event, Thread
18: import time
19: from typing import Any, Literal
21: from intelligence.services import agent_research
22: from intelligence.services.research_contract import (
23:     InformationCutoff,
24:     ResearchDeadline,
25: )
28: class FinanceQueryError(RuntimeError):
29:     """Base class for typed structured-query failures."""
32: class FinanceQueryValidationError(FinanceQueryError, ValueError):
33:     """The semantic query is outside the registered production surface."""
36: class FinanceQueryExecutionError(FinanceQueryError):
37:     """DuckDB could not execute an otherwise valid semantic query."""
40: class FinanceQueryLimitExceeded(FinanceQueryError):
41:     """The bounded result exceeded a hard output limit."""
44: class FinanceQueryCancelled(FinanceQueryError):
45:     """The caller cancelled before the result could be published."""
48: class FinanceQueryTimedOut(FinanceQueryError, TimeoutError):
49:     """The root or statement deadline interrupted execution."""
98: @dataclass(frozen=True)
99: class FinanceQuerySpec:
100:     dataset: str
101:     metrics: tuple[str, ...]
102:     dimensions: tuple[str, ...]
103:     filters: tuple[QueryFilter, ...] = ()
104:     time_range: TimeRange | None = None
105:     group_by: tuple[str, ...] = ()
106:     order_by: tuple[Order, ...] = ()
107:     limit: int = 50
108: 
109:     @classmethod
110:     def from_arguments(
111:         cls,
112:         arguments: Mapping[str, object],
113:     ) -> FinanceQuerySpec:
114:         unknown = set(arguments) - _TOP_LEVEL_KEYS
115:         if unknown:
116:             raise FinanceQueryValidationError(
117:                 "unknown query argument: " + ",".join(sorted(unknown))
118:             )
119:         dataset = _required_text(arguments.get("dataset"), "dataset")
120:         metrics = _string_tuple(arguments.get("metrics", ()), "metrics")
121:         dimensions = _string_tuple(
122:             arguments.get("dimensions", ()),
123:             "dimensions",
124:         )
125:         if not metrics and not dimensions:
126:             raise FinanceQueryValidationError(
127:                 "at least one metric or dimension is required"
128:             )
129:         filters = _parse_filters(arguments.get("filters", ()))
130:         time_range = _parse_time_range(arguments.get("time_range"))
131:         group_by = _string_tuple(arguments.get("group_by", ()), "group_by")
132:         order_by = _parse_orders(arguments.get("order_by", ()))
133:         raw_limit = arguments.get("limit", 50)
134:         if (
135:             isinstance(raw_limit, bool)
136:             or not isinstance(raw_limit, int)
137:             or raw_limit < 1
138:             or raw_limit > 1000
139:         ):
140:             raise FinanceQueryValidationError(
141:                 "limit must be an integer between 1 and 1000"
142:             )
143:         return cls(
144:             dataset=dataset,
145:             metrics=metrics,
146:             dimensions=dimensions,
147:             filters=filters,
148:             time_range=time_range,
149:             group_by=group_by,
150:             order_by=order_by,
151:             limit=raw_limit,
152:         )
155: @dataclass(frozen=True)
156: class FinanceQueryLimits:
157:     max_rows: int = 200
158:     max_bytes: int = 256_000
159:     timeout: float = 8.0
160: 
161:     def __post_init__(self) -> None:
162:         if self.max_rows < 1 or self.max_bytes < 1 or self.timeout <= 0:
163:             raise ValueError("finance query limits must be positive")
166: @dataclass(frozen=True)
167: class FinanceQueryAudit:
168:     dataset: str
169:     physical_sql: str
170:     bound_parameters: tuple[object, ...]
171:     sql_fingerprint: str
172:     applied_limit: int
173:     row_count: int
174:     output_bytes: int
175:     elapsed_seconds: float
176:     requested_time_range: tuple[str | None, str | None] | None = None
257: @dataclass(frozen=True)
258: class FinanceQueryResult:
259:     rows: tuple[dict[str, object], ...]
260:     evidence: tuple[agent_research.AgentEvidence, ...]
261:     observation: str
262:     served_date: str | None
263:     audit: FinanceQueryAudit
2175: class FinanceQuery:
2176:     """Compile and execute one model-owned semantic query under code-owned caps."""
2177: 
2178:     def __init__(
2179:         self,
2180:         db_path: str | Path,
2181:         *,
2182:         limits: FinanceQueryLimits | None = None,
2183:         connect: DuckDbConnect | None = None,
2184:     ) -> None:
2185:         self._db_path = Path(db_path).expanduser()
2186:         self._limits = limits or FinanceQueryLimits()
2187:         self._connect = connect or _duckdb_connect
2188: 
2189:     def run(
2190:         self,
2191:         spec: FinanceQuerySpec,
2192:         *,
2193:         information_cutoff: InformationCutoff,
2194:         deadline: ResearchDeadline,
2195:         is_cancelled: Callable[[], bool] | None = None,
2196:     ) -> FinanceQueryResult:
2197:         cancelled = is_cancelled or (lambda: False)
2198:         if cancelled():
2199:             raise FinanceQueryCancelled("finance query cancelled")
2200:         # 幂等：调用方（episode_tools）通常已归一化过，这里再调一次是 no-op。
2201:         # 保留这一步是因为本引擎也服务非 Episode 调用方，不能假设上游做过。
2202:         spec, _notes = normalize_spec(spec)
2203:         compiled = _compile_query(
2204:             spec,
2205:             information_cutoff=information_cutoff,
2206:             max_rows=self._limits.max_rows,
2207:         )
2208:         # Fix the absolute grant before connection setup or monitor scheduling.
2209:         query_deadline = deadline.bounded_stage(self._limits.timeout)
2210:         if query_deadline.remaining() <= 0.001:
2211:             raise FinanceQueryTimedOut("finance query deadline exhausted")
2212:         started = time.monotonic()
2213:         connection: Any | None = None
2214:         stop_monitor = Event()
2215:         interrupted_for: list[str] = []
2216:         try:
2217:             if cancelled():
2218:                 raise FinanceQueryCancelled("finance query cancelled")
2219:             connection = self._connect(str(self._db_path), read_only=True)
2220:             if cancelled():
2221:                 raise FinanceQueryCancelled("finance query cancelled")
2222:             if query_deadline.expired:
2223:                 raise FinanceQueryTimedOut("finance query deadline exhausted")
2224: 
2225:             def monitor() -> None:
2226:                 while not stop_monitor.is_set():
2227:                     if cancelled():
2228:                         interrupted_for.append("cancelled")
2229:                         connection.interrupt()
2230:                         return
2231:                     if query_deadline.expired:
2232:                         interrupted_for.append("timeout")
2233:                         connection.interrupt()
2234:                         return
2235:                     stop_monitor.wait(min(0.01, query_deadline.remaining()))
2236: 
2237:             monitor_thread = Thread(
2238:                 target=monitor,
2239:                 name="finance-query-deadline",
2240:                 daemon=True,
2241:             )
2242:             monitor_thread.start()
2243:             try:
2244:                 if cancelled():
2245:                     raise FinanceQueryCancelled("finance query cancelled")
2246:                 if query_deadline.expired:
2247:                     raise FinanceQueryTimedOut("finance query deadline exhausted")
2248:                 cursor = connection.execute(
2249:                     compiled.sql,
2250:                     list(compiled.parameters),
2251:                 )
2252:                 rows, source_dates, sector_universes, output_bytes = self._fetch_rows(
2253:                     cursor,
2254:                     compiled,
2255:                     cancelled=cancelled,
2256:                 )
2257:                 if compiled.reverse_after_fetch:
2258:                     rows = tuple(reversed(rows))
2259:                     source_dates = tuple(reversed(source_dates))
2260:                     sector_universes = tuple(reversed(sector_universes))
2261:             except Exception as exc:
2262:                 if interrupted_for:
2263:                     if interrupted_for[0] == "cancelled":
2264:                         raise FinanceQueryCancelled("finance query cancelled") from exc
2265:                     raise FinanceQueryTimedOut(
2266:                         "finance query statement timeout"
2267:                     ) from exc
2268:                 if isinstance(exc, FinanceQueryError):
2269:                     raise
2270:                 raise FinanceQueryExecutionError(
2271:                     f"finance query execution failed: {type(exc).__name__}"
2272:                 ) from exc
2273:             finally:
2274:                 stop_monitor.set()
2275:                 monitor_thread.join(timeout=0.2)
2276:             if interrupted_for:
2277:                 if interrupted_for[0] == "cancelled":
2278:                     raise FinanceQueryCancelled("finance query cancelled")
2279:                 raise FinanceQueryTimedOut("finance query statement timeout")
2280:             if cancelled():
2281:                 raise FinanceQueryCancelled("finance query cancelled")
2282:         finally:
2283:             stop_monitor.set()
2284:             if connection is not None:
2285:                 connection.close()
2286: 
2287:         if query_deadline.expired:
2288:             raise FinanceQueryTimedOut("finance query statement timeout")
2289:         elapsed = time.monotonic() - started
2290:         fingerprint = hashlib.sha256(compiled.sql.encode("utf-8")).hexdigest()[:16]
2291:         dataset = _DATASETS[spec.dataset]
2292:         evidence = _rows_to_evidence(
2293:             rows,
2294:             source_dates=source_dates,
2295:             dataset_name=spec.dataset,
2296:             dataset=dataset,
2297:             fingerprint=fingerprint,
2298:             sector_universes=sector_universes,
2299:         )
2300:         dates = tuple(item.source_date for item in evidence if item.source_date)
2301:         observation = "；".join(item.detail for item in evidence)
2302:         if not observation:
2303:             observation = f"{dataset.label}：结构化查询无结果"
2304:         audit = FinanceQueryAudit(
2305:             dataset=spec.dataset,
2306:             physical_sql=compiled.sql,
2307:             bound_parameters=compiled.parameters,
2308:             sql_fingerprint=fingerprint,
2309:             applied_limit=compiled.applied_limit,
2310:             row_count=len(rows),
2311:             output_bytes=output_bytes,
2312:             elapsed_seconds=round(elapsed, 6),
2313:             requested_time_range=_requested_time_range(spec),
2314:         )
2315:         return FinanceQueryResult(
2316:             rows=rows,
2317:             evidence=evidence,
2318:             observation=observation,
2319:             served_date=max(dates) if dates else None,
2320:             audit=audit,
2321:         )
2322: 
2323:     def dataset_max_date(
2324:         self,
2325:         spec: FinanceQuerySpec,
2326:         *,
2327:         information_cutoff: InformationCutoff,
2328:         deadline: ResearchDeadline,
2329:         is_cancelled: Callable[[], bool] | None = None,
2330:     ) -> str | None:
2331:         """同一时间窗口内、**去掉 filters** 之后该数据集的最新日期。
2332: 
2333:         用途只有一个：把「该主体退出了集合」与「整条管道陈旧」分开。
2334: 
2335:         `FinanceQueryResult.served_date` 取的是**被筛结果**的 max。筛子集停在更早
2336:         有两种截然不同的成因：
2337: 
2338:         - `fact_mainline_sector_daily` 整体有到 2026-08-14 的行，而「AI算力」最后
2339:           一天是 08-07 → **该题材掉出了主线**。这是行业生命周期观察，是答案本身，
2340:           不该当过期数据丢弃（2026-08-17 用户口径）。
2341:         - 数据集整体也停在 08-07 → 同步管道真的落后了，仍须拒绝。
2342: 
2343:         两者在 `served_date` 上完全同码，只有再读一次「不加 filter 的 max」才能分开。
2344: 
2345:         **只在即将判 stale 时调用**：happy path 一次额外查询都不发。探针本身
2346:         `limit=1` 且按时间倒序，成本是一行。
2347:         """
2348: 
2349:         dataset = _DATASETS.get(spec.dataset)
2350:         if dataset is None or not dataset.time_field:
2351:             return None
2352:         # spec 里的维度名未必等于物理列名（如 sector_code → sector_ts_code），
2353:         # 也可能是语义别名（as_of → source_date）。优先认 time_field 本身。
2354:         time_dimension = _semantic_time_dimension(dataset)
2355:         if time_dimension is None:
2356:             return None
2357:         probe = replace(
2358:             spec,
2359:             filters=(),
2360:             dimensions=(time_dimension,),
2361:             metrics=(),
2362:             group_by=(),
2363:             order_by=(Order(field=time_dimension, direction="desc"),),
2364:             limit=1,
2365:         )
2366:         try:
2367:             result = self.run(
2368:                 probe,
2369:                 information_cutoff=information_cutoff,
2370:                 deadline=deadline,
2371:                 is_cancelled=is_cancelled,
2372:             )
2373:         except FinanceQueryError:
2374:             # 探针失败不改变原判定——调用方按原来的 stale 处理。
2375:             # 这里吞异常是刻意的：探针是为了**放宽**误判，它自己坏掉时
2376:             # 必须落回更严的那一侧，不能把 stale 洗成通过。
2377:             return None
2378:         return result.served_date
2379: 
2380:     def _fetch_rows(
2381:         self,
2382:         cursor: Any,
2383:         compiled: _CompiledQuery,
2384:         *,
2385:         cancelled: Callable[[], bool],
2386:     ) -> tuple[tuple[dict[str, object], ...], tuple[str | None, ...], tuple[str, ...], int]:
2387:         rows: list[dict[str, object]] = []
2388:         sector_universes: list[str] = []
2389:         output_bytes = 0
2390:         while len(rows) < compiled.applied_limit:
2391:             if cancelled():
2392:                 raise FinanceQueryCancelled("finance query cancelled")
2393:             batch = cursor.fetchmany(min(64, compiled.applied_limit - len(rows)))
2394:             if not batch:
2395:                 break
2396:             for raw_row in batch:
2397:                 public = {
2398:                     field: _json_value(raw_row[index])
2399:                     for index, field in enumerate(compiled.output_fields)
2400:                 }
2401:                 source_date = _date_text(raw_row[compiled.source_date_index])
2402:                 public["__source_date"] = source_date
2403:                 universe = (
2404:                     str(raw_row[compiled.sector_universe_index] or "未知")
2405:                     if compiled.sector_universe_index is not None else ""
2406:                 )
2407:                 sector_universes.append(universe)
2408:                 public["__sector_universe"] = universe
2409:                 encoded = json.dumps(
2410:                     public,
2411:                     ensure_ascii=False,
2412:                     sort_keys=True,
2413:                     default=str,
2414:                 ).encode("utf-8")
2415:                 output_bytes += len(encoded)
2416:                 if output_bytes > self._limits.max_bytes:
2417:                     raise FinanceQueryLimitExceeded("finance query byte limit exceeded")
2418:                 rows.append(public)
2419:         visible_rows = tuple(
2420:             {key: value for key, value in row.items() if key not in {"__source_date", "__sector_universe"}}
2421:             for row in rows
2422:         )
2423:         source_dates = tuple(_date_text(row.get("__source_date")) for row in rows)
2424:         return visible_rows, source_dates, tuple(sector_universes), output_bytes
2748: def _rows_to_evidence(
2749:     rows: tuple[dict[str, object], ...],
2750:     *,
2751:     source_dates: tuple[str | None, ...],
2752:     dataset_name: str,
2753:     dataset: _DatasetDefinition,
2754:     fingerprint: str,
2755:     sector_universes: tuple[str, ...] = (),
2756: ) -> tuple[agent_research.AgentEvidence, ...]:
2757:     evidence: list[agent_research.AgentEvidence] = []
2758:     fields = dataset.fields
2759:     observations = _row_observations(
2760:         rows,
2761:         source_dates=source_dates,
2762:         dataset_name=dataset_name,
2763:         dataset=dataset,
2764:     )
2765:     for index, row in enumerate(rows, start=1):
2766:         source_date = source_dates[index - 1]
2767:         detail = "；".join(
2768:             f"{fields[name].label}={_display_value(value, fields[name])}"
2769:             for name, value in row.items()
2770:         )
2771:         if sector_universes and sector_universes[index - 1]:
2772:             detail += f"；板块分类口径={sector_universes[index - 1]}"
2773:         title = dataset.label + (f"（{source_date}）" if source_date else "")
2774:         item = agent_research.AgentEvidence(
2775:             tool="finance_query",
2776:             title=title,
2777:             detail=detail,
2778:             source=f"本地结构化数据 · {dataset.label}",
2779:             internal_locator=f"finance-query:{fingerprint}:{index}",
2780:             source_date=source_date,
2781:             evidence_tier=dataset.evidence_tier,
2782:             independent_key=f"duckdb:{dataset_name}:{source_date or 'undated'}",
2783:             freshness="current",
2784:             observations=observations[index - 1],
2785:         )
2786:         evidence.append(
2787:             replace(
2788:                 item,
2789:                 content_hash=agent_research.evidence_content_hash(item),
2790:             )
2791:         )
2792:     return tuple(evidence)

SOURCE intelligence/services/research_contract.py sha256=098a6dafbd3b6b266fbae274c3e9b1288a1487e3630958f02969123c240bdf26

1: from __future__ import annotations
3: from collections.abc import Mapping, Sequence
4: import hashlib
5: import json
6: import math
7: import os
8: import re
9: import time
10: from dataclasses import asdict, dataclass, field
11: from datetime import date
12: from threading import RLock
13: from typing import TYPE_CHECKING, Literal, Protocol, TypeAlias, cast
14: from weakref import WeakValueDictionary
16: from intelligence.services.query_resolution import (
17:     QueryResolution,
18:     classify_reference,
19: )
20: from intelligence.services.episode_effects import unknown_effects_from_payload
21: from intelligence.services.query_understanding import QueryEnvelope
22: from intelligence.services.route_table import owner_skills_from_route_table
23: from intelligence.services.evidence_capabilities import EvidencePlan, EvidenceRequirement
24: from intelligence.services.task_frame import TaskFrame
25: from intelligence.services.material_contract import MaterialContract
26: from intelligence.services.material_grounding import MaterialGrounding
27: from intelligence.services.premise_financial_calculation import PremiseCalculation
28: from intelligence.services.material_permissions import LOCAL_EVIDENCE_PRODUCERS, restrict_read_capabilities
29: from intelligence.services.historical_research.intent import HistoryIntent
30: from intelligence.services.user_task import (
31:     requests_previous_answer_review,
32:     top_level_message_text,
33: )
359: @dataclass(frozen=True)
360: class ResearchDeadline:
361:     expires_at: float
362:     # P0：为最终合成保留的硬预算（秒）。前置检索阶段的 stage_timeout 不得
363:     # 消费这段时间，避免检索耗尽预算后合成剩 0ms 只能降级为模板。
364:     synthesis_reserve: float = 0.0
365: 
366:     @classmethod
367:     def from_timeout(
368:         cls,
369:         timeout: float,
370:         *,
371:         synthesis_reserve: float = 0.0,
372:     ) -> ResearchDeadline:
373:         return cls(
374:             time.monotonic() + max(0.0, float(timeout)),
375:             synthesis_reserve=max(0.0, float(synthesis_reserve)),
376:         )
377: 
378:     def remaining(self) -> float:
379:         return max(0.0, self.expires_at - time.monotonic())
380: 
381:     def stage_timeout(self, configured_limit: float) -> float:
382:         available = max(0.0, self.remaining() - self.synthesis_reserve)
383:         return max(0.0, min(float(configured_limit), available))
384: 
385:     def synthesis_timeout(self, configured_limit: float) -> float:
386:         """合成阶段可用全部剩余时间（含保留段）。"""
387:         return max(0.0, min(float(configured_limit), self.remaining()))
388: 
389:     @property
390:     def expired(self) -> bool:
391:         return self.remaining() <= 0.0
392: 
393:     def bounded_stage(self, configured_limit: float) -> ResearchDeadline:
394:         """Intersect a child grant with this absolute research-stage window."""
395: 
396:         limit = max(0.0, float(configured_limit))
397:         return ResearchDeadline(
398:             expires_at=min(
399:                 self.expires_at - self.synthesis_reserve,
400:                 time.monotonic() + limit,
401:             )
402:         )
1241: @dataclass(frozen=True)
1242: class InformationCutoff:
1243:     as_of_date: date
1244:     source: InformationCutoffSource
1245: 
1246:     def __post_init__(self) -> None:
1247:         if type(self.as_of_date) is not date:
1248:             raise ValueError("information cutoff must use a date")
1249:         if self.source not in {
1250:             "requested",
1251:             "latest_available",
1252:             "runtime_default",
1253:         }:
1254:             raise ValueError("unsupported information cutoff source")
1255: 
1256:     @classmethod
1257:     def runtime_default(cls) -> InformationCutoff:
1258:         return cls(date.today(), "runtime_default")
1259: 
1260:     def to_dict(self) -> dict[str, str]:
1261:         return {
1262:             "as_of_date": self.as_of_date.isoformat(),
1263:             "source": self.source,
1264:         }

Public fixture guidance, not author tests: FinanceQuery accepts connect(path, read_only=True) and limits=FinanceQueryLimits(timeout=...). A fake connection may implement execute(sql, parameters)->cursor, cursor.fetchmany(count)->[], interrupt(), close(). FinanceQuerySpec.from_arguments({"dataset":"market_daily","metrics":["total_amount"],"dimensions":["trade_date"]}) is a valid empty-result query; use InformationCutoff(date(2026,7,24), "requested"). Import from intelligence.services.finance_query / research_contract. Use your own fixtures. If using a fake clock, replace module time bindings with a small object, not process-global time.monotonic. SQL compilation is real. No production database, network, or real model calls in probes. Distinguish dynamic verification from static observations and untested scheduling/IO boundaries. Do not import author tests.
