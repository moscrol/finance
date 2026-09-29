import { useEffect, useState } from "react";

type Ladder = Record<string, number>;
type Detail = { name: string; ts_code: string; boards: number; theme: string | null; pct: number | null };
type Day = {
  trade_date: string;
  ladder: Ladder;
  details: Detail[];
  total_lianban: number;
  max_boards: number;
  market: { limit_up: number | null; limit_down: number | null; advancers: number | null; amount: number | null; stage: string | null };
  leader: { height: number; name: string | null };
};

export function LimitUpCalendarDashboard() {
  const [data, setData] = useState<Day[]>([]);
  const [filter, setFilter] = useState<"all" | "high" | "5">("all");
  const [month, setMonth] = useState<string>("all");
  const [selected, setSelected] = useState<Day | null>(null);

  useEffect(() => {
    fetch("/limitup-calendar/data.json")
      .then(r => r.json())
      .then(setData)
      .catch(() => fetch("/market_snapshot/limitup_calendar.json").then(r=>r.json()).then(setData).catch(()=>{}));
  }, []);

  const months = [...new Set(data.map(d => d.trade_date.slice(0,7)))].sort().reverse();
  const filtered = data.filter(d => {
    if (month !== "all" && !d.trade_date.startsWith(month)) return false;
    if (filter === "high" && d.max_boards < 4) return false;
    if (filter === "5" && d.max_boards < 5) return false;
    return true;
  });

  const byMonth: Record<string, Day[]> = {};
  filtered.forEach(d => { const m = d.trade_date.slice(0,7); if(!byMonth[m]) byMonth[m]=[]; byMonth[m].push(d); });

  return (
    <div style={{ padding: 20 }}>
      <h1 style={{ fontSize: 20, fontWeight: 700 }}>连板日历 <span style={{ color: "#f43f5e" }}>Dashboard</span> 重做版</h1>
      <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
        <select value={month} onChange={e=>setMonth(e.target.value)}>
          <option value="all">全部</option>
          {months.map(m=><option key={m} value={m}>{m}</option>)}
        </select>
        <button onClick={()=>setFilter("all")} style={{ background: filter==="all"?"#f43f5e":"#27272a", color:"#fff", border:0, padding:"6px 10px", borderRadius:8 }}>全部</button>
        <button onClick={()=>setFilter("high")} style={{ background: filter==="high"?"#f43f5e":"#27272a", color:"#fff", border:0, padding:"6px 10px", borderRadius:8 }}>≥4板</button>
        <button onClick={()=>setFilter("5")} style={{ background: filter==="5"?"#f43f5e":"#27272a", color:"#fff", border:0, padding:"6px 10px", borderRadius:8 }}>≥5板</button>
      </div>

      {Object.keys(byMonth).sort().reverse().map(m=>(
        <div key={m} style={{ marginTop: 24 }}>
          <h2 style={{ fontSize: 14, marginBottom: 8 }}>{m}</h2>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(7,1fr)", gap: 1, background: "#1f1f23", borderRadius: 12, overflow: "hidden" }}>
            {["一","二","三","四","五","六","日"].map(w=><div key={w} style={{ background:"#111113", padding:8, textAlign:"center", fontSize:11, color:"#71717a" }}>周{w}</div>)}
            {byMonth[m].map(d=>(
              <div key={d.trade_date} onClick={()=>setSelected(d)} style={{ background: d.max_boards>=5?"rgba(244,63,94,0.15)":"#141416", minHeight:90, padding:8, cursor:"pointer" }}>
                <div style={{ display:"flex", justifyContent:"space-between", fontSize:11 }}>{d.trade_date.slice(5)}<b style={{ background: d.max_boards>=5?"#f43f5e":"#1f1f23", color: d.max_boards>=5?"#fff":"#e5e5e5", padding:"2px 6px", borderRadius:10 }}>{d.max_boards}板</b></div>
                <div style={{ marginTop:6, display:"flex", flexWrap:"wrap", gap:3 }}>{Object.entries(d.ladder).map(([b,c])=><span key={b} style={{ fontSize:10, padding:"2px 5px", borderRadius:6, background:"#1f1f23", border:"1px solid #2a2a2e" }}>{b}板×{c}</span>)}</div>
                <div style={{ marginTop:4, fontSize:10, color:"#71717a" }}>{d.total_lianban}只 · 涨停{d.market.limit_up||"-"}只</div>
                {d.leader.name && <div style={{ fontSize:10, color:"#f43f5e" }}>龙头:{d.leader.name} {d.leader.height}板</div>}
              </div>
            ))}
          </div>
        </div>
      ))}

      {selected && (
        <div style={{ position:"fixed", inset:0, background:"rgba(0,0,0,0.7)", display:"flex", alignItems:"center", justifyContent:"center", zIndex:50 }} onClick={()=>setSelected(null)}>
          <div style={{ background:"#18181b", border:"1px solid #27272a", borderRadius:16, maxWidth:720, width:"90%", maxHeight:"80vh", overflow:"auto", padding:20 }} onClick={e=>e.stopPropagation()}>
            <h2>{selected.trade_date} · 最高{selected.max_boards}板 · {selected.total_lianban}只</h2>
            <div style={{ display:"flex", gap:12, flexWrap:"wrap", marginTop:12, padding:10, background:"#111113", borderRadius:10, fontSize:12 }}>
              <span>涨停:{selected.market.limit_up}</span><span>跌停:{selected.market.limit_down}</span><span>上涨:{selected.market.advancers}</span><span>龙头:{selected.leader.name} {selected.leader.height}板</span>
            </div>
            <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fill,minmax(200px,1fr))", gap:8, marginTop:12 }}>
              {selected.details.map(s=><div key={s.ts_code} style={{ padding:"10px 12px", background:"#1f1f23", borderRadius:10, display:"flex", justifyContent:"space-between" }}><div><b>{s.name}</b><div style={{ fontSize:10, color:"#a1a1aa" }}>{s.theme||"—"}</div></div><b style={{ background: s.boards>=5?"#f43f5e":s.boards>=4?"#f59e0b":"#27272a", color: s.boards>=4?"#000":"#fff", padding:"4px 8px", borderRadius:8 }}>{s.boards}板</b></div>)}
            </div>
            <button onClick={()=>setSelected(null)} style={{ marginTop:16, background:"#27272a", color:"#fff", border:0, padding:"8px 16px", borderRadius:8 }}>关闭</button>
          </div>
        </div>
      )}
    </div>
  );
}
