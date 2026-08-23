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

    db.commit()
