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

function RevealStage({ fragment, graft, error, progress, onReadManuscript, onBindery, onRetry }) {
  const [phase, setPhase] = useStateR("reading"); // reading | choosing | stitching | revealed | error
  const SCAN_LINES = 9;
  const targetLine = 5;

  // Token-level progress (local CPU/MPS) carries tokensTotal and drives the real
  // bar + ETA. ZeroGPU sends only a coarse start event (no tokensTotal), so we
  // fall back to the staged intro animation below.
  const hasRealProgress = !!(progress && progress.tokensTotal != null);

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

  // While the editor works, let real progress override the timed intro phase so
  // the visuals track what the backend is actually doing. revealed/error always
  // win (set by the effects above).
  const activePhase =
    phase === "revealed" || phase === "error"
      ? phase
      : hasRealProgress && progress.phase
      ? progress.phase
      : phase;

  const phaseLabel = hasRealProgress && progress.label
    ? progress.label
    : {
        reading: "The editor is reading the hidden manuscript",
        choosing: "Choosing where it belongs",
        stitching: "Stitching your fragment into the canon",
        revealed: "Grafted",
        error: "The stitch slipped",
      }[activePhase];

  const pct = hasRealProgress ? Math.round(Math.max(0, Math.min(1, progress.fraction)) * 100) : 0;
  const etaText = hasRealProgress && progress.etaSeconds != null ? formatEta(progress.etaSeconds) : "";

  const reveal = graft ? parseReveal(graft.revealLine) : { before: "", emph: "", after: "" };

  return (
    <div className="stage">
      <div className="bq-grain" style={{ position: "absolute", inset: 0, opacity: .4 }} />
      <div className="stage__inner">
        <span className="stage__quill" style={{ opacity: activePhase === "revealed" ? 0 : 1, transition: "opacity .5s", height: activePhase === "revealed" ? 0 : 56, marginBottom: activePhase === "revealed" ? 0 : 30 }}>
          {activePhase !== "revealed" && <Icon name="quill" size={52} />}
        </span>

        {activePhase !== "revealed" && (
          <div className="stage__phase">
            {phaseLabel}{activePhase !== "error" && <span className="cursor">▍</span>}
          </div>
        )}

        {/* Real progress: a bar, percentage, step, and ETA so a slow local run
            tells the reader what is happening and how much is left. */}
        {hasRealProgress && activePhase !== "revealed" && activePhase !== "error" && (
          <div className="bq-progress">
            <div className="bq-progress__track">
              <div className="bq-progress__fill" style={{ width: pct + "%", transition: "width .3s var(--ease-out)" }} />
            </div>
            <div className="bq-progress__meta">
              <span>Step {progress.stageIndex}/{progress.stageTotal} · {pct}%</span>
              {etaText && <span>about {etaText} left</span>}
            </div>
            {progress.notice && <div className="bq-progress__notice">{progress.notice}</div>}
          </div>
        )}

        {/* The veiled doc being scanned */}
        {(activePhase === "reading" || activePhase === "choosing") && (
          <div className="scan-doc">
            {Array.from({ length: SCAN_LINES }).map((_, i) => {
              const isTarget = activePhase === "choosing" && i === targetLine;
              return (
                <div
                  key={i}
                  className={"scan-line" + (isTarget ? " is-target" : "")}
                  style={{
                    width: (62 + ((i * 41) % 33)) + "%",
                    opacity: activePhase === "choosing" ? (i === targetLine ? 1 : .28) : 1,
                    transition: "opacity .5s",
                  }}
                >
                  {activePhase === "reading" && <span className="scan-sweep" style={{ animationDelay: (i * 0.12) + "s" }} />}
                </div>
              );
            })}
          </div>
        )}

        {/* Stitching: the fragment lands + a stitch draws under it (loops until the editor answers) */}
        {activePhase === "stitching" && (
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
        {activePhase === "revealed" && graft && (
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
        {activePhase === "error" && (
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

// Human-friendly ETA: seconds → "8s" or "1m 12s".
function formatEta(seconds) {
  const s = Math.max(0, Math.round(seconds));
  if (s < 60) return s + "s";
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return rem ? m + "m " + rem + "s" : m + "m";
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
