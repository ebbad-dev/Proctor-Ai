function send(path, payload) {
  chrome.runtime.sendMessage({
    source: "proctorai_content",
    path,
    payload,
  });
}

window.addEventListener("message", (event) => {
  if (event.source !== window || event.origin !== location.origin || !event.data) return;
  if (event.data.type === "PROCTORAI_BROWSER_GUARD_TOKEN") {
    chrome.runtime.sendMessage({
      source: "proctorai_content",
      type: "set_session_token",
      token: event.data.token,
      session_id: event.data.session_id,
    });
  }
  if (event.data.type === "PROCTORAI_BROWSER_GUARD_CLEAR") {
    chrome.runtime.sendMessage({
      source: "proctorai_content",
      type: "clear_session_token",
    });
  }
});

document.addEventListener(
  "visibilitychange",
  () => {
    if (document.hidden) {
      send("/tab-event", {
        type: "visibility_hidden",
        title: document.title,
        url: location.href,
      });
    }
  },
  true,
);

window.addEventListener(
  "blur",
  () => {
    send("/tab-event", {
      type: "window_blur",
      title: document.title,
      url: location.href,
    });
  },
  true,
);

document.addEventListener(
  "keydown",
  (event) => {
    const parts = [];
    if (event.ctrlKey) parts.push("Ctrl");
    if (event.altKey) parts.push("Alt");
    if (event.shiftKey) parts.push("Shift");
    if (event.metaKey) parts.push("Meta");
    parts.push(event.key);
    const combo = parts.join("+");
    if (event.key === "F12" || (event.ctrlKey && event.shiftKey && ["I", "J", "C"].includes(event.key.toUpperCase()))) {
      send("/devtools-event", { combo, url: location.href, title: document.title });
      return;
    }
    if (event.ctrlKey || event.altKey || event.metaKey) {
      send("/keyboard-event", { combo, url: location.href, title: document.title });
    }
  },
  true,
);

document.addEventListener(
  "copy",
  () => send("/clipboard-event", { action: "copy", url: location.href, title: document.title }),
  true,
);

document.addEventListener(
  "paste",
  () => send("/clipboard-event", { action: "paste", url: location.href, title: document.title }),
  true,
);

document.addEventListener(
  "fullscreenchange",
  () => {
    send("/fullscreen-event", {
      state: document.fullscreenElement ? "entered" : "exit",
      url: location.href,
      title: document.title,
    });
  },
  true,
);
