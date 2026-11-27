from __future__ import annotations

import json
import multiprocessing
import os
import queue
import secrets
import sys
import uuid
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.security import hash_password
from database.db_connection import DatabaseConnection
from database.platform_repository import PlatformRepository


def _start_attempt_worker(
    worker_id: int,
    exam_id: str,
    user_id: str,
    assignment_id: str,
    tenant_id: str,
    ready_queue,
    start_gate,
    result_queue,
) -> None:
    db = DatabaseConnection()
    connected = db.connect(max_retries=2)
    ready_queue.put({"worker": worker_id, "connected": connected})
    if not connected:
        result_queue.put({"worker": worker_id, "ok": False, "error": "connection_failed"})
        return
    try:
        if not start_gate.wait(timeout=30):
            result_queue.put({"worker": worker_id, "ok": False, "error": "gate_timeout"})
            return
        repo = PlatformRepository(db)
        try:
            attempt = repo.create_attempt(
                exam_id=exam_id,
                user_id=user_id,
                roll_number="RACE-SMOKE",
                assignment_id=assignment_id,
                session_id=f"race_session_{worker_id}_{uuid.uuid4().hex}",
                tenant_id=tenant_id,
            )
            result_queue.put(
                {
                    "worker": worker_id,
                    "ok": True,
                    "attempt_id": attempt.get("attempt_id"),
                }
            )
        except Exception as exc:
            result_queue.put(
                {
                    "worker": worker_id,
                    "ok": False,
                    "error": exc.__class__.__name__,
                }
            )
    finally:
        db.close()


def _submit_attempt_worker(
    worker_id: int,
    attempt_id: str,
    ready_queue,
    start_gate,
    result_queue,
) -> None:
    db = DatabaseConnection()
    connected = db.connect(max_retries=2)
    ready_queue.put({"worker": worker_id, "connected": connected})
    if not connected:
        result_queue.put({"worker": worker_id, "ok": False, "error": "connection_failed"})
        return
    try:
        if not start_gate.wait(timeout=30):
            result_queue.put({"worker": worker_id, "ok": False, "error": "gate_timeout"})
            return
        repo = PlatformRepository(db)
        try:
            result = repo.submit_attempt(attempt_id)
            result_queue.put(
                {
                    "worker": worker_id,
                    "ok": bool(result),
                    "idempotent_replay": bool(
                        result and result.get("idempotent_replay")
                    ),
                }
            )
        except Exception as exc:
            result_queue.put(
                {
                    "worker": worker_id,
                    "ok": False,
                    "error": exc.__class__.__name__,
                }
            )
    finally:
        db.close()


def _run_workers(
    target: Callable[..., None],
    worker_args: list[tuple[Any, ...]],
) -> list[dict]:
    context = multiprocessing.get_context("spawn")
    ready_queue = context.Queue()
    start_gate = context.Event()
    result_queue = context.Queue()
    processes = [
        context.Process(
            target=target,
            args=(index, *args, ready_queue, start_gate, result_queue),
        )
        for index, args in enumerate(worker_args)
    ]
    for process in processes:
        process.start()

    ready = []
    try:
        for _ in processes:
            ready.append(ready_queue.get(timeout=45))
    except queue.Empty as exc:
        for process in processes:
            if process.is_alive():
                process.terminate()
        raise RuntimeError("Concurrency workers did not become ready") from exc
    if not all(item.get("connected") for item in ready):
        start_gate.set()
        raise RuntimeError("At least one concurrency worker could not connect to SQL Server")

    start_gate.set()
    for process in processes:
        process.join(timeout=60)
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)
            raise RuntimeError("Concurrency worker exceeded its timeout")
        if process.exitcode not in {0, None}:
            raise RuntimeError(f"Concurrency worker exited with code {process.exitcode}")

    results = []
    try:
        for _ in processes:
            results.append(result_queue.get(timeout=15))
    except queue.Empty as exc:
        raise RuntimeError("Concurrency worker did not return a result") from exc
    return results


def main() -> int:
    worker_count = max(2, min(int(os.getenv("ATTEMPT_RACE_WORKERS", "4")), 8))
    marker = uuid.uuid4().hex
    db = DatabaseConnection()
    if not db.connect(max_retries=1):
        raise SystemExit("SQL Server connection failed")
    repo = PlatformRepository(db)
    tenant_id = ""
    instructor_id = ""
    student_id = ""
    exam_id = ""
    assignment_id = ""
    question_id = ""
    attempt_ids: list[str] = []

    def cleanup() -> None:
        if attempt_ids:
            placeholders = ",".join("?" for _ in attempt_ids)
            db.execute(
                f"DELETE FROM StudentResponses WHERE attempt_id IN ({placeholders})",
                tuple(attempt_ids),
            )
            db.execute(
                f"DELETE FROM ExamAttempts WHERE attempt_id IN ({placeholders})",
                tuple(attempt_ids),
            )
        if question_id:
            db.execute("DELETE FROM QuestionOptions WHERE question_id = ?", (question_id,))
            db.execute("DELETE FROM ExamQuestions WHERE question_id = ?", (question_id,))
        if assignment_id:
            db.execute(
                "DELETE FROM ExamAssignments WHERE assignment_id = ?",
                (assignment_id,),
            )
        if exam_id:
            db.execute("DELETE FROM Exams WHERE exam_id = ?", (exam_id,))
        for user_id in (student_id, instructor_id):
            if user_id:
                db.execute("DELETE FROM AuditLogs WHERE actor_user_id = ?", (user_id,))
                db.execute("DELETE FROM PasswordResetTokens WHERE user_id = ?", (user_id,))
                db.execute("DELETE FROM Users WHERE user_id = ?", (user_id,))
        if tenant_id:
            db.execute("DELETE FROM Tenants WHERE tenant_id = ?", (tenant_id,))

    try:
        indexes = db.query(
            """
            SELECT name
            FROM sys.indexes
            WHERE object_id = OBJECT_ID('ExamAttempts')
              AND name = 'UX_ExamAttempts_ActiveUser'
            """
        )
        if not indexes:
            raise RuntimeError("UX_ExamAttempts_ActiveUser is missing")

        tenant = repo.create_tenant(
            "Attempt Race Smoke",
            f"attempt-race-{marker}",
        )
        tenant_id = tenant["tenant_id"]
        ephemeral_hash = hash_password(f"Race-{secrets.token_urlsafe(18)}-Aa1")
        instructor = repo.create_user(
            f"race-instructor-{marker}@example.invalid",
            "Race Instructor",
            "instructor",
            ephemeral_hash,
            tenant_id,
        )
        instructor_id = instructor["user_id"]
        student = repo.create_user(
            f"race-student-{marker}@example.invalid",
            "Race Student",
            "student",
            ephemeral_hash,
            tenant_id,
        )
        student_id = student["user_id"]
        exam = repo.create_exam(
            {
                "title": "Attempt Race Exam",
                "status": "published",
                "duration_minutes": 30,
                "total_marks": 1,
            },
            instructor_id,
            tenant_id,
        )
        exam_id = exam["exam_id"]
        question = repo.upsert_question(
            exam_id,
            {
                "question_text": "Race safety question",
                "question_type": "mcq",
                "marks": 1,
                "options": [
                    {"option_text": "A", "is_correct": True, "sort_order": 0},
                    {"option_text": "B", "is_correct": False, "sort_order": 1},
                ],
            },
            tenant_id,
        )
        question_id = question["question_id"]
        assignment = repo.assign_exam(
            exam_id,
            student_id,
            instructor_id,
            tenant_id,
        )
        assignment_id = assignment["assignment_id"]

        start_args = [
            (exam_id, student_id, assignment_id, tenant_id)
            for _ in range(worker_count)
        ]
        start_results = _run_workers(_start_attempt_worker, start_args)
        winners = [result for result in start_results if result.get("ok")]
        rejected = [result for result in start_results if not result.get("ok")]
        rows = db.query(
            """
            SELECT attempt_id, status
            FROM ExamAttempts
            WHERE user_id = ? AND exam_id = ?
            """,
            (student_id, exam_id),
        )
        attempt_ids.extend(str(row["attempt_id"]) for row in rows)
        active_rows = [row for row in rows if row.get("status") == "in_progress"]
        start_safe = (
            len(winners) == 1
            and len(rejected) == worker_count - 1
            and len(rows) == 1
            and len(active_rows) == 1
        )
        if not start_safe:
            raise RuntimeError("Parallel start did not resolve to exactly one active attempt")

        winner_id = str(winners[0]["attempt_id"])
        submit_results = _run_workers(
            _submit_attempt_worker,
            [(winner_id,) for _ in range(worker_count)],
        )
        submit_successes = [result for result in submit_results if result.get("ok")]
        original_submissions = [
            result
            for result in submit_successes
            if not result.get("idempotent_replay")
        ]
        replayed_submissions = [
            result
            for result in submit_successes
            if result.get("idempotent_replay")
        ]
        final_rows = db.query(
            """
            SELECT status, submitted_at, score, max_score
            FROM ExamAttempts WHERE attempt_id = ?
            """,
            (winner_id,),
        )
        final = final_rows[0] if final_rows else {}
        submit_safe = (
            len(submit_successes) == worker_count
            and len(original_submissions) == 1
            and len(replayed_submissions) == worker_count - 1
            and final.get("status") == "submitted"
            and final.get("submitted_at") is not None
        )
        if not submit_safe:
            raise RuntimeError("Parallel submit did not resolve to one commit plus replays")

        cleanup()
        leftovers = db.query(
            """
            SELECT
                (SELECT COUNT(*) FROM ExamAttempts WHERE user_id = ?) AS attempt_rows,
                (SELECT COUNT(*) FROM Users WHERE user_id IN (?, ?)) AS user_rows,
                (SELECT COUNT(*) FROM Exams WHERE exam_id = ?) AS exam_rows
            """,
            (student_id, student_id, instructor_id, exam_id),
        )[0]
        cleanup_verified = all(int(leftovers.get(key) or 0) == 0 for key in leftovers)
        result = {
            "status": "passed" if cleanup_verified else "failed",
            "workers": worker_count,
            "active_attempt_winners": len(winners),
            "active_attempt_conflicts": len(rejected),
            "submission_commits": len(original_submissions),
            "submission_replays": len(replayed_submissions),
            "final_status": final.get("status"),
            "unique_active_attempt_index": True,
            "cleanup_verified": cleanup_verified,
            "credentials_retained": False,
        }
        print(json.dumps(result, indent=2, default=str))
        return 0 if cleanup_verified else 1
    finally:
        try:
            cleanup()
        finally:
            db.close()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
