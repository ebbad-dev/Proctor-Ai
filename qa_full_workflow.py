from __future__ import annotations

import base64
import json
import os
import secrets
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def load_env() -> None:
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def expect(response, status: int, label: str):
    if response.status_code != status:
        raise AssertionError(f"{label}: expected {status}, got {response.status_code}: {response.text[:500]}")
    if response.headers.get("content-type", "").startswith("application/json"):
        return response.json()
    return response.content


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def run() -> dict:
    load_env()
    for dependency_dir in (ROOT / "python_runtime_deps", ROOT / "python_user_deps"):
        if dependency_dir.exists():
            sys.path.insert(0, str(dependency_dir))
    sys.path.insert(0, str(ROOT))

    from fastapi.testclient import TestClient
    import infrastructure.api.fastapi_app as fastapi_app

    admin_email = os.environ.get("PROCTORAI_BOOTSTRAP_ADMIN_EMAIL", "").strip()
    admin_password = os.environ.get("PROCTORAI_BOOTSTRAP_ADMIN_PASSWORD", "")
    if not admin_email or not admin_password:
        raise RuntimeError("Bootstrap admin credentials must be configured in .env for the live SQL workflow test.")

    suffix = secrets.token_hex(4)
    instructor_email = f"sarah.ahmed.{suffix}@qa.proctorai.local"
    student_email = f"amina.siddiqui.{suffix}@qa.proctorai.local"
    instructor_password = f"Qa!9{secrets.token_urlsafe(14)}"
    student_password = f"Qa!9{secrets.token_urlsafe(14)}"
    exam_code = f"CALC{suffix.upper()}"
    ids: dict[str, list[str]] = {
        "users": [],
        "exams": [],
        "questions": [],
        "attempts": [],
        "sessions": [],
    }
    checks: dict[str, object] = {}

    with TestClient(fastapi_app.app) as client:
        try:
            checks["health"] = expect(client.get("/health"), 200, "health").get("status")
            admin_session = expect(
                client.post("/auth/login", json={"email": admin_email, "password": admin_password}),
                200,
                "admin login",
            )
            admin_token = admin_session["access_token"]
            tenant_id = admin_session["user"].get("tenant_id") or "tenant_default"
            checks["admin_role"] = admin_session["user"]["role"]

            tenants = expect(client.get("/tenants", headers=auth(admin_token)), 200, "tenant dropdown data")
            assert any(row.get("tenant_id") == tenant_id for row in tenants), "Current tenant missing from admin tenant dropdown data."

            instructor = expect(
                client.post(
                    "/admin/users",
                    headers=auth(admin_token),
                    json={
                        "email": instructor_email,
                        "full_name": "Dr. Sarah Ahmed",
                        "role": "instructor",
                        "tenant_id": tenant_id,
                        "password": instructor_password,
                    },
                ),
                200,
                "create instructor",
            )
            ids["users"].append(instructor["user_id"])
            student = expect(
                client.post(
                    "/admin/users",
                    headers=auth(admin_token),
                    json={
                        "email": student_email,
                        "full_name": "Amina Siddiqui",
                        "role": "student",
                        "tenant_id": tenant_id,
                        "password": student_password,
                    },
                ),
                200,
                "create student",
            )
            ids["users"].append(student["user_id"])

            instructor_session = expect(
                client.post("/auth/login", json={"email": instructor_email, "password": instructor_password}),
                200,
                "instructor login",
            )
            student_session = expect(
                client.post("/auth/login", json={"email": student_email, "password": student_password}),
                200,
                "student login",
            )
            instructor_token = instructor_session["access_token"]
            student_token = student_session["access_token"]
            expect(client.get("/admin/users", headers=auth(instructor_token)), 403, "instructor admin denial")
            expect(client.get("/exams", headers=auth(student_token)), 403, "student instructor API denial")
            checks["role_access"] = "enforced"

            now = datetime.now(timezone.utc)
            exam_payload = {
                "exam_code": exam_code,
                "title": "Calculus I Midterm Assessment",
                "description": "A timed assessment covering limits and differential calculus.",
                "semester": "Fall 2026",
                "subject": "Calculus I",
                "department": "Mathematics",
                "total_marks": 20,
                "duration_minutes": 45,
                "start_time": (now - timedelta(minutes=10)).isoformat(),
                "end_time": (now + timedelta(hours=2)).isoformat(),
                "status": "draft",
                "rules": {
                    "require_fullscreen": True,
                    "browser_guard_required": False,
                    "camera_required": True,
                    "microphone_required": True,
                },
            }
            exam = expect(client.post("/exams", headers=auth(instructor_token), json=exam_payload), 200, "create exam")
            exam_id = exam["id"]
            ids["exams"].append(exam_id)
            listed = expect(client.get("/exams", headers=auth(instructor_token)), 200, "exam dropdown data")
            loaded = next(row for row in listed if row["id"] == exam_id)
            assert loaded["semester"] == "Fall 2026" and loaded["department"] == "Mathematics"
            checks["exam_fields_loaded"] = True

            question_payload = {
                "question_text": "What is the derivative of x squared?",
                "question_type": "mcq",
                "marks": 2,
                "sort_order": 0,
                "status": "active",
                "options": [
                    {"option_text": "2x", "is_correct": True, "sort_order": 0},
                    {"option_text": "x", "is_correct": False, "sort_order": 1},
                    {"option_text": "2", "is_correct": False, "sort_order": 2},
                    {"option_text": "x squared", "is_correct": False, "sort_order": 3},
                ],
            }
            question = expect(
                client.post(f"/exams/{exam_id}/questions", headers=auth(instructor_token), json=question_payload),
                200,
                "create MCQ",
            )
            ids["questions"].append(question["question_id"])
            correct_option = next(option for option in question["options"] if option.get("is_correct"))
            mismatch = client.post(f"/exams/{exam_id}/publish", headers=auth(instructor_token))
            expect(mismatch, 422, "marks mismatch validation")
            checks["publish_validation"] = mismatch.json().get("error")

            exam_payload["total_marks"] = 2
            expect(client.put(f"/exams/{exam_id}", headers=auth(instructor_token), json=exam_payload), 200, "correct marks")
            published = expect(client.post(f"/exams/{exam_id}/publish", headers=auth(instructor_token)), 200, "publish exam")
            assert published["status"] == "published"

            assignment = expect(
                client.post(
                    f"/exams/{exam_id}/assignments",
                    headers=auth(instructor_token),
                    json={"student_email": student_email},
                ),
                200,
                "assign student",
            )
            assigned = expect(client.get("/student/exams", headers=auth(student_token)), 200, "student exam dropdown data")
            assert any(row["id"] == exam_id for row in assigned)
            joined = expect(
                client.post("/student/exams/join-code", headers=auth(student_token), json={"exam_code": exam_code.lower()}),
                200,
                "join by exam code",
            )
            assert joined["id"] == exam_id and joined.get("assignment_id") == assignment.get("assignment_id")
            checks["code_join"] = True

            attempt = expect(
                client.post(
                    "/attempts/start",
                    headers=auth(student_token),
                    json={"exam_id": exam_id, "roll_number": "FA26-MTH-1042"},
                ),
                200,
                "start attempt",
            )
            attempt_id = attempt["attempt_id"]
            session_id = attempt["session_id"]
            ids["attempts"].append(attempt_id)
            ids["sessions"].append(session_id)
            assert attempt["questions"] and "is_correct" not in attempt["questions"][0]["options"][0]

            image_data = "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8\xff\xd9").decode("ascii")
            for evidence_type, label in (
                ("face", "Pre-exam face capture"),
                ("id_card", "Pre-exam university ID capture"),
                ("room_scan", "Pre-exam room scan confirmation"),
            ):
                expect(
                    client.post(
                        "/evidence",
                        headers=auth(student_token),
                        json={
                            "session_id": session_id,
                            "evidence_type": evidence_type,
                            "label": label,
                            "image_data": image_data,
                        },
                    ),
                    200,
                    f"persist {evidence_type} evidence",
                )
            evidence_rows = expect(client.get(f"/sessions/{session_id}/evidence", headers=auth(student_token)), 200, "read evidence")
            assert len(evidence_rows) >= 3
            checks["evidence_count"] = len(evidence_rows)

            for path, payload in (
                ("/tab-event", {"direction": "away", "session_id": session_id}),
                ("/keyboard-event", {"combo": "Ctrl+Shift+I", "session_id": session_id}),
                ("/clipboard-event", {"action": "paste", "session_id": session_id}),
                ("/devtools-event", {"state": "open", "session_id": session_id}),
                ("/fullscreen-event", {"state": "exit", "session_id": session_id}),
            ):
                expect(client.post(path, headers=auth(student_token), json=payload), 200, f"browser signal {path}")
            risk = expect(client.get(f"/sessions/{session_id}/risk", headers=auth(student_token)), 200, "risk score")
            events = expect(client.get(f"/sessions/{session_id}/events", headers=auth(student_token)), 200, "event timeline")
            browser_rows = expect(client.get(f"/sessions/{session_id}/browser-activity", headers=auth(student_token)), 200, "browser activity")
            assert risk["score"] > 0 and len(events) >= 5 and len(browser_rows) >= 5
            checks["risk_score"] = risk["score"]

            expect(
                client.post(
                    f"/attempts/{attempt_id}/responses",
                    headers=auth(student_token),
                    json={"question_id": question["question_id"], "selected_option_id": correct_option["option_id"]},
                ),
                200,
                "autosave answer",
            )
            active_attempt = expect(client.get(f"/attempts/{attempt_id}", headers=auth(student_token)), 200, "reload autosaved answer")
            assert active_attempt["responses"][0]["selected_option_id"] == correct_option["option_id"]

            submitted = expect(
                client.post(f"/attempts/{attempt_id}/submit", headers=auth(student_token), json={"generate_report": True}),
                200,
                "submit exam",
            )
            assert submitted["status"] == "submitted" and submitted["score"] == 2 and submitted["risk_score"] > 0
            expect(
                client.post(
                    "/attempts/start",
                    headers=auth(student_token),
                    json={"exam_id": exam_id, "roll_number": "FA26-MTH-1042"},
                ),
                409,
                "reattempt lock",
            )
            attendance = expect(client.get(f"/exams/{exam_id}/attendance", headers=auth(instructor_token)), 200, "attendance")
            attendance_row = next(row for row in attendance if row["student_user_id"] == student["user_id"])
            assert attendance_row["attempt_status"] == "submitted" and attendance_row["score"] == 2
            report = client.get(f"/sessions/{session_id}/report", headers=auth(instructor_token))
            if report.status_code not in {200, 404, 503}:
                raise AssertionError(f"report endpoint returned {report.status_code}: {report.text[:500]}")
            checks["report_status"] = report.status_code
            checks["submission"] = {"score": submitted["score"], "reattempt_locked": True}

            future_payload = {
                **exam_payload,
                "exam_code": f"FUT{suffix.upper()}",
                "title": "Linear Algebra Scheduled Assessment",
                "total_marks": 1,
                "start_time": (now + timedelta(days=1)).isoformat(),
                "end_time": (now + timedelta(days=2)).isoformat(),
                "status": "scheduled",
            }
            future_exam = expect(client.post("/exams", headers=auth(instructor_token), json=future_payload), 200, "create scheduled exam")
            future_exam_id = future_exam["id"]
            ids["exams"].append(future_exam_id)
            future_question = expect(
                client.post(
                    f"/exams/{future_exam_id}/questions",
                    headers=auth(instructor_token),
                    json={**question_payload, "marks": 1},
                ),
                200,
                "create scheduled question",
            )
            ids["questions"].append(future_question["question_id"])
            expect(
                client.post(
                    f"/exams/{future_exam_id}/assignments",
                    headers=auth(instructor_token),
                    json={"student_email": student_email},
                ),
                200,
                "assign scheduled exam",
            )
            scheduled_start = client.post(
                "/attempts/start",
                headers=auth(student_token),
                json={"exam_id": future_exam_id, "roll_number": "FA26-MTH-1042"},
            )
            expect(scheduled_start, 403, "scheduled start gate")
            checks["schedule_gate"] = scheduled_start.json().get("error")

            return checks
        finally:
            db = fastapi_app._get_db()
            if db and db.is_active:
                for session_id in ids["sessions"]:
                    for statement in (
                        "DELETE FROM Reports WHERE session_id = ?",
                        "DELETE FROM Evidence WHERE session_id = ?",
                        "DELETE FROM Events WHERE session_id = ?",
                    ):
                        try:
                            db.execute(statement, (session_id,))
                        except Exception:
                            pass
                for attempt_id in ids["attempts"]:
                    db.execute("DELETE FROM StudentResponses WHERE attempt_id = ?", (attempt_id,))
                    db.execute("DELETE FROM ExamAttempts WHERE attempt_id = ?", (attempt_id,))
                for session_id in ids["sessions"]:
                    db.execute("DELETE FROM Sessions WHERE session_id = ?", (session_id,))
                for question_id in ids["questions"]:
                    db.execute("DELETE FROM QuestionOptions WHERE question_id = ?", (question_id,))
                    db.execute("DELETE FROM ExamQuestions WHERE question_id = ?", (question_id,))
                for exam_id in ids["exams"]:
                    db.execute("DELETE FROM ExamAssignments WHERE exam_id = ?", (exam_id,))
                    db.execute("DELETE FROM Exams WHERE exam_id = ?", (exam_id,))
                for user_id in ids["users"]:
                    try:
                        db.execute("DELETE FROM PasswordResetTokens WHERE user_id = ?", (user_id,))
                    except Exception:
                        pass
                    db.execute("DELETE FROM Users WHERE user_id = ?", (user_id,))


if __name__ == "__main__":
    result = run()
    print(json.dumps({"status": "passed", "checks": result, "cleanup": "completed"}, indent=2, default=str))
