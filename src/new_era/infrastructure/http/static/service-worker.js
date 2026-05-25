const SHELL_CACHE_NAME = "new-era-shell-v3";
const OFFLINE_SHELL_URL = "/";
const SHELL_ASSETS = [
  OFFLINE_SHELL_URL,
  "/static/styles.css",
  "/static/app.js",
  "/manifest.webmanifest",
];
const SHELL_ASSET_SET = new Set(SHELL_ASSETS);
const SENSITIVE_PATH_PREFIXES = [
  "/api/",
  "/uploads/",
  "/document-analyses/",
  "/jobs/",
];
const SENSITIVE_RESPONSE_HEADERS = [
  "authorization",
  "cookie",
  "x-new-era-sensitive",
];

function isSameOrigin(url) {
  return url.origin === self.location.origin;
}

function isSensitivePath(pathname) {
  return SENSITIVE_PATH_PREFIXES.some((prefix) => pathname.startsWith(prefix));
}

function isShellAsset(url) {
  return isSameOrigin(url) && SHELL_ASSET_SET.has(url.pathname);
}

function variesOnSensitiveHeaders(response) {
  const varyHeader = response.headers.get("Vary");
  if (!varyHeader) {
    return false;
  }

  const varyValues = varyHeader
    .split(",")
    .map((value) => value.trim().toLowerCase())
    .filter(Boolean);
  return SENSITIVE_RESPONSE_HEADERS.some((header) => varyValues.includes(header));
}

function isSensitiveResponse(response) {
  const cacheControl = (response.headers.get("Cache-Control") || "").toLowerCase();
  if (cacheControl.includes("no-store") || cacheControl.includes("private")) {
    return true;
  }

  if ((response.headers.get("X-New-Era-Sensitive") || "").toLowerCase() === "true") {
    return true;
  }

  return variesOnSensitiveHeaders(response);
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

        if (isSensitiveResponse(networkResponse)) {
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
