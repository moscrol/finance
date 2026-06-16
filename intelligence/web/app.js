"use strict";

const state = {
  user: "default",
  profile: { focus_themes: [], watchlist: [] },
  affinity: [],
};

// ---- tiny helpers --------------------------------------------------------- //
function $(sel) { return document.querySelector(sel); }

function el(tag, props, children) {
  const node = document.createElement(tag);
  if (props) for (const [k, v] of Object.entries(props)) {
    if (k === "class") node.className = v;
    else if (k === "text") node.textContent = v;
    else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v);
  }
  for (const c of [].concat(children || [])) {
    if (c == null) continue;
    node.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
  }
  return node;
}

async function api(path, opts) {
  const res = await fetch(path, opts);
  const data = await res.json().catch(() => ({ error: `HTTP ${res.status}` }));
  if (!res.ok || data.error) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

let toastTimer = null;
function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("show"), 1900);
}

function uq(extra) {
  const p = new URLSearchParams({ user: state.user });
  if (extra) for (const [k, v] of Object.entries(extra)) p.set(k, v);
  return p.toString();
}

// ---- association extraction (which 题材/个股 a question is about) --------- //
function stockSet() {
  const s = new Set((state.profile.watchlist || []).map(String));
  for (const a of state.affinity) if (a.kind === "stock") s.add(a.label);
  return s;
}
function themeSet() {
  const s = new Set((state.profile.focus_themes || []).map(String));
  for (const a of state.affinity) if (a.kind === "theme") s.add(a.label);
  return s;
}
function classify(token) {
  return stockSet().has(token) ? "stock" : "theme";
}
function matchedTerms(text) {
  const out = [];
  const seen = new Set();
  for (const term of [...themeSet(), ...stockSet()]) {
    if (term && term.length >= 2 && text.includes(term) && !seen.has(term)) {
      seen.add(term);
      out.push(term);
    }
  }
  return out;
}
function splitTerms(raw) {
  return (raw || "").split(/[,，\s]+/).map(s => s.trim()).filter(Boolean);
}
function partition(terms) {
  const themes = [], stocks = [];
  for (const t of terms) (classify(t) === "stock" ? stocks : themes).push(t);
  return { themes, stocks };
}

// ---- record interaction (the auto-record surface) ------------------------- //
async function record({ kind, terms, question, rating }) {
  const { themes, stocks } = partition(terms || []);
  const body = { user: state.user, kind, themes, stocks };
  if (question) body.question = question;
  if (rating != null) body.rating = rating;
  const data = await api("/api/interaction", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  state.affinity = data.affinity || state.affinity;
  const label = themes.concat(stocks).join("、") || "（仅问题文本）";
  toast(`已记 ${kind} · ${label}` + ((!themes.length && !stocks.length) ? "（未关联题材/个股，亲和度不变）" : ""));
  if ($("#tab-affinity").classList.contains("active")) loadAffinity();
}

// ---- foresight ------------------------------------------------------------ //
async function loadForesight() {
  $("#foresight-meta").textContent = "加载中…";
  $("#cards").innerHTML = "";
  let data;
  try { data = await api("/api/foresight?" + uq()); }
  catch (e) { $("#foresight-meta").textContent = "加载失败：" + e.message; return; }
  renderForesight(data);
}

function renderForesight(data) {
  const llm = data.llm_used ? `LLM=${data.llm_provider || "on"}` : "LLM=降级(摘要)";
  $("#foresight-meta").innerHTML =
    `盘面日期 <b>${data.trade_date || "—"}</b> · 画像 <b>${data.profile_name || "—"}</b> · ${llm}` +
    ` · 反馈载入 <b>${data.interactions_loaded || 0}</b> · 亲和命中 <b>${data.affinity_applied || 0}</b>`;
  const cards = $("#cards");
  cards.innerHTML = "";
  (data.warnings || []).forEach(w => cards.appendChild(el("div", { class: "warn-box", text: w })));

  if (!data.questions || !data.questions.length) {
    cards.appendChild(el("div", { class: "empty", text: "暂无生成的问题（多为未配置 LLM）。以下是上下文摘要：" }));
    (data.context_digest || []).forEach(d => cards.appendChild(el("div", { class: "card" }, el("div", { class: "kv", text: d }))));
    return;
  }
  data.questions.forEach(q => cards.appendChild(questionCard(q)));
}

function questionCard(q) {
  const card = el("div", { class: "card" });
  card.appendChild(el("div", { class: "q", text: q.question }));
  if (q.rationale) card.appendChild(el("div", { class: "rationale", text: q.rationale }));

  const chips = el("div", { class: "chips" });
  (q.domains || []).forEach(d => chips.appendChild(el("span", { class: "chip", text: d })));
  if (q.affinity_boost > 0) chips.appendChild(el("span", { class: "chip boost", text: `反馈加成 +${q.affinity_boost}` }));
  if (chips.children.length) card.appendChild(chips);

  if (q.horizon) card.appendChild(el("div", { class: "kv" }, [el("b", { text: "时间窗：" }), q.horizon]));
  if (q.leading_indicator) card.appendChild(el("div", { class: "kv" }, [el("b", { text: "先行指标：" }), q.leading_indicator]));
  if (q.affinity_reasons && q.affinity_reasons.length)
    card.appendChild(el("div", { class: "kv" }, [el("b", { text: "命中：" }), q.affinity_reasons.join("、")]));

  // 关联题材/个股：预填命中项，反馈按钮即用此输入
  const assocInput = el("input", { type: "text", value: matchedTerms(q.question).join(", "), placeholder: "关联题材/个股（逗号分隔）" });
  card.appendChild(el("div", { class: "assoc" }, [el("label", { text: "关联" }), assocInput]));

  const terms = () => splitTerms(assocInput.value);
  const btn = (text, kind) => el("button", { class: "ghost", onclick: () => record({ kind, terms: terms(), question: q.question }).catch(e => toast("失败：" + e.message)) }, text);

  const actions = el("div", { class: "actions" }, [
    btn("想深挖", "click"), btn("关注", "follow"), btn("置顶", "pin"), btn("不看了", "dismiss"),
  ]);
  const stars = el("span", { class: "stars" });
  for (let i = 1; i <= 5; i++) {
    const star = el("span", { class: "star", title: `打 ${i} 分`, text: "★" });
    star.addEventListener("mouseenter", () => [...stars.children].forEach((s, j) => s.classList.toggle("on", j < i)));
    star.addEventListener("mouseleave", () => [...stars.children].forEach(s => s.classList.remove("on")));
    star.addEventListener("click", () => record({ kind: "rate", rating: i, terms: terms(), question: q.question }).catch(e => toast("失败：" + e.message)));
    stars.appendChild(star);
  }
  actions.appendChild(stars);
  card.appendChild(actions);
  return card;
}

// ---- affinity & records --------------------------------------------------- //
async function loadAffinity() {
  let data;
  try { data = await api("/api/interactions?" + uq({ window: 200 })); }
  catch (e) { toast("加载失败：" + e.message); return; }
  state.affinity = data.affinity || [];
  renderAffinity(data);
}

function renderAffinity(data) {
  const list = $("#affinity-list");
  list.innerHTML = "";
  if (!data.affinity.length) { list.appendChild(el("div", { class: "empty", text: "还没有反馈。去「猜你想问」点几下，或在上面记一笔。" })); }
  const max = Math.max(1, ...data.affinity.map(a => Math.abs(a.score)));
  data.affinity.forEach(a => {
    const pos = a.score >= 0;
    const row = el("div", { class: "aff-row" }, [
      el("span", { class: "aff-kind", text: a.kind === "stock" ? "个股" : "题材" }),
      el("span", { class: "aff-label", text: a.label }),
      el("span", { class: `aff-bar ${pos ? "pos" : "neg"}`, style: `width:${Math.round(Math.abs(a.score) / max * 220)}px` }),
      el("span", { class: "aff-score", text: (pos ? "+" : "") + a.score }),
    ]);
    list.appendChild(row);
  });

  const recs = $("#records-list");
  recs.innerHTML = "";
  if (!data.records.length) recs.appendChild(el("div", { class: "empty", text: "—" }));
  data.records.forEach(r => {
    const terms = (r.themes || []).concat(r.stocks || []).join("、");
    const wpos = (r.weight || 0) >= 0;
    recs.appendChild(el("div", { class: "rec" }, [
      el("span", { class: "ts", text: (r.ts || "").replace("T", " ") + "  " }),
      el("b", { text: r.kind }),
      el("span", { class: wpos ? "w-pos" : "w-neg", text: ` (${wpos ? "+" : ""}${r.weight}) ` }),
      terms ? document.createTextNode("· " + terms) : null,
      r.rating != null ? el("span", { class: "ts", text: "  ★" + r.rating }) : null,
    ]));
  });
}

async function submitQuick() {
  const kind = $("#qk-kind").value;
  const terms = splitTerms($("#qk-theme").value).concat(splitTerms($("#qk-stock").value));
  const ratingRaw = $("#qk-rating").value;
  const rating = ratingRaw ? Number(ratingRaw) : null;
  // 注意：题材/个股按各自输入框直接归类，避免误判
  const themes = splitTerms($("#qk-theme").value);
  const stocks = splitTerms($("#qk-stock").value);
  try {
    const body = { user: state.user, kind, themes, stocks };
    if (rating != null) body.rating = rating;
    const data = await api("/api/interaction", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    state.affinity = data.affinity || state.affinity;
    toast(`已记 ${kind}`);
    $("#qk-theme").value = ""; $("#qk-stock").value = ""; $("#qk-rating").value = "";
    loadAffinity();
  } catch (e) { toast("失败：" + e.message); }
}

// ---- profile -------------------------------------------------------------- //
async function loadProfile() {
  let data;
  try { data = await api("/api/profile?" + uq()); }
  catch (e) { $("#profile-meta").textContent = "加载失败：" + e.message; return; }
  state.profile = data.profile || { focus_themes: [], watchlist: [] };
  const p = data.profile || {};
  $("#profile-meta").innerHTML = `用户 <b>${data.user}</b> · 风格 <b>${p.style || "—"}</b> · 周期 <b>${p.horizon || "—"}</b>`;
  const warn = $("#profile-warn"); warn.innerHTML = "";
  (data.warnings || []).forEach(w => warn.appendChild(el("div", { class: "warn-box", text: w })));
  renderChips("#profile-themes", p.focus_themes || []);
  renderChips("#profile-watch", p.watchlist || []);
}

function renderChips(sel, items) {
  const box = $(sel); box.innerHTML = "";
  if (!items.length) box.appendChild(el("span", { class: "kv", text: "—" }));
  items.forEach(it => box.appendChild(el("span", { class: "chip", text: it })));
}

async function refreshProfile(apply) {
  const out = $("#refresh-result");
  out.innerHTML = "";
  out.appendChild(el("div", { class: "kv", text: apply ? "正在派生并应用…" : "正在派生（预览）…" }));
  try {
    const data = await api("/api/refresh-profile?" + uq({ apply: apply ? "1" : "0" }), { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
    out.innerHTML = "";
    (data.warnings || []).forEach(w => out.appendChild(el("div", { class: "warn-box", text: w })));
    out.appendChild(el("pre", { class: "answer", text: data.answer || "(无输出)" }));
    toast(apply ? "已应用派生候选" : "已生成 diff 预览");
    if (apply) loadProfile();
  } catch (e) { out.innerHTML = ""; out.appendChild(el("div", { class: "warn-box", text: "失败：" + e.message })); }
}

// ---- strategy overlay ----------------------------------------------------- //
async function loadStrategy() {
  let data;
  try { data = await api("/api/strategy?" + uq()); }
  catch (e) { $("#strategy-meta").textContent = "加载失败：" + e.message; return; }
  const m = data.meta || {};
  $("#strategy-meta").innerHTML = `用户 <b>${data.user}</b> · baseline <b>${m.base_version || "—"}</b> · overlay <b>${m.overlay_applied ? (m.overlay_version || "?") : "未启用"}</b>` +
    (m.overlay_sections && m.overlay_sections.length ? ` · 覆盖段 <b>${m.overlay_sections.join(", ")}</b>` : "");
  $("#allowed-sections").textContent = (data.allowed_sections || []).join(", ");
  $("#overlay-text").value = data.overlay_raw ? JSON.stringify(data.overlay_raw, null, 2) : "";
  $("#overlay-text").dataset.allowed = JSON.stringify(data.allowed_sections || []);
  $("#effective-params").textContent = JSON.stringify(data.params || {}, null, 2);
  (m.warnings || []).forEach(w => toast(w));
}

async function saveOverlay() {
  let parsed;
  try { parsed = JSON.parse($("#overlay-text").value || "{}"); }
  catch (e) { toast("JSON 解析失败：" + e.message); return; }
  try {
    const data = await api("/api/strategy?" + uq(), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ user: state.user, overlay: parsed }) });
    toast("已保存 overlay v" + (data.meta && data.meta.overlay_version));
    (data.warnings || []).forEach(w => toast(w));
    loadStrategy();
  } catch (e) { toast("保存失败：" + e.message); }
}

function insertSkeleton() {
  const allowed = JSON.parse($("#overlay-text").dataset.allowed || "[]");
  const skel = { _overlay_version: 1 };
  (allowed.length ? allowed : ["strategy1"]).forEach(s => { skel[s] = {}; });
  $("#overlay-text").value = JSON.stringify(skel, null, 2);
}

// ---- shell ---------------------------------------------------------------- //
function switchTab(name) {
  document.querySelectorAll("nav button").forEach(b => b.classList.toggle("active", b.dataset.tab === name));
  document.querySelectorAll(".panel").forEach(p => p.classList.toggle("active", p.id === "tab-" + name));
  if (name === "affinity") loadAffinity();
  else if (name === "profile") loadProfile();
  else if (name === "strategy") loadStrategy();
}

async function reloadAll() {
  await loadProfile();        // profile first so association/classify works
  await loadAffinity();
  await loadForesight();
}

async function init() {
  document.querySelectorAll("nav button").forEach(b => b.addEventListener("click", () => switchTab(b.dataset.tab)));
  $("#reload").addEventListener("click", reloadAll);
  $("#regen").addEventListener("click", loadForesight);
  $("#qk-submit").addEventListener("click", submitQuick);
  $("#refresh-diff").addEventListener("click", () => refreshProfile(false));
  $("#refresh-apply").addEventListener("click", () => refreshProfile(true));
  $("#overlay-save").addEventListener("click", saveOverlay);
  $("#overlay-skeleton").addEventListener("click", insertSkeleton);

  const sel = $("#user");
  sel.addEventListener("change", () => { state.user = sel.value; reloadAll(); });
  try {
    const data = await api("/api/users");
    const health = await api("/api/health");
    state.user = health.default_user || "default";
    (data.users || ["default"]).forEach(u => sel.appendChild(el("option", { value: u, text: u })));
    sel.value = state.user;
  } catch (e) {
    sel.appendChild(el("option", { value: "default", text: "default" }));
  }
  reloadAll();
}

document.addEventListener("DOMContentLoaded", init);
