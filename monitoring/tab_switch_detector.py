# ============================================================
# ProctorAI — monitoring/tab_switch_detector.py
#
# CHANGES:
#   1. Flask endpoints: /key-event, /clipboard-event,
#      /devtools-event, /fullscreen-event (for tab_monitor.js).
#   2. Browser Guard events consolidated to FastAPI on port 5051.
#      Flask no longer handles /browser-guard/* endpoints.
#   3. consume_*() methods for each event type.
#   4. Browser activity log for timeline in reports.
#   5. MJPEG video feed endpoints preserved.
# ============================================================

import threading
import logging as _logging
from collections import deque
from datetime import datetime

from utils.helpers import get_logger
from config.settings import FLASK_HOST, FLASK_PORT

logger = get_logger("TabSwitchDetector")

_GLOBAL_DETECTOR: "TabSwitchDetector | None" = None
_SINGLETON_LOCK = threading.Lock()


def get_or_create_detector() -> "TabSwitchDetector":
    global _GLOBAL_DETECTOR
    with _SINGLETON_LOCK:
        if _GLOBAL_DETECTOR is None:
            _GLOBAL_DETECTOR = TabSwitchDetector()
            _GLOBAL_DETECTOR.start()
        else:
            _GLOBAL_DETECTOR.reset()
        return _GLOBAL_DETECTOR


class TabSwitchDetector:
    """
    Lightweight Flask sidecar that receives browser events from
    the JS snippet injected into the exam page (tab switch,
    keyboard shortcuts, clipboard, devtools, fullscreen).

    Browser Guard extension events are handled exclusively by
    FastAPI on port 5051 — NOT by this Flask server.

    All events are consumed each monitoring tick and forwarded to
    the DetectionWorker via the main.py loop.
    """

    def __init__(self):
        self._lock    = threading.Lock()
        self._thread  = None
        self._running = False
        self._app     = None
        self._webcam  = None
        self._worker  = None

        # Event flags (consumed each tick)
        self._tab_switch_new     = False
        self._keyboard_new       = False
        self._clipboard_new      = False
        self._devtools_new       = False
        self._fullscreen_new     = False
        self._browser_guard_active = False

        # Counters
        self._tab_count    = 0
        self._keyboard_count = 0
        self._clipboard_count = 0
        self._devtools_count  = 0

        # Browser activity log (for report timeline)
        self._browser_log: deque = deque(maxlen=200)

    def set_providers(self, webcam, worker):
        self._webcam = webcam
        self._worker = worker

    @property
    def browser_guard_active(self) -> bool:
        with self._lock:
            return self._browser_guard_active

    # ── CORS helper ───────────────────────────────────────────
    @staticmethod
    def _add_cors(response):
        response.headers["Access-Control-Allow-Origin"]  = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Requested-With"
        return response

    # ── Start ─────────────────────────────────────────────────
    def start(self):
        try:
            from flask import Flask, request, jsonify, Response
        except ImportError:
            logger.warning("Flask not installed — browser monitoring disabled.")
            return

        app = Flask(__name__)
        app.logger.disabled = True
        _logging.getLogger("werkzeug").setLevel(_logging.ERROR)
        app.after_request(self._add_cors)

        # ── OPTIONS preflight ─────────────────────────────────
        for route in ["/tab-event", "/key-event", "/clipboard-event",
                      "/devtools-event", "/fullscreen-event"]:
            app.add_url_rule(
                route, f"preflight_{route.replace('/', '_')}",
                lambda: Response(status=204), methods=["OPTIONS"]
            )

        # Event ingestion has moved to FastAPI.
        # This Flask sidecar is now strictly used for MJPEG video feeds.

        # ── MJPEG video feed ──────────────────────────────────
        def require_video_access():
            from core.security import decode_media_token

            token = request.args.get("token", "")
            if not token:
                return None
            try:
                return decode_media_token(token)
            except Exception:
                return None

        @app.route("/video_feed")
        def video_feed():
            if not require_video_access():
                return jsonify({"error": "not_authenticated", "message": "A valid video token is required."}), 401
            def generate():
                import cv2, time
                last_id = -1
                while True:
                    if self._webcam and self._webcam.is_running:
                        fid, frame = self._webcam.get_latest_frame_with_id()
                        if frame is not None and fid != last_id:
                            last_id = fid
                            # Use annotated frame from worker if available
                            annotated = frame.copy()
                            if self._worker and self._worker.latest_result:
                                res = self._worker.latest_result
                                ann = res.get("annotated")
                                if ann is not None and ann.shape == frame.shape:
                                    annotated = ann
                            _, buf = cv2.imencode(
                                ".jpg", annotated,
                                [int(cv2.IMWRITE_JPEG_QUALITY), 85]
                            )
                            yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
                                   + buf.tobytes() + b"\r\n")
                        else:
                            time.sleep(0.001)
                    else:
                        time.sleep(0.1)
            return Response(generate(),
                            mimetype="multipart/x-mixed-replace; boundary=frame")

        @app.route("/video_feed_secondary")
        def video_feed_secondary():
            if not require_video_access():
                return jsonify({"error": "not_authenticated", "message": "A valid video token is required."}), 401
            def generate():
                import cv2, time
                last_id = -1
                webcam2 = getattr(self, "_webcam2", None)
                while True:
                    if webcam2 and webcam2.is_running:
                        fid, frame = webcam2.get_latest_frame_with_id()
                        if frame is not None and fid != last_id:
                            last_id = fid
                            _, buf = cv2.imencode(
                                ".jpg", frame,
                                [int(cv2.IMWRITE_JPEG_QUALITY), 80]
                            )
                            yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
                                   + buf.tobytes() + b"\r\n")
                        else:
                            time.sleep(0.001)
                    else:
                        time.sleep(0.1)
            return Response(generate(),
                            mimetype="multipart/x-mixed-replace; boundary=frame")

        @app.route("/ping")
        def ping():
            return jsonify({
                "status": "alive",
                "switches":  self._tab_count,
                "keyboard":  self._keyboard_count,
                "clipboard": self._clipboard_count,
                "devtools":  self._devtools_count,
                "guard":     self._browser_guard_active,
            })

        self._app    = app
        self._running = True
        self._thread  = threading.Thread(
            target=self._run_flask, daemon=True, name="TabSwitchFlask"
        )
        self._thread.start()
        logger.info(f"Browser monitor server on http://{FLASK_HOST}:{FLASK_PORT}")

    def _run_flask(self):
        try:
            self._app.run(
                host=FLASK_HOST, port=FLASK_PORT,
                use_reloader=False, threaded=True, debug=False,
            )
        except OSError as e:
            logger.error(
                f"Flask failed to bind {FLASK_HOST}:{FLASK_PORT} — {e}\n"
                f"  → Change FLASK_PORT in config/settings.py"
            )

    # ── Consumer API ──────────────────────────────────────────

    def consume_switch(self) -> bool:
        with self._lock:
            if self._tab_switch_new:
                self._tab_switch_new = False
                return True
        return False

    def consume_keyboard(self) -> bool:
        with self._lock:
            if self._keyboard_new:
                self._keyboard_new = False
                return True
        return False

    def consume_clipboard(self) -> bool:
        with self._lock:
            if self._clipboard_new:
                self._clipboard_new = False
                return True
        return False

    def consume_devtools(self) -> bool:
        with self._lock:
            if self._devtools_new:
                self._devtools_new = False
                return True
        return False

    def consume_fullscreen(self) -> bool:
        with self._lock:
            if self._fullscreen_new:
                self._fullscreen_new = False
                return True
        return False

    def consume_all_browser_events(self) -> dict:
        """Return dict of all pending browser events (resets flags)."""
        return {
            "tab_switch": self.consume_switch(),
            "keyboard":   self.consume_keyboard(),
            "clipboard":  self.consume_clipboard(),
            "devtools":   self.consume_devtools(),
            "fullscreen": self.consume_fullscreen(),
        }

    @property
    def total_switches(self) -> int:
        with self._lock:
            return self._tab_count

    def get_browser_log(self) -> list:
        """Return browser activity log for report timeline."""
        with self._lock:
            return list(reversed(self._browser_log))

    def _log_browser_event(self, event_type: str, description: str,
                           url: str = "", risk: str = "low"):
        with self._lock:
            self._browser_log.append({
                "time":        datetime.now().strftime("%H:%M:%S"),
                "event_type":  event_type,
                "description": description,
                "url":         url,
                "risk":        risk,
            })

    # ── FastAPI bridge ────────────────────────────────────────
    def bridge_browser_guard_event(self, event_type: str, url: str,
                                   title: str, category: str,
                                   risk: str):
        """Called by FastAPI to forward Browser Guard events into
        the monitoring loop so consume_*() picks them up."""
        with self._lock:
            self._browser_guard_active = True
            if event_type in ("tab_switch", "url_change", "suspicious_site"):
                self._tab_switch_new = True
                self._tab_count += 1
        self._log_browser_event(
            f"Browser: {event_type}",
            f"{category} — {title[:60]}" if title else url[:80],
            url=url, risk=risk,
        )
        logger.info(f"[FastAPI→Flask] Browser Guard: {event_type} | {category} | {url[:60]}")

    def bridge_extension_key_event(self, combo: str):
        """Called by FastAPI to forward content.js keyboard events."""
        with self._lock:
            self._keyboard_count += 1
            self._keyboard_new = True
        self._log_browser_event("Keyboard Shortcut", f"Shortcut: {combo}")

    def bridge_extension_clipboard_event(self, action: str):
        """Called by FastAPI to forward content.js clipboard events."""
        with self._lock:
            self._clipboard_count += 1
            self._clipboard_new = True
        self._log_browser_event("Clipboard Access", f"Action: {action}")

    def bridge_tab_event(self, direction: str):
        """Called by FastAPI to forward tab switch events."""
        if direction == "away":
            with self._lock:
                self._tab_count += 1
                self._tab_switch_new = True
            self._log_browser_event("Tab Switch", "Left exam tab")
            logger.info(f"Tab switch #{self._tab_count}")

    def bridge_devtools_event(self, state: str):
        """Called by FastAPI to forward devtools events."""
        with self._lock:
            self._devtools_count += 1
            self._devtools_new = True
        self._log_browser_event("DevTools Opened", "DevTools detected")
        logger.warning("DevTools opened by student!")

    def bridge_fullscreen_event(self, state: str):
        """Called by FastAPI to forward fullscreen events."""
        if state == "exit":
            with self._lock:
                self._fullscreen_new = True
            self._log_browser_event("Fullscreen Exit", "Exited fullscreen mode")

    def set_secondary_webcam(self, webcam2):
        self._webcam2 = webcam2

    def reset(self):
        with self._lock:
            self._tab_count         = 0
            self._keyboard_count    = 0
            self._clipboard_count   = 0
            self._devtools_count    = 0
            self._tab_switch_new    = False
            self._keyboard_new      = False
            self._clipboard_new     = False
            self._devtools_new      = False
            self._fullscreen_new    = False
            self._browser_guard_active = False
            self._browser_log       = deque(maxlen=200)
        logger.info("TabSwitchDetector counters reset for new session.")

    def stop(self):
        self._running = False
        logger.info("TabSwitchDetector stop() called (server remains alive).")
