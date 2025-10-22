/**
 * Service Worker for POS Offline Mode
 * 
 * Implements Requirement 35: Offline POS mode
 * - Caches essential POS resources for offline operation
 * - Handles offline transaction storage
 * - Manages background sync for offline transactions
 * - Provides offline/online status detection
 */

const CACHE_NAME = 'pos-offline-v1';
const OFFLINE_CACHE_NAME = 'pos-offline-data-v1';

// Essential resources to cache for offline POS operation
const ESSENTIAL_RESOURCES = [
    '/pos/',
    '/static/css/tailwind.min.css',
    '/static/js/alpine.min.js',
    '/static/js/htmx.min.js',
    '/static/js/pos-offline.js',
    '/static/js/pos-indexeddb.js',
    '/static/fonts/fontawesome-webfont.woff2',
    // Add other essential static resources
];

// API endpoints that should work offline (with cached responses)
const OFFLINE_API_PATTERNS = [
    /^\/api\/pos\/search\/products\//,
    /^\/api\/pos\/search\/customers\//,
    /^\/api\/pos\/terminals\//,
    /^\/api\/pos\/calculate-totals\//,
    /^\/api\/pos\/validate-inventory\//,
];

// Install event - cache essential resources
self.addEventListener('install', event => {
    console.log('[POS SW] Installing service worker...');
    
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => {
                console.log('[POS SW] Caching essential resources');
                return cache.addAll(ESSENTIAL_RESOURCES);
            })
            .then(() => {
                console.log('[POS SW] Service worker installed successfully');
                return self.skipWaiting();
            })
            .catch(error => {
                console.error('[POS SW] Failed to cache resources:', error);
            })
    );
});

// Activate event - clean up old caches
self.addEventListener('activate', event => {
    console.log('[POS SW] Activating service worker...');
    
    event.waitUntil(
        caches.keys()
            .then(cacheNames => {
                return Promise.all(
                    cacheNames.map(cacheName => {
                        if (cacheName !== CACHE_NAME && cacheName !== OFFLINE_CACHE_NAME) {
                            console.log('[POS SW] Deleting old cache:', cacheName);
                            return caches.delete(cacheName);
                        }
                    })
                );
            })
            .then(() => {
                console.log('[POS SW] Service worker activated');
                return self.clients.claim();
            })
    );
});

// Fetch event - handle offline requests
self.addEventListener('fetch', event => {
    const request = event.request;
    const url = new URL(request.url);
    
    // Handle POS API requests
    if (url.pathname.startsWith('/api/pos/')) {
        event.respondWith(handlePOSApiRequest(request));
        return;
    }
    
    // Handle essential resources with cache-first strategy
    if (ESSENTIAL_RESOURCES.some(resource => url.pathname.includes(resource))) {
        event.respondWith(handleCacheFirst(request));
        return;
    }
    
    // Handle other requests with network-first strategy
    event.respondWith(handleNetworkFirst(request));
});

/**
 * Handle POS API requests with offline support
 */
async function handlePOSApiRequest(request) {
    const url = new URL(request.url);
    
    try {
        // Try network first
        const response = await fetch(request);
        
        // Cache successful GET responses for offline use
        if (request.method === 'GET' && response.ok) {
            const cache = await caches.open(OFFLINE_CACHE_NAME);
            await cache.put(request, response.clone());
        }
        
        // Handle POST requests (sales creation) when online
        if (request.method === 'POST' && url.pathname === '/api/pos/sales/create/') {
            // Process any pending offline transactions first
            await processPendingOfflineTransactions();
        }
        
        return response;
        
    } catch (error) {
        console.log('[POS SW] Network request failed, trying offline handling:', error);
        
        // Handle offline scenarios
        if (request.method === 'GET') {
            return handleOfflineGetRequest(request);
        } else if (request.method === 'POST') {
            return handleOfflinePostRequest(request);
        }
        
        // Return offline response for unsupported methods
        return new Response(
            JSON.stringify({ 
                error: 'Offline mode', 
                message: 'This operation is not available offline' 
            }),
            { 
                status: 503, 
                headers: { 'Content-Type': 'application/json' } 
            }
        );
    }
}

/**
 * Handle offline GET requests using cached data
 */
async function handleOfflineGetRequest(request) {
    const cache = await caches.open(OFFLINE_CACHE_NAME);
    const cachedResponse = await cache.match(request);
    
    if (cachedResponse) {
        console.log('[POS SW] Serving cached response for:', request.url);
        return cachedResponse;
    }
    
    // Return empty results for search endpoints
    const url = new URL(request.url);
    if (url.pathname.includes('/search/')) {
        return new Response(
            JSON.stringify({ results: [] }),
            { 
                status: 200, 
                headers: { 'Content-Type': 'application/json' } 
            }
        );
    }
    
    // Return offline error for other endpoints
    return new Response(
        JSON.stringify({ 
            error: 'Offline mode', 
            message: 'No cached data available' 
        }),
        { 
            status: 503, 
            headers: { 'Content-Type': 'application/json' } 
        }
    );
}

/**
 * Handle offline POST requests by storing them for later sync
 */
async function handleOfflinePostRequest(request) {
    const url = new URL(request.url);
    
    // Handle sale creation offline
    if (url.pathname === '/api/pos/sales/create/') {
        try {
            const requestData = await request.json();
            
            // Store transaction in IndexedDB for later sync
            const offlineTransaction = {
                id: generateOfflineTransactionId(),
                url: request.url,
                method: request.method,
                headers: Object.fromEntries(request.headers.entries()),
                data: requestData,
                timestamp: Date.now(),
                status: 'pending',
                attempts: 0
            };
            
            // Store in IndexedDB (will be handled by pos-indexeddb.js)
            await storeOfflineTransaction(offlineTransaction);
            
            // Generate offline sale response
            const offlineSale = generateOfflineSaleResponse(requestData, offlineTransaction.id);
            
            // Notify client about offline mode
            await notifyClientsOfflineTransaction(offlineTransaction);
            
            return new Response(
                JSON.stringify(offlineSale),
                { 
                    status: 201, 
                    headers: { 
                        'Content-Type': 'application/json',
                        'X-Offline-Mode': 'true',
                        'X-Transaction-Id': offlineTransaction.id
                    } 
                }
            );
            
        } catch (error) {
            console.error('[POS SW] Failed to handle offline sale:', error);
            return new Response(
                JSON.stringify({ 
                    error: 'Offline storage failed', 
                    message: 'Unable to store transaction for later sync' 
                }),
                { 
                    status: 500, 
                    headers: { 'Content-Type': 'application/json' } 
                }
            );
        }
    }
    
    // For other POST requests, return offline error
    return new Response(
        JSON.stringify({ 
            error: 'Offline mode', 
            message: 'This operation requires internet connection' 
        }),
        { 
            status: 503, 
            headers: { 'Content-Type': 'application/json' } 
        }
    );
}

/**
 * Cache-first strategy for essential resources
 */
async function handleCacheFirst(request) {
    const cache = await caches.open(CACHE_NAME);
    const cachedResponse = await cache.match(request);
    
    if (cachedResponse) {
        return cachedResponse;
    }
    
    try {
        const response = await fetch(request);
        if (response.ok) {
            await cache.put(request, response.clone());
        }
        return response;
    } catch (error) {
        console.error('[POS SW] Cache-first fetch failed:', error);
        throw error;
    }
}

/**
 * Network-first strategy for other resources
 */
async function handleNetworkFirst(request) {
    try {
        const response = await fetch(request);
        return response;
    } catch (error) {
        const cache = await caches.open(CACHE_NAME);
        const cachedResponse = await cache.match(request);
        
        if (cachedResponse) {
            return cachedResponse;
        }
        
        throw error;
    }
}

/**
 * Generate unique ID for offline transactions
 */
function generateOfflineTransactionId() {
    return 'offline_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
}

/**
 * Generate offline sale response that mimics online response
 */
function generateOfflineSaleResponse(requestData, transactionId) {
    const now = new Date().toISOString();
    
    return {
        id: transactionId,
        sale_number: `OFFLINE_${Date.now()}`,
        customer: requestData.customer_id ? { id: requestData.customer_id } : null,
        terminal: { id: requestData.terminal_id },
        items: requestData.items.map((item, index) => ({
            id: `offline_item_${index}`,
            inventory_item: { id: item.inventory_item_id },
            quantity: item.quantity,
            unit_price: item.unit_price,
            subtotal: (parseFloat(item.unit_price) * item.quantity).toFixed(2)
        })),
        subtotal: requestData.items.reduce((sum, item) => 
            sum + (parseFloat(item.unit_price) * item.quantity), 0
        ).toFixed(2),
        tax: "0.00", // Will be calculated on sync
        discount: requestData.discount_value || "0.00",
        total: requestData.items.reduce((sum, item) => 
            sum + (parseFloat(item.unit_price) * item.quantity), 0
        ).toFixed(2),
        payment_method: requestData.payment_method,
        status: 'OFFLINE_PENDING',
        created_at: now,
        updated_at: now,
        offline_mode: true,
        sync_status: 'pending'
    };
}

/**
 * Store offline transaction in IndexedDB
 */
async function storeOfflineTransaction(transaction) {
    // This will be implemented in pos-indexeddb.js
    // For now, we'll use a simple message to the main thread
    const clients = await self.clients.matchAll();
    clients.forEach(client => {
        client.postMessage({
            type: 'STORE_OFFLINE_TRANSACTION',
            transaction: transaction
        });
    });
}

/**
 * Notify clients about offline transaction
 */
async function notifyClientsOfflineTransaction(transaction) {
    const clients = await self.clients.matchAll();
    clients.forEach(client => {
        client.postMessage({
            type: 'OFFLINE_TRANSACTION_CREATED',
            transaction: transaction
        });
    });
}

/**
 * Process pending offline transactions when back online
 */
async function processPendingOfflineTransactions() {
    const clients = await self.clients.matchAll();
    clients.forEach(client => {
        client.postMessage({
            type: 'PROCESS_PENDING_TRANSACTIONS'
        });
    });
}

// Background sync for offline transactions
self.addEventListener('sync', event => {
    console.log('[POS SW] Background sync triggered:', event.tag);
    
    if (event.tag === 'pos-offline-sync') {
        event.waitUntil(syncOfflineTransactions());
    }
});

/**
 * Sync offline transactions with server
 */
async function syncOfflineTransactions() {
    console.log('[POS SW] Starting offline transaction sync...');
    
    try {
        // Notify clients to start sync process
        const clients = await self.clients.matchAll();
        clients.forEach(client => {
            client.postMessage({
                type: 'START_OFFLINE_SYNC'
            });
        });
        
        console.log('[POS SW] Offline sync initiated');
        
    } catch (error) {
        console.error('[POS SW] Offline sync failed:', error);
    }
}

// Handle messages from main thread
self.addEventListener('message', event => {
    const { type, data } = event.data;
    
    switch (type) {
        case 'SKIP_WAITING':
            self.skipWaiting();
            break;
            
        case 'REGISTER_SYNC':
            // Register background sync
            self.registration.sync.register('pos-offline-sync')
                .then(() => {
                    console.log('[POS SW] Background sync registered');
                })
                .catch(error => {
                    console.error('[POS SW] Failed to register background sync:', error);
                });
            break;
            
        case 'CACHE_PRODUCT_DATA':
            // Cache product data for offline use
            cacheProductData(data);
            break;
            
        case 'CACHE_CUSTOMER_DATA':
            // Cache customer data for offline use
            cacheCustomerData(data);
            break;
    }
});

/**
 * Cache product data for offline search
 */
async function cacheProductData(products) {
    try {
        const cache = await caches.open(OFFLINE_CACHE_NAME);
        
        // Create a synthetic request/response for product data
        const request = new Request('/api/pos/offline/products');
        const response = new Response(
            JSON.stringify({ results: products }),
            { 
                status: 200, 
                headers: { 'Content-Type': 'application/json' } 
            }
        );
        
        await cache.put(request, response);
        console.log('[POS SW] Cached product data for offline use');
        
    } catch (error) {
        console.error('[POS SW] Failed to cache product data:', error);
    }
}

/**
 * Cache customer data for offline search
 */
async function cacheCustomerData(customers) {
    try {
        const cache = await caches.open(OFFLINE_CACHE_NAME);
        
        // Create a synthetic request/response for customer data
        const request = new Request('/api/pos/offline/customers');
        const response = new Response(
            JSON.stringify({ results: customers }),
            { 
                status: 200, 
                headers: { 'Content-Type': 'application/json' } 
            }
        );
        
        await cache.put(request, response);
        console.log('[POS SW] Cached customer data for offline use');
        
    } catch (error) {
        console.error('[POS SW] Failed to cache customer data:', error);
    }
}

console.log('[POS SW] Service worker script loaded');