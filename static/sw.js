const CACHE = 'sportcards-v3';
const OFFLINE_URLS = ['/', '/collection', '/static/css/app.css'];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(OFFLINE_URLS)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  // Never intercept non-GET requests (POST bodies get consumed and arrive empty)
  if (e.request.method !== 'GET') return;

  const url = new URL(e.request.url);
  // API calls: network first, no cache
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/uploads/')) {
    e.respondWith(
      fetch(e.request).catch(() => new Response(JSON.stringify({error: 'Sin conexión'}),
        {headers: {'Content-Type': 'application/json'}}))
    );
    return;
  }
  // Pages and assets: network first, fallback to cache
  e.respondWith(
    fetch(e.request)
      .then(r => {
        const clone = r.clone();
        caches.open(CACHE).then(c => c.put(e.request, clone));
        return r;
      })
      .catch(() => caches.match(e.request))
  );
});
