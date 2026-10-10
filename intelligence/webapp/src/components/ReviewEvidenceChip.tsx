import "../riverHistory.css";

/** Shows what the next message will carry: window coordinates only, verified by the server on send. */
export function ReviewEvidenceChip({ label, onRemove }: { label: string; onRemove: () => void }) {
  return <div className="rh-handoff-chip" role="status" aria-label="附带复盘证据">
    <span>附带连续复盘证据：{label}。发送时服务端按坐标重读同一份归档并核对；你查看后归档被改动会拒收。</span>
    <button type="button" onClick={onRemove}>不附带</button>
  </div>;
}
