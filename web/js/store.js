// Everything lives on the phone. localStorage can be missing or full (private mode), so every
// access is guarded and falls back to memory for the session.

const KEY = "grassy.v1";
const memory = {};

function read() {
  try {
    const raw = globalThis.localStorage?.getItem(KEY);
    if (raw) return JSON.parse(raw);
  } catch { /* fall through */ }
  return memory.state ?? null;
}

export function load() {
  const s = read();
  return s && typeof s === "object" ? s : { groups: [], current: null, lang: null, smartUrl: "" };
}

export function save(state) {
  memory.state = state;
  try {
    globalThis.localStorage?.setItem(KEY, JSON.stringify(state));
    return true;
  } catch {
    return false; // the app keeps working; the screen can warn that nothing was saved
  }
}

let counter = 0;
export const newId = () => `g${Date.now().toString(36)}${(counter++).toString(36)}`;
