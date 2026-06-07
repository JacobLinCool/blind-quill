// ============================================================
// BLIND QUILL — app root
// View state machine + routing + tweaks + share.
// Wired to the real bindery (app.py / gradio.Server) via BQ.
// ============================================================

const { useState: useStateA, useEffect: useEffectA } = React;

const THREADS = {
  Madder:    { base: "#b23a22", hi: "#cb4a2c", deep: "#8c2c18", glow: "rgba(203,74,44,.45)" },
  Verdigris: { base: "#2f7d6f", hi: "#3a9a88", deep: "#1f5a4f", glow: "rgba(58,154,136,.42)" },
  Indigo:    { base: "#43508f", hi: "#5b6ab1", deep: "#2c3566", glow: "rgba(91,106,177,.42)" },
  Plum:      { base: "#824062", hi: "#a04f79", deep: "#5c2944", glow: "rgba(160,79,121,.42)" },
};
const SERIFS = {
  Spectral:  '"Spectral", Georgia, serif',
  Newsreader:'"Newsreader", Georgia, serif',
  Garamond:  '"EB Garamond", Georgia, serif',
};

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "thread": "Madder",
  "serif": "Spectral",
  "measure": 60,
  "paperCool": false
}/*EDITMODE-END*/;

// Merge a fresh capsule card over any story we already hold, preserving the
// full chapters/log we may have unsealed this session.
function upsertStory(list, story) {
  if (!story) return list;
  const i = list.findIndex((s) => s.id === story.id);
  if (i === -1) return [story, ...list];
  const next = list.slice();
  next[i] = { ...next[i], ...story };
  return next;
}

// Refresh the gallery from server cards while keeping in-memory chapters/log.
function mergeList(prev, list) {
  return list.map((card) => {
    const old = prev.find((s) => s.id === card.id);
    return old && old.chapters ? { ...card, chapters: old.chapters, log: old.log } : card;
  });
}

function App() {
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);
  const [stories, setStories] = useStateA([]);
  const [view, setView] = useStateA("gallery"); // gallery|start|capsule|compose|reveal|reader
  const [activeId, setActiveId] = useStateA(null);
  const [contributed, setContributed] = useStateA(() => new Set());
  const [pending, setPending] = useStateA(null); // { fragment, graft, story, error }
  const [highlightIds, setHighlightIds] = useStateA([]);
  const [draft, setDraft] = useStateA("");
  const [toast, setToast] = useStateA(null);

  const active = stories.find((s) => s.id === activeId) || null;

  // ---- CSS variables from tweaks ----
  const th = THREADS[t.thread] || THREADS.Madder;
  const rootStyle = {
    "--thread": th.base, "--thread-hi": th.hi, "--thread-deep": th.deep, "--thread-glow": th.glow,
    "--serif": SERIFS[t.serif] || SERIFS.Spectral,
    "--measure": (t.measure || 60) + "ch",
    ...(t.paperCool ? { "--paper": "#e6e6da", "--paper-hi": "#f0f0e6", "--paper-edge": "#cdd0c4" } : {}),
  };

  const worldClass = (view === "capsule" || view === "compose" || view === "reader") ? "world-paper" : "world-dark";
  const mastheadClass = (view === "capsule" || view === "compose" || view === "reader") ? "on-paper" : "on-dark";

  // ---- boot: load the bindery + honor a ?story= share link ----
  useEffectA(() => {
    let cancelled = false;
    (async () => {
      try {
        const list = await BQ.listStories();
        if (cancelled) return;
        setStories((prev) => mergeList(prev, list));
        const sid = new URLSearchParams(window.location.search).get("story");
        if (sid) {
          let target = list.find((s) => s.id === sid);
          if (!target) {
            try { target = await BQ.getCapsule(sid); } catch (e) { target = null; }
          }
          if (cancelled) return;
          if (target) {
            setStories((prev) => upsertStory(prev, target));
            setActiveId(target.id);
            setView("capsule");
          } else {
            flash("That manuscript could not be found.");
          }
        }
      } catch (e) {
        if (!cancelled) flash("The bindery is waking up — give it a moment and refresh.");
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // ---- navigation ----
  const goGallery = () => {
    setView("gallery"); setActiveId(null); setHighlightIds([]);
    BQ.listStories().then((list) => setStories((prev) => mergeList(prev, list))).catch(() => {});
  };
  const openStory = (s) => { setActiveId(s.id); setHighlightIds([]); setView("capsule"); };
  const startNew = () => { setDraft(""); setView("start"); };
  const beginContribute = () => setView("compose");

  const createStory = (seed) =>
    BQ.createStory(seed).then((story) => {
      setStories((prev) => upsertStory(prev, story));
      setActiveId(story.id);
      setContributed((prev) => new Set(prev).add(story.id));
      setView("capsule");
      flash("Manuscript bound · share code " + story.id);
      return story;
    });

  const readStory = () => {
    if (!active) return;
    setHighlightIds([]);
    if (active.chapters && active.chapters.length) { setView("reader"); return; }
    BQ.readManuscript(active.id)
      .then((full) => { setStories((prev) => upsertStory(prev, full)); setView("reader"); })
      .catch((e) => flash((e && e.message) || "Could not open the manuscript."));
  };

  const stitch = (fragment) => {
    if (!active) return;
    setDraft(fragment);
    setPending({ fragment, graft: null, story: null, error: null, progress: null });
    setView("reveal");
    const onProgress = (p) => setPending((prev) => (prev ? { ...prev, progress: p } : prev));
    BQ.stitch(active.id, fragment, onProgress)
      .then((res) => setPending((p) => (p ? { ...p, graft: res.reveal, story: res.story } : p)))
      .catch((err) => setPending((p) => (p ? { ...p, error: (err && err.message) || "The bindery could not stitch this fragment." } : p)));
  };

  // The graft is already saved server-side once stitch() resolves; applying here
  // just folds the returned manuscript into local state.
  const applyPending = () => {
    if (!pending || !pending.story) return null;
    const updated = pending.story;
    setStories((prev) => upsertStory(prev, updated));
    setActiveId(updated.id);
    setContributed((prev) => new Set(prev).add(updated.id));
    setDraft("");
    return updated;
  };
  const commitAndRead = () => {
    const updated = applyPending();
    setHighlightIds(updated && pending.graft ? (pending.graft.highlightIds || []) : []);
    setPending(null);
    if (updated) setView("reader"); else goGallery();
  };
  const revealToBindery = () => { applyPending(); setPending(null); goGallery(); };
  const retryFragment = () => { setPending(null); setView("compose"); };

  const share = () => {
    const id = active ? active.id : "";
    const link = window.location.origin + "/?story=" + id;
    if (navigator.clipboard) navigator.clipboard.writeText(link).catch(() => {});
    flash("Share link copied · " + link.replace(/^https?:\/\//, ""));
  };

  let timer;
  const flash = (msg) => { setToast(msg); clearTimeout(timer); timer = setTimeout(() => setToast(null), 2600); };

  return (
    <div className={"bq-app " + worldClass} style={rootStyle}>
      {view !== "reveal" && (
      <header className={"masthead " + mastheadClass}>
        <Wordmark onClick={goGallery} />
        <div className="masthead__nav">
          {view !== "gallery" && <Btn kind={mastheadClass === "on-paper" ? "ghost-paper" : "ghost-dark"} size="sm" icon="book" onClick={goGallery}>The bindery</Btn>}
          {view === "gallery" && <Btn kind="thread" size="sm" icon="quill" onClick={startNew}>Begin</Btn>}
        </div>
      </header>
      )}

      {view === "gallery" && <GalleryView stories={stories} onOpen={openStory} onStartNew={startNew} />}
      {view === "start" && <StartView onBack={goGallery} onCreate={createStory} />}
      {view === "capsule" && active && (
        <CapsuleView
          story={active}
          onBack={goGallery}
          onContribute={beginContribute}
          onRead={readStory}
          canRead={contributed.has(active.id) || active.status === "sealed"}
        />
      )}
      {view === "compose" && active && (
        <ComposerView story={active} draft={draft} onDraftChange={setDraft} onBack={() => setView("capsule")} onStitch={stitch} />
      )}
      {view === "reader" && active && (
        <ReaderView story={active} highlightIds={highlightIds} onBack={goGallery} onShare={share} sealed={active.status === "sealed"} />
      )}

      {view === "reveal" && pending && (
        <RevealStage
          fragment={pending.fragment}
          graft={pending.graft}
          error={pending.error}
          progress={pending.progress}
          onReadManuscript={commitAndRead}
          onBindery={revealToBindery}
          onRetry={retryFragment}
        />
      )}

      {toast && <div className="toast"><Icon name="check" size={14} />{toast}</div>}

      <TweaksPanel>
        <TweakSection label="The thread" />
        <TweakColor label="Graft accent" value={th.base}
          options={[THREADS.Madder.base, THREADS.Verdigris.base, THREADS.Indigo.base, THREADS.Plum.base]}
          onChange={(v) => {
            const name = Object.keys(THREADS).find((k) => THREADS[k].base === v) || "Madder";
            setTweak("thread", name);
          }} />
        <TweakSection label="The page" />
        <TweakRadio label="Manuscript face" value={t.serif} options={["Spectral", "Newsreader", "Garamond"]} onChange={(v) => setTweak("serif", v)} />
        <TweakSlider label="Reading width" value={t.measure} min={50} max={74} unit="ch" onChange={(v) => setTweak("measure", v)} />
        <TweakToggle label="Cool paper" value={t.paperCool} onChange={(v) => setTweak("paperCool", v)} />
      </TweaksPanel>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
