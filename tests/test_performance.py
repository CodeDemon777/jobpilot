"""Performance tests for JobPilot — response times and load testing."""

import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from jobpilot.web.app import app
from jobpilot import database as db
from jobpilot.auth import register_user, get_password_hash


client = TestClient(app)

# Performance thresholds (seconds)
THRESHOLDS = {
    "api_response": 5.0,      # Max API response time
    "database_query": 3.0,    # Max database query time
    "resume_analysis": 10.0,  # Max resume analysis time
    "job_search": 5.0,        # Max job search time
    "page_load": 2.0,         # Max page load time
}


# =====================================================
# API RESPONSE TIME TESTS
# =====================================================

class TestAPIResponseTimes(unittest.TestCase):
    def test_health_endpoint_speed(self):
        """Test health endpoint responds quickly."""
        start = time.time()
        response = client.get("/health")
        duration = time.time() - start
        assert response.status_code == 200
        assert duration < THRESHOLDS["api_response"], f"Health endpoint too slow: {duration:.3f}s"

    def test_jobs_list_speed(self):
        """Test jobs listing responds quickly."""
        start = time.time()
        response = client.get("/api/jobs")
        duration = time.time() - start
        assert response.status_code == 200
        assert duration < THRESHOLDS["api_response"], f"Jobs list too slow: {duration:.3f}s"

    def test_resume_analysis_speed(self):
        """Test resume analysis completes within threshold."""
        start = time.time()
        response = client.post("/api/resume/analyze", json={
            "text": "John Doe\nPython developer with 5 years experience.\nSkills: Python, Django, PostgreSQL",
            "target_role": "backend engineer",
        })
        duration = time.time() - start
        assert response.status_code == 200
        assert duration < THRESHOLDS["resume_analysis"], f"Resume analysis too slow: {duration:.3f}s"

    def test_cover_letter_generation_speed(self):
        """Test cover letter generation completes within threshold."""
        start = time.time()
        response = client.post("/api/cover-letter/generate", json={
            "resume_text": "Python developer with 5 years experience",
            "job_description": "Looking for Python developer",
            "company_name": "TestCorp",
            "role_title": "Python Developer",
        })
        duration = time.time() - start
        assert response.status_code == 200
        assert duration < THRESHOLDS["api_response"], f"Cover letter too slow: {duration:.3f}s"

    def test_skill_gap_analysis_speed(self):
        """Test skill gap analysis completes within threshold."""
        start = time.time()
        response = client.post("/api/skill-gap/analyze", json={
            "resume_text": "Python developer with Django",
            "job_description": "Python, Django, Docker, AWS",
        })
        duration = time.time() - start
        assert response.status_code == 200
        assert duration < THRESHOLDS["api_response"], f"Skill gap analysis too slow: {duration:.3f}s"


# =====================================================
# DATABASE QUERY PERFORMANCE
# =====================================================

class TestDatabasePerformance(unittest.TestCase):
    def test_job_search_speed(self):
        """Test database search query performance."""
        start = time.time()
        response = client.get("/api/jobs?q=python")
        duration = time.time() - start
        assert response.status_code == 200
        assert duration < THRESHOLDS["database_query"], f"DB search too slow: {duration:.3f}s"

    def test_jobs_list_query_speed(self):
        """Test listing all jobs performance."""
        start = time.time()
        response = client.get("/api/jobs")
        duration = time.time() - start
        assert response.status_code == 200
        assert duration < THRESHOLDS["database_query"], f"DB list too slow: {duration:.3f}s"


# =====================================================
# CONCURRENT REQUEST TESTS
# =====================================================

class TestConcurrentRequests(unittest.TestCase):
    def test_concurrent_health_checks(self):
        """Test multiple concurrent health checks."""
        import concurrent.futures

        def health_check():
            return client.get("/health").status_code

        start = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(health_check) for _ in range(10)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        duration = time.time() - start

        assert all(r == 200 for r in results), "Some health checks failed"
        assert duration < 5.0, f"Concurrent requests too slow: {duration:.3f}s"

    def test_concurrent_api_calls(self):
        """Test multiple concurrent API calls."""
        import concurrent.futures

        def api_call(endpoint):
            return client.get(endpoint).status_code

        endpoints = ["/api/jobs", "/health", "/api/trending/skills", "/ready"]

        start = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(api_call, ep) for ep in endpoints * 3]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        duration = time.time() - start

        assert all(r == 200 for r in results), "Some API calls failed"
        assert duration < 30.0, f"Concurrent API calls too slow: {duration:.3f}s"


# =====================================================
# MEMORY USAGE TESTS
# =====================================================

class TestMemoryUsage(unittest.TestCase):
    def test_no_memory_leak_on_repeated_requests(self):
        """Test that repeated requests don't cause memory leaks."""
        import gc

        gc.collect()
        initial_objects = len(gc.get_objects())

        # Make 100 requests
        for _ in range(100):
            client.get("/api/jobs")
            client.get("/health")

        gc.collect()
        final_objects = len(gc.get_objects())

        # Allow some growth but not excessive
        growth = final_objects - initial_objects
        assert growth < 10000, f"Possible memory leak: {growth} objects created"


# =====================================================
# FILE UPLOAD PERFORMANCE
# =====================================================

class TestFileUploadPerformance(unittest.TestCase):
    def test_upload_performance(self):
        """Test file upload performance."""
        # Create a test file
        content = b"John Doe\nPython developer" * 1000  # ~20KB

        start = time.time()
        response = client.post(
            "/api/resume/upload",
            files={"file": ("resume.txt", content, "text/plain")},
        )
        duration = time.time() - start

        assert response.status_code == 200
        assert duration < THRESHOLDS["api_response"], f"Upload too slow: {duration:.3f}s"

    def test_large_file_rejection(self):
        """Test that large files are rejected quickly."""
        # Create a 10MB file (above limit)
        content = b"x" * (10 * 1024 * 1024)

        start = time.time()
        response = client.post(
            "/api/resume/upload",
            files={"file": ("large_resume.txt", content, "text/plain")},
        )
        duration = time.time() - start

        # Should be rejected quickly
        assert duration < 2.0, f"Large file rejection too slow: {duration:.3f}s"


# =====================================================
# RUN ALL TESTS
# =====================================================

if __name__ == "__main__":
    import unittest

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    test_classes = [
        TestAPIResponseTimes,
        TestDatabasePerformance,
        TestConcurrentRequests,
        TestMemoryUsage,
        TestFileUploadPerformance,
    ]

    for test_class in test_classes:
        suite.addTests(loader.loadTestsFromTestCase(test_class))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print(f"\n{'='*60}")
    print(f"Performance Tests: {result.testsRun} run, {len(result.failures)} failures, {len(result.errors)} errors")
    print(f"{'='*60}")

    sys.exit(0 if result.wasSuccessful() else 1)
