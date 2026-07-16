# ============================================================
# ProctorAI — utils/constants.py
#
# Re-exports all constants from core.events.event_types so
# that existing imports continue to work without any changes.
# New code should import directly from core.events.event_types.
# ============================================================

from core.events.event_types import (  # noqa: F401 — public re-export
    EVENT_FACE_MISSING,
    EVENT_MULTI_FACE,
    EVENT_LOOK_AWAY,
    EVENT_GAZE_AWAY,
    EVENT_PHONE,
    EVENT_TAB_SWITCH,
    EVENT_KEYBOARD_SHORTCUT,
    EVENT_CLIPBOARD_ACCESS,
    EVENT_DEVTOOLS_OPENED,
    EVENT_FULLSCREEN_EXIT,
    EVENT_AUDIO_ALERT,
    EVENT_CAMERA_COVERED,
    EVENT_CAMERA_FROZEN,
    EVENT_LOW_LIGHT,
    EVENT_BROWSER_ACTIVITY,
    ALL_EVENT_TYPES,
    VISION_EVENT_TYPES,
    EVENT_ICONS,
    EVENT_COLORS,
    RISK_LOW,
    RISK_MEDIUM,
    RISK_HIGH,
    RISK_CRITICAL,
    DIR_FORWARD,
    DIR_LEFT,
    DIR_RIGHT,
    DIR_DOWN,
    DIR_UP,
    TABLE_STUDENTS,
    TABLE_EVENTS,
    TABLE_SESSIONS,
)
