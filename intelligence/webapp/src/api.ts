import type {
  ArtifactDescriptor,
  Bootstrap,
  ChatMessage,
  Conversation,
  ConfigureLLMRequest,
  CreateMessageRequest,
  CreateMessageResponse,
  DailyReportProjection,
  Followup,
  LLMConfig,
  ProductSkillDescription,
  Run,
  RunContext,
  StructuredReport,
  TraceStep,
  WorkbenchOverview,
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

export function getWorkbenchOverview(): Promise<WorkbenchOverview> {
  return request<WorkbenchOverview>("/api/workbench/overview");
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

export function createConversation(
  title = "新对话",
  user?: string,
): Promise<Conversation> {
  return request<Conversation>(withUser("/api/conversations", user), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, user: user || undefined }),
  });
}

export function listConversations(user?: string): Promise<Conversation[]> {
  return request<Conversation[]>(withUser("/api/conversations", user));
}

export function getConversation(
  conversationId: string,
  user?: string,
): Promise<Conversation> {
  return request<Conversation>(
    withUser(`/api/conversations/${encodeURIComponent(conversationId)}`, user),
  );
}

export function renameConversation(
  conversationId: string,
  title: string,
  user?: string,
): Promise<Conversation> {
  return request<Conversation>(
    withUser(`/api/conversations/${encodeURIComponent(conversationId)}`, user),
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, user: user || undefined }),
    },
  );
}

export function archiveConversation(
  conversationId: string,
  user?: string,
): Promise<Conversation> {
  return request<Conversation>(
    withUser(`/api/conversations/${encodeURIComponent(conversationId)}/archive`, user),
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user: user || undefined }),
    },
  );
}

export function getConversationMessages(
  conversationId: string,
  user?: string,
): Promise<ChatMessage[]> {
  return request<ChatMessage[]>(
    withUser(`/api/conversations/${encodeURIComponent(conversationId)}/messages`, user),
  );
}

export function createConversationMessage(
  conversationId: string,
  message: CreateMessageRequest,
): Promise<CreateMessageResponse> {
  return request<CreateMessageResponse>(
    withUser(
      `/api/conversations/${encodeURIComponent(conversationId)}/messages`,
      message.user,
    ),
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(message),
    },
  );
}

export function getSkills(user?: string): Promise<ProductSkillDescription[]> {
  return request<ProductSkillDescription[]>(withUser("/api/skills", user));
}

export function getLLMConfig(user?: string): Promise<LLMConfig> {
  return request<LLMConfig>(withUser("/api/llm/config", user));
}

export function configureLLM(config: ConfigureLLMRequest): Promise<LLMConfig> {
  return request<LLMConfig>("/api/llm/config", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
}

export function selectBuiltInLLM(user?: string): Promise<LLMConfig> {
  return request<LLMConfig>(withUser("/api/llm/config", user), {
    method: "DELETE",
  });
}

export function cancelRun(
  runId: string,
  user?: string,
): Promise<{ run_id: string; cancel_requested: true }> {
  return request(withUser(`/api/runs/${encodeURIComponent(runId)}/cancel`, user), {
    method: "POST",
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
