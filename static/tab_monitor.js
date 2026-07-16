// ============================================================
// ProctorAI — static/tab_monitor.js
// Client-side fallback browser monitoring.
// Injected into Streamlit via components.html
//
// Detects: tab switches, keyboard shortcuts, clipboard access,
// DevTools heuristic, fullscreen exit.
// Sends events to FastAPI on port 5051.
// ============================================================

(function() {
    const API = "http://localhost:5051";

    function post(endpoint, payload) {
        fetch(`${API}${endpoint}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload || {})
        }).catch(() => {});
    }

    // ── Tab Switch Detection ─────────────────────────────────
    document.addEventListener("visibilitychange", function() {
        post("/tab-event", { direction: document.hidden ? "away" : "back" });
    });
    window.addEventListener("blur", function() {
        post("/tab-event", { direction: "away" });
    });
    window.addEventListener("focus", function() {
        post("/tab-event", { direction: "back" });
    });

    // ── Keyboard Shortcut Interception ───────────────────────
    // Block and report common cheat/escape shortcuts
    const BLOCKED_COMBOS = [
        { ctrl: true,  key: "c",      label: "Ctrl+C (Copy)" },
        { ctrl: true,  key: "v",      label: "Ctrl+V (Paste)" },
        { ctrl: true,  key: "x",      label: "Ctrl+X (Cut)" },
        { ctrl: true,  key: "a",      label: "Ctrl+A (Select All)" },
        { ctrl: true,  key: "Tab",    label: "Ctrl+Tab (Switch Tab)" },
        { ctrl: true,  key: "w",      label: "Ctrl+W (Close Tab)" },
        { ctrl: true,  key: "n",      label: "Ctrl+N (New Window)" },
        { ctrl: true,  key: "t",      label: "Ctrl+T (New Tab)" },
        { ctrl: true,  shift: true, key: "I", label: "Ctrl+Shift+I (DevTools)" },
        { ctrl: true,  shift: true, key: "J", label: "Ctrl+Shift+J (Console)" },
        { ctrl: true,  key: "u",      label: "Ctrl+U (View Source)" },
        { key: "F12",                  label: "F12 (DevTools)" },
    ];

    document.addEventListener("keydown", function(e) {
        for (const combo of BLOCKED_COMBOS) {
            const ctrlMatch  = combo.ctrl  ? (e.ctrlKey || e.metaKey) : true;
            const shiftMatch = combo.shift ? e.shiftKey : true;
            const keyMatch   = e.key === combo.key || e.key.toLowerCase() === combo.key.toLowerCase();

            if (ctrlMatch && shiftMatch && keyMatch && (combo.ctrl || combo.key === "F12")) {
                post("/keyboard-event", { combo: combo.label });

                // Also report DevTools-specific combos
                if (combo.label.includes("DevTools") || combo.label.includes("Console") ||
                    combo.label.includes("View Source") || combo.key === "F12") {
                    post("/devtools-event", { combo: combo.label });
                }
                break;
            }
        }
    });

    // ── Clipboard Event Detection ────────────────────────────
    document.addEventListener("copy",  function() { post("/clipboard-event", { action: "copy"  }); });
    document.addEventListener("cut",   function() { post("/clipboard-event", { action: "cut"   }); });
    document.addEventListener("paste", function() { post("/clipboard-event", { action: "paste" }); });

    // ── Fullscreen Exit Detection ────────────────────────────
    document.addEventListener("fullscreenchange", function() {
        if (!document.fullscreenElement) {
            post("/fullscreen-event", { state: "exit" });
        }
    });
    document.addEventListener("webkitfullscreenchange", function() {
        if (!document.webkitFullscreenElement) {
            post("/fullscreen-event", { state: "exit" });
        }
    });

    // ── DevTools Open Heuristic ──────────────────────────────
    // Detects devtools by window size difference (basic heuristic)
    let _devtoolsReported = false;
    const threshold = 160;
    setInterval(() => {
        const widthDiff  = window.outerWidth - window.innerWidth;
        const heightDiff = window.outerHeight - window.innerHeight;
        if (widthDiff > threshold || heightDiff > threshold) {
            if (!_devtoolsReported) {
                post("/devtools-event", { method: "size_heuristic" });
                _devtoolsReported = true;
            }
        } else {
            _devtoolsReported = false;
        }
    }, 3000);

    // ── Right-Click Prevention ───────────────────────────────
    document.addEventListener("contextmenu", function(e) {
        post("/key-event", { combo: "Right-Click (Context Menu)" });
    });

})();
