"""
models/question_feedback.py

QuestionFeedback model for storing granular, question-by-question evaluation,
ideal answers, critique feedback, and topic categorization linked to interview sessions.
Also powers student weak topic aggregation and targeted improvement tracking.
"""

import logging
from database.connection import get_db

logger = logging.getLogger(__name__)


class QuestionFeedback:
    """
    Represents question-level feedback for a single Q&A turn in an interview session.
    """

    def __init__(
        self,
        id=None,
        session_id=None,
        question_text='',
        student_answer='',
        ideal_answer='',
        feedback_text='',
        topic='',
        score=0,
        created_at=None
    ):
        self.id = id
        self.session_id = session_id
        self.question_text = question_text or ''
        self.student_answer = student_answer or ''
        self.ideal_answer = ideal_answer or ''
        self.feedback_text = feedback_text or ''
        self.topic = topic or 'General'
        self.score = int(score) if score is not None else 0
        self.created_at = created_at

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        session_id: int,
        question_text: str,
        student_answer: str,
        ideal_answer: str,
        feedback_text: str,
        topic: str,
        score: int
    ):
        """
        Insert a single question feedback record.
        Returns the created QuestionFeedback instance.
        """
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            """
            INSERT INTO question_feedback
                (session_id, question_text, student_answer, ideal_answer, feedback_text, topic, score)
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (
                session_id,
                str(question_text or '').strip(),
                str(student_answer or '').strip(),
                str(ideal_answer or '').strip(),
                str(feedback_text or '').strip(),
                str(topic or 'General').strip(),
                max(0, min(100, int(score or 0)))
            )
        )
        db.commit()
        feedback_id = cursor.lastrowid
        return cls.get_by_id(feedback_id)

    @classmethod
    def create_batch(cls, session_id: int, items: list) -> list:
        """
        Batch insert multiple question feedback entries for a session.
        Args:
            session_id: The interview session ID.
            items: List of dicts, each containing:
                   question/question_text, student_answer, ideal_answer, feedback/feedback_text, topic, score.
        Returns:
            List of created QuestionFeedback instances.
        """
        if not items:
            return []

        db = get_db()
        cursor = db.cursor()
        for item in items:
            q_text = str(item.get('question_text') or item.get('question') or '').strip()
            ans_text = str(item.get('student_answer') or '').strip()
            ideal_text = str(item.get('ideal_answer') or '').strip()
            fb_text = str(item.get('feedback_text') or item.get('feedback') or '').strip()
            topic_str = str(item.get('topic') or 'General').strip()
            score_val = max(0, min(100, int(item.get('score', 0))))

            if not q_text and not ans_text:
                continue

            cursor.execute(
                """
                INSERT INTO question_feedback
                    (session_id, question_text, student_answer, ideal_answer, feedback_text, topic, score)
                VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (session_id, q_text, ans_text, ideal_text, fb_text, topic_str, score_val)
            )
        db.commit()
        return cls.get_by_session(session_id)

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    @classmethod
    def get_by_id(cls, feedback_id: int):
        """Retrieve a single question feedback row by primary key."""
        if not feedback_id:
            return None
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "SELECT * FROM question_feedback WHERE id = ?;",
            (feedback_id,)
        )
        row = cursor.fetchone()
        return cls._from_row(row) if row else None

    @classmethod
    def get_by_session(cls, session_id: int) -> list:
        """
        Retrieve all question feedback items for a given interview session,
        ordered in conversational chronological order (id ASC).
        """
        if not session_id:
            return []
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            """
            SELECT * FROM question_feedback
            WHERE session_id = ?
            ORDER BY id ASC;
            """,
            (session_id,)
        )
        rows = cursor.fetchall()
        return [cls._from_row(row) for row in rows]

    @classmethod
    def get_weak_topics_by_user(cls, user_id: int, score_threshold: int = 70,
                                 session_type: str = 'full_interview') -> dict:
        """
        Retrieve and aggregate weak topics across past interviews for a user
        where individual question score is below score_threshold (default < 70).

        Args:
            user_id:         Student user ID.
            score_threshold: Questions below this score are considered weak (default 70).
            session_type:    Filter by session type: 'full_interview' (default) or 'practice'.
                             Pass None to aggregate across all session types.

        Returns:
            Dict mapping topic_name -> {
                'count': int,
                'avg_score': int,
                'last_question': str,
                'last_session_date': str,
                'example_question': str,
                'questions': list of dicts
            }, sorted by mistake count descending.
        """
        if not user_id:
            return {}

        db = get_db()
        cursor = db.cursor()

        if session_type:
            cursor.execute(
                """
                SELECT
                    q.id,
                    q.session_id,
                    q.question_text,
                    q.student_answer,
                    q.ideal_answer,
                    q.feedback_text,
                    q.topic,
                    q.score,
                    q.created_at AS feedback_created_at,
                    s.job_role,
                    s.created_at AS session_created_at
                FROM question_feedback q
                JOIN interview_sessions s ON q.session_id = s.id
                WHERE s.user_id = ? AND q.score < ? AND s.session_type = ?
                ORDER BY q.created_at DESC, q.id DESC;
                """,
                (user_id, score_threshold, session_type)
            )
        else:
            cursor.execute(
                """
                SELECT
                    q.id,
                    q.session_id,
                    q.question_text,
                    q.student_answer,
                    q.ideal_answer,
                    q.feedback_text,
                    q.topic,
                    q.score,
                    q.created_at AS feedback_created_at,
                    s.job_role,
                    s.created_at AS session_created_at
                FROM question_feedback q
                JOIN interview_sessions s ON q.session_id = s.id
                WHERE s.user_id = ? AND q.score < ?
                ORDER BY q.created_at DESC, q.id DESC;
                """,
                (user_id, score_threshold)
            )
        rows = cursor.fetchall()

        weak_topics = {}
        for row in rows:
            topic = (row['topic'] or 'General').strip()
            # Normalize title casing for consistent grouping
            topic_key = topic.title() if len(topic) <= 30 else topic

            if topic_key not in weak_topics:
                session_date = (row['session_created_at'] or row['feedback_created_at'] or '')[:10]
                weak_topics[topic_key] = {
                    'topic': topic_key,
                    'count': 0,
                    'total_score': 0,
                    'avg_score': 0,
                    'last_question': row['question_text'],
                    'last_session_date': session_date,
                    'example_question': row['question_text'],
                    'job_role': row['job_role'],
                    'questions': []
                }

            weak_topics[topic_key]['count'] += 1
            weak_topics[topic_key]['total_score'] += row['score']
            weak_topics[topic_key]['questions'].append({
                'id': row['id'],
                'session_id': row['session_id'],
                'question_text': row['question_text'],
                'student_answer': row['student_answer'],
                'ideal_answer': row['ideal_answer'],
                'feedback_text': row['feedback_text'],
                'score': row['score'],
                'job_role': row['job_role'],
                'date': (row['session_created_at'] or row['feedback_created_at'] or '')[:10]
            })

        # Calculate average score per weak topic and sort by count DESC
        for topic_key, data in weak_topics.items():
            if data['count'] > 0:
                data['avg_score'] = round(data['total_score'] / data['count'])

        sorted_topics = dict(
            sorted(
                weak_topics.items(),
                key=lambda item: (item[1]['count'], -item[1]['avg_score']),
                reverse=True
            )
        )
        return sorted_topics

    @classmethod
    def get_practice_weak_topics_by_user(cls, user_id: int, score_threshold: int = 70) -> dict:
        """
        Convenience wrapper: returns weak topics from practice sessions only.
        Used for the Practice Sessions tab on the History page.
        """
        return cls.get_weak_topics_by_user(
            user_id, score_threshold=score_threshold, session_type='practice'
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @classmethod
    def _from_row(cls, row):
        """Construct a QuestionFeedback instance from a SQLite Row."""
        return cls(
            id=row['id'],
            session_id=row['session_id'],
            question_text=row['question_text'],
            student_answer=row['student_answer'],
            ideal_answer=row['ideal_answer'],
            feedback_text=row['feedback_text'],
            topic=row['topic'],
            score=row['score'],
            created_at=row['created_at']
        )

    def to_dict(self):
        """Serialize question feedback to a plain dictionary."""
        return {
            'id': self.id,
            'session_id': self.session_id,
            'question_text': self.question_text,
            'student_answer': self.student_answer,
            'ideal_answer': self.ideal_answer,
            'feedback_text': self.feedback_text,
            'topic': self.topic,
            'score': self.score,
            'created_at': str(self.created_at) if self.created_at else None
        }
