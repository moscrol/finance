import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { Activity, ArrowDownToLine, ArrowRight, ArrowUpRight, BarChart3, BookOpen, Check, CheckCircle2, ChevronDown, Clipboard, Clock3, Code2, Equal, FileText, Flag, FlaskConical, History as HistoryIcon, Info, KeyRound, Layers3, LoaderCircle, LockKeyhole, Menu, MessageSquarePlus, PanelLeftClose, Plus, RefreshCw, Scale, ShieldCheck, SkipForward, Target, Users, X } from "lucide-react";
import DOMPurify from "dompurify";
import { marked } from "marked";
import { api, bootstrap, type Assignment, type Board, type Bootstrap, type Category, type Choice, type History, type Mode, type Reason, type Strategy } from "./api";

type View = "arena" | "leaderboard" | "strategies" | "history" | "connect" | "method";
type ModalName = "join" | "question" | "evidence" | "report" | null;
const categories: Record<Category, string> = { financial: "财务分析", industry: "产业研究", event: "事件研判", strategy: "策略研究" };
const choices: Record<Choice, string> = { left: "A 更好", right: "B 更好", tie: "同样好", both_bad: "都不够好" };
const reasons: Record<Reason, string> = { evidence: "证据扎实", reasoning: "分析深入", numbers: "数字准确", risk: "风险充分", clarity: "表达清晰" };
const navigation = [
  { id: "arena", name: "研究盲评", icon: Scale }, { id: "leaderboard", name: "胜率观察", icon: BarChart3 },
  { id: "strategies", name: "策略前向", icon: Target }, { id: "history", name: "我的评测", icon: HistoryIcon },
] as const;
const questionStates: Record<string, string> = { pending: "待运营审核", running: "正在运行", review: "等待发布", published: "已发布", failed: "运行失败", withdrawn: "已撤销" };
const titles: Record<View, string> = { arena: "研究盲评", leaderboard: "胜率观察", strategies: "策略前向", history: "我的评测", connect: "Agent 接入", method: "评测规则" };
const formatDate = (value: string) => new Date(value).toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false });
const percent = (value: number | null) => value === null ? "—" : `${(value * 100).toFixed(1)}%`;

function Markdown({ content }: { content: string }) {
  // Participant output is untrusted. No links, images, HTML controls or tracking pixels.
  const html = DOMPurify.sanitize(marked.parse(content, { async: false }), {
    ALLOWED_TAGS: ["p", "strong", "em", "ul", "ol", "li", "h2", "h3", "h4", "blockquote", "code", "pre", "table", "thead", "tbody", "tr", "th", "td", "hr", "br"], ALLOWED_ATTR: [],
  });
  return <div className="answer-prose" dangerouslySetInnerHTML={{ __html: html }} />;
}

function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => { const el = ref.current; el?.showModal(); return () => el?.close(); }, []);
  return <dialog ref={ref} className="arena-modal" onCancel={onClose} onClick={event => { if (event.target === event.currentTarget) onClose(); }}>
    <header><h2>{title}</h2><button className="icon-btn" onClick={onClose} aria-label="关闭" title="关闭"><X size={20} /></button></header>
    {children}
  </dialog>;
}

function Empty({ icon, title, detail, children }: { icon: ReactNode; title: string; detail: string; children?: ReactNode }) {
  return <div className="empty-state"><div className="empty-icon">{icon}</div><h3>{title}</h3><p>{detail}</p><div className="empty-actions">{children}</div></div>;
}

export default function Arena() {
  const [boot, setBoot] = useState<Bootstrap | null>(null);
  const [view, setView] = useState<View>("arena");
  const [mode, setMode] = useState<Mode>("demo");
  const [category, setCategory] = useState<Category | "">("");
  const [assignment, setAssignment] = useState<Assignment | null>(null);
  const [board, setBoard] = useState<Board | null>(null);
  const [history, setHistory] = useState<History | null>(null);
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [modal, setModal] = useState<ModalName>(null);
  const [modalError, setModalError] = useState("");
  const [selectedReasons, setSelectedReasons] = useState<Reason[]>([]);
  const [mobileSide, setMobileSide] = useState(0);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [boardMode, setBoardMode] = useState<"overall" | "pairwise">("overall");
  const requestSequence = useRef(0);

  const notify = useCallback((text: string) => setToast(text), []);
  useEffect(() => { if (toast) { const timer = setTimeout(() => setToast(""), 4000); return () => clearTimeout(timer); } }, [toast]);

  const loadAssignment = useCallback(async (nextMode: Mode, nextCategory: Category | "", questionId?: string) => {
    const seq = ++requestSequence.current;
    setLoading(true); setError(""); setSelectedReasons([]); setMobileSide(0);
    try {
      const result = await api<{ assignment: Assignment | null }>("assignments", { mode: nextMode, category: nextCategory || null, question_id: questionId ?? null });
      if (seq === requestSequence.current) setAssignment(result.assignment);
    } catch (err) { if (seq === requestSequence.current) setError(String(err instanceof Error ? err.message : err)); }
    finally { if (seq === requestSequence.current) setLoading(false); }
  }, []);

  const initialize = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const data = await bootstrap(); setBoot(data);
      const initialMode = data.summary.live_cases ? "live" : "demo";
      setMode(initialMode);
      await loadAssignment(initialMode, "");
    } catch (err) { setError(err instanceof Error ? err.message : "连接失败"); setLoading(false); }
  }, [loadAssignment]);
  useEffect(() => { void initialize(); }, [initialize]);

  useEffect(() => {
    if (!boot || view === "arena" || view === "connect" || view === "method") return;
    let active = true;
    setLoading(true); setError("");
    const run = async () => {
      try {
        if (view === "leaderboard") { const data = await api<Board>(`leaderboard${category ? `?category=${category}` : ""}`); if (active) setBoard(data); }
        if (view === "history") { const data = await api<History>("history"); if (active) setHistory(data); }
        if (view === "strategies") { const data = await api<{ strategies: Strategy[] }>("strategies"); if (active) setStrategies(data.strategies); }
      } catch (err) { if (active) setError(err instanceof Error ? err.message : "读取失败"); }
      finally { if (active) setLoading(false); }
    };
    void run(); return () => { active = false; };
  }, [view, category, boot]);

  const navigate = (next: View) => { setView(next); setError(""); setSidebarOpen(false); if (next === "arena") void loadAssignment(mode, category); };
  const openModal = (name: ModalName) => { setModalError(""); setModal(name); };
  const changeMode = (next: Mode) => { setMode(next); void loadAssignment(next, category); };
  const changeCategory = (value: string) => { const next = value as Category | ""; setCategory(next); if (view === "arena") void loadAssignment(mode, next); };

  const vote = async (choice: Choice) => {
    if (!assignment || busy) return;
    setBusy(true); setError("");
    try {
      const result = await api<Assignment>(`assignments/${assignment.id}/vote`, { choice, reasons: selectedReasons });
      setAssignment(result); setBoot(await bootstrap());
      notify(result.vote?.counted ? "投票已计入正式统计" : "体验投票已保存，不计入正式统计");
    } catch (err) { setError(err instanceof Error ? err.message : "投票失败，请重试"); }
    finally { setBusy(false); }
  };
  const skip = async () => {
    if (!assignment || busy) return;
    setBusy(true);
    try { await api(`assignments/${assignment.id}/skip`, {}); await loadAssignment(mode, category); }
    catch (err) { setError(err instanceof Error ? err.message : "跳过失败"); }
    finally { setBusy(false); }
  };
  const copy = async (text: string) => {
    try { await navigator.clipboard.writeText(text); notify("已复制"); }
    catch { notify("浏览器未允许访问剪贴板"); }
  };
  const readHistory = async (id: string) => {
    setLoading(true); setError(""); setView("arena");
    try { const data = await api<Assignment>(`assignments/${id}`); setAssignment(data); setMode(data.mode); }
    catch (err) { setError(err instanceof Error ? err.message : "读取失败"); }
    finally { setLoading(false); }
  };

  return <div className="arena-shell">
    {sidebarOpen && <button className="sidebar-backdrop" aria-label="收起导航" onClick={() => setSidebarOpen(false)} />}
    <aside className={`arena-sidebar ${sidebarOpen ? "is-open" : ""}`}>
      <a className="brand" href="#arena" onClick={event => { event.preventDefault(); navigate("arena"); }}><span className="brand-mark"><Scale size={22} /></span><span>FinArena<small>金融 Agent 评测</small></span></a>
      <button className="mobile-close icon-btn" aria-label="收起导航" title="收起导航" onClick={() => setSidebarOpen(false)}><PanelLeftClose size={19} /></button>
      <div className="nav-label">评测工作台</div>
      <nav aria-label="主导航">{navigation.map(({ id, name, icon: Icon }) => <button key={id} className={view === id ? "active" : ""} aria-current={view === id ? "page" : undefined} onClick={() => navigate(id)}><Icon size={19} /><span>{name}</span>{id === "arena" && <span className="nav-dot" />}</button>)}</nav>
      <div className="sidebar-divider" />
      <nav aria-label="平台信息"><button className={view === "connect" ? "active" : ""} onClick={() => navigate("connect")}><Code2 size={19} />Agent 接入</button><button className={view === "method" ? "active" : ""} onClick={() => navigate("method")}><BookOpen size={19} />评测规则</button></nav>
      <div className="sidebar-bottom"><span className="status-dot" /><span>邀请试运行</span><span className="version">v0.1</span></div>
    </aside>
    <div className="arena-workspace">
      <header className="topbar"><div className="breadcrumb"><button className="icon-btn mobile-menu" title="打开导航" aria-label="打开导航" onClick={() => setSidebarOpen(true)}><Menu size={21} /></button><span>评测工作台</span><span className="slash">/</span><strong>{titles[view]}</strong></div><button className={`reviewer-button ${boot?.reviewer ? "verified" : ""}`} onClick={() => openModal("join")}><span className="avatar"><Users size={15} /></span><span>{boot?.reviewer ?? "游客"}</span>{boot?.reviewer ? <ShieldCheck size={16} /> : <span className="join-label">加入评审 <ArrowUpRight size={14} /></span>}</button></header>
      <main>
        <div className="page-heading"><div><div className="eyebrow">FINANCIAL AGENT ARENA</div><h1>{titles[view]}</h1></div><div className="heading-actions">{view === "arena" && <button className="secondary" onClick={() => openModal("question")}><Plus size={16} />提交题目</button>}<span className="pilot-label"><span className="status-dot" />邀请试运行</span></div></div>
        {error && <div className="error-banner" role="alert"><Info size={18} /><span>{error}</span><button onClick={() => void initialize()} className="text-button"><RefreshCw size={15} />重新连接</button></div>}
        {!boot ? <div className="loading-state"><LoaderCircle className="spin" size={24} /><span>连接评测台</span></div> : <>
          {view === "arena" && <>
            <div className="arena-toolbar"><div className="segmented" aria-label="评测模式"><button aria-pressed={mode === "live"} className={mode === "live" ? "selected" : ""} disabled={busy || loading} onClick={() => changeMode("live")}><ShieldCheck size={15} />正式盲评<span>{boot.summary.live_cases}</span></button><button aria-pressed={mode === "demo"} className={mode === "demo" ? "selected" : ""} disabled={busy || loading} onClick={() => changeMode("demo")}><FlaskConical size={15} />体验场</button></div><label className="filter-label"><Layers3 size={15} /><select aria-label="研究类型" value={category} disabled={busy || loading} onChange={event => changeCategory(event.target.value)}><option value="">全部研究</option>{Object.entries(categories).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select><ChevronDown size={14} /></label></div>
            {loading ? <div className="loading-state"><LoaderCircle className="spin" size={24} /><span>正在分配评测</span></div> : !assignment ? <Empty icon={<Scale size={30} />} title={mode === "live" ? "暂无可参与的正式对战" : "本组体验题已完成"} detail={mode === "live" ? "正式结果等待接入与发布，当前没有模拟胜率。" : "你的体验记录已保存，未计入正式榜。"}><button className="primary" onClick={() => mode === "live" ? changeMode("demo") : navigate("history")}>{mode === "live" ? "进入体验场" : "查看我的评测"}<ArrowRight size={16} /></button><button className="secondary" onClick={() => openModal("question")}><MessageSquarePlus size={16} />提交题目</button></Empty> : <>
              <div className={`provenance-band ${assignment.mode === "demo" ? "demo" : "live"}`}>{assignment.mode === "demo" ? <FlaskConical size={16} /> : <ShieldCheck size={16} />}<strong>{assignment.mode === "demo" ? "演示场" : "正式对战"}</strong><span>{assignment.mode === "demo" ? "人工编写的虚构材料与回答 · 不计入正式统计" : boot.reviewer ? "邀请评审 · 投票后揭晓身份" : "游客体验票 · 不计入正式统计"}</span>{!boot.reviewer && assignment.mode === "live" && <button className="text-button" onClick={() => openModal("join")}>加入正式评审<ArrowRight size={14} /></button>}</div>
              <section className="question-band"><div className="question-meta"><span className="category-tag">{categories[assignment.category]}</span><span><Clock3 size={13} />{assignment.as_of}</span></div><h2>{assignment.question}</h2><div className="question-bottom"><button className="source-button" onClick={() => openModal("evidence")}><img src="/arena-evidence.png" alt="" /><span>共同参考材料<strong>{assignment.evidence.length} 份</strong></span><ArrowUpRight size={15} /></button><span className="privacy-note"><LockKeyhole size={14} />{assignment.vote ? "身份已揭晓" : "双方身份已隐藏"}</span></div></section>
              {assignment.invalid_reason && <div className="error-banner" role="alert">本场已撤销：{assignment.invalid_reason}</div>}
              <div className="mobile-answer-tabs segmented" aria-label="切换回答">{["A", "B"].map((label, i) => <button key={label} className={mobileSide === i ? "selected" : ""} aria-pressed={mobileSide === i} onClick={() => setMobileSide(i)}>回答 {label}{assignment.vote?.choice === (i === 0 ? "left" : "right") && <Check size={15} />}</button>)}</div>
              <div className="answer-grid">{assignment.answers.map((answer, index) => {
                const won = assignment.vote?.choice === answer.side;
                return <article key={`${assignment.id}-${answer.side}`} className={`answer-panel ${mobileSide === index ? "mobile-visible" : ""} ${won ? "chosen" : ""}`} aria-label={`回答 ${index === 0 ? "A" : "B"}`}>
                  <header className="answer-header"><span className={`answer-letter letter-${index}`}>{index === 0 ? "A" : "B"}</span><div><h3>{answer.participant?.name ?? `匿名 Agent ${index === 0 ? "A" : "B"}`}</h3><span>{answer.participant ? answer.participant.version : "独立研究结果"}</span></div>{won ? <span className="chosen-label"><CheckCircle2 size={15} />你的选择</span> : !assignment.vote ? <LockKeyhole size={14} className="muted" /> : null}</header>
                  <Markdown content={answer.content} />
                  <footer className="answer-footer"><span><FileText size={13} />{answer.content.length.toLocaleString()} 字符</span>{answer.participant && assignment.mode === "live" && <span><Clock3 size={13} />{answer.duration_seconds?.toFixed(1)} 秒</span>}<span>{assignment.mode === "demo" ? "人工样例" : "平台运行原件"}</span></footer>
                </article>;
              })}</div>
              <div className="evaluation-bar">
                {assignment.vote ? <div className="vote-receipt"><CheckCircle2 size={22} /><div><strong>{assignment.vote.counted ? "已计入正式统计" : "体验投票已记录"}</strong><span>{choices[assignment.vote.choice]} · {formatDate(assignment.vote.created_at)}{!assignment.vote.counted && " · 不计入正式榜"}</span></div><button className="icon-btn" aria-label="复制评测回执" title="复制评测回执" onClick={() => void copy(JSON.stringify({ assignment_id: assignment.id, vote: assignment.vote, receipt: assignment.receipt }, null, 2))}><Clipboard size={17} /></button><button className="primary" onClick={() => void loadAssignment(mode, category)}>下一场<ArrowRight size={16} /></button></div> : <>
                  <div className="reason-row"><span>判断依据 <small>可选</small></span><div>{Object.entries(reasons).map(([key, label]) => <label key={key} className={selectedReasons.includes(key as Reason) ? "checked" : ""}><input type="checkbox" checked={selectedReasons.includes(key as Reason)} onChange={event => setSelectedReasons(previous => event.target.checked ? [...previous, key as Reason] : previous.filter(item => item !== key))} />{label}</label>)}</div></div>
                  <div className="vote-controls"><span className="vote-prompt">哪份研究更值得采纳？</span><div className="vote-buttons"><button disabled={busy || !!assignment.invalid_reason} onClick={() => void vote("left")} className="vote-choice"><span className="mini-letter" aria-hidden="true">A</span>A 更好</button><button disabled={busy || !!assignment.invalid_reason} onClick={() => void vote("right")} className="vote-choice"><span className="mini-letter blue" aria-hidden="true">B</span>B 更好</button><button disabled={busy || !!assignment.invalid_reason} onClick={() => void vote("tie")} className="vote-choice neutral"><Equal size={17} />同样好</button><button disabled={busy || !!assignment.invalid_reason} onClick={() => void vote("both_bad")} className="vote-choice neutral"><X size={16} />都不够好</button></div><button className="icon-btn skip" disabled={busy} title="跳过，不计票" aria-label="跳过，不计票" onClick={() => void skip()}>{busy ? <LoaderCircle className="spin" size={18} /> : <SkipForward size={18} />}</button></div>
                </>}
              </div>
              <div className="under-evaluation"><span><ShieldCheck size={13} />一场一票 · 揭晓后不可改票</span><button className="text-button" onClick={() => openModal("report")}><Flag size={13} />报告问题</button></div>
            </>}
          </>}
          {view === "leaderboard" && <>
            <div className="metrics-strip"><div><span>有效正式票</span><strong>{board?.formal_votes ?? 0}</strong><small>演示与游客票不计入</small></div><div><span>邀请评审</span><strong>{boot.summary.reviewers}</strong><small>至少提交一张正式票</small></div><div><span>参赛版本</span><strong>{board?.rows.length ?? 0}</strong><small>仅已发布的真实运行</small></div></div>
            <div className="arena-toolbar"><div className="segmented"><button className={boardMode === "overall" ? "selected" : ""} onClick={() => setBoardMode("overall")}>观测胜率</button><button className={boardMode === "pairwise" ? "selected" : ""} onClick={() => setBoardMode("pairwise")}>两两对战</button></div><label className="filter-label"><select aria-label="榜单研究类型" value={category} onChange={event => changeCategory(event.target.value)}><option value="">全部研究</option>{Object.entries(categories).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select><ChevronDown size={14} /></label></div>
            <div className="table-scroll"><table className="leaderboard-table"><thead><tr>{(boardMode === "overall" ? ["Agent / 版本", "观测胜率", "胜 / 负", "平局", "双差", "评审 / 题目", "状态"] : ["对战组合", "A 胜", "B 胜", "平局", "双差", "A 胜率"]).map(header => <th key={header}>{header}</th>)}</tr></thead><tbody>{boardMode === "overall" ? board?.rows.map(row => <tr key={row.key}><td><strong>{row.name}</strong><small>{row.version} · {row.kind === "model" ? "模型对照" : "Agent"}</small></td><td><strong className="rate">{percent(row.win_rate)}</strong><div className="rate-track"><span style={{ width: `${(row.win_rate ?? 0) * 100}%` }} /></div></td><td>{row.wins} / {row.losses}</td><td>{row.ties}</td><td>{row.both_bad}</td><td>{row.reviewers} / {row.cases}</td><td><span className={`status-label ${row.status === "collecting" ? "amber" : ""}`}>{row.status === "collecting" ? "样本积累中" : "描述统计"}</span></td></tr>) : board?.pairs.map(pair => <tr key={`${pair.a}-${pair.b}`}><td><strong>{board.rows.find(row => row.key === pair.a)?.name}</strong><small>vs {board.rows.find(row => row.key === pair.b)?.name}</small></td><td>{pair.a_wins}</td><td>{pair.b_wins}</td><td>{pair.ties}</td><td>{pair.both_bad}</td><td>{percent(pair.a_wins + pair.b_wins ? pair.a_wins / (pair.a_wins + pair.b_wins) : null)}</td></tr>)}</tbody></table></div>
            {loading ? <div className="loading-state"><LoaderCircle className="spin" size={22} />读取统计</div> : !board?.rows.length && <Empty icon={<BarChart3 size={30} />} title="胜率从第一张真实评审票开始" detail="当前没有已发布的正式对战；不会用示例票数填充榜单。"><button className="secondary" onClick={() => navigate("connect")}><Code2 size={16} />Agent 接入</button></Empty>}
            <section className="method-note"><Info size={18} /><div><h3>胜率不是收益率，也不是绝对实力排名</h3><p>观测胜率 = 胜场 /（胜场 + 负场）。平局、双差与跳过不进入这一分母；双差单独保留。当前按名称展示，未校正对手与题目分布，不提供显著性排名。</p><p>少于 30 个胜负票、10 位评审或 5 道题，标记为样本积累中。这些门槛不是统计显著性的证明。</p></div></section>
          </>}
          {view === "strategies" && <>
            <div className="section-intro"><span className="status-label amber"><Clock3 size={14} />前向登记阶段</span><span>事前锁定 · 真实时间窗口 · 独立于偏好投票</span></div><div className="strategy-stages">{["策略登记", "前向观察", "成交与费用复核", "公布实绩"].map((text, index) => <div key={text}><span>{String(index + 1).padStart(2, "0")}</span><strong>{text}</strong>{index < 3 && <ArrowRight size={16} />}</div>)}</div>
            {loading ? <div className="loading-state"><LoaderCircle className="spin" />读取策略</div> : !strategies.length ? <Empty icon={<Activity size={31} />} title="尚无已登记的前向策略" detail="成交核算与行情结算尚未接入，当前不展示策略收益或投资胜率。"><button className="secondary" onClick={() => navigate("method")}><BookOpen size={16} />查看评测口径</button></Empty> : <div className="strategy-list">{strategies.map(strategy => <article key={strategy.id}><div><span className="category-tag">{strategy.participant.name}</span><h3>{strategy.title}</h3><p>基准：{strategy.benchmark} · {strategy.holdings_count} 只证券</p><small>{formatDate(strategy.starts_at)} 至 {formatDate(strategy.ends_at)}</small></div><span className="status-label amber">{{ scheduled: "等待生效", observing: "观察中", awaiting_audit: "等待核算" }[strategy.status]}</span><button className="icon-btn" title="复制登记指纹" aria-label="复制登记指纹" onClick={() => void copy(strategy.sha256)}><Clipboard size={17} /></button></article>)}</div>}
          </>}
          {view === "history" && <>
            <div className="section-title"><h2>我的投票</h2><span>{history?.votes.length ?? 0} 条</span></div>
            {loading ? <div className="loading-state"><LoaderCircle className="spin" />读取记录</div> : !history?.votes.length ? <Empty icon={<HistoryIcon size={28} />} title="还没有评测记录" detail="当前浏览器的评测记录会保存在这里。"><button className="primary" onClick={() => navigate("arena")}>参与一场评测<ArrowRight size={16} /></button></Empty> : <div className="history-list">{history.votes.map(item => <button key={item.id} onClick={() => void readHistory(item.id)}><span className="history-icon"><CheckCircle2 size={18} /></span><div><span className="history-meta">{categories[item.category]} · {formatDate(item.created_at)}</span><h3>{item.question}</h3><span>{choices[item.choice]} · {item.counted ? "计入正式统计" : "体验票，不计入正式统计"}</span></div><ArrowUpRight size={18} /></button>)}</div>}
            <div className="section-title questions-title"><h2>我提交的题目</h2><button className="text-button" onClick={() => openModal("question")}><Plus size={15} />提交题目</button></div>{history?.questions.length ? <div className="question-list">{history.questions.map(item => <div key={item.id}><div><span className="history-meta">{categories[item.category]} · {formatDate(new Date(item.created * 1000).toISOString())}</span><h3>{item.question}</h3></div><span className="status-label amber">{questionStates[item.status] ?? item.status}</span>{item.status === "published" && <button className="icon-btn" title="参与该题" aria-label="参与该题" onClick={() => { setView("arena"); setMode("live"); setCategory(item.category); void loadAssignment("live", item.category, item.id); }}><ArrowUpRight size={18} /></button>}</div>)}</div> : <p className="muted empty-line">暂无题目提交</p>}
          </>}
          {view === "method" && <div className="document-page"><section><span className="document-number">01</span><div><h2>匿名比较，投票后揭晓</h2><p>平台随机分配左右位置，重复打开保持原位置。同一浏览器对同一份对战只能投一次，身份揭晓后不可修改选择。正式邀请使用一次后绑定当前浏览器会话。</p></div></section><section><span className="document-number">02</span><div><h2>真实统计有明确分母</h2><p>正式统计只接纳邀请评审对平台真实运行结果的票。人工样例、游客体验、跳过、撤销对战均不计入。平局与双差保留为独立结果，不暗中算成胜场。</p><p>榜单展示观测数据，不推断某个 Agent 一定更强；尚未加入对手难度校正或评审相关性估计。</p></div></section><section><span className="document-number">03</span><div><h2>记录不会被事后美化</h2><p>原始回答与资料绑定内容指纹，已发布结果不能原地覆盖。撤销需记录原因，原票与回执保留。报告问题不会自动改分，由运营复核。</p></div></section><section><span className="document-number">04</span><div><h2>研究偏好与策略实绩分开</h2><p>研究票反映评审偏好，不等于事实准确率或投资收益。策略须在生效前登记股票池、权重、基准和规则，不能回填历史成绩。本期尚未实现成交及收益结算。</p></div></section><section><span className="document-number">05</span><div><h2>试运行边界</h2><p>邀请机制限制重复身份，但不是实名认证，也不能完全阻止多人串票。当前浏览器会话有效期 30 天；清理浏览器数据会失去原记录访问权。平台尚未开放账户恢复。</p><p>提交题目会保存至运营队列，不会自动调用付费 Agent。请勿提交账户、个人敏感信息或机构保密材料。</p></div></section></div>}
          {view === "connect" && <div className="document-page"><div className="integration-header"><Code2 size={28} /><div><h2>开放评测接口</h2><p>arena-v1 · 异步运行 · 原始交付留存</p></div><span className="status-label">运营审核接入</span></div><section><span className="document-number">01</span><div><h2>提供三个任务接口</h2><div className="endpoint-list"><code><b>POST</b> /runs</code><code><b>GET</b> /runs/&#123;run_id&#125;</code><code><b>POST</b> /runs/&#123;run_id&#125;/cancel</code></div><p>任务包含问题、资料、截止口径与时限。完成时返回 status=completed 和 answer.content。API 地址与密钥由运营方在服务端配置，不接受访客输入任意调用地址。</p></div></section><section><span className="document-number">02</span><div><h2>固定版本与公开身份</h2><p>登记产品名、版本及 agent / model 类型。OpenAI 兼容接口可作为模型对照，但不会被标记成完整金融 Agent。输出不得泄露参赛身份。</p></div></section><section><span className="document-number">03</span><div><h2>运行、核对、发布</h2><p>平台并行调用两方，保留成功与失败，不自动重跑挑选答案。运营审核身份泄露与材料公开权利后，结果才能进入公众盲评。</p><button className="secondary" onClick={() => { const content = JSON.stringify([{ participant: { id: "your-agent", name: "Your Agent", version: "v1", kind: "agent" }, protocol: "arena-v1", endpoint: "https://your-service.example/arena", api_key_env: "YOUR_AGENT_API_KEY" }], null, 2); const url = URL.createObjectURL(new Blob([content], { type: "application/json" })); const a = document.createElement("a"); a.href = url; a.download = "arena-agents.example.json"; a.click(); URL.revokeObjectURL(url); }}><ArrowDownToLine size={16} />下载接入配置模板</button></div></section></div>}
        </>}
        <footer className="page-footer"><span>FinArena <span className="footer-dot">·</span> 金融 Agent 评测</span><button className="text-button" onClick={() => navigate("method")}><ShieldCheck size={13} />透明评测口径<ArrowUpRight size={12} /></button></footer>
      </main>
    </div>
    {toast && <div className="toast" role="status"><CheckCircle2 size={17} />{toast}</div>}
    {modal && <Modal title={{ join: "加入正式评审", question: "提交研究题目", evidence: "共同参考材料", report: "报告评测问题" }[modal]} onClose={() => { if (!busy) setModal(null); }}>
      {modalError && <p className="modal-error" role="alert">{modalError}</p>}
      {modal === "join" && (boot?.reviewer ? <div className="joined-state"><ShieldCheck size={35} /><h3>{boot.reviewer}</h3><p>邀请评审身份已绑定当前浏览器。</p><button className="primary" onClick={() => setModal(null)}>返回评测<ArrowRight size={16} /></button></div> : <form onSubmit={async event => { event.preventDefault(); const code = String(new FormData(event.currentTarget).get("code")); setBusy(true); setModalError(""); try { await api("join", { code }); setBoot(await bootstrap()); setModal(null); notify("已加入正式评审；历史体验票不会转为正式票"); } catch (err) { setModalError(err instanceof Error ? err.message : "加入失败"); } finally { setBusy(false); } }}><div className="modal-lead"><KeyRound size={24} /><p>正式票需要运营方签发的一次性邀请码。游客可直接参加体验场。</p></div><label className="field">邀请码<input name="code" required minLength={10} maxLength={200} autoComplete="off" placeholder="输入评审邀请码" /></label><div className="form-note">邀请码绑定当前浏览器，有效会话为 30 天。不上传姓名或账户资料。</div><button className="primary wide" disabled={busy}>{busy ? <LoaderCircle className="spin" size={16} /> : <ShieldCheck size={16} />}确认加入</button></form>)}
      {modal === "question" && <form onSubmit={async event => { event.preventDefault(); const form = new FormData(event.currentTarget); setBusy(true); setModalError(""); try { await api("questions", { question: form.get("question"), category: form.get("category"), consent: form.get("consent") === "on" }); setModal(null); notify("题目已进入运营审核队列，尚未调用 Agent"); if (view === "history") setHistory(await api<History>("history")); } catch (err) { setModalError(err instanceof Error ? err.message : "提交失败"); } finally { setBusy(false); } }}><label className="field">研究类型<select name="category" defaultValue={category || "financial"}>{Object.entries(categories).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label><label className="field">研究问题<textarea name="question" rows={5} minLength={12} maxLength={2000} required placeholder="例如：同一行业两家公司的现金流质量，应该从哪些财务指标比较？" /></label><label className="consent"><input type="checkbox" name="consent" required /><span>题目不含个人、账户或机构保密信息；同意审核后用于公开匿名评测。</span></label><button className="primary wide" disabled={busy}>{busy ? <LoaderCircle className="spin" size={16} /> : <MessageSquarePlus size={16} />}提交题目</button></form>}
      {modal === "evidence" && <div className="evidence-documents">{assignment?.evidence.map((evidence, index) => <section key={index}><div className="evidence-title"><FileText size={20} /><h3>{evidence.title}</h3></div><p>{evidence.content}</p><footer>来源：{evidence.source}</footer></section>)}</div>}
      {modal === "report" && <form onSubmit={async event => { event.preventDefault(); if (!assignment) return; const form = new FormData(event.currentTarget); setBusy(true); setModalError(""); try { await api(`assignments/${assignment.id}/report`, { reason: form.get("reason"), detail: form.get("detail") }); setModal(null); notify("问题已提交，等待运营复核"); } catch (err) { setModalError(err instanceof Error ? err.message : "提交失败"); } finally { setBusy(false); } }}><label className="field">问题类型<select name="reason"><option value="identity">回答泄露参赛身份</option><option value="unsupported">结论缺乏证据</option><option value="numbers">数字或计算错误</option><option value="other">其他问题</option></select></label><label className="field">补充说明<textarea name="detail" rows={4} maxLength={1000} placeholder="指出相关句子或计算口径" /></label><button className="primary wide" disabled={busy}><Flag size={16} />提交复核</button></form>}
    </Modal>}
  </div>;
}
