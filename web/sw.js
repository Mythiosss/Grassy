// Offline shell: cache every app file on install, serve from cache first. Never touch /api.
const CACHE = "grassy-v1";
const FILES = [
  "./", "index.html", "style.css", "manifest.webmanifest",
  "js/app.js", "js/calendar.js", "js/csv.js", "js/dates.js", "js/engine.js", "js/i18n.js",
  "js/invite.js", "js/planner.js", "js/store.js", "js/sun.js", "js/views.js",
  "data/calendar.json", "data/sample.json",
  "icons/icon-192.png", "icons/icon-512.png", "icons/icon-32.png", "icons/apple-touch-icon.png",
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(FILES)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin || url.pathname.startsWith("/api")) return;
  e.respondWith(
    caches.match(e.request).then(
      (hit) =>
        hit ||
        fetch(e.request).then((res) => {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(e.request, copy));
          return res;
        }),
    ),
  );
});
