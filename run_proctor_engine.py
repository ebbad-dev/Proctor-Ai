from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
USER_DEPS = ROOT / "python_user_deps"
RUNTIME_DEPS = ROOT / "python_runtime_deps"
# Prefer the dependency tree built for the configured backend interpreter.
# The runtime tree is only a fallback because it may target a different Python ABI.
if USER_DEPS.exists():
    sys.path.insert(0, str(USER_DEPS))
if RUNTIME_DEPS.exists():
    sys.path.append(str(RUNTIME_DEPS))
sys.path.insert(0, str(ROOT))

try:
    import requests
except Exception:  # pragma: no cover - reported in status if it ever happens
    requests = None

from config.settings import (
    API_HOST,
    API_PORT,
    AUDIO_COOLDOWN_SEC,
    AUDIO_RMS_THRESHOLD,
    PHONE_CONFIDENCE_THRESHOLD,
    PHONE_MODEL_CLASSES,
    PHONE_MODEL_PATH,
    PROCTOR_ACTIVE_FILE,
    PROCTOR_EVENT_COOLDOWN_SEC,
    PROCTOR_FACE_MISSING_SEC,
    PROCTOR_LOW_LIGHT_THRESHOLD,
    PROCTOR_POLL_SEC,
    PROCTOR_STATUS_FILE,
    PROCTOR_DEVICE_SECRET,
    WEBCAM_INDEX_SECONDARY,
)
from core.events.event_types import (
    EVENT_AUDIO_ALERT,
    EVENT_CAMERA_FROZEN,
    EVENT_FACE_MISSING,
    EVENT_LOW_LIGHT,
    EVENT_MULTI_FACE,
    EVENT_PHONE,
)
from core.risk.risk_config import BASE_POINTS
from utils.helpers import get_logger

logger = get_logger("ProctorEngine")
API_BASE = f"http://{API_HOST}:{API_PORT}"


class OptionalPhoneDetector:
    def __init__(self) -> None:
        self.available = False
        self.reason = ""
        self.labels: list[str] = []
        self.net = None
        self._cv2 = None
        self._np = None
        self._load()

    def _load(self) -> None:
        try:
            import cv2
            import numpy as np
        except Exception as exc:
            self.reason = f"opencv/numpy unavailable: {exc}"
            return
        self._cv2 = cv2
        self._np = np
        model_path = Path(PHONE_MODEL_PATH)
        if not model_path.exists():
            self.reason = f"model not found: {model_path}"
            return
        classes_path = Path(PHONE_MODEL_CLASSES)
        if classes_path.exists():
            self.labels = [
                line.strip().lower()
                for line in classes_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        else:
            self.labels = ["cell phone", "mobile phone", "phone"]
        try:
            self.net = cv2.dnn.readNetFromONNX(str(model_path))
            self.available = True
            self.reason = "loaded"
        except Exception as exc:
            self.reason = f"model load failed: {exc}"

    def detect_phone(self, frame: Any) -> bool:
        if not self.available or self.net is None or frame is None:
            return False
        cv2 = self._cv2
        np = self._np
        try:
            blob = cv2.dnn.blobFromImage(frame, 1 / 255.0, (640, 640), swapRB=True, crop=False)
            self.net.setInput(blob)
            output = self.net.forward()
            rows = output[0].T if output.ndim == 3 and output.shape[1] < output.shape[2] else output[0]
            for row in rows:
                values = np.asarray(row).reshape(-1)
                if values.size < 6:
                    continue
                if len(self.labels) and values.size >= len(self.labels) + 5:
                    objectness = float(values[4])
                    class_scores = values[5:5 + len(self.labels)]
                    class_id = int(np.argmax(class_scores))
                    confidence = objectness * float(class_scores[class_id])
                elif len(self.labels) and values.size >= len(self.labels) + 4:
                    class_scores = values[4:4 + len(self.labels)]
                    class_id = int(np.argmax(class_scores))
                    confidence = float(class_scores[class_id])
                else:
                    scores = values[4:]
                    class_id = int(np.argmax(scores))
                    confidence = float(scores[class_id])
                label = self.labels[class_id] if class_id < len(self.labels) else ""
                if confidence >= PHONE_CONFIDENCE_THRESHOLD and "phone" in label:
                    return True
        except Exception as exc:
            self.available = False
            self.reason = f"inference failed: {exc}"
        return False


class ProctorEngine:
    def __init__(self) -> None:
        self.session: dict[str, str] = {}
        self.webcam = None
        self.webcam2 = None
        self.mic = None
        self.detector = None
        self.screenshots = None
        self.phone_detector = OptionalPhoneDetector()
        self.last_events: dict[str, float] = {}
        self.face_missing_since: float | None = None
        self.last_detection_at = ""
        self.last_error = ""
        self.startup_errors: list[str] = []

    def start(self) -> None:
        self._start_camera()
        self._start_microphone()
        self._start_video_sidecar()
        while True:
            try:
                self._sync_session()
                self._detect_once()
                self._write_status()
            except Exception as exc:
                self.last_error = str(exc)
                logger.warning("Detection loop error: %s", exc)
                self._write_status()
            time.sleep(PROCTOR_POLL_SEC)

    def _start_camera(self) -> None:
        try:
            from input.webcam_capture import WebcamCapture

            self.webcam = WebcamCapture(label="primary")
            self.webcam.start_camera()
            if WEBCAM_INDEX_SECONDARY >= 0:
                self.webcam2 = WebcamCapture(camera_index=WEBCAM_INDEX_SECONDARY, label="secondary")
                self.webcam2.start_camera()
        except Exception as exc:
            self.last_error = f"camera startup failed: {exc}"
            self.startup_errors.append(self.last_error)
            logger.warning(self.last_error)

    def _start_microphone(self) -> None:
        try:
            from input.audio_capture import AudioCapture

            self.mic = AudioCapture()
            self.mic.start_microphone()
        except Exception as exc:
            self.last_error = f"microphone startup failed: {exc}"
            self.startup_errors.append(self.last_error)
            logger.warning(self.last_error)

    def _start_video_sidecar(self) -> None:
        try:
            from monitoring.tab_switch_detector import get_or_create_detector

            self.detector = get_or_create_detector()
            self.detector.set_providers(self.webcam, None)
            if self.webcam2:
                self.detector.set_secondary_webcam(self.webcam2)
        except Exception as exc:
            self.last_error = f"video sidecar startup failed: {exc}"
            self.startup_errors.append(self.last_error)
            logger.warning(self.last_error)

    def _sync_session(self) -> None:
        next_session: dict[str, str] = {}
        status_path = Path(PROCTOR_ACTIVE_FILE)
        if status_path.exists():
            try:
                data = json.loads(status_path.read_text(encoding="utf-8"))
                if data.get("running") and data.get("session_id"):
                    next_session = {
                        "session_id": str(data.get("session_id", "")),
                        "student_id": str(data.get("student_id", "")),
                        "exam_code": str(data.get("exam_code", "")),
                    }
            except Exception:
                next_session = {}
        if next_session.get("session_id") != self.session.get("session_id"):
            self.session = next_session
            if self.session:
                from input.screenshot_capture import ScreenshotCapture

                self.screenshots = ScreenshotCapture(
                    self.session["session_id"],
                    student_id=self.session.get("student_id", ""),
                )
                logger.info("Active proctor session: %s", self.session["session_id"])
            else:
                self.screenshots = None

    def _detect_once(self) -> None:
        if not self.session:
            return
        frame = None
        if self.webcam and self.webcam.is_running:
            frame = self.webcam.get_frame()
        if frame is not None:
            self._detect_frame(frame)
        if self.mic and getattr(self.mic, "is_available", False):
            level = float(getattr(self.mic, "audio_level", 0.0) or 0.0)
            if level >= AUDIO_RMS_THRESHOLD:
                self._emit(EVENT_AUDIO_ALERT, f"Microphone RMS level {level:.3f}", cooldown=AUDIO_COOLDOWN_SEC)
        self.last_detection_at = datetime.now().isoformat()

    def _detect_frame(self, frame: Any) -> None:
        try:
            import cv2
            import numpy as np
        except Exception:
            return
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        brightness = float(np.mean(gray))
        if brightness < PROCTOR_LOW_LIGHT_THRESHOLD:
            self._emit(EVENT_LOW_LIGHT, f"Low light detected, brightness {brightness:.1f}", frame=frame)
        if self.webcam and self.webcam.is_frozen:
            self._emit(EVENT_CAMERA_FROZEN, "Camera frame appears frozen", frame=frame)

        faces = self._detect_faces(gray)
        now = time.monotonic()
        if not faces:
            if self.face_missing_since is None:
                self.face_missing_since = now
            elif now - self.face_missing_since >= PROCTOR_FACE_MISSING_SEC:
                self._emit(EVENT_FACE_MISSING, "No face visible in primary camera", frame=frame)
        else:
            self.face_missing_since = None
            if len(faces) > 1:
                self._emit(EVENT_MULTI_FACE, f"{len(faces)} faces visible", frame=frame)

        if self.phone_detector.detect_phone(frame):
            self._emit(EVENT_PHONE, "Phone-like object detected in frame", frame=frame)

    def _detect_faces(self, gray: Any) -> list[Any]:
        try:
            import cv2

            cascade_path = str(Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml")
            cascade = cv2.CascadeClassifier(cascade_path)
            faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
            return list(faces)
        except Exception:
            return []

    def _emit(self, event_type: str, notes: str, *, frame: Any = None, cooldown: float | None = None) -> None:
        cooldown = PROCTOR_EVENT_COOLDOWN_SEC if cooldown is None else cooldown
        now = time.monotonic()
        if now - self.last_events.get(event_type, 0.0) < cooldown:
            return
        self.last_events[event_type] = now
        if frame is not None and self.screenshots:
            self.screenshots.capture_on_events(
                frame,
                [event_type],
                risk_score=BASE_POINTS.get(event_type, 0),
                confidence=1.0,
                camera="primary",
            )
            self.screenshots.export_index()
        self._post_event(event_type, notes)

    def _post_event(self, event_type: str, notes: str) -> None:
        if not requests:
            return
        payload = {
            "session_id": self.session.get("session_id", ""),
            "student_id": self.session.get("student_id", ""),
            "event_type": event_type,
            "risk_points": BASE_POINTS.get(event_type, 0),
            "notes": notes,
        }
        try:
            response = requests.post(
                f"{API_BASE}/events",
                json=payload,
                headers={"X-Proctor-Device-Secret": PROCTOR_DEVICE_SECRET},
                timeout=2,
            )
            response.raise_for_status()
            if self.last_error.startswith("event post failed:"):
                self.last_error = ""
        except Exception as exc:
            self.last_error = f"event post failed: {exc}"

    def _write_status(self) -> None:
        status = self.status()
        path = Path(PROCTOR_STATUS_FILE)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(status, indent=2), encoding="utf-8")

    def status(self) -> dict[str, Any]:
        primary_active = bool(self.webcam and self.webcam.is_running)
        secondary_active = bool(self.webcam2 and self.webcam2.is_running)
        microphone_active = bool(self.mic and getattr(self.mic, "is_available", False))
        engine_ready = primary_active and microphone_active
        width, height = self.webcam.resolution if primary_active else (0, 0)
        width2, height2 = self.webcam2.resolution if secondary_active else (0, 0)
        return {
            "engine_running": True,
            "ready": engine_ready,
            "status": "ready" if engine_ready else "degraded",
            "updated_at": datetime.now().astimezone().isoformat(),
            "active_session_id": self.session.get("session_id") or None,
            "student_id": self.session.get("student_id") or "",
            "last_detection_at": self.last_detection_at,
            "last_error": self.last_error,
            "startup_errors": self.startup_errors,
            "primary_camera": {
                "active": primary_active,
                "resolution": f"{width}x{height}" if primary_active else "",
                "fps": self.webcam.fps if primary_active else 0,
                "frozen": bool(self.webcam and self.webcam.is_frozen),
            },
            "secondary_camera": {
                "active": secondary_active,
                "resolution": f"{width2}x{height2}" if secondary_active else "",
                "fps": self.webcam2.fps if secondary_active else 0,
            },
            "microphone": {
                "active": microphone_active,
                "level": float(getattr(self.mic, "audio_level", 0.0) or 0.0) if self.mic else 0.0,
            },
            "video_stream": {
                "active": bool(self.detector and primary_active),
                "url": "http://127.0.0.1:5050/video_feed",
            },
            "phone_detection": {
                "available": self.phone_detector.available,
                "status": "ready" if self.phone_detector.available else "unavailable",
                "reason": self.phone_detector.reason,
            },
        }


def main() -> None:
    ProctorEngine().start()


if __name__ == "__main__":
    main()
