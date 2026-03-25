/**
 * WebSocket JSON-RPC 2.0 Client for whatsapp-rpc
 * Connects directly to the Go backend at ws://localhost:PORT/ws/rpc
 *
 * Based on ws-chat test-client.html pattern.
 */
class RpcClient {
  constructor() {
    this._ws = null;
    this._requestId = 0;
    this._pending = new Map(); // id -> { resolve, reject, timer }
    this._eventListeners = new Map(); // event -> Set<callback>
    this._stateListeners = new Set();
    this._state = 'disconnected'; // disconnected, connecting, connected
    this._reconnectTimer = null;
    this._reconnectDelay = 1000;
    this._maxReconnectDelay = 10000;
    this._wsUrl = null;
  }

  get state() { return this._state; }
  get connected() { return this._state === 'connected'; }

  /**
   * Connect to the WebSocket RPC server.
   * @param {string} wsUrl - e.g. 'ws://127.0.0.1:9400/ws/rpc'
   */
  connect(wsUrl) {
    if (wsUrl) this._wsUrl = wsUrl;
    if (!this._wsUrl) throw new Error('No WebSocket URL provided');

    this._clearReconnect();
    this._setState('connecting');

    try {
      this._ws = new WebSocket(this._wsUrl);
    } catch (e) {
      this._setState('disconnected');
      this._scheduleReconnect();
      return;
    }

    this._ws.onopen = () => {
      this._setState('connected');
      this._reconnectDelay = 1000;
    };

    this._ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        this._handleMessage(msg);
      } catch (e) {
        console.error('Failed to parse message:', e);
      }
    };

    this._ws.onerror = () => {
      // onclose will fire after this
    };

    this._ws.onclose = () => {
      this._setState('disconnected');
      this._rejectAllPending('WebSocket closed');
      this._scheduleReconnect();
    };
  }

  /**
   * Call an RPC method and return a Promise.
   * @param {string} method - RPC method name (e.g. 'status', 'send')
   * @param {object} [params] - Method parameters
   * @param {number} [timeout=30000] - Timeout in ms
   * @returns {Promise<any>} - The result field from the response
   */
  call(method, params, timeout = 30000) {
    return new Promise((resolve, reject) => {
      if (!this._ws || this._ws.readyState !== WebSocket.OPEN) {
        reject(new Error('Not connected'));
        return;
      }

      const id = ++this._requestId;
      const timer = setTimeout(() => {
        this._pending.delete(id);
        reject(new Error(`Request timeout: ${method}`));
      }, timeout);

      this._pending.set(id, { resolve, reject, timer });

      this._ws.send(JSON.stringify({
        jsonrpc: '2.0',
        id: id,
        method: method,
        ...(params !== undefined && params !== null ? { params } : {})
      }));
    });
  }

  /**
   * Subscribe to server-pushed events.
   * @param {string} event - Event name (e.g. 'event.qr_code', 'event.connected')
   * @param {function} callback - Called with event params
   */
  on(event, callback) {
    if (!this._eventListeners.has(event)) {
      this._eventListeners.set(event, new Set());
    }
    this._eventListeners.get(event).add(callback);
  }

  /**
   * Unsubscribe from an event.
   */
  off(event, callback) {
    const listeners = this._eventListeners.get(event);
    if (listeners) listeners.delete(callback);
  }

  /**
   * Listen for connection state changes.
   * @param {function} callback - Called with state string
   */
  onStateChange(callback) {
    this._stateListeners.add(callback);
  }

  /**
   * Close the connection (no reconnect).
   */
  close() {
    this._clearReconnect();
    if (this._ws) {
      this._ws.onclose = null;
      this._ws.close();
      this._ws = null;
    }
    this._rejectAllPending('Connection closed');
    this._setState('disconnected');
  }

  // --- Internal ---

  _handleMessage(msg) {
    // Response to a request (has id)
    if (msg.id != null && this._pending.has(msg.id)) {
      const { resolve, reject, timer } = this._pending.get(msg.id);
      this._pending.delete(msg.id);
      clearTimeout(timer);

      if (msg.error) {
        reject(new Error(msg.error.message || 'RPC error'));
      } else {
        resolve(msg.result);
      }
      return;
    }

    // Server notification/event (has method, no id)
    if (msg.method) {
      const listeners = this._eventListeners.get(msg.method);
      if (listeners) {
        for (const cb of listeners) {
          try { cb(msg.params || {}); } catch (e) { console.error('Event handler error:', e); }
        }
      }

      // Also emit to wildcard '*' listeners
      const wildcardListeners = this._eventListeners.get('*');
      if (wildcardListeners) {
        for (const cb of wildcardListeners) {
          try { cb(msg.method, msg.params || {}); } catch (e) { console.error('Wildcard handler error:', e); }
        }
      }
    }
  }

  _setState(state) {
    if (this._state === state) return;
    this._state = state;
    for (const cb of this._stateListeners) {
      try { cb(state); } catch (e) { console.error('State listener error:', e); }
    }
  }

  _scheduleReconnect() {
    this._clearReconnect();
    this._reconnectTimer = setTimeout(() => {
      this._reconnectDelay = Math.min(this._reconnectDelay * 1.5, this._maxReconnectDelay);
      this.connect();
    }, this._reconnectDelay);
  }

  _clearReconnect() {
    if (this._reconnectTimer) {
      clearTimeout(this._reconnectTimer);
      this._reconnectTimer = null;
    }
  }

  _rejectAllPending(reason) {
    for (const [id, { reject, timer }] of this._pending) {
      clearTimeout(timer);
      reject(new Error(reason));
    }
    this._pending.clear();
  }
}

// Export as global
window.RpcClient = RpcClient;
