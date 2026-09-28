import {
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  RefreshCw,
  SlidersHorizontal,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { getBoardCalendar } from "../api";
import type { BoardCalendar, BoardCalendarDay } from "../types";

const WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"];
const DEFAULT_VISIBLE_STOCKS = 8;

function monthLabel(month: string): string {
  const [year, monthNumber] = month.split("-");
  return `${year} 年 ${Number(monthNumber)} 月`;
}

function shiftMonth(month: string, delta: number): string {
  const [yearText, monthText] = month.split("-");
  const index = Number(yearText) * 12 + Number(monthText) - 1 + delta;
  const year = Math.floor(index / 12);
  const monthNumber = (index % 12) + 1;
  return `${year}-${String(monthNumber).padStart(2, "0")}`;
}

function dayNumber(value: string): number {
  return Number(value.slice(-2));
}

function shortStockCode(value: string): string {
  return value.split(".", 1)[0] || value;
}

function weekdayOffset(month: string): number {
  const [year, monthNumber] = month.split("-").map(Number);
  // JS Sunday=0; the dashboard starts weeks on Monday.
  return (new Date(year, monthNumber - 1, 1).getDay() + 6) % 7;
}

function dayStatus(day: BoardCalendarDay, minBoards: number): string {
  if (day.calendar_status === "closed") return "休市";
  if (day.calendar_status === "future") return "待发生";
  if (day.calendar_status === "market_data_missing") {
    return "交易日 · 市场数据缺失";
  }
  if (day.calendar_status === "calendar_unknown") return "日历未知";
  if (day.data_status === "board_data_missing") return "交易日 · 连板数据缺失";
  return day.stock_count
    ? `交易日 · ${day.stock_count} 只 ≥${minBoards}板`
    : `交易日 · 无 ≥${minBoards}板`;
}

function statusClass(day: BoardCalendarDay): string {
  if (day.calendar_status === "trading") {
    return day.data_status === "available" ? "available" : "data-gap";
  }
  return day.calendar_status;
}

function BoardGroups({
  day,
  expanded,
  onToggle,
}: {
  day: BoardCalendarDay;
  expanded: boolean;
  onToggle: () => void;
}) {
  const groups = useMemo(() => {
    let remaining = DEFAULT_VISIBLE_STOCKS;
    return day.board_groups.flatMap((group) => {
      const stocks = expanded ? group.stocks : group.stocks.slice(0, Math.max(0, remaining));
      remaining -= stocks.length;
      return stocks.length ? [{ group, stocks }] : [];
    });
  }, [day.board_groups, expanded]);
  const visibleCount = expanded
    ? day.stock_count
    : Math.min(day.stock_count, DEFAULT_VISIBLE_STOCKS);
  const hasMore = day.stock_count > DEFAULT_VISIBLE_STOCKS;

  return (
    <div className="board-calendar-groups">
      {groups.map(({ group, stocks }) => (
        <section className="board-calendar-group" key={group.boards}>
          <span className="board-calendar-group-title">{group.boards}板</span>
          <div className="board-calendar-stocks">
            {stocks.map((stock) => (
              <span
                className="board-calendar-stock"
                key={stock.stock_ts_code || stock.stock_name}
                title={`${stock.stock_name} · ${stock.stock_ts_code}${stock.theme ? ` · ${stock.theme}` : ""}`}
              >
                {group.boards}-{shortStockCode(stock.stock_ts_code)} {stock.stock_name}
              </span>
            ))}
          </div>
        </section>
      ))}
      {hasMore && (
        <button className="board-calendar-expand" type="button" onClick={onToggle}>
          {expanded ? "收起" : `展开其余 ${day.stock_count - visibleCount} 只`}
        </button>
      )}
    </div>
  );
}

function CalendarDayCell({
  day,
  minBoards,
  expanded,
  onToggle,
}: {
  day: BoardCalendarDay;
  minBoards: number;
  expanded: boolean;
  onToggle: () => void;
}) {
  const isQuietTradingDay =
    day.calendar_status === "trading" &&
    day.data_status === "available" &&
    day.stock_count === 0;
  return (
    <article className={`board-calendar-day ${statusClass(day)}`}>
      <header className="board-calendar-day-header">
        <strong>{dayNumber(day.date)}</strong>
        <span>{dayStatus(day, minBoards)}</span>
      </header>
      {day.calendar_status === "trading" && day.data_status !== "board_data_missing" ? (
        isQuietTradingDay ? (
          <p className="board-calendar-empty">没有达到门槛的个股</p>
        ) : (
          <BoardGroups day={day} expanded={expanded} onToggle={onToggle} />
        )
      ) : (
        <p className="board-calendar-empty">
          {day.calendar_status === "closed" || day.calendar_status === "future"
            ? "非交易日"
            : day.calendar_status === "market_data_missing"
              ? "未找到市场日数据"
              : day.data_status === "board_data_missing"
                ? "连板数据缺失"
                : "暂不能确认"}
        </p>
      )}
    </article>
  );
}

export function BoardCalendarDashboard() {
  const [month, setMonth] = useState(() => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  });
  const [selectedMinBoards, setSelectedMinBoards] = useState<number | null>(null);
  const [calendar, setCalendar] = useState<BoardCalendar | null>(null);
  const [expandedDates, setExpandedDates] = useState<Set<string>>(() => new Set());
  const [retryToken, setRetryToken] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let disposed = false;
    setLoading(true);
    setError(null);
    setExpandedDates(new Set());
    void getBoardCalendar(month, selectedMinBoards ?? undefined)
      .then((next) => {
        if (disposed) return;
        setCalendar(next);
      })
      .catch((caught) => {
        if (!disposed) {
          setCalendar(null);
          setError(caught instanceof Error ? caught.message : "无法加载交易日历");
        }
      })
      .finally(() => {
        if (!disposed) setLoading(false);
      });
    return () => {
      disposed = true;
    };
  }, [month, retryToken, selectedMinBoards]);

  const minBoards = selectedMinBoards ?? calendar?.min_boards ?? 3;
  const gridDays = useMemo(
    () => (calendar ? [...Array(weekdayOffset(month)).fill(null), ...calendar.calendar_days] : []),
    [calendar, month],
  );
  const tradingCount = calendar?.trading_days.length ?? 0;
  const populatedCount = calendar?.trading_days.filter((day) => day.stock_count > 0).length ?? 0;

  const toggleExpanded = (date: string) => {
    setExpandedDates((current) => {
      const next = new Set(current);
      if (next.has(date)) next.delete(date);
      else next.add(date);
      return next;
    });
  };

  return (
    <main className="board-calendar-workbench">
      <header className="board-calendar-header">
        <div>
          <span className="output-eyebrow">交易日历 · 连板梯队</span>
          <h1>哪一天，哪些股走到了几板</h1>
          <p>
            以市场交易日为底座；标签按达到的最高连板数展示。非交易日、市场缺口和连板数据缺口分开标记，不把空白猜成休市。
          </p>
        </div>
        <div className="board-calendar-controls">
          <div className="board-calendar-month-nav" aria-label="切换月份">
            <button
              type="button"
              aria-label="上个月"
              onClick={() => setMonth((current) => shiftMonth(current, -1))}
            >
              <ChevronLeft aria-hidden="true" size={16} />
            </button>
            <strong>{monthLabel(month)}</strong>
            <button
              type="button"
              aria-label="下个月"
              onClick={() => setMonth((current) => shiftMonth(current, 1))}
            >
              <ChevronRight aria-hidden="true" size={16} />
            </button>
          </div>
          <div className="board-calendar-threshold" role="group" aria-label="连板门槛">
            <SlidersHorizontal aria-hidden="true" size={14} />
            <span>展示</span>
            {[2, 3].map((threshold) => (
              <button
                className={minBoards === threshold ? "active" : ""}
                type="button"
                key={threshold}
                aria-pressed={minBoards === threshold}
                onClick={() => setSelectedMinBoards(threshold)}
              >
                ≥{threshold}板
              </button>
            ))}
          </div>
        </div>
      </header>

      {loading && <div className="board-calendar-loading">正在加载交易日历…</div>}
      {error && (
        <div className="board-calendar-error" role="alert">
          <AlertTriangle aria-hidden="true" size={16} />
          <span>{error}</span>
          <button type="button" onClick={() => setRetryToken((current) => current + 1)}>
            <RefreshCw aria-hidden="true" size={14} /> 重试
          </button>
        </div>
      )}
      {!loading && calendar && (
        <>
          <section className={`board-calendar-notice ${calendar.status}`}>
            {calendar.status === "partial" ? <AlertTriangle aria-hidden="true" size={15} /> : <CircleHelp aria-hidden="true" size={15} />}
            <span>{calendar.message}</span>
            <small>
              门槛 ≥{minBoards}板 · 市场数据至 {calendar.market_data_cutoff ?? "未知"} · 连板数据至 {calendar.board_data_cutoff ?? "未知"}
            </small>
          </section>
          <section className="board-calendar-summary" aria-label="日历摘要">
            <div><strong>{tradingCount}</strong><span>个交易日</span></div>
            <div><strong>{populatedCount}</strong><span>天有达标个股</span></div>
            <div><strong>{calendar.recommended_min_boards}板</strong><span>系统建议起始门槛</span></div>
          </section>
          <div className="board-calendar-grid-scroll">
            <section className="board-calendar-grid" aria-label={`${monthLabel(month)}交易日历`}>
              {WEEKDAYS.map((weekday) => (
                <div className="board-calendar-weekday" key={weekday}>
                  周{weekday}
                </div>
              ))}
              {gridDays.map((day, index) =>
                day ? (
                  <CalendarDayCell
                    day={day}
                    minBoards={minBoards}
                    expanded={expandedDates.has(day.date)}
                    onToggle={() => toggleExpanded(day.date)}
                    key={day.date}
                  />
                ) : (
                  <div
                    className="board-calendar-placeholder"
                    aria-hidden="true"
                    key={`placeholder-${index}`}
                  />
                ),
              )}
            </section>
          </div>
        </>
      )}
    </main>
  );
}
