from __future__ import annotations

import re
from dataclasses import dataclass, field

# Guide Assistant: a deterministic, role-aware knowledge base describing how ProctorAI works.
# Answers must stay in sync with the actual product flow (setup wizard, exam page, risk scoring,
# review and reports). Confidence reflects how strongly the question matched an entry.

STUDENT = "student"
STAFF = "staff"  # instructors and admins
ANY = "any"

_STOPWORDS = {
    "a", "an", "the", "i", "my", "me", "do", "does", "is", "are", "to", "of", "in", "on", "for",
    "how", "what", "why", "can", "when", "where", "it", "this", "that", "with", "be", "and", "or",
    "you", "your", "should", "will", "get", "there", "not", "isnt", "doesnt", "dont",
}


@dataclass(frozen=True)
class Entry:
    intent: str
    audience: str
    keywords: tuple[str, ...]
    answer: str
    quick_actions: tuple[str, ...] = ()
    references: tuple[str, ...] = field(default_factory=tuple)


ENTRIES: tuple[Entry, ...] = (
    Entry(
        "start_exam", STUDENT,
        ("start", "begin", "take", "exam", "setup", "wizard", "ready", "join"),
        "Open Setup Wizard and work through each step: Permissions (run the camera and microphone "
        "tests), Camera Check, Microphone Check, Browser Guard (enter fullscreen if your exam requires "
        "it), ID Verification (capture your face and your university ID), and Room Scan (capture the room "
        "and confirm your desk is clear). On the Ready step choose your assigned exam or type the exam "
        "code from your instructor, enter your official roll number, then press Start exam.",
        ("Camera help", "Exam code", "Submit exam"),
        ("/setup",),
    ),
    Entry(
        "exam_code", STUDENT,
        ("code", "join", "exam code", "published", "found"),
        "Type the exam code your instructor gave you on the Ready step of the Setup Wizard. The code "
        "only works once the exam is published and inside its scheduled window. If you also see the exam "
        "in the Assigned exam list, leave the code field empty and select it there instead; a code in the "
        "field always takes priority.",
        ("Start exam",),
        ("/setup",),
    ),
    Entry(
        "submit_exam", STUDENT,
        ("submit", "finish", "end", "done", "autosave", "save", "reattempt", "retake", "timer", "time"),
        "Answers are saved automatically as soon as you select them. Press Submit exam when you are "
        "finished; submission is final and the exam cannot be reattempted. If the timer reaches zero "
        "your answers are submitted automatically.",
        ("Risk score",),
        ("/exam",),
    ),
    Entry(
        "camera_help", ANY,
        ("camera", "webcam", "video", "blocked", "use", "permission", "black", "allowed"),
        "Allow camera access for this site from the camera icon in the browser address bar, and close "
        "other apps that use the camera (Teams, Zoom, OBS, Camera). If the wizard says the camera is in "
        "use by another app, close those apps and press Restart camera. During the exam the ProctorAI "
        "engine uses the camera, so the browser preview is released when you press Start exam. "
        "Administrators can add a secondary camera by setting WEBCAM_INDEX_SECONDARY.",
        ("Microphone help", "Start exam"),
        ("/setup", "/checklist"),
    ),
    Entry(
        "microphone_help", ANY,
        ("microphone", "mic", "audio", "sound", "noise", "voice"),
        "Allow microphone access from the browser address bar and check that the right input device is "
        "selected in Windows sound settings. During the exam, sustained sound above the configured level "
        "is recorded as an Audio Alert (8 risk points), so take the exam in a quiet room.",
        ("Camera help", "Risk score"),
        ("/setup",),
    ),
    Entry(
        "id_room_scan", STUDENT,
        ("id", "identity", "verification", "card", "face", "room", "scan", "desk", "photo", "capture"),
        "In ID Verification press Capture face, then hold your university ID to the camera and press "
        "Capture ID. In Room Scan, turn the camera around the room, press Capture room and confirm the "
        "desk is clear. These photos are stored as evidence for your instructor.",
        ("Start exam", "Camera help"),
        ("/id-verification", "/room-scan"),
    ),
    Entry(
        "browser_rules", ANY,
        ("browser", "guard", "tab", "switch", "fullscreen", "copy", "paste", "devtools", "extension", "shortcut"),
        "During the exam, leaving the exam tab, copy/paste, blocked keyboard shortcuts, opening DevTools "
        "and exiting fullscreen are recorded and add risk points. Browser Guard is an optional browser "
        "extension that additionally reports the exact sites opened; when an exam requires it, load the "
        "extension from the Browser Guard page before starting.",
        ("Risk score", "Start exam"),
        ("/browser-guard",),
    ),
    Entry(
        "risk_score", ANY,
        ("risk", "score", "points", "flag", "flagged", "critical", "high", "level", "calculated", "suspicious"),
        "The risk score is the sum of points from monitoring events, capped at 100: phone detected 20, "
        "multiple faces 15, DevTools opened 15, face missing 8, tab switch 8, fullscreen exit 8, audio "
        "alert 8, copy/paste and shortcuts 5. Levels are Low (under 20), Medium (under 50), High (under 80) "
        "and Critical (80 and above). The score only highlights sessions for review; an instructor makes "
        "the final decision.",
        ("Reports", "Browser rules"),
    ),
    Entry(
        "review_session", STAFF,
        ("review", "decision", "valid", "false", "positive", "dismiss", "violation", "notes", "evidence", "flagged"),
        "Open the session from the Instructor dashboard or Live Monitor. Check the risk contributors, "
        "evidence (including the pre-exam face, ID and room photos), browser activity and answers, add a "
        "note, then mark it Valid violation, False positive, Manual review recommended or Dismiss. Every "
        "decision is saved to the session and the audit log.",
        ("Reports", "Risk score"),
        ("/instructor", "/monitor"),
    ),
    Entry(
        "reports", ANY,
        ("report", "pdf", "download", "export", "generate"),
        "Open Reports (or Open report from a session review) and use Download PDF. The integrity report "
        "lists the student, exam, duration, risk score, event breakdown, evidence screenshots and the "
        "event timeline. Students can download reports for their own sessions only.",
        ("Risk score",),
        ("/reports",),
    ),
    Entry(
        "create_exam", STAFF,
        ("create", "exam", "question", "questions", "mcq", "publish", "assign", "schedule", "window", "marks", "draft"),
        "On the Instructor dashboard fill in the exam details and schedule window, then press Create new. "
        "Add multiple-choice questions in the Question builder and mark the correct option. Total marks "
        "must match the question marks before you can Publish. Assign students by email, or share the "
        "exam code so students can join from the Setup Wizard.",
        ("Review a session", "Reports"),
        ("/instructor",),
    ),
    Entry(
        "system_status", ANY,
        ("database", "offline", "online", "status", "connected", "backend", "server", "sql", "api", "down"),
        "The Live API and Backend badges show whether ProctorAI can reach its server and database. "
        "Monitoring events are only accepted once they are saved to SQL Server and are retried until "
        "then, so if the database is offline ask your administrator to restart SQL Server before starting "
        "an exam. Administrators can check database, migrations, camera engine and Browser Guard status "
        "on the Ops status endpoint.",
        ("Camera help",),
    ),
    Entry(
        "account_help", ANY,
        ("password", "login", "sign", "account", "reset", "forgot", "register", "google"),
        "Use Forgot password on the sign-in page to receive a reset link by email (this requires email to "
        "be configured by your administrator). Students can create an account from Create account; "
        "instructor and admin accounts are created by an administrator in the Admin Console.",
        (),
        ("/login",),
    ),
)

_CONTENT_REQUEST = re.compile(
    r"\b(solve|correct (option|answer)|answer (to|for|of)|which option|what is the answer|give me the answer)\b"
)


def _stem(word: str) -> str:
    # Light plural folding so "reports"/"questions"/"scans" match their keywords.
    return word[:-1] if len(word) > 3 and word.endswith("s") and not word.endswith("ss") else word


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {_stem(word) for word in words if word not in _STOPWORDS}


def _audience_allows(entry: Entry, role: str) -> bool:
    if entry.audience == ANY:
        return True
    is_staff = role in {"instructor", "admin"}
    return is_staff if entry.audience == STAFF else not is_staff


def _score(entry: Entry, query: str, tokens: set[str]) -> int:
    score = 0
    for keyword in entry.keywords:
        if " " in keyword:
            score += 2 if keyword in query else 0
        elif _stem(keyword) in tokens:
            score += 1
    return score


def chat(query: str, role: str = "student", context: dict | None = None) -> dict:
    text = (query or "").strip().lower()
    role = (role or "student").lower()
    if _CONTENT_REQUEST.search(text):
        return {
            "found": True,
            "intent": "exam_content_refusal",
            "confidence": 1.0,
            "answer": "I can't help with exam answers. I can help with ProctorAI setup, monitoring, reports, and review workflows.",
            "quick_actions": ["Start exam", "Camera help", "Risk score"],
            "references": [],
        }

    tokens = _tokens(text)
    ranked = sorted(
        ((_score(entry, text, tokens), index, entry) for index, entry in enumerate(ENTRIES) if _audience_allows(entry, role)),
        key=lambda row: (-row[0], row[1]),
    )
    best_score, _, best = ranked[0] if ranked else (0, 0, None)
    if not best or best_score == 0:
        topics = "starting an exam, camera and microphone, browser rules, risk scores and reports"
        if role in {"instructor", "admin"}:
            topics = "creating exams, reviewing sessions, risk scores, reports and browser monitoring"
        return {
            "found": False,
            "intent": "fallback",
            "confidence": 0.0,
            "answer": f"I don't have an answer for that yet. I can help with {topics}.",
            "quick_actions": ["Start exam", "Camera help", "Risk score"] if role == "student" else ["Create exam", "Review a session", "Reports"],
            "references": [],
        }

    runner_up = ranked[1][0] if len(ranked) > 1 else 0
    confidence = min(0.95, 0.45 + 0.15 * best_score - (0.1 if runner_up == best_score else 0.0))
    return {
        "found": True,
        "intent": best.intent,
        "confidence": round(max(confidence, 0.35), 2),
        "answer": best.answer,
        "quick_actions": list(best.quick_actions),
        "references": list(best.references),
    }
