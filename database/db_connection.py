from __future__ import annotations

import logging
import threading
import time
from typing import Any

from config.settings import DB_DRIVER, DB_ENCRYPT, DB_NAME, DB_PASSWORD, DB_SERVER, DB_TRUSTED, DB_USER

logger = logging.getLogger("DatabaseConnection")


class DatabaseConnection:
    def __init__(self):
        self.connection = None
        self.is_active = False
        self._lock = threading.RLock()

    def _connection_string(self) -> str:
        auth = "Trusted_Connection=yes;" if DB_TRUSTED else f"UID={DB_USER};PWD={DB_PASSWORD};"
        return (
            f"DRIVER={{{DB_DRIVER}}};"
            f"SERVER={DB_SERVER};"
            f"DATABASE={DB_NAME};"
            f"{auth}"
            f"Encrypt={'yes' if DB_ENCRYPT else 'no'};"
            "TrustServerCertificate=yes;"
        )

    def connect(self, max_retries: int = 3, delay_sec: float = 1.0) -> bool:
        try:
            import pyodbc
        except Exception as exc:
            logger.warning("pyodbc is unavailable: %s", exc)
            self.is_active = False
            return False

        for attempt in range(1, max_retries + 1):
            try:
                with self._lock:
                    self.connection = pyodbc.connect(self._connection_string(), timeout=5, autocommit=False)
                    self.is_active = True
                    self.initialize_schema()
                    return True
            except Exception as exc:
                logger.warning("DB connection attempt %s/%s failed: %s", attempt, max_retries, exc)
                self.is_active = False
                if attempt < max_retries:
                    time.sleep(delay_sec)
        return False

    def initialize_schema(self) -> None:
        self.execute(
            """
            IF OBJECT_ID('Tenants', 'U') IS NULL
            CREATE TABLE Tenants (
                tenant_id NVARCHAR(64) NOT NULL PRIMARY KEY,
                name NVARCHAR(255) NOT NULL,
                slug NVARCHAR(128) NOT NULL UNIQUE,
                status NVARCHAR(32) NOT NULL DEFAULT 'active',
                plan_name NVARCHAR(64) NOT NULL DEFAULT 'enterprise',
                settings_json NVARCHAR(MAX) NULL,
                created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
                updated_at DATETIME2 NULL
            )
            """
        )
        self.execute(
            """
            IF NOT EXISTS (SELECT 1 FROM Tenants WHERE tenant_id = 'tenant_default')
            INSERT INTO Tenants (tenant_id, name, slug, status, plan_name, settings_json)
            VALUES ('tenant_default', 'Default Institution', 'default', 'active', 'enterprise', '{}')
            """
        )
        self.execute(
            """
            IF OBJECT_ID('Users', 'U') IS NULL
            CREATE TABLE Users (
                user_id NVARCHAR(64) NOT NULL PRIMARY KEY,
                tenant_id NVARCHAR(64) NULL,
                email NVARCHAR(255) NOT NULL UNIQUE,
                full_name NVARCHAR(255) NOT NULL,
                role NVARCHAR(32) NOT NULL,
                password_hash NVARCHAR(MAX) NOT NULL,
                is_active BIT NOT NULL DEFAULT 1,
                created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
                updated_at DATETIME2 NULL
            )
            """
        )
        self.execute(
            """
            IF OBJECT_ID('PasswordResetTokens', 'U') IS NULL
            CREATE TABLE PasswordResetTokens (
                token_id NVARCHAR(64) NOT NULL PRIMARY KEY,
                user_id NVARCHAR(64) NOT NULL,
                token_hash NVARCHAR(128) NOT NULL UNIQUE,
                expires_at DATETIME2 NOT NULL,
                used_at DATETIME2 NULL,
                created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
            )
            """
        )
        self.execute(
            """
            IF OBJECT_ID('Exams', 'U') IS NULL
            CREATE TABLE Exams (
                exam_id NVARCHAR(64) NOT NULL PRIMARY KEY,
                tenant_id NVARCHAR(64) NULL,
                exam_code NVARCHAR(64) NULL UNIQUE,
                title NVARCHAR(255) NOT NULL,
                description NVARCHAR(MAX) NULL,
                semester NVARCHAR(128) NULL,
                subject NVARCHAR(255) NULL,
                department NVARCHAR(255) NULL,
                total_marks INT NOT NULL DEFAULT 0,
                duration_minutes INT NOT NULL,
                start_time DATETIME2 NULL,
                end_time DATETIME2 NULL,
                status NVARCHAR(32) NOT NULL DEFAULT 'draft',
                rules_json NVARCHAR(MAX) NULL,
                created_by NVARCHAR(64) NULL,
                created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
                updated_at DATETIME2 NULL
            )
            """
        )
        for column, definition in (
            ("exam_code", "NVARCHAR(64) NULL"),
            ("semester", "NVARCHAR(128) NULL"),
            ("subject", "NVARCHAR(255) NULL"),
            ("department", "NVARCHAR(255) NULL"),
            ("total_marks", "INT NOT NULL DEFAULT 0"),
        ):
            self.execute(
                f"""
                IF COL_LENGTH('Exams', '{column}') IS NULL
                ALTER TABLE Exams ADD {column} {definition}
                """
            )
        self.execute(
            """
            IF OBJECT_ID('ExamAssignments', 'U') IS NULL
            CREATE TABLE ExamAssignments (
                assignment_id NVARCHAR(64) NOT NULL PRIMARY KEY,
                exam_id NVARCHAR(64) NOT NULL,
                student_user_id NVARCHAR(64) NOT NULL,
                assigned_by NVARCHAR(64) NULL,
                assigned_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
                status NVARCHAR(32) NOT NULL DEFAULT 'assigned'
            )
            """
        )
        self.execute(
            """
            IF OBJECT_ID('ExamQuestions', 'U') IS NULL
            CREATE TABLE ExamQuestions (
                question_id NVARCHAR(64) NOT NULL PRIMARY KEY,
                tenant_id NVARCHAR(64) NULL,
                exam_id NVARCHAR(64) NOT NULL,
                question_text NVARCHAR(MAX) NOT NULL,
                question_type NVARCHAR(32) NOT NULL DEFAULT 'mcq',
                marks INT NOT NULL DEFAULT 1,
                sort_order INT NOT NULL DEFAULT 0,
                status NVARCHAR(32) NOT NULL DEFAULT 'active',
                created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
                updated_at DATETIME2 NULL
            )
            """
        )
        self.execute(
            """
            IF OBJECT_ID('QuestionOptions', 'U') IS NULL
            CREATE TABLE QuestionOptions (
                option_id NVARCHAR(64) NOT NULL PRIMARY KEY,
                tenant_id NVARCHAR(64) NULL,
                question_id NVARCHAR(64) NOT NULL,
                option_text NVARCHAR(MAX) NOT NULL,
                is_correct BIT NOT NULL DEFAULT 0,
                sort_order INT NOT NULL DEFAULT 0,
                created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
                updated_at DATETIME2 NULL
            )
            """
        )
        self.execute(
            """
            IF OBJECT_ID('ExamAttempts', 'U') IS NULL
            CREATE TABLE ExamAttempts (
                attempt_id NVARCHAR(64) NOT NULL PRIMARY KEY,
                tenant_id NVARCHAR(64) NULL,
                exam_id NVARCHAR(64) NOT NULL,
                assignment_id NVARCHAR(64) NULL,
                session_id NVARCHAR(128) NULL,
                user_id NVARCHAR(64) NOT NULL,
                roll_number NVARCHAR(128) NOT NULL,
                status NVARCHAR(32) NOT NULL DEFAULT 'in_progress',
                started_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
                submitted_at DATETIME2 NULL,
                score INT NOT NULL DEFAULT 0,
                max_score INT NOT NULL DEFAULT 0,
                created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
                updated_at DATETIME2 NULL
            )
            """
        )
        self.execute(
            """
            IF OBJECT_ID('StudentResponses', 'U') IS NULL
            CREATE TABLE StudentResponses (
                response_id NVARCHAR(64) NOT NULL PRIMARY KEY,
                tenant_id NVARCHAR(64) NULL,
                attempt_id NVARCHAR(64) NOT NULL,
                question_id NVARCHAR(64) NOT NULL,
                selected_option_id NVARCHAR(64) NULL,
                response_text NVARCHAR(MAX) NULL,
                is_correct BIT NULL,
                awarded_marks INT NOT NULL DEFAULT 0,
                answered_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
                updated_at DATETIME2 NULL
            )
            """
        )
        self.execute(
            """
            IF OBJECT_ID('Sessions', 'U') IS NULL
            CREATE TABLE Sessions (
                session_id NVARCHAR(128) NOT NULL PRIMARY KEY,
                user_id NVARCHAR(64) NULL,
                exam_id NVARCHAR(64) NULL,
                student_id NVARCHAR(128) NULL,
                student_name NVARCHAR(255) NULL,
                roll_number NVARCHAR(128) NULL,
                exam_code NVARCHAR(128) NULL,
                start_time DATETIME2 NULL,
                end_time DATETIME2 NULL,
                status NVARCHAR(50) NULL,
                final_score INT NULL,
                review_mark NVARCHAR(128) NULL,
                instructor_notes NVARCHAR(MAX) NULL
            )
            """
        )
        for column, definition in (
            ("user_id", "NVARCHAR(64) NULL"),
            ("exam_id", "NVARCHAR(64) NULL"),
            ("roll_number", "NVARCHAR(128) NULL"),
        ):
            self.execute(
                f"""
                IF COL_LENGTH('Sessions', '{column}') IS NULL
                ALTER TABLE Sessions ADD {column} {definition}
                """
            )
        self.execute(
            """
            IF OBJECT_ID('Events', 'U') IS NULL
            CREATE TABLE Events (
                event_id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
                session_id NVARCHAR(128) NOT NULL,
                student_id NVARCHAR(128) NULL,
                event_type NVARCHAR(255) NOT NULL,
                event_time DATETIME2 NOT NULL,
                risk_points INT NOT NULL DEFAULT 0,
                confidence FLOAT NULL,
                model_name NVARCHAR(128) NULL,
                detection_class NVARCHAR(128) NULL,
                bounding_box_json NVARCHAR(MAX) NULL,
                evidence_id NVARCHAR(64) NULL,
                ingest_id NVARCHAR(64) NULL,
                notes NVARCHAR(MAX) NULL
            )
            """
        )
        for column, definition in (
            ("confidence", "FLOAT NULL"),
            ("model_name", "NVARCHAR(128) NULL"),
            ("detection_class", "NVARCHAR(128) NULL"),
            ("bounding_box_json", "NVARCHAR(MAX) NULL"),
            ("evidence_id", "NVARCHAR(64) NULL"),
            ("ingest_id", "NVARCHAR(64) NULL"),
        ):
            self.execute(
                f"""
                IF COL_LENGTH('Events', '{column}') IS NULL
                ALTER TABLE Events ADD {column} {definition}
                """
            )
        self.execute(
            """
            IF COL_LENGTH('Events', 'session_id') < 256
            BEGIN
                IF EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Events_SessionTime' AND object_id = OBJECT_ID('Events'))
                    DROP INDEX IX_Events_SessionTime ON Events;
                ALTER TABLE Events ALTER COLUMN session_id NVARCHAR(128) NOT NULL;
            END
            """
        )
        self.execute(
            """
            IF OBJECT_ID('BrowserActivity', 'U') IS NULL
            CREATE TABLE BrowserActivity (
                activity_id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
                tenant_id NVARCHAR(64) NULL,
                session_id NVARCHAR(128) NOT NULL,
                activity_type NVARCHAR(64) NOT NULL,
                url NVARCHAR(2048) NULL,
                title NVARCHAR(1024) NULL,
                category NVARCHAR(128) NULL,
                risk_level NVARCHAR(16) NOT NULL DEFAULT 'low',
                risk_points INT NOT NULL DEFAULT 0,
                source NVARCHAR(64) NULL,
                ingest_id NVARCHAR(64) NULL,
                event_time DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
            )
            """
        )
        self.execute(
            """
            IF COL_LENGTH('BrowserActivity', 'ingest_id') IS NULL
            ALTER TABLE BrowserActivity ADD ingest_id NVARCHAR(64) NULL
            """
        )
        self.execute(
            """
            IF OBJECT_ID('Evidence', 'U') IS NULL
            CREATE TABLE Evidence (
                evidence_id NVARCHAR(64) NOT NULL PRIMARY KEY,
                session_id NVARCHAR(128) NOT NULL,
                user_id NVARCHAR(64) NULL,
                evidence_type NVARCHAR(64) NOT NULL,
                label NVARCHAR(255) NULL,
                filepath NVARCHAR(MAX) NOT NULL,
                confidence FLOAT NULL,
                model_name NVARCHAR(128) NULL,
                detection_class NVARCHAR(128) NULL,
                bounding_box_json NVARCHAR(MAX) NULL,
                created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
            )
            """
        )
        for column, definition in (
            ("confidence", "FLOAT NULL"),
            ("model_name", "NVARCHAR(128) NULL"),
            ("detection_class", "NVARCHAR(128) NULL"),
            ("bounding_box_json", "NVARCHAR(MAX) NULL"),
        ):
            self.execute(
                f"""
                IF COL_LENGTH('Evidence', '{column}') IS NULL
                ALTER TABLE Evidence ADD {column} {definition}
                """
            )
        self.execute(
            """
            IF OBJECT_ID('Reports', 'U') IS NULL
            CREATE TABLE Reports (
                report_id NVARCHAR(64) NOT NULL PRIMARY KEY,
                session_id NVARCHAR(128) NOT NULL,
                pdf_path NVARCHAR(MAX) NOT NULL,
                generated_by NVARCHAR(64) NULL,
                generated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
            )
            """
        )
        self.execute(
            """
            IF OBJECT_ID('AppSettings', 'U') IS NULL
            CREATE TABLE AppSettings (
                tenant_id NVARCHAR(64) NULL,
                setting_key NVARCHAR(128) NOT NULL PRIMARY KEY,
                setting_value NVARCHAR(MAX) NOT NULL,
                updated_by NVARCHAR(64) NULL,
                updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
            )
            """
        )
        self.execute(
            """
            IF OBJECT_ID('AuditLogs', 'U') IS NULL
            CREATE TABLE AuditLogs (
                audit_id NVARCHAR(64) NOT NULL PRIMARY KEY,
                tenant_id NVARCHAR(64) NULL,
                actor_user_id NVARCHAR(64) NULL,
                actor_email NVARCHAR(255) NULL,
                actor_role NVARCHAR(32) NULL,
                action NVARCHAR(128) NOT NULL,
                resource_type NVARCHAR(64) NULL,
                resource_id NVARCHAR(128) NULL,
                ip_address NVARCHAR(64) NULL,
                user_agent NVARCHAR(512) NULL,
                details_json NVARCHAR(MAX) NULL,
                created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
            )
            """
        )
        for table in ("Users", "Exams", "ExamAssignments", "ExamQuestions", "QuestionOptions", "ExamAttempts", "StudentResponses", "Sessions", "Events", "BrowserActivity", "Evidence", "Reports", "AppSettings"):
            self.execute(
                f"""
                IF COL_LENGTH('{table}', 'tenant_id') IS NULL
                ALTER TABLE {table} ADD tenant_id NVARCHAR(64) NULL
                """
            )
            self.execute(f"UPDATE {table} SET tenant_id = 'tenant_default' WHERE tenant_id IS NULL")
        for name, sql in {
            "IX_Tenants_Status": "CREATE INDEX IX_Tenants_Status ON Tenants(status, slug)",
            "IX_Users_TenantRole": "CREATE INDEX IX_Users_TenantRole ON Users(tenant_id, role)",
            "IX_PasswordResetTokens_User": "CREATE INDEX IX_PasswordResetTokens_User ON PasswordResetTokens(user_id, expires_at)",
            "IX_Exams_Tenant": "CREATE INDEX IX_Exams_Tenant ON Exams(tenant_id, status, created_at)",
            "IX_Exams_Code": "CREATE INDEX IX_Exams_Code ON Exams(tenant_id, exam_code)",
            "IX_ExamAssignments_Student": "CREATE INDEX IX_ExamAssignments_Student ON ExamAssignments(tenant_id, student_user_id, exam_id)",
            "IX_ExamQuestions_Exam": "CREATE INDEX IX_ExamQuestions_Exam ON ExamQuestions(tenant_id, exam_id, sort_order)",
            "IX_QuestionOptions_Question": "CREATE INDEX IX_QuestionOptions_Question ON QuestionOptions(tenant_id, question_id, sort_order)",
            "IX_ExamAttempts_UserExam": "CREATE INDEX IX_ExamAttempts_UserExam ON ExamAttempts(tenant_id, user_id, exam_id, status)",
            "IX_StudentResponses_Attempt": "CREATE INDEX IX_StudentResponses_Attempt ON StudentResponses(tenant_id, attempt_id, question_id)",
            "IX_Sessions_UserExam": "CREATE INDEX IX_Sessions_UserExam ON Sessions(tenant_id, user_id, exam_id)",
            "IX_Events_SessionTime": "CREATE INDEX IX_Events_SessionTime ON Events(tenant_id, session_id, event_time)",
            "UX_Events_IngestId": "CREATE UNIQUE INDEX UX_Events_IngestId ON Events(ingest_id) WHERE ingest_id IS NOT NULL",
            "IX_BrowserActivity_SessionTime": "CREATE INDEX IX_BrowserActivity_SessionTime ON BrowserActivity(tenant_id, session_id, event_time)",
            "UX_BrowserActivity_IngestId": "CREATE UNIQUE INDEX UX_BrowserActivity_IngestId ON BrowserActivity(ingest_id) WHERE ingest_id IS NOT NULL",
            "IX_Evidence_Session": "CREATE INDEX IX_Evidence_Session ON Evidence(tenant_id, session_id, created_at)",
            "IX_AuditLogs_TenantTime": "CREATE INDEX IX_AuditLogs_TenantTime ON AuditLogs(tenant_id, created_at DESC)",
            "IX_AuditLogs_ActorTime": "CREATE INDEX IX_AuditLogs_ActorTime ON AuditLogs(actor_user_id, created_at DESC)",
        }.items():
            self.execute(
                f"""
                IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = '{name}')
                {sql}
                """
            )

    def query(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict]:
        if not self.connection:
            return []
        with self._lock:
            cursor = self.connection.cursor()
            try:
                cursor.execute(sql, params)
                columns = [column[0] for column in cursor.description or []]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
            finally:
                cursor.close()

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> int:
        if not self.connection:
            return 0
        with self._lock:
            cursor = self.connection.cursor()
            try:
                cursor.execute(sql, params)
                try:
                    count = cursor.rowcount
                except Exception:
                    count = 0
                while cursor.nextset():
                    pass
                self.connection.commit()
                return count if count is not None else 0
            except Exception:
                self.connection.rollback()
                raise
            finally:
                cursor.close()

    def close(self) -> None:
        if self.connection:
            self.connection.close()
        self.connection = None
        self.is_active = False
