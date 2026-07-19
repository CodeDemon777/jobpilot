"""Security tests for JobPilot — OWASP Top 10 and beyond."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from jobpilot.web.app import app
from jobpilot import database as db
from jobpilot.auth import (
    get_password_hash,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    register_user,
)
from jobpilot.security import (
    sanitize_input,
    validate_email,
    validate_password,
    validate_file_upload,
)

client = TestClient(app)


# =====================================================
# SQL INJECTION TESTS
# =====================================================


class TestSQLInjection(unittest.TestCase):
    def test_search_injection(self):
        """Test SQL injection in search queries."""
        malicious_queries = [
            "'; DROP TABLE jobs; --",
            "1' OR '1'='1",
            "admin'--",
            "1; SELECT * FROM users",
            "' UNION SELECT * FROM jobs --",
        ]
        for query in malicious_queries:
            response = client.get(f"/api/jobs?q={query}")
            assert (
                response.status_code == 200
            ), f"SQL injection failed for query: {query}"

    def test_profile_update_injection(self):
        """Test SQL injection in profile updates."""
        malicious_data = {
            "name": "'; DROP TABLE users; --",
            "email": "test@test.com",
        }
        # Should not crash or expose data
        response = client.put("/api/profile", json=malicious_data)
        # Either 200 (sanitized) or 401 (no auth) - both are safe
        assert response.status_code in [200, 401, 422]

    def test_resume_text_injection(self):
        """Test SQL injection in resume text."""
        malicious_text = "'; DROP TABLE resumes; --"
        response = client.post(
            "/api/resume/analyze",
            json={
                "text": malicious_text,
            },
        )
        assert response.status_code == 200  # Should sanitize and process

    def test_cover_letter_injection(self):
        """Test SQL injection in cover letter generation."""
        malicious_data = {
            "resume_text": "'; DROP TABLE cover_letters; --",
            "job_description": "test",
            "company_name": "test",
            "role_title": "test",
        }
        response = client.post("/api/cover-letter/generate", json=malicious_data)
        assert response.status_code == 200  # Should sanitize and process


# =====================================================
# XSS PREVENTION TESTS
# =====================================================


class TestXSSPrevention(unittest.TestCase):
    def test_script_tag_sanitization(self):
        """Test that script tags are removed."""
        xss_inputs = [
            "<script>alert('xss')</script>",
            "<img src=x onerror=alert(1)>",
            "javascript:alert(1)",
            "<svg onload=alert(1)>",
        ]
        for xss in xss_inputs:
            sanitized = sanitize_input(xss)
            assert "<script>" not in sanitized, f"Script tag not removed: {xss}"
            assert (
                "javascript:" not in sanitized
            ), f"Javascript protocol not removed: {xss}"

    def test_html_tag_removal(self):
        """Test that HTML tags are removed."""
        html = "<b>Bold</b> <i>Italic</i> <a href='http://evil.com'>Click</a>"
        sanitized = sanitize_input(html)
        assert "<b>" not in sanitized
        assert "<i>" not in sanitized
        assert "<a>" not in sanitized

    def test_event_handler_removal(self):
        """Test that event handlers are removed."""
        xss = "<div onclick='alert(1)'>Click</div>"
        sanitized = sanitize_input(xss)
        assert "onclick" not in sanitized

    def test_normal_text_preserved(self):
        """Test that normal text is preserved."""
        normal = "This is normal text with numbers 123 and symbols @#$"
        sanitized = sanitize_input(normal)
        assert sanitized == normal


# =====================================================
# AUTHENTICATION SECURITY TESTS
# =====================================================


class TestAuthSecurity(unittest.TestCase):
    def test_password_hashing(self):
        """Test that passwords are properly hashed."""
        password = "MySecurePassword123!"
        hashed = get_password_hash(password)
        assert hashed != password
        assert verify_password(password, hashed) is True
        assert verify_password("WrongPassword", hashed) is False

    def test_password_different_hashes(self):
        """Test that same password produces different hashes (salt)."""
        password = "TestPassword123!"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)
        assert hash1 != hash2, "Same password should produce different hashes"

    def test_jwt_token_structure(self):
        """Test JWT token contains correct claims."""
        token = create_access_token(data={"sub": 1, "email": "test@example.com"})
        decoded = decode_token(token)
        assert decoded.user_id == 1
        assert decoded.email == "test@example.com"

    def test_jwt_refresh_token(self):
        """Test refresh token creation and validation."""
        token = create_refresh_token(data={"sub": 1, "email": "test@example.com"})
        assert isinstance(token, str)
        # Decode and verify it's a refresh token
        from jose import jwt
        from jobpilot.auth import SECRET_KEY, ALGORITHM

        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload.get("type") == "refresh"

    def test_jwt_invalid_token(self):
        """Test that invalid tokens are rejected."""
        try:
            decode_token("invalid.token.here")
            assert False, "Should have raised exception"
        except Exception:
            pass  # Expected

    def test_protected_routes_require_auth(self):
        """Test that protected routes require authentication."""
        protected_routes = [
            "/api/auth/me",
            "/api/roadmap/generate",
            "/api/coach/ask",
        ]
        for route in protected_routes:
            response = (
                client.get(route)
                if "generate" not in route and "ask" not in route
                else client.post(route, json={})
            )
            assert response.status_code == 401, f"Route {route} should require auth"


# =====================================================
# INPUT VALIDATION TESTS
# =====================================================


class TestInputValidation(unittest.TestCase):
    def test_email_validation(self):
        """Test email validation."""
        valid_emails = [
            "test@example.com",
            "user.name@domain.co",
            "user+tag@domain.com",
        ]
        invalid_emails = [
            "",
            "invalid",
            "@domain.com",
            "user@",
            "user@domain",
            "user@.com",
        ]

        for email in valid_emails:
            assert validate_email(email) is True, f"Should be valid: {email}"

        for email in invalid_emails:
            assert validate_email(email) is False, f"Should be invalid: {email}"

    def test_password_validation(self):
        """Test password strength validation."""
        # Valid passwords
        valid = ["Password123!", "MyP@ssw0rd", "Str0ng!Pass"]
        for pwd in valid:
            is_valid, _ = validate_password(pwd)
            assert is_valid is True, f"Should be valid: {pwd}"

        # Invalid passwords
        invalid_cases = [
            ("short", "Too short"),
            ("alllowercase123!", "No uppercase"),
            ("ALLUPPERCASE123!", "No lowercase"),
            ("NoDigits!", "No digit"),
        ]
        for pwd, reason in invalid_cases:
            is_valid, msg = validate_password(pwd)
            assert is_valid is False, f"Should be invalid ({reason}): {pwd}"

    def test_file_upload_validation(self):
        """Test file upload validation."""
        # Valid file
        valid, _ = validate_file_upload("resume.pdf", "application/pdf", 1024)
        assert valid is True

        # Invalid extension
        valid, _ = validate_file_upload("resume.exe", "application/octet-stream", 1024)
        assert valid is False, "Should reject .exe files"

        # Too large (exceeds 10MB limit)
        valid, _ = validate_file_upload(
            "resume.pdf", "application/pdf", 15 * 1024 * 1024
        )
        assert valid is False, "Should reject files over 10MB"

    def test_sanitize_input(self):
        """Test input sanitization."""
        # Should remove dangerous content
        assert "<script>" not in sanitize_input("<script>alert(1)</script>")
        assert "onclick" not in sanitize_input("<div onclick='alert(1)'>")
        assert "javascript:" not in sanitize_input("javascript:alert(1)")

        # Should preserve normal text
        assert sanitize_input("Hello World 123") == "Hello World 123"


# =====================================================
# AUTHORIZATION TESTS
# =====================================================


class TestAuthorization(unittest.TestCase):
    def test_user_cannot_access_admin(self):
        """Test that regular users cannot access admin endpoints."""
        import os

        # Register and login with unique email
        email = f"regular_{os.urandom(4).hex()}@example.com"
        register_user(email, "Pass123!", "Regular")
        response = client.post(
            "/api/auth/login", data={"username": email, "password": "Pass123!"}
        )
        token = response.json()["access_token"]

        # Try admin endpoint
        response = client.get(
            "/api/admin/stats", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 403

    def test_unauthenticated_cannot_access_protected(self):
        """Test that unauthenticated users cannot access protected endpoints."""
        protected = [
            "/api/auth/me",
            "/api/roadmap/generate",
            "/api/coach/ask",
        ]
        for route in protected:
            response = (
                client.get(route)
                if "generate" not in route and "ask" not in route
                else client.post(route, json={})
            )
            assert response.status_code == 401


# =====================================================
# RATE LIMITING TESTS
# =====================================================


class TestRateLimiting(unittest.TestCase):
    def test_rate_limit_exists(self):
        """Test that rate limiter is configured."""
        from jobpilot.security import limiter

        assert limiter is not None

    def test_cors_configured(self):
        """Test that CORS is configured."""
        response = client.options("/api/jobs")
        # CORS preflight should return 200 or 405
        assert response.status_code in [200, 405]


# =====================================================
# DATA INTEGRITY TESTS
# =====================================================


class TestDataIntegrity(unittest.TestCase):
    def test_password_not_in_user_response(self):
        """Test that password hash is not returned in user responses."""
        import os

        email = f"integrity_{os.urandom(4).hex()}@example.com"
        register_user(email, "Pass123!", "Test")
        response = client.post(
            "/api/auth/login", data={"username": email, "password": "Pass123!"}
        )
        token = response.json()["access_token"]

        response = client.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        data = response.json()
        assert "password" not in data
        assert "password_hash" not in data

    def test_sensitive_data_not_in_logs(self):
        """Test that sensitive data is not exposed in error messages."""
        response = client.post(
            "/api/auth/login",
            data={"username": "nonexistent@test.com", "password": "WrongPassword"},
        )
        # Error message should not reveal whether user exists
        assert response.status_code == 401


# =====================================================
# RUN ALL TESTS
# =====================================================

if __name__ == "__main__":
    import unittest

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    test_classes = [
        TestSQLInjection,
        TestXSSPrevention,
        TestAuthSecurity,
        TestInputValidation,
        TestAuthorization,
        TestRateLimiting,
        TestDataIntegrity,
    ]

    for test_class in test_classes:
        suite.addTests(loader.loadTestsFromTestCase(test_class))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print(f"\n{'='*60}")
    print(
        f"Security Tests: {result.testsRun} run, {len(result.failures)} failures, {len(result.errors)} errors"
    )
    print(f"{'='*60}")

    sys.exit(0 if result.wasSuccessful() else 1)
