import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/services.dart' show rootBundle;

/// Serves static web assets from Flutter's rootBundle via a local HTTP server.
/// Injects the Go backend WebSocket port via a dynamic /config.js endpoint.
class WebServer {
  HttpServer? _server;
  final int _backendWsPort;
  final Map<String, Uint8List> _cache = {};

  WebServer(this._backendWsPort);

  int? get port => _server?.port;

  Future<void> start() async {
    _server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    _server!.listen(_handle);
  }

  Future<void> stop() async {
    await _server?.close();
    _server = null;
  }

  Future<void> _handle(HttpRequest req) async {
    var path = req.uri.path;
    if (path == '/') path = '/index.html';

    // Dynamic config — inject WebSocket port
    if (path == '/config.js') {
      req.response
        ..headers.contentType = ContentType('application', 'javascript')
        ..write('window.WS_PORT = $_backendWsPort;')
        ..close();
      return;
    }

    final assetPath = 'assets/web$path';

    try {
      final bytes = _cache[assetPath] ?? await _loadAsset(assetPath);
      _cache[assetPath] = bytes;
      req.response
        ..headers.contentType = _contentType(path)
        ..add(bytes)
        ..close();
    } catch (_) {
      req.response
        ..statusCode = HttpStatus.notFound
        ..write('Not found')
        ..close();
    }
  }

  Future<Uint8List> _loadAsset(String path) async {
    final data = await rootBundle.load(path);
    return data.buffer.asUint8List();
  }

  ContentType _contentType(String path) {
    if (path.endsWith('.html')) return ContentType.html;
    if (path.endsWith('.js')) return ContentType('application', 'javascript');
    if (path.endsWith('.css')) return ContentType('text', 'css');
    if (path.endsWith('.json')) return ContentType.json;
    if (path.endsWith('.png')) return ContentType('image', 'png');
    if (path.endsWith('.jpg')) return ContentType('image', 'jpeg');
    if (path.endsWith('.svg')) return ContentType('image', 'svg+xml');
    return ContentType.binary;
  }
}
