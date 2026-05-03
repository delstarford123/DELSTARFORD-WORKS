const CACHE_NAME = 'dsw-enterprise-cache-v1';

// Core assets to cache immediately upon installation
const CORE_ASSETS = [
    '/',
    '/about',
    '/services',
    '/static/css/style.css',
    '/static/images/logo.png',
    'https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap'
];

// 1. Install Event: Cache Core Assets
self.addEventListener('install', (event) => {
    self.skipWaiting(); // Force the waiting service worker to become the active service worker.
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            console.log('[Service Worker] Caching Core Assets');
            return cache.addAll(CORE_ASSETS);
        })
    );
});

// 2. Activate Event: Clean up old caches
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    if (cacheName !== CACHE_NAME) {
                        console.log('[Service Worker] Deleting Old Cache:', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        })
    );
    self.clients.claim();
});

// 3. Fetch Event: Network First, Fallback to Cache Strategy
self.addEventListener('fetch', (event) => {
    // Ignore API requests and Firebase auth requests (do not cache sensitive db calls)
    if (event.request.url.includes('/api/') || event.request.url.includes('firestore') || event.request.method !== 'GET') {
        return;
    }

    event.respondWith(
        fetch(event.request)
            .then((networkResponse) => {
                // If network fetch is successful, clone the response and update the cache
                return caches.open(CACHE_NAME).then((cache) => {
                    cache.put(event.request, networkResponse.clone());
                    return networkResponse;
                });
            })
            .catch(() => {
                // If network fails (offline), return from cache
                console.log('[Service Worker] Network failed, serving from cache:', event.request.url);
                return caches.match(event.request);
            })
    );
});