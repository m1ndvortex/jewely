/**
 * POS Offline Mode Manager
 * 
 * Implements Requirement 35: Offline POS mode
 * - Manages online/offline status detection
 * - Handles offline transaction sync
 * - Provides conflict resolution for inventory
 * - Displays offline mode indicators
 * - Manages local data caching
 */

class POSOfflineManager {
    constructor() {
        this.isOnline = navigator.onLine;
        this.db = new POSIndexedDB();
        this.syncInProgress = false;
        this.offlineIndicatorVisible = false;
        this.pendingTransactions = [];
        this.conflictResolutions = [];
        
        // Configuration
        this.config = {
            syncRetryDelay: 5000, // 5 seconds
            maxSyncAttempts: 3,
            cacheRefreshInterval: 30000, // 30 seconds
            conflictResolutionTimeout: 60000 // 1 minute
        };
        
        // Event listeners
        this.eventListeners = new Map();
        
        this.init();
    }

    /**
     * Initialize offline manager
     */
    async init() {
        try {
            console.log('[POS Offline] Initializing offline manager...');
            
            // Initialize IndexedDB
            await this.db.init();
            
            // Register service worker
            await this.registerServiceWorker();
            
            // Set up event listeners
            this.setupEventListeners();
            
            // Initialize offline indicator
            this.initOfflineIndicator();
            
            // Load pending transactions
            await this.loadPendingTransactions();
            
            // Start periodic sync check
            this.startPeriodicSync();
            
            // Cache initial data if online
            if (this.isOnline) {
                await this.cacheEssentialData();
            }
            
            console.log('[POS Offline] Offline manager initialized successfully');
            
        } catch (error) {
            console.error('[POS Offline] Failed to initialize offline manager:', error);
            throw error;
        }
    }

    /**
     * Register service worker
     */
    async registerServiceWorker() {
        if ('serviceWorker' in navigator) {
            try {
                const registration = await navigator.serviceWorker.register('/static/js/pos-service-worker.js');
                console.log('[POS Offline] Service worker registered:', registration);
                
                // Listen for service worker messages
                navigator.serviceWorker.addEventListener('message', (event) => {
                    this.handleServiceWorkerMessage(event.data);
                });
                
                // Handle service worker updates
                registration.addEventListener('updatefound', () => {
                    console.log('[POS Offline] Service worker update found');
                });
                
                return registration;
                
            } catch (error) {
                console.error('[POS Offline] Service worker registration failed:', error);
                throw error;
            }
        } else {
            throw new Error('Service workers not supported');
        }
    }

    /**
     * Set up event listeners
     */
    setupEventListeners() {
        // Online/offline status
        window.addEventListener('online', () => {
            console.log('[POS Offline] Connection restored');
            this.handleOnlineStatusChange(true);
        });
        
        window.addEventListener('offline', () => {
            console.log('[POS Offline] Connection lost');
            this.handleOnlineStatusChange(false);
        });
        
        // Page visibility for sync triggers
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden && this.isOnline && this.pendingTransactions.length > 0) {
                this.syncPendingTransactions();
            }
        });
        
        // Before unload - ensure data is saved
        window.addEventListener('beforeunload', () => {
            // Sync any pending data
            if (this.pendingTransactions.length > 0) {
                navigator.sendBeacon('/api/pos/offline/beacon-sync/', 
                    JSON.stringify({ pending_count: this.pendingTransactions.length })
                );
            }
        });
    }

    /**
     * Handle online/offline status changes
     */
    async handleOnlineStatusChange(online) {
        const wasOnline = this.isOnline;
        this.isOnline = online;
        
        if (online && !wasOnline) {
            // Just came back online
            this.hideOfflineIndicator();
            await this.cacheEssentialData();
            await this.syncPendingTransactions();
            this.emit('online');
            
        } else if (!online && wasOnline) {
            // Just went offline
            this.showOfflineIndicator();
            this.emit('offline');
        }
        
        this.emit('statusChange', { online: this.isOnline });
    }

    /**
     * Handle messages from service worker
     */
    handleServiceWorkerMessage(data) {
        const { type, transaction } = data;
        
        switch (type) {
            case 'STORE_OFFLINE_TRANSACTION':
                this.storeOfflineTransaction(transaction);
                break;
                
            case 'OFFLINE_TRANSACTION_CREATED':
                this.handleOfflineTransactionCreated(transaction);
                break;
                
            case 'PROCESS_PENDING_TRANSACTIONS':
                this.syncPendingTransactions();
                break;
                
            case 'START_OFFLINE_SYNC':
                this.syncPendingTransactions();
                break;
        }
    }

    /**
     * Store offline transaction in IndexedDB
     */
    async storeOfflineTransaction(transaction) {
        try {
            await this.db.storeOfflineTransaction(transaction);
            this.pendingTransactions.push(transaction);
            this.updateOfflineIndicator();
            
            console.log('[POS Offline] Offline transaction stored:', transaction.id);
            this.emit('transactionStored', transaction);
            
        } catch (error) {
            console.error('[POS Offline] Failed to store offline transaction:', error);
            this.emit('error', { type: 'storage', error });
        }
    }

    /**
     * Handle offline transaction created
     */
    handleOfflineTransactionCreated(transaction) {
        console.log('[POS Offline] Offline transaction created:', transaction.id);
        
        // Show notification to user
        this.showOfflineTransactionNotification(transaction);
        
        // Emit event for UI updates
        this.emit('offlineTransactionCreated', transaction);
    }

    /**
     * Load pending transactions from IndexedDB
     */
    async loadPendingTransactions() {
        try {
            this.pendingTransactions = await this.db.getPendingTransactions();
            console.log(`[POS Offline] Loaded ${this.pendingTransactions.length} pending transactions`);
            
            if (this.pendingTransactions.length > 0) {
                this.updateOfflineIndicator();
            }
            
        } catch (error) {
            console.error('[POS Offline] Failed to load pending transactions:', error);
        }
    }

    /**
     * Sync pending transactions with server
     */
    async syncPendingTransactions() {
        if (this.syncInProgress || !this.isOnline || this.pendingTransactions.length === 0) {
            return;
        }
        
        this.syncInProgress = true;
        console.log(`[POS Offline] Starting sync of ${this.pendingTransactions.length} pending transactions`);
        
        try {
            const results = {
                success: 0,
                failed: 0,
                conflicts: 0
            };
            
            for (const transaction of this.pendingTransactions) {
                try {
                    await this.db.logSyncAttempt(transaction.id, 'started');
                    
                    const result = await this.syncSingleTransaction(transaction);
                    
                    if (result.success) {
                        await this.db.updateTransactionStatus(transaction.id, 'synced');
                        results.success++;
                        
                    } else if (result.conflict) {
                        await this.handleSyncConflict(transaction, result.conflictData);
                        results.conflicts++;
                        
                    } else {
                        await this.db.updateTransactionStatus(transaction.id, 'failed', result.error);
                        results.failed++;
                    }
                    
                } catch (error) {
                    console.error(`[POS Offline] Failed to sync transaction ${transaction.id}:`, error);
                    await this.db.updateTransactionStatus(transaction.id, 'failed', error.message);
                    results.failed++;
                }
            }
            
            // Reload pending transactions
            await this.loadPendingTransactions();
            
            console.log('[POS Offline] Sync completed:', results);
            this.emit('syncCompleted', results);
            
            // Update UI
            this.updateOfflineIndicator();
            
        } catch (error) {
            console.error('[POS Offline] Sync process failed:', error);
            this.emit('syncFailed', error);
            
        } finally {
            this.syncInProgress = false;
        }
    }

    /**
     * Sync single transaction with server
     */
    async syncSingleTransaction(transaction) {
        try {
            // First, validate inventory availability
            const validationResult = await this.validateInventoryForSync(transaction);
            
            if (!validationResult.valid) {
                return {
                    success: false,
                    conflict: true,
                    conflictData: validationResult
                };
            }
            
            // Attempt to create the sale on server
            const response = await fetch(transaction.url, {
                method: transaction.method,
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': transaction.headers.Authorization || '',
                    'X-CSRFToken': this.getCsrfToken(),
                    'X-Offline-Sync': 'true',
                    'X-Original-Transaction-Id': transaction.id
                },
                body: JSON.stringify(transaction.data)
            });
            
            if (response.ok) {
                const saleData = await response.json();
                
                await this.db.logSyncAttempt(transaction.id, 'success', {
                    server_sale_id: saleData.id,
                    server_sale_number: saleData.sale_number
                });
                
                return { success: true, saleData };
                
            } else {
                const errorData = await response.json();
                
                // Check if it's an inventory conflict
                if (response.status === 409 || errorData.code === 'INVENTORY_CONFLICT') {
                    return {
                        success: false,
                        conflict: true,
                        conflictData: errorData
                    };
                }
                
                await this.db.logSyncAttempt(transaction.id, 'failed', {
                    status: response.status,
                    error: errorData
                });
                
                return {
                    success: false,
                    error: errorData.detail || 'Server error'
                };
            }
            
        } catch (error) {
            console.error('[POS Offline] Network error during sync:', error);
            
            await this.db.logSyncAttempt(transaction.id, 'failed', {
                error: error.message
            });
            
            return {
                success: false,
                error: error.message
            };
        }
    }

    /**
     * Validate inventory availability for sync
     */
    async validateInventoryForSync(transaction) {
        try {
            const response = await fetch('/api/pos/offline/sync-validation/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': transaction.headers.Authorization || '',
                    'X-CSRFToken': this.getCsrfToken()
                },
                body: JSON.stringify({
                    transactions: [{
                        id: transaction.id,
                        items: transaction.data.items
                    }]
                })
            });
            
            if (response.ok) {
                const data = await response.json();
                const result = data.validation_results[0];
                
                return {
                    valid: result.valid,
                    items: result.conflicts.map(conflict => ({
                        inventory_item_id: conflict.inventory_item_id,
                        available: false,
                        available_quantity: conflict.available_quantity,
                        requested_quantity: conflict.requested_quantity,
                        error: `${conflict.conflict_type}: ${conflict.item_name} (${conflict.item_sku})`
                    }))
                };
            } else {
                throw new Error('Validation request failed');
            }
            
        } catch (error) {
            console.error('[POS Offline] Inventory validation failed:', error);
            return { valid: false, error: error.message };
        }
    }

    /**
     * Handle sync conflicts
     */
    async handleSyncConflict(transaction, conflictData) {
        console.log('[POS Offline] Handling sync conflict for transaction:', transaction.id);
        
        // Store conflict data
        for (const item of conflictData.items || []) {
            if (!item.available) {
                await this.db.storeConflictResolution(
                    transaction.id,
                    item.inventory_item_id,
                    item,
                    'pending_user_decision'
                );
            }
        }
        
        // Update transaction status
        await this.db.updateTransactionStatus(transaction.id, 'conflict', 'Inventory conflict detected');
        
        // Emit conflict event for UI handling
        this.emit('syncConflict', {
            transaction,
            conflictData
        });
        
        // Show conflict resolution UI
        this.showConflictResolutionDialog(transaction, conflictData);
    }

    /**
     * Cache essential data for offline use
     */
    async cacheEssentialData() {
        if (!this.isOnline) {
            return;
        }
        
        try {
            console.log('[POS Offline] Caching essential data...');
            
            // Cache recent inventory items
            await this.cacheInventoryData();
            
            // Cache recent customers
            await this.cacheCustomerData();
            
            console.log('[POS Offline] Essential data cached successfully');
            
        } catch (error) {
            console.error('[POS Offline] Failed to cache essential data:', error);
        }
    }

    /**
     * Cache inventory data
     */
    async cacheInventoryData() {
        try {
            const response = await fetch('/api/pos/search/products/?limit=1000');
            
            if (response.ok) {
                const data = await response.json();
                await this.db.cacheInventoryItems(data.results || []);
                
                // Also send to service worker for caching
                if (navigator.serviceWorker.controller) {
                    navigator.serviceWorker.controller.postMessage({
                        type: 'CACHE_PRODUCT_DATA',
                        data: data.results || []
                    });
                }
            }
            
        } catch (error) {
            console.error('[POS Offline] Failed to cache inventory data:', error);
        }
    }

    /**
     * Cache customer data
     */
    async cacheCustomerData() {
        try {
            const response = await fetch('/api/pos/search/customers/?limit=500');
            
            if (response.ok) {
                const data = await response.json();
                await this.db.cacheCustomers(data.results || []);
                
                // Also send to service worker for caching
                if (navigator.serviceWorker.controller) {
                    navigator.serviceWorker.controller.postMessage({
                        type: 'CACHE_CUSTOMER_DATA',
                        data: data.results || []
                    });
                }
            }
            
        } catch (error) {
            console.error('[POS Offline] Failed to cache customer data:', error);
        }
    }

    /**
     * Initialize offline indicator
     */
    initOfflineIndicator() {
        // Create offline indicator element
        const indicator = document.createElement('div');
        indicator.id = 'pos-offline-indicator';
        indicator.className = 'fixed top-0 left-0 right-0 bg-yellow-500 text-white text-center py-2 px-4 z-50 transform -translate-y-full transition-transform duration-300';
        indicator.innerHTML = `
            <div class="flex items-center justify-center space-x-2">
                <i class="fas fa-wifi-slash"></i>
                <span id="offline-indicator-text">Working offline</span>
                <span id="offline-pending-count" class="bg-yellow-600 px-2 py-1 rounded text-xs"></span>
            </div>
        `;
        
        document.body.appendChild(indicator);
        
        // Show indicator if currently offline
        if (!this.isOnline) {
            this.showOfflineIndicator();
        }
    }

    /**
     * Show offline indicator
     */
    showOfflineIndicator() {
        const indicator = document.getElementById('pos-offline-indicator');
        if (indicator) {
            indicator.classList.remove('-translate-y-full');
            this.offlineIndicatorVisible = true;
            this.updateOfflineIndicator();
        }
    }

    /**
     * Hide offline indicator
     */
    hideOfflineIndicator() {
        const indicator = document.getElementById('pos-offline-indicator');
        if (indicator) {
            indicator.classList.add('-translate-y-full');
            this.offlineIndicatorVisible = false;
        }
    }

    /**
     * Update offline indicator with pending transaction count
     */
    updateOfflineIndicator() {
        const countElement = document.getElementById('offline-pending-count');
        const textElement = document.getElementById('offline-indicator-text');
        
        if (countElement && textElement) {
            const pendingCount = this.pendingTransactions.length;
            
            if (pendingCount > 0) {
                countElement.textContent = `${pendingCount} pending`;
                countElement.style.display = 'inline';
                textElement.textContent = this.isOnline ? 'Syncing transactions...' : 'Working offline';
            } else {
                countElement.style.display = 'none';
                textElement.textContent = this.isOnline ? 'Online' : 'Working offline';
            }
        }
    }

    /**
     * Show offline transaction notification
     */
    showOfflineTransactionNotification(transaction) {
        // Create a temporary notification
        const notification = document.createElement('div');
        notification.className = 'fixed top-16 right-4 bg-blue-500 text-white p-4 rounded shadow-lg z-50 transform translate-x-full transition-transform duration-300';
        notification.innerHTML = `
            <div class="flex items-center space-x-2">
                <i class="fas fa-info-circle"></i>
                <div>
                    <div class="font-semibold">Transaction saved offline</div>
                    <div class="text-sm opacity-90">Will sync when connection is restored</div>
                </div>
            </div>
        `;
        
        document.body.appendChild(notification);
        
        // Animate in
        setTimeout(() => {
            notification.classList.remove('translate-x-full');
        }, 100);
        
        // Auto-hide after 5 seconds
        setTimeout(() => {
            notification.classList.add('translate-x-full');
            setTimeout(() => {
                document.body.removeChild(notification);
            }, 300);
        }, 5000);
    }

    /**
     * Show conflict resolution dialog
     */
    showConflictResolutionDialog(transaction, conflictData) {
        // This would show a modal dialog for user to resolve conflicts
        // For now, we'll just log and emit an event
        console.log('[POS Offline] Conflict resolution needed:', { transaction, conflictData });
        
        // Emit event for UI to handle
        this.emit('conflictResolutionNeeded', {
            transaction,
            conflictData
        });
    }

    /**
     * Start periodic sync check
     */
    startPeriodicSync() {
        setInterval(() => {
            if (this.isOnline && this.pendingTransactions.length > 0 && !this.syncInProgress) {
                this.syncPendingTransactions();
            }
        }, this.config.syncRetryDelay);
    }

    /**
     * Get CSRF token
     */
    getCsrfToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
    }

    /**
     * Event emitter functionality
     */
    on(event, callback) {
        if (!this.eventListeners.has(event)) {
            this.eventListeners.set(event, []);
        }
        this.eventListeners.get(event).push(callback);
    }

    off(event, callback) {
        if (this.eventListeners.has(event)) {
            const listeners = this.eventListeners.get(event);
            const index = listeners.indexOf(callback);
            if (index > -1) {
                listeners.splice(index, 1);
            }
        }
    }

    emit(event, data) {
        if (this.eventListeners.has(event)) {
            this.eventListeners.get(event).forEach(callback => {
                try {
                    callback(data);
                } catch (error) {
                    console.error(`[POS Offline] Event listener error for ${event}:`, error);
                }
            });
        }
    }

    /**
     * Get offline statistics
     */
    async getStats() {
        const dbStats = await this.db.getStats();
        
        return {
            isOnline: this.isOnline,
            pendingTransactions: this.pendingTransactions.length,
            syncInProgress: this.syncInProgress,
            dbStats: dbStats
        };
    }

    /**
     * Manual sync trigger
     */
    async forcSync() {
        if (this.isOnline) {
            await this.syncPendingTransactions();
        } else {
            throw new Error('Cannot sync while offline');
        }
    }

    /**
     * Clear offline data
     */
    async clearOfflineData() {
        await this.db.clearOldCache();
        console.log('[POS Offline] Offline data cleared');
    }

    /**
     * Cleanup and close
     */
    destroy() {
        this.db.close();
        
        // Remove event listeners
        window.removeEventListener('online', this.handleOnlineStatusChange);
        window.removeEventListener('offline', this.handleOnlineStatusChange);
        
        // Remove offline indicator
        const indicator = document.getElementById('pos-offline-indicator');
        if (indicator) {
            document.body.removeChild(indicator);
        }
        
        console.log('[POS Offline] Offline manager destroyed');
    }
}

// Export for global use
window.POSOfflineManager = POSOfflineManager;