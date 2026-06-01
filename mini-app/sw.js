// Dilux Bakery — Service Worker (xavfsiz, faqat brauzer/PWA uchun)
// MUHIM: HTML/navigatsiya HECH QACHON keshlanmaydi — har doim tarmoqdan keladi,
// shuning uchun "qora ekran" yoki eski versiya muammosi bo'lmaydi.
const CACHE = 'dilux-v5';
const ASSETS = [
  './manifest.webmanifest',
  './icon-192.png',
  './icon-512.png',
  './icon-maskable-512.png',
  './apple-touch-icon.png',
  './favicon-64.png'
];

self.addEventListener('install', e => {
  self.skipWaiting();
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)).catch(() => {}));
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const accept = req.headers.get('accept') || '';
  // Sahifa (HTML): doim tarmoqdan — keshlamaymiz
  if (req.mode === 'navigate' || accept.includes('text/html')) {
    e.respondWith(
      fetch(req).catch(() =>
        new Response('<meta charset="utf-8"><h2 style="font-family:sans-serif;text-align:center;margin-top:40px">Internet aloqasi yo’q</h2>',
          { headers: { 'Content-Type': 'text/html' } })
      )
    );
    return;
  }
  // Faqat statik resurslar (ikona/manifest): kesh, bo'lmasa tarmoq
  e.respondWith(caches.match(req).then(hit => hit || fetch(req)));
});
