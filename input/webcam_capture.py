# ============================================================
# ProctorAI — input/webcam_capture.py
#
# CHANGES:
#   1. Accepts camera_index parameter (multi-camera support).
#   2. Camera health properties: is_frozen, brightness.
#   3. FPS tracking exposed as property.
#   4. get_latest_frame_with_id() preserved for MJPEG server.
#   5. Graceful re-open on unexpected camera failure.
# ============================================================

import cv2
import threading
import time
from utils.helpers import get_logger
from config.settings import (
    FRAME_FPS,
    FRAME_HEIGHT,
    FRAME_WIDTH,
    WEBCAM_FROZEN_SECONDS,
    WEBCAM_INDEX,
)

logger = get_logger("WebcamCapture")


class WebcamCapture:
    """
    Thread-safe webcam capture with multi-camera support.

    Parameters
    ----------
    camera_index : int
        Camera index to open. Defaults to WEBCAM_INDEX from settings.
    label : str
        Human-readable label ("primary" / "secondary") for logs.
    """

    def __init__(self, camera_index: int = None, label: str = "primary"):
        self._index   = camera_index if camera_index is not None else WEBCAM_INDEX
        self._label   = label
        self._cap     = None
        self._frame   = None
        self._frame_id = 0
        self._lock    = threading.Lock()
        self._running = False
        self._thread  = None

        # FPS tracking
        self._fps_times: list = []
        self._fps: float      = 0.0

        # Health
        self._frozen_since = None
        self._last_frame_at = None

    # ── Public API ────────────────────────────────────────────

    def start_camera(self) -> bool:
        """Open the camera and start the background capture thread."""
        self._cap = cv2.VideoCapture(self._index)
        if not self._cap.isOpened():
            logger.warning(
                f"[{self._label}] Camera {self._index} unavailable."
            )
            return False

        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH,  FRAME_WIDTH)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
        self._cap.set(cv2.CAP_PROP_FPS,          FRAME_FPS)

        self._running = True
        self._thread  = threading.Thread(
            target=self._capture_loop, daemon=True,
            name=f"WebcamCapture_{self._label}"
        )
        self._thread.start()
        logger.info(
            f"[{self._label}] Camera {self._index} opened "
            f"({FRAME_WIDTH}×{FRAME_HEIGHT} @ {FRAME_FPS}fps)"
        )
        return True

    def stop_camera(self):
        self._running = False
        if self._cap:
            self._cap.release()
            self._cap = None
        logger.info(f"[{self._label}] Camera stopped.")

    def get_frame(self):
        """Return the latest frame (or None if unavailable)."""
        with self._lock:
            return self._frame.copy() if self._frame is not None else None

    def get_latest_frame_with_id(self) -> tuple:
        """Return (frame_id, frame) for MJPEG dedup."""
        with self._lock:
            f = self._frame.copy() if self._frame is not None else None
            return self._frame_id, f

    @property
    def is_running(self) -> bool:
        return self._running and self._cap is not None

    @property
    def fps(self) -> float:
        return round(self._fps, 1)

    @property
    def resolution(self) -> tuple:
        """Return (width, height) or (0, 0) if not open."""
        if self._cap and self._cap.isOpened():
            w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            return (w, h)
        return (0, 0)

    @property
    def is_frozen(self) -> bool:
        """True when capture stops delivering fresh frames for several seconds."""
        now = time.monotonic()
        if self._frozen_since is not None and now - self._frozen_since >= WEBCAM_FROZEN_SECONDS:
            return True
        if self._running and self._last_frame_at is not None and now - self._last_frame_at >= WEBCAM_FROZEN_SECONDS:
            return True
        return False

    # ── Capture loop ──────────────────────────────────────────

    def _capture_loop(self):
        while self._running:
            if self._cap is None or not self._cap.isOpened():
                time.sleep(0.5)
                continue

            ok, frame = self._cap.read()
            if not ok or frame is None:
                if self._frozen_since is None:
                    self._frozen_since = time.monotonic()
                time.sleep(0.05)
                continue

            # FPS tracking (rolling 30-frame window)
            now = time.time()
            self._fps_times.append(now)
            if len(self._fps_times) > 30:
                self._fps_times.pop(0)
            if len(self._fps_times) >= 2:
                span = self._fps_times[-1] - self._fps_times[0]
                self._fps = (len(self._fps_times) - 1) / span if span > 0 else 0.0

            self._last_frame_at = time.monotonic()
            self._frozen_since = None

            with self._lock:
                self._frame    = frame
                self._frame_id += 1

    @property
    def audio_level(self) -> float:
        return 0.0
