import { CalendarClock } from "lucide-react";
import type { ReactNode } from "react";
import type { MarketFreshness } from "../types";

export function StaleDataBanner({ freshness, viewingDate }: {
  freshness: MarketFreshness;
  viewingDate?: string | null;
}) {
  const { as_of: asOf, expected_trade_date: expected, lag_trading_days: lag, status } = freshness;
  const current = status === "current" && freshness.calendar_certain && asOf &&
    asOf === expected && lag === 0;
  const stale = status === "stale" && freshness.calendar_certain && asOf &&
    expected && lag !== null && lag > 0;
  const observation = viewingDate && viewingDate !== asOf ? (
    <div className="stale-data-banner historical" role="status" aria-label="观察日期">
      <CalendarClock aria-hidden="true" size={15} />
      <span>
        选择观察日 <b>{viewingDate}</b>；
        {current || stale || status === "unsettled"
          ? <>库内最新盘面日期 <b>{asOf}</b>。</>
          : "库内盘面日期尚待确认。"}
      </span>
    </div>
  ) : null;
  if (current) return observation;

  let message: ReactNode;
  if (!asOf || status === "missing") {
    message = <>尚未取得盘面数据日期，无法判断是否已更新{expected ? <>至 <b>{expected}</b></> : ""}。</>;
  } else if (status === "invalid") {
    message = <>盘面数据日期无效，无法判断是否已更新。请核对数据日期。</>;
  } else if (status === "future") {
    message = <>盘面数据日期 <b>{asOf}</b> 晚于今天，无法据此判断是否已更新。请核对数据日期。</>;
  } else if (status === "unsettled") {
    message = <>库内已有 <b>{asOf}</b> 的盘面记录；尚未到上海时间 15:30，暂不视为已确认的收盘数据。</>;
  } else if (stale) {
    const missing = freshness.missing_trade_dates;
    message = <>
      库内最新盘面数据截至 <b>{asOf}</b>，落后最近已收盘交易日 <b>{expected}</b> 共 <b>{lag}</b> 个交易日。
      {missing.length > 0 && <>
        待补日期：{missing.join("、")}{lag > missing.length ? `（仅列前 ${missing.length} 个）` : ""}。
      </>}
    </>;
  } else {
    message = <>
      库内盘面记录日期 <b>{asOf}</b>；
      {!freshness.calendar_certain ? "交易日历信息不完整，" : ""}暂时无法判断是否已更新至最近已收盘交易日。
    </>;
  }
  return <>
    {observation}
    <div className={`stale-data-banner${stale ? "" : " uncertain"}`} role={stale ? "alert" : "status"} aria-label="盘面数据日期">
      <CalendarClock aria-hidden="true" size={15} />
      <span>{message}</span>
    </div>
  </>;
}
