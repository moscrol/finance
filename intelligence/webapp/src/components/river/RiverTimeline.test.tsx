import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import type { Timeline } from "../../river/types";
import { RiverTimeline } from "./RiverTimeline";

const timeline = (known: number, pct: number | null, caliber: string): Timeline => ({
  entity: { id: "S1", name: "测试板块", codes_seen: ["S1"], alias_applied: false },
  start: "2026-08-05", end: "2026-08-05", trading_days: 1, judgment_source: { path: "fixture", exists: false },
  days: [{ date: "2026-08-05", market: null, theme: null, opinion: null, judgment: null,
    capital: { fund_flow_1d: caliber.startsWith("mixed:") ? null : 5, n_with_fund: 1, n_stocks: 2, fund_caliber: caliber },
    stock: { n_stocks: 2, n_with_pct: known, n_up: known ? Number((pct ?? 0) > 0) : null, n_down: known ? 0 : null,
      n_limit_like: known ? 0 : null, top_name: "测试股", top_pct: pct, amount_leader: "测试股" },
  }],
});

it("marks all-null stock prices missing and does not draw a balanced breadth bar", () => {
  const { container } = render(<RiverTimeline timeline={timeline(0, null, "em-main-net")} selected={null} onSelect={vi.fn()}/>);
  const stock = screen.getByRole("gridcell", { name: /个股.*涨跌幅缺失/ });
  expect(stock).toHaveClass("missing");
  expect(stock).not.toHaveAccessibleName(/涨 0/);
  expect(stock.querySelector(".river-cell-bar")).toBeNull();
  expect(container.querySelector(".river-row-stock .river-lane-label")).toHaveTextContent("0% 有数");
});

it("keeps a real zero distinct from missing while exposing partial price coverage", () => {
  render(<RiverTimeline timeline={timeline(1, 0, "em-main-net")} selected={null} onSelect={vi.fn()}/>);
  const stock = screen.getByRole("gridcell", { name: /涨 0 \/ 跌 0/ });
  expect(stock).not.toHaveClass("missing");
  expect(stock).toHaveAccessibleName(/涨跌幅覆盖 1\/2/);
});

it("shows the mixed capital caliber as a gap, and labels a single source accurately", () => {
  const { rerender } = render(<RiverTimeline timeline={timeline(1, 1, "mixed:em-main-net|fupanhui-native")} selected={null} onSelect={vi.fn()}/>);
  expect(screen.getByRole("gridcell", { name: /资金.*混合口径.*em-main-net.*fupanhui-native/ })).toHaveClass("missing");
  rerender(<RiverTimeline timeline={timeline(1, 1, "fupanhui-native")} selected={null} onSelect={vi.fn()}/>);
  const capital = screen.getByRole("gridcell", { name: /资金流合计 5.00/ });
  expect(capital).toHaveAccessibleName(/fupanhui-native/);
  expect(capital).toHaveAccessibleName(/1\/2/);
  expect(capital).not.toHaveAccessibleName(/主力净流入/);
});
