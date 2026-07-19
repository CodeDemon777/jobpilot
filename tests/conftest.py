"""Pytest configuration and fixtures for JobPilot QA system."""

import sys
import os
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient

from jobpilot.web.app import app
from jobpilot import database as db
from jobpilot.config import DB_PATH
from jobpilot.auth import get_password_hash, create_access_token

# Test database path
TEST_DB = Path(__file__).resolve().parent / "test_qa.db"


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Set up test database once for all tests."""
    if TEST_DB.exists():
        TEST_DB.unlink()
    # Initialize the database
    conn = db.get_connection(TEST_DB)
    conn.close()
    yield
    # Cleanup
    if TEST_DB.exists():
        TEST_DB.unlink()


@pytest.fixture(autouse=True)
def clean_test_db():
    """Clean test database before each test."""
    if TEST_DB.exists():
        TEST_DB.unlink()
    # Reinitialize
    conn = db.get_connection(TEST_DB)
    conn.close()
    yield
    # Cleanup after test
    if TEST_DB.exists():
        TEST_DB.unlink()


@pytest.fixture
def client():
    """Create a test client for FastAPI."""
    return TestClient(app)


@pytest.fixture
def auth_client():
    """Create an authenticated test client."""
    client = TestClient(app)

    # Create a test user
    email = f"test_{os.urandom(4).hex()}@example.com"
    password = "TestPass123!"

    from jobpilot.auth import register_user

    register_user(email, password, "Test User")

    # Login and get token
    response = client.post(
        "/api/auth/login", data={"username": email, "password": password}
    )
    token = response.json()["access_token"]

    # Create authenticated client
    client.headers["Authorization"] = f"Bearer {token}"
    return client


@pytest.fixture
def sample_job():
    """Create a sample job listing."""
    from jobpilot.models import JobListing

    return JobListing(
        company="TestCorp",
        title="Python Developer",
        location="San Francisco",
        remote_status="remote",
        required_skills=["python", "django", "postgresql"],
        preferred_skills=["redis", "docker"],
        experience_years=3,
        description="We need a Python developer with Django experience.",
        url="https://example.com/job/1",
        source="test",
    )


@pytest.fixture
def sample_profile():
    """Create a sample user profile."""
    from jobpilot.models import UserProfile

    return UserProfile(
        name="John Doe",
        email="john@example.com",
        phone="555-0123",
        location="San Francisco",
        skills=["python", "django", "postgresql", "redis"],
        programming_languages=["python", "javascript"],
        frameworks=["django", "fastapi"],
        cloud_platforms=["aws"],
        experience_years=5,
        preferred_roles=["backend engineer", "full stack developer"],
        remote_preference="remote",
    )


@pytest.fixture
def sample_resume_text():
    """Sample resume text for testing."""
    return """
John Doe
john@example.com | (555) 123-4567 | linkedin.com/in/johndoe | github.com/johndoe

Summary
Senior Software Engineer with 5 years of experience building scalable web applications.

Experience
Senior Software Engineer | TechCorp | 2021 - Present
- Built microservices architecture serving 10M+ requests/day using Python and FastAPI
- Led migration from monolith to microservices, reducing deploy time by 60%
- Implemented CI/CD pipelines with GitHub Actions and Docker

Software Engineer | StartupXYZ | 2018 - 2021
- Developed React frontend used by 50K+ users
- Designed RESTful APIs with Node.js and PostgreSQL
- Improved application performance by 40% through query optimization

Education
B.S. Computer Science | Stanford University | 2018

Skills
Python, JavaScript, TypeScript, React, Node.js, FastAPI, Django, PostgreSQL,
Docker, Kubernetes, AWS, Redis, Git, GraphQL, REST API, CI/CD
"""


@pytest.fixture
def sample_cover_letter_data():
    """Sample data for cover letter generation."""
    return {
        "resume_text": "John Doe\nPython developer with 5 years experience.",
        "job_description": "Looking for a Python developer with Django experience.",
        "company_name": "TestCorp",
        "role_title": "Python Developer",
    }


@pytest.fixture
def sample_interview_data():
    """Sample interview question request data."""
    return {
        "role_title": "Python Developer",
        "categories": ["technical", "behavioral"],
        "difficulty": "intermediate",
        "count": 5,
    }


@pytest.fixture
def sample_skill_gap_data():
    """Sample skill gap analysis data."""
    return {
        "resume_text": "Python developer with Django and PostgreSQL",
        "job_description": "Looking for Python, Django, Docker, and AWS experience",
    }


@pytest.fixture
def sample_linkedin_data():
    """Sample LinkedIn profile data."""
    return {
        "headline": "Senior Software Engineer at TechCorp",
        "about": "I am a passionate developer with 5 years of experience building scalable systems.",
        "skills": "Python, Java, AWS, Docker, Kubernetes",
        "experience": "Led team of 5 engineers. Built microservices handling 1M requests/day.",
    }


@pytest.fixture
def sample_salary_data():
    """Sample salary estimate request data."""
    return {
        "role": "Software Engineer",
        "company": "TestCorp",
        "location": "San Francisco",
        "experience_level": "mid",
        "skills": ["python", "react", "aws"],
    }


@pytest.fixture
def sample_roadmap_data():
    """Sample career roadmap request data."""
    return {
        "goal_role": "Backend Developer",
        "goal_company": "Google",
    }


@pytest.fixture
def sample_coach_data():
    """Sample career coach question."""
    return {
        "question": "Why is my ATS score low?",
    }
