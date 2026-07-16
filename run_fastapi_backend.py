from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
USER_DEPS = ROOT / "python_user_deps"
RUNTIME_DEPS = ROOT / "python_runtime_deps"
if USER_DEPS.exists():
    sys.path.insert(0, str(USER_DEPS))
if RUNTIME_DEPS.exists():
    sys.path.append(str(RUNTIME_DEPS))
sys.path.insert(0, str(ROOT))

import uvicorn


def main() -> None:
    host = os.getenv("API_HOST", "127.0.0.1")
    port = int(os.getenv("API_PORT", "5051"))
    uvicorn.run(
        "infrastructure.api.fastapi_app:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
