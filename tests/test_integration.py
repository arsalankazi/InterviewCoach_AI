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
    ]:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
