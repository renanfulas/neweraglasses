const SHELL_CACHE_NAME = "new-era-shell-v2";
const OFFLINE_SHELL_URL = "/";
const SHELL_ASSETS = [
  OFFLINE_SHELL_URL,
  "/static/styles.css",
  "/static/app.js",
  "/manifest.webmanifest",
];
const SHELL_ASSET_SET = new Set(SHELL_ASSETS);
const NO_FALLBACK_PREFIXES = [
  "/api/",
  "/uploads/",
  "/document-analyses/",
  "/jobs/",
];

function isSameOrigin(url) {
  return url.origin === self.location.origin;
}

function isSensitivePath(pathname) {
  return NO_FALLBACK_PREFIXES.some((prefix) => pathname.startsWith(prefix));
}

function isShellAsset(url) {
  return isSameOrigin(url) && SHELL_ASSET_SET.has(url.pathname);
}

async function populateShellCache() {
  const cache = await caches.open(SHELL_CACHE_NAME);
  await Promise.all(
    SHELL_ASSETS.map((asset) => cache.add(new Request(asset, { cache: "reload" })))
  );
}

self.addEventListener("install", (event) => {
  event.waitUntil(
    populateShellCache().then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) =>
      Promise.all(
        cacheNames
          .filter((cacheName) => cacheName !== SHELL_CACHE_NAME)
          .map((cacheName) => caches.delete(cacheName))
      )
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;

  if (request.method !== "GET") {
    return;
  }

  const requestUrl = new URL(request.url);

  if (!isSameOrigin(requestUrl)) {
    return;
  }

  if (request.mode === "navigate") {
    if (isSensitivePath(requestUrl.pathname)) {
      return;
    }

    event.respondWith(
      fetch(request).catch(async () => {
        const cache = await caches.open(SHELL_CACHE_NAME);
        return cache.match(OFFLINE_SHELL_URL);
      })
    );
    return;
  }

  if (!isShellAsset(requestUrl) || isSensitivePath(requestUrl.pathname)) {
    return;
  }

  event.respondWith(
    caches.match(request).then((cachedResponse) => {
      if (cachedResponse) {
        return cachedResponse;
      }

      return fetch(request).then((networkResponse) => {
        if (!networkResponse || networkResponse.status !== 200) {
          return networkResponse;
        }

        const responseToCache = networkResponse.clone();
        caches.open(SHELL_CACHE_NAME).then((cache) => {
          cache.put(request, responseToCache);
        });
        return networkResponse;
      });
    })
  );
});
