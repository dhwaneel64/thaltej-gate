/* Keeps the app usable with no signal. The simulation runs locally, so a cached
   page is still a working app — only the live delays need the network, and
   live.json is deliberately never cached. */
const CACHE = "thaltej-v2";
const SHELL = ["./", "./index.html", "./model.js", "./vendor/three.min.js",
               "./manifest.webmanifest", "./icon.svg", "./apple-touch-icon.png"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", e => {
  e.waitUntil(
    caches.keys()
      .then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;
  if (url.pathname.endsWith("live.json")) return;           // always straight to the network

  // stale-while-revalidate: instant load, quietly updated for next time
  e.respondWith(caches.open(CACHE).then(async cache => {
    const hit = await cache.match(e.request);
    const net = fetch(e.request).then(res => {
      if (res && res.ok) cache.put(e.request, res.clone());
      return res;
    }).catch(() => hit);
    return hit || net;
  }));
});
