// dashboard.js - Main dashboard functionality for Yumi Sugoi Bot
"use strict";

// Global variables for chart instances and configuration
const CONFIG = {
    UPDATE_INTERVAL: 30000, // 30 seconds
    RETRY_DELAY: 5000,     // 5 seconds
    MAX_RETRIES: 3
};

// Chart instances
let serverActivityChart = null;
let commandUsageChart = null;
let messageVolumeChart = null;

// Debug function to check DOM state
function debugDOMState() {
    console.log('DOM Debug Check:');
    console.log('Document ready state:', document.readyState);
    console.log('Body exists:', !!document.body);
    console.log('activityChart element:', document.getElementById('activityChart'));
    console.log('Overview tab element:', document.getElementById('overview'));
    console.log('All canvas elements:', document.querySelectorAll('canvas'));
}

// WebSocket connection handling
class WebSocketManager {
    constructor(endpoint) {
        this.endpoint = endpoint;
        this.socket = null;
        this.reconnectAttempts = 0;
        this.isConnecting = false;
        this.reconnectTimer = null;
        this.maxReconnectDelay = 30000; // Maximum delay between reconnection attempts (30 seconds)
    }

    connect() {
        if (this.isConnecting) return;
        this.isConnecting = true;

        try {
            this.socket = new WebSocket(this.endpoint);
            
            this.socket.onopen = () => {
                console.log('📡 WebSocket connected');
                this.reconnectAttempts = 0;
                this.isConnecting = false;
                showToast('Real-time updates connected', 'success');
                
                // Clear any existing reconnection timer
                if (this.reconnectTimer) {
                    clearTimeout(this.reconnectTimer);
                    this.reconnectTimer = null;
                }
            };            this.socket.onclose = (event) => {
                console.log(`WebSocket disconnected (code: ${event.code})`);
                this.isConnecting = false;
                
                // Don't reconnect if the connection was closed cleanly
                if (event.code === 1000 || event.code === 1001) {
                    console.log('Clean WebSocket disconnect, not reconnecting');
                    return;
                }

                // Calculate reconnection delay with exponential backoff
                const delay = Math.min(
                    1000 * Math.pow(2, this.reconnectAttempts),
                    this.maxReconnectDelay
                );
                
                if (this.reconnectAttempts < CONFIG.MAX_RETRIES) {
                    console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts + 1}/${CONFIG.MAX_RETRIES})`);
                    this.reconnectTimer = setTimeout(() => this.connect(), delay);
                    this.reconnectAttempts++;                } else {
                    console.log('Max reconnection attempts reached, falling back to polling');
                    showToast('Real-time updates disconnected. Falling back to polling.', 'warning');
                    setupPolling();
                }
            };

            this.socket.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.isConnecting = false;
                
                // Log additional error details if available
                if (error.message) {
                    console.error('Error details:', error.message);
                }
            };

            this.socket.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    if (data && typeof data === 'object') {
                        handleRealtimeUpdate(data);
                    } else {
                        console.warn('Received invalid data format:', data);
                    }
                } catch (error) {
                    console.error('Error processing WebSocket message:', error);
                    showToast('Failed to process real-time update', 'danger');
                }
            };

        } catch (error) {
            console.error('Failed to create WebSocket:', error);
            this.isConnecting = false;
            setupPolling();
        }
    }

    send(data) {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            try {
                this.socket.send(JSON.stringify(data));
            } catch (error) {
                console.error('Failed to send WebSocket message:', error);
                showToast('Failed to send update', 'danger');
            }
        } else {
            console.warn('Cannot send message - WebSocket is not open');
        }
    }

    disconnect() {
        if (this.socket) {
            this.socket.close(1000, 'Disconnecting');
        }
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
    }
}

// Initialize components and tooltips
function initializeComponents() {
    // Initialize Bootstrap tooltips
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    if (tooltipTriggerList.length > 0) {
        tooltipTriggerList.forEach(tooltipTriggerEl => {
            new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }

    // Initialize Bootstrap popovers
    const popoverTriggerList = document.querySelectorAll('[data-bs-toggle="popover"]');
    if (popoverTriggerList.length > 0) {
        popoverTriggerList.forEach(popoverTriggerEl => {
            new bootstrap.Popover(popoverTriggerEl);
        });
    }

    // Setup tab change event listeners
    const tabList = document.querySelectorAll('button[data-bs-toggle="tab"]');
    tabList.forEach(tabEl => {
        tabEl.addEventListener('shown.bs.tab', event => {
            const targetId = event.target.getAttribute('data-bs-target');
            loadTabContent(targetId);
        });
    });

    // Setup other event listeners
    document.getElementById('refreshData')?.addEventListener('click', (e) => {
        e.preventDefault();
        refreshDashboard();
    });

    document.getElementById('botRestart')?.addEventListener('click', async (e) => {
        e.preventDefault();
        if (confirm('Are you sure you want to restart the bot?')) {
            await handleBotRestart();
        }
    });

    document.getElementById('botUpdate')?.addEventListener('click', async (e) => {
        e.preventDefault();
        await checkForUpdates();
    });    // Initialize charts
    initializeCharts();
}

// Toast notification system
function showToast(message, type = 'success') {
    const toastContainer = document.getElementById('toast-container') || createToastContainer();

    const toast = document.createElement('div');
    toast.className = `toast show border-${type}`;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');
    toast.setAttribute('aria-atomic', 'true');

    const icon = type === 'success' ? '✅' : type === 'warning' ? '⚠️' : type === 'info' ? 'ℹ️' : '❌';

    toast.innerHTML = `
        <div class="toast-header">
            <span class="me-1">${icon}</span>
            <strong class="me-auto">${type.charAt(0).toUpperCase() + type.slice(1)}</strong>
            <button type="button" class="btn-close" data-bs-dismiss="toast"></button>
        </div>
        <div class="toast-body">${message}</div>
    `;

    toastContainer.appendChild(toast);

    setTimeout(() => {
        toast.remove();
    }, 5000);
}

// Create toast container if it doesn't exist
function createToastContainer() {
    const container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
    document.body.appendChild(container);
    return container;
}

// Fetch API wrapper with retries and error handling
async function fetchApi(endpoint, options = {}) {
    let attempts = 0;
    const maxRetries = CONFIG.MAX_RETRIES;
    
    while (attempts < maxRetries) {
        try {
            // Ensure endpoint starts with /
            if (!endpoint.startsWith('/')) {
                endpoint = '/' + endpoint;
            }

            // Add default headers
            const headers = {
                'Content-Type': 'application/json',
                ...options.headers
            };

            // Make the request
            const response = await fetch(endpoint, {
                ...options,
                headers
            });

            // Check if response is ok
            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`API returned ${response.status}: ${errorText}`);
            }

            // Parse and return JSON
            const data = await response.json();
            return data;

        } catch (error) {
            attempts++;
            console.error(`Attempt ${attempts}/${maxRetries} failed for ${endpoint}:`, error);
            
            if (attempts === maxRetries) {
                showToast(`Failed to fetch ${endpoint.split('/').pop()}: ${error.message}`, 'danger');
                throw error;
            }
            
            // Wait before retrying
            await new Promise(resolve => setTimeout(resolve, CONFIG.RETRY_DELAY * attempts));
        }
    }
}

// Load content based on active tab
async function loadTabContent(tabId) {
    try {
        switch (tabId) {
            case '#overview':
                await loadOverviewTab();
                break;
            case '#personas':
                await loadPersonasTab();
                break;
            case '#servers':
                await loadServersTab();
                break;
            case '#users':
                await loadUsersTab();
                break;
            case '#moderation':
                await loadModerationTab();
                break;
            case '#analytics':
                await loadAnalyticsTab();
                break;
            case '#livechat':
                await loadLiveChatTab();
                break;
            case '#scheduled':
                await loadScheduledTab();
                break;
            case '#settings':
                await loadSettingsTab();
                break;
        }
    } catch (error) {
        console.error('Error loading tab content:', error);
        showToast(`Failed to load ${tabId.substring(1)} content`, 'danger');
    }
}

// Dashboard data refresh
async function refreshDashboard() {
    const refreshButton = document.getElementById('refreshData');
    if (refreshButton) {
        refreshButton.disabled = true;
        refreshButton.innerHTML = '<i class="fas fa-spin fa-spinner me-1"></i> Refreshing...';
    }

    try {
        await Promise.all([
            loadDashboardOverview(),
            updateCharts(),
            loadActiveServers()
        ]);
        showToast('Dashboard updated successfully', 'success');
    } catch (error) {
        console.error('Error refreshing dashboard:', error);
        showToast('Failed to refresh dashboard', 'danger');
    } finally {
        if (refreshButton) {
            refreshButton.disabled = false;
            refreshButton.innerHTML = '<i class="fas fa-sync-alt me-1"></i> Refresh Data';
        }
    }
}

// Load dashboard overview statistics
async function loadDashboardOverview() {
    try {
        const loadingIndicators = ['server-count', 'user-count', 'message-count', 'persona-count'];
        loadingIndicators.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.innerHTML = '<div class="spinner-border spinner-border-sm" role="status"></div>';
        });

        // Try to fetch from overview/stats as a fallback for the analytics endpoint
        let analyticsData;
        try {
            // First try the original endpoint
            analyticsData = await fetchApi('/api/analytics');
            console.log('Analytics data received from /api/analytics:', analyticsData);
        } catch (error) {
            console.warn('Failed to load from /api/analytics, trying fallback endpoint');
            // Use the fallback endpoint if the original fails
            analyticsData = await fetchApi('/api/overview/stats');
            console.log('Analytics data received from fallback endpoint:', analyticsData);
        }
        
        // Update statistics with animation, handling different API response formats
        // and ensuring fallbacks for missing values
        updateStatWithAnimation('server-count', 
            analyticsData.server_count || 
            (analyticsData.overview && analyticsData.overview.total_servers) || 0);
            
        updateStatWithAnimation('user-count', 
            analyticsData.total_users || 
            (analyticsData.overview && analyticsData.overview.total_users) || 0);
            
        updateStatWithAnimation('message-count', 
            analyticsData.message_count || 
            (analyticsData.overview && analyticsData.overview.total_messages) || 0);
            
        updateStatWithAnimation('persona-count', 
            analyticsData.persona_count || 5);

    } catch (error) {
        console.error('Failed to load dashboard overview:', error);
        const errorIndicators = ['server-count', 'user-count', 'message-count', 'persona-count'];
        errorIndicators.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.textContent = '-';
        });
    }
}

// Animate number updates
function updateStatWithAnimation(elementId, newValue) {
    const element = document.getElementById(elementId);
    if (!element) {
        console.warn(`Element with ID '${elementId}' not found`);
        return;
    }

    // Validate and clean the new value
    let cleanValue = newValue;
    if (typeof cleanValue !== 'number' || isNaN(cleanValue) || !isFinite(cleanValue)) {
        console.warn(`Invalid value for ${elementId}:`, newValue, 'defaulting to 0');
        cleanValue = 0;
    }
    
    // Ensure the value is a positive integer
    cleanValue = Math.max(0, Math.floor(cleanValue));

    const oldValue = parseInt(element.textContent) || 0;
    const duration = 1000; // 1 second animation
    const steps = 60;
    const stepDuration = duration / steps;
    const increment = (cleanValue - oldValue) / steps;

    let currentStep = 0;
    
    const animate = () => {
        currentStep++;
        const current = Math.round(oldValue + (increment * currentStep));
        element.textContent = current.toLocaleString();

        if (currentStep < steps) {
            setTimeout(animate, stepDuration);
        }
    };

    animate();
}

// Initialize chart data
function initializeCharts() {
    // Use a delay to ensure DOM is fully rendered and CSS animations complete
    setTimeout(() => {
        const serverActivityElement = document.getElementById('activityChart');
        
        const ctx = {
            serverActivity: serverActivityElement?.getContext('2d'),
            commandUsage: document.getElementById('commandUsageChart')?.getContext('2d'),
            messageVolume: document.getElementById('messageVolumeChart')?.getContext('2d')
        };        // Initialize charts if canvas elements exist
        if (ctx.serverActivity && !serverActivityChart) {
            serverActivityChart = createServerActivityChart(ctx.serverActivity);
        }
        if (ctx.commandUsage && !commandUsageChart) {
            commandUsageChart = createCommandUsageChart(ctx.commandUsage);
        }
        if (ctx.messageVolume && !messageVolumeChart) {
            messageVolumeChart = createMessageVolumeChart(ctx.messageVolume);
        }
    }, 1000);
}

// Chart creation functions
function createServerActivityChart(ctx) {
    if (typeof Chart === 'undefined') {
        console.error('Chart.js library not loaded');
        return null;
    }
    
    if (!ctx) {
        console.error('Canvas context is null');
        return null;
    }
    
    // Destroy existing chart if it exists to prevent canvas reuse error
    if (serverActivityChart) {
        console.log('Destroying existing serverActivityChart before creating new one');
        serverActivityChart.destroy();
        serverActivityChart = null;
    }
    
    try {
        const chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Server Activity',
                    data: [],
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            precision: 0
                        }
                    }
                }
            }
        });
        return chart;
    } catch (error) {
        console.error('Error creating server activity chart:', error);
        return null;
    }
}

function createCommandUsageChart(ctx) {
    return new Chart(ctx, {
        type: 'bar',
        data: {
            labels: [],
            datasets: [{
                label: 'Commands Used',
                data: [],
                backgroundColor: '#10b981',
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        precision: 0
                    }
                }
            }
        }
    });
}

function createMessageVolumeChart(ctx) {
    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: Array(7).fill('').map((_, i) => {
                const d = new Date();
                d.setDate(d.getDate() - (6 - i));
                return d.toLocaleDateString('en-US', { weekday: 'short' });
            }),
            datasets: [{
                label: 'Messages',
                data: Array(7).fill(0),
                borderColor: '#f59e0b',
                backgroundColor: 'rgba(245, 158, 11, 0.1)',
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        precision: 0
                    }
                }
            }
        }
    });
}

// Chart update functions
async function updateCharts() {
    try {
        const serverActivityResponse = await fetchApi('/api/analytics/server-activity');
        const commandUsageResponse = await fetchApi('/api/analytics/command-usage');
        const messageVolumeResponse = await fetchApi('/api/analytics/message-volume');

        // Update server activity chart
        if (serverActivityChart && serverActivityResponse) {
            const serverData = serverActivityResponse.servers || [];
            const serverValues = serverData.map(server => server.messages_today || 0);
            
            serverActivityChart.data.labels = serverData.map(server => server.server_name || 'Unknown Server');
            serverActivityChart.data.datasets[0].data = serverValues;
            serverActivityChart.update();
        }

        // Update command usage chart
        if (commandUsageChart && commandUsageResponse) {
            const commands = commandUsageResponse.commands || [];
            const commandLabels = commands.map(cmd => cmd.name || 'Unknown');
            const commandValues = commands.map(cmd => cmd.count || 0);
            
            commandUsageChart.data.labels = commandLabels;
            commandUsageChart.data.datasets[0].data = commandValues;
            commandUsageChart.update();
        }

        // Update message volume chart
        if (messageVolumeChart && messageVolumeResponse) {
            let volumeData = [];
            let volumeLabels = [];
            
            if (messageVolumeResponse.daily && Array.isArray(messageVolumeResponse.daily)) {
                volumeLabels = messageVolumeResponse.daily.map(day => day.date || '');
                volumeData = messageVolumeResponse.daily.map(day => day.messages || 0);
            } else if (messageVolumeResponse.hourly && Array.isArray(messageVolumeResponse.hourly)) {
                volumeLabels = messageVolumeResponse.hourly.map(hour => hour.hour || '');
                volumeData = messageVolumeResponse.hourly.map(hour => hour.messages || 0);
            }
            
            if (volumeLabels.length > 0) {
                messageVolumeChart.data.labels = volumeLabels;
                messageVolumeChart.data.datasets[0].data = volumeData;
                messageVolumeChart.update();
            }
        }
    } catch (error) {
        console.error('Failed to update charts:', error);
        showToast('Failed to update charts', 'danger');
    }
}

// User management functions
function manageUser(userId) {
    showToast(`Managing user with ID: ${userId}`, 'info');
    console.log(`Managing user with ID: ${userId}`);
    
    const userModal = document.getElementById('userManagementModal');
    if (userModal) {
        const modal = new bootstrap.Modal(userModal);
        const userIdField = userModal.querySelector('#managed-user-id');
        if (userIdField) userIdField.value = userId;
        
        fetchApi(`/api/users/${userId}`)
            .then(userData => {
                const userNameEl = userModal.querySelector('.user-name');
                if (userNameEl) userNameEl.textContent = userData.username || 'Unknown User';
                modal.show();
            })
            .catch(error => {
                console.error('Error loading user data:', error);
                const userNameEl = userModal.querySelector('.user-name');
                if (userNameEl) userNameEl.textContent = 'User #' + userId;
                modal.show();
            });
    } else {
        showToast(`User management functionality for user ${userId} is not yet implemented in this version.`, 'info');
    }
}

// Task management functions
function editTask(taskId) {
    showToast(`Editing task with ID: ${taskId}`, 'info');
    console.log(`Editing task with ID: ${taskId}`);
    
    const taskModal = document.getElementById('editTaskModal');
    if (taskModal) {
        const modal = new bootstrap.Modal(taskModal);
        const taskIdField = taskModal.querySelector('#edit-task-id');
        if (taskIdField) taskIdField.value = taskId;
        
        fetchApi(`/api/tasks/${taskId}`)
            .then(taskData => {
                const taskNameField = taskModal.querySelector('#edit-task-name');
                if (taskNameField) taskNameField.value = taskData.name || '';
                
                const taskDescField = taskModal.querySelector('#edit-task-description');
                if (taskDescField) taskDescField.value = taskData.description || '';
                
                modal.show();
            })
            .catch(error => {
                console.error('Error loading task data:', error);
                modal.show();
            });
    } else {
        showToast(`Task editing functionality for task ${taskId} is not yet implemented in this version.`, 'info');
    }
}

function deleteTask(taskId) {
    if (confirm(`Are you sure you want to delete task ${taskId}?`)) {
        showToast(`Deleting task with ID: ${taskId}`, 'info');
        console.log(`Deleting task with ID: ${taskId}`);
        
        fetchApi(`/api/tasks/${taskId}`, {
            method: 'DELETE'
        })
        .then(data => {
            showToast('Task deleted successfully', 'success');
            const scheduledTab = document.querySelector('.nav-link.active[href="#scheduled"]');
            if (scheduledTab) {
                loadScheduledTasks();
            }
        })
        .catch(error => {
            console.error('Error deleting task:', error);
            showToast(`Failed to delete task: ${error}`, 'danger');
        });
    }
}

// Load active servers list
async function loadActiveServers() {
    const container = document.getElementById('active-servers');
    if (!container) return;

    try {
        container.innerHTML = '<div class="d-flex justify-content-center"><div class="spinner-border text-primary" role="status"></div></div>';
        const response = await fetchApi('/api/servers');
        const data = response?.guilds || response?.servers || [];

        if (!Array.isArray(data) || data.length === 0) {
            container.innerHTML = '<div class="text-muted">No active servers found</div>';
            return;
        }

        const serverList = data.map(server => `
            <div class="server-item d-flex align-items-center p-2 border-bottom">
                <img src="${server.icon || '/static/img/default_server.png'}" alt="${server.name}" class="me-2 rounded-circle" width="32" height="32">
                <div class="flex-grow-1">
                    <div class="d-flex justify-content-between align-items-center">
                        <strong>${server.name}</strong>
                        <span class="badge bg-primary">${server.member_count || 0} members</span>
                    </div>
                    <small class="text-muted">${server.text_channels || 0} channels</small>
                </div>
            </div>
        `).join('');

        container.innerHTML = serverList;

    } catch (error) {
        console.error('Failed to load active servers:', error);
        container.innerHTML = '<div class="text-danger">Error loading active servers</div>';
    }
}

// Polling fallback setup
function setupPolling() {
    console.log('Setting up polling fallback');
    const POLL_INTERVAL = CONFIG.UPDATE_INTERVAL;
    
    // Clear any existing polling interval
    if (window._pollInterval) {
        clearInterval(window._pollInterval);
    }
    
    // Set up new polling interval
    window._pollInterval = setInterval(() => {
        refreshDashboard();
    }, POLL_INTERVAL);
    
    console.log(`Polling setup complete. Will refresh every ${POLL_INTERVAL}ms`);
}

// Initialize everything when the DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    initializeComponents();
    setupEventListeners();
    refreshDashboard();
    
    // Load initial tab content (overview tab is active by default)
    setTimeout(() => {
        loadTabContent('#overview');
    }, 800);
    
    // Initialize Socket.IO connection
    try {
        const socket = io(window.location.origin, {
            transports: ['websocket', 'polling'],
            reconnection: true,
            reconnectionAttempts: 5,
            reconnectionDelay: 1000,
            timeout: 10000
        });

        // Handle Socket.IO events
        socket.on('connect', () => {
            console.log('Socket.IO connected');
            showToast('Real-time updates connected', 'success');
        });

        socket.on('disconnect', (reason) => {
            console.log('Socket.IO disconnected:', reason);
            showToast('Real-time updates disconnected: ' + reason, 'warning');
            
            // If disconnected due to transport error, attempt fallback to polling
            if (reason === 'transport error' || reason === 'transport close') {
                console.log('Attempting reconnection with polling transport');
                socket.io.opts.transports = ['polling'];
            }
        });

        socket.on('connect_error', (error) => {
            console.error('Socket.IO connection error:', error);
            showToast('Connection error: ' + error.message, 'danger');
            
            // After multiple failed attempts, fall back to regular polling
            if (socket.io.backoff.attempts > 3) {
                console.log('Multiple connection failures, falling back to regular polling');
                setupPolling();
            }
        });

        socket.on('error', (error) => {
            console.error('Socket.IO error:', error);
            showToast('Socket error: ' + (error.message || 'Unknown error'), 'danger');
        });

        socket.on('analytics_update', (data) => {
            // Update statistics in real-time with proper validation
            if (data) {
                if (data.server_count !== undefined && !isNaN(data.server_count)) {
                    updateStatWithAnimation('server-count', data.server_count);
                }
                if (data.total_users !== undefined && !isNaN(data.total_users)) {
                    updateStatWithAnimation('user-count', data.total_users);
                }
                if (data.message_count !== undefined && !isNaN(data.message_count)) {
                    updateStatWithAnimation('message-count', data.message_count);
                }
            }
        });

        socket.on('new_message', (data) => {
            // Handle new messages in live chat
            if (typeof handleNewMessage === 'function' && data) {
                handleNewMessage(data);
            }
        });

        socket.on('notification', (notification) => {
            if (notification && notification.message) {
                showToast(notification.message, notification.type || 'info');
            }
        });

        socket.on('data_refresh', () => {
            // Refresh current tab data
            const activeTab = document.querySelector('.nav-link.active');
            if (activeTab) {
                const targetId = activeTab.getAttribute('data-bs-target');
                loadTabContent(targetId);
            }
        });
    } catch (error) {
        console.error('Failed to initialize Socket.IO:', error);
        showToast('Failed to initialize real-time updates: ' + error.message, 'danger');
        setupPolling(); // Fall back to polling
    }
});

// Tab content loading functions
async function loadPersonas() {
    try {
        const data = await fetchApi('/api/personas');
        const container = document.getElementById('personas-list');
        if (!container) return;

        if (!data.personas || data.personas.length === 0) {
            container.innerHTML = '<div class="text-muted">No personas configured</div>';
            return;
        }

        const personasList = data.personas.map(persona => `
            <div class="persona-item card mb-3">
                <div class="card-body">
                    <h5 class="card-title">${persona.name}</h5>
                    <p class="card-text">${persona.description}</p>
                    <div class="d-flex justify-content-between align-items-center">
                        <span class="badge bg-${persona.type === 'default' ? 'primary' : 'success'}">${persona.type}</span>
                        <small class="text-muted">${persona.messages_sent} messages sent</small>
                    </div>
                </div>
            </div>
        `).join('');

        container.innerHTML = personasList;
    } catch (error) {
        console.error('Failed to load personas:', error);
        showToast('Failed to load personas', 'danger');
    }
}

async function loadServers() {
    try {
        const data = await fetchApi('/api/servers');
        const container = document.getElementById('servers-list');
        if (!container) return;

        if (!data || !Array.isArray(data) || data.length === 0) {
            container.innerHTML = '<div class="text-muted">No servers found</div>';
            return;
        }

        const serversList = data.map(server => `
            <div class="server-card card mb-3">
                <div class="card-body">
                    <div class="d-flex align-items-center">
                        <img src="${server.icon}" alt="${server.name}" class="me-3 rounded-circle" width="48" height="48">
                        <div class="flex-grow-1">
                            <h5 class="card-title mb-1">${server.name}</h5>
                            <div class="text-muted small">
                                <i class="fas fa-users me-1"></i> ${server.member_count} members
                                <i class="fas fa-hashtag ms-2 me-1"></i> ${server.channels.length} channels
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `).join('');

        container.innerHTML = serversList;
    } catch (error) {
        console.error('Failed to load servers:', error);
        showToast('Failed to load servers', 'danger');
    }
}

async function loadUsers() {
    try {
        const data = await fetchApi('/api/users');
        const container = document.getElementById('users-list');
        if (!container) return;

        if (!data.users || data.users.length === 0) {
            container.innerHTML = '<div class="text-muted">No users found</div>';
            return;
        }

        const usersList = data.users.map(user => `
            <tr>
                <td>
                    <div class="d-flex align-items-center">
                        <img src="${user.avatar}" alt="${user.name}" class="me-2 rounded-circle" width="32" height="32">
                        <div>
                            <div class="fw-bold">${user.name}</div>
                            <div class="text-muted small">${user.id}</div>
                        </div>
                    </div>
                </td>
                <td>${user.messages_sent}</td>
                <td>${user.commands_used}</td>
                <td>
                    <button class="btn btn-sm btn-outline-primary" onclick="manageUser('${user.id}')">
                        Manage
                    </button>
                </td>
            </tr>
        `).join('');

        container.innerHTML = `
            <table class="table table-hover">
                <thead>
                    <tr>
                        <th>User</th>
                        <th>Messages</th>
                        <th>Commands</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>${usersList}</tbody>
            </table>
        `;
    } catch (error) {
        console.error('Failed to load users:', error);
        showToast('Failed to load users', 'danger');
    }
}

async function loadModerationLogs() {
    try {
        const data = await fetchApi('/api/moderation/logs');
        const container = document.getElementById('moderation-logs');
        if (!container) return;

        if (!data.logs || data.logs.length === 0) {
            container.innerHTML = '<div class="text-muted">No moderation logs found</div>';
            return;
        }

        const logsList = data.logs.map(log => `
            <div class="log-item border-bottom p-2">
                <div class="d-flex justify-content-between">
                    <strong>${log.action}</strong>
                    <small class="text-muted">${new Date(log.timestamp).toLocaleString()}</small>
                </div>
                <div>${log.details}</div>
                <div class="text-muted small">
                    By ${log.moderator} in ${log.server}
                </div>
            </div>
        `).join('');

        container.innerHTML = logsList;
    } catch (error) {
        console.error('Failed to load moderation logs:', error);
        showToast('Failed to load moderation logs', 'danger');
    }
}

async function loadAnalytics() {
    try {
        const [overviewData, activityData, commandData, messageData] = await Promise.all([
            fetchApi('/api/analytics'),
            fetchApi('/api/analytics/server-activity'),
            fetchApi('/api/analytics/command-usage'),
            fetchApi('/api/analytics/message-volume')
        ]);

        // Update overview stats
        updateAnalyticsOverview(overviewData);
        
        // Update charts
        updateAnalyticsCharts(activityData, commandData, messageData);
    } catch (error) {
        console.error('Failed to load analytics:', error);
        showToast('Failed to load analytics data', 'danger');
    }
}

async function loadActiveChannels() {
    try {
        const data = await fetchApi('/api/channels/active');
        const container = document.getElementById('active-channels');
        if (!container) return;

        if (!data.channels || data.channels.length === 0) {
            container.innerHTML = '<div class="text-muted">No active channels found</div>';
            return;
        }

        const channelsList = data.channels.map(channel => `
            <div class="channel-item d-flex justify-content-between align-items-center p-2 border-bottom">
                <div>
                    <strong>#${channel.name}</strong>
                    <div class="text-muted small">${channel.server}</div>
                </div>
                <span class="badge bg-primary">${channel.active_users} active</span>
            </div>
        `).join('');

        container.innerHTML = channelsList;
    } catch (error) {
        console.error('Failed to load active channels:', error);
        showToast('Failed to load active channels', 'danger');
    }
}

async function loadScheduledTasks() {
    try {
        const data = await fetchApi('/api/tasks');
        const container = document.getElementById('scheduled-tasks');
        if (!container) return;

        if (!data.tasks || data.tasks.length === 0) {
            container.innerHTML = '<div class="text-muted">No scheduled tasks found</div>';
            return;
        }

        const tasksList = data.tasks.map(task => `
            <div class="task-item card mb-3">
                <div class="card-body">
                    <h5 class="card-title">${task.name}</h5>
                    <p class="card-text">${task.description}</p>
                    <div class="d-flex justify-content-between align-items-center">
                        <span class="badge bg-${task.status === 'active' ? 'success' : 'warning'}">${task.status}</span>
                        <div class="btn-group">
                            <button class="btn btn-sm btn-outline-primary" onclick="editTask('${task.id}')">Edit</button>
                            <button class="btn btn-sm btn-outline-danger" onclick="deleteTask('${task.id}')">Delete</button>
                        </div>
                    </div>
                </div>
            </div>
        `).join('');

        container.innerHTML = tasksList;
    } catch (error) {
        console.error('Failed to load scheduled tasks:', error);
        showToast('Failed to load scheduled tasks', 'danger');
    }
}

async function loadSettings() {
    try {
        const data = await fetchApi('/api/settings');
        const container = document.getElementById('bot-settings');
        if (!container) return;

        if (!data) {
            container.innerHTML = '<div class="text-danger">Failed to load settings</div>';
            return;
        }

        // Update settings form values
        Object.entries(data).forEach(([key, value]) => {
            const input = document.querySelector(`[name="setting-${key}"]`);
            if (input) {
                if (input.type === 'checkbox') {
                    input.checked = value;
                } else {
                    input.value = value;
                }
            }
        });
    } catch (error) {
        console.error('Failed to load settings:', error);
        showToast('Failed to load settings', 'danger');
    }
}

// Animation monitoring function
function monitorAnimationState() {    // Find the card element that contains the activity chart canvas
    const canvasElement = document.getElementById('activityChart');
    const cardElement = canvasElement?.closest('.card.fade-in');
    
    if (!cardElement) {
        console.log('Activity chart card not found for animation monitoring');
        return;
    }
    
    const computedStyle = window.getComputedStyle(cardElement);
    console.log('Animation state for activity chart card:', {
        animationName: computedStyle.animationName,
        animationDuration: computedStyle.animationDuration,
        animationDelay: computedStyle.animationDelay,
        animationPlayState: computedStyle.animationPlayState,
        opacity: computedStyle.opacity,
        classes: cardElement.className
    });
    
    // Listen for animation events on the card
    cardElement.addEventListener('animationstart', (e) => {
        console.log('Card animation started:', e.animationName);
    });
    
    cardElement.addEventListener('animationend', (e) => {
        console.log('Card animation ended:', e.animationName);
        console.log('Chart card animation complete, initializing chart...');
        setTimeout(() => loadActivityChart('day'), 100);
    });
}

// === NEW COMPREHENSIVE API FUNCTIONS ===

// Overview Tab Functions
async function loadOverviewTab() {
    try {
        await Promise.all([
            loadSystemStatus(),
            loadNotifications(),
            loadActivityChart('day'),
            loadActiveServers()
        ]);
    } catch (error) {
        console.error('Error loading overview tab:', error);
        showToast('Failed to load overview data', 'danger');
    }
}

async function loadSystemStatus() {
    try {
        const status = await fetchApi('/api/overview/system-status');
        const statusElement = document.getElementById('system-status');
        if (statusElement) {
            statusElement.innerHTML = `
                <div class="row g-2 text-center">
                    <div class="col-6">
                        <div class="bg-light p-2 rounded">
                            <div class="h6 mb-1">${status?.bot?.status?.toUpperCase() || 'UNKNOWN'}</div>
                            <small class="text-muted">Bot Status</small>
                        </div>
                    </div>
                    <div class="col-6">
                        <div class="bg-light p-2 rounded">
                            <div class="h6 mb-1">${status?.bot?.uptime || '0h'}</div>
                            <small class="text-muted">Uptime</small>
                        </div>
                    </div>
                    <div class="col-6">
                        <div class="bg-light p-2 rounded">
                            <div class="h6 mb-1">${status?.api?.response_time || 'N/A'}ms</div>
                            <small class="text-muted">Response Time</small>
                        </div>
                    </div>
                    <div class="col-6">
                        <div class="bg-light p-2 rounded">
                            <div class="h6 mb-1">${status?.bot?.cpu_usage || 'N/A'}%</div>
                            <small class="text-muted">CPU Usage</small>
                        </div>
                    </div>
                </div>
            `;
        }
    } catch (error) {
        console.error('Failed to load system status:', error);
        const statusElement = document.getElementById('system-status');
        if (statusElement) {
            statusElement.innerHTML = '<div class="text-danger">Error loading system status</div>';
        }
    }
}

async function loadNotifications() {
    const notificationsElement = document.getElementById('notifications');
    if (!notificationsElement) return;

    try {
        notificationsElement.innerHTML = '<div class="text-muted">Loading notifications...</div>';
        const response = await fetchApi('/api/overview/notifications');
        const notifications = response?.notifications || [];

        if (!Array.isArray(notifications) || notifications.length === 0) {
            notificationsElement.innerHTML = '<div class="text-muted">No notifications found.</div>';
            return;
        }

        notificationsElement.innerHTML = notifications.map(notif => `
            <div class="notification-item ${notif.read ? '' : 'unread'} mb-2">
                <div class="d-flex align-items-start">
                    <i class="fas fa-${getNotificationIcon(notif.type || 'info')} text-${notif.type || 'info'} me-2 mt-1"></i>
                    <div class="flex-grow-1">
                        <div class="fw-medium">${notif.message || 'No message content'}</div>
                        <small class="text-muted">${notif.timestamp ? formatRelativeTime(notif.timestamp) : 'Unknown time'}</small>
                    </div>
                </div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Error loading notifications:', error);
        if (notificationsElement) {
            notificationsElement.innerHTML = '<div class="text-danger">Error loading notifications.</div>';
        }
    }
}

async function loadActivityChart(period = 'day') {
    console.log(`Loading activity chart for period: ${period}`);
    
    debugChartState('loadActivityChart start');
    
    // Function to wait for element to be available AND visible
    const waitForElement = (id, maxAttempts = 30) => {
        return new Promise((resolve) => {
            let attempts = 0;
            const checkElement = () => {
                const element = document.getElementById(id);
                  if (element) {
                    // Check if element is visible (not hidden by CSS animations)
                    const computedStyle = window.getComputedStyle(element);
                    const rect = element.getBoundingClientRect();                    const opacityValue = parseFloat(computedStyle.opacity) || 0;
                    const isVisible = opacityValue > 0.9 && 
                                    computedStyle.visibility !== 'hidden' && 
                                    computedStyle.display !== 'none' &&
                                    rect.width > 0 && rect.height > 0;
                    
                    if (isVisible) {
                        resolve(element);
                        return;
                    }
                }
                
                if (attempts < maxAttempts) {
                    attempts++;
                    setTimeout(checkElement, 100); // Check every 100ms
                } else {
                    resolve(null);
                }
            };
            checkElement();
        });
    };
    
    const chartCanvas = await waitForElement('activityChart');
      if (!chartCanvas) {
        console.error('Activity chart canvas not found after waiting');
        // Try alternative approach - look for canvas in overview tab
        const overviewCanvas = document.querySelector('#overview canvas');
        if (overviewCanvas && !overviewCanvas.id) {
            overviewCanvas.id = 'activityChart';
            return loadActivityChart(period); // Retry
        }
          // Final fallback: try to find the element by ID without visibility check
        const fallbackElement = document.getElementById('activityChart');
        if (fallbackElement) {
            // Force the element to be visible
            fallbackElement.style.opacity = '1';
            fallbackElement.style.visibility = 'visible';
            fallbackElement.style.display = 'block';
            
            // Wait a moment for the style changes to take effect
            setTimeout(() => {
                loadActivityChart(period);
            }, 200);
            return;
        }
        
        return;
    }
      // Destroy existing chart if it exists to prevent reuse error
    if (serverActivityChart) {
        serverActivityChart.destroy();
        serverActivityChart = null;
    }
    
    // Create new chart instance
    const ctx = chartCanvas.getContext('2d');
    if (ctx) {
        serverActivityChart = createServerActivityChart(ctx);
    } else {
        console.error('Failed to get canvas context');
        return;
    }
    
    if (!serverActivityChart) {
        console.error('Failed to create chart instance');
        return;
    }

    try {
        // Display a loading state on the chart
        serverActivityChart.data.labels = [];
        serverActivityChart.data.datasets[0].data = [];
        if (!serverActivityChart.options.plugins) {
            serverActivityChart.options.plugins = {};
        }
        serverActivityChart.options.plugins.title = {
            display: true,
            text: 'Loading activity data...'
        };
        serverActivityChart.update();
        
        const response = await fetchApi(`/api/overview/activity-chart?period=${period}`);
        
        const data = response?.datasets?.[0]?.data || response?.data || [];
        const labels = response?.labels || [];

        if (!Array.isArray(data) || !Array.isArray(labels) || data.length === 0 || labels.length === 0) {
            console.warn('No valid data received');
            serverActivityChart.options.plugins.title.text = 'No activity data available for this period.';
            serverActivityChart.data.labels = [];
            serverActivityChart.data.datasets[0].data = [];
            serverActivityChart.update();
            return;
        }

        serverActivityChart.data.labels = labels;
        serverActivityChart.data.datasets[0].data = data;
        serverActivityChart.options.plugins.title.text = 'Server Activity'; // Reset title
        serverActivityChart.update();

        // Update active period button
        document.querySelectorAll('[data-period]').forEach(btn => {
            btn.classList.remove('active');
            if (btn.getAttribute('data-period') === period) {
                btn.classList.add('active');
            }
        });
        
        console.log('Activity chart loaded successfully');
    } catch (error) {
        console.error('Error loading activity chart:', error);
        if (serverActivityChart) {
            serverActivityChart.options.plugins.title.text = 'Error loading chart data';
            serverActivityChart.data.labels = [];
            serverActivityChart.data.datasets[0].data = [];
            serverActivityChart.update();
        }
    }
}

// Quick Actions
async function handleQuickAction(action, data = {}) {
    try {
        const response = await fetchApi('/api/overview/quick-actions', {
            method: 'POST',
            body: JSON.stringify({ action, ...data })
        });
        
        if (response.success) {
            showToast(response.message, 'success');
        } else {
            showToast(response.error || 'Action failed', 'danger');
        }
    } catch (error) {
        console.error('Quick action error:', error);
        showToast('Failed to execute action', 'danger');
    }
}

// Personas Tab Functions
async function loadPersonasTab() {
    try {
        await loadPersonasList();
        setupPersonaForm();
    } catch (error) {
        console.error('Error loading personas tab:', error);
        showToast('Failed to load personas', 'danger');
    }
}

async function loadPersonasList() {
    try {
        const response = await fetchApi('/api/personas');
        const personasListElement = document.getElementById('personas-list');
        
        if (personasListElement && response.personas) {
            personasListElement.innerHTML = response.personas.map(persona => `
                <div class="persona-item mb-3 p-3 border rounded">
                    <div class="d-flex justify-content-between align-items-start">
                        <div>
                            <h6 class="mb-1">${persona.name}</h6>
                            <span class="badge bg-${persona.type === 'default' ? 'primary' : 'secondary'} mb-2">
                                ${persona.type}
                            </span>
                            <p class="text-muted small mb-0">${persona.description || 'No description'}</p>
                        </div>
                        <div class="btn-group">
                            <button class="btn btn-sm btn-outline-primary" onclick="editPersona('${persona.name}')">
                                <i class="fas fa-edit"></i>
                            </button>
                            ${persona.type === 'custom' ? `
                                <button class="btn btn-sm btn-outline-danger" onclick="deletePersona('${persona.name}')">
                                    <i class="fas fa-trash"></i>
                                </button>
                            ` : ''}
                        </div>
                    </div>
                </div>
            `).join('');
        }
    } catch (error) {
        console.error('Error loading personas list:', error);
    }
}

async function createPersona(formData) {
    try {
        const response = await fetchApi('/api/personas/create', {
            method: 'POST',
            body: JSON.stringify(formData)
        });
        
        if (response.success) {
            showToast('Persona created successfully', 'success');
            await loadPersonasList();
            document.getElementById('create-persona-form').reset();
        } else {
            showToast(response.error || 'Failed to create persona', 'danger');
        }
    } catch (error) {
        console.error('Error creating persona:', error);
        showToast('Failed to create persona', 'danger');
    }
}

async function deletePersona(personaName) {
    if (!confirm(`Are you sure you want to delete the "${personaName}" persona?`)) {
        return;
    }
    
    try {
        const response = await fetchApi(`/api/persona/${personaName}`, {
            method: 'DELETE'
        });
        
        if (response.success) {
            showToast('Persona deleted successfully', 'success');
            await loadPersonasList();
        } else {
            showToast(response.error || 'Failed to delete persona', 'danger');
        }
    } catch (error) {
        console.error('Error deleting persona:', error);
        showToast('Failed to delete persona', 'danger');
    }
}

// Servers Tab Functions
async function loadServersTab() {
    try {
        await loadServersList();
    } catch (error) {
        console.error('Error loading servers tab:', error);
        showToast('Failed to load servers', 'danger');
    }
}

async function loadServersList() {
    try {
        const response = await fetchApi('/api/servers');
        const serversListElement = document.getElementById('servers-list');
        
        if (serversListElement && response.servers) {
            serversListElement.innerHTML = response.servers.map(server => `
                <div class="server-item mb-3 p-3 border rounded">
                    <div class="d-flex align-items-center">
                        <img src="${server.icon}" alt="${server.name}" class="rounded me-3" width="48" height="48">
                        <div class="flex-grow-1">
                            <h6 class="mb-1">${server.name}</h6>
                            <p class="text-muted mb-0">${server.member_count} members • ${server.channels.length} channels</p>
                        </div>
                        <button class="btn btn-outline-primary btn-sm" onclick="selectServer('${server.id}')">
                            Manage
                        </button>
                    </div>
                </div>
            `).join('');
        }
    } catch (error) {
        console.error('Error loading servers list:', error);
    }
}

async function selectServer(serverId) {
    try {
        const analytics = await fetchApi(`/api/servers/${serverId}/analytics`);
        const settingsElement = document.getElementById('server-settings');
        
        if (settingsElement) {
            settingsElement.innerHTML = `
                <h6>Server Analytics</h6>
                <div class="mb-3">
                    <div class="row g-2 text-center">
                        <div class="col-6">
                            <div class="bg-light p-2 rounded">
                                <div class="h6 mb-1">${analytics.member_count}</div>
                                <small class="text-muted">Members</small>
                            </div>
                        </div>
                        <div class="col-6">
                            <div class="bg-light p-2 rounded">
                                <div class="h6 mb-1">${analytics.message_count_today}</div>
                                <small class="text-muted">Messages Today</small>
                            </div>
                        </div>
                    </div>
                </div>
                <button class="btn btn-primary btn-sm w-100">Configure Settings</button>
            `;
        }
    } catch (error) {
        console.error('Error selecting server:', error);
        showToast('Failed to load server details', 'danger');
    }
}

// Users Tab Functions
async function loadUsersTab() {
    try {
        await loadActiveUsers();
        setupUserSearch();
    } catch (error) {
        console.error('Error loading users tab:', error);
        showToast('Failed to load users', 'danger');
    }
}

async function loadActiveUsers() {
    try {
        const response = await fetchApi('/api/users/active');
        const usersListElement = document.getElementById('active-users-list');
        
        if (usersListElement && response.users) {
            usersListElement.innerHTML = response.users.map(user => `
                <div class="user-item mb-2 p-2 border rounded d-flex align-items-center">
                    <img src="${user.avatar_url || '/static/img/default_avatar.png'}" 
                         alt="${user.name}" class="rounded-circle me-3" width="40" height="40">
                    <div class="flex-grow-1">
                        <div class="fw-medium">${user.name}</div>
                        <small class="text-muted">${user.messages} messages • ${user.guild_name}</small>
                    </div>
                    <button class="btn btn-outline-primary btn-sm" onclick="selectUser('${user.id}')">
                        Manage
                    </button>
                </div>
            `).join('');
        }
    } catch (error) {
        console.error('Error loading active users:', error);
    }
}

async function searchUsers(query) {
    try {
        const response = await fetchApi(`/api/users/search?q=${encodeURIComponent(query)}`);
        if (response && Array.isArray(response)) {
            displayUserSearchResults(response);
        }
    } catch (error) {
        console.error('Error searching users:', error);
        showToast('Failed to search users', 'danger');
    }
}

function displayUserSearchResults(users) {
    const resultsContainer = document.getElementById('user-search-results');
    if (resultsContainer) {
        resultsContainer.innerHTML = users.map(user => `
            <div class="user-result p-2 border rounded mb-2">
                <div class="d-flex align-items-center">
                    <img src="${user.avatar_url || '/static/img/default_avatar.png'}" 
                         alt="${user.name}" class="rounded-circle me-2" width="32" height="32">
                    <div>
                        <div class="fw-medium">${user.name}</div>
                        <small class="text-muted">${user.guild}</small>
                    </div>
                </div>
            </div>
        `).join('');
    }
}

// Moderation Tab Functions
async function loadModerationTab() {
    try {
        await loadModerationLogs();
        setupModerationTools();
    } catch (error) {
        console.error('Error loading moderation tab:', error);
        showToast('Failed to load moderation data', 'danger');
    }
}

async function loadModerationLogs() {
    try {
        const response = await fetchApi('/api/moderation/logs');
        const logsElement = document.getElementById('moderation-logs');
        
        if (logsElement && response.logs) {
            logsElement.innerHTML = response.logs.map(log => `
                <div class="moderation-log-item mb-2 p-3 border rounded">
                    <div class="d-flex justify-content-between align-items-start">
                        <div>
                            <span class="badge bg-${getModerationActionColor(log.action)} me-2">
                                ${log.action.toUpperCase()}
                            </span>
                            <strong>${log.user_name}</strong> by <em>${log.mod_name}</em>
                            <p class="mb-1 mt-1">${log.reason}</p>
                            <small class="text-muted">${formatRelativeTime(log.timestamp)}</small>
                        </div>
                    </div>
                </div>
            `).join('');
        }
    } catch (error) {
        console.error('Error loading moderation logs:', error);
    }
}

async function executeModerationAction(action, data = {}) {
    try {
        const response = await fetchApi('/api/moderation/action', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ action, ...data })
        });
        
        if (response.success) {
            showToast(`${action.charAt(0).toUpperCase() + action.slice(1)} action completed`, 'success');
            loadModerationLogs(); // Refresh logs
        } else {
            showToast(`Failed to execute ${action}`, 'danger');
        }
    } catch (error) {
        console.error(`Error executing ${action}:`, error);
        showToast(`Error executing ${action}`, 'danger');
    }
}

// Analytics Tab Functions
async function loadAnalyticsTab() {
    try {
        await Promise.all([
            loadPersonaUsageChart(),
            loadMessageActivityChart(),
            loadCommandUsageChart(),
            loadEngagementAnalytics()
        ]);
    } catch (error) {
        console.error('Error loading analytics tab:', error);
        showToast('Failed to load analytics', 'danger');
    }
}

async function loadPersonaUsageChart() {
    try {
        const response = await fetchApi('/api/analytics/persona-usage');
        const ctx = document.getElementById('personaChart')?.getContext('2d');
        
        if (ctx && response.data) {
            new Chart(ctx, {
                type: 'pie',
                data: {
                    labels: Object.keys(response.data),
                    datasets: [{
                        data: Object.values(response.data),
                        backgroundColor: [
                            '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF'
                        ]
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false
                }
            });
        }
    } catch (error) {
        console.error('Error loading persona usage chart:', error);
    }
}

async function loadMessageActivityChart() {
    try {
        const response = await fetchApi('/api/analytics/message-activity');
        const ctx = document.getElementById('messageActivityChart')?.getContext('2d');
        
        if (ctx && response.labels && response.data) {
            // Destroy existing chart if it exists
            if (window.messageActivityChart) {
                window.messageActivityChart.destroy();
            }
            
            window.messageActivityChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: response.labels,
                    datasets: [{
                        label: 'Messages',
                        data: response.data,
                        borderColor: 'rgba(74, 144, 226, 1)',
                        backgroundColor: 'rgba(74, 144, 226, 0.1)',
                        tension: 0.4,
                        fill: true
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true,
                            grid: {
                                color: 'rgba(255,255,255,0.1)'
                            }
                        },
                        x: {
                            grid: {
                                color: 'rgba(255,255,255,0.1)'
                            }
                        }
                    },
                    plugins: {
                        legend: {
                            display: false
                        }
                    }
                }
            });
        }
    } catch (error) {
        console.error('Error loading message activity chart:', error);
    }
}

// Live Chat Tab Functions
async function loadLiveChatTab() {
    try {
        await loadChatChannels();
        setupLiveChat();
    } catch (error) {
        console.error('Error loading live chat tab:', error);
        showToast('Failed to load live chat', 'danger');
    }
}

async function loadChatChannels() {
    try {
        const response = await fetchApi('/api/livechat/channels');
        const channelsElement = document.getElementById('chat-channels');
        
        if (channelsElement && response.channels) {
            channelsElement.innerHTML = response.channels.map(channel => `
                <div class="channel-item p-2 border rounded mb-2 cursor-pointer" 
                     onclick="selectChatChannel('${channel.id}', '${channel.name}')">
                    <div class="fw-medium">#${channel.name}</div>
                    <small class="text-muted">${channel.guild_name}</small>
                </div>
            `).join('');
        }
    } catch (error) {
        console.error('Error loading chat channels:', error);
    }
}

// Scheduled Tab Functions
async function loadScheduledTab() {
    try {
        await loadScheduledTasks();
        setupTaskCreation();
    } catch (error) {
        console.error('Error loading scheduled tab:', error);
        showToast('Failed to load scheduled tasks', 'danger');
    }
}

async function loadScheduledTasks() {
    try {
        const response = await fetchApi('/api/scheduled/tasks');
        const tasksElement = document.getElementById('scheduled-tasks');
        
        if (tasksElement && response.tasks) {
            tasksElement.innerHTML = response.tasks.map(task => `
                <div class="task-item mb-3 p-3 border rounded">
                    <div class="d-flex justify-content-between align-items-start">
                        <div>
                            <h6 class="mb-1">${task.name}</h6>
                            <p class="mb-1 text-muted">${task.description}</p>
                            <small class="text-muted">Next run: ${formatRelativeTime(task.next_run)}</small>
                        </div>
                        <div class="btn-group">
                            <button class="btn btn-sm btn-outline-primary" onclick="editTask('${task.id}')">
                                <i class="fas fa-edit"></i>
                            </button>
                            <button class="btn btn-sm btn-outline-danger" onclick="deleteTask('${task.id}')">
                                <i class="fas fa-trash"></i>
                            </button>
                        </div>
                    </div>
                </div>
            `).join('');
        }
    } catch (error) {
        console.error('Error loading scheduled tasks:', error);
    }
}

// Settings Tab Functions
async function loadSettingsTab() {
    try {
        await Promise.all([
            loadBotConfig(),
            loadAISettings()
        ]);
    } catch (error) {
        console.error('Error loading settings tab:', error);
        showToast('Failed to load settings', 'danger');
    }
}

// --- MISSING FUNCTION IMPLEMENTATIONS ---
function editPersona(personaName) {
    showToast(`Edit persona: ${personaName} (not yet implemented)`, 'info');
    console.log('Edit persona:', personaName);
    // TODO: Open persona edit modal and populate fields
}

function selectUser(userId) {
    showToast(`Select user: ${userId} (not yet implemented)`, 'info');
    console.log('Select user:', userId);
    // TODO: Open user management modal
}

function handleNewMessage(data) {
    // Example: append message to live chat window
    console.log('New live chat message:', data);
    // TODO: Update live chat UI if present
}

function setupPersonaForm() {
    // Already stubbed, keep as is or expand as needed
    console.log('Setting up persona form...');
}

function setupModerationTools() {
    // Already stubbed, keep as is or expand as needed
    console.log('Setting up moderation tools...');
}

function setupTaskCreation() {
    // Already stubbed, keep as is or expand as needed
    console.log('Setting up task creation...');
}

async function loadAISettings() {
    // Fetch and display AI settings if available
    try {
        const data = await fetchApi('/api/settings/ai-settings');
        console.log('Loaded AI settings:', data);
        // TODO: Populate AI settings form if present
    } catch (error) {
        console.error('Failed to load AI settings:', error);
    }
}

function updateAnalyticsOverview(data) {
    // Update analytics overview stats if present
    if (!data) return;
    if (data.server_count !== undefined) updateStatWithAnimation('server-count', data.server_count);
    if (data.total_users !== undefined) updateStatWithAnimation('user-count', data.total_users);
    if (data.message_count !== undefined) updateStatWithAnimation('message-count', data.message_count);
    if (data.persona_count !== undefined) updateStatWithAnimation('persona-count', data.persona_count);
}

function updateAnalyticsCharts(activityData, commandData, messageData) {
    // Update analytics charts if present
    // Server Activity Chart
    if (serverActivityChart && activityData && Array.isArray(activityData.values)) {
        serverActivityChart.data.labels = activityData.labels || serverActivityChart.data.labels;
        serverActivityChart.data.datasets[0].data = activityData.values;
        serverActivityChart.update();
    }
    // Command Usage Chart
    if (commandUsageChart && commandData && Array.isArray(commandData.values)) {
        commandUsageChart.data.labels = commandData.labels || commandUsageChart.data.labels;
        commandUsageChart.data.datasets[0].data = commandData.values;
        commandUsageChart.update();
    }
    // Message Volume Chart
    if (messageVolumeChart && messageData && Array.isArray(messageData.values)) {
        messageVolumeChart.data.labels = messageData.labels || messageVolumeChart.data.labels;
        messageVolumeChart.data.datasets[0].data = messageData.values;
        messageVolumeChart.update();
    }
}

// Missing helper functions implementation

function setupEventListeners() {
    // Set up event listeners for dashboard functionality
    
    // Bot restart button
    const restartBtn = document.getElementById('restart-bot-btn');
    if (restartBtn) {
        restartBtn.addEventListener('click', async () => {
            await handleBotRestart();
        });
    }

    // Check updates button
    const updateBtn = document.getElementById('check-updates-btn');
    if (updateBtn) {
        updateBtn.addEventListener('click', async () => {
            await checkForUpdates();
        });
    }

    // Tab switching listeners
    document.querySelectorAll('[data-bs-toggle="tab"]').forEach(tab => {
        tab.addEventListener('shown.bs.tab', function (e) {
            const targetTab = e.target.getAttribute('href');
            if (targetTab) {
                loadTabContent(targetTab);
            }
        });
    });

    // Form submission listeners
    const configForm = document.getElementById('config-form');
    if (configForm) {
        configForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            await saveConfiguration();
        });
    }    // Search functionality
    const searchInput = document.getElementById('search-input');
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            const query = this.value.toLowerCase();
            // Add search functionality for current tab content
            filterCurrentTabContent(query);
        });
    }

    // Period button listeners for activity chart
    document.querySelectorAll('[data-period]').forEach(btn => {
        btn.addEventListener('click', function() {
            const period = this.getAttribute('data-period');
            if (period) {
                loadActivityChart(period);
            }
        });
    });
}

async function handleBotRestart() {
    try {
        showToast('Initiating bot restart...', 'info');
        
        const response = await fetchApi('/api/bot/restart', {
            method: 'POST'
        });
        
        if (response.success) {
            showToast('Bot restart initiated successfully', 'success');
            // Refresh dashboard after a delay
            setTimeout(() => {
                window.location.reload();
            }, 3000);
        } else {
            showToast('Failed to restart bot: ' + (response.error || 'Unknown error'), 'danger');
        }
    } catch (error) {
        console.error('Bot restart error:', error);
        showToast('Error restarting bot: ' + error.message, 'danger');
    }
}

async function checkForUpdates() {
    try {
        showToast('Checking for updates...', 'info');
        
        const response = await fetchApi('/api/bot/check-updates');
        
        if (response.updates_available) {
            showToast(`Updates available: ${response.version}`, 'warning');
            // Show update modal or notification
            showUpdateNotification(response);
        } else {
            showToast('Bot is up to date', 'success');
        }
    } catch (error) {
        console.error('Update check error:', error);
        showToast('Error checking for updates: ' + error.message, 'danger');
    }
}

function handleRealtimeUpdate(data) {
    // Handle real-time updates from WebSocket
    if (!data || !data.type) return;

    switch (data.type) {
        case 'user_message':
            updateMessageCount(data);
            break;
        case 'command_used':
            updateCommandStats(data);
            break;
        case 'user_joined':
        case 'user_left':
            updateUserCount(data);
            break;
        case 'moderation_action':
            addModerationLogEntry(data);
            break;
        case 'notification':
            addNotification(data);
            break;
        case 'bot_status':
            updateBotStatus(data);
            break;
        default:
            console.log('Unknown realtime update type:', data.type);
    }
}

function getNotificationIcon(type) {
    // Return appropriate icon class for notification type
    const iconMap = {
        'success': 'check-circle',
        'info': 'info-circle',
               'warning': 'exclamation-triangle',
        'danger': 'exclamation-circle',
        'error': 'exclamation-circle',
        'message': 'comment',
        'user': 'user',
        'moderation': 'shield-alt',
        'system': 'cog',
        'bot': 'robot'
    };
    
    return iconMap[type] || 'bell';
}

function getModerationActionColor(action) {
    // Return appropriate color class for moderation actions
    const colorMap = {
        'ban': 'danger',
        'kick': 'warning',
        'mute': 'info',
        'warn': 'warning',
        'timeout': 'warning',
        'unban': 'success',
        'unmute': 'success',
        'delete': 'danger'
    };
    
    return colorMap[action] || 'secondary';
}

function formatRelativeTime(timestamp) {
    // Format timestamp as relative time (e.g., "2 hours ago")
    if (!timestamp) return 'Unknown';
    
    const now = new Date();
    const time = new Date(timestamp);
    const diffInSeconds = Math.floor((now - time) / 1000);
    
    if (diffInSeconds < 60) {
        return 'Just now';
    } else if (diffInSeconds < 3600) {
        const minutes = Math.floor(diffInSeconds / 60);
        return `${minutes} minute${minutes !== 1 ? 's' : ''} ago`;
    } else if (diffInSeconds < 86400) {
        const hours = Math.floor(diffInSeconds / 3600);
        return `${hours} hour${hours !== 1 ? 's' : ''} ago`;
    } else if (diffInSeconds < 2592000) {
        const days = Math.floor(diffInSeconds / 86400);
        return `${days} day${days !== 1 ? 's' : ''} ago`;
    } else {
        const months = Math.floor(diffInSeconds / 2592000);
        return `${months} month${months !== 1 ? 's' : ''} ago`;
    }
}

function setupUserSearch() {
    // Setup user search functionality
    const searchInput = document.getElementById('user-search');
    if (!searchInput) return;

    searchInput.addEventListener('input', function() {
        const query = this.value.toLowerCase();
        const userRows = document.querySelectorAll('#users-list tr');
        
        userRows.forEach(row => {
            const userName = row.querySelector('.fw-bold')?.textContent.toLowerCase() || '';
            const userId = row.querySelector('.text-muted')?.textContent.toLowerCase() || '';
            
            if (userName.includes(query) || userId.includes(query)) {
                row.style.display = '';
            } else {
                row.style.display = 'none';
            }
        });
    });
}

function setupLiveChat() {
    // Setup live chat functionality
    const chatContainer = document.getElementById('live-chat-messages');
    const chatInput = document.getElementById('live-chat-input');
    const sendButton = document.getElementById('live-chat-send');
    
    if (!chatContainer || !chatInput || !sendButton) return;

    // Send message function
    const sendMessage = async () => {
        const message = chatInput.value.trim();
        if (!message) return;

        try {
            await fetchApi('/api/chat/send', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    message: message,
                    channel: document.getElementById('chat-channel-select')?.value
                })
            });
            
            chatInput.value = '';
            chatInput.focus();
        } catch (error) {
            console.error('Failed to send message:', error);
            showToast('Failed to send message', 'danger');
        }
    };

    // Event listeners
    sendButton.addEventListener('click', sendMessage);
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Load initial messages
    loadChatMessages();
}

async function loadBotConfig() {
    // Load bot configuration
    try {
        const config = await fetchApi('/api/bot/config');
        populateConfigForm(config);
    } catch (error) {
        console.error('Failed to load bot config:', error);
        showToast('Failed to load bot configuration', 'danger');
    }
}

function selectChatChannel(channelId) {
    // Select chat channel for live chat
    const currentChannel = document.getElementById('current-channel');
    if (currentChannel) {
        currentChannel.textContent = channelId;
    }
    
    // Clear current messages and load new channel messages
    const chatContainer = document.getElementById('live-chat-messages');
    if (chatContainer) {
        chatContainer.innerHTML = '<div class="text-muted">Loading messages...</div>';
    }
    
    loadChatMessages(channelId);
}

async function loadCommandUsageChart() {
    // Load command usage chart data
    try {
        const data = await fetchApi('/api/analytics/command-usage');
        if (commandUsageChart && data) {
            commandUsageChart.data.labels = data.labels || [];
            commandUsageChart.data.datasets[0].data = data.values || [];
            commandUsageChart.update();
        }
    } catch (error) {
        console.error('Failed to load command usage chart:', error);
    }
}

async function loadEngagementAnalytics() {
    // Load engagement analytics
    try {
        const data = await fetchApi('/api/analytics/engagement');
        if (data) {
            updateEngagementMetrics(data);
        }
    } catch (error) {
        console.error('Failed to load engagement analytics:', error);
    }
}

// Helper functions for real-time updates
function updateMessageCount(data) {
    const messageCountElement = document.getElementById('message-count');
    if (messageCountElement && data.count) {
       
        updateStatWithAnimation('message-count', data.count);
    }
}

function updateCommandStats(data) {
    // Update command statistics in real-time
    if (commandUsageChart && data.command) {
        // Find command in chart and increment count
        const commandIndex = commandUsageChart.data.labels.indexOf(data.command);
        if (commandIndex !== -1) {
            commandUsageChart.data.datasets[0].data[commandIndex]++;
            commandUsageChart.update();
        }
    }
}

function updateUserCount(data) {
    const userCountElement = document.getElementById('user-count');
    if (userCountElement && data.count) {
        updateStatWithAnimation('user-count', data.count);
    }
}

function addModerationLogEntry(data) {
    // Add new moderation log entry to the top of the list
    const container = document.getElementById('moderation-logs');
    if (!container || !data) return;

    const logEntry = `
        <div class="moderation-log-entry border-bottom py-2">
            <div class="d-flex justify-content-between">
                <div>
                    <span class="badge bg-${getModerationActionColor(data.action)}">${data.action}</span>
                    <strong>${data.target_user}</strong>
                    <span class="text-muted">by ${data.moderator}</span>
                </div>
                <small class="text-muted">${formatRelativeTime(data.timestamp)}</small>
            </div>
            ${data.reason ? `<div class="text-muted small mt-1">${data.reason}</div>` : ''}
        </div>
    `;
    
    container.insertAdjacentHTML('afterbegin', logEntry);
}

function addNotification(data) {
    // Add new notification to the notifications list
    const container = document.getElementById('notifications-list');
    if (!container || !data) return;

    const notification = `
        <div class="notification-item d-flex align-items-start p-3 border-bottom">
            <i class="fas fa-${getNotificationIcon(data.type)} text-${data.type} me-2 mt-1"></i>
            <div class="flex-grow-1">
                <div class="fw-bold">${data.title}</div>
                <div class="text-muted">${data.message}</div>
                <small class="text-muted">${formatRelativeTime(data.timestamp)}</small>
            </div>
        </div>
    `;
    
    container.insertAdjacentHTML('afterbegin', notification);
}

function updateBotStatus(data) {
    // Update bot status indicator
    const statusElement = document.getElementById('bot-status');
    if (statusElement && data.status) {
        statusElement.textContent = data.status;
        statusElement.className = `badge bg-${data.status === 'online' ? 'success' : 'danger'}`;
    }
}

function filterCurrentTabContent(query) {
    // Filter content in the currently active tab
    const activeTab = document.querySelector('.tab-pane.active');
    if (!activeTab) return;

    // Filter based on tab content type
    const rows = activeTab.querySelectorAll('tr, .card, .list-group-item');
    rows.forEach(row => {
        const text = row.textContent.toLowerCase();
        if (text.includes(query)) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });
}

function showUpdateNotification(updateData) {
    // Show update notification modal or toast
    const message = `Version ${updateData.version} is available. ${updateData.changelog || ''}`;
    showToast(message, 'info', 10000); // Show for 10 seconds
}

function populateConfigForm(config) {
    // Populate configuration form with current settings
    if (!config) return;

    Object.keys(config).forEach(key => {
        const input = document.getElementById(key) || document.querySelector(`[name="${key}"]`);
        if (input) {
            if (input.type === 'checkbox') {
                input.checked = config[key];
            } else {
                input.value = config[key];
            }
        }
    });
}

async function loadChatMessages(channelId = null) {
    // Load chat messages for live chat
    try {
        const endpoint = channelId ? `/api/chat/messages?channel=${channelId}` : '/api/chat/messages';
        const data = await fetchApi(endpoint);
        
        const container = document.getElementById('live-chat-messages');
        if (!container) return;

        if (!data.messages || data.messages.length === 0) {
            container.innerHTML = '<div class="text-muted">No messages found</div>';
            return;
        }

        const messagesList = data.messages.map(msg => `
            <div class="chat-message d-flex align-items-start mb-2">
                <img src="${msg.avatar}" alt="${msg.author}" class="me-2 rounded-circle" width="32" height="32">
                <div>
                    <div class="fw-bold">${msg.author}</div>
                    <div>${msg.content}</div>
                    <small class="text-muted">${formatRelativeTime(msg.timestamp)}</small>
                </div>
            </div>
        `).join('');

        container.innerHTML = messagesList;
        container.scrollTop = container.scrollHeight;
    } catch (error) {
        console.error('Failed to load chat messages:', error);
    }
}

function updateEngagementMetrics(data) {
    // Update engagement metrics display
    if (!data) return;

    const metrics = ['active_users', 'messages_per_hour', 'command_usage_rate', 'retention_rate'];
    metrics.forEach(metric => {
        if (data[metric] !== undefined) {
            updateStatWithAnimation(metric.replace('_', '-'), data[metric]);
        }
    });
}

async function saveConfiguration() {
    // Save bot configuration
    try {
        const formData = new FormData(document.getElementById('config-form'));
        const config = {};
        
        for (let [key, value] of formData.entries()) {
            config[key] = value;
        }

        const response = await fetchApi('/api/bot/config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(config)
        });

        if (response.success) {
            showToast('Configuration saved successfully', 'success');
        } else {
            showToast('Failed to save configuration: ' + (response.error || 'Unknown error'), 'danger');
        }
    } catch (error) {
        console.error('Failed to save configuration:', error);
        showToast('Error saving configuration: ' + error.message, 'danger');
    }
}

// Chart debugging function
function debugChartState(location) {
    console.log(`🔍 Chart Debug at ${location}:`);
    console.log('  - serverActivityChart global:', !!serverActivityChart);
    console.log('  - Canvas element exists:', !!document.getElementById('activityChart'));
    console.log('  - Chart.js loaded:', typeof Chart !== 'undefined');
    
    const canvas = document.getElementById('activityChart');
    if (canvas) {
        const style = window.getComputedStyle(canvas);
        const rect = canvas.getBoundingClientRect();
        console.log('  - Canvas visibility:', {
            opacity: style.opacity,
            display: style.display,
            visibility: style.visibility,
            width: rect.width,
            height: rect.height
        });
        
        const card = canvas.closest('.card');
        if (card) {
            const cardStyle = window.getComputedStyle(card);
            console.log('  - Card visibility:', {
                opacity: cardStyle.opacity,
                animationName: cardStyle.animationName,
                animationPlayState: cardStyle.animationPlayState
            });
        }
    }
}