import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { CrossSectionRow, ScanResult } from "../../river/types";
import { ScanPanel } from "./ScanPanel";

const riverApi = vi.hoisted(() => ({ getScan: vi.fn() }));
vi.mock("../../river/api", () => riverApi);

function row(overrides: Partial<CrossSectionRow>): CrossSectionRow {
  return {
    entity_id: "BK0001",
    entity_name: "半导体",
    pct_chg: -1.2,
    diff_ratio: -10,
    amount: 1.2e10,
    strict_double_red: false,
    limit_up_count: 1,
    coverage_90d: 5,
    coverage_cumulative: 40,
    days_since_last_report: 3,
    fund_flow_1d: null,
    fund_caliber: "em-main-net",
    market_pctile: 0.2,
    opinion_pctile: 0.9,
    dislocation: 0.7,
    ...overrides,
  };
}

function scan(rows: CrossSectionRow[]): ScanResult {
  return { as_of: "2026-09-24", mode: "dislocation", count: rows.length, rows };
}

describe("ScanPanel", () => {
  beforeEach(() => riverApi.getScan.mockReset());

  it("hides the 资金 column when every row is empty and says why", async () => {
    riverApi.getScan.mockResolvedValue(
      scan([row({}), row({ entity_id: "BK0002", entity_name: "军工" })]),
    );
    render(<ScanPanel asOf="2026-09-24" tradingDays={["2026-09-24"]} onPickEntity={() => {}} />);

    expect(await screen.findByText(/资金列已隐藏/)).toHaveTextContent("em-main-net");
    expect(screen.queryByRole("button", { name: "资金" })).toBeNull();
    expect(screen.getByRole("columnheader", { name: /双红\s*0/ })).toBeVisible();
  });

  it("keeps the 资金 column when some rows have values", async () => {
    riverApi.getScan.mockResolvedValue(
      scan([
        row({ fund_flow_1d: 3.4, fund_caliber: "fupanhui-native", strict_double_red: true }),
        row({ entity_id: "BK0002", entity_name: "军工", fund_flow_1d: null }),
      ]),
    );
    render(<ScanPanel asOf="2026-09-01" tradingDays={["2026-09-01"]} onPickEntity={() => {}} />);

    expect(await screen.findByRole("button", { name: "资金" })).toBeVisible();
    expect(screen.queryByText(/资金列已隐藏/)).toBeNull();
    expect(screen.getByRole("columnheader", { name: /双红\s*1/ })).toBeVisible();
  });
});
