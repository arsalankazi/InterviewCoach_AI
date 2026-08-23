"""
models/interview_message.py

InterviewMessage model for tracking multi-turn conversation messages
between the AI interviewer and the student for a given interview session.
"""

from database.connection import get_db


class InterviewMessage:
    """
    Represents a single message turn in an interview session.
    Tracks sender ('ai' or 'student'), message text, and timestamp.
    """

    def __init__(
        self,
        id=None,
        session_id=None,
        sender=None,
        message_text=None,
        created_at=None
    ):
        self.id = id
        self.session_id = session_id
        self.sender = sender
        self.message_text = message_text
        self.created_at = created_at

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    @classmethod
    def create(cls, session_id: int, sender: str, message_text: str):
        """
        Insert a new message turn into the interview_messages table.
        Returns the created InterviewMessage instance.

        Args:
            session_id:   FK reference to the interview_sessions table.
            sender:       'ai' or 'student'.
            message_text: The full text content of the message turn.
        """
        if not session_id or sender not in ('ai', 'student') or not message_text:
            raise ValueError("session_id, valid sender ('ai'|'student'), and message_text are required.")

        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            """
            INSERT INTO interview_messages (session_id, sender, message_text)
            VALUES (?, ?, ?);
            """,
            (session_id, sender, message_text.strip())
        )
        db.commit()
        message_id = cursor.lastrowid
        return cls.get_by_id(message_id)

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    @classmethod
    def get_by_id(cls, message_id: int):
        """Retrieve a single message by its primary key ID."""
        if not message_id:
            return None
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "SELECT * FROM interview_messages WHERE id = ?;",
            (message_id,)
        )
        row = cursor.fetchone()
        return cls._from_row(row) if row else None

    @classmethod
    def get_by_session(cls, session_id: int) -> list:
        """
        Retrieve all messages for a given interview session in chronological order.
        """
        if not session_id:
            return []
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            """
            SELECT * FROM interview_messages
            WHERE session_id = ?
            ORDER BY created_at ASC, id ASC;
            """,
            (session_id,)
        )
        rows = cursor.fetchall()
        return [cls._from_row(row) for row in rows]

    @classmethod
    def get_count_by_session(cls, session_id: int) -> int:
        """Return the count of messages stored for a given session."""
        if not session_id:
            return 0
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM interview_messages WHERE session_id = ?;",
            (session_id,)
        )
        row = cursor.fetchone()
        return row[0] if row else 0

    # ------------------------------------------------------------------
    # Internal helpers & Serialization
    # ------------------------------------------------------------------

    @classmethod
    def _from_row(cls, row):
        """Construct an InterviewMessage instance from a SQLite Row."""
        return cls(
            id=row['id'],
            session_id=row['session_id'],
            sender=row['sender'],
            message_text=row['message_text'],
            created_at=row['created_at']
        )

    def to_dict(self):
        """Serialize the message to a dictionary for JSON API responses."""
        return {
            'id': self.id,
            'session_id': self.session_id,
            'sender': self.sender,
            'message_text': self.message_text,
            'created_at': str(self.created_at) if self.created_at else None
        }
