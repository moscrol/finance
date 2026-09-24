import { webcrypto } from "node:crypto";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import { postResearchEvolutionEvents } from "../api";
import { ResearchActivityControl } from "./ResearchActivityControl";

vi.mock("../api", () => ({ postResearchEvolutionEvents: vi.fn() }));
const post = vi.mocked(postResearchEvolutionEvents);

beforeEach(() => {
  vi.stubGlobal("crypto", webcrypto);
  post.mockResolvedValue(undefined);
});
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); post.mockReset(); });

it("默认关闭，拒收同意不启动区间，也不影响其他研究控件", async () => {
  post.mockRejectedValueOnce(new Error("拒收同意"));
  render(<><ResearchActivityControl conversationId="a" user="default" /><button>继续研究</button></>);
  expect(post).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText("同意并开始本次计时"));
  await screen.findByRole("alert");
  expect(screen.getByRole("alert")).toHaveTextContent("拒收同意");
  expect(screen.getByText("继续研究")).toBeEnabled();
  expect(screen.queryByText("停止使用计时")).not.toBeInTheDocument();
  await waitFor(() => expect(post).toHaveBeenCalledTimes(2));
  expect(post.mock.calls[1][1][0].payload).toMatchObject({ action: "withdraw" });
});

it("先同意再计时，停止写撤回并移除监听，不跨会话写区间", async () => {
  const { unmount } = render(<ResearchActivityControl conversationId="a" user="default" />);
  fireEvent.click(screen.getByText("同意并开始本次计时"));
  await screen.findByText("停止使用计时");
  await new Promise((resolve) => setTimeout(resolve, 5));
  fireEvent.click(screen.getByText("停止使用计时"));
  await waitFor(() => expect(screen.getByText("同意并开始本次计时")).toBeEnabled());
  const types = post.mock.calls.flatMap((c) => c[1].map((e) => e.event_type));
  expect(types).toEqual(["consent_changed", "time_interval", "consent_changed"]);
  const closing = post.mock.calls[1][1];
  expect(closing[1].payload).toMatchObject({ action: "withdraw" });
  expect(Date.parse(String(closing[1].event_at))).toBeGreaterThan(Date.parse(String(closing[0].event_at)));
  const count = post.mock.calls.length;
  unmount();
  document.dispatchEvent(new Event("visibilitychange"));
  expect(post.mock.calls).toHaveLength(count);
  expect(post.mock.calls.every((c) => c[0] === "a")).toBe(true);
});

it("区间保存失败如实显示缺口，停止仍可用", async () => {
  render(<ResearchActivityControl conversationId="a" user="default" />);
  fireEvent.click(screen.getByText("同意并开始本次计时"));
  await screen.findByText("停止使用计时");
  post.mockRejectedValueOnce(new Error("离线"));
  await new Promise((resolve) => setTimeout(resolve, 5));
  await act(async () => { fireEvent.click(screen.getByText("停止使用计时")); });
  expect(await screen.findByRole("alert")).toHaveTextContent("离线");
  await waitFor(() => expect(screen.getByText("同意并开始本次计时")).toBeEnabled());
});

it("切会话期间晚到同意回包只补旧会话撤回，不重启旧钟", async () => {
  let accept: () => void = () => {};
  post.mockImplementationOnce(() => new Promise<void>((resolve) => { accept = resolve; }));
  const { rerender } = render(<ResearchActivityControl key="a" conversationId="a" user="default" />);
  fireEvent.click(screen.getByText("同意并开始本次计时"));
  await waitFor(() => expect(post).toHaveBeenCalledTimes(1));
  rerender(<ResearchActivityControl key="b" conversationId="b" user="default" />);
  await act(async () => { accept(); });
  await waitFor(() => expect(post).toHaveBeenCalledTimes(2));
  expect(post.mock.calls.every((call) => call[0] === "a")).toBe(true);
  expect(post.mock.calls[1][1][0].payload).toMatchObject({ action: "withdraw" });
  expect(screen.queryByText("停止使用计时")).not.toBeInTheDocument();
});

it("pagehide 立即发送末段与撤回，重复通知/bfcache 恢复不重开计时", async () => {
  render(<ResearchActivityControl conversationId="a" user="default" />);
  fireEvent.click(screen.getByText("同意并开始本次计时"));
  await screen.findByText("停止使用计时");
  await new Promise((resolve) => setTimeout(resolve, 5));
  await act(async () => { window.dispatchEvent(new Event("pagehide")); });
  const closing = post.mock.calls[1][1];
  expect(closing.map((event) => event.event_type)).toEqual(["time_interval", "consent_changed"]);
  await act(async () => {
    window.dispatchEvent(new Event("pagehide"));
    window.dispatchEvent(new Event("pageshow"));
  });
  expect(post).toHaveBeenCalledTimes(2);
  expect(screen.getByText("同意并开始本次计时")).toBeEnabled();
});
