from pathlib import Path
from flask import current_app
from database.connection import get_db, db

SCHEMA_FILE = Path(__file__).resolve().parent / 'schema.sql'


def init_db(app=None):
    """
    Initialize database tables for PostgreSQL or SQLite.
    Creates all necessary schemas, tables, and indexes.
    """
    if app:
        with app.app_context():
            _initialize_database()
    else:
        _initialize_database()


def _initialize_database():
    """Create tables using SQLAlchemy or raw SQLite script depending on engine."""
    uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
    is_testing = current_app.config.get('TESTING', False)
    db_path = current_app.config.get('DATABASE_PATH')

    is_sqlite = is_testing or uri.startswith('sqlite:') or 'sqlite' in uri or (not uri and db_path)

    if is_sqlite:
        _execute_sqlite_schema()
        _run_sqlite_migrations()
    else:
        # PostgreSQL / SQLAlchemy
        db.create_all()
        _ensure_postgres_defaults()


def _ensure_postgres_defaults():
    """Ensure column defaults and nullability on PostgreSQL tables."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("ALTER TABLE users ALTER COLUMN onboarding_completed SET DEFAULT 0;")
        cursor.execute("ALTER TABLE users ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP;")
        cursor.execute("ALTER TABLE admins ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP;")
        cursor.execute("ALTER TABLE interview_sessions ALTER COLUMN status SET DEFAULT 'setup';")
        cursor.execute("ALTER TABLE interview_sessions ALTER COLUMN session_type SET DEFAULT 'full_interview';")
        cursor.execute("ALTER TABLE interview_sessions ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP;")
        cursor.execute("ALTER TABLE interview_messages ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP;")
        cursor.execute("ALTER TABLE interview_reports ALTER COLUMN technical_score SET DEFAULT 0;")
        cursor.execute("ALTER TABLE interview_reports ALTER COLUMN communication_score SET DEFAULT 0;")
        cursor.execute("ALTER TABLE interview_reports ALTER COLUMN overall_score SET DEFAULT 0;")
        cursor.execute("ALTER TABLE interview_reports ALTER COLUMN confidence_level SET DEFAULT 'Moderate';")
        cursor.execute("ALTER TABLE interview_reports ALTER COLUMN strengths SET DEFAULT '[]';")
        cursor.execute("ALTER TABLE interview_reports ALTER COLUMN weaknesses SET DEFAULT '[]';")
        cursor.execute("ALTER TABLE interview_reports ALTER COLUMN suggestions SET DEFAULT '[]';")
        cursor.execute("ALTER TABLE interview_reports ALTER COLUMN analysis_available SET DEFAULT 1;")
        cursor.execute("ALTER TABLE interview_reports ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP;")
        cursor.execute("ALTER TABLE question_feedback ALTER COLUMN score SET DEFAULT 0;")
        cursor.execute("ALTER TABLE question_feedback ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP;")
        conn.commit()
    except Exception:
        pass



def _execute_sqlite_schema():
    """Execute the schema SQL file against the current SQLite connection."""
    conn = get_db()
    with open(SCHEMA_FILE, mode='r', encoding='utf-8') as f:
        schema_sql = f.read()
    conn.executescript(schema_sql)
    conn.commit()


def _run_sqlite_migrations():
    """Safely apply column additions for existing SQLite database tables."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(users);")
    rows = cursor.fetchall()
    
    columns = [row['name'] if isinstance(row, dict) or hasattr(row, 'keys') else row[1] for row in rows]
    
    if 'resume_filename' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN resume_filename TEXT DEFAULT NULL;")
    if 'resume_uploaded_at' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN resume_uploaded_at TIMESTAMP DEFAULT NULL;")
    if 'extracted_skills' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN extracted_skills TEXT DEFAULT NULL;")
    if 'onboarding_completed' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN onboarding_completed INTEGER NOT NULL DEFAULT 0;")

    # Ensure interview_sessions table exists
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

    # Ensure interview_messages table exists
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

    # Ensure interview_reports table exists
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

    # Ensure question_feedback table exists
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

    conn.commit()
