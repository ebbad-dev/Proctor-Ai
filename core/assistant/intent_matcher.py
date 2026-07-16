from __future__ import annotations


def chat(query: str, role: str = "student", context: dict | None = None) -> dict:
    q = (query or "").lower()
    if any(token in q for token in ("solve", "answer", "mcq", "correct option", "question")):
        return {
            "found": True,
            "intent": "exam_content_refusal",
            "confidence": 1.0,
            "answer": "I can't help with exam answers. I can help with ProctorAI setup, monitoring, reports, and review workflows.",
            "quick_actions": ["Camera help", "Browser Guard", "Report help"],
            "references": [],
        }
    if "camera" in q or "webcam" in q:
        answer = "Check camera permissions, close other camera apps, then retry the setup checklist. If the wrong camera opens, adjust WEBCAM_INDEX in config/settings.py."
        intent = "camera_help"
    elif "browser" in q or "guard" in q or "tab" in q:
        answer = "Start the FastAPI backend, install/load the Browser Guard extension, and verify /browser-guard/ping returns alive."
        intent = "browser_guard_help"
    elif "report" in q or "pdf" in q:
        answer = "Reports are generated from session events and saved in the reports folder as <session_id>_report.pdf when PDF dependencies are available."
        intent = "report_help"
    elif "database" in q or "sql" in q:
        answer = "The backend tries SQL Server first and falls back to in-memory data if the database is unavailable."
        intent = "database_help"
    else:
        answer = "I can help with camera/mic setup, Browser Guard, session review, reports, and database connectivity."
        intent = "fallback"
    return {
        "found": True,
        "intent": intent,
        "confidence": 0.9,
        "answer": answer,
        "quick_actions": ["Camera help", "Browser Guard", "Reports", "Database"],
        "references": [],
    }
