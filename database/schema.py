from pathlib import Path
from flask import current_app
from database.connection import get_db

SCHEMA_FILE = Path(__file__).resolve().parent / 'schema.sql'


def init_db(app=None):
    """
    Initialize SQLite database tables using the schema.sql definition.
    """
    if app:
        with app.app_context():
            _execute_schema()
    else:
        _execute_schema()


def _execute_schema():
    """Execute the schema SQL file against the current database connection."""
    db = get_db()
    with open(SCHEMA_FILE, mode='r', encoding='utf-8') as f:
        schema_sql = f.read()
    db.executescript(schema_sql)
    db.commit()
