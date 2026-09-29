import { CalendarClock } from "lucide-react";
import type { MarketFreshness } from "../types";

/**
 * 看板级「数据落后」提示。
 *
 * 各数据源的「完整」只说明截至日那天齐不齐；这里回答另一件事：截至日离最近已收盘
 * 交易日差几个交易日。判据是后端交易所日历（不读库），日历判不了就明说判不了。
 */
export function StaleDataBanner({ freshness }: { freshness: MarketFreshness }) {
  const { as_of: asOf, expected_trade_date: expected, lag_trading_days: lag } = freshness;
  if (!asOf) return null;
  if (lag === null) {
    if (freshness.calendar_certain) return null;
    return (
      <div className="stale-data-banner uncertain" role="status">
        <CalendarClock aria-hidden="true" size={15} />
        <span>
          盘面数据截至 <b>{asOf}</b>；交易所日历未登记当前年份，无法判断是否已是最新交易日。
        </span>
      </div>
    );
  }
  if (lag <= 0) return null;
  const missing = freshness.missing_trade_dates;
  const listed = missing.map((day) => day.slice(5)).join("、");
  const more = lag > missing.length ? ` 等 ${lag} 天` : "";
  return (
    <div className="stale-data-banner" role="alert">
      <CalendarClock aria-hidden="true" size={15} />
      <span>
        盘面数据截至 <b>{asOf}</b>，落后最近已收盘交易日 <b>{expected}</b> 共{" "}
        <b>{lag}</b> 个交易日{listed ? `（缺 ${listed}${more}）` : ""}。本页结论均基于 {asOf}，
        不代表最新盘面。
      </span>
    </div>
  );
}
