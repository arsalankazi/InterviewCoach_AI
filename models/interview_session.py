"""
models/interview_session.py

InterviewSession model for managing student mock-interview session records.
Handles creation, retrieval, and serialization of interview_sessions rows.

session_type field:
    'full_interview' — standard 4-stage AI mock interview (default)
    'practice'       — focused single-topic quick practice session
"""

from database.connection import get_db
from utils.helpers import safe_format_datetime


class InterviewSession:
    """
    Represents a single student mock-interview or quick-practice session.
    Tracks the chosen interviewer persona, target job role / practice topic,
    session lifecycle status, and session type.
    """

    def __init__(
        self,
        id=None,
        user_id=None,
        interviewer_gender=None,
        interviewer_name=None,
        job_role=None,
        status='setup',
        session_type='full_interview',
        interview_type='mixed',
        total_questions=8,
        difficulty_level='medium',
        avatar_mode='general',
        faculty_avatar=None,
        created_at=None
    ):
        self.id = id
        self.user_id = user_id
        self.interviewer_gender = interviewer_gender
        self.interviewer_name = interviewer_name
        self.job_role = job_role
        self.status = status
        self.session_type = session_type
        self.interview_type = interview_type
        self.total_questions = total_questions
        self.difficulty_level = difficulty_level
        self.avatar_mode = avatar_mode
        self.faculty_avatar = faculty_avatar
        self.created_at = created_at

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    @classmethod
    def create(cls, user_id: int, interviewer_gender: str, interviewer_name: str, job_role: str,
                session_type: str = 'full_interview', interview_type: str = 'mixed',
                total_questions: int = 8, difficulty_level: str = 'medium',
                avatar_mode: str = 'general', faculty_avatar: str = None):
        """
        Insert a new interview session row with status='setup'.
        Returns the created InterviewSession instance.

        Args:
            user_id:            FK reference to the users table.
            interviewer_gender: 'male' or 'female'.
            interviewer_name:   Custom name given by the student.
            job_role:           Target job role for this session.
            session_type:       'full_interview' (default) or 'practice'.
            interview_type:     'technical', 'general', or 'mixed' (default).
            total_questions:    Number of questions for this session (default 8, min 3, max 20).
            difficulty_level:   'easy', 'medium' (default), 'hard', or 'adaptive'.
            avatar_mode:        'general' (default) or 'faculty'.
            faculty_avatar:     'director' or 'hod' (if avatar_mode is 'faculty', else None).
        """
        if session_type not in ('full_interview', 'practice'):
            raise ValueError(f"Invalid session_type '{session_type}'.")
        if interview_type not in ('technical', 'general', 'mixed'):
            raise ValueError(f"Invalid interview_type '{interview_type}'.")
        if not (3 <= int(total_questions) <= 20):
            raise ValueError("total_questions must be an integer between 3 and 20.")
        if difficulty_level not in ('easy', 'medium', 'hard', 'adaptive'):
            difficulty_level = 'medium'
        if avatar_mode not in ('general', 'faculty'):
            avatar_mode = 'general'
        if avatar_mode == 'faculty':
            if faculty_avatar not in ('director', 'hod'):
                raise ValueError(f"Invalid faculty_avatar '{faculty_avatar}'.")
        else:
            faculty_avatar = None

        total_questions = int(total_questions)
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            """
            INSERT INTO interview_sessions
                (user_id, interviewer_gender, interviewer_name, job_role, status, session_type, interview_type, total_questions, difficulty_level, avatar_mode, faculty_avatar)
            VALUES (?, ?, ?, ?, 'setup', ?, ?, ?, ?, ?, ?);
            """,
            (user_id, interviewer_gender, interviewer_name.strip(), job_role.strip(), session_type, interview_type, total_questions, difficulty_level, avatar_mode, faculty_avatar)
        )
        db.commit()
        session_id = cursor.lastrowid
        return cls.get_by_id(session_id)

    @classmethod
    def create_practice(cls, user_id: int, topic: str, difficulty_level: str = 'medium', total_questions: int = 6):
        """
        Insert a new quick-practice session row.
        Uses 'Practice Coach' as interviewer name and 'male' as gender
        (gender is a required NOT NULL column; it is not displayed in the practice UI).
        The topic is stored in the job_role column.

        Args:
            user_id:          FK reference to the users table.
            topic:            The practice topic / skill name chosen by the student.
            difficulty_level: 'easy', 'medium' (default), 'hard', or 'adaptive'.
            total_questions:  Total number of questions for the practice drill (3-20, default 6).

        Returns:
            The created InterviewSession instance with session_type='practice'.
        """
        if difficulty_level not in ('easy', 'medium', 'hard', 'adaptive'):
            difficulty_level = 'medium'
        if not isinstance(total_questions, int) or total_questions < 3 or total_questions > 20:
            total_questions = 6
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            """
            INSERT INTO interview_sessions
                (user_id, interviewer_gender, interviewer_name, job_role, status, session_type, interview_type, total_questions, difficulty_level)
            VALUES (?, 'male', 'Practice Coach', ?, 'setup', 'practice', 'technical', ?, ?);
            """,
            (user_id, topic.strip(), total_questions, difficulty_level)
        )
        db.commit()
        session_id = cursor.lastrowid
        return cls.get_by_id(session_id)

    def update_status(self, new_status: str):
        """Update the lifecycle status of this session instance ('setup', 'in_progress', 'completed')."""
        if new_status not in ('setup', 'in_progress', 'completed'):
            raise ValueError(f"Invalid status '{new_status}'.")
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "UPDATE interview_sessions SET status = ? WHERE id = ?;",
            (new_status, self.id)
        )
        db.commit()
        self.status = new_status

    def complete(self):
        """Mark this interview session as completed."""
        self.update_status('completed')

    @classmethod
    def update_status_by_id(cls, session_id: int, new_status: str):
        """Update the lifecycle status for a session by its primary key."""
        if new_status not in ('setup', 'in_progress', 'completed'):
            raise ValueError(f"Invalid status '{new_status}'.")
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "UPDATE interview_sessions SET status = ? WHERE id = ?;",
            (new_status, session_id)
        )
        db.commit()

    # ------------------------------------------------------------------
    # Aggregate / count operations
    # ------------------------------------------------------------------

    @classmethod
    def count_all(cls) -> int:
        """Return total count of full_interview sessions across all users (excludes practice)."""
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM interview_sessions WHERE session_type = 'full_interview';"
        )
        row = cursor.fetchone()
        return row[0] if row else 0

    @classmethod
    def count_today(cls) -> int:
        """Return count of full_interview sessions created today (UTC date). Excludes practice."""
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM interview_sessions "
            "WHERE date(created_at) = date('now') AND session_type = 'full_interview';"
        )
        row = cursor.fetchone()
        return row[0] if row else 0

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
        Retrieve ALL interview sessions for a given user (both types),
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
    def get_full_interviews_by_user(cls, user_id):
        """
        Retrieve only full_interview sessions for a given user,
        ordered by creation date descending.
        """
        if not user_id:
            return []
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            """
            SELECT * FROM interview_sessions
            WHERE user_id = ? AND session_type = 'full_interview'
            ORDER BY created_at DESC, id DESC;
            """,
            (user_id,)
        )
        rows = cursor.fetchall()
        return [cls._from_row(row) for row in rows]

    @classmethod
    def get_practice_sessions_by_user(cls, user_id):
        """
        Retrieve only practice sessions for a given user,
        ordered by creation date descending.
        """
        if not user_id:
            return []
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            """
            SELECT * FROM interview_sessions
            WHERE user_id = ? AND session_type = 'practice'
            ORDER BY created_at DESC, id DESC;
            """,
            (user_id,)
        )
        rows = cursor.fetchall()
        return [cls._from_row(row) for row in rows]

    @classmethod
    def get_latest_by_user(cls, user_id):
        """
        Return the most recently created interview session (any type) for a user,
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

    @classmethod
    def get_sessions_with_reports_by_user(cls, user_id: int, session_type: str = None) -> list:
        """
        Retrieve interview sessions for a given user with their associated evaluation reports.
        Returns a list of dicts containing session data and report metrics.

        Args:
            user_id:      The student's user ID.
            session_type: Optional filter — 'full_interview', 'practice', or None (all).
        """
        if not user_id:
            return []
        db = get_db()
        cursor = db.cursor()

        if session_type:
            cursor.execute(
                """
                SELECT
                    s.id AS session_id,
                    s.user_id,
                    s.interviewer_gender,
                    s.interviewer_name,
                    s.job_role,
                    s.status,
                    s.session_type,
                    s.interview_type,
                    s.total_questions,
                    s.difficulty_level,
                    s.avatar_mode,
                    s.faculty_avatar,
                    s.created_at AS session_created_at,
                    r.id AS report_id,
                    r.technical_score,
                    r.communication_score,
                    r.overall_score,
                    r.confidence_level,
                    r.analysis_available,
                    r.created_at AS report_created_at
                FROM interview_sessions s
                LEFT JOIN interview_reports r ON s.id = r.session_id
                WHERE s.user_id = ? AND s.session_type = ?
                ORDER BY s.created_at DESC, s.id DESC;
                """,
                (user_id, session_type)
            )
        else:
            cursor.execute(
                """
                SELECT
                    s.id AS session_id,
                    s.user_id,
                    s.interviewer_gender,
                    s.interviewer_name,
                    s.job_role,
                    s.status,
                    s.session_type,
                    s.interview_type,
                    s.total_questions,
                    s.difficulty_level,
                    s.avatar_mode,
                    s.faculty_avatar,
                    s.created_at AS session_created_at,
                    r.id AS report_id,
                    r.technical_score,
                    r.communication_score,
                    r.overall_score,
                    r.confidence_level,
                    r.analysis_available,
                    r.created_at AS report_created_at
                FROM interview_sessions s
                LEFT JOIN interview_reports r ON s.id = r.session_id
                WHERE s.user_id = ?
                ORDER BY s.created_at DESC, s.id DESC;
                """,
                (user_id,)
            )

        rows = cursor.fetchall()
        results = []
        for row in rows:
            keys = row.keys() if hasattr(row, 'keys') else []
            results.append({
                'session_id': row['session_id'],
                'user_id': row['user_id'],
                'interviewer_gender': row['interviewer_gender'],
                'interviewer_name': row['interviewer_name'],
                'job_role': row['job_role'],
                'status': row['status'],
                'session_type': row['session_type'],
                'interview_type': row['interview_type'] if 'interview_type' in keys else 'mixed',
                'total_questions': row['total_questions'] if 'total_questions' in keys else 8,
                'difficulty_level': row['difficulty_level'] if 'difficulty_level' in keys else 'medium',
                'avatar_mode': row['avatar_mode'] if 'avatar_mode' in keys else 'general',
                'faculty_avatar': row['faculty_avatar'] if 'faculty_avatar' in keys else None,
                'session_created_at': safe_format_datetime(row['session_created_at'], fmt='%Y-%m-%d %H:%M:%S', fallback=None),
                'report_id': row['report_id'],
                'technical_score': row['technical_score'],
                'communication_score': row['communication_score'],
                'overall_score': row['overall_score'],
                'confidence_level': row['confidence_level'],
                'analysis_available': bool(row['analysis_available']) if row['analysis_available'] is not None else False,
                'has_report': row['report_id'] is not None,
                'report_created_at': safe_format_datetime(row['report_created_at'], fmt='%Y-%m-%d %H:%M:%S', fallback=None)
            })
        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @classmethod
    def _from_row(cls, row):
        """Construct an InterviewSession instance from a SQLite Row."""
        keys = row.keys() if hasattr(row, 'keys') else []
        return cls(
            id=row['id'],
            user_id=row['user_id'],
            interviewer_gender=row['interviewer_gender'],
            interviewer_name=row['interviewer_name'],
            job_role=row['job_role'],
            status=row['status'],
            session_type=row['session_type'] if 'session_type' in keys else 'full_interview',
            interview_type=row['interview_type'] if 'interview_type' in keys else 'mixed',
            total_questions=row['total_questions'] if 'total_questions' in keys else 8,
            difficulty_level=row['difficulty_level'] if 'difficulty_level' in keys else 'medium',
            avatar_mode=row['avatar_mode'] if 'avatar_mode' in keys else 'general',
            faculty_avatar=row['faculty_avatar'] if 'faculty_avatar' in keys else None,
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
            'session_type': self.session_type,
            'interview_type': self.interview_type,
            'total_questions': self.total_questions,
            'difficulty_level': self.difficulty_level,
            'avatar_mode': self.avatar_mode,
            'faculty_avatar': self.faculty_avatar,
            'created_at': str(self.created_at) if self.created_at else None
        }
