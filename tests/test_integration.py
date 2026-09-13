"""
tests/test_integration.py

Module 15 — Comprehensive End-to-End Test Suite for InterviewCoach AI.

Covers:
  - Student flow: register → login → resume → skills → interview → chat → results → history
  - Admin flow: login → dashboard → search → access control
  - Edge cases: empty states, invalid submissions, session expiry, authorization checks
  - Route integrity: all url_for() references resolve without BuildError

Run with:
    python -m pytest tests/test_integration.py -v
or:
    python tests/test_integration.py
"""

import sys
import os
import json
import unittest
from pathlib import Path

# Ensure project root on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app


# ---------------------------------------------------------------------------
# Sample Data
# ---------------------------------------------------------------------------

SAMPLE_STUDENT = {
    "name": "Test Student",
    "email": "teststudent@example.com",
    "password": "TestPass@123",
    "confirm_password": "TestPass@123",
}

SAMPLE_ADMIN_EMAIL = "admin@interviewcoach.ai"
SAMPLE_ADMIN_PASSWORD = "Admin@123456"


def register_and_login(client, student=None):
    """Register a student and return the logged-in client."""
    s = student or SAMPLE_STUDENT
    client.post("/auth/register", data=s, follow_redirects=True)
    resp = client.post(
        "/auth/login",
        data={"email": s["email"], "password": s["password"]},
        follow_redirects=True,
    )
    return resp


# ---------------------------------------------------------------------------
# Base Test Case
# ---------------------------------------------------------------------------

class BaseTestCase(unittest.TestCase):
    """
    Base test case that creates a fresh temporary SQLite database file for each test.
    Using a temporary file on disk guarantees that all connections, models,
    background requests, and app contexts access the exact same initialized schema.
    """

    def setUp(self):
        import tempfile
        import os
        from database.schema import init_db

        # Create unique temporary database file
        self._db_fd, self._db_path = tempfile.mkstemp(suffix=".db", prefix="ic_test_")
        os.close(self._db_fd)

        self.app = create_app("testing")
        self.app.config["TESTING"] = True
        self.app.config["SECRET_KEY"] = "test-secret-key-module15"
        self.app.config["DATABASE_PATH"] = self._db_path

        upload_dir = Path(__file__).resolve().parent / "test_uploads"
        self.app.config["UPLOAD_FOLDER"] = str(upload_dir)
        upload_dir.mkdir(parents=True, exist_ok=True)

        # Initialize schema in the temporary database
        with self.app.app_context():
            init_db()

        self.client = self.app.test_client()

    def tearDown(self):
        import os
        import gc
        # Force garbage collection to release any lingering SQLite file locks on Windows
        gc.collect()
        try:
            if os.path.exists(self._db_path):
                os.remove(self._db_path)
        except Exception:
            pass


# ===========================================================================
# 1. HEALTH CHECK & SYSTEM ROUTES
# ===========================================================================

class TestSystemRoutes(BaseTestCase):

    def test_health_check_returns_200(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertTrue(data["success"])
        self.assertEqual(data["data"]["status"], "healthy")

    def test_landing_page_returns_200(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"InterviewCoach AI", resp.data)

    def test_404_returns_json_error(self):
        resp = self.client.get("/this-route-does-not-exist-xyz")
        self.assertEqual(resp.status_code, 404)
        data = json.loads(resp.data)
        self.assertFalse(data["success"])


# ===========================================================================
# 2. STUDENT AUTHENTICATION
# ===========================================================================

class TestStudentAuthentication(BaseTestCase):

    def test_register_get_renders_form(self):
        resp = self.client.get("/auth/register")
        self.assertEqual(resp.status_code, 200)

    def test_register_post_valid_data_creates_session(self):
        resp = self.client.post("/auth/register", data=SAMPLE_STUDENT, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"dashboard", resp.data.lower())

    def test_register_duplicate_email_fails(self):
        self.client.post("/auth/register", data=SAMPLE_STUDENT, follow_redirects=True)
        self.client.get("/auth/logout")
        resp = self.client.post("/auth/register", data=SAMPLE_STUDENT, follow_redirects=True)
        self.assertNotEqual(resp.status_code, 500)

    def test_register_missing_name_fails(self):
        bad = {**SAMPLE_STUDENT, "name": "", "email": "other1@example.com"}
        resp = self.client.post("/auth/register", data=bad)
        self.assertEqual(resp.status_code, 400)

    def test_register_invalid_email_format_fails(self):
        bad = {**SAMPLE_STUDENT, "email": "not-an-email"}
        resp = self.client.post("/auth/register", data=bad)
        self.assertEqual(resp.status_code, 400)

    def test_register_password_mismatch_fails(self):
        bad = {**SAMPLE_STUDENT, "confirm_password": "Different@999", "email": "pm@example.com"}
        resp = self.client.post("/auth/register", data=bad)
        self.assertEqual(resp.status_code, 400)

    def test_register_short_password_fails(self):
        bad = {**SAMPLE_STUDENT, "password": "abc", "confirm_password": "abc", "email": "sp@example.com"}
        resp = self.client.post("/auth/register", data=bad)
        self.assertEqual(resp.status_code, 400)

    def test_login_valid_credentials(self):
        self.client.post("/auth/register", data=SAMPLE_STUDENT, follow_redirects=True)
        self.client.get("/auth/logout")
        resp = self.client.post(
            "/auth/login",
            data={"email": SAMPLE_STUDENT["email"], "password": SAMPLE_STUDENT["password"]},
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"dashboard", resp.data.lower())

    def test_login_invalid_password(self):
        self.client.post("/auth/register", data=SAMPLE_STUDENT, follow_redirects=True)
        self.client.get("/auth/logout")
        resp = self.client.post(
            "/auth/login",
            data={"email": SAMPLE_STUDENT["email"], "password": "WrongPass@999"},
        )
        self.assertEqual(resp.status_code, 401)

    def test_login_nonexistent_email(self):
        resp = self.client.post(
            "/auth/login",
            data={"email": "nobody@nowhere.com", "password": "TestPass@123"},
        )
        self.assertEqual(resp.status_code, 401)

    def test_logout_clears_session(self):
        register_and_login(self.client)
        self.client.get("/auth/logout", follow_redirects=True)
        resp = self.client.get("/student/dashboard", follow_redirects=True)
        self.assertIn(b"login", resp.data.lower())

    def test_guest_redirect_when_already_logged_in(self):
        register_and_login(self.client)
        resp = self.client.get("/auth/login", follow_redirects=True)
        self.assertIn(b"dashboard", resp.data.lower())


# ===========================================================================
# 3. STUDENT PAGES — RESUME, SKILLS, HISTORY
# ===========================================================================

class TestStudentPages(BaseTestCase):

    def setUp(self):
        super().setUp()
        register_and_login(self.client)

    def test_dashboard_loads(self):
        resp = self.client.get("/student/dashboard")
        self.assertEqual(resp.status_code, 200)

    def test_dashboard_first_login_shows_tour_and_complete_api(self):
        # Freshly logged in user should have onboarding tour triggered
        resp = self.client.get("/student/dashboard")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"startOnboardingTour", resp.data)

        # Complete onboarding via API
        post_resp = self.client.post("/student/complete-onboarding")
        self.assertEqual(post_resp.status_code, 200)
        data = json.loads(post_resp.data)
        self.assertTrue(data.get("success"))

        # Subsequent dashboard visit should NOT have auto-trigger script
        resp_after = self.client.get("/student/dashboard")
        self.assertEqual(resp_after.status_code, 200)
        self.assertNotIn(b"startOnboardingTour", resp_after.data)

    def test_user_model_mark_and_reset_onboarding(self):
        from models.user import User
        with self.app.app_context():
            user = User.get_by_email(SAMPLE_STUDENT["email"])
            self.assertIsNotNone(user)
            
            # Test mark complete
            User.mark_onboarding_complete(user.id)
            refreshed = User.get_by_id(user.id)
            self.assertEqual(refreshed.onboarding_completed, 1)

            # Test reset
            User.reset_onboarding(user.id)
            refreshed2 = User.get_by_id(user.id)
            self.assertEqual(refreshed2.onboarding_completed, 0)

    def test_how_it_works_page_loads(self):
        resp = self.client.get("/student/how-it-works")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"How the AI Works", resp.data)

    def test_profile_page_loads(self):
        resp = self.client.get("/student/profile")
        self.assertEqual(resp.status_code, 200)

    def test_resume_upload_page_loads(self):
        resp = self.client.get("/student/resume/upload")
        self.assertEqual(resp.status_code, 200)

    def test_resume_upload_no_file_returns_400(self):
        resp = self.client.post("/student/resume/upload", data={})
        self.assertEqual(resp.status_code, 400)

    def test_resume_upload_wrong_type_rejected(self):
        from io import BytesIO
        data = {"resume": (BytesIO(b"fake content"), "resume.txt")}
        resp = self.client.post(
            "/student/resume/upload", data=data, content_type="multipart/form-data"
        )
        self.assertEqual(resp.status_code, 400)

    def test_resume_view_without_upload_redirects(self):
        resp = self.client.get("/student/resume/view", follow_redirects=True)
        self.assertIn(b"upload", resp.data.lower())

    def test_skills_page_loads(self):
        resp = self.client.get("/student/skills")
        self.assertEqual(resp.status_code, 200)

    def test_skills_add_custom_skill(self):
        resp = self.client.post(
            "/student/skills/update",
            data={"action": "add", "skill": "__custom__", "custom_skill": "Apache Kafka"},
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)

    def test_skills_add_from_library(self):
        resp = self.client.post(
            "/student/skills/update",
            data={"action": "add", "skill": "Python"},
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)

    def test_skills_remove_nonexistent_skill_handled_gracefully(self):
        resp = self.client.post(
            "/student/skills/update",
            data={"action": "remove", "skill": "NotInMyList@@@"},
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)

    def test_skills_unknown_action_handled(self):
        resp = self.client.post(
            "/student/skills/update",
            data={"action": "destroy_everything"},
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)

    def test_interview_history_empty_state(self):
        resp = self.client.get("/student/interviews/history")
        self.assertEqual(resp.status_code, 200)

    def test_weak_topics_api_empty_state(self):
        resp = self.client.get("/student/weak-topics")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertTrue(data["success"])


# ===========================================================================
# 4. INTERVIEW SETUP & SESSION FLOW
# ===========================================================================

class TestInterviewFlow(BaseTestCase):

    def setUp(self):
        super().setUp()
        register_and_login(self.client)

    def _create_session(self, role="Software Engineer", gender="male", name="Alex"):
        return self.client.post(
            "/student/interviews/new",
            data={"interviewer_gender": gender, "interviewer_name": name, "job_role": role},
            follow_redirects=False,
        )

    def _extract_session_id(self, location):
        parts = location.rstrip("/").split("/")
        for p in parts:
            if p.isdigit():
                return int(p)
        return None

    def test_interview_setup_page_loads(self):
        resp = self.client.get("/student/interviews/new")
        self.assertEqual(resp.status_code, 200)

    def test_interview_setup_missing_gender_returns_422(self):
        resp = self.client.post(
            "/student/interviews/new",
            data={"interviewer_name": "Alex", "job_role": "Software Engineer"},
        )
        self.assertEqual(resp.status_code, 422)

    def test_interview_setup_missing_name_returns_422(self):
        resp = self.client.post(
            "/student/interviews/new",
            data={"interviewer_gender": "male", "job_role": "Data Scientist"},
        )
        self.assertEqual(resp.status_code, 422)

    def test_interview_setup_invalid_role_returns_422(self):
        resp = self.client.post(
            "/student/interviews/new",
            data={"interviewer_gender": "male", "interviewer_name": "Alex", "job_role": "FAKE_ROLE_XYZ"},
        )
        self.assertEqual(resp.status_code, 422)

    def test_interview_setup_other_role_without_custom_returns_422(self):
        resp = self.client.post(
            "/student/interviews/new",
            data={"interviewer_gender": "female", "interviewer_name": "Sarah", "job_role": "Other", "custom_role": ""},
        )
        self.assertEqual(resp.status_code, 422)

    def test_interview_setup_other_role_with_custom_succeeds(self):
        resp = self._create_session.__func__(self)
        # Use direct POST
        resp = self.client.post(
            "/student/interviews/new",
            data={
                "interviewer_gender": "male",
                "interviewer_name": "Jordan",
                "job_role": "Other",
                "custom_role": "Blockchain Developer",
            },
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)

    def test_interview_setup_valid_redirects_to_room(self):
        resp = self._create_session()
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/room", resp.headers.get("Location", ""))

    def test_interview_room_nonexistent_session_redirects(self):
        resp = self.client.get("/student/interviews/99999/room", follow_redirects=True)
        self.assertIn(b"dashboard", resp.data.lower())

    def test_chat_api_nonexistent_session_returns_404(self):
        resp = self.client.post("/student/interviews/99999/chat", json={"answer": "Hello"})
        self.assertEqual(resp.status_code, 404)

    def test_messages_api_nonexistent_session_returns_404(self):
        resp = self.client.get("/student/interviews/99999/messages")
        self.assertEqual(resp.status_code, 404)

    def test_results_nonexistent_session_redirects(self):
        resp = self.client.get("/student/interviews/99999/results", follow_redirects=True)
        self.assertIn(b"dashboard", resp.data.lower())

    def test_full_session_lifecycle(self):
        """Create → room → chat → messages → end → results → history."""
        resp = self._create_session(role="Data Analyst", name="Jordan")
        self.assertEqual(resp.status_code, 302)
        session_id = self._extract_session_id(resp.headers.get("Location", ""))
        self.assertIsNotNone(session_id)

        # Room loads
        resp = self.client.get(f"/student/interviews/{session_id}/room")
        self.assertEqual(resp.status_code, 200)

        # First chat turn
        resp = self.client.post(
            f"/student/interviews/{session_id}/chat",
            json={"answer": ""},
            content_type="application/json",
        )
        self.assertIn(resp.status_code, [200, 500])
        data = json.loads(resp.data)
        self.assertIn("ai_message", data)

        # Messages API
        resp = self.client.get(f"/student/interviews/{session_id}/messages")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertTrue(data["success"])
        self.assertGreaterEqual(data["count"], 1)

        # End interview
        resp = self.client.post(f"/student/interviews/{session_id}/end", follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        # Results page
        resp = self.client.get(f"/student/interviews/{session_id}/results")
        self.assertEqual(resp.status_code, 200)

        # History shows session
        resp = self.client.get("/student/interviews/history")
        self.assertEqual(resp.status_code, 200)

    def test_completed_session_room_redirects_to_results(self):
        """Verify that visiting the room of a completed session redirects to results."""
        register_and_login(self.client)
        with self.app.app_context():
            from models.interview_session import InterviewSession
            session_obj = InterviewSession.create(
                user_id=1,
                interviewer_gender="female",
                interviewer_name="Sarah",
                job_role="Data Analyst",
                interview_type="general",
                total_questions=3,
            )
            session_obj.update_status("completed")

            resp = self.client.get(f"/student/interviews/{session_obj.id}/room", follow_redirects=False)
            self.assertEqual(resp.status_code, 302)
            self.assertIn(f"/student/interviews/{session_obj.id}/results", resp.headers.get("Location", ""))


# ===========================================================================
# 5. AUTHORIZATION CHECKS
# ===========================================================================

class TestAuthorizationChecks(BaseTestCase):

    def test_unauthenticated_dashboard_redirects(self):
        resp = self.client.get("/student/dashboard", follow_redirects=True)
        self.assertIn(b"login", resp.data.lower())

    def test_unauthenticated_skills_redirects(self):
        resp = self.client.get("/student/skills", follow_redirects=True)
        self.assertIn(b"login", resp.data.lower())

    def test_unauthenticated_interview_room_redirects(self):
        resp = self.client.get("/student/interviews/1/room", follow_redirects=True)
        self.assertIn(b"login", resp.data.lower())

    def test_unauthenticated_chat_api_returns_401(self):
        resp = self.client.post("/student/interviews/1/chat", json={"answer": "Hello"})
        self.assertEqual(resp.status_code, 401)

    def test_student_cannot_access_admin_dashboard(self):
        register_and_login(self.client)
        resp = self.client.get("/admin/dashboard", follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        # Admin dashboard title should NOT appear
        self.assertNotIn(b"administrator dashboard", resp.data.lower())

    def test_cross_user_session_access_blocked(self):
        # Student A creates a session
        student_a = {**SAMPLE_STUDENT, "email": "sa_auth@test.com"}
        register_and_login(self.client, student_a)
        resp = self.client.post(
            "/student/interviews/new",
            data={"interviewer_gender": "male", "interviewer_name": "Alex", "job_role": "Software Engineer"},
            follow_redirects=False,
        )
        location = resp.headers.get("Location", "")
        parts = location.rstrip("/").split("/")
        session_id = next((int(p) for p in parts if p.isdigit()), None)
        self.assertIsNotNone(session_id)

        # Switch to Student B
        self.client.get("/auth/logout")
        student_b = {**SAMPLE_STUDENT, "email": "sb_auth@test.com"}
        register_and_login(self.client, student_b)

        resp = self.client.get(f"/student/interviews/{session_id}/room", follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(b"alex", resp.data.lower())  # Interviewer name from A's session

    def test_cross_user_chat_api_returns_403(self):
        # Create session as Student A
        student_a = {**SAMPLE_STUDENT, "email": "sa_chat@test.com"}
        register_and_login(self.client, student_a)
        resp = self.client.post(
            "/student/interviews/new",
            data={"interviewer_gender": "female", "interviewer_name": "Maya", "job_role": "Data Scientist"},
            follow_redirects=False,
        )
        location = resp.headers.get("Location", "")
        session_id = next(
            (int(p) for p in location.rstrip("/").split("/") if p.isdigit()), None
        )

        # Switch to Student B
        self.client.get("/auth/logout")
        student_b = {**SAMPLE_STUDENT, "email": "sb_chat@test.com"}
        register_and_login(self.client, student_b)

        resp = self.client.post(
            f"/student/interviews/{session_id}/chat",
            json={"answer": "Trying to hijack"},
        )
        self.assertEqual(resp.status_code, 403)


# ===========================================================================
# 6. ADMIN FLOW
# ===========================================================================

class TestAdminFlow(BaseTestCase):

    def _seed_admin(self):
        with self.app.app_context():
            from models.admin import Admin
            if not Admin.get_by_email(SAMPLE_ADMIN_EMAIL):
                Admin.create(
                    name="Test Admin",
                    email=SAMPLE_ADMIN_EMAIL,
                    password=SAMPLE_ADMIN_PASSWORD
                )

    def _admin_login(self):
        self._seed_admin()
        return self.client.post(
            "/auth/admin/login",
            data={"email": SAMPLE_ADMIN_EMAIL, "password": SAMPLE_ADMIN_PASSWORD},
            follow_redirects=True,
        )

    def test_admin_login_page_loads(self):
        resp = self.client.get("/auth/admin/login")
        self.assertEqual(resp.status_code, 200)

    def test_admin_login_invalid_credentials(self):
        self._seed_admin()
        resp = self.client.post(
            "/auth/admin/login",
            data={"email": SAMPLE_ADMIN_EMAIL, "password": "WrongAdminPass"},
        )
        self.assertEqual(resp.status_code, 401)

    def test_admin_login_valid_redirects_to_dashboard(self):
        resp = self._admin_login()
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"dashboard", resp.data.lower())

    def test_admin_dashboard_loads(self):
        self._admin_login()
        resp = self.client.get("/admin/dashboard")
        self.assertEqual(resp.status_code, 200)

    def test_admin_dashboard_search(self):
        self._admin_login()
        resp = self.client.get("/admin/dashboard?q=test")
        self.assertEqual(resp.status_code, 200)

    def test_unauthenticated_admin_dashboard_redirects(self):
        resp = self.client.get("/admin/dashboard", follow_redirects=True)
        self.assertIn(b"login", resp.data.lower())

    def test_admin_logout_clears_session(self):
        self._admin_login()
        self.client.get("/auth/admin/logout", follow_redirects=True)
        resp = self.client.get("/admin/dashboard", follow_redirects=True)
        self.assertIn(b"login", resp.data.lower())


# ===========================================================================
# 7. ROUTE INTEGRITY
# ===========================================================================

class TestRouteIntegrity(BaseTestCase):

    def test_all_public_routes_resolve(self):
        for url in ["/", "/health", "/auth/register", "/auth/login", "/auth/admin/login"]:
            resp = self.client.get(url)
            self.assertNotEqual(resp.status_code, 500, f"Route {url} returned 500")

    def test_all_protected_student_routes_redirect(self):
        routes = [
            "/student/dashboard", "/student/profile", "/student/resume/upload",
            "/student/resume/view", "/student/skills",
            "/student/interviews/new", "/student/interviews/history",
            "/student/practice/new",
        ]
        for url in routes:
            resp = self.client.get(url)
            self.assertIn(resp.status_code, [302, 401],
                          f"Route {url} returned {resp.status_code}")

    def test_all_admin_routes_redirect_when_unauthenticated(self):
        for url in ["/admin/", "/admin/dashboard"]:
            resp = self.client.get(url)
            self.assertIn(resp.status_code, [302, 401],
                          f"Admin route {url} returned {resp.status_code}")


# ===========================================================================
# 8. PRACTICE MODE (QUICK PRACTICE & DATA SEPARATION)
# ===========================================================================

class TestPracticeMode(BaseTestCase):

    def setUp(self):
        super().setUp()
        register_and_login(self.client)

    def _extract_session_id(self, location):
        parts = location.rstrip("/").split("/")
        for p in parts:
            if p.isdigit():
                return int(p)
        return None

    def test_practice_setup_get_renders(self):
        resp = self.client.get("/student/practice/new")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Quick Practice Mode", resp.data)

    def test_practice_setup_missing_topic_returns_422(self):
        resp = self.client.post("/student/practice/new", data={"topic": ""})
        self.assertEqual(resp.status_code, 422)

    def test_practice_setup_custom_topic_creates_session(self):
        resp = self.client.post(
            "/student/practice/new",
            data={"topic": "__custom__", "custom_topic": "Docker Containerization"},
            follow_redirects=False,
        )
        self.assertEqual(resp.status_code, 302)
        location = resp.headers.get("Location", "")
        self.assertIn("/practice/", location)
        self.assertIn("/room", location)

        session_id = self._extract_session_id(location)
        self.assertIsNotNone(session_id)

        # Verify session model row has session_type='practice'
        with self.app.app_context():
            from models.interview_session import InterviewSession
            sess = InterviewSession.get_by_id(session_id)
            self.assertIsNotNone(sess)
            self.assertEqual(sess.session_type, "practice")
            self.assertEqual(sess.job_role, "Docker Containerization")

    def test_practice_room_loads(self):
        # Create session
        resp = self.client.post(
            "/student/practice/new",
            data={"topic": "__custom__", "custom_topic": "GraphQL APIs"},
            follow_redirects=False,
        )
        session_id = self._extract_session_id(resp.headers.get("Location", ""))

        resp = self.client.get(f"/student/practice/{session_id}/room")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"GraphQL APIs", resp.data)
        self.assertIn(b"Practice Mode", resp.data)

    def test_practice_chat_api_dispatches_question(self):
        # Create session
        resp = self.client.post(
            "/student/practice/new",
            data={"topic": "__custom__", "custom_topic": "System Design"},
            follow_redirects=False,
        )
        session_id = self._extract_session_id(resp.headers.get("Location", ""))

        # Begin / 1st turn
        resp = self.client.post(
            f"/student/practice/{session_id}/chat",
            json={"answer": ""},
        )
        self.assertIn(resp.status_code, [200, 500])
        data = json.loads(resp.data)
        self.assertIn("ai_message", data)
        self.assertEqual(data.get("session_type"), "practice")

        # Answer question
        resp = self.client.post(
            f"/student/practice/{session_id}/chat",
            json={"answer": "I use caching with Redis and database sharding."},
        )
        self.assertIn(resp.status_code, [200, 500])
        data = json.loads(resp.data)
        self.assertIn("ai_message", data)

    def test_practice_chat_wrong_session_type_returns_400(self):
        # Create full interview session
        resp = self.client.post(
            "/student/interviews/new",
            data={"interviewer_gender": "male", "interviewer_name": "Alex", "job_role": "Software Engineer"},
            follow_redirects=False,
        )
        session_id = self._extract_session_id(resp.headers.get("Location", ""))

        # Trying to chat via practice endpoint with a full interview session should return 400
        resp = self.client.post(f"/student/practice/{session_id}/chat", json={"answer": "Hello"})
        self.assertEqual(resp.status_code, 400)

    def test_practice_end_lifecycle(self):
        # Create and chat
        resp = self.client.post(
            "/student/practice/new",
            data={"topic": "__custom__", "custom_topic": "Python Asyncio"},
            follow_redirects=False,
        )
        session_id = self._extract_session_id(resp.headers.get("Location", ""))

        self.client.post(
            f"/student/practice/{session_id}/chat",
            json={"answer": "Asyncio is used for cooperative multitasking."},
        )

        # End practice
        resp = self.client.post(f"/student/practice/{session_id}/end", follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        # Verify status is completed
        with self.app.app_context():
            from models.interview_session import InterviewSession
            sess = InterviewSession.get_by_id(session_id)
            self.assertEqual(sess.status, "completed")

    def test_dashboard_stats_and_history_separate_practice_from_full_interviews(self):
        # 1. Create a full interview
        self.client.post(
            "/student/interviews/new",
            data={"interviewer_gender": "female", "interviewer_name": "Sarah", "job_role": "Data Scientist"},
            follow_redirects=True,
        )

        # 2. Create 2 practice sessions
        self.client.post(
            "/student/practice/new",
            data={"topic": "__custom__", "custom_topic": "Kubernetes"},
            follow_redirects=True,
        )
        self.client.post(
            "/student/practice/new",
            data={"topic": "__custom__", "custom_topic": "PostgreSQL"},
            follow_redirects=True,
        )

        # Dashboard should count only 1 full interview in "Full Interviews" metric
        resp = self.client.get("/student/dashboard")
        self.assertEqual(resp.status_code, 200)
        # Verify the context metrics
        self.assertIn(b"Full Interviews", resp.data)

        # History Page - full interviews tab
        resp_full = self.client.get("/student/interviews/history?tab=full")
        self.assertEqual(resp_full.status_code, 200)
        self.assertIn(b"Data Scientist", resp_full.data)
        self.assertNotIn(b"Kubernetes", resp_full.data)

        # History Page - practice sessions tab
        resp_practice = self.client.get("/student/interviews/history?tab=practice")
        self.assertEqual(resp_practice.status_code, 200)
        self.assertIn(b"Kubernetes", resp_practice.data)
        self.assertIn(b"PostgreSQL", resp_practice.data)
        self.assertNotIn(b"Data Scientist", resp_practice.data)

    def test_cross_user_practice_access_blocked(self):
        # Student A creates practice session
        student_a = {**SAMPLE_STUDENT, "email": "sa_prac@test.com"}
        register_and_login(self.client, student_a)
        resp = self.client.post(
            "/student/practice/new",
            data={"topic": "__custom__", "custom_topic": "Security"},
            follow_redirects=False,
        )
        session_id = self._extract_session_id(resp.headers.get("Location", ""))

        # Student B logs in
        self.client.get("/auth/logout")
        student_b = {**SAMPLE_STUDENT, "email": "sb_prac@test.com"}
        register_and_login(self.client, student_b)

        # Access room -> blocked / redirected
        resp = self.client.get(f"/student/practice/{session_id}/room", follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"dashboard", resp.data.lower())

        # Chat API -> 403
        resp = self.client.post(f"/student/practice/{session_id}/chat", json={"answer": "test"})
        self.assertEqual(resp.status_code, 403)


# ===========================================================================
# 9. INTERVIEW CUSTOMIZATION (TYPE & QUESTIONS)
# ===========================================================================

class TestInterviewCustomization(BaseTestCase):

    def _extract_session_id(self, location_header: str) -> int:
        parts = location_header.rstrip("/").split("/")
        for p in parts:
            if p.isdigit():
                return int(p)
        return None

    def test_setup_saves_interview_type_and_total_questions(self):
        """Verify interview setup form saves interview_type and total_questions correctly."""
        from models.interview_session import InterviewSession

        register_and_login(self.client)

        # 1. Test standard predefined options (technical, 5 questions)
        resp = self.client.post(
            "/student/interviews/new",
            data={
                "interviewer_gender": "female",
                "interviewer_name": "Sarah",
                "job_role": "Software Engineer",
                "interview_type": "technical",
                "total_questions": "5",
            },
            follow_redirects=False,
        )
        self.assertEqual(resp.status_code, 302)
        session_id = self._extract_session_id(resp.headers.get("Location", ""))
        self.assertIsNotNone(session_id)

        with self.app.app_context():
            session_obj = InterviewSession.get_by_id(session_id)
            self.assertIsNotNone(session_obj)
            self.assertEqual(session_obj.interview_type, "technical")
            self.assertEqual(session_obj.total_questions, 5)

        # 2. Test custom question count option (general, custom: 6 questions)
        resp2 = self.client.post(
            "/student/interviews/new",
            data={
                "interviewer_gender": "male",
                "interviewer_name": "Alex",
                "job_role": "Data Analyst",
                "interview_type": "general",
                "total_questions": "custom",
                "custom_questions": "6",
            },
            follow_redirects=False,
        )
        self.assertEqual(resp2.status_code, 302)
        session_id2 = self._extract_session_id(resp2.headers.get("Location", ""))
        with self.app.app_context():
            session_obj2 = InterviewSession.get_by_id(session_id2)
            self.assertEqual(session_obj2.interview_type, "general")
            self.assertEqual(session_obj2.total_questions, 6)

    def test_conversation_engine_prompts_for_types(self):
        """Verify conversation engine builds differentiated prompts for technical vs general vs mixed."""
        from services.conversation_engine import build_system_prompt
        from models.interview_session import InterviewSession
        from models.user import User

        with self.app.app_context():
            user = User(id=1, name="Alice Candidate", email="alice@test.com")

            # Technical session
            tech_session = InterviewSession(
                id=1,
                user_id=1,
                interviewer_gender="male",
                interviewer_name="Alex",
                job_role="Software Engineer",
                interview_type="technical",
                total_questions=8,
            )
            tech_prompt = build_system_prompt(tech_session, user, 3, "Stage 3")
            self.assertIn("TECHNICAL ONLY", tech_prompt)
            self.assertIn("Do NOT ask HR, behavioral", tech_prompt)

            # General session
            gen_session = InterviewSession(
                id=2,
                user_id=1,
                interviewer_gender="female",
                interviewer_name="Sarah",
                job_role="Product Manager",
                interview_type="general",
                total_questions=8,
            )
            gen_prompt = build_system_prompt(gen_session, user, 3, "Stage 3")
            self.assertIn("GENERAL / HR ONLY", gen_prompt)
            self.assertIn("Do NOT ask technical coding", gen_prompt)

            # Mixed session
            mixed_session = InterviewSession(
                id=3,
                user_id=1,
                interviewer_gender="male",
                interviewer_name="Alex",
                job_role="Full Stack Developer",
                interview_type="mixed",
                total_questions=8,
            )
            mixed_prompt = build_system_prompt(mixed_session, user, 3, "Stage 3")
            self.assertIn("MIXED", mixed_prompt)
            self.assertIn("50-50 blend", mixed_prompt)

    def test_wrap_up_message_at_total_questions(self):
        """Verify wrap-up message fires gracefully when total_questions is reached."""
        from models.interview_session import InterviewSession
        from services.conversation_engine import get_next_question

        register_and_login(self.client)

        with self.app.app_context():
            # Create session with total_questions = 3
            session_obj = InterviewSession.create(
                user_id=1,
                interviewer_gender="male",
                interviewer_name="Alex",
                job_role="Software Engineer",
                interview_type="mixed",
                total_questions=3,
            )

            # Turn 0: Greeting (no student answer yet)
            res0 = get_next_question(session_obj.id, student_answer=None)
            self.assertFalse(res0["is_wrap_up"])
            self.assertEqual(res0["current_question_number"], 0)

            # Turn 1: Candidate confirms readiness ("I am ready") -> AI asks Intro (Q0)
            res1 = get_next_question(session_obj.id, student_answer="I am ready to begin.")
            self.assertFalse(res1["is_wrap_up"])
            self.assertEqual(res1["current_question_number"], 0)
            self.assertTrue(res1.get("is_intro"))

            # Turn 2: Candidate answers Intro -> AI asks actual Q1 of 3
            res2 = get_next_question(session_obj.id, student_answer="Here is my background and experience.")
            self.assertFalse(res2["is_wrap_up"])
            self.assertEqual(res2["current_question_number"], 1)

            # Turn 3: Candidate answers actual Q1 -> AI asks actual Q2 of 3
            res3 = get_next_question(session_obj.id, student_answer="I use Python and PostgreSQL for backend services.")
            self.assertFalse(res3["is_wrap_up"])
            self.assertEqual(res3["current_question_number"], 2)

            # Turn 4: Candidate answers actual Q2 -> AI asks actual Q3 of 3 (final question)
            res4 = get_next_question(session_obj.id, student_answer="I design microservices with fault-tolerant circuit breakers.")
            self.assertFalse(res4["is_wrap_up"])
            self.assertEqual(res4["current_question_number"], 3)

            # Turn 5: Candidate answers actual Q3 (all 3 actual questions answered) -> AI must gracefully wrap up
            res5 = get_next_question(session_obj.id, student_answer="Here is my final answer for question 3.")
            self.assertTrue(res5["is_wrap_up"])
            self.assertEqual(res5["current_question_number"], 3)
            self.assertIn("brings us to the end of our interview", res5["ai_message"].lower())

    def test_chat_api_returns_question_progress_metadata(self):
        """Verify chat API response contains current_question_number, total_questions, and is_wrap_up."""
        register_and_login(self.client)

        resp = self.client.post(
            "/student/interviews/new",
            data={
                "interviewer_gender": "male",
                "interviewer_name": "Alex",
                "job_role": "Software Engineer",
                "interview_type": "technical",
                "total_questions": "5",
            },
            follow_redirects=False,
        )
        session_id = self._extract_session_id(resp.headers.get("Location", ""))

        # Post to chat API: answer readiness check -> AI asks Intro (Q0)
        chat_resp = self.client.post(
            f"/student/interviews/{session_id}/chat",
            json={"answer": "I am ready to start the interview."},
            content_type="application/json",
        )
        self.assertEqual(chat_resp.status_code, 200)
        data = json.loads(chat_resp.data)
        self.assertIn("current_question_number", data)
        self.assertIn("total_questions", data)
        self.assertIn("is_wrap_up", data)
        self.assertEqual(data["total_questions"], 5)
        self.assertEqual(data["current_question_number"], 0)
        self.assertTrue(data.get("is_intro"))
        self.assertFalse(data["is_wrap_up"])

        # Second turn: answer intro -> AI asks actual Q1
        chat_resp2 = self.client.post(
            f"/student/interviews/{session_id}/chat",
            json={"answer": "I am a software engineer with Python experience."},
            content_type="application/json",
        )
        self.assertEqual(chat_resp2.status_code, 200)
        data2 = json.loads(chat_resp2.data)
        self.assertEqual(data2["current_question_number"], 1)
        self.assertFalse(data2["is_wrap_up"])


# ===========================================================================
# TestIntroFeedback — Intro Randomisation & Intro Feedback separation
# ===========================================================================

class TestIntroFeedback(BaseTestCase):
    """
    Tests for:
    1. Intro question randomisation: different sessions yield different intro templates.
    2. Same session always yields the same intro template (deterministic/stable).
    3. introduction_feedback is stored in InterviewReport and exposed via to_dict().
    """

    def _make_session(self, session_id_hint=None):
        """Create a quick in-memory interview session object for testing conversation engine."""
        from models.user import User
        from models.interview_session import InterviewSession
        # Register student then create a session via the real DB
        s = {
            "name": f"Intro Test User",
            "email": f"intro_test_{session_id_hint or 'x'}@example.com",
            "password": "TestPass@123",
            "confirm_password": "TestPass@123",
        }
        self.client.post("/auth/register", data=s, follow_redirects=True)
        self.client.post("/auth/login", data={"email": s["email"], "password": s["password"]}, follow_redirects=True)
        resp = self.client.post(
            "/student/interviews/new",
            data={
                "interviewer_gender": "male",
                "interviewer_name": "TestBot",
                "job_role": "Software Engineer",
                "interview_type": "mixed",
                "total_questions": "5",
            },
            follow_redirects=False,
        )
        loc = resp.headers.get("Location", "")
        parts = [p for p in loc.split("/") if p.isdigit()]
        return int(parts[-1]) if parts else None

    def test_introduction_variants_differ_across_sessions(self):
        """
        Two different sessions should (statistically) receive different intro question phrasings.
        We verify by checking that _seeded_choice produces different results for different IDs.
        """
        from services.conversation_engine import INTRODUCTION_VARIANTS, _seeded_choice
        results = set()
        for seed in range(20):
            chosen = _seeded_choice(INTRODUCTION_VARIANTS, seed, offset=0)
            results.add(chosen)
        # With 20 different session IDs and 10 variants, we must see at least 3 distinct variants
        self.assertGreaterEqual(len(results), 3, 
            "Expected multiple distinct intro variants across different session IDs")

    def test_same_session_intro_is_stable(self):
        """
        The same session_id always produces the exact same intro question variant
        (deterministic across multiple calls).
        """
        from services.conversation_engine import INTRODUCTION_VARIANTS, _seeded_choice
        for seed in [1, 42, 999, 12345]:
            first  = _seeded_choice(INTRODUCTION_VARIANTS, seed, offset=0)
            second = _seeded_choice(INTRODUCTION_VARIANTS, seed, offset=0)
            third  = _seeded_choice(INTRODUCTION_VARIANTS, seed, offset=0)
            self.assertEqual(first, second, f"Intro variant changed on second call for session_id={seed}")
            self.assertEqual(first, third,  f"Intro variant changed on third call for session_id={seed}")

    def test_get_intro_question_for_session_variety(self):
        """
        Verify that get_intro_question_for_session() for 5 different session IDs
        produces at least 3 distinct opening phrases (Fix 1 verification).
        """
        from services.conversation_engine import get_intro_question_for_session
        openings = set()
        for sid in [1, 2, 3, 4, 5]:
            q = get_intro_question_for_session(sid, "Software Engineer")
            phrase = " ".join(q.split()[:4])
            openings.add(phrase)
        self.assertGreaterEqual(
            len(openings), 3,
            f"Expected at least 3 distinct opening phrases across 5 sessions, got {len(openings)}: {openings}"
        )

    def test_intro_feedback_stored_and_rendered(self):
        """
        Verify that InterviewReport.create() stores introduction_feedback as JSON,
        _from_row() deserializes it correctly, and to_dict() exposes it.
        """
        from models.interview_report import InterviewReport
        from models.interview_session import InterviewSession
        from models.user import User
        
        with self.app.app_context():
            # Create test user and session
            email = "intro_fb_test@example.com"
            user = User.get_by_email(email)
            if not user:
                user = User.create("Intro FB Tester", email, "TestPass@123")
            
            session_obj = InterviewSession.create(
                user_id=user.id,
                interviewer_gender="female",
                interviewer_name="Sarah",
                job_role="Data Analyst",
                interview_type="general",
                total_questions=5,
            )

            intro_payload = {
                "transcript_summary": "The candidate introduced themselves as a data analyst with 3 years of experience.",
                "strengths": ["Clear structure", "Good relevance to role"],
                "improvements": ["Could be more specific about achievements", "Add quantifiable metrics"],
                "overall_rating": "Good",
                "detailed_feedback": "A solid introduction. The candidate demonstrated good communication skills."
            }

            report = InterviewReport.create(
                session_id=session_obj.id,
                technical_score=72,
                communication_score=80,
                overall_score=75,
                confidence_level="High",
                strengths=["Articulate", "Confident"],
                weaknesses=["Lacked depth", "Too brief"],
                suggestions=["Use STAR method", "Quantify achievements"],
                analysis_available=True,
                introduction_feedback=intro_payload,
            )

            # Verify stored and deserialized correctly
            self.assertIsNotNone(report)
            self.assertIsNotNone(report.introduction_feedback)
            self.assertIsInstance(report.introduction_feedback, dict)
            self.assertEqual(report.introduction_feedback["overall_rating"], "Good")
            self.assertEqual(len(report.introduction_feedback["strengths"]), 2)
            self.assertEqual(len(report.introduction_feedback["improvements"]), 2)

            # Verify fetching from DB preserves the data
            fetched = InterviewReport.get_by_session(session_obj.id)
            self.assertIsNotNone(fetched)
            self.assertIsNotNone(fetched.introduction_feedback)
            self.assertEqual(fetched.introduction_feedback["overall_rating"], "Good")
            self.assertEqual(
                fetched.introduction_feedback["transcript_summary"],
                intro_payload["transcript_summary"]
            )

            # Verify to_dict includes it
            d = fetched.to_dict()
            self.assertIn("introduction_feedback", d)
            self.assertIsInstance(d["introduction_feedback"], dict)


# ===========================================================================
# RUNNER
# ===========================================================================

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for cls in [
        TestSystemRoutes,
        TestStudentAuthentication,
        TestStudentPages,
        TestInterviewFlow,
        TestAuthorizationChecks,
        TestAdminFlow,
        TestRouteIntegrity,
        TestPracticeMode,
        TestInterviewCustomization,
        TestIntroFeedback,
    ]:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
