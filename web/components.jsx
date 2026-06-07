// ============================================================
// BLIND QUILL — shared components
// Stateless presentational pieces, exported to window.
// ============================================================

const { useState, useEffect, useRef } = React;

// ---------- Icons (stroke-only, 24x24) ----------
function Icon({ name, size = 18, stroke = 1.7, style }) {
  const common = {
    width: size, height: size, viewBox: "0 0 24 24", fill: "none",
    stroke: "currentColor", strokeWidth: stroke, strokeLinecap: "round", strokeLinejoin: "round", style,
  };
  switch (name) {
    case "quill":
      return (
        <svg {...common}>
          <path d="M20 4c-7 1-12 5-15 11l-2 5 5-2c6-3 10-8 11-15" />
          <path d="M14 7c1 2 0 4-2 5" />
          <path d="M3 21l6-6" />
        </svg>
      );
    case "lock":
      return (<svg {...common}><rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/><circle cx="12" cy="15.5" r="1.2" fill="currentColor" stroke="none"/></svg>);
    case "arrow-right":
      return (<svg {...common}><path d="M5 12h14"/><path d="M13 6l6 6-6 6"/></svg>);
    case "arrow-left":
      return (<svg {...common}><path d="M19 12H5"/><path d="M11 6l-6 6 6 6"/></svg>);
    case "plus":
      return (<svg {...common}><path d="M12 5v14"/><path d="M5 12h14"/></svg>);
    case "book":
      return (<svg {...common}><path d="M4 5c0-1 1-2 2-2h12v16H6c-1 0-2 1-2 2z"/><path d="M4 19c0-1 1-2 2-2h12"/></svg>);
    case "link":
      return (<svg {...common}><path d="M9 13a5 5 0 0 0 7 0l2-2a5 5 0 0 0-7-7l-1 1"/><path d="M15 11a5 5 0 0 0-7 0l-2 2a5 5 0 0 0 7 7l1-1"/></svg>);
    case "seal":
      return (<svg {...common}><circle cx="12" cy="12" r="8"/><path d="M12 4v16M4 12h16" opacity=".4"/><circle cx="12" cy="12" r="3"/></svg>);
    case "check":
      return (<svg {...common}><path d="M5 12l5 5L19 7"/></svg>);
    case "scroll":
      return (<svg {...common}><path d="M6 4h11v13a3 3 0 0 0 3 3H8a3 3 0 0 1-3-3V5"/><path d="M9 8h6M9 11h6"/></svg>);
    case "eye-off":
      return (<svg {...common}><path d="M3 3l18 18"/><path d="M10.6 5.1A9 9 0 0 1 21 12a16 16 0 0 1-2.6 3.3M6.6 6.6A16 16 0 0 0 3 12a9 9 0 0 0 12.9 4.2"/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/></svg>);
    default:
      return null;
  }
}

// ---------- Wordmark ----------
function Wordmark({ onClick }) {
  return (
    <div className="wordmark" onClick={onClick}>
      <span className="wordmark__name">Blind <span className="q">Quill</span></span>
      <span className="wordmark__sub">The Invisible Bindery</span>
    </div>
  );
}

// ---------- Buttons ----------
function Btn({ kind = "ghost-paper", size, icon, iconRight, children, onClick, disabled, type }) {
  const cls = ["btn", `btn--${kind}`, size ? `btn--${size}` : ""].join(" ");
  return (
    <button className={cls} onClick={onClick} disabled={disabled} type={type || "button"}>
      {icon && <Icon name={icon} size={size === "sm" ? 13 : 15} />}
      {children}
      {iconRight && <Icon name={iconRight} size={size === "sm" ? 13 : 15} />}
    </button>
  );
}

// ---------- Badge + Ledger ----------
function StatusBadge({ status }) {
  const sealed = status === "sealed";
  return (
    <span className={"badge " + (sealed ? "badge--sealed" : "badge--open")}>
      <span className="dot" />
      {sealed ? "Sealed" : "Open"}
    </span>
  );
}

function Ledger({ count, max, sealed }) {
  const pct = Math.round((count / max) * 100);
  return (
    <span className={"ledger" + (sealed ? " ledger--sealed" : "")}>
      <span className="ledger__track"><span className="ledger__fill" style={{ width: pct + "%" }} /></span>
      <span className="ledger__count">{count} / {max}</span>
    </span>
  );
}

// ---------- Veiled lines (blinded text) ----------
function Veil({ lines = 4, widths }) {
  const ws = widths || Array.from({ length: lines }, (_, i) => 70 + ((i * 37) % 28));
  return (
    <span className="veil" aria-hidden="true">
      {ws.map((w, i) => <span key={i} className="veil__bar" style={{ width: w + "%" }} />)}
    </span>
  );
}

// ---------- Manuscript card (gallery) ----------
function ManuscriptCard({ story, onOpen }) {
  const c = story.capsule;
  return (
    <button className="ms-card" onClick={() => onOpen(story)}>
      <div className="ms-card__top">
        <StatusBadge status={story.status} />
        <Ledger count={story.graftCount} max={story.maxGrafts} sealed={story.status === "sealed"} />
      </div>
      <div className="ms-card__genre">{c.genre} · {c.tone}</div>
      <div className="ms-card__title">{c.title}</div>
      <div className="ms-card__summary">{c.summary}</div>
      <div className="ms-card__foot">
        <span className="ms-card__code">{story.id}</span>
        <span className="ms-card__code" style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
          {story.status === "sealed" ? "Read" : "Contribute"} <Icon name="arrow-right" size={13} />
        </span>
      </div>
    </button>
  );
}

function NewManuscriptCard({ onClick }) {
  return (
    <button className="ms-card ms-card--new" onClick={onClick}>
      <span className="plus">+</span>
      <h3>Begin a Hidden Manuscript</h3>
      <p>Plant a seed. The bindery grows it into a story only its public capsule will betray.</p>
    </button>
  );
}

// ---------- Wax seal ----------
function WaxSeal({ label = "Sealed · 30 of 30" }) {
  return (
    <div style={{ display: "grid", justifyItems: "center", gap: 16 }}>
      <div className="wax"><span className="wax__q">Q</span></div>
      <span className="eyebrow" style={{ color: "var(--thread-hi)" }}>{label}</span>
    </div>
  );
}

// ---------- Manuscript reader ----------
function ManuscriptReader({ story, highlightId, highlightIds, newGraft }) {
  const [active, setActive] = useState(story.chapters[0] ? 0 : 0);
  const refs = useRef([]);
  // A graft can land 1–3 paragraphs; accept either a single id or a set.
  const grafted = new Set(highlightIds || (highlightId ? [highlightId] : []));

  const goChapter = (i) => {
    setActive(i);
    const el = refs.current[i];
    if (el) {
      const top = el.getBoundingClientRect().top + window.scrollY - 90;
      window.scrollTo({ top, behavior: "smooth" });
    }
  };

  return (
    <div className="reader">
      <aside className="reader-rail">
        <div className="reader-rail__head">Folio</div>
        {story.chapters.map((ch, i) => (
          <button key={i} className={"toc-item" + (active === i ? " is-active" : "")} onClick={() => goChapter(i)}>
            <span className="toc-item__no">{ch.no}</span>
            <span className="toc-item__title">{ch.title}</span>
          </button>
        ))}
        <div style={{ marginTop: 18 }}>
          <Ledger count={story.graftCount} max={story.maxGrafts} sealed={story.status === "sealed"} />
        </div>
      </aside>

      <div className="reader-body">
        <header className="reader-body__head">
          <div className="chapter__no">{story.capsule.genre} · {story.capsule.tone}</div>
          <h1 className="reader-body__title">{story.capsule.title}</h1>
          <div className="reader-meta">
            <span>Story · {story.id}</span>
            <span>Grafts · {story.graftCount}/{story.maxGrafts}</span>
            <span>{story.status === "sealed" ? "Sealed manuscript" : "Open for grafting"}</span>
          </div>
        </header>

        {story.chapters.map((ch, i) => (
          <section key={i} className="chapter" ref={(el) => (refs.current[i] = el)}>
            <div className="chapter__no">Chapter {ch.no}</div>
            <h2 className="chapter__title">{ch.title}</h2>
            <p className="chapter__summary">{ch.summary}</p>
            <div className="chapter__body">
              {ch.paragraphs.map((p) => {
                const isGraft = grafted.has(p.id);
                if (isGraft) {
                  return (
                    <p key={p.id} className="graft is-new">
                      <span className="graft__tag">Your graft</span>
                      {p.text}
                    </p>
                  );
                }
                if (p.lead) {
                  const first = p.text.charAt(0);
                  const rest = p.text.slice(1);
                  return (
                    <p key={p.id} className="lead">
                      <span className="dropcap">{first}</span>{rest}
                    </p>
                  );
                }
                return <p key={p.id}>{p.text}</p>;
              })}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}

Object.assign(window, {
  Icon, Wordmark, Btn, StatusBadge, Ledger, Veil,
  ManuscriptCard, NewManuscriptCard, WaxSeal, ManuscriptReader,
});
