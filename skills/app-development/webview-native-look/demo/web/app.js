// app.js — host contract on the web side. Everything here is portable: copy `host` and
// `chooseGlass` into any app, keep the rest as demo UI.
(function () {
  var root = document.documentElement;
  var hasHost = !!(window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.ipcRequest);

  // ---- IPC: a request/response RPC over the WKWebView message handler -------------------
  // The native side replies by calling window.__nativeHost.resolve(id, result|null, error|null).
  var pending = new Map(), nextId = 1;
  function request(method, data, timeoutMs) {
    if (!hasHost) return Promise.reject(new Error("no native host"));
    return new Promise(function (resolve, reject) {
      var id = nextId++;
      var timer = setTimeout(function () { pending.delete(id); reject(new Error(method + " timed out")); }, timeoutMs || 5000);
      pending.set(id, { resolve: resolve, reject: reject, timer: timer });
      window.webkit.messageHandlers.ipcRequest.postMessage({ id: id, method: method, data: data == null ? null : data });
    });
  }
  window.__nativeHost = window.__nativeHost || {};
  window.__nativeHost.resolve = function (id, result, error) {
    var p = pending.get(id); if (!p) return;
    pending.delete(id); clearTimeout(p.timer);
    error ? p.reject(new Error(error)) : p.resolve(result);
  };

  // ---- Material strategy -----------------------------------------------------------------
  // `native` when the host put a real material behind the page; `system` only if the private
  // property exists (it does not in third-party WKWebViews we tested); `blur` when
  // backdrop-filter exists; `solid` otherwise. A query string can
  // force one (?glass=solid) so the same page can be compared side by side.
  function chooseGlass() {
    var forced = new URLSearchParams(location.search).get("glass");
    if (forced) return forced;
    var backdrop = root.getAttribute("backdrop");
    if (hasHost && backdrop && backdrop !== "none") return "native";
    if (hasHost && window.CSS && CSS.supports("-apple-visual-effect", "-apple-system-glass-material")) return "system";
    if (window.CSS && (CSS.supports("backdrop-filter", "blur(1px)") || CSS.supports("-webkit-backdrop-filter", "blur(1px)"))) return "blur";
    return "solid";
  }

  // ---- Browser fallback for the attributes the host would normally set -------------------
  if (!hasHost) {
    var mq = matchMedia("(prefers-color-scheme: dark)");
    var setDark = function () { mq.matches ? root.setAttribute("dark", "") : root.removeAttribute("dark"); };
    setDark(); mq.addEventListener("change", setDark);
  }
  root.setAttribute("glass", chooseGlass());

  // Allow transitions only after the first two frames.
  requestAnimationFrame(function () { requestAnimationFrame(function () { root.classList.add("transitions-ready"); }); });

  // ---- Demo UI ----------------------------------------------------------------------------
  function show(view) {
    document.querySelectorAll("[data-panel]").forEach(function (p) { p.hidden = p.dataset.panel !== view; });
    document.querySelectorAll(".nav").forEach(function (n) { n.toggleAttribute("aria-current", n.dataset.view === view); if (n.dataset.view === view) n.setAttribute("aria-current", "page"); else n.removeAttribute("aria-current"); });
    if (view === "lab") report();
  }
  document.querySelectorAll(".nav").forEach(function (n) { n.addEventListener("click", function () { show(n.dataset.view); }); });
  show(new URLSearchParams(location.search).get("view") || "launcher");

  document.querySelectorAll(".switch").forEach(function (s) {
    s.addEventListener("click", function () { s.setAttribute("aria-checked", String(s.getAttribute("aria-checked") !== "true")); });
  });

  var apply = {
    dark: function (v) { v === "dark" ? root.setAttribute("dark", "") : root.removeAttribute("dark"); },
    macos: function (v) { v ? root.setAttribute("macos", v) : root.removeAttribute("macos"); },
    glass: function (v) { root.setAttribute("glass", v); },
    zoom: function (v) { root.style.setProperty("--zoom", v); }
  };
  document.querySelectorAll("[data-lab]").forEach(function (group) {
    group.addEventListener("click", function (e) {
      var b = e.target.closest("button"); if (!b) return;
      apply[group.dataset.lab](b.dataset.v); mark(); report();
    });
  });
  function current(key) {
    if (key === "dark") return root.hasAttribute("dark") ? "dark" : "light";
    if (key === "macos") return root.getAttribute("macos") || "";
    if (key === "glass") return root.getAttribute("glass");
    return String(parseFloat(getComputedStyle(root).getPropertyValue("--zoom")) || 1);
  }
  function mark() {
    document.querySelectorAll("[data-lab]").forEach(function (g) {
      var cur = current(g.dataset.lab);
      g.querySelectorAll("button").forEach(function (b) { b.setAttribute("aria-pressed", String(b.dataset.v === cur)); });
    });
  }
  function report() {
    var lines = [
      "host bridge      " + (hasHost ? "yes (ipcRequest)" : "no (plain browser)"),
      "macos attribute  " + (root.getAttribute("macos") || "—"),
      "appearance       " + current("dark"),
      "backdrop         " + (root.getAttribute("backdrop") || "—"),
      "glass strategy   " + root.getAttribute("glass"),
      "-apple-visual-effect supported  " + (window.CSS && CSS.supports("-apple-visual-effect", "-apple-system-glass-material")),
      "backdrop-filter supported       " + (window.CSS && (CSS.supports("backdrop-filter", "blur(1px)") || CSS.supports("-webkit-backdrop-filter", "blur(1px)"))),
      "relative colour supported       " + (window.CSS && CSS.supports("color", "rgb(from red r g b / 50%)")),
      "accent           " + (getComputedStyle(root).getPropertyValue("--color-system-accent").trim() || "(default)"),
      "zoom             " + current("zoom"),
      "devicePixelRatio " + devicePixelRatio
    ];
    document.getElementById("report").textContent = lines.join("\n");
    mark();
  }
  window.addEventListener("nativehost", report);
  report();

  if (hasHost) request("host.info").then(function (info) {
    window.__hostInfo = info;   // also lets verify.sh assert a full request/response round trip
    document.getElementById("report").textContent += "\nhost.info → " + JSON.stringify(info);
  }).catch(function (e) { document.getElementById("report").textContent += "\nhost.info failed: " + e.message; });
})();
