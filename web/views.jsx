// ============================================================
// BLIND QUILL — primary views
// Gallery (Bindery), Start flow, blinded Capsule, Composer, Reader.
// Exported to window.
// ============================================================

const { useState: useStateV, useEffect: useEffectV, useRef: useRefV } = React;

const SEED_EXAMPLES = [
  {
    label: "Bare image",
    text: "A city where every doorway remembers the last person who lied inside it.",
  },
  {
    label: "Clear premise",
    text: "Every winter, a mountain village elects one child to speak for the dead until spring.",
  },
  {
    label: "Open scene",
    text: "An apprentice cartographer finds a coastline on her new map that is not on the land, and each morning the ink moves closer to home.",
  },
  {
    label: "Full setup",
    text: "On a generation ship whose crew believes Earth was a myth invented to calm children, a janitor discovers a sealed garden where rain falls upward and an old radio is still receiving ocean weather reports.",
  },
];

const FRAGMENT_EXAMPLES = [
  {
    label: "Object",
    kind: "an object",
    text: "A brass key in the protagonist's pocket becomes warm whenever someone nearby tells the truth.",
  },
  {
    label: "Trait",
    kind: "a trait",
    text: "The quietest character always counts exits before answering a question.",
  },
  {
    label: "Scene",
    kind: "a scene",
    text: "During a celebration, all the candles bend toward a locked room no one admits exists.",
  },
  {
    label: "Strange rule",
    kind: "a strange rule",
    text: "A page torn from a field guide: 'If the moths arrive before dawn, do not look at the moon.'",
  },
];

// ---------------- Gallery / The Bindery ----------------
function GalleryView({ stories, onOpen, onStartNew }) {
  const open = stories.filter((s) => s.status !== "sealed");
  const sealed = stories.filter((s) => s.status === "sealed");
  return (
    <div className="page">
      <section className="bindery-hero stagger">
        <div className="eyebrow bindery-hero__eyebrow">A blinded story-grafting game</div>
        <h1>You never read the whole book. You only <em>change</em> it.</h1>
        <p className="bindery-hero__lede">
          Every manuscript here is hidden. You see a single public capsule — a genre, a few
          characters, a whisper of plot. Add one fragment, and an invisible editor decides where
          in the secret canon it belongs, then reveals how it was stitched in.
        </p>
        <div className="bindery-hero__actions">
          <Btn kind="thread" size="lg" icon="quill" onClick={onStartNew}>Begin a manuscript</Btn>
          <span className="eyebrow" style={{ color: "var(--bone-faint)" }}>{stories.length} manuscripts bound</span>
        </div>
      </section>

      <div className="section-head">
        <h2>Open for grafting</h2>
        <span className="eyebrow" style={{ color: "var(--bone-faint)" }}>{open.length} open</span>
      </div>
      <div className="shelf">
        <NewManuscriptCard onClick={onStartNew} />
        {open.map((s) => <ManuscriptCard key={s.id} story={s} onOpen={onOpen} />)}
      </div>

      {sealed.length > 0 && (
        <React.Fragment>
          <div className="section-head" style={{ marginTop: 48 }}>
            <h2>Sealed canon</h2>
            <span className="eyebrow" style={{ color: "var(--bone-faint)" }}>read only</span>
          </div>
          <div className="shelf">
            {sealed.map((s) => <ManuscriptCard key={s.id} story={s} onOpen={onOpen} />)}
          </div>
        </React.Fragment>
      )}
    </div>
  );
}

// ---------------- Start a manuscript ----------------
function StartView({ onBack, onCreate }) {
  const [seed, setSeed] = useStateV("");
  const [phase, setPhase] = useStateV("write"); // write | binding
  const [error, setError] = useStateV(null);
  const MAX = 500;
  const placeholder = SEED_EXAMPLES[1].text;

  const begin = () => {
    if (!seed.trim()) return;
    setError(null);
    setPhase("binding");
    // The real bindery (Qwen) takes as long as it takes. Stay on the binding
    // beat until App swaps the view on success; surface failures inline.
    Promise.resolve(onCreate(seed)).catch((e) => {
      setError((e && e.message) || "The bindery could not bind this seed. Try again.");
      setPhase("write");
    });
  };

  if (phase === "binding") {
    return (
      <div className="page page--narrow binding-page">
        <div className="binding-panel stagger" role="status" aria-live="polite">
          <span className="binding-mark" aria-hidden="true">
            <Icon name="book" size={42} stroke={1.5} />
            <span className="binding-mark__thread" />
          </span>
          <div className="eyebrow binding-panel__eyebrow">
            Creating your hidden manuscript<span className="cursor">▍</span>
          </div>
          <h2>Binding a new story from your seed</h2>
          <p className="binding-panel__lede">
            The bindery is expanding your prompt into chapters, characters, and secret world rules.
            When it finishes, you will land on the public capsule for the new manuscript.
          </p>
          <ol className="binding-steps" aria-label="What is happening now">
            <li>
              <span className="binding-steps__dot" />
              <div>
                <strong>Building the hidden canon</strong>
                <p>Drafting the full story that later players cannot read up front.</p>
              </div>
            </li>
            <li>
              <span className="binding-steps__dot" />
              <div>
                <strong>Writing the public capsule</strong>
                <p>Preparing the title, genre, visible characters, and open questions.</p>
              </div>
            </li>
            <li>
              <span className="binding-steps__dot" />
              <div>
                <strong>Saving it to the bindery</strong>
                <p>After this, you can read it, share it, or add another fragment.</p>
              </div>
            </li>
          </ol>
          <p className="binding-note">This can take about a minute on ZeroGPU. Keep this tab open.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="page page--narrow">
      <button className="backlink" onClick={onBack}><Icon name="arrow-left" size={13} /> The bindery</button>
      <div className="composer__prompt">
        <div className="eyebrow">New hidden manuscript</div>
        <h2 style={{ color: "var(--bone)" }}>Plant a seed</h2>
        <p style={{ color: "var(--bone-soft)" }}>
          One or two sentences. The bindery grows it into a full manuscript — then hides everything
          but a public capsule. You'll be the only one who sees the whole thing.
        </p>
      </div>

      <div className="field" style={{ background: "var(--paper-hi)", padding: 24, borderRadius: "var(--r-lg)", border: "1px solid var(--paper-edge)" }}>
        <label className="field__label">Your seed</label>
        <textarea
          rows={4}
          maxLength={MAX}
          value={seed}
          placeholder={placeholder}
          onChange={(e) => setSeed(e.target.value)}
        />
        <div className="field__count">{seed.length} / {MAX}</div>
        <ExampleChooser
          title="Example seeds"
          examples={SEED_EXAMPLES}
          value={seed}
          onSelect={(example) => setSeed(example.text)}
        />
        <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center", gap: 12, marginTop: 14, flexWrap: "wrap" }}>
          <Btn kind="thread" icon="quill" onClick={begin} disabled={!seed.trim()}>Begin manuscript</Btn>
        </div>
      </div>
      {error && (
        <p className="composer__hint text-center" style={{ marginTop: 18, color: "var(--thread-hi)" }}>{error}</p>
      )}
    </div>
  );
}

// ---------------- Blinded capsule (the teaser before contributing) ----------------
function CapsuleView({ story, onBack, onContribute, onRead, canRead }) {
  const c = story.capsule;
  const sealed = story.status === "sealed";
  return (
    <div className="page">
      <button className="backlink" onClick={onBack}><Icon name="arrow-left" size={13} /> The bindery</button>
      <div className="capsule-wrap stagger">
        <article className="capsule bq-grain">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, marginBottom: 22 }}>
            <StatusBadge status={story.status} />
            <Ledger count={story.graftCount} max={story.maxGrafts} sealed={sealed} />
          </div>
          <div className="eyebrow capsule__eyebrow">Public capsule · all you may see</div>
          <h1 className="capsule__title">{c.title}</h1>
          <div className="capsule__genre">{c.genre} · {c.tone}</div>
          <p className="capsule__summary">{c.summary}</p>

          <p className="capsule__sub">Visible characters</p>
          <div className="char-list">
            {c.characters.map((ch, i) => (
              <div className="char" key={i}>
                <span className="char__name">{ch.name}</span>
                <span className="char__desc">{ch.desc}</span>
              </div>
            ))}
          </div>

          <p className="capsule__sub">Open questions</p>
          <ul className="qlist">
            {c.questions.map((q, i) => <li key={i}>{q}</li>)}
          </ul>

          <div className="divider-stitch" style={{ margin: "26px 0 20px" }} />
          {sealed ? (
            <Btn kind="ink" icon="book" onClick={onRead}>Read the sealed manuscript</Btn>
          ) : canRead ? (
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
              <Btn kind="thread" icon="quill" onClick={onContribute}>Add another fragment</Btn>
              <Btn kind="ghost-paper" icon="book" onClick={onRead}>Read the manuscript</Btn>
            </div>
          ) : (
            <Btn kind="thread" icon="quill" onClick={onContribute}>Contribute a fragment</Btn>
          )}
        </article>

        <aside className="veil-panel">
          <div className="veil-panel__head">
            <span className="veil-panel__lock"><Icon name={sealed ? "seal" : "eye-off"} size={20} /></span>
            <span className="veil-panel__title">{sealed ? "Sealed canon" : "The hidden manuscript"}</span>
          </div>
          {sealed ? (
            <div style={{ padding: "20px 0 6px" }}>
              <WaxSeal label="Sealed · 30 of 30" />
            </div>
          ) : (
            <div className="veil-panel__doc">
              {[0, 1, 2].map((b) => (
                <div className="veil-block" key={b}>
                  <div className="h" />
                  <Veil lines={4} />
                </div>
              ))}
            </div>
          )}
          <p className="veil-panel__note">
            {sealed
              ? "This canon is sealed. Read it freely — it can accept no more grafts."
              : "You cannot read the canon until you have changed it. Add a fragment to unseal the full story."}
          </p>
        </aside>
      </div>
    </div>
  );
}

// ---------------- Composer (write a fragment) ----------------
function ComposerView({ story, draft, onDraftChange, onBack, onStitch }) {
  const [frag, setFrag] = useStateV(draft || "");
  const [kind, setKind] = useStateV(null);
  const MAX = 500;
  const placeholder = FRAGMENT_EXAMPLES[0].text;
  // Keep App's draft in sync so a failed stitch can return here without losing text.
  const update = (v) => { setFrag(v); if (onDraftChange) onDraftChange(v); };
  const chooseExample = (example) => {
    setKind(example.kind);
    update(example.text);
  };

  return (
    <div className="page page--narrow">
      <button className="backlink" onClick={onBack}><Icon name="arrow-left" size={13} /> Back to capsule</button>
      <div className="composer">
        <div className="composer__prompt">
          <div className="eyebrow">{story.capsule.title} · {story.graftCount}/{story.maxGrafts}</div>
          <h2>Press one fragment into the dark</h2>
          <p>You don't choose where it lands. Write a secret, an object, a scene, a place, a trait,
            a strange rule — the editor will find the seam where it always belonged.</p>
        </div>

        <div className="kinds">
          {KINDS.map((k) => (
            <button key={k} className={"kind" + (kind === k ? " is-active" : "")} onClick={() => setKind(kind === k ? null : k)}>{k}</button>
          ))}
        </div>

        <div className="field" style={{ background: "var(--paper-hi)", padding: 24, borderRadius: "var(--r-lg)", border: "1px solid var(--paper-edge)" }}>
          <label className="field__label">Your fragment{kind ? " · " + kind : ""}</label>
          <textarea rows={4} maxLength={MAX} value={frag} placeholder={placeholder} onChange={(e) => update(e.target.value)} />
          <div className="field__count">{frag.length} / {MAX}</div>
          <ExampleChooser
            title="Example fragments"
            examples={FRAGMENT_EXAMPLES}
            value={frag}
            onSelect={chooseExample}
          />
          <div className="composer__actions">
            <Btn kind="thread" icon="quill" onClick={() => frag.trim() && onStitch(frag)} disabled={!frag.trim()}>Stitch my fragment</Btn>
          </div>
        </div>
        <p className="composer__hint text-center" style={{ marginTop: 18 }}>
          Once stitched, the full manuscript unseals — and your fragment is part of the canon forever.
        </p>
      </div>
    </div>
  );
}

function ExampleChooser({ title, examples, value, onSelect }) {
  return (
    <div className="examples">
      <div className="examples__head">{title}</div>
      <div className="examples__list">
        {examples.map((example) => (
          <button
            type="button"
            key={example.label}
            className={"example-choice" + (value === example.text ? " is-active" : "")}
            onClick={() => onSelect(example)}
          >
            <span className="example-choice__label">{example.label}</span>
            <span className="example-choice__text">{example.text}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

// ---------------- Reader (full manuscript) ----------------
function ReaderView({ story, highlightIds, onBack, onShare, sealed }) {
  return (
    <div className="page">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <button className="backlink" onClick={onBack} style={{ marginBottom: 0 }}><Icon name="arrow-left" size={13} /> The bindery</button>
        <Btn kind="ghost-paper" size="sm" icon="link" onClick={onShare}>Copy share link</Btn>
      </div>
      <div style={{ height: 26 }} />
      <ManuscriptReader story={story} highlightIds={highlightIds} />

      {story.log && story.log.length > 0 && (
        <div style={{ maxWidth: "var(--measure)", marginLeft: "auto", marginRight: "auto" }}>
          <div className="ledger-panel">
            <h3>The graft ledger · who changed this story</h3>
            {story.log.map((row, i) => (
              <div className="ledger-row" key={i}>
                <span className="ledger-row__no">{String(row.no).padStart(2, "0")}</span>
                <div>
                  <div className="ledger-row__frag">"{row.frag}"</div>
                  <div className="ledger-row__where">{row.where}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

Object.assign(window, { GalleryView, StartView, CapsuleView, ComposerView, ReaderView });
