from __future__ import annotations

import hashlib
import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


def _load_env_file() -> None:
    env_path = ROOT_DIR / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_env_file()


def _path_env(name: str, default: str) -> str:
    value = os.getenv(name, default)
    path = Path(value)
    if not path.is_absolute():
        path = ROOT_DIR / path
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


REPORTS_DIR = _path_env("REPORTS_DIR", "reports")
SCREENSHOTS_DIR = _path_env("SCREENSHOTS_DIR", "screenshots")
LOGS_DIR = _path_env("LOGS_DIR", "logs")
EXPORTS_DIR = _path_env("EXPORTS_DIR", "exports")
RUNTIME_DIR = _path_env("RUNTIME_DIR", "runtime")
APP_ENV = os.getenv("APP_ENV", "local")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
REQUEST_LOGGING = os.getenv("REQUEST_LOGGING", "true").lower() in {"1", "true", "yes", "on"}

API_HOST = os.getenv("API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("API_PORT", "5051"))
FLASK_HOST = os.getenv("VIDEO_HOST", "127.0.0.1")
FLASK_PORT = int(os.getenv("VIDEO_PORT", "5050"))

WEBCAM_INDEX = int(os.getenv("WEBCAM_INDEX", "0"))
WEBCAM_INDEX_SECONDARY = int(os.getenv("WEBCAM_INDEX_SECONDARY", "-1"))
FRAME_WIDTH = int(os.getenv("FRAME_WIDTH", "640"))
FRAME_HEIGHT = int(os.getenv("FRAME_HEIGHT", "480"))
FRAME_FPS = int(os.getenv("FRAME_FPS", "20"))
WEBCAM_FROZEN_DIFF_THRESHOLD = float(os.getenv("WEBCAM_FROZEN_DIFF_THRESHOLD", "0.05"))
WEBCAM_FROZEN_SECONDS = float(os.getenv("WEBCAM_FROZEN_SECONDS", "8.0"))

AUDIO_SAMPLE_RATE = int(os.getenv("AUDIO_SAMPLE_RATE", "16000"))
AUDIO_CHANNELS = int(os.getenv("AUDIO_CHANNELS", "1"))
AUDIO_CHUNK_SEC = float(os.getenv("AUDIO_CHUNK_SEC", "1.0"))
AUDIO_CHUNK_SIZE = int(os.getenv("AUDIO_CHUNK_SIZE", str(int(AUDIO_SAMPLE_RATE * AUDIO_CHUNK_SEC))))
AUDIO_DEVICE_INDEX_RAW = os.getenv("AUDIO_DEVICE_INDEX", "")
AUDIO_DEVICE_INDEX = int(AUDIO_DEVICE_INDEX_RAW) if AUDIO_DEVICE_INDEX_RAW.strip() else None
AUDIO_RMS_THRESHOLD = float(os.getenv("AUDIO_RMS_THRESHOLD", "0.08"))
AUDIO_COOLDOWN_SEC = float(os.getenv("AUDIO_COOLDOWN_SEC", "20.0"))

PROCTOR_POLL_SEC = float(os.getenv("PROCTOR_POLL_SEC", "0.5"))
PROCTOR_FACE_MISSING_SEC = float(os.getenv("PROCTOR_FACE_MISSING_SEC", "3.0"))
PROCTOR_EVENT_COOLDOWN_SEC = float(os.getenv("PROCTOR_EVENT_COOLDOWN_SEC", "20.0"))
PROCTOR_LOW_LIGHT_THRESHOLD = float(os.getenv("PROCTOR_LOW_LIGHT_THRESHOLD", "45.0"))
PROCTOR_STATUS_FILE = os.getenv(
    "PROCTOR_STATUS_FILE",
    str(Path(RUNTIME_DIR) / "proctor_engine_status.json"),
)
PROCTOR_ACTIVE_FILE = os.getenv(
    "PROCTOR_ACTIVE_FILE",
    str(Path(RUNTIME_DIR) / "active_proctor_session.json"),
)
PHONE_MODEL_PATH = os.getenv("PHONE_MODEL_PATH", str(ROOT_DIR / "models" / "phone_detector.onnx"))
PHONE_MODEL_CLASSES = os.getenv("PHONE_MODEL_CLASSES", str(ROOT_DIR / "models" / "coco.names"))
PHONE_CONFIDENCE_THRESHOLD = float(os.getenv("PHONE_CONFIDENCE_THRESHOLD", "0.35"))

EXAM_DURATION_MIN = int(os.getenv("EXAM_DURATION_MIN", "60"))
DASHBOARD_REFRESH_SEC = int(os.getenv("DASHBOARD_REFRESH_SEC", "2"))

RISK_LOW_MAX = int(os.getenv("RISK_LOW_MAX", "20"))
RISK_MEDIUM_MAX = int(os.getenv("RISK_MEDIUM_MAX", "50"))
STRICTNESS_MODE = os.getenv("STRICTNESS_MODE", "medium").lower()
BROWSER_GUARD_REQUIRED = os.getenv("BROWSER_GUARD_REQUIRED", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}

DB_SERVER = os.getenv("PROCTORAI_DB_SERVER", "localhost")
DB_NAME = os.getenv("PROCTORAI_DB_NAME", "ProctorAI_Lite")
DB_TRUSTED = os.getenv("PROCTORAI_DB_TRUSTED", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
DB_DRIVER = os.getenv("PROCTORAI_DB_DRIVER", "ODBC Driver 17 for SQL Server")
DB_USER = os.getenv("PROCTORAI_DB_USER", "")
DB_PASSWORD = os.getenv("PROCTORAI_DB_PASSWORD", "")
DB_ENCRYPT = os.getenv("PROCTORAI_DB_ENCRYPT", "false").lower() in {
    "1",
    "true",
    "yes",
    "on",
}

AUTH_SECRET = os.getenv("AUTH_SECRET", "")
if APP_ENV.lower() in {"production", "prod"} and len(AUTH_SECRET) < 32:
    raise RuntimeError("AUTH_SECRET must be configured with at least 32 characters in production.")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))
PASSWORD_RESET_EXPIRE_MINUTES = int(os.getenv("PASSWORD_RESET_EXPIRE_MINUTES", "30"))
BROWSER_GUARD_TOKEN_EXPIRE_MINUTES = int(os.getenv("BROWSER_GUARD_TOKEN_EXPIRE_MINUTES", "15"))
MEDIA_TOKEN_EXPIRE_MINUTES = int(os.getenv("MEDIA_TOKEN_EXPIRE_MINUTES", "5"))
PROCTOR_DEVICE_SECRET = os.getenv("PROCTOR_DEVICE_SECRET") or (
    hashlib.sha256(f"{AUTH_SECRET}:proctor-device-v1".encode("utf-8")).hexdigest()
    if AUTH_SECRET
    else ""
)
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://127.0.0.1:8080").rstrip("/")
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://127.0.0.1:8080,http://localhost:8080,http://127.0.0.1:5173,http://localhost:5173",
    ).split(",")
    if origin.strip()
]

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)
SMTP_TLS = os.getenv("SMTP_TLS", "true").lower() in {"1", "true", "yes", "on"}

PROCTORAI_BOOTSTRAP_ADMIN_EMAIL = os.getenv("PROCTORAI_BOOTSTRAP_ADMIN_EMAIL", "")
PROCTORAI_BOOTSTRAP_ADMIN_PASSWORD = os.getenv("PROCTORAI_BOOTSTRAP_ADMIN_PASSWORD", "")

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", f"http://{API_HOST}:{API_PORT}/auth/google/callback")
