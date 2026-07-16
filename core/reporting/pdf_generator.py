from __future__ import annotations

from collections import Counter
from datetime import datetime
import json
from pathlib import Path
from typing import Any

from reporting.report_generator import ReportGenerator


class PDFReportGenerator:
    def __init__(
        self,
        session_id: str,
        *,
        repo: Any = None,
        session: dict | None = None,
        events: list[dict] | None = None,
        browser_log: list[dict] | None = None,
    ):
        self.session_id = session_id
        self.repo = repo
        self.session = session
        self.events = events
        self.browser_log = browser_log or []

    def generate(self) -> str | None:
        session = self.session
        events = self.events
        if self.repo:
            session = self.repo.get_session(self.session_id)
            events = self.repo.get_events(self.session_id)

        session = session or {"session_id": self.session_id}
        events = events or []
        event_counts = Counter(e.get("event_type", "Unknown") for e in events)
        raw_risk_score = sum(int(e.get("risk_points") or 0) for e in events)
        risk_score = min(raw_risk_score, 100)
        contributors = [
            {
                "event_type": event_type,
                "count": count,
                "points": sum(
                    int(e.get("risk_points") or 0)
                    for e in events
                    if e.get("event_type") == event_type
                ),
                "pct": 0 if raw_risk_score == 0 else round(
                    sum(
                        int(e.get("risk_points") or 0)
                        for e in events
                        if e.get("event_type") == event_type
                    )
                    * 100
                    / raw_risk_score
                ),
            }
            for event_type, count in event_counts.items()
        ]
        start = session.get("start_time") or session.get("started_at")
        duration_sec = 0
        if start:
            try:
                started = datetime.fromisoformat(str(start).replace("Z", "+00:00"))
                duration_sec = max(0, int((datetime.now(started.tzinfo) - started).total_seconds()))
            except Exception:
                duration_sec = 0

        screenshots = self._load_screenshots()
        _, pdf_path = ReportGenerator().generate(
            student_name=session.get("student_name") or session.get("student_id") or "Unknown",
            student_id=session.get("student_id") or "",
            exam_code=session.get("exam_code") or "",
            session_id=self.session_id,
            duration_sec=duration_sec,
            event_counts=dict(event_counts),
            risk_score=risk_score,
            screenshots=screenshots,
            event_log=events,
            browser_log=self.browser_log,
            contributors=contributors,
        )
        return pdf_path

    def _load_screenshots(self) -> list[dict]:
        from config.settings import SCREENSHOTS_DIR

        session_dir = (Path(SCREENSHOTS_DIR) / self.session_id).resolve()
        index_path = session_dir / "evidence_index.json"
        if index_path.is_file():
            try:
                payload = json.loads(index_path.read_text(encoding="utf-8"))
                evidence = []
                for item in payload.get("evidence", []):
                    path = Path(item.get("path") or session_dir / item.get("filename", "")).resolve()
                    try:
                        path.relative_to(session_dir)
                    except ValueError:
                        continue
                    if not path.is_file():
                        continue
                    timestamp = item.get("timestamp") or ""
                    evidence.append({
                        **item,
                        "path": str(path),
                        "time": item.get("time") or (str(timestamp)[11:19] if len(str(timestamp)) >= 19 else str(timestamp)),
                    })
                return evidence
            except Exception:
                pass
        return []
