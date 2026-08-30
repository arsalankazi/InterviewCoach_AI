"""
database/connection.py

Database connection manager supporting Flask-SQLAlchemy, Flask-Migrate,
and multi-dialect adapters for PostgreSQL (Neon) and SQLite.
"""

import os
import re
import sqlite3
from datetime import datetime
from flask import current_app, g
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy import func

db = SQLAlchemy()
migrate = Migrate()


# ---------------------------------------------------------------------------
# SQLAlchemy Declarative Models for Flask-Migrate / Alembic
# ---------------------------------------------------------------------------

class UserModel(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    resume_filename = db.Column(db.String(255), nullable=True)
    resume_uploaded_at = db.Column(db.DateTime, nullable=True)
    extracted_skills = db.Column(db.Text, nullable=True)
    onboarding_completed = db.Column(db.Integer, default=0, server_default='0', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, server_default=func.now())


class AdminModel(db.Model):
    __tablename__ = 'admins'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, server_default=func.now())


class InterviewSessionModel(db.Model):
    __tablename__ = 'interview_sessions'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    interviewer_gender = db.Column(db.String(10), nullable=False)
    interviewer_name = db.Column(db.String(100), nullable=False)
    job_role = db.Column(db.String(150), nullable=False)
    status = db.Column(db.String(20), default='setup', server_default='setup', nullable=False)
    session_type = db.Column(db.String(30), default='full_interview', server_default='full_interview', nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, server_default=func.now())


class InterviewMessageModel(db.Model):
    __tablename__ = 'interview_messages'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(db.Integer, db.ForeignKey('interview_sessions.id', ondelete='CASCADE'), nullable=False, index=True)
    sender = db.Column(db.String(10), nullable=False)
    message_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, server_default=func.now())


class InterviewReportModel(db.Model):
    __tablename__ = 'interview_reports'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(db.Integer, db.ForeignKey('interview_sessions.id', ondelete='CASCADE'), nullable=False, index=True)
    technical_score = db.Column(db.Integer, default=0, server_default='0', nullable=False)
    communication_score = db.Column(db.Integer, default=0, server_default='0', nullable=False)
    overall_score = db.Column(db.Integer, default=0, server_default='0', nullable=False)
    confidence_level = db.Column(db.String(50), default='Moderate', server_default='Moderate', nullable=False)
    strengths = db.Column(db.Text, default='[]', server_default="'[]'", nullable=False)
    weaknesses = db.Column(db.Text, default='[]', server_default="'[]'", nullable=False)
    suggestions = db.Column(db.Text, default='[]', server_default="'[]'", nullable=False)
    analysis_available = db.Column(db.Integer, default=1, server_default='1', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, server_default=func.now())


class QuestionFeedbackModel(db.Model):
    __tablename__ = 'question_feedback'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(db.Integer, db.ForeignKey('interview_sessions.id', ondelete='CASCADE'), nullable=False, index=True)
    question_text = db.Column(db.Text, nullable=False)
    student_answer = db.Column(db.Text, nullable=False)
    ideal_answer = db.Column(db.Text, nullable=False)
    feedback_text = db.Column(db.Text, nullable=False)
    topic = db.Column(db.String(150), nullable=False, index=True)
    score = db.Column(db.Integer, default=0, server_default='0', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, server_default=func.now())



# ---------------------------------------------------------------------------
# PostgreSQL Row & Cursor Compatibility Adapters
# ---------------------------------------------------------------------------

class PostgresRow:
    """
    A row wrapper mimicking sqlite3.Row for PostgreSQL results.
    Provides key access (row['name']), index access (row[0]), .keys(), and iteration.
    """
    def __init__(self, description, values):
        self._columns = [d[0] for d in description] if description else []
        self._col_map = {name: idx for idx, name in enumerate(self._columns)}
        self._values = tuple(values)

    def __getitem__(self, key):
        if isinstance(key, (int, slice)):
            return self._values[key]
        if isinstance(key, str):
            if key in self._col_map:
                return self._values[self._col_map[key]]
            raise KeyError(key)
        raise TypeError(f"Row indices must be integers or strings, not {type(key).__name__}")

    def get(self, key, default=None):
        if isinstance(key, str) and key in self._col_map:
            return self._values[self._col_map[key]]
        return default

    def keys(self):
        return list(self._columns)

    def values(self):
        return list(self._values)

    def items(self):
        return list(zip(self._columns, self._values))

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)

    def __contains__(self, key):
        return key in self._col_map

    def __repr__(self):
        return f"<PostgresRow {dict(self.items())}>"


class PostgresCursorWrapper:
    """
    Cursor wrapper adapting SQLite-style queries (? placeholders, lastrowid, etc.)
    to PostgreSQL via psycopg2.
    """
    def __init__(self, raw_cursor, raw_conn):
        self._cursor = raw_cursor
        self._conn = raw_conn
        self.lastrowid = None

    @property
    def description(self):
        return self._cursor.description

    @property
    def rowcount(self):
        return self._cursor.rowcount

    def _convert_sql(self, sql):
        """
        Translate SQLite-style SQL to PostgreSQL syntax:
        - Replaces ? with %s outside string literals
        - Translates COLLATE NOCASE to case-insensitive comparison
        """
        # Case insensitive comparison conversion
        sql = re.sub(
            r'(\w+)\s*=\s*\?\s*COLLATE\s+NOCASE',
            r'LOWER(\1) = LOWER(?)',
            sql,
            flags=re.IGNORECASE
        )
        # Replace ? with %s outside single-quoted string literals
        parts = re.split(r"('(?:''|[^'])*')", sql)
        for i in range(0, len(parts), 2):
            parts[i] = parts[i].replace('?', '%s')
        return ''.join(parts)

    def execute(self, sql, params=None):
        converted_sql = self._convert_sql(sql)
        self.lastrowid = None

        # Check if INSERT query without RETURNING clause
        is_insert = bool(re.match(r'^\s*INSERT\s+INTO\s+', sql, re.IGNORECASE))
        has_returning = 'RETURNING' in sql.upper()

        if is_insert and not has_returning:
            insert_sql_returning = converted_sql.rstrip().rstrip(';') + " RETURNING id;"
            try:
                if params is not None:
                    self._cursor.execute(insert_sql_returning, params)
                else:
                    self._cursor.execute(insert_sql_returning)
                res = self._cursor.fetchone()
                if res:
                    self.lastrowid = res[0]
                return self
            except Exception:
                # If RETURNING id is not applicable, rollback and execute standard statement
                self._conn.rollback()

        if params is not None:
            self._cursor.execute(converted_sql, params)
        else:
            self._cursor.execute(converted_sql)
        return self

    def executemany(self, sql, seq_of_parameters):
        converted_sql = self._convert_sql(sql)
        return self._cursor.executemany(converted_sql, seq_of_parameters)

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None:
            return None
        return PostgresRow(self._cursor.description, row)

    def fetchall(self):
        rows = self._cursor.fetchall()
        if not rows:
            return []
        desc = self._cursor.description
        return [PostgresRow(desc, r) for r in rows]

    def fetchmany(self, size=None):
        rows = self._cursor.fetchmany(size) if size else self._cursor.fetchmany()
        if not rows:
            return []
        desc = self._cursor.description
        return [PostgresRow(desc, r) for r in rows]

    def close(self):
        try:
            self._cursor.close()
        except Exception:
            pass


class PostgresConnectionWrapper:
    """
    Connection wrapper providing SQLite-compatible API over PostgreSQL raw connection.
    """
    def __init__(self, raw_conn):
        self._conn = raw_conn

    def cursor(self):
        return PostgresCursorWrapper(self._conn.cursor(), self._conn)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def executescript(self, script):
        with self._conn.cursor() as cur:
            cur.execute(script)
        self._conn.commit()

    def execute(self, sql, params=None):
        cur = self.cursor()
        cur.execute(sql, params)
        return cur

    def close(self):
        try:
            self._conn.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Database Management Functions
# ---------------------------------------------------------------------------

def get_db():
    """
    Establish and return a database connection for the current application context.
    Seamlessly adapts to PostgreSQL (Neon) or SQLite.
    The connection is cached in Flask's `g` object for the lifetime of the request.
    """
    if 'db_conn' in g:
        return g.db_conn

    uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
    is_testing = current_app.config.get('TESTING', False)
    db_path = current_app.config.get('DATABASE_PATH')

    # SQLite connection for testing or local SQLite config
    if is_testing or uri.startswith('sqlite:') or 'sqlite' in uri or (not uri and db_path):
        sqlite_file = db_path if db_path else (uri.replace('sqlite:///', '') if uri else ':memory:')
        conn = sqlite3.connect(sqlite_file)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        g.db_conn = conn
        return g.db_conn

    # PostgreSQL connection via SQLAlchemy raw_connection
    raw_conn = db.engine.raw_connection()
    g.db_conn = PostgresConnectionWrapper(raw_conn)
    return g.db_conn


def close_db(e=None):
    """
    Close the database connection at the end of the request context.
    Registered as a teardown handler.
    """
    conn = g.pop('db_conn', None)
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass


def init_app(app):
    """
    Register Flask-SQLAlchemy, Flask-Migrate, and teardown hooks with the Flask app.
    """
    db.init_app(app)
    migrate.init_app(app, db)
    app.teardown_appcontext(close_db)
