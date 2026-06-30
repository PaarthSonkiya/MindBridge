import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import { IntentBadge, RiskBadge } from "./components/Badges";
import { ScoreGauge } from "./components/ScoreGauge";
import type {
  Expertise,
  HandoverResponse,
  Health,
  Language,
  ProcessResponse,
  VerifyResponse,
} from "./types";

interface Turn {
  id: string;
  result: ProcessResponse;
  readback: string;
  verifying: boolean;
  verification?: VerifyResponse;
}

const PRESETS: { label: string; text: string }[] = [
  { label: "Filter swap", text: "Replace Filter B before restarting the machine." },
  { label: "Lockout/Tagout", text: "Perform lockout on the conveyor before clearing the jam." },
  { label: "Engineer note", text: "Inspect the pump for cavitation caused by low NPSH." },
  { label: "Emergency", text: "Gas leak detected in zone 3, evacuate the area immediately!" },
];

const EXPERTISE_OPTIONS: Expertise[] = ["engineer", "technician", "operator", "trainee"];

let counter = 0;
const nextId = () => `turn-${++counter}`;

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [text, setText] = useState(PRESETS[0].text);
  const [sourceLang, setSourceLang] = useState<Language>("en");
  const [targetLang, setTargetLang] = useState<Language>("vi");
  const [expertise, setExpertise] = useState<Expertise>("operator");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [handover, setHandover] = useState<HandoverResponse | null>(null);
  const sessionId = useRef(`shift-${Date.now()}`);
  const feedRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null));
  }, []);

  useEffect(() => {
    feedRef.current?.scrollTo({ top: feedRef.current.scrollHeight, behavior: "smooth" });
  }, [turns.length]);

  async function process() {
    if (!text.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api.process({
        text: text.trim(),
        source_lang: sourceLang,
        target_lang: targetLang,
        listener_expertise: expertise,
        session_id: sessionId.current,
        speaker: "supervisor",
      });
      setTurns((t) => [...t, { id: nextId(), result, readback: "", verifying: false }]);
      setText("");
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function verify(turn: Turn) {
    if (!turn.readback.trim()) return;
    setTurns((ts) => ts.map((t) => (t.id === turn.id ? { ...t, verifying: true } : t)));
    try {
      const verification = await api.verify({
        session_id: sessionId.current,
        original_text: turn.result.original_text,
        readback_text: turn.readback.trim(),
        listener_expertise: expertise,
      });
      setTurns((ts) =>
        ts.map((t) => (t.id === turn.id ? { ...t, verification, verifying: false } : t)),
      );
    } catch (e) {
      setError(String(e));
      setTurns((ts) => ts.map((t) => (t.id === turn.id ? { ...t, verifying: false } : t)));
    }
  }

  async function generateHandover() {
    try {
      setHandover(await api.handover(sessionId.current));
    } catch (e) {
      setError(String(e));
    }
  }

  function updateReadback(id: string, value: string) {
    setTurns((ts) => ts.map((t) => (t.id === id ? { ...t, readback: value } : t)));
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="logo">◇</span>
          <div>
            <h1>MindBridge</h1>
            <p>Translating Understanding, Not Just Language</p>
          </div>
        </div>
        <div className="status">
          {health ? (
            <span className={`pill ${health.llm_enabled ? "pill-claude" : "pill-offline"}`}>
              {health.llm_enabled ? "Claude engine" : "Edge engine (offline)"} · v{health.version}
            </span>
          ) : (
            <span className="pill pill-down">backend offline</span>
          )}
        </div>
      </header>

      <main className="layout">
        <section className="composer panel">
          <h2>Compose message</h2>

          <div className="presets">
            {PRESETS.map((p) => (
              <button key={p.label} className="chip" onClick={() => setText(p.text)} type="button">
                {p.label}
              </button>
            ))}
          </div>

          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Type an instruction, warning, or question…"
            rows={4}
          />

          <div className="controls">
            <label>
              From
              <select value={sourceLang} onChange={(e) => setSourceLang(e.target.value as Language)}>
                <option value="en">English</option>
                <option value="vi">Vietnamese</option>
              </select>
            </label>
            <label>
              To
              <select value={targetLang} onChange={(e) => setTargetLang(e.target.value as Language)}>
                <option value="vi">Vietnamese</option>
                <option value="en">English</option>
              </select>
            </label>
            <label>
              Listener
              <select value={expertise} onChange={(e) => setExpertise(e.target.value as Expertise)}>
                {EXPERTISE_OPTIONS.map((o) => (
                  <option key={o} value={o}>
                    {o[0].toUpperCase() + o.slice(1)}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <button className="primary" onClick={process} disabled={busy} type="button">
            {busy ? "Analysing…" : "Run through Understanding Engine →"}
          </button>

          {error && <p className="error">{error}</p>}

          <button className="ghost handover-btn" onClick={generateHandover} type="button">
            Generate shift handover
          </button>

          {handover && (
            <div className="handover">
              <h3>Shift Handover · {new Date(handover.generated_at).toLocaleString()}</h3>
              <p className="summary">{handover.summary}</p>
              <HandoverList title="Completed (verified)" items={handover.completed_tasks} />
              <HandoverList title="Pending issues" items={handover.pending_issues} />
              <HandoverList title="Safety observations" items={handover.safety_observations} />
              <HandoverList title="Equipment referenced" items={handover.equipment_referenced} />
            </div>
          )}
        </section>

        <section className="feed panel" ref={feedRef}>
          {turns.length === 0 && (
            <div className="empty">
              <p>
                Run a message through the engine to see intent recognition, risk intelligence,
                expertise-adapted output, and the <strong>Understanding Score™</strong>.
              </p>
            </div>
          )}

          {turns.map((turn) => (
            <article key={turn.id} className="card">
              <div className="card-head">
                <IntentBadge intent={turn.result.intent} />
                <RiskBadge level={turn.result.risk.level} />
                <span className="engine-tag">{turn.result.engine}</span>
              </div>

              <p className="original">“{turn.result.original_text}”</p>

              <div className="row">
                <div className="block">
                  <span className="block-label">Translation ({targetLang.toUpperCase()})</span>
                  <p>{turn.result.translation}</p>
                </div>
                <div className="block">
                  <span className="block-label">Adapted for {expertise}</span>
                  <p>{turn.result.adapted_message}</p>
                </div>
              </div>

              {turn.result.key_points.length > 0 && (
                <div className="keypoints">
                  <span className="block-label">Key points to confirm</span>
                  <ul>
                    {turn.result.key_points.map((k, i) => (
                      <li key={i}>{k}</li>
                    ))}
                  </ul>
                </div>
              )}

              {turn.result.risk.requires_confirmation && (
                <p className="risk-note">
                  ⚠ Safety-critical — explicit read-back confirmation required.
                </p>
              )}

              {turn.result.requires_readback && !turn.verification && (
                <div className="readback">
                  <span className="block-label">Listener read-back</span>
                  <textarea
                    value={turn.readback}
                    onChange={(e) => updateReadback(turn.id, e.target.value)}
                    placeholder="Type what the worker repeats back…"
                    rows={2}
                  />
                  <button
                    className="primary small"
                    onClick={() => verify(turn)}
                    disabled={turn.verifying}
                    type="button"
                  >
                    {turn.verifying ? "Scoring…" : "Verify understanding"}
                  </button>
                </div>
              )}

              {turn.verification && <Verification v={turn.verification} />}
            </article>
          ))}
        </section>
      </main>

      <footer className="footer">
        <span>
          MindBridge — an AI Communication Operating System. Edge-first, privacy-preserving,
          upgradeable to Claude reasoning.
        </span>
      </footer>
    </div>
  );
}

function Verification({ v }: { v: VerifyResponse }) {
  return (
    <div className={`verification ${v.understood ? "ok" : "low"}`}>
      <div className="verification-head">
        <ScoreGauge score={v.understanding_score} />
        <div>
          <span className="block-label">Understanding Score™</span>
          <p className={`verdict ${v.understood ? "ok" : "low"}`}>
            {v.understood ? "Understanding verified" : "Low understanding detected"}
          </p>
          <p className="follow-up">{v.follow_up}</p>
        </div>
      </div>

      <div className="factors">
        {v.factors.map((f) => (
          <div className="factor" key={f.name}>
            <div className="factor-top">
              <span>{f.name}</span>
              <span className="factor-score">{f.score}</span>
            </div>
            <div className="bar">
              <div className="bar-fill" style={{ width: `${f.score}%` }} />
            </div>
            <p className="factor-detail">{f.detail}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function HandoverList({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div className="handover-list">
      <span className="block-label">{title}</span>
      <ul>
        {items.map((i, idx) => (
          <li key={idx}>{i}</li>
        ))}
      </ul>
    </div>
  );
}
