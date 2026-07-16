import { spawn } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { basename, dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const ARTIFACTS = resolve(ROOT, "e2e_artifacts");
const SHOTS = resolve(ARTIFACTS, "screenshots");
const SEED = JSON.parse(readFileSync(resolve(ARTIFACTS, "seed.json"), "utf8"));
const API = "http://127.0.0.1:5051";
const APP = "http://127.0.0.1:8080";
const DEBUG_PORT = 9333;
const PROFILE = "C:\\tmp\\proctorai_e2e_capture_profile";

mkdirSync(SHOTS, { recursive: true });

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

function sleep(ms) {
  return new Promise((resolveSleep) => setTimeout(resolveSleep, ms));
}

async function api(path, options = {}, token = "") {
  const response = await fetch(`${API}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
  });
  const text = await response.text();
  const body = text ? JSON.parse(text) : {};
  if (!response.ok) {
    throw new Error(`${path} failed: ${response.status} ${text}`);
  }
  return body;
}

async function waitForDebug() {
  for (let i = 0; i < 40; i++) {
    try {
      const response = await fetch(`http://127.0.0.1:${DEBUG_PORT}/json/version`);
      if (response.ok) return;
    } catch {}
    await sleep(250);
  }
  throw new Error("Timed out waiting for Chrome DevTools protocol.");
}

async function createTarget(url) {
  const response = await fetch(`http://127.0.0.1:${DEBUG_PORT}/json/new?${encodeURIComponent(url)}`, {
    method: "PUT",
  });
  if (!response.ok) throw new Error(`Could not create browser tab: ${response.status}`);
  return response.json();
}

class CDP {
  constructor(wsUrl) {
    this.ws = new WebSocket(wsUrl);
    this.nextId = 1;
    this.pending = new Map();
    this.opened = new Promise((resolveOpen, rejectOpen) => {
      this.ws.addEventListener("open", resolveOpen, { once: true });
      this.ws.addEventListener("error", rejectOpen, { once: true });
    });
    this.ws.addEventListener("message", (event) => {
      const msg = JSON.parse(event.data);
      if (msg.id && this.pending.has(msg.id)) {
        const { resolveSend, rejectSend } = this.pending.get(msg.id);
        this.pending.delete(msg.id);
        if (msg.error) rejectSend(new Error(JSON.stringify(msg.error)));
        else resolveSend(msg.result || {});
      }
    });
  }

  async send(method, params = {}) {
    await this.opened;
    const id = this.nextId++;
    this.ws.send(JSON.stringify({ id, method, params }));
    return new Promise((resolveSend, rejectSend) => {
      this.pending.set(id, { resolveSend, rejectSend });
    });
  }

  close() {
    this.ws.close();
  }
}

async function evaluate(cdp, expression) {
  const result = await cdp.send("Runtime.evaluate", {
    expression,
    awaitPromise: true,
    returnByValue: true,
  });
  return result.result?.value;
}

async function navigate(cdp, url, waitMs = 1600) {
  await cdp.send("Page.navigate", { url });
  await sleep(waitMs);
  await evaluate(cdp, "document.readyState");
  await sleep(500);
}

async function screenshot(cdp, name, title, notes, shots) {
  await sleep(500);
  const data = await cdp.send("Page.captureScreenshot", {
    format: "png",
    fromSurface: true,
    captureBeyondViewport: false,
  });
  const file = resolve(SHOTS, `${String(shots.length + 1).padStart(2, "0")}_${name}.png`);
  writeFileSync(file, Buffer.from(data.data, "base64"));
  shots.push({ file, title, notes });
  console.log(`Captured ${basename(file)}`);
}

function reportHtml(shots, sessionId) {
  const items = shots
    .map((shot, index) => {
      const b64 = readFileSync(shot.file).toString("base64");
      return `<section>
        <h2>${index + 1}. ${escapeHtml(shot.title)}</h2>
        <p>${escapeHtml(shot.notes)}</p>
        <img src="data:image/png;base64,${b64}" alt="${escapeHtml(shot.title)}" />
      </section>`;
    })
    .join("\n");
  return `<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>ProctorAI E2E Screenshots</title>
  <style>
    body { margin: 0; font-family: Arial, sans-serif; color: #111827; background: #f8fafc; }
    header { padding: 28px 34px; background: #07111f; color: white; }
    h1 { margin: 0 0 8px; font-size: 28px; }
    header p { margin: 4px 0; color: #b6c6dc; }
    section { page-break-inside: avoid; margin: 24px auto; width: 92%; padding: 20px; background: white; border: 1px solid #dbe4ef; border-radius: 10px; }
    h2 { margin: 0 0 8px; font-size: 18px; color: #0f172a; }
    section p { margin: 0 0 14px; color: #475569; }
    img { width: 100%; border: 1px solid #cbd5e1; border-radius: 8px; display: block; }
  </style>
</head>
<body>
  <header>
    <h1>ProctorAI End-to-End Run Screenshots</h1>
    <p>Generated: ${new Date().toLocaleString()}</p>
    <p>Session: ${escapeHtml(sessionId)}</p>
    <p>Student: ${escapeHtml(SEED.student.email)} | Exam: ${escapeHtml(SEED.exam.title)}</p>
  </header>
  ${items}
</body>
</html>`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

async function printPdf(reportPath, pdfPath) {
  const target = await createTarget(`file:///${reportPath.replaceAll("\\", "/")}`);
  const cdp = new CDP(target.webSocketDebuggerUrl);
  await cdp.send("Page.enable");
  await navigate(cdp, `file:///${reportPath.replaceAll("\\", "/")}`, 1000);
  const pdf = await cdp.send("Page.printToPDF", {
    printBackground: true,
    landscape: true,
    paperWidth: 13.333,
    paperHeight: 7.5,
    marginTop: 0.25,
    marginBottom: 0.25,
    marginLeft: 0.25,
    marginRight: 0.25,
  });
  writeFileSync(pdfPath, Buffer.from(pdf.data, "base64"));
  cdp.close();
}

async function main() {
  const executable = browserPath();
  if (!executable) throw new Error("Chrome or Edge was not found.");
  mkdirSync(PROFILE, { recursive: true });
  const browser = spawn(executable, [
    "--headless=new",
    `--remote-debugging-port=${DEBUG_PORT}`,
    `--user-data-dir=${PROFILE}`,
    "--no-first-run",
    "--disable-gpu",
    "--window-size=1440,1000",
    `${APP}/login`,
  ], { stdio: "ignore" });

  try {
    await waitForDebug();
    const target = await createTarget(`${APP}/login`);
    const cdp = new CDP(target.webSocketDebuggerUrl);
    await cdp.send("Page.enable");
    await cdp.send("Runtime.enable");
    await cdp.send("Emulation.setDeviceMetricsOverride", {
      width: 1440,
      height: 1000,
      deviceScaleFactor: 1,
      mobile: false,
    });

    const shots = [];
    await navigate(cdp, `${APP}/login`);
    await screenshot(cdp, "login", "Login", "Premium ProctorAI authentication page.", shots);

    const studentLogin = await api("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email: SEED.student.email, password: SEED.student.password }),
    });
    await evaluate(cdp, `localStorage.setItem("proctorai_auth", ${JSON.stringify(JSON.stringify({ ...studentLogin, logged_in_at: new Date().toISOString() }))})`);

    await navigate(cdp, `${APP}/setup`);
    await screenshot(cdp, "setup", "Student Setup", "Authenticated student setup wizard with backend, camera stream, and Browser Guard status.", shots);

    await navigate(cdp, `${APP}/browser-guard`);
    await screenshot(cdp, "browser_guard", "Browser Guard", "Exact URL tracking status and installation/connection screen.", shots);

    await navigate(cdp, `${APP}/checklist`);
    await screenshot(cdp, "checklist", "Pre-Exam Checklist", "Live readiness checks for camera, microphone, database, Browser Guard, and evidence tasks.", shots);

    await navigate(cdp, `${APP}/id-verification`);
    await screenshot(cdp, "id_verification", "ID Verification", "Camera-based identity evidence capture flow.", shots);

    await navigate(cdp, `${APP}/room-scan`);
    await screenshot(cdp, "room_scan", "Room Scan", "Room/environment scan workflow before exam start.", shots);

    const session = await api("/sessions/start", {
      method: "POST",
      body: JSON.stringify({
        student_id: SEED.student.user_id,
        student_name: SEED.student.full_name,
        exam_id: SEED.exam.exam_id,
        exam_code: SEED.exam.title,
      }),
    }, studentLogin.access_token);
    const sessionId = session.session_id;

    await api("/tab-event", { method: "POST", body: JSON.stringify({ direction: "away", session_id: sessionId }) });
    await api("/keyboard-event", { method: "POST", body: JSON.stringify({ combo: "Ctrl+Shift+I", session_id: sessionId }) });
    await api("/fullscreen-event", { method: "POST", body: JSON.stringify({ state: "exit", session_id: sessionId }) });
    await api("/events", {
      method: "POST",
      body: JSON.stringify({
        session_id: sessionId,
        student_id: SEED.student.user_id,
        event_type: "Audio Alert",
        risk_points: 8,
        notes: "E2E verification audio alert event.",
      }),
    });

    await navigate(cdp, `${APP}/monitor?session_id=${encodeURIComponent(sessionId)}`, 2200);
    await screenshot(cdp, "monitor", "Live Monitor", "Live exam monitor with camera, health strip, event timeline, Browser Guard, and nonzero risk.", shots);

    await api(`/sessions/${sessionId}/end`, {
      method: "POST",
      body: JSON.stringify({ generate_report: true }),
    }, studentLogin.access_token);

    await navigate(cdp, `${APP}/sessions/${encodeURIComponent(sessionId)}`, 2200);
    await screenshot(cdp, "session_review", "Session Review", "Ended session with risk contributors, events, browser activity, and instructor review tools.", shots);

    await navigate(cdp, `${APP}/reports?session_id=${encodeURIComponent(sessionId)}`, 1800);
    await screenshot(cdp, "reports", "Reports", "Report page for the completed monitored session.", shots);

    const adminLogin = await api("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email: SEED.admin.email, password: SEED.admin.password }),
    });
    await evaluate(cdp, `localStorage.setItem("proctorai_auth", ${JSON.stringify(JSON.stringify({ ...adminLogin, logged_in_at: new Date().toISOString() }))})`);
    await navigate(cdp, `${APP}/instructor`, 2000);
    await screenshot(cdp, "instructor_dashboard", "Instructor Dashboard", "Instructor/admin dashboard backed by live database metrics.", shots);

    const reportPath = resolve(ARTIFACTS, "ProctorAI_E2E_Screenshots.html");
    const pdfPath = resolve(ARTIFACTS, "ProctorAI_E2E_Screenshots.pdf");
    writeFileSync(reportPath, reportHtml(shots, sessionId), "utf8");
    await printPdf(reportPath, pdfPath);
    cdp.close();
    console.log(JSON.stringify({ sessionId, reportPath, pdfPath, screenshots: shots.map((s) => s.file) }, null, 2));
  } finally {
    browser.kill();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
