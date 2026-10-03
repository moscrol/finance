import type {
  CohortRequest,
  CohortResult,
  EntityHit,
  Kline,
  LimitUpCalendar,
  RangeResult,
  RiverMeta,
  RiverSlice,
  ScanResult,
  Timeline,
} from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    let detail = "";
    try {
      const body = (await response.json()) as { detail?: unknown };
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    } catch {
      detail = await response.text().catch(() => "");
    }
    throw new Error(detail || `${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

function qs(params: Record<string, string | number | boolean | null | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === null || value === undefined || value === "") continue;
    search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

export function getRiverMeta(days = 120): Promise<RiverMeta> {
  return request<RiverMeta>(`/api/river/meta${qs({ days })}`);
}

export function searchEntities(q: string, asOf?: string | null): Promise<{ as_of: string | null; items: EntityHit[] }> {
  return request(`/api/river/entities${qs({ q, as_of: asOf, limit: 20 })}`);
}

export function getTimeline(entity: string, start: string, end: string): Promise<Timeline> {
  return request<Timeline>(`/api/river/timeline${qs({ entity, start, end })}`);
}

export function getSlice(
  asOf: string,
  entity: string,
  options: { cutoff?: string | null; requireStrict?: boolean; allowHindsight?: boolean } = {},
): Promise<RiverSlice> {
  return request<RiverSlice>(
    `/api/river/slice${qs({
      as_of: asOf,
      entity,
      cutoff: options.cutoff,
      require_strict: options.requireStrict ? "true" : undefined,
      allow_hindsight: options.allowHindsight ? "true" : undefined,
    })}`,
  );
}

export function getScan(
  asOf: string,
  mode: "all" | "dislocation",
  options: { minCoverage90d?: number; maxMarketPctile?: number } = {},
): Promise<ScanResult> {
  return request<ScanResult>(
    `/api/river/scan${qs({
      as_of: asOf,
      mode,
      min_coverage_90d: options.minCoverage90d,
      max_market_pctile: options.maxMarketPctile,
    })}`,
  );
}

export function postCohort(body: CohortRequest): Promise<CohortResult> {
  return request<CohortResult>("/api/river/cohort", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function getRange(
  entity: string,
  start: string,
  end: string,
  options: { kind?: "stock" | "sector" | null; requireComplete?: boolean } = {},
): Promise<RangeResult> {
  return request<RangeResult>(
    `/api/river/range${qs({
      entity,
      start,
      end,
      kind: options.kind,
      require_complete: options.requireComplete ? "true" : undefined,
    })}`,
  );
}

export function getKline(start: string, end: string, entity?: string): Promise<Kline> {
  return request<Kline>(`/api/river/kline${qs({ start, end, entity })}`);
}

export function getLimitUpCalendar(days = 60, end?: string | null): Promise<LimitUpCalendar> {
  return request<LimitUpCalendar>(`/api/limitup/calendar${qs({ days, end })}`);
}
