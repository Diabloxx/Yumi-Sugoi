// Fetch and display personas
fetch('/api/personas')
  .then(res => res.json())
  .then(data => {
    const el = document.getElementById('personas-list');
    let html = '<strong>Default Personas:</strong><ul>';
    data.default.forEach(p => html += `<li><i class='fa-solid fa-star text-warning'></i> ${p}</li>`);
    html += '</ul><strong>Custom Personas:</strong><ul>';
    if (data.custom.length === 0) html += '<li><em>None yet</em></li>';
    else data.custom.forEach(p => html += `<li><i class='fa-solid fa-user-pen text-info'></i> ${p}</li>`);
    html += '</ul>';
    el.innerHTML = html;
  });

// User XP lookup
const xpForm = document.getElementById('xp-form');
xpForm.addEventListener('submit', function(e) {
  e.preventDefault();
  const userId = document.getElementById('user-id-input').value;
  const result = document.getElementById('xp-result');
  if (!userId) {
    result.innerHTML = '<span class="text-danger">Please enter a user ID.</span>';
    return;
  }
  result.innerHTML = '<div class="spinner-border text-success" role="status"></div>';
  fetch(`/api/user/${userId}/xp`)
    .then(res => res.json())
    .then(data => {
      result.innerHTML = `<strong>Level:</strong> ${data.level} <br><strong>XP:</strong> ${data.xp}`;
    })
    .catch(() => {
      result.innerHTML = '<span class="text-danger">User not found or error.</span>';
    });
});

// Fetch and display servers Yumi is in
function loadServers() {
    fetch('/api/servers')
        .then(res => res.json())
        .then(servers => {
            const list = document.getElementById('servers-list');
            if (!servers.length) {
                list.innerHTML = '<div class="text-muted">No servers found.</div>';
                return;
            }
            let html = '<ul class="list-group">';
            servers.forEach(s => {
                html += `<li class="list-group-item d-flex justify-content-between align-items-center">
                    <span><strong>${s.name}</strong> <span class="text-muted">(ID: ${s.id})</span></span>
                    <span class="badge bg-primary">${s.member_count} members</span>
                    <button class="btn btn-sm btn-outline-secondary ms-2" onclick="loadServerSettings(${s.id}, '${s.name}')">Settings</button>
                </li>`;
            });
            html += '</ul>';
            list.innerHTML = html;
        });
}

// Ensure servers list refreshes when the Servers tab is shown
const serversTab = document.getElementById('servers-tab');
if (serversTab) {
    serversTab.addEventListener('shown.bs.tab', function() {
        loadServers();
    });
}

// Ensure live chat servers reload when the Live Chat tab is shown
const liveChatTab = document.getElementById('livechat-tab');
if (liveChatTab) {
    liveChatTab.addEventListener('shown.bs.tab', function() {
        showLiveChatUI();
    });
}

// Fetch and display settings for a server (only official server is editable)
function loadServerSettings(serverId, serverName) {
    const settingsDiv = document.getElementById('official-server-settings');
    settingsDiv.innerHTML = '<div class="spinner-border text-secondary" role="status"></div>';
    fetch(`/api/server/${serverId}/settings`)
        .then(res => res.json())
        .then(data => {
            if (data.error) {
                settingsDiv.innerHTML = `<div class="alert alert-danger">${data.error}</div>`;
                return;
            }
            // Settings form (mode, lockdown channels, lockdown toggle)
            let html = `<h6>${serverName}</h6>`;
            html += `<form id="server-settings-form">
                <div class="mb-2">
                    <label class="form-label">Persona Mode</label>
                    <select class="form-select" name="mode">
                        ${data.all_modes.map(m => `<option value="${m}"${m===data.mode?' selected':''}>${m}</option>`).join('')}
                    </select>
                </div>
                <div class="mb-2">
                    <label class="form-label">Locked Channels (IDs, comma separated)</label>
                    <input type="text" class="form-control" name="locked_channels" value="${data.locked_channels.join(',')}">
                </div>
                <div class="form-check form-switch mb-2">
                    <input class="form-check-input" type="checkbox" id="lockdownSwitch" name="lockdown"${data.lockdown?' checked':''}>
                    <label class="form-check-label" for="lockdownSwitch">Lockdown Active</label>
                </div>
                <button class="btn btn-primary" type="submit">Save Settings</button>
            </form>`;
            settingsDiv.innerHTML = html;
            document.getElementById('server-settings-form').onsubmit = function(e) {
                e.preventDefault();
                const form = e.target;
                const mode = form.mode.value;
                const locked_channels = form.locked_channels.value.split(',').map(x => x.trim()).filter(x => x);
                const lockdown = form.lockdown.checked;
                fetch(`/api/server/${serverId}/settings`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({mode, locked_channels, lockdown})
                })
                .then(res => res.json())
                .then(resp => {
                    if (resp.success) {
                        settingsDiv.innerHTML += '<div class="alert alert-success mt-2">Settings updated!</div>';
                    } else {
                        settingsDiv.innerHTML += '<div class="alert alert-danger mt-2">Failed to update settings.</div>';
                    }
                });
            };
        });
}

// Fetch and display moderation logs for the official server (placeholder)
function loadModerationLogs() {
    fetch('/api/server/1375103404493373510/logs') // Replace with your official server ID
        .then(res => res.json())
        .then(data => {
            if (data.error) {
                logsDiv.innerHTML = `<div class="alert alert-danger">${data.error}</div>`;
                return;
            }
            if (!data.logs || !data.logs.length) {
                logsDiv.innerHTML = '<div class="text-muted">No logs found.</div>';
                return;
            }
            let html = '<ul class="list-group">';
            data.logs.forEach(log => {
                html += `<li class="list-group-item small">${log}</li>`;
            });
            html += '</ul>';
            logsDiv.innerHTML = html;
        })
        .catch(() => {
            logsDiv.innerHTML = '<div class="text-muted">No logs available (API not implemented).</div>';
        });
}

// Real-time log updates (poll every 5s)
let logInterval = null;
function startLogPolling() {
    if (logInterval) clearInterval(logInterval);
    loadModerationLogs();
    logInterval = setInterval(loadModerationLogs, 5000);
}

// Persona editing UI (basic: rename, delete, add)
function loadPersonaManagement() {
    const pmDiv = document.getElementById('persona-management');
    fetch('/api/personas')
        .then(res => res.json())
        .then(data => {
            let html = '<h6>Available Personas</h6>';
            html += '<ul class="list-group mb-2">';
            data.default.forEach(p => {
                html += `<li class="list-group-item d-flex justify-content-between align-items-center">${p}<span class='text-muted small'>(default)</span></li>`;
            });
            if (data.custom && data.custom.length) {
                html += '<li class="list-group-item list-group-item-info">Custom Personas:</li>';
                data.custom.forEach(p => {
                    html += `<li class="list-group-item d-flex justify-content-between align-items-center">${p}
                        <span>
                            <button class="btn btn-sm btn-outline-danger" onclick="deletePersona('${p}')"><i class="fa fa-trash"></i></button>
                        </span>
                    </li>`;
                });
            }
            html += '</ul>';
            html += `<form id="add-persona-form" class="mt-2">
                <div class="input-group">
                    <input type="text" class="form-control" name="persona_name" placeholder="New persona name">
                    <button class="btn btn-info" type="submit"><i class="fa fa-plus"></i> Add</button>
                </div>
            </form>`;
            pmDiv.innerHTML = html;
            document.getElementById('add-persona-form').onsubmit = function(e) {
                e.preventDefault();
                const name = e.target.persona_name.value.trim();
                if (!name) return;
                fetch('/api/persona', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({name})
                }).then(() => loadPersonaManagement());
            };
        })
        .catch(() => {
            pmDiv.innerHTML = '<div class="text-muted">Persona management not available.</div>';
        });
}
window.deletePersona = function(name) {
    if (!confirm('Delete persona ' + name + '?')) return;
    fetch('/api/persona/' + encodeURIComponent(name), {method: 'DELETE'})
        .then(() => loadPersonaManagement());
};

// --- LIVE CHAT CONSOLE ---
function showLiveChatUI() {
    console.log('showLiveChatUI called');
    const liveChatDiv = document.getElementById('live-chat');
    if (!liveChatDiv) return;
    liveChatDiv.innerHTML = `
        <div class="card mb-3 p-3">
            <form id="live-chat-form" class="d-flex align-items-center mb-2">
                <select id="chat-server-select" class="form-select me-2" style="max-width:200px"></select>
                <select id="chat-channel-select" class="form-select me-2" style="max-width:200px"></select>
                <input type="text" id="chat-message-input" class="form-control me-2" placeholder="Type a message...">
                <button class="btn btn-primary" type="submit"><i class="fa fa-paper-plane"></i> Send</button>
            </form>
            <div id="live-chat-feed" class="bg-light rounded p-3" style="min-height:200px; max-height:400px; overflow-y:auto;"></div>
        </div>
    `;
    document.getElementById('live-chat-form').onsubmit = sendLiveChatMessage;
    loadLiveChatServers();
}

// (Removed duplicate liveChatTab declaration here)
if (liveChatTab) {
    liveChatTab.addEventListener('shown.bs.tab', function() {
        showLiveChatUI();
    });
}

function loadLiveChatServers() {
    fetch('/api/servers')
        .then(res => res.json())
        .then(servers => {
            const serverSelect = document.getElementById('chat-server-select');
            const channelSelect = document.getElementById('chat-channel-select');
            if (!servers.length) {
                serverSelect.innerHTML = '<option>No servers</option>';
                channelSelect.innerHTML = '<option>No channels</option>';
                return;
            }
            serverSelect.innerHTML = servers.map(s => `<option value="${s.id}">${s.name}</option>`).join('');
            // Set channels for first server
            if (servers[0].channels.length) {
                channelSelect.innerHTML = servers[0].channels.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
            } else {
                channelSelect.innerHTML = '<option>No channels</option>';
            }
            serverSelect.onchange = function() {
                const selected = servers.find(s => s.id == serverSelect.value);
                if (selected && selected.channels.length) {
                    channelSelect.innerHTML = selected.channels.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
                } else {
                    channelSelect.innerHTML = '<option>No channels</option>';
                }
                loadLiveChatFeed();
            };
            channelSelect.onchange = loadLiveChatFeed;
            loadLiveChatFeed();
        });
}
function sendLiveChatMessage(e) {
    e.preventDefault();
    const serverId = document.getElementById('chat-server-select').value;
    const channelId = document.getElementById('chat-channel-select').value;
    const content = document.getElementById('chat-message-input').value;
    if (!content) return;
    fetch('/api/live_chat', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({server_id: serverId, channel_id: channelId, message: content})
    }).then(() => {
        document.getElementById('chat-message-input').value = '';
        loadLiveChatFeed();
    });
}
function loadLiveChatFeed() {
    const serverId = document.getElementById('chat-server-select').value;
    const channelId = document.getElementById('chat-channel-select').value;
    fetch(`/api/live_chat?server_id=${serverId}&channel_id=${channelId}`)
        .then(res => res.json())
        .then(data => {
            const feed = document.getElementById('live-chat-feed');
            if (!data.messages || !data.messages.length) {
                feed.innerHTML = '<div class="text-muted">No messages yet.</div>';
                return;
            }
            feed.innerHTML = data.messages.map(m => `<div><strong>${m.author}:</strong> ${m.content}</div>`).join('');
        });
}

// On page load, if live chat is visible, render UI
if (document.getElementById('livechat').classList.contains('show')) {
    showLiveChatUI();
}

// --- USER MANAGEMENT ---
document.getElementById('user-management').innerHTML = `
  <form id="user-search-form" class="mb-3 d-flex align-items-center">
    <input type="text" class="form-control me-2" id="user-search-input" placeholder="Search users by name or ID">
    <button class="btn btn-info" type="submit"><i class="fa fa-search"></i> Search</button>
  </form>
  <div id="user-search-results"></div>
  <div id="user-profile-modal" style="display:none;"></div>
`;
document.getElementById('user-search-form').onsubmit = function(e) {
    e.preventDefault();
    const q = document.getElementById('user-search-input').value;
    fetch(`/api/users/search?q=${encodeURIComponent(q)}`)
        .then(res => res.json())
        .then(users => {
            const results = document.getElementById('user-search-results');
            if (!users.length) {
                results.innerHTML = '<div class="text-muted">No users found.</div>';
                return;
            }
            let html = '<ul class="list-group">';
            users.forEach(u => {
                html += `<li class="list-group-item d-flex justify-content-between align-items-center">
                    <span>${u.name} <span class="text-muted">(ID: ${u.id}, ${u.guild})</span></span>
                    <button class="btn btn-sm btn-outline-info" onclick="showUserProfile(${u.id})">Profile</button>
                </li>`;
            });
            html += '</ul>';
            results.innerHTML = html;
        });
};
window.showUserProfile = function(userId) {
    fetch(`/api/user/${userId}`)
        .then(res => res.json())
        .then(data => {
            const modal = document.getElementById('user-profile-modal');
            let html = `<div class="card"><div class="card-body">
                <h5>${data.name} <span class="text-muted small">(ID: ${data.id})</span></h5>
                <div><strong>Level:</strong> ${data.level} | <strong>XP:</strong> ${data.xp}</div>
                <div><strong>Facts:</strong> ${data.facts || '<em>None</em>'}</div>
                <div><strong>Joined:</strong> ${data.joined_at}</div>
                <div><strong>Infractions:</strong> ${data.infractions.length ? data.infractions.join(', ') : '<em>None</em>'}</div>
                <div class="mt-2">
                    <button class="btn btn-danger btn-sm me-2" onclick="userAction(${data.id},'kick')">Kick</button>
                    <button class="btn btn-warning btn-sm me-2" onclick="userAction(${data.id},'ban')">Ban</button>
                    <button class="btn btn-success btn-sm" onclick="userAction(${data.id},'unban')">Unban</button>
                    <button class="btn btn-secondary btn-sm float-end" onclick="closeUserProfile()">Close</button>
                </div>
            </div></div>`;
            modal.innerHTML = html;
            modal.style.display = 'block';
        });
};
window.closeUserProfile = function() {
    document.getElementById('user-profile-modal').style.display = 'none';
};
window.userAction = function(userId, action) {
    fetch(`/api/user/${userId}/action`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({action})
    }).then(() => closeUserProfile());
};

// --- SCHEDULED TASKS ---
function loadScheduledTasks() {
    fetch('/api/scheduled')
        .then(res => res.json())
        .then(tasks => {
            const list = document.getElementById('scheduled-list');
            if (!tasks.length) {
                list.innerHTML = '<div class="text-muted">No scheduled tasks.</div>';
                return;
            }
            let html = '<table class="table table-sm"><thead><tr><th>Time</th><th>Channel</th><th>Message</th><th></th></tr></thead><tbody>';
            tasks.forEach((t,i) => {
                html += `<tr><td>${t.time}</td><td>${t.channel_id}</td><td>${t.message}</td>
                    <td><button class="btn btn-sm btn-danger" onclick="deleteScheduled(${i})"><i class="fa fa-trash"></i></button></td></tr>`;
            });
            html += '</tbody></table>';
            list.innerHTML = html;
        });
}
document.getElementById('add-scheduled-btn').onclick = function() {
    const time = prompt('Enter time (YYYY-MM-DD HH:MM)');
    const channel_id = prompt('Enter channel ID');
    const message = prompt('Enter message');
    if (!time || !channel_id || !message) return;
    fetch('/api/scheduled', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({time, channel_id, message})
    }).then(() => loadScheduledTasks());
};
window.deleteScheduled = function(index) {
    fetch(`/api/scheduled/${index}`, {method: 'DELETE'})
        .then(() => loadScheduledTasks());
};

// Moderation Logs
function loadModerationLogs() {
  fetch('/api/moderation_logs')
    .then(r => r.json())
    .then(data => {
      const logs = data.logs || [];
      const ul = document.getElementById('moderation-logs');
      ul.innerHTML = '';
      if (logs.length === 0) {
        ul.innerHTML = '<li class="list-group-item">No moderation logs found.</li>';
      } else {
        logs.forEach(log => {
          const li = document.createElement('li');
          li.className = 'list-group-item';
          li.textContent = log;
          ul.appendChild(li);
        });
      }
    });
}
document.getElementById('refresh-moderation-logs').onclick = loadModerationLogs;

// Analytics
function loadAnalytics() {
  fetch('/api/analytics')
    .then(r => r.json())
    .then(data => {
      const summary = document.getElementById('analytics-summary');
      summary.innerHTML = `Guilds: <b>${data.guild_count}</b> | Users: <b>${data.user_count}</b>`;
      // Optionally render chart (placeholder)
      if (window.Chart) {
        const ctx = document.getElementById('analyticsChart').getContext('2d');
        new Chart(ctx, {
          type: 'bar',
          data: {
            labels: ['Guilds', 'Users'],
            datasets: [{
              label: 'Count',
              data: [data.guild_count, data.user_count],
              backgroundColor: ['#17a2b8', '#007bff']
            }]
          },
          options: {responsive: true, plugins: {legend: {display: false}}}
        });
      }
    });
}

// Audit Logs
function loadAuditLogs() {
  fetch('/api/auditlog')
    .then(r => r.json())
    .then(data => {
      const logs = data.logs || [];
      const ul = document.getElementById('audit-logs');
      ul.innerHTML = '';
      if (logs.length === 0) {
        ul.innerHTML = '<li class="list-group-item">No audit log entries found.</li>';
      } else {
        logs.forEach(log => {
          const li = document.createElement('li');
          li.className = 'list-group-item';
          li.textContent = log;
          ul.appendChild(li);
        });
      }
    });
}
document.getElementById('refresh-audit-logs').onclick = loadAuditLogs;

// Chat Logs (Moderation Review)
function loadChatLogs() {
  fetch('/api/chat_logs')
    .then(r => r.json())
    .then(data => {
      const logs = data.logs || {};
      const div = document.getElementById('chat-logs');
      div.innerHTML = '';
      // Render chat logs in a readable format
      Object.entries(logs).forEach(([key, convo]) => {
        const group = document.createElement('div');
        group.className = 'mb-3';
        const title = document.createElement('div');
        title.className = 'fw-bold';
        title.textContent = key;
        group.appendChild(title);
        if (Array.isArray(convo)) {
          convo.forEach(entry => {
            if (Array.isArray(entry) && entry.length === 2) {
              const [role, text] = entry;
              const p = document.createElement('div');
              p.innerHTML = `<span class="badge bg-${role === 'user' ? 'primary' : 'success'}">${role}</span> <span>${text}</span>`;
              group.appendChild(p);
            } else if (typeof entry === 'object' && entry.user && entry.bot) {
              const pUser = document.createElement('div');
              pUser.innerHTML = `<span class="badge bg-primary">user</span> <span>${entry.user}</span>`;
              group.appendChild(pUser);
              const pBot = document.createElement('div');
              pBot.innerHTML = `<span class="badge bg-success">bot</span> <span>${entry.bot}</span>`;
              group.appendChild(pBot);
            }
          });
        }
        div.appendChild(group);
      });
    });
}
document.getElementById('refresh-chat-logs').onclick = loadChatLogs;

document.addEventListener('DOMContentLoaded', function() {
    loadServers();
    startLogPolling();
    loadPersonaManagement();
    loadLiveChatServers();
    document.getElementById('live-chat-form').onsubmit = sendLiveChatMessage;
    document.getElementById('chat-server-select').onchange = function() {
        loadLiveChatFeed();
    };
    document.getElementById('chat-channel-select').onchange = function() {
        loadLiveChatFeed();
    };
    setInterval(loadLiveChatFeed, 5000);
    loadScheduledTasks();
    loadModerationLogs();
    loadAnalytics();
    loadAuditLogs();
    loadChatLogs();
    showLiveChatUI();
});
