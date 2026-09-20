export type Category = "financial" | "industry" | "event" | "strategy";
export type Mode = "demo" | "live";
export type Choice = "left" | "right" | "tie" | "both_bad";
export type Reason = "evidence" | "reasoning" | "numbers" | "risk" | "clarity";
export type Participant = { id: string; name: string; version: string; kind: "agent" | "model" | "demo" };
export type Bootstrap = {
  csrf: string; reviewer: string | null; categories: Record<Category, string>;
  summary: { live_cases: number; demo_cases: number; formal_votes: number; reviewers: number };
};
export type Assignment = {
  id: string; question: string; category: Category; as_of: string; mode: Mode;
  evidence: { title: string; content: string; source: string }[];
  answers: { side: "left" | "right"; content: string; participant?: Participant; duration_seconds?: number }[];
  vote: { choice: Choice; reasons: Reason[]; counted: boolean; created_at: string } | null;
  skipped: boolean; invalid_reason: string | null;
  receipt: { match_sha256: string; run_id: string | null } | null;
};
export type BoardRow = Participant & {
  key: string; wins: number; losses: number; ties: number; both_bad: number;
  decisive: number; win_rate: number | null; votes: number; reviewers: number; cases: number;
  status: "collecting" | "observed";
};
export type Board = {
  rows: BoardRow[]; pairs: { a: string; b: string; a_wins: number; b_wins: number; ties: number; both_bad: number }[];
  formal_votes: number; method: string; minimum: { decisive: number; reviewers: number; cases: number };
};
export type History = {
  votes: { id: string; question: string; category: Category; mode: Mode; choice: Choice; counted: boolean; created_at: string }[];
  questions: { id: string; question: string; category: Category; status: string; created: number }[];
};
export type Strategy = {
  id: string; title: string; participant: Participant; benchmark: string;
  starts_at: string; ends_at: string; registered_at: string; sha256: string;
  holdings_count: number; status: "scheduled" | "observing" | "awaiting_audit";
  net_return: number | null; excess_return: number | null;
};

let csrf = "";
export async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api/arena/${path}`, {
    method: body === undefined ? "GET" : "POST",
    credentials: "same-origin",
    headers: body === undefined ? {} : { "Content-Type": "application/json", "X-Arena-Csrf": csrf },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) {
    const message = typeof data.detail === "string" ? data.detail : "请求未通过检查，请核对输入后重试。";
    throw new Error(message);
  }
  return data;
}
export async function bootstrap(): Promise<Bootstrap> {
  const data = await api<Bootstrap>("bootstrap");
  csrf = data.csrf;
  return data;
}
