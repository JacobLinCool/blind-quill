// ============================================================
// BLIND QUILL — backend bridge
// Talks to the gradio.Server endpoints (app.py) through the
// Gradio JS Client. Replaces the prototype's local stub editor
// with the real invisible editor (Qwen) behind the queue.
// Exposes BQ + KINDS to window for the Babel views.
// ============================================================

// Fragment kinds offered in the composer (player-facing labels).
const KINDS = ["a secret", "an object", "a scene", "a place", "a trait", "a strange rule", "a line of dialogue"];

// The Gradio client is imported as an ES module in index.html and parked on
// window.__bqClientReady (a promise). Wait for it, then connect once.
let _clientPromise = null;
async function bqClient() {
  for (let i = 0; i < 200 && !window.__bqClientReady; i++) {
    await new Promise((r) => setTimeout(r, 50));
  }
  if (!window.__bqClientReady) {
    throw new Error("The bindery client could not load. Check your connection and reload.");
  }
  if (!_clientPromise) _clientPromise = window.__bqClientReady;
  return _clientPromise;
}

// Call a named @app.api endpoint and return its single JSON payload.
async function bqCall(name, payload) {
  const client = await bqClient();
  let result;
  try {
    result = await client.predict("/" + name, payload || {});
  } catch (err) {
    throw new Error(bqErrorMessage(err));
  }
  const data = result && result.data;
  return Array.isArray(data) ? data[0] : data;
}

function bqErrorMessage(err) {
  if (!err) return "The bindery did not answer. Try again.";
  if (typeof err === "string") return err;
  if (err.message) return err.message;
  return "The bindery did not answer. Try again.";
}

const BQ = {
  // Gallery: capsule-level cards only (no hidden chapters).
  listStories: () => bqCall("list_stories", {}).then((r) => (r && r.stories) || []),
  // One story's full public capsule (still blinded — no chapters).
  getCapsule: (story_id) => bqCall("get_capsule", { story_id }).then((r) => r && r.story),
  // Create from a seed; the creator receives the full manuscript.
  createStory: (seed) => bqCall("create_story", { seed }).then((r) => r && r.story),
  // Stitch a fragment: { story (full, updated), reveal: { revealLine, rationale, targetLabel, highlightIds } }.
  stitch: (story_id, fragment) => bqCall("stitch", { story_id, fragment }),
  // Read a sealed manuscript end to end.
  readManuscript: (story_id) => bqCall("read_manuscript", { story_id }).then((r) => r && r.story),
};

Object.assign(window, { BQ, KINDS });
