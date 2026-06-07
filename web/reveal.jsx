// ============================================================
// BLIND QUILL — the reveal stage (the dopamine peak)
// A staged sequence: the editor READS the veiled manuscript,
// CHOOSES a target, STITCHES the fragment in, then REVEALS.
//
// Wired to the real backend: the editor's work is two genuine
// model calls (plan + patch). The stage animates while they run
// and only reveals once the real graft returns. `graft` is null
// until the server answers; `error` flips it to a recovery state.
// ============================================================

const { useState: useStateR, useEffect: useEffectR } = React;

function RevealStage({ fragment, graft, error, onReadManuscript, onBindery, onRetry }) {
  const [phase, setPhase] = useStateR("reading"); // reading | choosing | stitching | revealed | error
  const SCAN_LINES = 9;
  const targetLine = 5;

  // Intro beats. We never auto-advance past "stitching" — the reveal waits for
  // the real graft so a slow editor keeps stitching rather than lying about a result.
  useEffectR(() => {
    if (error) return;
    const timers = [];
    timers.push(setTimeout(() => setPhase((p) => (p === "reading" ? "choosing" : p)), 1900));
    timers.push(setTimeout(() => setPhase((p) => (p === "reading" || p === "choosing" ? "stitching" : p)), 3400));
    return () => timers.forEach(clearTimeout);
  }, [error]);

  // Surface a failed stitch immediately.
  useEffectR(() => {
    if (error) setPhase("error");
  }, [error]);

  // When the real graft lands, draw the stitch, then reveal.
  useEffectR(() => {
    if (!graft || error) return;
    setPhase((p) => (p === "reading" || p === "choosing" ? "stitching" : p));
    const t = setTimeout(() => setPhase("revealed"), 1500);
    return () => clearTimeout(t);
  }, [graft, error]);

  const phaseLabel = {
    reading: "The editor is reading the hidden manuscript",
    choosing: "Choosing where it belongs",
    stitching: "Stitching your fragment into the canon",
    revealed: "Grafted",
    error: "The stitch slipped",
  }[phase];

  const reveal = graft ? parseReveal(graft.revealLine) : { before: "", emph: "", after: "" };

  return (
    <div className="stage">
      <div className="bq-grain" style={{ position: "absolute", inset: 0, opacity: .4 }} />
      <div className="stage__inner">
        <span className="stage__quill" style={{ opacity: phase === "revealed" ? 0 : 1, transition: "opacity .5s", height: phase === "revealed" ? 0 : 56, marginBottom: phase === "revealed" ? 0 : 30 }}>
          {phase !== "revealed" && <Icon name="quill" size={52} />}
        </span>

        {phase !== "revealed" && (
          <div className="stage__phase">
            {phaseLabel}{phase !== "error" && <span className="cursor">▍</span>}
          </div>
        )}

        {/* The veiled doc being scanned */}
        {(phase === "reading" || phase === "choosing") && (
          <div className="scan-doc">
            {Array.from({ length: SCAN_LINES }).map((_, i) => {
              const isTarget = phase === "choosing" && i === targetLine;
              return (
                <div
                  key={i}
                  className={"scan-line" + (isTarget ? " is-target" : "")}
                  style={{
                    width: (62 + ((i * 41) % 33)) + "%",
                    opacity: phase === "choosing" ? (i === targetLine ? 1 : .28) : 1,
                    transition: "opacity .5s",
                  }}
                >
                  {phase === "reading" && <span className="scan-sweep" style={{ animationDelay: (i * 0.12) + "s" }} />}
                </div>
              );
            })}
          </div>
        )}

        {/* Stitching: the fragment lands + a stitch draws under it (loops until the editor answers) */}
        {phase === "stitching" && (
          <div style={{ animation: "fadeUp .5s var(--ease-out)" }}>
            <div className="frag-card" style={{ animation: "fadeUp .5s var(--ease-out), glowPulse 1.6s var(--ease-out)" }}>
              "{fragment.length > 160 ? fragment.slice(0, 157) + "…" : fragment}"
            </div>
            <svg width="320" height="40" viewBox="0 0 320 40" style={{ margin: "6px auto 0", display: "block" }}>
              <path
                d="M10 20 H310"
                stroke="var(--thread)"
                strokeWidth="2.4"
                strokeLinecap="round"
                strokeDasharray="10 9"
                style={{ "--len": "320", strokeDashoffset: 320, animation: "drawStitch 1.4s var(--ease-out) infinite" }}
              />
              <circle cx="10" cy="20" r="3" fill="var(--thread)" />
              <circle cx="310" cy="20" r="3" fill="var(--thread)" />
            </svg>
          </div>
        )}

        {/* The reveal */}
        {phase === "revealed" && graft && (
          <div className="stagger" style={{ display: "grid", justifyItems: "center", gap: 0 }}>
            <div className="eyebrow" style={{ color: "var(--thread-hi)", marginBottom: 22 }}>Your fragment found its place</div>
            <h2 className="reveal-line">
              {reveal.before}<em>{reveal.emph}</em>{reveal.after}
            </h2>
            <p className="reveal-rationale">{graft.rationale}</p>
            {graft.targetLabel && <span className="reveal-target"><Icon name="scroll" size={14} /> {graft.targetLabel}</span>}
            <div className="reveal-actions">
              <Btn kind="thread" size="lg" icon="book" onClick={onReadManuscript}>Read the unsealed manuscript</Btn>
              <Btn kind="ghost-dark" onClick={onBindery}>Back to the bindery</Btn>
            </div>
          </div>
        )}

        {/* The fragment could not be stitched */}
        {phase === "error" && (
          <div className="stagger" style={{ display: "grid", justifyItems: "center", gap: 0 }}>
            <h2 className="reveal-line">{error}</h2>
            <p className="reveal-rationale">Your fragment was kept. You can try the stitch again, or step back to the capsule.</p>
            <div className="reveal-actions">
              {onRetry && <Btn kind="thread" size="lg" icon="quill" onClick={onRetry}>Back to the fragment</Btn>}
              <Btn kind="ghost-dark" onClick={onBindery}>Back to the bindery</Btn>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// Split "...Chapter II, just before X." (or "Chapter 2") so the chapter clause
// can be emphasised. The backend reveal uses Arabic numerals; accept both.
function parseReveal(line) {
  const m = (line || "").match(/(Chapter\s+(?:[IVXLCDM]+|\d+))/i);
  if (!m) return { before: line || "", emph: "", after: "" };
  const idx = line.indexOf(m[1]);
  return {
    before: line.slice(0, idx),
    emph: m[1],
    after: line.slice(idx + m[1].length),
  };
}

Object.assign(window, { RevealStage });
