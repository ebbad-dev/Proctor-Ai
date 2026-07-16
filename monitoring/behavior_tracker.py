# ============================================================
# ProctorAI — monitoring/behavior_tracker.py
#
# CHANGES:
#   1. Accepts new event types: low_light, keyboard, clipboard,
#      devtools, fullscreen from the upgraded DetectionWorker.
#   2. COOLDOWN table extended for all new event types.
#   3. Bounded deque (maxlen=500) preserved.
#   4. gaze_away, low_light added as first-class parameters.
# ============================================================

from collections import deque
from datetime import datetime
from utils.helpers import get_logger, now_str
from core.events.event_types import (
    EVENT_FACE_MISSING, EVENT_MULTI_FACE, EVENT_LOOK_AWAY,
    EVENT_PHONE, EVENT_TAB_SWITCH, EVENT_AUDIO_ALERT, EVENT_GAZE_AWAY,
    EVENT_KEYBOARD_SHORTCUT, EVENT_CLIPBOARD_ACCESS,
    EVENT_DEVTOOLS_OPENED, EVENT_FULLSCREEN_EXIT, EVENT_LOW_LIGHT,
)

logger = get_logger("BehaviorTracker")

_ALL_EVENTS = [
    EVENT_FACE_MISSING, EVENT_MULTI_FACE, EVENT_LOOK_AWAY,
    EVENT_GAZE_AWAY, EVENT_PHONE, EVENT_TAB_SWITCH, EVENT_AUDIO_ALERT,
    EVENT_KEYBOARD_SHORTCUT, EVENT_CLIPBOARD_ACCESS,
    EVENT_DEVTOOLS_OPENED, EVENT_FULLSCREEN_EXIT, EVENT_LOW_LIGHT,
]

_LOG_MAXLEN = 500


class BehaviorTracker:
    """
    Receives detection results each tick and:
      1. Applies per-event cooldowns to suppress duplicate alerts.
      2. Fires events to the in-memory log and the database.
      3. Exposes event_counts and event_log for the dashboard.

    Now handles full set of browser + vision + audio events.
    """

    COOLDOWN = {
        EVENT_FACE_MISSING:      5,
        EVENT_MULTI_FACE:        5,
        EVENT_LOOK_AWAY:         4,
        EVENT_GAZE_AWAY:         4,
        EVENT_PHONE:             6,
        EVENT_TAB_SWITCH:        0,   # every switch matters
        EVENT_AUDIO_ALERT:       4,
        EVENT_KEYBOARD_SHORTCUT: 3,
        EVENT_CLIPBOARD_ACCESS:  3,
        EVENT_DEVTOOLS_OPENED:   5,
        EVENT_FULLSCREEN_EXIT:   5,
        EVENT_LOW_LIGHT:        10,
    }

    def __init__(self, event_logger):
        self._logger       = event_logger
        self._last_fired   = {}
        self._event_log    = deque(maxlen=_LOG_MAXLEN)
        self._event_counts = {e: 0 for e in _ALL_EVENTS}
        logger.info("BehaviorTracker ready.")

    def update(
        self,
        face_present:  bool,
        multi_face:    bool,
        look_away:     bool,
        gaze_away:     bool,
        phone:         bool,
        tab_switch:    bool,
        audio_alert:   bool,
        low_light:     bool = False,
        keyboard:      bool = False,
        clipboard:     bool = False,
        devtools:      bool = False,
        fullscreen:    bool = False,
    ) -> list:
        """
        Process one monitoring tick.
        Returns list of event-type strings fired this tick.
        """
        checks = [
            (not face_present, EVENT_FACE_MISSING),
            (multi_face,       EVENT_MULTI_FACE),
            (look_away,        EVENT_LOOK_AWAY),
            (gaze_away,        EVENT_GAZE_AWAY),
            (phone,            EVENT_PHONE),
            (tab_switch,       EVENT_TAB_SWITCH),
            (audio_alert,      EVENT_AUDIO_ALERT),
            (low_light,        EVENT_LOW_LIGHT),
            (keyboard,         EVENT_KEYBOARD_SHORTCUT),
            (clipboard,        EVENT_CLIPBOARD_ACCESS),
            (devtools,         EVENT_DEVTOOLS_OPENED),
            (fullscreen,       EVENT_FULLSCREEN_EXIT),
        ]

        fired = []
        now   = datetime.now()

        for condition, event_type in checks:
            if not condition:
                continue

            last     = self._last_fired.get(event_type)
            cooldown = self.COOLDOWN.get(event_type, 3)
            if last and (now - last).total_seconds() < cooldown:
                continue

            self._last_fired[event_type]   = now
            self._event_counts[event_type] += 1
            self._event_log.append({
                "time":       now_str(),
                "event_type": event_type,
                "count":      self._event_counts[event_type],
            })
            self._logger.log(event_type)
            fired.append(event_type)
            logger.info(
                f"Behavior: {event_type} (total #{self._event_counts[event_type]})"
            )

        return fired

    @property
    def event_log(self) -> list:
        return list(reversed(self._event_log))

    @property
    def event_counts(self) -> dict:
        return dict(self._event_counts)

    def reset(self):
        self._last_fired   = {}
        self._event_log    = deque(maxlen=_LOG_MAXLEN)
        self._event_counts = {k: 0 for k in _ALL_EVENTS}
