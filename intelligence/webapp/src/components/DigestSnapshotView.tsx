import { Camera, ChevronDown } from "lucide-react";
import type { WatchlistDigestSnapshot } from "../types";

/** 主张档前缀与包渲染同源（fact/inference/gap），不新开 marker 方言。 */
const TIER_PREFIX: Record<string, string> = {
  fact: "（事实）",
  inference: "（推断）",
  gap: "（缺口）",
};

const BAG_LABELS: Record<string, string> = {
  market_daily: "全市场袋",
  mainline: "主线袋",
  dual_red: "严格双红袋",
  limit_heat: "涨停热度袋",
};

interface DigestSnapshotViewProps {
  snapshot: WatchlistDigestSnapshot;
}

/**
 * 自选简报证据快照页（P1b）：只读渲染包生成时刻冻住的袋行、清单与接合行。
 * 事后对账只对这份快照；本组件不提供任何改写入口。
 */
export function DigestSnapshotView({ snapshot }: DigestSnapshotViewProps) {
  const snapshotId = `${snapshot.schema} · ${
    snapshot.standing_date ?? "无站立日"
  } · ${snapshot.user_id}`;
  const listItems = [...snapshot.watchlist, ...snapshot.focus_themes];
  const fermentations = snapshot.fermentations ?? [];

  return (
    <details
      className="message-run-details digest-snapshot"
      data-testid="digest-snapshot"
    >
      <summary>
        <span>
          <ChevronDown aria-hidden="true" size={15} />
          <Camera aria-hidden="true" size={15} />
          证据快照 · {snapshot.standing_date ?? "站立日不可用"}
        </span>
        <span className="digest-snapshot-id">{snapshot.schema}</span>
      </summary>
      <div className="message-run-body">
        <dl className="message-run-meta">
          <div>
            <dt>快照标识</dt>
            <dd>{snapshotId}</dd>
          </div>
          <div>
            <dt>清单（{listItems.length} 项）</dt>
            <dd>{listItems.join("、") || "空"}</dd>
          </div>
        </dl>
        <p className="digest-snapshot-method">方法卡：{snapshot.method_card}</p>

        <section aria-label="四袋状态">
          <h3>四袋状态</h3>
          <table className="digest-snapshot-bags">
            <thead>
              <tr>
                <th>袋</th>
                <th>状态</th>
                <th>served_date</th>
                <th>行数</th>
              </tr>
            </thead>
            <tbody>
              {snapshot.bags.map((bag) => (
                <tr key={bag.name}>
                  <td>{BAG_LABELS[bag.name] ?? bag.name}</td>
                  <td>{bag.status}</td>
                  <td>{bag.served_date ?? "—"}</td>
                  <td>{bag.rows.length}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        <section aria-label="接合行">
          <h3>接合行（清单 × 袋）</h3>
          <ul className="digest-snapshot-rows">
            {snapshot.rows.map((row, index) => (
              <li key={`${row.subject}-${row.tier}-${index}`}>
                {TIER_PREFIX[row.tier] ?? ""}
                {row.text}
              </li>
            ))}
            {snapshot.rows.length === 0 && <li>无接合行。</li>}
          </ul>
        </section>

        {fermentations.length > 0 && (
          <section aria-label="发酵摘要">
            <h3>发酵摘要</h3>
            <ul className="digest-snapshot-rows">
              {fermentations.map((item, index) => (
                <li key={`ferm-${index}`}>{String(item.text ?? "")}</li>
              ))}
            </ul>
          </section>
        )}

        <section aria-label="袋行明细">
          <h3>袋行明细（冻结原样）</h3>
          {snapshot.bags.map((bag) => (
            <details key={`detail-${bag.name}`}>
              <summary>
                {BAG_LABELS[bag.name] ?? bag.name} · {bag.rows.length} 行
              </summary>
              <pre className="digest-snapshot-json">
                {JSON.stringify(bag.rows, null, 2)}
              </pre>
            </details>
          ))}
        </section>
      </div>
    </details>
  );
}
