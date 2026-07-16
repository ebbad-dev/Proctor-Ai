import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync } from "node:fs";

const API_BASE = process.env.VITE_API_BASE_URL || process.env.API_BASE_URL || "http://127.0.0.1:5051";
const FRONTEND_URL = process.env.FRONTEND_URL || "http://127.0.0.1:8080/login";
const DEBUG_PORT = Number(process.env.BROWSER_GUARD_DEBUG_PORT || 9222);
const PROFILE = process.env.BROWSER_GUARD_PROFILE || "C:\\tmp\\proctorai_browser_guard_profile";
const VERSION = "1.0.0";
const DEVICE_SECRET =
  process.env.PROCTOR_DEVICE_SECRET ||
  (process.env.AUTH_SECRET
    ? createHash("sha256").update(`${process.env.AUTH_SECRET}:proctor-device-v1`).digest("hex")
    : "");

function deviceHeaders(includeJson = false) {
  return {
    ...(includeJson ? { "Content-Type": "application/json" } : {}),
    "X-Proctor-Device-Secret": DEVICE_SECRET,
  };
}

function browserPath() {
  const candidates = [
    `${process.env.ProgramFiles}\\Google\\Chrome\\Application\\chrome.exe`,
    `${process.env["ProgramFiles(x86)"]}\\Google\\Chrome\\Application\\chrome.exe`,
    `${process.env.LOCALAPPDATA}\\Google\\Chrome\\Application\\chrome.exe`,
    `${process.env.ProgramFiles}\\Microsoft\\Edge\\Application\\msedge.exe`,
    `${process.env["ProgramFiles(x86)"]}\\Microsoft\\Edge\\Application\\msedge.exe`,
  ].filter(Boolean);
  return candidates.find((candidate) => existsSync(candidate));
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

async function ping() {
  await fetch(`${API_BASE}/browser-guard/ping?source=browser_guard_companion&version=${VERSION}`, {
    headers: deviceHeaders(),
  }).catch(() => {});
}

async function postEvent(target, type) {
  const { category, risk } = classifyUrl(target.url || "");
  await fetch(`${API_BASE}/browser-events`, {
    method: "POST",
    headers: deviceHeaders(true),
    body: JSON.stringify({
      type,
      url: target.url || "",
      title: target.title || "",
      category,
      risk,
      source: "browser_guard_companion",
      version: VERSION,
    }),
  }).catch(() => {});
}

async function pollTabs(state) {
  await ping();
  const response = await fetch(`http://127.0.0.1:${DEBUG_PORT}/json`).catch(() => null);
  if (!response?.ok) return;
  const targets = await response.json();
  const pages = targets.filter((target) => target.type === "page" && target.url && !target.url.startsWith("devtools://"));
  const active = pages[0];
  if (!active) return;
  const signature = `${active.id}|${active.url}|${active.title}`;
  if (signature !== state.lastSignature) {
    state.lastSignature = signature;
    await postEvent(active, "tab_activity");
  }
}

function startBrowser() {
  const executable = browserPath();
  if (!executable) {
    throw new Error("Chrome or Edge was not found for Browser Guard companion.");
  }
  mkdirSync(PROFILE, { recursive: true });
  const child = spawn(
    executable,
    [
      `--remote-debugging-port=${DEBUG_PORT}`,
      `--user-data-dir=${PROFILE}`,
      "--no-first-run",
      "--disable-default-apps",
      FRONTEND_URL,
    ],
    { detached: false, stdio: "ignore" },
  );
  child.unref();
}

async function main() {
  if (!DEVICE_SECRET) {
    throw new Error("AUTH_SECRET or PROCTOR_DEVICE_SECRET must be configured before Browser Guard starts.");
  }
  startBrowser();
  const state = { lastSignature: "" };
  setInterval(() => pollTabs(state), 2000);
  setInterval(ping, 15000);
  await ping();
}

main().catch((error) => {
  console.error(`[browser-guard] ${error.message}`);
  process.exit(1);
});
