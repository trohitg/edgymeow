/**
 * Shared application logic for all pages.
 * Initializes RPC client, renders navigation, manages connection status.
 */

// Initialize RPC client
const rpc = new RpcClient();
window.rpc = rpc;

// Determine WebSocket URL
const wsPort = window.WS_PORT || new URLSearchParams(window.location.search).get('wsPort') || 9400;
const wsUrl = `ws://127.0.0.1:${wsPort}/ws/rpc`;

// Current page for nav highlighting
const currentPage = window.location.pathname.split('/').pop() || 'index.html';

// WhatsApp connection status (from event.status)
let waConnected = false;
let waHasSession = false;

/**
 * Render the navigation bar into #main-nav
 */
function renderNav() {
  const nav = document.getElementById('main-nav');
  if (!nav) return;

  const pages = [
    { href: '/', label: 'Dashboard', match: ['index.html', '', '/'] },
    {
      label: 'Messaging', dropdown: [
        { href: '/send.html', label: 'Simple Send' },
        { href: '/messaging.html', label: 'Enhanced Messaging' },
        { href: '/messages.html', label: 'Received Messages' },
      ]
    },
    { href: '/groups.html', label: 'Groups', match: ['groups.html'] },
    { href: '/contacts.html', label: 'Contacts', match: ['contacts.html'] },
    { href: '/settings.html', label: 'Settings', match: ['settings.html'] },
  ];

  const isActive = (item) => {
    if (item.match) return item.match.includes(currentPage);
    return false;
  };

  const linkClass = 'text-white hover:text-green-200 px-3 py-2 rounded text-sm';

  let navLinks = '';
  for (const item of pages) {
    if (item.dropdown) {
      const dropdownItems = item.dropdown.map(d =>
        `<a href="${d.href}" class="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-100">${d.label}</a>`
      ).join('');
      navLinks += `
        <div class="relative group">
          <button class="${linkClass} flex items-center">
            ${item.label}
            <svg class="w-4 h-4 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path>
            </svg>
          </button>
          <div class="absolute left-0 mt-2 w-48 bg-white rounded-md shadow-lg opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 z-50">
            ${dropdownItems}
          </div>
        </div>`;
    } else {
      navLinks += `<a href="${item.href}" class="${linkClass}">${item.label}</a>`;
    }
  }

  nav.innerHTML = `
    <div class="bg-green-600 shadow-lg">
      <div class="max-w-7xl mx-auto px-4">
        <div class="flex justify-between items-center h-16">
          <div class="flex items-center">
            <h1 class="text-white text-xl font-bold">
              <a href="/">WhatsApp Controller</a>
            </h1>
          </div>
          <div class="flex items-center space-x-4">
            <div id="status-indicator" class="flex items-center text-white">
              <span id="status-dot" class="inline-block w-3 h-3 rounded-full mr-2 bg-red-500"></span>
              <span id="status-text">Disconnected</span>
            </div>
            <div class="flex items-center space-x-1">
              ${navLinks}
            </div>
          </div>
        </div>
      </div>
    </div>`;
}

/**
 * Update the status indicator in the nav bar.
 */
function updateStatusIndicator(wsState) {
  const dot = document.getElementById('status-dot');
  const text = document.getElementById('status-text');
  if (!dot || !text) return;

  if (wsState === 'connected' && waConnected) {
    dot.className = 'inline-block w-3 h-3 rounded-full mr-2 bg-green-500';
    text.textContent = 'Connected';
  } else if (wsState === 'connected') {
    dot.className = 'inline-block w-3 h-3 rounded-full mr-2 bg-yellow-500 animate-pulse';
    text.textContent = waHasSession ? 'Connecting' : 'Disconnected';
  } else if (wsState === 'connecting') {
    dot.className = 'inline-block w-3 h-3 rounded-full mr-2 bg-yellow-500 animate-pulse';
    text.textContent = 'Connecting...';
  } else {
    dot.className = 'inline-block w-3 h-3 rounded-full mr-2 bg-red-500';
    text.textContent = 'Offline';
  }
}

/**
 * Show a toast notification.
 */
function showNotification(message, type = 'info') {
  const colors = {
    success: 'bg-green-500',
    error: 'bg-red-500',
    info: 'bg-blue-500',
    warning: 'bg-yellow-500 text-black',
  };
  const notification = document.createElement('div');
  notification.className = `fixed top-4 right-4 p-4 rounded-lg shadow-lg z-50 text-white ${colors[type] || colors.info}`;
  notification.textContent = message;
  document.body.appendChild(notification);
  setTimeout(() => notification.remove(), 3000);
}

/**
 * Escape HTML to prevent XSS.
 */
function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

/**
 * Format file size in bytes to human readable.
 */
function formatFileSize(bytes) {
  if (!bytes || bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
}

// --- Initialize ---

// Render nav
renderNav();

// Track WebSocket connection state
rpc.onStateChange((state) => {
  updateStatusIndicator(state);

  // On connect, request WhatsApp status
  if (state === 'connected') {
    rpc.call('status').then(result => {
      waConnected = !!result.connected;
      waHasSession = !!result.has_session;
      updateStatusIndicator('connected');
    }).catch(() => {});
  }
});

// Listen for WhatsApp status events
rpc.on('event.status', (params) => {
  waConnected = !!params.connected;
  waHasSession = !!params.has_session;
  updateStatusIndicator(rpc.state);
});

rpc.on('event.connected', () => {
  waConnected = true;
  updateStatusIndicator(rpc.state);
});

rpc.on('event.disconnected', () => {
  waConnected = false;
  updateStatusIndicator(rpc.state);
});

rpc.on('event.logged_out', () => {
  waConnected = false;
  waHasSession = false;
  updateStatusIndicator(rpc.state);
});

// Connect
rpc.connect(wsUrl);

// Refresh status periodically
setInterval(() => {
  if (rpc.connected) {
    rpc.call('status').then(result => {
      waConnected = !!result.connected;
      waHasSession = !!result.has_session;
      updateStatusIndicator('connected');
    }).catch(() => {});
  }
}, 30000);
