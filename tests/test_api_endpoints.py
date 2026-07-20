"""Comprehensive API endpoint tests for all JobPilot routes."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from jobpilot.web.app import app
from jobpilot import database as db
from jobpilot.auth import register_user, get_password_hash, create_access_token

# =====================================================
# TEST FIXTURES
# =====================================================

client = TestClient(app)

# Create test user and get token
TEST_EMAIL = "qa_test@example.com"
TEST_PASSWORD = "TestPass123!"


def get_auth_token():
    """Get authentication token for testing."""
    import os
    # Use unique email to avoid conflicts
    test_email = f"qa_test_{os.urandom(4).hex()}@example.com"
    try:
        register_user(test_email, TEST_PASSWORD, "QA Tester")
    except Exception:
        pass

    response = client.post(
        "/api/auth/login", data={"username": test_email, "password": TEST_PASSWORD}
    )
    if response.status_code == 200:
        return response.json()["access_token"]
    return None


AUTH_TOKEN = get_auth_token()
HEADERS = {"Authorization": f"Bearer {AUTH_TOKEN}"} if AUTH_TOKEN else {}


# =====================================================
# AUTHENTICATION API TESTS
# =====================================================


class TestAuthAPI(unittest.TestCase):
    def test_register_success(self):
        import os

        unique_email = f"test_{os.urandom(4).hex()}@example.com"
        response = client.post(
            "/api/auth/register",
            json={
                "email": unique_email,
                "password": "TestPass123!",
                "name": "New User",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["email"] == unique_email

    def test_register_duplicate_email(self):
        response = client.post(
            "/api/auth/register",
            json={"email": TEST_EMAIL, "password": "TestPass123!", "name": "Duplicate"},
        )
        assert response.status_code == 400

    def test_login_success(self):
        import os
        email = f"login_test_{os.urandom(4).hex()}@example.com"
        register_user(email, TEST_PASSWORD, "Login Test")
        response = client.post(
            "/api/auth/login", data={"username": email, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200
        assert "access_token" in response.json()

    def test_login_wrong_password(self):
        import os
        email = f"wrong_test_{os.urandom(4).hex()}@example.com"
        register_user(email, TEST_PASSWORD, "Wrong Test")
        response = client.post(
            "/api/auth/login",
            data={"username": email, "password": "WrongPassword"},
        )
        assert response.status_code == 401

    def test_protected_route(self):
        response = client.get("/api/auth/me")
        assert response.status_code == 401

    def test_get_me_with_token(self):
        response = client.get("/api/auth/me", headers=HEADERS)
        assert response.status_code == 200
        assert "email" in response.json()

    def test_refresh_token(self):
        import os
        email = f"refresh_test_{os.urandom(4).hex()}@example.com"
        register_user(email, TEST_PASSWORD, "Refresh Test")
        response = client.post(
            "/api/auth/login", data={"username": email, "password": TEST_PASSWORD}
        )
        refresh_token = response.json()["refresh_token"]
        response = client.post(f"/api/auth/refresh?refresh_token={refresh_token}")
        assert response.status_code == 200
        assert "access_token" in response.json()


# =====================================================
# JOBS API TESTS
# =====================================================


class TestJobsAPI(unittest.TestCase):
    def test_list_jobs(self):
        response = client.get("/api/jobs", headers=HEADERS)
        assert response.status_code == 200
        assert "jobs" in response.json()
        assert "total" in response.json()

    def test_list_jobs_with_query(self):
        response = client.get("/api/jobs?q=python", headers=HEADERS)
        assert response.status_code == 200

    def test_list_jobs_with_source(self):
        response = client.get("/api/jobs?source=greenhouse", headers=HEADERS)
        assert response.status_code == 200

    def test_import_job_invalid_url(self):
        response = client.post("/api/jobs/import", json={"url": ""}, headers=HEADERS)
        assert response.status_code == 400


# =====================================================
# RESUME API TESTS
# =====================================================


class TestResumeAPI(unittest.TestCase):
    def test_analyze_resume(self):
        response = client.post(
            "/api/resume/analyze",
            json={
                "text": "John Doe\nPython developer with 5 years experience.\nSkills: Python, Django",
                "target_role": "backend engineer",
            },
            headers=HEADERS,
        )
        assert response.status_code == 200
        data = response.json()
        assert "skills" in data
        assert "scores" in data
        assert "ats_score" in data["scores"]

    def test_resume_history(self):
        response = client.get("/api/resume/history", headers=HEADERS)
        assert response.status_code == 200
        assert "resumes" in response.json()

    def test_resume_uploads(self):
        response = client.get("/api/resume/uploads", headers=HEADERS)
        assert response.status_code == 200
        assert "uploads" in response.json()


# =====================================================
# COVER LETTER API TESTS
# =====================================================


class TestCoverLetterAPI(unittest.TestCase):
    def test_generate_cover_letter(self):
        response = client.post(
            "/api/cover-letter/generate",
            json={
                "resume_text": "John Doe\nPython developer",
                "job_description": "Looking for Python developer",
                "company_name": "TestCorp",
                "role_title": "Python Developer",
            },
            headers=HEADERS,
        )
        assert response.status_code == 200
        assert "letter_text" in response.json()

    def test_cover_letter_history(self):
        response = client.get("/api/cover-letter/history", headers=HEADERS)
        assert response.status_code == 200
        assert "cover_letters" in response.json()


# =====================================================
# INTERVIEW API TESTS
# =====================================================


class TestInterviewAPI(unittest.TestCase):
    def test_generate_questions(self):
        response = client.post(
            "/api/interview/questions",
            json={
                "role_title": "Python Developer",
                "categories": ["technical"],
                "difficulty": "intermediate",
                "count": 5,
            },
            headers=HEADERS,
        )
        assert response.status_code == 200
        assert "questions" in response.json()
        assert len(response.json()["questions"]) > 0

    def test_interview_history(self):
        response = client.get("/api/interview/history", headers=HEADERS)
        assert response.status_code == 200


# =====================================================
# SKILL GAP API TESTS
# =====================================================


class TestSkillGapAPI(unittest.TestCase):
    def test_analyze_skill_gap(self):
        response = client.post(
            "/api/skill-gap/analyze",
            json={
                "resume_text": "Python developer with Django",
                "job_description": "Python, Django, Docker, AWS",
            },
            headers=HEADERS,
        )
        assert response.status_code == 200
        assert "match_percentage" in response.json()
        assert "missing_skills" in response.json()


# =====================================================
# LINKEDIN API TESTS
# =====================================================


class TestLinkedInAPI(unittest.TestCase):
    def test_analyze_linkedin(self):
        response = client.post(
            "/api/linkedin/analyze",
            json={
                "headline": "Software Engineer",
                "about": "Passionate developer",
                "skills": "Python, Java",
                "experience": "5 years experience",
            },
            headers=HEADERS,
        )
        assert response.status_code == 200
        assert "visibility_score" in response.json()


# =====================================================
# RESUME TAILORING API TESTS
# =====================================================


class TestResumeTailorAPI(unittest.TestCase):
    def test_tailor_resume(self):
        response = client.post(
            "/api/resume/tailor",
            json={
                "resume_text": "Python developer with Django experience",
                "job_description": "Python, Docker, AWS, Kubernetes",
            },
            headers=HEADERS,
        )
        assert response.status_code == 200
        assert "original_score" in response.json()
        assert "tailored_score" in response.json()


# =====================================================
# ALERTS API TESTS
# =====================================================


class TestAlertsAPI(unittest.TestCase):
    def test_subscribe_alert(self):
        response = client.post(
            "/api/alerts/subscribe",
            json={
                "role": "Python Developer",
                "location": "Remote",
                "frequency": "daily",
            },
            headers=HEADERS,
        )
        assert response.status_code == 200

    def test_list_alerts(self):
        response = client.get("/api/alerts/preferences", headers=HEADERS)
        assert response.status_code == 200
        assert "alerts" in response.json()


# =====================================================
# DASHBOARD API TESTS
# =====================================================


class TestDashboardAPI(unittest.TestCase):
    def test_dashboard_stats(self):
        response = client.get("/api/dashboard/stats", headers=HEADERS)
        assert response.status_code == 200
        assert "job_search_metrics" in response.json()

    def test_dashboard_summary(self):
        response = client.get("/api/dashboard/summary", headers=HEADERS)
        assert response.status_code == 200

    def test_trending_skills(self):
        response = client.get("/api/trending/skills", headers=HEADERS)
        assert response.status_code == 200
        assert "skills" in response.json()

    def test_trending_companies(self):
        response = client.get("/api/trending/companies", headers=HEADERS)
        assert response.status_code == 200
        assert "companies" in response.json()


# =====================================================
# NOTIFICATIONS API TESTS
# =====================================================


class TestNotificationsAPI(unittest.TestCase):
    def test_list_notifications(self):
        response = client.get("/api/notifications", headers=HEADERS)
        assert response.status_code == 200
        assert "notifications" in response.json()

    def test_unread_count(self):
        response = client.get("/api/notifications/unread-count", headers=HEADERS)
        assert response.status_code == 200
        assert "unread_count" in response.json()


# =====================================================
# APPLICATIONS API TESTS
# =====================================================


class TestApplicationsAPI(unittest.TestCase):
    def test_list_applications(self):
        response = client.get("/api/applications", headers=HEADERS)
        assert response.status_code == 200
        assert "applications" in response.json()

    def test_application_stats(self):
        response = client.get("/api/applications/stats", headers=HEADERS)
        assert response.status_code == 200


# =====================================================
# CAREER FEATURES API TESTS
# =====================================================


class TestCareerAPI(unittest.TestCase):
    def test_roadmap_generate(self):
        response = client.post(
            "/api/roadmap/generate",
            json={
                "goal_role": "Backend Developer",
                "goal_company": "Google",
            },
            headers=HEADERS,
        )
        assert response.status_code == 200
        assert "roadmap_data" in response.json()

    def test_coach_ask(self):
        response = client.post(
            "/api/coach/ask",
            json={
                "question": "Why is my ATS score low?",
            },
            headers=HEADERS,
        )
        assert response.status_code == 200
        assert "answer" in response.json()

    def test_resume_versions(self):
        response = client.get("/api/resume/versions", headers=HEADERS)
        assert response.status_code == 200
        assert "versions" in response.json()

    def test_salary_estimate(self):
        response = client.post(
            "/api/salary/estimate",
            json={
                "role": "Software Engineer",
                "location": "San Francisco",
                "skills": ["python"],
            },
            headers=HEADERS,
        )
        assert response.status_code == 200
        assert "estimated_min" in response.json()

    def test_company_interviews(self):
        response = client.get("/api/interviews/company/google", headers=HEADERS)
        assert response.status_code == 200
        assert "company" in response.json()


# =====================================================
# HEALTH CHECK TESTS
# =====================================================


class TestHealthAPI(unittest.TestCase):
    def test_health_endpoint(self):
        response = client.get("/health", headers=HEADERS)
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_readiness_endpoint(self):
        response = client.get("/ready", headers=HEADERS)
        assert response.status_code == 200
        assert response.json()["status"] == "ready"


# =====================================================
# RUN ALL TESTS
# =====================================================

if __name__ == "__main__":
    import unittest

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    test_classes = [
        TestAuthAPI,
        TestJobsAPI,
        TestResumeAPI,
        TestCoverLetterAPI,
        TestInterviewAPI,
        TestSkillGapAPI,
        TestLinkedInAPI,
        TestResumeTailorAPI,
        TestAlertsAPI,
        TestDashboardAPI,
        TestNotificationsAPI,
        TestApplicationsAPI,
        TestCareerAPI,
        TestHealthAPI,
    ]

    for test_class in test_classes:
        suite.addTests(loader.loadTestsFromTestCase(test_class))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print(f"\n{'='*60}")
    print(
        f"API Tests: {result.testsRun} run, {len(result.failures)} failures, {len(result.errors)} errors"
    )
    print(f"{'='*60}")

    sys.exit(0 if result.wasSuccessful() else 1)
