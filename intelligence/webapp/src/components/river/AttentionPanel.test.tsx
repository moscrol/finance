import { act, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { AttentionPanel } from "./DailyRiverDashboard";

afterEach(() => vi.unstubAllGlobals());
const reply = (count: number) => ({ ok: true, json: async () => ({ collection_status: "connected", events: [], visible_observations: count, event_count: 0, gaps: [], truncated: false }) }) as Response;
it("an obsolete public-news request cannot overwrite the selected date", async () => {
  let release!: (response: Response) => void;
  vi.stubGlobal("fetch", vi.fn().mockImplementationOnce(() => new Promise<Response>(resolve => { release = resolve; })).mockResolvedValue(reply(2)));
  const { rerender } = render(<AttentionPanel date="2026-09-23" sector={null} onClear={() => {}}/>);
  rerender(<AttentionPanel date="2026-09-24" sector={null} onClear={() => {}}/>);
  expect(await screen.findByText("2 条当时可见记录")).toBeInTheDocument();
  await act(async () => { release(reply(99)); });
  expect(screen.queryByText("99 条当时可见记录")).not.toBeInTheDocument();
  expect(screen.getByText(/公开消息传播/)).toBeInTheDocument();
  expect(screen.getByText(/研报覆盖独立保留/)).toBeInTheDocument();
});
