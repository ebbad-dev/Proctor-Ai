# ============================================================
# ProctorAI — input/screenshot_capture.py
#
# CHANGES:
#   1. Each screenshot now stored with full evidence metadata:
#      session_id, student_id, event_type, timestamp, risk_score,
#      confidence, camera source, description.
#   2. get_recent_screenshots(n) returns metadata + path list.
#   3. get_evidence_for_report() returns structured data for PDF.
#   4. Evidence index saved as JSON alongside screenshots.
# ============================================================

import os
import json
import cv2
from datetime import datetime
from utils.helpers import get_logger, ensure_dir
from config.settings import SCREENSHOTS_DIR

logger = get_logger("ScreenshotCapture")

# Only capture screenshots for these high-value events
_CAPTURE_EVENTS = {
    "Phone Detected", "Multiple Faces", "Face Missing",
    "DevTools Opened", "Clipboard Access", "Keyboard Shortcut",
    "Tab Switch", "Fullscreen Exit", "Camera Covered",
}


class ScreenshotCapture:
    """
    Captures and stores timestamped evidence screenshots linked
    to suspicious events.

    Each screenshot is saved with a metadata sidecar stored in
    an in-memory index (and optionally as JSON).
    """

    def __init__(self, session_id: str, student_id: str = "",
                 student_name: str = ""):
        self._session_id   = session_id
        self._student_id   = student_id
        self._student_name = student_name
        self._dir          = os.path.join(SCREENSHOTS_DIR, session_id)
        ensure_dir(self._dir)
        self._evidence: list[dict] = []
        self._total_saved = 0
        logger.info(f"ScreenshotCapture ready → {self._dir}")

    # ── Capture ───────────────────────────────────────────────

    def capture_on_events(self, frame, event_types: list,
                          risk_score: int = 0,
                          confidence: float = 0.0,
                          camera: str = "primary"):
        """
        Save a screenshot for each qualifying event in event_types.
        Only events in _CAPTURE_EVENTS trigger a capture.
        """
        if frame is None:
            return
        for event_type in event_types:
            if event_type in _CAPTURE_EVENTS:
                self._save(frame, event_type, risk_score, confidence, camera)

    def capture_manual(self, frame, event_type: str,
                       risk_score: int = 0,
                       confidence: float = 0.0,
                       camera: str = "primary") -> str | None:
        """Force-capture a screenshot regardless of event type."""
        return self._save(frame, event_type, risk_score, confidence, camera)

    # ── Query ─────────────────────────────────────────────────

    def get_recent_screenshots(self, n: int = 6) -> list[dict]:
        """
        Return the last n evidence items (newest first).
        Each item: {path, event_type, time, risk_score, camera, description}
        """
        return list(reversed(self._evidence))[:n]

    def get_all_evidence(self) -> list[dict]:
        return list(self._evidence)

    def get_evidence_for_report(self, max_items: int = 8) -> list[dict]:
        """
        Return up to max_items evidence items for embedding in the PDF.
        Prioritise highest-severity events.
        """
        from core.risk.risk_config import BASE_POINTS
        scored = sorted(
            self._evidence,
            key=lambda e: BASE_POINTS.get(e["event_type"], 0),
            reverse=True,
        )
        return scored[:max_items]

    @property
    def total_saved(self) -> int:
        return self._total_saved

    # ── Internal ──────────────────────────────────────────────

    def _save(self, frame, event_type: str,
              risk_score: int, confidence: float,
              camera: str) -> str | None:
        """Write one screenshot and record its metadata."""
        ts       = datetime.now()
        ts_str   = ts.strftime("%Y%m%d_%H%M%S_%f")[:19]
        safe_evt = event_type.replace(" ", "_")
        filename = f"{ts_str}_{safe_evt}_{camera}.jpg"
        path     = os.path.join(self._dir, filename)

        try:
            ok = cv2.imwrite(path, frame,
                             [int(cv2.IMWRITE_JPEG_QUALITY), 90])
            if not ok:
                logger.warning(f"Screenshot write failed: {path}")
                return None
        except Exception as e:
            logger.error(f"Screenshot error: {e}")
            return None

        meta = {
            "path":        path,
            "filename":    filename,
            "event_type":  event_type,
            "time":        ts.strftime("%H:%M:%S"),
            "timestamp":   ts.isoformat(),
            "risk_score":  risk_score,
            "confidence":  round(confidence, 3),
            "camera":      camera,
            "session_id":  self._session_id,
            "student_id":  self._student_id,
            "description": f"{event_type} detected at {ts.strftime('%H:%M:%S')}",
        }
        self._evidence.append(meta)
        self._total_saved += 1
        logger.info(f"Evidence captured: {filename}")
        return path

    def export_index(self) -> str | None:
        """Save evidence index JSON alongside screenshots."""
        path = os.path.join(self._dir, "evidence_index.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({
                    "session_id": self._session_id,
                    "student_id": self._student_id,
                    "total":      self._total_saved,
                    "evidence":   self._evidence,
                }, f, indent=2)
            return path
        except Exception as e:
            logger.error(f"Evidence index export failed: {e}")
            return None
