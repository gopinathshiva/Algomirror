/**
 * Ping Monitoring Client-Side Script
 * Monitors account connection status and displays toast notifications
 */

class PingMonitorClient {
    constructor() {
        this.checkInterval = 10000; // 10 seconds for faster response
        this.intervalId = null;
        this.lastStatuses = {}; // Track previous statuses to avoid duplicate notifications
        this.isEnabled = true;
        
        this.init();
    }
    
    init() {
        // Only start monitoring if user is authenticated and on dashboard
        if (document.body.dataset.page === 'dashboard' && document.body.dataset.authenticated === 'true') {
            this.startMonitoring();
            
            // Listen for visibility changes to pause/resume monitoring
            document.addEventListener('visibilitychange', () => {
                if (document.hidden) {
                    this.pauseMonitoring();
                } else {
                    this.resumeMonitoring();
                }
            });
        }
    }
    
    startMonitoring() {
        if (this.intervalId) return; // Already monitoring
        
        // Initial check
        this.checkAccountStatuses();
        
        // Set up periodic checks
        this.intervalId = setInterval(() => {
            this.checkAccountStatuses();
        }, this.checkInterval);
        
        console.log('Ping monitoring started');
    }
    
    pauseMonitoring() {
        if (this.intervalId) {
            clearInterval(this.intervalId);
            this.intervalId = null;
            console.log('Ping monitoring paused');
        }
    }
    
    resumeMonitoring() {
        if (!this.intervalId && this.isEnabled) {
            this.startMonitoring();
            console.log('Ping monitoring resumed');
        }
    }
    
    stopMonitoring() {
        this.pauseMonitoring();
        this.isEnabled = false;
        console.log('Ping monitoring stopped');
    }
    
    async checkAccountStatuses() {
        try {
            const response = await fetchWithCSRF('/api/ping-status', {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            if (!response.ok) {
                console.error('Failed to fetch ping status:', response.statusText);
                return;
            }
            
            const data = await response.json();
            console.log('Ping status response:', data); // Debug logging
            
            if (data.status === 'success') {
                this.processStatusUpdate(data);
            } else {
                console.error('Ping status API error:', data.message);
            }
            
        } catch (error) {
            console.error('Error checking account statuses:', error);
        }
    }
    
    processStatusUpdate(statusData) {
        if (!statusData.accounts) {
            console.warn('No accounts data in status update:', statusData);
            return;
        }
        
        console.log(`Processing status update for ${statusData.accounts.length} accounts`);
        
        statusData.accounts.forEach(account => {
            const accountId = account.id;
            const currentStatus = account.status;
            const lastStatus = this.lastStatuses[accountId];
            
            // Check for status changes (including first-time status)
            if (lastStatus && lastStatus !== currentStatus) {
                this.handleStatusChange(account, lastStatus, currentStatus);
            } else if (!lastStatus && currentStatus !== 'connected') {
                // First time seeing this account and it's not connected
                console.log(`Initial status for account ${account.name}: ${currentStatus}`);
            }
            
            // Update stored status
            this.lastStatuses[accountId] = currentStatus;
        });
        
        // Update dashboard indicators if available
        this.updateDashboardIndicators(statusData);
    }
    
    handleStatusChange(account, oldStatus, newStatus) {
        const accountName = account.name || account.broker || `Account ${account.id}`;
        console.log(`Status change detected: ${accountName} from ${oldStatus} to ${newStatus}`);
        
        switch (newStatus) {
            case 'connected':
                if (oldStatus === 'failed' || oldStatus === 'error' || oldStatus === 'disconnected') {
                    this.showToast(
                        `✓ Connection restored: ${accountName}`,
                        'success'
                    );
                }
                break;
                
            case 'failed':
                this.showToast(
                    `✗ Connection failed: ${accountName}`,
                    'error'
                );
                break;
                
            case 'error':
                this.showToast(
                    `⚠ Connection error: ${accountName}`,
                    'warning'
                );
                break;
                
            case 'disconnected':
                this.showToast(
                    `⚠ Disconnected: ${accountName}`,
                    'warning'
                );
                break;
        }
    }
    
    updateDashboardIndicators(statusData) {
        // Update status indicators on dashboard
        const statusElement = document.querySelector('#connection-status-summary');
        if (statusElement) {
            const { total, connected, failed, error } = statusData;
            let statusClass = 'text-success';
            let statusText = 'All Connected';
            
            if (failed > 0 || error > 0) {
                statusClass = 'text-error';
                statusText = `${failed + error} Disconnected`;
            } else if (connected === 0) {
                statusClass = 'text-warning';
                statusText = 'No Accounts';
            }
            
            statusElement.className = `font-semibold ${statusClass}`;
            statusElement.textContent = `${connected}/${total} ${statusText}`;
        }
        
        // Update individual account indicators
        statusData.accounts.forEach(account => {
            const indicator = document.querySelector(`#account-status-${account.id}`);
            if (indicator) {
                const statusClass = this.getStatusClass(account.status);
                indicator.className = `w-3 h-3 rounded-full ${statusClass}`;
                indicator.title = `${account.name}: ${account.status}`;
            }
        });
    }
    
    getStatusClass(status) {
        switch (status) {
            case 'connected':
                return 'bg-success';
            case 'failed':
                return 'bg-error';
            case 'error':
                return 'bg-warning';
            default:
                return 'bg-gray-400';
        }
    }
    
    showToast(message, type = 'info') {
        // Use the global showToast function if available
        if (typeof showToast === 'function') {
            showToast(message, type);
            console.log(`Toast shown: [${type}] ${message}`);
        } else {
            console.log(`Toast: [${type}] ${message}`);
            // Fallback: create a simple alert-style notification
            const toast = document.createElement('div');
            toast.className = `alert alert-${type} shadow-lg fixed top-4 right-4 z-50 max-w-sm`;
            toast.innerHTML = `<span>${message}</span>`;
            document.body.appendChild(toast);
            setTimeout(() => toast.remove(), 5000);
        }
    }
    
    forceCheckAccount(accountId) {
        // Force immediate check for specific account
        fetchWithCSRF(`/api/accounts/${accountId}/ping`, {
            method: 'POST'
        }).then(response => {
            if (response.ok) {
                // Refresh status after force check
                setTimeout(() => this.checkAccountStatuses(), 1000);
            }
        }).catch(error => {
            console.error('Failed to force check account:', error);
        });
    }
    
    // Test function for debugging notifications
    testNotification(type = 'error') {
        const testMessages = {
            'success': '✓ Test connection restored: Test Account',
            'error': '✗ Test connection failed: Test Account', 
            'warning': '⚠ Test connection error: Test Account'
        };
        this.showToast(testMessages[type] || testMessages.error, type);
    }
}

// Initialize ping monitoring when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    // Only initialize if we're authenticated
    if (document.body.dataset.authenticated === 'true') {
        window.pingMonitor = new PingMonitorClient();
    }
});

// Export for global access
window.PingMonitorClient = PingMonitorClient;