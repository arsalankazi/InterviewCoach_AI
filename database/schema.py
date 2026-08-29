from pathlib import Path
from flask import current_app
from database.connection import get_db

SCHEMA_FILE = Path(__file__).resolve().parent / 'schema.sql'


def init_db(app=None):
    """
    Initialize SQLite database tables using the schema.sql definition
    and apply any necessary schema column migrations safely.
    """
    if app:
        with app.app_context():
            _execute_schema()
            _run_migrations()
    else:
        _execute_schema()
        _run_migrations()


def _execute_schema():
    """Execute the schema SQL file against the current database connection."""
    db = get_db()
    with open(SCHEMA_FILE, mode='r', encoding='utf-8') as f:
        schema_sql = f.read()
    db.executescript(schema_sql)
    db.commit()


def _run_migrations():
    """Safely apply column additions for existing database tables."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute("PRAGMA table_info(users);")
    rows = cursor.fetchall()
    
    # Extract column names (supporting sqlite3.Row and tuples)
    columns = [row['name'] if isinstance(row, dict) or hasattr(row, 'keys') else row[1] for row in rows]
    
    if 'resume_filename' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN resume_filename TEXT DEFAULT NULL;")
    if 'resume_uploaded_at' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN resume_uploaded_at TIMESTAMP DEFAULT NULL;")
    if 'extracted_skills' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN extracted_skills TEXT DEFAULT NULL;")
    if 'onboarding_completed' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN onboarding_completed INTEGER NOT NULL DEFAULT 0;")

    # ── Create interview_sessions table if it doesn't exist yet ───────────
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS interview_sessions (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id            INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            interviewer_gender TEXT    NOT NULL CHECK(interviewer_gender IN ('male', 'female')),
            interviewer_name   TEXT    NOT NULL,
            job_role           TEXT    NOT NULL,
            status             TEXT    NOT NULL DEFAULT 'setup'
                                       CHECK(status IN ('setup', 'in_progress', 'completed')),
            session_type       TEXT    NOT NULL DEFAULT 'full_interview'
                                       CHECK(session_type IN ('full_interview', 'practice')),
            created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_sessions_user ON interview_sessions(user_id);"
    )

    # ── Migrate session_type column onto existing interview_sessions table ──
    cursor.execute("PRAGMA table_info(interview_sessions);")
    session_cols = [
        row['name'] if isinstance(row, dict) or hasattr(row, 'keys') else row[1]
        for row in cursor.fetchall()
    ]
    if 'session_type' not in session_cols:
        cursor.execute(
            "ALTER TABLE interview_sessions "
            "ADD COLUMN session_type TEXT NOT NULL DEFAULT 'full_interview';"
        )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_sessions_type ON interview_sessions(session_type);"
    )

    # ── Create interview_messages table if it doesn't exist yet ───────────
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS interview_messages (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id   INTEGER NOT NULL REFERENCES interview_sessions(id) ON DELETE CASCADE,
            sender       TEXT    NOT NULL CHECK(sender IN ('ai', 'student')),
            message_text TEXT    NOT NULL,
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_messages_session ON interview_messages(session_id);"
    )

    # ── Create interview_reports table if it doesn't exist yet ────────────
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS interview_reports (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id          INTEGER NOT NULL REFERENCES interview_sessions(id) ON DELETE CASCADE,
            technical_score     INTEGER NOT NULL DEFAULT 0,
            communication_score INTEGER NOT NULL DEFAULT 0,
            overall_score       INTEGER NOT NULL DEFAULT 0,
            confidence_level    TEXT    NOT NULL DEFAULT 'Moderate',
            strengths           TEXT    NOT NULL DEFAULT '[]',
            weaknesses          TEXT    NOT NULL DEFAULT '[]',
            suggestions         TEXT    NOT NULL DEFAULT '[]',
            analysis_available  INTEGER NOT NULL DEFAULT 1,
            created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_reports_session ON interview_reports(session_id);"
    )

    # ── Create question_feedback table if it doesn't exist yet ───────────
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS question_feedback (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id     INTEGER NOT NULL REFERENCES interview_sessions(id) ON DELETE CASCADE,
            question_text  TEXT    NOT NULL,
            student_answer TEXT    NOT NULL,
            ideal_answer   TEXT    NOT NULL,
            feedback_text  TEXT    NOT NULL,
            topic          TEXT    NOT NULL,
            score          INTEGER NOT NULL DEFAULT 0,
            created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_qfeedback_session ON question_feedback(session_id);"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_qfeedback_topic ON question_feedback(topic);"
    )

    db.commit()
