// main.swift — the smallest AppKit host that lets a web page look native.
//
//   swiftc -O -swift-version 5 main.swift -o NativeLookHost
//   ./NativeLookHost --url file:///…/web/index.html [--backdrop vibrancy|glass|none] [--glass system|blur|solid]
//                    [--appearance system|light|dark] [--screenshot out.png] [--eval 'js'] [--delay 2]
//
// What it demonstrates (each is a few lines, grep for the MARK):
//   1. transparent window + transparent WKWebView, so system materials can show through
//   2. native material behind the web view: NSVisualEffectView (vibrancy) or NSGlassEffectView (macOS 26+ Liquid Glass)
//   3. host attributes injected before first paint: macos=<major>, dark, accent colour, zoom
//   4. live updates when the user changes appearance or accent colour
//   5. a request/response IPC bridge (ipcRequest) with ids, so the page can await native results
//   6. ⌘+ / ⌘- / ⌘0 zoom that only changes a CSS variable

import AppKit
import WebKit

// MARK: options

struct Options {
    var url = URL(string: "about:blank")!
    var backdrop = "vibrancy"          // vibrancy | glass | none
    var glass: String?                 // forwarded to the page as ?glass=
    var appearance = "system"          // system | light | dark
    var screenshot: String?
    var eval: String?                  // JS evaluated after load; its result is printed
    var delay = 2.0
    var prefs: [String] = []           // experimental: KVC keys on WKPreferences set to true
}

func parseOptions() -> Options {
    var o = Options()
    var it = CommandLine.arguments.dropFirst().makeIterator()
    while let a = it.next() {
        switch a {
        case "--url": if let v = it.next(), let u = URL(string: v) { o.url = u }
        case "--backdrop": o.backdrop = it.next() ?? o.backdrop
        case "--glass": o.glass = it.next()
        case "--appearance": o.appearance = it.next() ?? o.appearance
        case "--screenshot": o.screenshot = it.next()
        case "--eval": o.eval = it.next()
        case "--pref": if let v = it.next() { o.prefs.append(v) }
        case "--delay": o.delay = Double(it.next() ?? "") ?? o.delay
        default: break
        }
    }
    return o
}

// MARK: host

final class Host: NSObject, NSApplicationDelegate, WKScriptMessageHandler, WKNavigationDelegate {
    let options: Options
    var window: NSWindow!
    var webView: WKWebView!
    var zoom = 1.0
    var observations: [NSKeyValueObservation] = []
    var effectiveBackdrop = "none"

    init(options: Options) { self.options = options }

    func applicationDidFinishLaunching(_ notification: Notification) {
        switch options.appearance {
        case "dark": NSApp.appearance = NSAppearance(named: .darkAqua)
        case "light": NSApp.appearance = NSAppearance(named: .aqua)
        default: break
        }
        installMenu()
        if options.backdrop == "glass", #unavailable(macOS 26.0) { effectiveBackdrop = "vibrancy" } else { effectiveBackdrop = options.backdrop }

        // MARK: 3. host attributes before first paint
        let configuration = WKWebViewConfiguration()
        let script = WKUserScript(source: Self.bootstrapScript(state: stateJSON()), injectionTime: .atDocumentStart, forMainFrameOnly: true)
        configuration.userContentController.addUserScript(script)
        // MARK: 5. IPC bridge
        configuration.userContentController.add(self, name: "ipcRequest")
        for key in options.prefs {   // experimental, private: report instead of crashing when a key is absent
            if configuration.preferences.responds(to: NSSelectorFromString("_set" + key.prefix(1).uppercased() + key.dropFirst() + ":")) {
                configuration.preferences.setValue(true, forKey: key); print("pref \(key) = true")
            } else { print("pref \(key) not available") }
        }

        webView = WKWebView(frame: .zero, configuration: configuration)
        webView.navigationDelegate = self
        webView.isInspectable = true
        // MARK: 1. transparent web view: without this, system materials have nothing to show through
        webView.setValue(false, forKey: "drawsBackground")
        webView.underPageBackgroundColor = .clear

        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 920, height: 640),
                          styleMask: [.titled, .closable, .miniaturizable, .resizable, .fullSizeContentView],
                          backing: .buffered, defer: false)
        window.title = "Native Look Host"
        window.titlebarAppearsTransparent = true
        window.titleVisibility = .hidden
        window.isOpaque = false
        window.backgroundColor = .clear
        window.center()

        // MARK: 2. native material behind the transparent web view
        if effectiveBackdrop == "glass", #available(macOS 26.0, *) {
            let glass = NSGlassEffectView()
            glass.contentView = webView
            window.contentView = glass
        } else if effectiveBackdrop != "none" {
            let effect = NSVisualEffectView()
            effect.material = .underWindowBackground
            effect.blendingMode = .behindWindow
            effect.state = .active
            webView.frame = effect.bounds
            webView.autoresizingMask = [.width, .height]
            effect.addSubview(webView)
            window.contentView = effect
        } else {
            window.contentView = webView
        }

        var url = options.url
        if let glass = options.glass, var c = URLComponents(url: url, resolvingAgainstBaseURL: false) {
            c.queryItems = (c.queryItems ?? []) + [URLQueryItem(name: "glass", value: glass)]
            url = c.url ?? url
        }
        if url.isFileURL { webView.loadFileURL(url, allowingReadAccessTo: url.deletingLastPathComponent()) }
        else { webView.load(URLRequest(url: url)) }

        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)

        // MARK: 4. live updates
        observations.append(NSApp.observe(\.effectiveAppearance) { [weak self] _, _ in self?.push() })
        DistributedNotificationCenter.default().addObserver(forName: NSNotification.Name("AppleColorPreferencesChangedNotification"), object: nil, queue: .main) { [weak self] _ in self?.push() }
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }

    // MARK: state

    func stateJSON() -> String {
        let v = ProcessInfo.processInfo.operatingSystemVersion
        let dark = NSApp.effectiveAppearance.bestMatch(from: [.darkAqua, .aqua]) == .darkAqua
        let accent = (NSColor.controlAccentColor.usingColorSpace(.sRGB) ?? .systemBlue)
        let hex = String(format: "#%02x%02x%02x", Int(round(accent.redComponent * 255)), Int(round(accent.greenComponent * 255)), Int(round(accent.blueComponent * 255)))
        return "{\"macos\":\"\(v.majorVersion)\",\"dark\":\(dark),\"accent\":\"\(hex)\",\"zoom\":\(zoom),\"backdrop\":\"\(effectiveBackdrop)\"}"
    }

    func push() {
        webView?.evaluateJavaScript("window.__nativeHost && window.__nativeHost.apply(\(stateJSON()))", completionHandler: nil)
    }

    /// Installed at document start. `documentElement` may not exist yet, so retry until it does.
    static func bootstrapScript(state: String) -> String {
        """
        (function () {
          var host = window.__nativeHost = window.__nativeHost || {};
          host.apply = function (s) {
            var r = document.documentElement; if (!r) return false;
            r.setAttribute('macos', s.macos);
            s.dark ? r.setAttribute('dark', '') : r.removeAttribute('dark');
            r.style.setProperty('--color-system-accent', s.accent);
            r.style.setProperty('--zoom', String(s.zoom));
            r.setAttribute('backdrop', s.backdrop);
            window.dispatchEvent(new CustomEvent('nativehost', { detail: s }));
            return true;
          };
          var initial = \(state);
          if (!host.apply(initial)) {
            var mo = new MutationObserver(function () { if (host.apply(initial)) mo.disconnect(); });
            mo.observe(document, { childList: true });
          }
        })();
        """
    }

    // MARK: 5. IPC

    func userContentController(_ controller: WKUserContentController, didReceive message: WKScriptMessage) {
        guard let body = message.body as? [String: Any], let id = body["id"] as? Int, let method = body["method"] as? String else { return }
        var result: Any = NSNull()
        var error: String?
        switch method {
        case "host.info":
            let v = ProcessInfo.processInfo.operatingSystemVersionString
            result = ["os": v, "pid": ProcessInfo.processInfo.processIdentifier]
        case "host.ping": result = "pong"
        default: error = "unknown method \(method)"
        }
        let payload = (try? JSONSerialization.data(withJSONObject: ["r": result], options: [])).flatMap { String(data: $0, encoding: .utf8) } ?? "{\"r\":null}"
        let errJS = error.map { "\"\($0)\"" } ?? "null"
        webView.evaluateJavaScript("window.__nativeHost.resolve(\(id), \(payload).r, \(errJS))", completionHandler: nil)
    }

    // MARK: zoom + screenshot

    @objc func zoomIn() { zoom = min(1.6, (zoom * 100 + 10).rounded() / 100); push() }
    @objc func zoomOut() { zoom = max(0.7, (zoom * 100 - 10).rounded() / 100); push() }
    @objc func zoomReset() { zoom = 1; push() }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        guard options.screenshot != nil || options.eval != nil else { return }
        DispatchQueue.main.asyncAfter(deadline: .now() + options.delay) { [self] in
            func finish() {
                if let out = options.screenshot {
                    let p = Process()
                    p.executableURL = URL(fileURLWithPath: "/usr/sbin/screencapture")
                    p.arguments = ["-x", "-o", "-l", String(window.windowNumber), out]
                    try? p.run(); p.waitUntilExit()
                    print("screenshot status \(p.terminationStatus) -> \(out)")
                }
                NSApp.terminate(nil)
            }
            if let js = options.eval {
                webView.evaluateJavaScript(js) { result, error in
                    print("eval \(result.map { "\($0)" } ?? error.map { "error: \($0)" } ?? "nil")")
                    finish()
                }
            } else { finish() }
        }
    }

    func installMenu() {
        let main = NSMenu()
        func add(_ title: String, _ items: [NSMenuItem]) {
            let item = NSMenuItem(); main.addItem(item)
            let m = NSMenu(title: title); items.forEach(m.addItem); item.submenu = m
        }
        add("App", [NSMenuItem(title: "Quit", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")])
        add("Edit", [
            NSMenuItem(title: "Copy", action: #selector(NSText.copy(_:)), keyEquivalent: "c"),
            NSMenuItem(title: "Paste", action: #selector(NSText.paste(_:)), keyEquivalent: "v"),
            NSMenuItem(title: "Select All", action: #selector(NSText.selectAll(_:)), keyEquivalent: "a"),
        ])
        let zin = NSMenuItem(title: "Zoom In", action: #selector(zoomIn), keyEquivalent: "=")
        let zout = NSMenuItem(title: "Zoom Out", action: #selector(zoomOut), keyEquivalent: "-")
        let zreset = NSMenuItem(title: "Actual Size", action: #selector(zoomReset), keyEquivalent: "0")
        [zin, zout, zreset].forEach { $0.target = self }
        add("View", [zin, zout, zreset])
        NSApp.mainMenu = main
    }
}

let host = Host(options: parseOptions())
let app = NSApplication.shared
app.setActivationPolicy(.regular)
app.delegate = host
app.run()
