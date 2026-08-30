"""
tests/test_question_feedback.py

Automated test suite for Question-Level Feedback and Weak Topics Tracker.
"""

from app import create_app
from database.connection import get_db
from database.schema import init_db
from models.user import User
from models.interview_session import InterviewSession
from models.interview_report import InterviewReport
from models.question_feedback import QuestionFeedback
from services.analysis_service import _validate_and_clean, _parse_gemini_response


def run_tests():
    app = create_app()
    with app.app_context():
        init_db()
        print("[1/6] DB schema & migrations initialized successfully.")

        users = User.get_all()
        student = users[0] if users else None
        assert student is not None, "Need at least 1 student in DB"

        # Create test session
        sess = InterviewSession.create(student.id, 'female', 'Sophia Test', 'Data Analyst')
        print(f"[2/6] Created test session #{sess.id}")

        sample_items = [
            {
                'question': 'Explain the difference between WHERE and HAVING in SQL.',
                'student_answer': 'WHERE is for rows, HAVING is for groups.',
                'ideal_answer': 'WHERE filters rows before aggregation; HAVING filters groups after aggregation with GROUP BY.',
                'feedback': 'Good distinction. Mention GROUP BY explicitly.',
                'topic': 'SQL Queries',
                'score': 65
            },
            {
                'question': 'What is the purpose of an index in a database?',
                'student_answer': 'To find rows faster like an index in a book.',
                'ideal_answer': 'An index creates a B-tree data structure to allow O(log n) lookup for indexed columns.',
                'feedback': 'Great metaphor. Include details on B-trees.',
                'topic': 'Database Indexing',
                'score': 85
            },
            {
                'question': 'How do you handle missing values in Pandas?',
                'student_answer': 'I just drop them with dropna.',
                'ideal_answer': 'Analyze missingness pattern; use fillna with mean/median/mode, forward fill, or dropna.',
                'feedback': 'Dropping rows causes data loss. Mention imputation.',
                'topic': 'Python Pandas',
                'score': 45
            }
        ]

        saved_items = QuestionFeedback.create_batch(sess.id, sample_items)
        assert len(saved_items) == 3, f"Expected 3 items, got {len(saved_items)}"
        print(f"[3/6] Batch saved {len(saved_items)} question feedback records.")

        # Test get_by_session
        by_session = QuestionFeedback.get_by_session(sess.id)
        assert len(by_session) == 3
        assert by_session[0].topic == 'SQL Queries'

        # Test get_weak_topics_by_user (score < 70)
        weak_topics = QuestionFeedback.get_weak_topics_by_user(student.id, score_threshold=70)
        print(f"[4/6] Weak topics retrieved: {list(weak_topics.keys())}")
        assert 'Sql Queries' in weak_topics or 'SQL Queries' in [k.upper() for k in weak_topics.keys()]
        assert 'Python Pandas' in weak_topics or 'PYTHON PANDAS' in [k.upper() for k in weak_topics.keys()]
        assert 'Database Indexing' not in weak_topics  # score 85 is not weak

        # Test analysis service parser with question_breakdown
        sample_dict = {
            "technical_score": 75,
            "communication_score": 70,
            "overall_score": 73,
            "confidence_level": "Moderate",
            "strengths": ["Good SQL knowledge", "Clear communication"],
            "weaknesses": ["Needs deeper Pandas knowledge", "Brief answers"],
            "suggestions": ["Study imputation techniques in Pandas", "Practice B-tree explanations"],
            "question_breakdown": [
                {
                    "question": "What is overfitting?",
                    "student_answer": "Model fits training data too well.",
                    "ideal_answer": "Overfitting occurs when a model learns noise in training data and fails to generalize.",
                    "feedback": "Accurate definition. Mention regularization and cross-validation.",
                    "topic": "Machine Learning",
                    "score": 60
                }
            ]
        }
        validated = _validate_and_clean(sample_dict)
        assert validated is not None
        assert len(validated['question_breakdown']) == 1
        assert validated['question_breakdown'][0]['topic'] == 'Machine Learning'
        print("[5/6] Analysis parser validated question_breakdown structure.")

    with app.test_client() as client:
        with client.session_transaction() as session_ctx:
            session_ctx['user_id'] = student.id
            session_ctx['student_id'] = student.id
            session_ctx['role'] = 'student'
            session_ctx['user_name'] = student.name

        with app.app_context():
            sess.complete()
            InterviewReport.create(
                session_id=sess.id,
                technical_score=75,
                communication_score=70,
                overall_score=73,
                confidence_level='Moderate',
                strengths=['Good SQL knowledge'],
                weaknesses=['Needs deeper Pandas knowledge'],
                suggestions=['Study imputation techniques']
            )

        # 1. Results page verification
        res_results = client.get(f'/student/interviews/{sess.id}/results')
        assert res_results.status_code == 200
        assert b'Question-by-Question Breakdown' in res_results.data
        assert b'SQL Queries' in res_results.data
        assert b'Ideal Benchmark Answer' in res_results.data

        # 2. Dashboard verification
        res_dash = client.get('/student/dashboard')
        assert res_dash.status_code == 200
        assert b'Weak Topics' in res_dash.data

        # 3. Weak topics API verification
        res_api = client.get('/student/weak-topics')
        assert res_api.status_code == 200
        api_json = res_api.get_json()
        assert api_json.get('success') is True
        assert 'weak_topics' in api_json

        print("[6/6] Verified results page, dashboard card, and JSON API endpoint.")

    print("\n" + "="*60)
    print("ALL QUESTION FEEDBACK & WEAK TOPICS TESTS PASSED!")
    print("="*60)


if __name__ == '__main__':
    run_tests()
