/* MindBridge device UI. Plain JS, no build step, no network beyond 127.0.0.1. */
"use strict";

const T = {
  talk: { en: "Tap to speak", vi: "Nhấn để nói", ko: "눌러서 말하기", zh: "点击说话" },
  listening: { en: "Listening… tap to finish", vi: "Đang nghe… nhấn để dừng", ko: "듣는 중… 눌러서 끝내기", zh: "正在听…点击结束" },
  working: { en: "Translating…", vi: "Đang dịch…", ko: "번역 중…", zh: "翻译中…" },
  ask: { en: "Ask about the line", vi: "Hỏi về dây chuyền", ko: "라인에 대해 묻기", zh: "询问生产线情况" },
  answer: { en: "Answer", vi: "Trả lời", ko: "대답하기", zh: "回答" },
};
const tr = (key, lang) => (T[key] && (T[key][lang] || T[key].en)) || key;
const KIND = {
  instruction: "Instruction", decision: "Decision", issue: "Issue", commitment: "Commitment",
  procedure: "Procedure", exception: "Exception", outcome: "Outcome", note: "Note",
};
const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const S = { status: null, sides: null, state: "idle", activeSide: null, mode: "talk", memoryId: null, rec: null };

/* ---------------- audio playback queue ---------------- */
const playQ = [];
let playing = false;
function enqueueAudio(url) { playQ.push(url); if (!playing) playNext(); }
function playNext() {
  const url = playQ.shift();
  if (!url) { playing = false; return; }
  playing = true;
  const a = new Audio(url);
  a.onended = a.onerror = () => playNext();
  a.play().catch(() => playNext());
}
async function sayText(text, lang) {
  const r = await fetch("/api/say", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text, lang }) });
  if (r.status === 200) enqueueAudio(URL.createObjectURL(await r.blob()));
}

/* ---------------- websocket ---------------- */
function connect() {
  const ws = new WebSocket(`ws://${location.host}/ws`);
  ws.onmessage = (e) => handle(JSON.parse(e.data));
  ws.onclose = () => setTimeout(connect, 1000);
}
function handle(ev) {
  switch (ev.type) {
    case "hello": applyStatus(ev.status); refreshMemory(); break;
    case "state": setState(ev.state, ev.side, ev.mode); break;
    case "turn": renderTurn(ev.turn, ev.side, ev.has_audio); break;
    case "turn_update": updateTurn(ev.turn); break;
    case "memory": renderMemory(ev.items, ev.light); break;
    case "error": toast(ev.message); break;
  }
}

/* ---------------- status / pairs ---------------- */
function applyStatus(st) {
  S.status = st; S.sides = st.sides;
  const pairs = $("#pairs");
  pairs.innerHTML = "";
  for (const p of st.pairs) {
    const [a, b] = p.split("-");
    const btn = document.createElement("button");
    btn.textContent = `${nativeName(a)} ⇄ ${nativeName(b)}`;
    btn.setAttribute("aria-pressed", String(p === st.pair));
    btn.onclick = () => setPair(p);
    pairs.appendChild(btn);
  }
  for (const k of ["a", "b"]) {
    const side = st.sides[k], el = $(`#side-${k}`);
    $("[data-role]", el).textContent = side.role;
    $("[data-lang]", el).textContent = side.native;
    $("[data-cta]", el).textContent = tr("talk", side.lang);
    $("[data-ask]", el).textContent = tr("ask", side.lang);
    $("[data-cta]", el).lang = side.lang;
  }
  const sel = $("#typer-side");
  sel.innerHTML = ["a", "b"].map((k) => `<option value="${k}">${esc(st.sides[k].role)} (${esc(st.sides[k].native)})</option>`).join("");
  const net = st.offline.network, chip = $("#chip-net");
  const online = net.has_default_route || net.any_external_ip;
  chip.className = "chip " + (online ? "warn" : "ok");
  chip.textContent = online ? "Network is on — turn it off for the demo" : "Offline: no network";
  const asr = st.models.find((m) => m.stage === "Speech recognition");
  const npu = $("#chip-npu");
  npu.className = "chip " + (asr && asr.unit === "NPU" ? "ok" : "warn");
  npu.textContent = asr && asr.unit === "NPU" ? "Speech on NPU" : "Speech on CPU";
  npu.title = asr ? `${asr.model}${asr.note ? " — " + asr.note : ""}` : "";
  setLight(st.light);
}
function nativeName(code) { return { vi: "Tiếng Việt", en: "English", ko: "한국어", zh: "中文" }[code] || code; }
async function setPair(p) {
  await fetch("/api/pair", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ pair: p }) });
  applyStatus(await (await fetch("/api/status")).json());
}

/* ---------------- talking ---------------- */
function setState(state, side, mode) {
  S.state = state;
  for (const k of ["a", "b"]) {
    const el = $(`#side-${k}`), lang = S.sides ? S.sides[k].lang : "en";
    el.classList.toggle("listening", state === "listening" && side === k);
    el.classList.toggle("processing", state === "processing" && side === k);
    const cta = $("[data-cta]", el);
    cta.textContent = state === "listening" && side === k ? tr("listening", lang)
      : state === "processing" && side === k ? tr("working", lang) : tr("talk", lang);
  }
  S.activeSide = state === "idle" ? null : side;
}
async function start(side, mode = "talk", memoryId = null) {
  if (S.state === "listening") return stop();
  if (S.state === "processing") return;
  S.mode = mode; S.memoryId = memoryId;
  if (S.status && S.status.mic.available) {
    const r = await post("/api/listen/start", { side, mode, memory_id: memoryId });
    if (!r.ok && r.error) toast(r.error);
  } else {
    browserRecord(side, mode, memoryId);
  }
}
async function stop() {
  if (S.rec) return S.rec.stop();
  await post("/api/listen/stop", {});
}
async function post(url, body) {
  const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  return r.json().catch(() => ({}));
}

/* Browser-microphone fallback (used when the device has no PortAudio input). */
async function browserRecord(side, mode, memoryId) {
  let stream;
  try { stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } }); }
  catch (e) { toast("No microphone found. Plug in a USB microphone or type a line below."); return; }
  const ctx = new AudioContext();
  const src = ctx.createMediaStreamSource(stream);
  const proc = ctx.createScriptProcessor(4096, 1, 1);
  const chunks = []; let heard = false, silentFor = 0; const t0 = performance.now();
  setState("listening", side, mode);
  const finish = async () => {
    proc.disconnect(); src.disconnect(); stream.getTracks().forEach((t) => t.stop());
    const rate = ctx.sampleRate; await ctx.close(); S.rec = null;
    const wav = encodeWav(chunks, rate);
    const fd = new FormData();
    fd.append("file", new Blob([wav], { type: "audio/wav" }), "speech.wav");
    fd.append("side", side); fd.append("mode", mode); fd.append("memory_id", memoryId ?? "");
    await fetch("/api/upload", { method: "POST", body: fd });
  };
  proc.onaudioprocess = (e) => {
    const x = new Float32Array(e.inputBuffer.getChannelData(0)); chunks.push(x);
    let s = 0; for (const v of x) s += v * v; const rms = Math.sqrt(s / x.length);
    if (rms > 0.02) { heard = true; silentFor = 0; } else silentFor += x.length / ctx.sampleRate;
    if ((heard && silentFor > 1.0) || performance.now() - t0 > 25000) { if (S.rec) S.rec.stop(); }
  };
  src.connect(proc); proc.connect(ctx.destination);
  let stopped = false;
  S.rec = { stop: () => { if (!stopped) { stopped = true; finish(); } } };
}
function encodeWav(chunks, rate) {
  const n = chunks.reduce((a, c) => a + c.length, 0);
  const buf = new ArrayBuffer(44 + n * 2), v = new DataView(buf);
  const w = (o, s) => [...s].forEach((c, i) => v.setUint8(o + i, c.charCodeAt(0)));
  w(0, "RIFF"); v.setUint32(4, 36 + n * 2, true); w(8, "WAVE"); w(12, "fmt "); v.setUint32(16, 16, true);
  v.setUint16(20, 1, true); v.setUint16(22, 1, true); v.setUint32(24, rate, true); v.setUint32(28, rate * 2, true);
  v.setUint16(32, 2, true); v.setUint16(34, 16, true); w(36, "data"); v.setUint32(40, n * 2, true);
  let o = 44; for (const c of chunks) for (const s of c) { v.setInt16(o, Math.max(-1, Math.min(1, s)) * 32767, true); o += 2; }
  return buf;
}

/* ---------------- conversation ---------------- */
function sideOfLang(lang) { if (!S.sides) return "a"; return S.sides.a.lang === lang ? "a" : "b"; }
function latencyBar(t, unit) {
  const pre = t.preprocess || 0, asr = t.asr || 0, mt = t.mt || 0, tts = t.tts || 0;
  const total = pre + asr + mt + tts;
  if (!total) return "";
  const pct = (x) => `${(100 * x / total).toFixed(1)}%`;
  const ms = (x) => `${Math.round(x)} ms`;
  const parts = [];
  if (asr) parts.push(`recognise ${ms(asr)} on ${unit || "CPU"}`);
  if (mt) parts.push(`translate ${ms(mt)}`);
  if (tts) parts.push(`voice ${ms(tts)}`);
  return `<div class="lat" title="Processing time by stage">
      <span class="s-pre" style="width:${pct(pre)}"></span><span class="s-asr" style="width:${pct(asr)}"></span>
      <span class="s-mt" style="width:${pct(mt)}"></span><span class="s-tts" style="width:${pct(tts)}"></span></div>
    <div class="lat-legend">${parts.join(", ")}; ${ms(total)} in total</div>`;
}
function hideEmpty() { const e = $("#empty"); if (e) e.remove(); }
function scrollLog() { const log = $("#log"); log.scrollTop = log.scrollHeight; }
function asrUnit() { const a = S.status && S.status.models.find((m) => m.stage === "Speech recognition"); return a ? a.unit : "CPU"; }

function renderTurn(turn, side, hasAudio) {
  hideEmpty();
  const log = $("#log");
  const time = new Date(turn.created_at * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  if (turn.mode === "verify") return renderVerifyResult(turn);
  const el = document.createElement("div");
  el.id = `turn-${turn.id}`;
  if (turn.mode === "ask") {
    el.className = "turn mb";
    el.innerHTML = `<div class="meta">${time}, question to MindBridge</div>
      <div class="src" lang="${turn.speaker_lang}">${esc(turn.source_text)}</div>
      <div class="tgt" lang="${turn.speaker_lang}">${esc(turn.answer)}</div>
      ${hasAudio ? `<button class="replay">Play again</button>` : ""}`;
  } else {
    if (!turn.source_text) { toast("Didn't catch that. Tap and speak again, a little closer to the mic."); return; }
    el.className = `turn from-${side}`;
    el.innerHTML = `<div class="meta">${time}, ${esc(turn.speaker_role)} said</div>
      <div class="src" lang="${turn.speaker_lang}">${esc(turn.source_text)}</div>
      <div class="tgt" lang="${turn.listener_lang}">${esc(turn.translation)}</div>
      ${hasAudio ? `<button class="replay">Play again</button>` : ""}
      ${latencyBar(turn.timings_ms, asrUnit())}`;
  }
  const url = `/api/audio/${turn.id}.wav`;
  const rp = $(".replay", el); if (rp) rp.onclick = () => enqueueAudio(url);
  log.appendChild(el);
  if (hasAudio) enqueueAudio(url);
  scrollLog();
}
function updateTurn(turn) {
  const anchor = $(`#turn-${turn.id}`);
  const log = $("#log");
  let after = anchor;
  const insert = (node) => { if (after && after.parentNode) { after.after(node); after = node; } else log.appendChild(node); };
  for (const a of turn.alerts || []) {
    const div = document.createElement("div");
    div.className = `alert ${a.level}`;
    const own = a.text[turn.listener_lang] || a.text_en, other = a.text[turn.speaker_lang];
    div.innerHTML = `<span lang="${turn.listener_lang}">${esc(own)}</span>${other && other !== own ? `<span class="sub" lang="${turn.speaker_lang}">${esc(other)}</span>` : ""}`;
    insert(div);
    if (a.level === "red") sayText(own, turn.listener_lang);
  }
  if (turn.answer) {
    const div = document.createElement("div");
    div.className = "turn mb";
    div.innerHTML = `<div class="meta">MindBridge answers from memory</div><div class="tgt" lang="${turn.speaker_lang}">${esc(turn.answer)}</div>`;
    insert(div); sayText(turn.answer, turn.speaker_lang);
  }
  if (turn.verification) {
    const v = turn.verification, lside = sideOfLang(v.lang);
    const div = document.createElement("div");
    div.className = "verify"; div.id = `verify-${v.memory_id}`;
    div.innerHTML = `<div class="meta">Check understanding (${esc(S.sides[lside].role)})</div>
      <div class="q" lang="${v.lang}">${esc(v.question)}</div>
      <button lang="${v.lang}">${tr("answer", v.lang)}</button><div class="result"></div>`;
    $("button", div).onclick = () => start(lside, "verify", v.memory_id);
    insert(div); sayText(v.question, v.lang);
  }
  scrollLog();
}
function renderVerifyResult(turn) {
  const v = turn.verification || {};
  const card = $(`#verify-${v.memory_id}`);
  const msg = `${esc(turn.source_text)} — ${esc(turn.answer)}`;
  if (card) {
    const r = $(".result", card);
    r.className = "result " + (v.ok ? "ok" : "no");
    r.innerHTML = msg;
  } else toast(turn.answer);
  sayText(turn.answer, turn.speaker_lang);
}

/* ---------------- memory + badge ---------------- */
async function refreshMemory() {
  const r = await (await fetch("/api/memory")).json();
  renderMemory(r.items, r.light);
}
let lastBadge = "";
function renderMemory(items, light) {
  setLight(light);
  const list = $("#mem");
  const order = { active: 0, held: 1, info: 2, resolved: 3, superseded: 4 };
  const sorted = [...items].sort((x, y) => (order[x.status] - order[y.status]) || (y.id - x.id));
  list.innerHTML = sorted.map((m) => {
    const cls = [m.polarity === "forbid" ? "forbid" : m.kind === "instruction" ? "require" : m.kind, m.status].join(" ");
    const ver = m.verified !== "n/a" ? `<span class="state ${m.verified}">${{ pending: "Awaiting check", confirmed: "Understood", failed: "Re-explain" }[m.verified]}</span>` : "";
    const status = { resolved: "Cleared", superseded: "Replaced", held: "On hold", info: "", active: "" }[m.status];
    return `<li class="${cls}"><div class="top"><span>${KIND[m.kind] || m.kind}, ${m.time}</span><span>${status}</span></div>
      ${m.subject ? `<div class="subj">${esc(m.subject)}</div>` : ""}<div class="txt">${esc(m.text_en)}</div>${ver}</li>`;
  }).join("") || `<li class="muted">Nothing yet. Instructions, issues and decisions appear here as people speak.</li>`;
  const focus = sorted.find((m) => m.status === "active" && m.polarity === "forbid")
    || sorted.find((m) => m.status === "active" && m.kind === "issue");
  const lines = focus ? focus.card : ["ALL CLEAR", "NO ACTIVE", "RESTRICTIONS"];
  const key = lines.join("|");
  const eink = $("#eink");
  eink.innerHTML = lines.map((l, i) => `<div class="eink-${i + 1}">${esc(l)}</div>`).join("");
  if (key !== lastBadge) { eink.classList.remove("flash"); void eink.offsetWidth; eink.classList.add("flash"); lastBadge = key; }
}
function setLight(light) { $("#led").className = `led ${light || ""}`; }

/* ---------------- dialogs ---------------- */
async function showDetails() {
  const st = await (await fetch("/api/status")).json();
  applyStatus(st);
  const rows = st.models.map((m) => `<tr><td>${esc(m.stage)}</td><td>${esc(m.model)}</td><td>${esc(m.unit)}</td><td>${m.size_mb} MB</td></tr>`).join("");
  const total = st.models.reduce((a, m) => a + m.size_mb, 0).toFixed(0);
  const net = st.offline.network;
  $("#details-body").innerHTML = `
    <table><tr><th>Stage</th><th>Model</th><th>Runs on</th><th>Size</th></tr>${rows}
      <tr><th colspan="3">Total model size</th><th>${total} MB</th></tr></table>
    <table>
      <tr><th>Device</th><td>${esc(st.device.soc || st.device.machine)} (${esc(st.device.platform)}), ${st.device.total_ram_mb} MB RAM</td></tr>
      <tr><th>Process memory</th><td>${st.memory_mb.rss} MB now, ${st.memory_mb.peak} MB peak</td></tr>
      <tr><th>Model load time</th><td>${Object.entries(st.load_ms).map(([k, v]) => `${k} ${v} ms`).join(", ")}</td></tr>
      <tr><th>Network</th><td>${net.has_default_route ? "Default route present" : "No default route"}; ${net.any_external_ip ? "an interface has an IP address" : "no interface has an external IP"}. Outbound blocking ${st.offline.strict_guard ? "on" : "off"}; ${st.offline.blocked_attempts} attempts blocked.</td></tr>
      <tr><th>Microphone</th><td>${st.mic.available ? "Device microphone" : "Browser microphone (" + esc(st.mic.error) + ")"}</td></tr>
    </table>
    <pre>${esc(JSON.stringify(net, null, 2))}</pre>`;
  $("#details").showModal();
}
async function showHandover() {
  const a = S.sides.a.lang, b = S.sides.b.lang;
  $("#handover-body").innerHTML = `<p class="muted">Preparing…</p>`;
  $("#handover").showModal();
  const [hb, ha] = await Promise.all([fetch(`/api/handover?lang=${b}`).then((r) => r.json()), fetch(`/api/handover?lang=${a}`).then((r) => r.json())]);
  $("#handover-body").innerHTML = `
    <p class="handover-text" lang="${b}">${esc(hb.text)}</p><p><button type="button" id="ho-play-b">Read aloud (${nativeName(b)})</button></p>
    <hr><p class="handover-text" lang="${a}">${esc(ha.text)}</p><p><button type="button" id="ho-play-a">Read aloud (${nativeName(a)})</button></p>`;
  $("#ho-play-b").onclick = () => sayText(hb.text, b);
  $("#ho-play-a").onclick = () => sayText(ha.text, a);
}
let toastTimer;
function toast(msg) {
  let t = $("#toast");
  if (!t) { t = document.createElement("div"); t.id = "toast"; t.className = "alert amber"; t.style.cssText = "position:fixed;left:50%;bottom:20px;transform:translateX(-50%);z-index:9"; document.body.appendChild(t); }
  t.textContent = msg; t.hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => (t.hidden = true), 4000);
}

/* ---------------- wiring ---------------- */
document.querySelectorAll(".talk").forEach((b) => (b.onclick = () => start(b.dataset.side, "talk")));
document.querySelectorAll("[data-ask]").forEach((b) => (b.onclick = () => start(b.dataset.side, "ask")));
$("#btn-handover").onclick = showHandover;
$("#btn-details").onclick = showDetails;
$("#btn-clear").onclick = async () => { await post("/api/memory/clear", {}); refreshMemory(); };
$("#typer").onsubmit = async (e) => {
  e.preventDefault();
  const text = $("#typer-text").value.trim(); if (!text) return;
  await post("/api/text", { side: $("#typer-side").value, text, mode: "talk" });
  $("#typer-text").value = "";
};
document.addEventListener("keydown", (e) => {
  if (e.target.tagName === "INPUT" || document.querySelector("dialog[open]")) return;
  if (["1", "PageUp", "ArrowLeft"].includes(e.key)) { e.preventDefault(); start("a"); }
  else if (["2", "PageDown", "ArrowRight"].includes(e.key)) { e.preventDefault(); start("b"); }
  else if (e.key === " " || e.key === "Escape") { if (S.state === "listening") { e.preventDefault(); stop(); } }
  else if (e.key.toLowerCase() === "h") showHandover();
});
connect();
