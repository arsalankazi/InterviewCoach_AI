"""
models/interview_session.py

InterviewSession model for managing student mock-interview session records.
Handles creation, retrieval, and serialization of interview_sessions rows.
"""

from database.connection import get_db


class InterviewSession:
    """
    Represents a single student mock-interview session.
    Tracks the chosen interviewer persona, target job role, and session lifecycle status.
    """

    def __init__(
        self,
        id=None,
        user_id=None,
        interviewer_gender=None,
        interviewer_name=None,
        job_role=None,
        status='setup',
        created_at=None
    ):
        self.id = id
        self.user_id = user_id
        self.interviewer_gender = interviewer_gender
        self.interviewer_name = interviewer_name
        self.job_role = job_role
        self.status = status
        self.created_at = created_at

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    @classmethod
    def create(cls, user_id: int, interviewer_gender: str, interviewer_name: str, job_role: str):
        """
        Insert a new interview session row with status='setup'.
        Returns the created InterviewSession instance.

        Args:
            user_id:            FK reference to the users table.
            interviewer_gender: 'male' or 'female'.
            interviewer_name:   Custom name given by the student.
            job_role:           Target job role for this session.
        """
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            """
            INSERT INTO interview_sessions
                (user_id, interviewer_gender, interviewer_name, job_role, status)
            VALUES (?, ?, ?, ?, 'setup');
            """,
            (user_id, interviewer_gender, interviewer_name.strip(), job_role.strip())
        )
        db.commit()
        session_id = cursor.lastrowid
        return cls.get_by_id(session_id)

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    @classmethod
    def get_by_id(cls, session_id):
        """Retrieve a single interview session by its primary key."""
        if not session_id:
            return None
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "SELECT * FROM interview_sessions WHERE id = ?;",
            (session_id,)
        )
        row = cursor.fetchone()
        return cls._from_row(row) if row else None

    @classmethod
    def get_by_user(cls, user_id):
        """
        Retrieve all interview sessions for a given user,
        ordered by creation date descending (most recent first).
        """
        if not user_id:
            return []
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            """
            SELECT * FROM interview_sessions
            WHERE user_id = ?
            ORDER BY created_at DESC, id DESC;
            """,
            (user_id,)
        )
        rows = cursor.fetchall()
        return [cls._from_row(row) for row in rows]

    @classmethod
    def get_latest_by_user(cls, user_id):
        """
        Return the most recently created interview session for a user,
        or None if the user has no sessions.
        """
        if not user_id:
            return None
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            """
            SELECT * FROM interview_sessions
            WHERE user_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 1;
            """,
            (user_id,)
        )
        row = cursor.fetchone()
        return cls._from_row(row) if row else None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @classmethod
    def _from_row(cls, row):
        """Construct an InterviewSession instance from a SQLite Row."""
        return cls(
            id=row['id'],
            user_id=row['user_id'],
            interviewer_gender=row['interviewer_gender'],
            interviewer_name=row['interviewer_name'],
            job_role=row['job_role'],
            status=row['status'],
            created_at=row['created_at']
        )

    def to_dict(self):
        """Serialize the session to a plain dictionary."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'interviewer_gender': self.interviewer_gender,
            'interviewer_name': self.interviewer_name,
            'job_role': self.job_role,
            'status': self.status,
            'created_at': str(self.created_at) if self.created_at else None
        }
