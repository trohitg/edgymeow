#!/usr/bin/env node
/**
 * Static file server for the whatsapp-rpc web client.
 * Serves web/client/ on localhost, with dynamic /config.js for WebSocket port injection.
 *
 * Based on MachinaOs/scripts/serve-client.js pattern.
 *
 * Environment variables:
 *   WEB_PORT  - Port for the web UI (default: 3001)
 *   WS_PORT   - Go backend WebSocket port (default: 9400)
 */
import { createServer } from 'http';
import { readFile } from 'fs';
import { extname, resolve } from 'path';
import { dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const CLIENT_DIR = resolve(__dirname, '..', 'web', 'client');
const PORT = parseInt(process.env.WEB_PORT) || 3001;
const WS_PORT = parseInt(process.env.WS_PORT || process.env.WHATSAPP_RPC_PORT || process.env.PORT) || 9400;

const MIME_TYPES = {
  '.html': 'text/html',
  '.js': 'text/javascript',
  '.css': 'text/css',
  '.json': 'application/json',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.gif': 'image/gif',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.ttf': 'font/ttf',
};

const server = createServer((req, res) => {
  let url = req.url === '/' ? '/index.html' : req.url;
  url = url.split('?')[0];

  // Dynamic config — injects the Go backend WebSocket port
  if (url === '/config.js') {
    res.writeHead(200, { 'Content-Type': 'text/javascript' });
    res.end(`window.WS_PORT = ${WS_PORT};`);
    return;
  }

  const filePath = resolve(CLIENT_DIR, '.' + url);

  // Prevent path traversal
  if (!filePath.startsWith(CLIENT_DIR)) {
    res.writeHead(403);
    res.end('Forbidden');
    return;
  }

  readFile(filePath, (err, content) => {
    if (err) {
      if (err.code === 'ENOENT' && !extname(url)) {
        // SPA fallback
        readFile(resolve(CLIENT_DIR, 'index.html'), (err2, indexContent) => {
          if (err2) { res.writeHead(404); res.end('Not found'); }
          else { res.writeHead(200, { 'Content-Type': 'text/html' }); res.end(indexContent); }
        });
      } else {
        res.writeHead(404);
        res.end('Not found');
      }
    } else {
      const ext = extname(filePath);
      res.writeHead(200, { 'Content-Type': MIME_TYPES[ext] || 'application/octet-stream' });
      res.end(content);
    }
  });
});

server.listen(PORT, '0.0.0.0', () => {
  console.log(`Web UI: http://localhost:${PORT}`);
  console.log(`Backend: ws://localhost:${WS_PORT}/ws/rpc`);
});
