"""
models/interview_report.py

InterviewReport model for storing AI-generated performance analysis reports
linked to completed interview sessions.
"""

import json
import logging
from database.connection import get_db

logger = logging.getLogger(__name__)


class InterviewReport:
    """
    Represents a single AI-generated performance analysis report
    for a completed mock-interview session.
    """

    def __init__(
        self,
        id=None,
        session_id=None,
        technical_score=0,
        communication_score=0,
        overall_score=0,
        confidence_level='Moderate',
        strengths=None,
        weaknesses=None,
        suggestions=None,
        analysis_available=True,
        created_at=None
    ):
        self.id = id
        self.session_id = session_id
        self.technical_score = technical_score
        self.communication_score = communication_score
        self.overall_score = overall_score
        self.confidence_level = confidence_level
        self.strengths = strengths if strengths is not None else []
        self.weaknesses = weaknesses if weaknesses is not None else []
        self.suggestions = suggestions if suggestions is not None else []
        self.analysis_available = analysis_available
        self.created_at = created_at

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        session_id: int,
        technical_score: int,
        communication_score: int,
        overall_score: int,
        confidence_level: str,
        strengths: list,
        weaknesses: list,
        suggestions: list,
        analysis_available: bool = True
    ):
        """
        Insert a new interview report row with full analysis data.
        Lists (strengths, weaknesses, suggestions) are serialized to JSON strings.
        Returns the created InterviewReport instance.

        Args:
            session_id:          FK reference to interview_sessions.
            technical_score:     Integer 0-100, technical quality score.
            communication_score: Integer 0-100, communication clarity score.
            overall_score:       Integer 0-100, weighted combined score.
            confidence_level:    'Low', 'Moderate', or 'High'.
            strengths:           List of 2-4 short strength strings.
            weaknesses:          List of 2-4 short weakness strings.
            suggestions:         List of 2-4 actionable improvement tips.
            analysis_available:  True if analysis succeeded, False if unavailable.
        """
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            """
            INSERT INTO interview_reports
                (session_id, technical_score, communication_score, overall_score,
                 confidence_level, strengths, weaknesses, suggestions, analysis_available)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                session_id,
                int(technical_score),
                int(communication_score),
                int(overall_score),
                str(confidence_level).strip(),
                json.dumps(strengths if isinstance(strengths, list) else []),
                json.dumps(weaknesses if isinstance(weaknesses, list) else []),
                json.dumps(suggestions if isinstance(suggestions, list) else []),
                1 if analysis_available else 0
            )
        )
        db.commit()
        report_id = cursor.lastrowid
        return cls.get_by_id(report_id)

    @classmethod
    def create_unavailable(cls, session_id: int):
        """
        Insert a placeholder report row flagged as analysis_available=0.
        Used when the Gemini API is unreachable or JSON parsing fails,
        ensuring the session can still be completed and the results page
        renders a friendly 'analysis unavailable' state without crashing.

        Args:
            session_id: FK reference to interview_sessions.
        """
        return cls.create(
            session_id=session_id,
            technical_score=0,
            communication_score=0,
            overall_score=0,
            confidence_level='Moderate',
            strengths=[],
            weaknesses=[],
            suggestions=[],
            analysis_available=False
        )

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    @classmethod
    def get_by_id(cls, report_id: int):
        """Retrieve a single interview report by its primary key."""
        if not report_id:
            return None
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "SELECT * FROM interview_reports WHERE id = ?;",
            (report_id,)
        )
        row = cursor.fetchone()
        return cls._from_row(row) if row else None

    @classmethod
    def get_by_session(cls, session_id: int):
        """
        Retrieve the most recent interview report for a given session.
        Returns None if no report exists (e.g. legacy sessions completed
        before Module 12 was introduced).
        """
        if not session_id:
            return None
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            """
            SELECT * FROM interview_reports
            WHERE session_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 1;
            """,
            (session_id,)
        )
        row = cursor.fetchone()
        return cls._from_row(row) if row else None

    @classmethod
    def get_all_by_user(cls, user_id: int) -> list:
        """
        Retrieve all completed and evaluated interview reports for a given user,
        ordered chronologically (oldest to newest) to display progress trends.
        Joins interview_reports with interview_sessions to include session context.
        """
        if not user_id:
            return []
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            """
            SELECT 
                r.id AS report_id,
                r.session_id,
                r.technical_score,
                r.communication_score,
                r.overall_score,
                r.confidence_level,
                r.strengths,
                r.weaknesses,
                r.suggestions,
                r.analysis_available,
                r.created_at AS report_created_at,
                s.job_role,
                s.interviewer_name,
                s.interviewer_gender,
                s.created_at AS session_created_at
            FROM interview_reports r
            JOIN interview_sessions s ON r.session_id = s.id
            WHERE s.user_id = ? AND r.analysis_available = 1
            ORDER BY r.created_at ASC, r.id ASC;
            """,
            (user_id,)
        )
        rows = cursor.fetchall()

        results = []
        for row in rows:
            results.append({
                'report_id': row['report_id'],
                'session_id': row['session_id'],
                'technical_score': row['technical_score'],
                'communication_score': row['communication_score'],
                'overall_score': row['overall_score'],
                'confidence_level': row['confidence_level'],
                'job_role': row['job_role'],
                'interviewer_name': row['interviewer_name'],
                'interviewer_gender': row['interviewer_gender'],
                'session_created_at': str(row['session_created_at']) if row['session_created_at'] else None,
                'report_created_at': str(row['report_created_at']) if row['report_created_at'] else None,
            })
        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @classmethod
    def _from_row(cls, row):
        """
        Construct an InterviewReport instance from a SQLite Row.
        Safely deserializes JSON list columns; falls back to empty list on error.
        """
        def _safe_json_list(raw):
            if not raw:
                return []
            try:
                parsed = json.loads(raw)
                return parsed if isinstance(parsed, list) else []
            except (json.JSONDecodeError, TypeError):
                return []

        return cls(
            id=row['id'],
            session_id=row['session_id'],
            technical_score=row['technical_score'],
            communication_score=row['communication_score'],
            overall_score=row['overall_score'],
            confidence_level=row['confidence_level'],
            strengths=_safe_json_list(row['strengths']),
            weaknesses=_safe_json_list(row['weaknesses']),
            suggestions=_safe_json_list(row['suggestions']),
            analysis_available=bool(row['analysis_available']),
            created_at=row['created_at']
        )

    def to_dict(self):
        """Serialize the report to a plain dictionary for template rendering."""
        return {
            'id': self.id,
            'session_id': self.session_id,
            'technical_score': self.technical_score,
            'communication_score': self.communication_score,
            'overall_score': self.overall_score,
            'confidence_level': self.confidence_level,
            'strengths': self.strengths,
            'weaknesses': self.weaknesses,
            'suggestions': self.suggestions,
            'analysis_available': self.analysis_available,
            'created_at': str(self.created_at) if self.created_at else None
        }
