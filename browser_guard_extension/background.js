const API_BASE = "http://127.0.0.1:5051";
const VERSION = "1.0.0";
let sessionToken = "";
let sessionId = "";

chrome.storage.session.get(["proctoraiSessionToken", "proctoraiSessionId"], (values) => {
  sessionToken = values.proctoraiSessionToken || "";
  sessionId = values.proctoraiSessionId || "";
  if (sessionToken) heartbeat();
});

async function postJson(path, payload) {
  if (!sessionToken) return;
  const body = JSON.stringify({
    ...payload,
    session_id: sessionId,
    ingest_id: payload.ingest_id || crypto.randomUUID(),
  });
  let lastError;
  for (const delay of [0, 250, 750]) {
    if (delay) await new Promise((resolveDelay) => setTimeout(resolveDelay, delay));
    try {
      const response = await fetch(`${API_BASE}${path}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Proctor-Session-Token": sessionToken,
        },
        body,
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const result = await response.json();
      if (result.persistence && result.persistence !== "persisted") {
        throw new Error("persistence was not confirmed");
      }
      return;
    } catch (error) {
      lastError = error;
    }
  }
  console.warn("ProctorAI Browser Guard request failed after 3 attempts", lastError);
}

function ping() {
  if (!sessionToken) return;
  fetch(`${API_BASE}/browser-guard/ping?source=extension&version=${encodeURIComponent(VERSION)}`, {
    headers: { "X-Proctor-Session-Token": sessionToken },
  })
    .catch((error) => console.warn("ProctorAI Browser Guard ping failed", error));
}

function classifyUrl(url = "") {
  if (!url) return { category: "unknown", risk: "low" };
  if (url.startsWith("chrome://") || url.startsWith("edge://") || url.startsWith("devtools://")) {
    return { category: "browser_internal", risk: "high" };
  }
  if (url.startsWith("http://127.0.0.1") || url.startsWith("http://localhost")) {
    return { category: "proctorai_local", risk: "low" };
  }
  return { category: "external_site", risk: "medium" };
}

function reportTab(tab, type = "tab_activity") {
  if (!tab) return;
  const { category, risk } = classifyUrl(tab.url || "");
  postJson("/browser-events", {
    type,
    url: tab.url || "",
    title: tab.title || "",
    category,
    risk,
    source: "browser_guard_extension",
    version: VERSION,
  });
}

function reportActiveTab(type = "tab_activity") {
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (chrome.runtime.lastError) return;
    reportTab(tabs && tabs[0], type);
  });
}

function heartbeat() {
  ping();
  reportActiveTab("heartbeat");
}

chrome.runtime.onInstalled.addListener(() => {
  chrome.alarms.create("proctorai-heartbeat", { periodInMinutes: 0.25 });
  heartbeat();
});

chrome.runtime.onStartup.addListener(() => {
  chrome.alarms.create("proctorai-heartbeat", { periodInMinutes: 0.25 });
  heartbeat();
});

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "proctorai-heartbeat") heartbeat();
});

chrome.tabs.onActivated.addListener(({ tabId }) => {
  ping();
  chrome.tabs.get(tabId, (tab) => {
    if (chrome.runtime.lastError) return;
    reportTab(tab, "tab_switch");
  });
});

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === "complete" || changeInfo.url || changeInfo.title) {
    ping();
    reportTab(tab, changeInfo.url ? "navigation" : "tab_update");
  }
});

chrome.windows.onFocusChanged.addListener((windowId) => {
  ping();
  if (windowId === chrome.windows.WINDOW_ID_NONE) {
    postJson("/browser-events", {
      type: "window_blur",
      category: "focus_loss",
      risk: "medium",
      source: "browser_guard_extension",
      version: VERSION,
    });
    return;
  }
  reportActiveTab("window_focus");
});

chrome.runtime.onMessage.addListener((message) => {
  if (!message || message.source !== "proctorai_content") return;
  if (message.type === "set_session_token") {
    sessionToken = message.token || "";
    sessionId = message.session_id || "";
    chrome.storage.session.set({
      proctoraiSessionToken: sessionToken,
      proctoraiSessionId: sessionId,
    });
    heartbeat();
    return;
  }
  if (message.type === "clear_session_token") {
    sessionToken = "";
    sessionId = "";
    chrome.storage.session.remove(["proctoraiSessionToken", "proctoraiSessionId"]);
    return;
  }
  ping();
  postJson(message.path || "/browser-events", {
    ...(message.payload || {}),
    source: "browser_guard_extension",
    version: VERSION,
  });
});

heartbeat();
