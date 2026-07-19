"""Comprehensive unit tests for all JobPilot modules."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobpilot.models import (
    UserProfile,
    JobListing,
    MatchResult,
    Application,
    Company,
    Resume,
    CoverLetter,
    InterviewQuestion,
    SkillGapReport,
    LinkedInReport,
    TailoredResume,
    AlertSubscription,
    DashboardStats,
    JobNotification,
    JobScanHistory,
    _generate_id,
)
from jobpilot import database as db
from jobpilot.matcher import compute_match

TEST_DB = Path(__file__).resolve().parent / "test_unit.db"


def cleanup():
    """Force cleanup of test database."""
    import gc
    import os

    gc.collect()  # Force garbage collection to release any open file handles
    if TEST_DB.exists():
        try:
            TEST_DB.unlink()
        except PermissionError:
            # Try to close any open connections first
            try:
                import sqlite3

                conn = sqlite3.connect(str(TEST_DB))
                conn.close()
            except:
                pass
            try:
                TEST_DB.unlink()
            except:
                pass


# =====================================================
# MODEL TESTS
# =====================================================


class TestModels(unittest.TestCase):
    def test_job_listing_id_deterministic(self):
        j1 = JobListing(company="Co", title="Dev", url="http://x.com")
        j2 = JobListing(company="Co", title="Dev", url="http://x.com")
        assert j1.id == j2.id

    def test_job_listing_id_unique(self):
        j1 = JobListing(company="Co", title="Dev", url="http://x.com/1")
        j2 = JobListing(company="Co", title="Dev", url="http://x.com/2")
        assert j1.id != j2.id

    def test_job_listing_id_case_insensitive(self):
        j1 = JobListing(company="TestCo", title="Engineer", url="http://x.com")
        j2 = JobListing(company="testco", title="engineer", url="http://x.com")
        assert j1.id == j2.id

    def test_job_listing_to_dict(self):
        j = JobListing(company="Co", title="Dev", url="http://x.com")
        d = j.to_dict()
        assert "id" in d
        assert d["company"] == "Co"

    def test_job_listing_skills_normalization(self):
        j = JobListing(required_skills=["Python", "GO"], preferred_skills=["Docker"])
        assert "python" in j.all_required_skills
        assert "go" in j.all_required_skills

    def test_user_profile_skills_combination(self):
        p = UserProfile(
            skills=["Python"],
            programming_languages=["Go"],
            frameworks=["FastAPI"],
            cloud_platforms=["AWS"],
        )
        assert set(p.all_skills) == {"python", "go", "fastapi", "aws"}

    def test_user_profile_empty(self):
        p = UserProfile()
        assert p.all_skills == []
        assert p.name == ""

    def test_application_id_deterministic(self):
        a1 = Application(job_id="abc", company="Co", role="Role")
        a2 = Application(job_id="abc", company="Co", role="Role")
        assert a1.id == a2.id

    def test_company_defaults(self):
        c = Company(name="TestCo")
        assert c.job_count == 0
        assert c.industry == ""

    def test_resume_defaults(self):
        r = Resume()
        assert r.id == ""
        assert r.to_dict().get("raw_text") is None

    def test_cover_letter_defaults(self):
        cl = CoverLetter()
        assert cl.tone == "professional"
        assert cl.word_count == 0

    def test_interview_question_defaults(self):
        iq = InterviewQuestion()
        assert iq.difficulty == ""
        assert iq.category == ""

    def test_skill_gap_report_defaults(self):
        sgr = SkillGapReport()
        assert sgr.match_percentage == 0.0
        assert sgr.matched_skills == []

    def test_linkedin_report_defaults(self):
        lr = LinkedInReport()
        assert lr.visibility_score == 0.0
        assert lr.strength_score == 0.0

    def test_tailored_resume_defaults(self):
        tr = TailoredResume()
        assert tr.original_score == 0.0
        assert tr.improvement_pct == 0.0

    def test_alert_subscription_defaults(self):
        a = AlertSubscription()
        assert a.frequency == "daily"
        assert a.is_active is True

    def test_dashboard_stats_defaults(self):
        ds = DashboardStats()
        assert ds.total_jobs == 0
        assert ds.period == "all"

    def test_job_notification_defaults(self):
        n = JobNotification()
        assert n.is_read is False
        assert n.notification_type == "new_match"

    def test_job_scan_history_defaults(self):
        h = JobScanHistory()
        assert h.jobs_found == 0
        assert h.duration_seconds == 0.0

    def test_generate_id_deterministic(self):
        id1 = _generate_id("company", "title", "url")
        id2 = _generate_id("company", "title", "url")
        assert id1 == id2

    def test_generate_id_unique(self):
        id1 = _generate_id("company", "title", "url1")
        id2 = _generate_id("company", "title", "url2")
        assert id1 != id2


# =====================================================
# AUTH TESTS
# =====================================================


class TestAuth(unittest.TestCase):
    def test_password_hash_and_verify(self):
        from jobpilot.auth import get_password_hash, verify_password

        password = "TestPass123!"
        hashed = get_password_hash(password)
        assert hashed != password
        assert verify_password(password, hashed) is True
        assert verify_password("WrongPass", hashed) is False

    def test_token_creation(self):
        from jobpilot.auth import create_access_token

        token = create_access_token(data={"sub": 1, "email": "test@example.com"})
        assert isinstance(token, str)
        assert len(token) > 0

    def test_refresh_token_creation(self):
        from jobpilot.auth import create_refresh_token

        token = create_refresh_token(data={"sub": 1, "email": "test@example.com"})
        assert isinstance(token, str)
        assert len(token) > 0

    def test_token_decode(self):
        from jobpilot.auth import create_access_token, decode_token

        token = create_access_token(data={"sub": 1, "email": "test@example.com"})
        data = decode_token(token)
        assert data.user_id == 1
        assert data.email == "test@example.com"

    def test_token_decode_invalid(self):
        from jobpilot.auth import decode_token

        try:
            decode_token("invalid.token.here")
            assert False, "Should raise HTTPException"
        except Exception:
            pass  # Expected

    def test_password_validation(self):
        from jobpilot.security import validate_password

        assert validate_password("short")[0] is False
        assert validate_password("nouppercase123!")[0] is False
        assert validate_password("NOLOWERCASE123!")[0] is False
        assert validate_password("NoDigits!")[0] is False
        assert validate_password("ValidPass123!")[0] is True

    def test_email_validation(self):
        from jobpilot.security import validate_email

        assert validate_email("test@example.com") is True
        assert validate_email("invalid") is False
        assert validate_email("@example.com") is False
        assert validate_email("test@") is False

    def test_input_sanitization(self):
        from jobpilot.security import sanitize_input

        assert "<script>" not in sanitize_input("<script>alert('xss')</script>")
        assert "<b>" not in sanitize_input("Hello <b>World</b>")
        assert sanitize_input("Normal text") == "Normal text"


# =====================================================
# RESUME ANALYZER TESTS
# =====================================================


class TestResumeAnalyzer(unittest.TestCase):
    def test_skill_extraction(self):
        from jobpilot.resume_analyzer import _extract_skills

        skills = _extract_skills("We need Python, React, and AWS experience")
        assert "python" in skills
        assert "react" in skills
        assert "aws" in skills

    def test_section_detection(self):
        from jobpilot.resume_analyzer import _detect_sections

        text = "Summary\nAbout me\n\nExperience\nWork history\n\nSkills\nPython, React"
        sections = _detect_sections(text)
        assert "summary" in sections
        assert "experience" in sections
        assert "skills" in sections

    def test_contact_extraction(self):
        from jobpilot.resume_analyzer import _extract_contact

        text = "John Doe\njohn@example.com | (555) 123-4567"
        contact = _extract_contact(text)
        assert contact.get("email") == "john@example.com"
        assert contact.get("phone") == "(555) 123-4567"

    def test_experience_years(self):
        from jobpilot.resume_analyzer import _estimate_experience_years

        text = "5 years of experience in software development"
        years = _estimate_experience_years(text, {})
        assert years >= 5

    def test_analyze_resume(self):
        from jobpilot.resume_analyzer import analyze_resume

        text = """
        John Doe
        john@example.com
        Python developer with 3 years experience.
        Skills: Python, Django, PostgreSQL
        """
        result = analyze_resume(text)
        assert result.ats_score > 0
        assert "python" in result.skills

    def test_empty_resume(self):
        from jobpilot.resume_analyzer import analyze_resume

        result = analyze_resume("")
        assert result.ats_score == 0

    def test_alias_matching(self):
        from jobpilot.resume_analyzer import _extract_skills

        skills = _extract_skills("Experience with reactjs and nodejs")
        assert "react" in skills
        assert "node.js" in skills


# =====================================================
# MATCHER TESTS
# =====================================================


class TestMatcher(unittest.TestCase):
    def test_strong_match(self):
        from jobpilot.models import UserProfile

        profile = UserProfile(
            skills=["python", "react", "aws", "redis"],
            experience_years=5,
            preferred_roles=["backend engineer"],
            remote_preference="remote",
        )
        job = JobListing(
            company="Co",
            title="Python Engineer",
            required_skills=["python", "react", "aws"],
            experience_years=3,
        )
        result = compute_match(profile, job)
        assert result.overall_score >= 0.6

    def test_poor_match(self):
        from jobpilot.models import UserProfile

        profile = UserProfile(skills=["cooking"], experience_years=1)
        job = JobListing(
            company="Co",
            title="Rust Engineer",
            required_skills=["rust", "c++", "go"],
            experience_years=8,
        )
        result = compute_match(profile, job)
        assert result.overall_score < 0.5

    def test_weights_sum(self):
        assert (
            abs(
                sum(
                    __import__("jobpilot.config", fromlist=["WEIGHTS"]).WEIGHTS.values()
                )
                - 1.0
            )
            < 0.001
        )

    def test_experience_score_capped(self):
        from jobpilot.models import UserProfile

        profile = UserProfile(experience_years=20)
        job = JobListing(company="Co", title="Dev", experience_years=2)
        result = compute_match(profile, job)
        assert result.experience_score <= 1.0


# =====================================================
# PDF PARSER TESTS
# =====================================================


class TestPdfParser(unittest.TestCase):
    def test_validate_upload_valid(self):
        from jobpilot.pdf_parser import validate_upload

        valid, msg = validate_upload(b"test content", "resume.txt")
        assert valid is True

    def test_validate_upload_empty(self):
        from jobpilot.pdf_parser import validate_upload

        valid, msg = validate_upload(b"", "resume.txt")
        assert valid is False

    def test_validate_upload_unsupported(self):
        from jobpilot.pdf_parser import validate_upload

        valid, msg = validate_upload(b"test", "resume.exe")
        assert valid is False

    def test_extract_text_from_txt(self):
        from jobpilot.pdf_parser import extract_text_from_file

        text = extract_text_from_file(b"Hello World\nTest Content", "test.txt")
        assert "Hello World" in text

    def test_generate_resume_id(self):
        from jobpilot.pdf_parser import generate_resume_id

        id1 = generate_resume_id(b"test content", "resume.txt")
        id2 = generate_resume_id(b"test content", "resume.txt")
        assert id1 == id2

    def test_get_file_type(self):
        from jobpilot.pdf_parser import get_file_type

        assert get_file_type("resume.pdf") == "pdf"
        assert get_file_type("resume.txt") == "txt"
        assert get_file_type("resume.md") == "txt"


# =====================================================
# COVER LETTER GENERATOR TESTS
# =====================================================


class TestCoverLetterGenerator(unittest.TestCase):
    def test_generate_professional(self):
        from jobpilot.cover_letter_generator import generate_cover_letter

        result = generate_cover_letter(
            resume_text="John Doe\nPython developer with 5 years experience.",
            job_description="Looking for a Python developer with Django experience.",
            company="TestCorp",
            role="Python Developer",
            tone="professional",
        )
        assert "letter_text" in result
        assert "TestCorp" in result["letter_text"]
        assert result["word_count"] > 50

    def test_generate_enthusiastic(self):
        from jobpilot.cover_letter_generator import generate_cover_letter

        result = generate_cover_letter(
            resume_text="Resume",
            job_description="Job",
            company="Co",
            role="Dev",
            tone="enthusiastic",
        )
        assert "letter_text" in result

    def test_tone_variations(self):
        from jobpilot.cover_letter_generator import generate_cover_letter

        r1 = generate_cover_letter("Resume", "Job", "Co", "Dev", tone="professional")
        r2 = generate_cover_letter("Resume", "Job", "Co", "Dev", tone="enthusiastic")
        assert r1["letter_text"] != r2["letter_text"]


# =====================================================
# SKILL GAP ANALYZER TESTS
# =====================================================


class TestSkillGapAnalyzer(unittest.TestCase):
    def test_matching_skills(self):
        from jobpilot.skill_gap_analyzer import analyze_skill_gap

        result = analyze_skill_gap(
            resume_skills=["python", "django"],
            job_required_skills=["python", "django", "docker"],
        )
        assert "python" in result["matched_skills"]
        assert "django" in result["matched_skills"]
        assert "docker" in result["missing_skills"]

    def test_match_percentage(self):
        from jobpilot.skill_gap_analyzer import analyze_skill_gap

        result = analyze_skill_gap(
            resume_skills=["python", "django", "docker"],
            job_required_skills=["python", "django", "docker"],
        )
        assert result["match_percentage"] == 100.0

    def test_empty_skills(self):
        from jobpilot.skill_gap_analyzer import analyze_skill_gap

        result = analyze_skill_gap(
            resume_skills=[],
            job_required_skills=["python", "django"],
        )
        assert result["match_percentage"] == 0.0
        assert len(result["missing_skills"]) == 2


# =====================================================
# LINKEDIN ANALYZER TESTS
# =====================================================


class TestLinkedInAnalyzer(unittest.TestCase):
    def test_analyze_profile(self):
        from jobpilot.linkedin_analyzer import analyze_linkedin_profile

        result = analyze_linkedin_profile(
            headline="Senior Software Engineer at TechCorp",
            about="I am a passionate developer with 5 years of experience.",
            skills="Python, Java, AWS",
            experience="Led team of 5 engineers.",
        )
        assert "visibility_score" in result
        assert "strength_score" in result
        assert result["visibility_score"] > 0

    def test_empty_profile(self):
        from jobpilot.linkedin_analyzer import analyze_linkedin_profile

        result = analyze_linkedin_profile()
        assert result["visibility_score"] == 0
        assert result["strength_score"] == 0


# =====================================================
# SALARY ESTIMATOR TESTS
# =====================================================


class TestSalaryEstimator(unittest.TestCase):
    def test_estimate_salary(self):
        from jobpilot.salary_estimator import SalaryEstimator

        estimator = SalaryEstimator()
        result = estimator.estimate(
            role="Software Engineer",
            location="San Francisco",
            skills=["python", "react", "aws"],
        )
        assert result["estimated_min"] > 0
        assert result["estimated_max"] > result["estimated_min"]
        assert result["currency"] == "USD"

    def test_location_multiplier(self):
        from jobpilot.salary_estimator import SalaryEstimator

        estimator = SalaryEstimator()
        sf = estimator.estimate(role="Software Engineer", location="San Francisco")
        remote = estimator.estimate(role="Software Engineer", location="Remote")
        assert sf["estimated_min"] > remote["estimated_min"]

    def test_skill_premium(self):
        from jobpilot.salary_estimator import SalaryEstimator

        estimator = SalaryEstimator()
        no_skills = estimator.estimate(role="Software Engineer", skills=[])
        with_ml = estimator.estimate(
            role="Software Engineer", skills=["machine learning", "python"]
        )
        assert with_ml["estimated_min"] > no_skills["estimated_min"]


# =====================================================
# CAREER ROADMAP TESTS
# =====================================================


class TestCareerRoadmap(unittest.TestCase):
    def test_generate_roadmap(self):
        from jobpilot.career_roadmap import CareerRoadmapGenerator

        generator = CareerRoadmapGenerator()
        roadmap = generator.generate_roadmap(goal_role="Backend Developer")
        assert "roadmap_data" in roadmap
        assert len(roadmap["roadmap_data"]) > 0
        assert "missing_skills" in roadmap

    def test_roadmap_phases(self):
        from jobpilot.career_roadmap import CareerRoadmapGenerator

        generator = CareerRoadmapGenerator()
        roadmap = generator.generate_roadmap(goal_role="ML Engineer")
        phases = [p["phase"] for p in roadmap["roadmap_data"]]
        assert "Projects & Portfolio" in phases
        assert "Interview Preparation" in phases
        assert "Job Applications" in phases


# =====================================================
# CAREER COACH TESTS
# =====================================================


class TestCareerCoach(unittest.TestCase):
    def test_ask_ats_question(self):
        from jobpilot.career_coach import CareerCoach

        coach = CareerCoach()
        result = coach.ask("Why is my ATS score low?")
        assert "answer" in result
        assert "ATS" in result["answer"]

    def test_ask_project_question(self):
        from jobpilot.career_coach import CareerCoach

        coach = CareerCoach()
        result = coach.ask("What projects should I add?")
        assert "answer" in result
        assert "Project" in result["answer"]

    def test_ask_salary_question(self):
        from jobpilot.career_coach import CareerCoach

        coach = CareerCoach()
        result = coach.ask("What salary should I expect?")
        assert "answer" in result
        assert "Salary" in result["answer"] or "salary" in result["answer"]


# =====================================================
# RESUME VERSION MANAGER TESTS
# =====================================================


class TestResumeVersionManager(unittest.TestCase):
    def test_create_version(self):
        from jobpilot.resume_version_manager import ResumeVersionManager

        manager = ResumeVersionManager()
        result = manager.create_version(
            user_id=1,
            name="Backend Resume",
            raw_text="John Doe\nPython developer with 5 years experience.",
        )
        assert "id" in result
        assert result["name"] == "Backend Resume"
        assert result["ats_score"] > 0

    def test_get_versions(self):
        import gc
        import os

        gc.collect()
        cleanup()
        from jobpilot.resume_version_manager import ResumeVersionManager

        manager = ResumeVersionManager()
        # Use unique user ID to avoid conflicts
        user_id = int.from_bytes(os.urandom(4), "big")
        manager.create_version(user_id=user_id, name="V1", raw_text="Resume v1")
        manager.create_version(user_id=user_id, name="V2", raw_text="Resume v2")
        versions = manager.get_versions(user_id)
        assert len(versions) == 2


# =====================================================
# COMPANY INTERVIEWS TESTS
# =====================================================


class TestCompanyInterviews(unittest.TestCase):
    def test_get_google_interview(self):
        from jobpilot.company_interviews import CompanyInterviewManager

        manager = CompanyInterviewManager()
        info = manager.get_interview_info("google")
        assert info["company"] == "Google"
        assert info["is_preloaded"] is True
        assert len(info["typical_rounds"]) > 0

    def test_get_unknown_company(self):
        from jobpilot.company_interviews import CompanyInterviewManager

        manager = CompanyInterviewManager()
        info = manager.get_interview_info("unknown_company")
        assert info["is_preloaded"] is False

    def test_get_all_companies(self):
        from jobpilot.company_interviews import CompanyInterviewManager

        manager = CompanyInterviewManager()
        companies = manager.get_all_companies()
        assert len(companies) >= 5
        assert "google" in companies


# =====================================================
# DATABASE CRUD TESTS
# =====================================================


class TestDatabase(unittest.TestCase):
    def test_job_crud(self):
        import gc, os

        gc.collect()
        cleanup()
        from jobpilot.models import JobListing

        url = f"http://test{os.urandom(4).hex()}.com"
        j = JobListing(company="Co", title="Dev", url=url, source="test")
        assert db.upsert_job(j, TEST_DB) is True
        fetched = db.get_job(j.id, TEST_DB)
        assert fetched is not None
        assert fetched.company == "Co"
        assert db.upsert_job(j, TEST_DB) is False  # Update

    def test_search_jobs(self):
        cleanup()
        from jobpilot.models import JobListing

        db.upsert_job(
            JobListing(
                company="PythonCo",
                title="Python Dev",
                url="http://a.com",
                source="test",
                description="python developer",
            ),
            TEST_DB,
        )
        db.upsert_job(
            JobListing(
                company="JavaCo", title="Java Dev", url="http://b.com", source="test"
            ),
            TEST_DB,
        )
        results = db.search_jobs(query="python", db_path=TEST_DB)
        assert len(results) == 1
        assert results[0].company == "PythonCo"

    def test_application_lifecycle(self):
        cleanup()
        from jobpilot.models import JobListing, Application

        j = JobListing(company="Co", title="Dev", url="http://t.com", source="test")
        db.upsert_job(j, TEST_DB)
        app = Application(job_id=j.id, company="Co", role="Dev", status="discovered")
        db.upsert_application(app, TEST_DB)
        apps = db.get_applications(db_path=TEST_DB)
        assert len(apps) == 1
        db.update_application_status(app.id, "applied", TEST_DB)
        apps = db.get_applications(db_path=TEST_DB)
        assert apps[0].status == "applied"

    def test_resume_crud(self):
        cleanup()
        r = Resume(
            id="r1", name="test", filename="t.txt", raw_text="hello", target_role="dev"
        )
        db.upsert_resume(r, TEST_DB)
        fetched = db.get_resume("r1", TEST_DB)
        assert fetched is not None
        assert fetched.raw_text == "hello"

    def test_notification_crud(self):
        import gc, os

        gc.collect()
        cleanup()
        from jobpilot.models import JobListing

        j = JobListing(
            company="Co",
            title="Dev",
            url=f"http://t{os.urandom(2).hex()}.com",
            source="test",
        )
        db.upsert_job(j, TEST_DB)
        notif_id = db.create_job_notification(j.id, "new_match", "Test", 0.85, TEST_DB)
        assert notif_id > 0
        notifs = db.get_job_notifications(db_path=TEST_DB)
        assert len(notifs) >= 1

    def test_alert_subscription_crud(self):
        cleanup()
        from jobpilot.models import AlertSubscription

        alert = AlertSubscription(role="Python", location="Remote")
        alert_id = db.save_alert_subscription(alert, TEST_DB)
        alerts = db.get_alert_subscriptions(TEST_DB)
        assert len(alerts) == 1
        db.update_alert_subscription(alert_id, {"frequency": "weekly"}, TEST_DB)
        alerts = db.get_alert_subscriptions(TEST_DB)
        assert alerts[0]["frequency"] == "weekly"
        db.delete_alert_subscription(alert_id, TEST_DB)
        assert len(db.get_alert_subscriptions(TEST_DB)) == 0

    def test_roadmap_crud(self):
        import gc, os

        gc.collect()
        cleanup()
        user_id = int.from_bytes(os.urandom(4), "big")
        roadmap_id = db.save_roadmap(
            user_id=user_id,
            goal_role="Backend Dev",
            goal_company="Google",
            current_skills=["python"],
            missing_skills=["docker"],
            roadmap_data=[],
            estimated_weeks=12,
            db_path=TEST_DB,
        )
        roadmaps = db.get_roadmaps(user_id, TEST_DB)
        assert len(roadmaps) == 1
        db.update_roadmap_status(roadmap_id, "completed", TEST_DB)
        roadmaps = db.get_roadmaps(user_id, TEST_DB)
        assert roadmaps[0]["status"] == "completed"

    def test_salary_estimate_crud(self):
        import gc, os

        gc.collect()
        cleanup()
        role = f"Engineer_{os.urandom(4).hex()}"
        db.save_salary_estimate(
            role=role,
            company="Google",
            location="SF",
            experience_level="senior",
            skills=["python"],
            estimated_min=150000,
            estimated_max=200000,
            currency="USD",
            confidence=0.8,
            data_source="test",
            db_path=TEST_DB,
        )
        estimates = db.get_salary_estimates(role=role, db_path=TEST_DB)
        assert len(estimates) == 1
        assert estimates[0]["estimated_min"] == 150000

    def test_cover_letter_crud(self):
        cleanup()
        from jobpilot.models import CoverLetter

        cl = CoverLetter(
            company_name="Co", role_title="Dev", letter_text="Dear Hiring Manager..."
        )
        letter_id = db.save_cover_letter(cl, TEST_DB)
        assert letter_id > 0
        letters = db.get_cover_letters(TEST_DB)
        assert len(letters) == 1
        db.delete_cover_letter(letter_id, TEST_DB)
        assert len(db.get_cover_letters(TEST_DB)) == 0

    def test_skill_gap_report_crud(self):
        import gc

        gc.collect()
        cleanup()
        from jobpilot.models import SkillGapReport

        report = SkillGapReport(
            matched_skills=["python"],
            missing_skills=["docker"],
            match_percentage=50.0,
            learning_areas=["DevOps"],
        )
        report_id = db.save_skill_gap_report(report, TEST_DB)
        assert report_id > 0
        reports = db.get_skill_gap_reports(TEST_DB)
        assert len(reports) >= 1

    def test_linkedin_report_crud(self):
        import gc, os

        gc.collect()
        cleanup()
        from jobpilot.models import LinkedInReport

        report = LinkedInReport(
            headline=f"Engineer_{os.urandom(4).hex()}",
            visibility_score=75.0,
            strength_score=80.0,
        )
        report_id = db.save_linkedin_report(report, TEST_DB)
        assert report_id > 0
        reports = db.get_linkedin_reports(TEST_DB)
        assert len(reports) >= 1

    def test_tailored_resume_crud(self):
        cleanup()
        from jobpilot.models import TailoredResume

        tr = TailoredResume(
            original_text="Original",
            tailored_text="Tailored",
            original_score=0.5,
            tailored_score=0.8,
            improvement_pct=60.0,
        )
        tr_id = db.save_tailored_resume(tr, TEST_DB)
        assert tr_id > 0
        trs = db.get_tailored_resumes(TEST_DB)
        assert len(trs) == 1
        db.delete_tailored_resume(tr_id, TEST_DB)
        assert len(db.get_tailored_resumes(TEST_DB)) == 0

    def test_verification_flow(self):
        import gc

        # Force cleanup of any open connections
        gc.collect()
        cleanup()
        # Use a unique entity_id to avoid conflicts
        entity_id = f"verify_{id(self)}"
        db.log_verification_event(
            "profile", entity_id, "profile_verification_requested", db_path=TEST_DB
        )
        db.log_verification_event(
            "profile", entity_id, "profile_verification_accepted", db_path=TEST_DB
        )
        events = db.get_verification_events("profile", entity_id, TEST_DB)
        assert len(events) == 2
        status = db.get_latest_verification_status("profile", entity_id, TEST_DB)
        assert status["is_verified"] is True

    def test_user_management(self):
        import os

        cleanup()
        unique_email = f"test_{os.urandom(4).hex()}@example.com"
        user_id = db.create_user(unique_email, "hashedpass", "Test User", TEST_DB)
        assert user_id > 0
        user = db.get_user_by_email(unique_email, TEST_DB)
        assert user is not None
        assert user["name"] == "Test User"
        db.update_user(user_id, {"name": "Updated User"}, TEST_DB)
        user = db.get_user_by_id(user_id, TEST_DB)
        assert user["name"] == "Updated User"


# =====================================================
# SECURITY TESTS
# =====================================================


class TestSecurity(unittest.TestCase):
    def test_sql_injection_prevention(self):
        from jobpilot.security import sanitize_input

        malicious = "<script>'; DROP TABLE users; --</script>"
        sanitized = sanitize_input(malicious)
        # HTML tags should be removed from input
        assert "<script>" not in sanitized, "Script tags should be removed"

    def test_xss_prevention(self):
        from jobpilot.security import sanitize_input

        xss = "<script>alert('xss')</script>"
        sanitized = sanitize_input(xss)
        assert "<script>" not in sanitized, "Script tags should be removed"

    def test_password_strength_requirements(self):
        from jobpilot.security import validate_password

        # Too short
        valid, _ = validate_password("abc")
        assert valid is False
        # No uppercase
        valid, _ = validate_password("alllowercase123!")
        assert valid is False
        # No lowercase
        valid, _ = validate_password("ALLUPPERCASE123!")
        assert valid is False
        # No digit
        valid, _ = validate_password("NoDigitsHere!")
        assert valid is False
        # Valid
        valid, _ = validate_password("ValidPass123!")
        assert valid is True

    def test_jwt_token_expiry(self):
        from jobpilot.auth import create_access_token
        from jose import jwt
        from jobpilot.auth import SECRET_KEY, ALGORITHM

        token = create_access_token(data={"sub": 1})
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert "exp" in payload

    def test_file_upload_validation(self):
        from jobpilot.security import validate_file_upload

        # Valid file
        valid, _ = validate_file_upload("resume.pdf", "application/pdf", 1024)
        assert valid is True
        # Invalid extension
        valid, _ = validate_file_upload("resume.exe", "application/octet-stream", 1024)
        assert valid is False
        # Too large
        valid, _ = validate_file_upload(
            "resume.pdf", "application/pdf", 20 * 1024 * 1024
        )
        assert valid is False


# =====================================================
# RUN ALL TESTS
# =====================================================


def cleanup():
    TEST_DB = Path(__file__).resolve().parent / "test_qa.db"
    if TEST_DB.exists():
        TEST_DB.unlink()


if __name__ == "__main__":
    # Run all test classes
    import unittest

    # Create a test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    test_classes = [
        TestModels,
        TestAuth,
        TestResumeAnalyzer,
        TestMatcher,
        TestPdfParser,
        TestCoverLetterGenerator,
        TestSkillGapAnalyzer,
        TestLinkedInAnalyzer,
        TestSalaryEstimator,
        TestCareerRoadmap,
        TestCareerCoach,
        TestResumeVersionManager,
        TestCompanyInterviews,
        TestDatabase,
        TestSecurity,
    ]

    for test_class in test_classes:
        suite.addTests(loader.loadTestsFromTestCase(test_class))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print(f"\n{'='*60}")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"{'='*60}")

    if result.failures:
        print("\nFailures:")
        for test, trace in result.failures:
            print(f"  {test}: {trace}")

    if result.errors:
        print("\nErrors:")
        for test, trace in result.errors:
            print(f"  {test}: {trace}")

    sys.exit(0 if result.wasSuccessful() else 1)
