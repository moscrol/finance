import { useEffect, useState } from "react";
import type { ReviewHistory } from "../../river/historyTypes";
import { buildReviewEvidenceHandoff, buildReviewEvidencePacket, sendReviewEvidenceToChat, type ReadingInstructions } from "../../river/reviewEvidence";

const draftKey = "river-review-reading-instructions-v1";
const empty: ReadingInstructions = { question: "", method: "", cautions: "" };
function loadDraft(): ReadingInstructions {
  try {
    const value = JSON.parse(sessionStorage.getItem(draftKey) ?? "null");
    return value && ["question", "method", "cautions"].every(k => typeof value[k] === "string") ? value : empty;
  } catch { return empty; }
}

export function ReviewReadingGuide({ data, selectedDate }: { data: ReviewHistory; selectedDate: string | null }) {
  const [draft, setDraft] = useState<ReadingInstructions>(loadDraft);
  const [saved, setSaved] = useState(true);
  useEffect(() => {
    try { sessionStorage.setItem(draftKey, JSON.stringify(draft)); setSaved(true); }
    catch { setSaved(false); }
  }, [draft]);
  const contract = data.evidence_contract;
  if (!contract || contract.version !== "review-evidence/v1") return <p className="rh-empty">接口尚未提供兼容的数据种类说明；原始读数可查，Agent 交接暂不可用。请配套更新后端。</p>;
  const exportPacket = () => {
    const packet = buildReviewEvidencePacket(data, selectedDate, draft);
    const url = URL.createObjectURL(new Blob([JSON.stringify(packet, null, 2)], { type: "application/json" }));
    const link = document.createElement("a"); link.href = url; link.download = `复盘联立证据-${data.start}-${data.end}.json`; link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  const canHandOff = Boolean(data.window_fingerprint && data.industry);
  const handOff = () => sendReviewEvidenceToChat(buildReviewEvidenceHandoff(data, selectedDate, draft));
  return <section className="rh-reading" aria-label="人和Agent共用证据">
    <header><span className="rh-eyebrow">SAME EVIDENCE · TWO WAYS TO READ</span><h3>你看图表，Agent 读同种数据。</h3><p>不是让 Agent 看 dashboard，也不是只给它一段摘要。下面四类证据与页面读数来自同一接口；先对齐名称，再说明怎样联立。以下问题是阅读提示，不是自动判断。</p></header>
    <div className="rh-reading-map">{contract.groups.map((group, i) => <article key={group.id}><span className="rh-eyebrow">0{i + 1}</span><h4>{group.label}</h4><p>{group.question}</p><details><summary>对应字段与边界</summary><code>{group.fields.join(" · ")}</code><p>{group.boundary}</p>{group.selection && <p><b>入选条件：</b>{group.selection}</p>}</details></article>)}</div>
    {contract.selection_bias && <p className="rh-boundary" role="note">{contract.selection_bias}</p>}
    <p className="rh-muted">{contract.scope}。前三项只是名单预览，交接包保留接口返回的全部行与截断标志；不因页面折叠或矩阵切换而省略数据。</p>
    <details className="rh-dictionary"><summary>数据字典 · 指标、缺失含义与来源限制</summary>
      <div className="rh-scroll"><table className="rh-table"><caption>市场读数：原日报 facts，不按本窗重算</caption><thead><tr><th>页面名称</th><th>单位</th><th>Agent 字段</th><th>原日报字段</th></tr></thead><tbody>{data.metrics.map(m => <tr key={m.key}><th>{m.label}</th><td>{m.unit}</td><td><code>points[].metrics.{m.key}</code></td><td><code>{m.source_field}</code></td></tr>)}</tbody></table></div>
      {contract.related_reader && <><h4>需要完整日报的其他栏目？</h4><p>{contract.related_reader.purpose}</p><code>{contract.related_reader.endpoint}</code><p>{contract.related_reader.boundary}</p></>}
      <h4>共同对齐方式</h4><ul>{contract.join_keys.map(k => <li key={k}>{k}</li>)}</ul><p>{contract.citation_rule}</p>
      <h4>缺失不能当成零</h4><dl>{Object.entries(contract.missing_semantics).map(([k, v]) => <div key={k}><dt><code>{k}</code></dt><dd>{v}</dd></div>)}</dl>
      <h4>来源与版本：未知就是未知</h4><dl>{Object.entries(contract.provenance_policy).map(([k, v]) => <div key={k}><dt><code>{k}</code></dt><dd>{v === null ? "未记录" : v === false ? "不保证" : String(v)}</dd></div>)}</dl>
    </details>
    <details className="rh-teaching"><summary>告诉 Agent：这些数据应该怎样联立解读</summary>
      <p>可复用的方法草稿不随选日清空。导出前请确认下面的窗口与行业；这些说明不会写入日报事实，也不会自动发送或自动执行。</p>
      <div className="rh-instruction-scope">本次交接：{data.start} → {data.end} · {data.industry || "未指定行业"} · 查看日 {selectedDate ?? "未选"}</div>
      <label>这次想判断什么<textarea maxLength={2000} value={draft.question} onChange={e => setDraft({ ...draft, question: e.target.value })} placeholder="例如：电子行业这段时间的强化，是否同时得到市场环境、子板块和发动机名单的支持？"/></label>
      <label>先看什么，再结合什么<textarea maxLength={8000} value={draft.method} onChange={e => setDraft({ ...draft, method: e.target.value })} placeholder="例如：先看成交额与涨家数的 MA5，再看行业榜内顺位；按同日核对子板块双红、新高和发动机原表。分别列出一致与不一致的证据，不直接把同时变化当因果。"/></label>
      <label>哪些情况不能直接下结论<textarea maxLength={4000} value={draft.cautions} onChange={e => setDraft({ ...draft, cautions: e.target.value })} placeholder="例如：缺归档不推断退潮；名单截断不判断股票退出；未列榜不当零；公式口径不明时先提出疑问。"/></label>
      <p className="rh-muted" role="status">{saved ? "草稿仅保存在当前浏览器标签页的会话存储；关闭标签页后可能丢失，请导出保存。" : "浏览器未允许保存草稿，离开页面可能丢失，请导出保存。"}</p>
      <div className="rh-reading-actions"><button type="button" disabled={!canHandOff} title={canHandOff ? "打开问答并预填上面的方法；只发送窗口坐标，服务端重读同一份归档并核对" : "需要固定行业且接口提供窗口指纹"} onClick={handOff}>带着证据去问答</button><button type="button" onClick={exportPacket}>导出 Agent 联立证据包</button><button type="button" onClick={() => setDraft({ ...empty })}>清空解读说明</button></div>
      <details><summary>交接要求与 Agent 回答结构</summary><ul>{contract.agent_rules.map(rule => <li key={rule}>{rule}</li>)}</ul><p>回答按“覆盖与口径限制 → 联立证据 → 支持与不支持 → 尚不能判断”组织，并引用日期、字段和内容哈希。“带着证据去问答”会打开新对话并预填方法，不自动发送；发送时服务端按坐标重读同一份归档，内容在你查看后被改动则拒收。回答仍须你核对。</p></details>
    </details>
  </section>;
}
