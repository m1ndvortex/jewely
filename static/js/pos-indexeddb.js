/**
 * IndexedDB utilities for POS offline mode
 * 
 * Implements Requirement 35: IndexedDB for local transaction storage
 * - Stores offline transactions for later sync
 * - Manages local inventory cache
 * - Handles conflict resolution data
 * - Provides transaction history and status tracking
 */

class POSIndexedDB {
    constructor() {
        this.dbName = 'POSOfflineDB';
        this.dbVersion = 1;
        this.db = null;
        
        // Object store names
        this.stores = {
            TRANSACTIONS: 'offline_transactions',
            INVENTORY_CACHE: 'inventory_cache',
            CUSTOMER_CACHE: 'customer_cache',
            SYNC_LOG: 'sync_log',
            CONFLICT_RESOLUTION: 'conflict_resolution'
        };
    }

    /**
     * Initialize IndexedDB database
     */
    async init() {
        return new Promise((resolve, reject) => {
            const request = indexedDB.open(this.dbName, this.dbVersion);
            
            request.onerror = () => {
                console.error('[POS IndexedDB] Failed to open database:', request.error);
                reject(request.error);
            };
            
            request.onsuccess = () => {
                this.db = request.result;
                console.log('[POS IndexedDB] Database opened successfully');
                resolve(this.db);
            };
            
            request.onupgradeneeded = (event) => {
                const db = event.target.result;
                console.log('[POS IndexedDB] Upgrading database schema...');
                
                // Create offline transactions store
                if (!db.objectStoreNames.contains(this.stores.TRANSACTIONS)) {
                    const transactionStore = db.createObjectStore(this.stores.TRANSACTIONS, {
                        keyPath: 'id'
                    });
                    
                    transactionStore.createIndex('status', 'status', { unique: false });
                    transactionStore.createIndex('timestamp', 'timestamp', { unique: false });
                    transactionStore.createIndex('terminal_id', 'data.terminal_id', { unique: false });
                }
                
                // Create inventory cache store
                if (!db.objectStoreNames.contains(this.stores.INVENTORY_CACHE)) {
                    const inventoryStore = db.createObjectStore(this.stores.INVENTORY_CACHE, {
                        keyPath: 'id'
                    });
                    
                    inventoryStore.createIndex('sku', 'sku', { unique: false });
                    inventoryStore.createIndex('barcode', 'barcode', { unique: false });
                    inventoryStore.createIndex('branch_id', 'branch_id', { unique: false });
                    inventoryStore.createIndex('last_updated', 'last_updated', { unique: false });
                }
                
                // Create customer cache store
                if (!db.objectStoreNames.contains(this.stores.CUSTOMER_CACHE)) {
                    const customerStore = db.createObjectStore(this.stores.CUSTOMER_CACHE, {
                        keyPath: 'id'
                    });
                    
                    customerStore.createIndex('phone', 'phone', { unique: false });
                    customerStore.createIndex('email', 'email', { unique: false });
                    customerStore.createIndex('customer_number', 'customer_number', { unique: false });
                }
                
                // Create sync log store
                if (!db.objectStoreNames.contains(this.stores.SYNC_LOG)) {
                    const syncStore = db.createObjectStore(this.stores.SYNC_LOG, {
                        keyPath: 'id',
                        autoIncrement: true
                    });
                    
                    syncStore.createIndex('transaction_id', 'transaction_id', { unique: false });
                    syncStore.createIndex('timestamp', 'timestamp', { unique: false });
                    syncStore.createIndex('status', 'status', { unique: false });
                }
                
                // Create conflict resolution store
                if (!db.objectStoreNames.contains(this.stores.CONFLICT_RESOLUTION)) {
                    const conflictStore = db.createObjectStore(this.stores.CONFLICT_RESOLUTION, {
                        keyPath: 'id',
                        autoIncrement: true
                    });
                    
                    conflictStore.createIndex('transaction_id', 'transaction_id', { unique: false });
                    conflictStore.createIndex('inventory_item_id', 'inventory_item_id', { unique: false });
                    conflictStore.createIndex('resolution_status', 'resolution_status', { unique: false });
                }
                
                console.log('[POS IndexedDB] Database schema created successfully');
            };
        });
    }

    /**
     * Store offline transaction
     */
    async storeOfflineTransaction(transaction) {
        if (!this.db) {
            throw new Error('Database not initialized');
        }
        
        const tx = this.db.transaction([this.stores.TRANSACTIONS], 'readwrite');
        const store = tx.objectStore(this.stores.TRANSACTIONS);
        
        // Add metadata
        transaction.created_at = new Date().toISOString();
        transaction.last_attempt = null;
        transaction.error_message = null;
        
        return new Promise((resolve, reject) => {
            const request = store.add(transaction);
            
            request.onsuccess = () => {
                console.log('[POS IndexedDB] Offline transaction stored:', transaction.id);
                resolve(transaction);
            };
            
            request.onerror = () => {
                console.error('[POS IndexedDB] Failed to store transaction:', request.error);
                reject(request.error);
            };
        });
    }

    /**
     * Get all pending offline transactions
     */
    async getPendingTransactions() {
        if (!this.db) {
            throw new Error('Database not initialized');
        }
        
        const tx = this.db.transaction([this.stores.TRANSACTIONS], 'readonly');
        const store = tx.objectStore(this.stores.TRANSACTIONS);
        const index = store.index('status');
        
        return new Promise((resolve, reject) => {
            const request = index.getAll('pending');
            
            request.onsuccess = () => {
                const transactions = request.result.sort((a, b) => a.timestamp - b.timestamp);
                console.log(`[POS IndexedDB] Found ${transactions.length} pending transactions`);
                resolve(transactions);
            };
            
            request.onerror = () => {
                console.error('[POS IndexedDB] Failed to get pending transactions:', request.error);
                reject(request.error);
            };
        });
    }

    /**
     * Update transaction status
     */
    async updateTransactionStatus(transactionId, status, errorMessage = null) {
        if (!this.db) {
            throw new Error('Database not initialized');
        }
        
        const tx = this.db.transaction([this.stores.TRANSACTIONS], 'readwrite');
        const store = tx.objectStore(this.stores.TRANSACTIONS);
        
        return new Promise((resolve, reject) => {
            const getRequest = store.get(transactionId);
            
            getRequest.onsuccess = () => {
                const transaction = getRequest.result;
                if (!transaction) {
                    reject(new Error('Transaction not found'));
                    return;
                }
                
                transaction.status = status;
                transaction.last_attempt = new Date().toISOString();
                transaction.attempts = (transaction.attempts || 0) + 1;
                
                if (errorMessage) {
                    transaction.error_message = errorMessage;
                }
                
                const putRequest = store.put(transaction);
                
                putRequest.onsuccess = () => {
                    console.log(`[POS IndexedDB] Transaction ${transactionId} status updated to ${status}`);
                    resolve(transaction);
                };
                
                putRequest.onerror = () => {
                    console.error('[POS IndexedDB] Failed to update transaction:', putRequest.error);
                    reject(putRequest.error);
                };
            };
            
            getRequest.onerror = () => {
                console.error('[POS IndexedDB] Failed to get transaction:', getRequest.error);
                reject(getRequest.error);
            };
        });
    }

    /**
     * Cache inventory items for offline search
     */
    async cacheInventoryItems(items) {
        if (!this.db) {
            throw new Error('Database not initialized');
        }
        
        const tx = this.db.transaction([this.stores.INVENTORY_CACHE], 'readwrite');
        const store = tx.objectStore(this.stores.INVENTORY_CACHE);
        
        const promises = items.map(item => {
            return new Promise((resolve, reject) => {
                // Add cache metadata
                item.last_updated = new Date().toISOString();
                item.cached_at = Date.now();
                
                const request = store.put(item);
                
                request.onsuccess = () => resolve(item);
                request.onerror = () => reject(request.error);
            });
        });
        
        try {
            await Promise.all(promises);
            console.log(`[POS IndexedDB] Cached ${items.length} inventory items`);
            return items;
        } catch (error) {
            console.error('[POS IndexedDB] Failed to cache inventory items:', error);
            throw error;
        }
    }

    /**
     * Search cached inventory items
     */
    async searchCachedInventory(query, limit = 20) {
        if (!this.db) {
            throw new Error('Database not initialized');
        }
        
        const tx = this.db.transaction([this.stores.INVENTORY_CACHE], 'readonly');
        const store = tx.objectStore(this.stores.INVENTORY_CACHE);
        
        return new Promise((resolve, reject) => {
            const request = store.getAll();
            
            request.onsuccess = () => {
                const allItems = request.result;
                const queryLower = query.toLowerCase();
                
                // Filter items based on search query
                const filteredItems = allItems.filter(item => {
                    return (
                        item.sku?.toLowerCase().includes(queryLower) ||
                        item.name?.toLowerCase().includes(queryLower) ||
                        item.barcode === query ||
                        item.serial_number === query
                    );
                }).slice(0, limit);
                
                console.log(`[POS IndexedDB] Found ${filteredItems.length} cached inventory items for query: ${query}`);
                resolve(filteredItems);
            };
            
            request.onerror = () => {
                console.error('[POS IndexedDB] Failed to search cached inventory:', request.error);
                reject(request.error);
            };
        });
    }

    /**
     * Cache customer data for offline search
     */
    async cacheCustomers(customers) {
        if (!this.db) {
            throw new Error('Database not initialized');
        }
        
        const tx = this.db.transaction([this.stores.CUSTOMER_CACHE], 'readwrite');
        const store = tx.objectStore(this.stores.CUSTOMER_CACHE);
        
        const promises = customers.map(customer => {
            return new Promise((resolve, reject) => {
                // Add cache metadata
                customer.last_updated = new Date().toISOString();
                customer.cached_at = Date.now();
                
                const request = store.put(customer);
                
                request.onsuccess = () => resolve(customer);
                request.onerror = () => reject(request.error);
            });
        });
        
        try {
            await Promise.all(promises);
            console.log(`[POS IndexedDB] Cached ${customers.length} customers`);
            return customers;
        } catch (error) {
            console.error('[POS IndexedDB] Failed to cache customers:', error);
            throw error;
        }
    }

    /**
     * Search cached customers
     */
    async searchCachedCustomers(query, limit = 10) {
        if (!this.db) {
            throw new Error('Database not initialized');
        }
        
        const tx = this.db.transaction([this.stores.CUSTOMER_CACHE], 'readonly');
        const store = tx.objectStore(this.stores.CUSTOMER_CACHE);
        
        return new Promise((resolve, reject) => {
            const request = store.getAll();
            
            request.onsuccess = () => {
                const allCustomers = request.result;
                const queryLower = query.toLowerCase();
                
                // Filter customers based on search query
                const filteredCustomers = allCustomers.filter(customer => {
                    return (
                        customer.first_name?.toLowerCase().includes(queryLower) ||
                        customer.last_name?.toLowerCase().includes(queryLower) ||
                        customer.phone?.includes(query) ||
                        customer.email?.toLowerCase().includes(queryLower) ||
                        customer.customer_number?.toLowerCase().includes(queryLower)
                    );
                }).slice(0, limit);
                
                console.log(`[POS IndexedDB] Found ${filteredCustomers.length} cached customers for query: ${query}`);
                resolve(filteredCustomers);
            };
            
            request.onerror = () => {
                console.error('[POS IndexedDB] Failed to search cached customers:', request.error);
                reject(request.error);
            };
        });
    }

    /**
     * Log sync attempt
     */
    async logSyncAttempt(transactionId, status, details = {}) {
        if (!this.db) {
            throw new Error('Database not initialized');
        }
        
        const tx = this.db.transaction([this.stores.SYNC_LOG], 'readwrite');
        const store = tx.objectStore(this.stores.SYNC_LOG);
        
        const logEntry = {
            transaction_id: transactionId,
            status: status, // 'started', 'success', 'failed', 'conflict'
            timestamp: new Date().toISOString(),
            details: details
        };
        
        return new Promise((resolve, reject) => {
            const request = store.add(logEntry);
            
            request.onsuccess = () => {
                console.log(`[POS IndexedDB] Sync log entry created for transaction ${transactionId}`);
                resolve(logEntry);
            };
            
            request.onerror = () => {
                console.error('[POS IndexedDB] Failed to create sync log entry:', request.error);
                reject(request.error);
            };
        });
    }

    /**
     * Store conflict resolution data
     */
    async storeConflictResolution(transactionId, inventoryItemId, conflictData, resolution) {
        if (!this.db) {
            throw new Error('Database not initialized');
        }
        
        const tx = this.db.transaction([this.stores.CONFLICT_RESOLUTION], 'readwrite');
        const store = tx.objectStore(this.stores.CONFLICT_RESOLUTION);
        
        const conflictEntry = {
            transaction_id: transactionId,
            inventory_item_id: inventoryItemId,
            conflict_data: conflictData,
            resolution: resolution,
            resolution_status: 'pending', // 'pending', 'resolved', 'failed'
            created_at: new Date().toISOString(),
            resolved_at: null
        };
        
        return new Promise((resolve, reject) => {
            const request = store.add(conflictEntry);
            
            request.onsuccess = () => {
                console.log(`[POS IndexedDB] Conflict resolution stored for transaction ${transactionId}`);
                resolve(conflictEntry);
            };
            
            request.onerror = () => {
                console.error('[POS IndexedDB] Failed to store conflict resolution:', request.error);
                reject(request.error);
            };
        });
    }

    /**
     * Get transaction history for display
     */
    async getTransactionHistory(limit = 50) {
        if (!this.db) {
            throw new Error('Database not initialized');
        }
        
        const tx = this.db.transaction([this.stores.TRANSACTIONS], 'readonly');
        const store = tx.objectStore(this.stores.TRANSACTIONS);
        const index = store.index('timestamp');
        
        return new Promise((resolve, reject) => {
            const request = index.openCursor(null, 'prev'); // Newest first
            const transactions = [];
            let count = 0;
            
            request.onsuccess = (event) => {
                const cursor = event.target.result;
                
                if (cursor && count < limit) {
                    transactions.push(cursor.value);
                    count++;
                    cursor.continue();
                } else {
                    console.log(`[POS IndexedDB] Retrieved ${transactions.length} transaction history entries`);
                    resolve(transactions);
                }
            };
            
            request.onerror = () => {
                console.error('[POS IndexedDB] Failed to get transaction history:', request.error);
                reject(request.error);
            };
        });
    }

    /**
     * Clear old cached data to free up space
     */
    async clearOldCache(maxAge = 7 * 24 * 60 * 60 * 1000) { // 7 days default
        if (!this.db) {
            throw new Error('Database not initialized');
        }
        
        const cutoffTime = Date.now() - maxAge;
        const stores = [this.stores.INVENTORY_CACHE, this.stores.CUSTOMER_CACHE];
        
        for (const storeName of stores) {
            const tx = this.db.transaction([storeName], 'readwrite');
            const store = tx.objectStore(storeName);
            
            await new Promise((resolve, reject) => {
                const request = store.getAll();
                
                request.onsuccess = () => {
                    const items = request.result;
                    const oldItems = items.filter(item => item.cached_at < cutoffTime);
                    
                    if (oldItems.length > 0) {
                        const deletePromises = oldItems.map(item => {
                            return new Promise((deleteResolve, deleteReject) => {
                                const deleteRequest = store.delete(item.id);
                                deleteRequest.onsuccess = () => deleteResolve();
                                deleteRequest.onerror = () => deleteReject(deleteRequest.error);
                            });
                        });
                        
                        Promise.all(deletePromises)
                            .then(() => {
                                console.log(`[POS IndexedDB] Cleared ${oldItems.length} old items from ${storeName}`);
                                resolve();
                            })
                            .catch(reject);
                    } else {
                        resolve();
                    }
                };
                
                request.onerror = () => reject(request.error);
            });
        }
    }

    /**
     * Get database statistics
     */
    async getStats() {
        if (!this.db) {
            throw new Error('Database not initialized');
        }
        
        const stats = {};
        
        for (const [key, storeName] of Object.entries(this.stores)) {
            const tx = this.db.transaction([storeName], 'readonly');
            const store = tx.objectStore(storeName);
            
            stats[key] = await new Promise((resolve, reject) => {
                const request = store.count();
                
                request.onsuccess = () => resolve(request.result);
                request.onerror = () => reject(request.error);
            });
        }
        
        console.log('[POS IndexedDB] Database statistics:', stats);
        return stats;
    }

    /**
     * Close database connection
     */
    close() {
        if (this.db) {
            this.db.close();
            this.db = null;
            console.log('[POS IndexedDB] Database connection closed');
        }
    }
}

// Export for use in other modules
window.POSIndexedDB = POSIndexedDB;