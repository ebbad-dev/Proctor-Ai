import { spawn } from "node:child_process";
import { createWriteStream, existsSync, mkdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { homedir } from "node:os";

mkdirSync("logs", { recursive: true });

function loadEnvFile() {
  if (!existsSync(".env")) return;
  for (const rawLine of readFileSync(".env", "utf8").split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#") || !line.includes("=")) continue;
    const [key, ...rest] = line.split("=");
    if (!key || process.env[key]) continue;
    process.env[key] = rest.join("=").trim().replace(/^['"]|['"]$/g, "");
  }
}

loadEnvFile();

const children = [];

function bundledPythonCommand() {
  const bundled = join(
    homedir(),
    ".cache",
    "codex-runtimes",
    "codex-primary-runtime",
    "dependencies",
    "python",
    "python.exe",
  );
  if (existsSync(bundled)) return bundled;
  return "python";
}

function backendPythonCommand() {
  const localVenv = join(process.cwd(), ".venv", "Scripts", "python.exe");
  if (existsSync(localVenv)) return localVenv;
  if (process.env.PYTHON_EXE) return process.env.PYTHON_EXE;
  if (process.env.PYTHON) return process.env.PYTHON;
  return bundledPythonCommand();
}

function proctorPythonCommand() {
  if (process.env.PROCTOR_PYTHON_EXE) return process.env.PROCTOR_PYTHON_EXE;
  return backendPythonCommand();
}

function legacyPythonCommand() {
  const windowsPython = join(
    process.env.LOCALAPPDATA ?? "",
    "Programs",
    "Python",
    "Python313",
    "python.exe",
  );
  if (existsSync(windowsPython)) return windowsPython;
  return "python";
}

function pythonPath(entries = [], includeEnv = true) {
  return [
    process.cwd(),
    ...entries,
    includeEnv ? (process.env.PYTHONPATH ?? "") : "",
  ]
    .filter(Boolean)
    .join(process.platform === "win32" ? ";" : ":");
}

function start(name, command, args, options = {}) {
  const log = createWriteStream(join("logs", `${name}.log`), { flags: "a" });
  log.write(`\n=== ${name} starting ${new Date().toISOString()} ===\n`);
  const child = spawn(command, args, {
    stdio: ["ignore", "pipe", "pipe"],
    shell: process.platform === "win32",
    env: {
      ...process.env,
      PYTHONPATH: pythonPath(
        options.pythonPathEntries ?? [
          join(process.cwd(), "python_runtime_deps"),
          join(process.cwd(), "python_user_deps"),
        ],
        options.includeEnvPythonPath ?? true,
      ),
      ...options.env,
    },
    cwd: options.cwd ?? process.cwd(),
  });
  children.push(child);
  child.stdout?.on("data", (chunk) => {
    process.stdout.write(`[${name}] ${chunk}`);
    log.write(chunk);
  });
  child.stderr?.on("data", (chunk) => {
    process.stderr.write(`[${name}] ${chunk}`);
    log.write(chunk);
  });
  child.on("exit", (code) => {
    log.write(`\n=== ${name} exited ${new Date().toISOString()} code=${code} ===\n`);
    log.end();
    if (code && code !== 0) {
      console.error(`[${name}] exited with code ${code}`);
    }
  });
}

const backendPython = backendPythonCommand();
const proctorPython = proctorPythonCommand();
start("fastapi", backendPython, ["run_fastapi_backend.py"], {
  pythonPathEntries: [
    join(process.cwd(), "python_user_deps"),
    join(process.cwd(), "python_runtime_deps"),
  ],
});
start("proctor", proctorPython, ["run_proctor_engine.py"], {
  pythonPathEntries: [
    join(process.cwd(), "python_user_deps"),
    join(process.cwd(), "python_runtime_deps"),
  ],
  includeEnvPythonPath: false,
});
start("frontend", "npm", ["--prefix", "frontend", "run", "dev"]);
if ((process.env.BROWSER_GUARD_AUTO_START ?? "true").toLowerCase() !== "false") {
  start("browser-guard", "node", ["run_browser_guard.js"]);
}

process.on("SIGINT", () => {
  for (const child of children) child.kill("SIGINT");
  process.exit(0);
});
