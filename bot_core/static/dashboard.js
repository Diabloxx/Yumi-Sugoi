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
            };

            this.socket.onclose = (event) => {
                console.log(`❌ WebSocket disconnected (code: ${event.code})`);
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
                    this.reconnectAttempts++;
                } else {
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

            this.    socket.onmessage = (event) => {
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
    });

    // Initialize charts
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
                await Promise.all([
                    loadDashboardOverview(),
                    updateCharts(),
                    loadActiveServers()
                ]);
                break;
            case '#personas':
                await loadPersonas();
                break;
            case '#servers':
                await loadServers();
                break;
            case '#users':
                await loadUsers();
                break;
            case '#moderation':
                await loadModerationLogs();
                break;
            case '#analytics':
                await loadAnalytics();
                break;
            case '#livechat':
                await loadActiveChannels();
                break;
            case '#scheduled':
                await loadScheduledTasks();
                break;
            case '#settings':
                await loadSettings();
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

        const analyticsData = await fetchApi('/api/analytics');
        
        // Update statistics with animation
        updateStatWithAnimation('server-count', analyticsData.server_count);
        updateStatWithAnimation('user-count', analyticsData.total_users);
        updateStatWithAnimation('message-count', analyticsData.message_count);
        updateStatWithAnimation('persona-count', analyticsData.persona_count);

    } catch (error) {
        console.error('Failed to load dashboard overview:', error);
        loadingIndicators.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.textContent = '-';
        });
    }
}

// Animate number updates
function updateStatWithAnimation(elementId, newValue) {
    const element = document.getElementById(elementId);
    if (!element) return;

    const oldValue = parseInt(element.textContent) || 0;
    const duration = 1000; // 1 second animation
    const steps = 60;
    const stepDuration = duration / steps;
    const increment = (newValue - oldValue) / steps;

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
    const ctx = {
        serverActivity: document.getElementById('serverActivityChart')?.getContext('2d'),
        commandUsage: document.getElementById('commandUsageChart')?.getContext('2d'),
        messageVolume: document.getElementById('messageVolumeChart')?.getContext('2d')
    };

    // Initialize charts if canvas elements exist
    if (ctx.serverActivity) {
        serverActivityChart = createServerActivityChart(ctx.serverActivity);
    }
    if (ctx.commandUsage) {
        commandUsageChart = createCommandUsageChart(ctx.commandUsage);
    }
    if (ctx.messageVolume) {
        messageVolumeChart = createMessageVolumeChart(ctx.messageVolume);
    }
}

// Chart creation functions
function createServerActivityChart(ctx) {
    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: Array(24).fill('').map((_, i) => `${i}:00`),
            datasets: [{
                label: 'Active Servers',
                data: Array(24).fill(0),
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
        const [activityData, commandData, messageData] = await Promise.all([
            fetchApi('/api/analytics/server-activity'),
            fetchApi('/api/analytics/command-usage'),
            fetchApi('/api/analytics/message-volume')
        ]);

        // Update server activity chart
        if (serverActivityChart && activityData) {
            serverActivityChart.data.datasets[0].data = activityData.values;
            serverActivityChart.update();
        }

        // Update command usage chart
        if (commandUsageChart && commandData) {
            commandUsageChart.data.labels = commandData.labels;
            commandUsageChart.data.datasets[0].data = commandData.values;
            commandUsageChart.update();
        }

        // Update message volume chart
        if (messageVolumeChart && messageData) {
            messageVolumeChart.data.datasets[0].data = messageData.values;
            messageVolumeChart.update();
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
        const data = response?.servers || [];
        
        if (!Array.isArray(data) || data.length === 0) {
            container.innerHTML = '<div class="text-muted">No active servers found</div>';
            return;
        }        const serverList = data.map(server => `
            <div class="server-item d-flex align-items-center p-2 border-bottom">
                <img src="${server.icon}" alt="${server.name}" class="me-2 rounded-circle" width="32" height="32">
                <div class="flex-grow-1">
                    <div class="d-flex justify-content-between align-items-center">
                        <strong>${server.name}</strong>
                        <span class="badge bg-primary">${server.member_count} members</span>
                    </div>
                    <small class="text-muted">${server.channels ? server.channels.length : 0} channels</small>
                </div>
            </div>
        `).join('');

        container.innerHTML = serverList;

    } catch (error) {
        console.error('Failed to load active servers:', error);
        container.innerHTML = '<div class="text-danger">Failed to load servers</div>';
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
    refreshDashboard();

    // Initialize WebSocket connection for real-time updates
    // Initialize Socket.IO connection
    const socket = io(window.location.origin, {
        path: '/ws/dashboard',
        transports: ['websocket', 'polling'],
        reconnection: true,
        reconnectionAttempts: 3,
        reconnectionDelay: 1000
    });
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

// Socket.IO connection
const socket = io(window.location.origin, {
    path: '/socket.io',
    transports: ['websocket', 'polling'],
    reconnection: true,
    reconnectionAttempts: 3,
    reconnectionDelay: 1000,
    autoConnect: true
});

// Socket.IO event handlers
socket.on('connect', () => {
    console.log('✅ Connected to WebSocket');
    document.getElementById('connection-status').innerHTML = '🟢 Connected';
});

socket.on('disconnect', () => {
    console.log('❌ WebSocket disconnected');
    document.getElementById('connection-status').innerHTML = '🔴 Disconnected';
});

socket.on('error', (error) => {
    console.error('WebSocket error:', error);
    document.getElementById('connection-status').innerHTML = '🟡 Error';
});

socket.on('stats_update', (data) => {
    updateDashboard(data);
});

// Error handling for data loading
function handleDataError(error, context) {
    console.error(`Failed to load ${context}:`, error);
    // Show error in UI if needed
    const errorDiv = document.getElementById('error-messages');
    if (errorDiv) {
        errorDiv.innerHTML += `<div class="alert alert-danger alert-dismissible fade show">
            <strong>Error loading ${context}:</strong> ${error.message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>`;
    }
}

// Update dashboard with real-time data
function updateDashboard(data) {
    try {
        if (data.servers) {
            updateServerList(data.servers);
        }
        if (data.stats) {
            updateAnalyticsOverview(data.stats);
        }
    } catch (error) {
        handleDataError(error, 'dashboard update');
    }
}

// Server list update
function updateServerList(servers) {
    try {
        const serverList = document.getElementById('server-list');
        if (!serverList) return;

        serverList.innerHTML = servers.map(server => `
            <div class="server-card">
                <img src="${server.icon_url}" alt="${server.name}" class="server-icon">
                <div class="server-info">
                    <h3>${server.name}</h3>
                    <p>${server.member_count} members</p>
                </div>
            </div>
        `).join('');
    } catch (error) {
        handleDataError(error, 'server list');
    }
}

// Analytics overview update
function updateAnalyticsOverview(stats) {
    try {
        document.getElementById('uptime').textContent = stats.uptime;
        document.getElementById('total-servers').textContent = stats.servers;
        document.getElementById('total-members').textContent = stats.total_members;
        document.getElementById('commands-today').textContent = stats.commands_today;
        document.getElementById('messages-today').textContent = stats.messages_today;
    } catch (error) {
        handleDataError(error, 'analytics');
    }
}

// Request updates periodically
function setupPeriodicUpdates() {
    // Initial update
    socket.emit('request_update');
    
    // Regular updates
    setInterval(() => {
        if (socket.connected) {
            socket.emit('request_update');
        }
    }, 30000); // Update every 30 seconds
}

// Initialize when document is ready
document.addEventListener('DOMContentLoaded', () => {
    setupPeriodicUpdates();
});