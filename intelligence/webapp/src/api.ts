import type {
  ArtifactDescriptor,
  Bootstrap,
  DailyReportProjection,
  Followup,
  Run,
  RunContext,
  StructuredReport,
  TraceStep,
} from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

function withUser(path: string, user?: string): string {
  if (!user) return path;
  const separator = path.includes("?") ? "&" : "?";
  return `${path}${separator}user=${encodeURIComponent(user)}`;
}

export function getBootstrap(user?: string): Promise<Bootstrap> {
  return request<Bootstrap>(withUser("/api/workbench/bootstrap", user));
}

export function getRun(runId: string, user?: string): Promise<Run> {
  return request<Run>(withUser(`/api/runs/${encodeURIComponent(runId)}`, user));
}

export function getTrace(runId: string, user?: string): Promise<TraceStep[]> {
  return request<TraceStep[]>(withUser(`/api/runs/${encodeURIComponent(runId)}/trace`, user));
}

export async function getFollowups(runId: string, user?: string): Promise<Followup[]> {
  const payload = await request<{ followups: Followup[] }>(
    withUser(`/api/runs/${encodeURIComponent(runId)}/followups`, user),
  );
  return payload.followups ?? [];
}

export function getRunContext(runId: string, user?: string): Promise<RunContext> {
  return request<RunContext>(withUser(`/api/runs/${encodeURIComponent(runId)}/context`, user));
}

export function getRunReport(
  runId: string,
  user?: string,
): Promise<StructuredReport | null> {
  return request<StructuredReport | null>(
    withUser(`/api/runs/${encodeURIComponent(runId)}/report`, user),
  );
}

export async function getRunArtifactText(
  runId: string,
  name: string,
  user?: string,
): Promise<string> {
  const response = await fetch(
    withUser(
      `/api/runs/${encodeURIComponent(runId)}/artifacts/${encodeURIComponent(name)}`,
      user,
    ),
  );
  if (!response.ok) throw new Error(await response.text());
  return response.text();
}

export function createRun(
  question: string,
  taskType: string,
  user?: string,
  parentRunId?: string | null,
): Promise<{ run_id: string; status: string }> {
  return request("/api/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      task_type: taskType,
      user: user || undefined,
      parent_run_id: parentRunId || undefined,
      compose: true,
    }),
  });
}

export function listArtifacts(
  filters: { category?: string; date?: string; status?: string; q?: string } = {},
  user?: string,
): Promise<ArtifactDescriptor[]> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value) params.set(key, value);
  });
  if (user) params.set("user", user);
  const query = params.toString();
  return request<ArtifactDescriptor[]>(`/api/artifacts${query ? `?${query}` : ""}`);
}

export function getArtifact(artifactId: string, user?: string): Promise<ArtifactDescriptor> {
  return request<ArtifactDescriptor>(
    withUser(`/api/artifacts/${encodeURIComponent(artifactId)}`, user),
  );
}

export function getArtifactProjection(
  artifactId: string,
  user?: string,
): Promise<DailyReportProjection> {
  return request<DailyReportProjection>(
    withUser(`/api/artifacts/${encodeURIComponent(artifactId)}/projection`, user),
  );
}

export async function getArtifactText(artifactId: string, user?: string): Promise<string> {
  const response = await fetch(
    withUser(`/api/artifacts/${encodeURIComponent(artifactId)}/content`, user),
  );
  if (!response.ok) throw new Error(await response.text());
  return response.text();
}

export function artifactContentUrl(artifactId: string, user?: string): string {
  return withUser(`/api/artifacts/${encodeURIComponent(artifactId)}/content`, user);
}

export function runEventsUrl(runId: string, user?: string): string {
  return withUser(`/api/runs/${encodeURIComponent(runId)}/events`, user);
}
