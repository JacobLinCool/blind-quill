// ============================================================
// BLIND QUILL — backend bridge
// Talks to the gradio.Server endpoints (app.py) through the
// Gradio JS Client. Runs the invisible editor (Qwen) behind the queue.
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

// Call a streaming generator endpoint. The editor yields { type: "progress" }
// events while it works and a final { type: "result" } event. Progress events
// are forwarded to onProgress; the result is returned. Some runs (ZeroGPU) emit
// only a coarse start event, so the UI must tolerate sparse progress.
async function bqStream(name, payload, onProgress) {
  const client = await bqClient();
  let stream;
  try {
    stream = client.submit("/" + name, payload || {});
  } catch (err) {
    throw new Error(bqErrorMessage(err));
  }
  let result = null;
  try {
    for await (const msg of stream) {
      if (msg.type === "data") {
        const item = msg.data && msg.data[0];
        if (!item) continue;
        if (item.type === "progress") {
          if (onProgress) { try { onProgress(item); } catch (_e) { /* progress is best-effort */ } }
        } else if (item.type === "result") {
          result = item;
        }
      } else if (msg.type === "status" && msg.stage === "error") {
        throw new Error(bqErrorMessage(msg.message || msg));
      }
    }
  } catch (err) {
    throw new Error(bqErrorMessage(err));
  }
  if (!result) throw new Error("The bindery did not finish the stitch. Try again.");
  return result;
}

const BQ = {
  // Gallery: capsule-level cards only (no hidden chapters).
  listStories: () => bqCall("list_stories", {}).then((r) => (r && r.stories) || []),
  // One story's full public capsule (still blinded — no chapters).
  getCapsule: (story_id) => bqCall("get_capsule", { story_id }).then((r) => r && r.story),
  // Create from a seed; the creator receives the full manuscript.
  createStory: (seed) => bqCall("create_story", { seed }).then((r) => r && r.story),
  // Stitch a fragment (streaming): forwards { type:"progress", ... } events to
  // onProgress and resolves with { story (full, updated), reveal: {...} }.
  stitch: (story_id, fragment, onProgress) => bqStream("stitch", { story_id, fragment }, onProgress),
  // Read a manuscript end to end. The UI warns first when the reader has not contributed.
  readManuscript: (story_id) => bqCall("read_manuscript", { story_id }).then((r) => r && r.story),
};

Object.assign(window, { BQ, KINDS });
