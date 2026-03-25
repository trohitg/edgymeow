import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:wakelock_plus/wakelock_plus.dart';
import 'package:webview_flutter/webview_flutter.dart';

import 'web_server.dart';

const _defaultPort = 9400;
const _channel = MethodChannel('com.crossmeow/backend');

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const CrossMeowApp());
}

class CrossMeowApp extends StatelessWidget {
  const CrossMeowApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'CrossMeow',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: Colors.teal,
          brightness: Brightness.dark,
        ),
        useMaterial3: true,
      ),
      home: const HomePage(),
    );
  }
}

class HomePage extends StatefulWidget {
  const HomePage({super.key});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  String _status = 'Starting backend...';
  WebServer? _webServer;
  WebViewController? _webViewController;
  bool _ready = false;
  int _backendPort = _defaultPort;

  @override
  void initState() {
    super.initState();
    _init();
  }

  @override
  void dispose() {
    WakelockPlus.disable();
    _webServer?.stop();
    _stopBackend();
    super.dispose();
  }

  Future<void> _init() async {
    try {
      // 1. Start Go backend
      setState(() => _status = 'Starting backend...');
      final result = await _channel.invokeMethod<Map>('startBackend', {'port': _backendPort});
      if (result != null && result['port'] != null) {
        _backendPort = result['port'] as int;
      }

      // Wait for backend to be ready
      await Future.delayed(const Duration(seconds: 3));

      // 2. Start Dart web server serving static assets
      setState(() => _status = 'Starting web server...');
      _webServer = WebServer(_backendPort);
      await _webServer!.start();

      // 3. Enable wakelock
      WakelockPlus.enable();

      // 4. Create WebView controller
      final controller = WebViewController()
        ..setJavaScriptMode(JavaScriptMode.unrestricted)
        ..setNavigationDelegate(NavigationDelegate(
          onPageStarted: (_) => setState(() => _status = 'Loading...'),
          onPageFinished: (_) => setState(() {
            _status = 'Ready';
            _ready = true;
          }),
          onWebResourceError: (error) {
            setState(() => _status = 'Error: ${error.description}');
          },
        ))
        ..loadRequest(Uri.parse('http://127.0.0.1:${_webServer!.port}/'));

      setState(() {
        _webViewController = controller;
      });
    } on PlatformException catch (e) {
      setState(() => _status = 'Backend failed: ${e.message}');
    } catch (e) {
      setState(() => _status = 'Error: $e');
    }
  }

  Future<void> _stopBackend() async {
    try {
      await _channel.invokeMethod('stopBackend');
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    if (_webViewController == null) {
      return Scaffold(
        backgroundColor: Colors.grey.shade900,
        body: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const CircularProgressIndicator(),
              const SizedBox(height: 16),
              Text(_status, style: const TextStyle(color: Colors.white70)),
            ],
          ),
        ),
      );
    }

    return Scaffold(
      body: SafeArea(
        child: WebViewWidget(controller: _webViewController!),
      ),
    );
  }
}
