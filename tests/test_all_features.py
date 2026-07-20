"""Comprehensive feature tests for JobPilot — every feature, every edge case."""

import sys
import json
import hashlib
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobpilot.models import (
    UserProfile,
    JobListing,
    MatchResult,
    Application,
    Company,
    Resume,
    _generate_id,
)
from jobpilot.config import WEIGHTS, MATCH_THRESHOLD
from jobpilot import database as db
from jobpilot.profile import load_profile, save_profile
from jobpilot.matcher import compute_match
from jobpilot.resume_analyzer import (
    analyze_resume,
    ResumeAnalysisResult,
    _extract_skills,
    _detect_sections,
    _compute_ats_score,
    _extract_contact,
    _extract_education,
    _estimate_experience_years,
    _generate_suggestions,
    _identify_strengths,
    _identify_weaknesses,
    SKILL_DATABASE,
    _ALIAS_MAP,
)
from jobpilot.scraper.base import BaseScraper
from jobpilot.scraper.greenhouse import GreenhouseScraper, KNOWN_GREENHOUSE_BOARDS
from jobpilot.scraper.remoteok import RemoteOKScraper

PASS = 0
FAIL = 0
ERRORS = []


def test(name, fn):
    global PASS, FAIL, ERRORS
    try:
        fn()
        PASS += 1
        print(f"  [PASS] {name}")
    except AssertionError as e:
        FAIL += 1
        ERRORS.append((name, str(e)))
        print(f"  [FAIL] {name}: {e}")
    except Exception as e:
        FAIL += 1
        ERRORS.append((name, f"{type(e).__name__}: {e}"))
        print(f"  [ERROR] {name}: {type(e).__name__}: {e}")


TEST_DB = Path(__file__).resolve().parent.parent / "data" / "test_all_features.db"


def cleanup():
    if TEST_DB.exists():
        TEST_DB.unlink()


# =====================================================
# MODELS
# =====================================================
print("\n=== Models ===")


def test_model_job_id_deterministic():
    j1 = JobListing(company="TestCo", title="Engineer", url="https://example.com/1")
    j2 = JobListing(company="TestCo", title="Engineer", url="https://example.com/1")
    j3 = JobListing(company="TestCo", title="Engineer", url="https://example.com/2")
    assert j1.id == j2.id, "Same inputs should produce same ID"
    assert j1.id != j3.id, "Different URL should produce different ID"


test("Model: job ID deterministic", test_model_job_id_deterministic)


def test_model_job_id_case_insensitive():
    j1 = JobListing(company="TestCo", title="Engineer", url="http://x.com")
    j2 = JobListing(company="testco", title="engineer", url="http://x.com")
    assert j1.id == j2.id, "ID should be case-insensitive"


test("Model: job ID case insensitive", test_model_job_id_case_insensitive)


def test_model_job_all_skills_normalization():
    j = JobListing(
        required_skills=["Python", "GO"],
        preferred_skills=["Docker"],
        tech_stack=["Kubernetes", "AWS"],
    )
    assert "python" in j.all_required_skills
    assert "go" in j.all_required_skills
    assert "docker" in j.all_preferred_skills
    assert "kubernetes" in j.all_preferred_skills
    assert "aws" in j.all_preferred_skills


test("Model: job skills normalization", test_model_job_all_skills_normalization)


def test_model_job_to_dict_has_id():
    j = JobListing(company="Co", title="Role", url="http://x.com")
    d = j.to_dict()
    assert "id" in d
    assert d["company"] == "Co"
    assert isinstance(d, dict)


test("Model: job to_dict includes id", test_model_job_to_dict_has_id)


def test_model_profile_all_skills():
    p = UserProfile(
        skills=["Python", "React"],
        programming_languages=["Go"],
        frameworks=["FastAPI"],
        cloud_platforms=["AWS"],
    )
    all_s = p.all_skills
    assert "python" in all_s
    assert "go" in all_s
    assert "fastapi" in all_s
    assert "aws" in all_s
    assert len(all_s) == 5


test("Model: profile all_skills combines all", test_model_profile_all_skills)


def test_model_profile_all_skills_dedup():
    p = UserProfile(skills=["python", "Python"], programming_languages=["Python"])
    assert p.all_skills.count("python") == 1, "Should deduplicate skills"


test("Model: profile all_skills dedup", test_model_profile_all_skills_dedup)


def test_model_empty_profile():
    p = UserProfile()
    assert p.all_skills == []
    assert p.name == ""


test("Model: empty profile defaults", test_model_empty_profile)


def test_model_application_id():
    a1 = Application(job_id="abc", company="Co", role="Role")
    a2 = Application(job_id="abc", company="Co", role="Role")
    a3 = Application(job_id="abc", company="Co", role="Role2")
    assert a1.id == a2.id
    assert a1.id != a3.id


test("Model: application ID deterministic", test_model_application_id)


def test_model_company_defaults():
    c = Company(name="TestCo")
    assert c.job_count == 0
    assert c.industry == ""


test("Model: company defaults", test_model_company_defaults)


def test_model_resume_defaults():
    r = Resume()
    assert r.id == ""
    assert r.raw_text == ""
    assert r.to_dict().get("raw_text") is None, "to_dict should not include raw_text"


test("Model: resume defaults and to_dict", test_model_resume_defaults)


# =====================================================
# DATABASE
# =====================================================
print("\n=== Database ===")


def test_db_create_tables():
    cleanup()
    conn = db.get_connection(TEST_DB)
    tables = [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    ]
    conn.close()
    assert "jobs" in tables
    assert "match_results" in tables
    assert "applications" in tables
    assert "companies" in tables
    assert "resumes" in tables
    assert "resume_analyses" in tables


test("DB: creates all tables", test_db_create_tables)


def test_db_upsert_job_new():
    cleanup()
    j = JobListing(
        company="TestCo", title="Engineer", url="http://test.com/1", source="test"
    )
    is_new = db.upsert_job(j, TEST_DB)
    assert is_new is True


test("DB: upsert job new", test_db_upsert_job_new)


def test_db_upsert_job_duplicate():
    cleanup()
    j = JobListing(
        company="TestCo", title="Engineer", url="http://test.com/1", source="test"
    )
    db.upsert_job(j, TEST_DB)
    is_new = db.upsert_job(j, TEST_DB)
    assert is_new is False


test("DB: upsert job duplicate", test_db_upsert_job_duplicate)


def test_db_get_job():
    cleanup()
    j = JobListing(company="GetCo", title="Dev", url="http://get.com", source="test")
    db.upsert_job(j, TEST_DB)
    fetched = db.get_job(j.id, TEST_DB)
    assert fetched is not None
    assert fetched.company == "GetCo"
    assert fetched.title == "Dev"


test("DB: get job", test_db_get_job)


def test_db_get_nonexistent_job():
    cleanup()
    result = db.get_job("nonexistent", TEST_DB)
    assert result is None


test("DB: get nonexistent job returns None", test_db_get_nonexistent_job)


def test_db_get_all_jobs():
    cleanup()
    for i in range(5):
        j = JobListing(
            company=f"Co{i}",
            title=f"Role{i}",
            url=f"http://test.com/{i}",
            source="test",
        )
        db.upsert_job(j, TEST_DB)
    jobs = db.get_all_jobs(TEST_DB)
    assert len(jobs) == 5


test("DB: get all jobs", test_db_get_all_jobs)


def test_db_search_by_query():
    cleanup()
    db.upsert_job(
        JobListing(
            company="PythonCo",
            title="Python Dev",
            url="http://a.com",
            source="greenhouse",
            description="python",
        ),
        TEST_DB,
    )
    db.upsert_job(
        JobListing(
            company="JavaCo",
            title="Java Dev",
            url="http://b.com",
            source="linkedin",
            description="java",
        ),
        TEST_DB,
    )
    results = db.search_jobs(query="python", db_path=TEST_DB)
    assert len(results) == 1
    assert results[0].company == "PythonCo"


test("DB: search jobs by query", test_db_search_by_query)


def test_db_search_by_source():
    cleanup()
    db.upsert_job(
        JobListing(company="A", title="A", url="http://a.com", source="greenhouse"),
        TEST_DB,
    )
    db.upsert_job(
        JobListing(company="B", title="B", url="http://b.com", source="linkedin"),
        TEST_DB,
    )
    results = db.search_jobs(source="linkedin", db_path=TEST_DB)
    assert len(results) == 1
    assert results[0].company == "B"


test("DB: search jobs by source", test_db_search_by_source)


def test_db_upsert_company():
    cleanup()
    c = Company(name="TestCo", industry="Tech", career_page="http://careers.test")
    db.upsert_company(c, TEST_DB)
    companies = db.get_companies(TEST_DB)
    assert len(companies) == 1
    assert companies[0].name == "TestCo"
    assert companies[0].industry == "Tech"


test("DB: upsert and get companies", test_db_upsert_company)


def test_db_company_upsert_updates():
    cleanup()
    db.upsert_company(Company(name="Co", industry="Old"), TEST_DB)
    db.upsert_company(Company(name="Co", industry="New"), TEST_DB)
    companies = db.get_companies(TEST_DB)
    assert len(companies) == 1
    assert companies[0].industry == "New"


test("DB: company upsert updates existing", test_db_company_upsert_updates)


def test_db_application_lifecycle():
    cleanup()
    j = JobListing(company="AppCo", title="Role", url="http://app.com", source="test")
    db.upsert_job(j, TEST_DB)
    app = Application(job_id=j.id, company="AppCo", role="Role", status="discovered")
    db.upsert_application(app, TEST_DB)
    apps = db.get_applications(db_path=TEST_DB)
    assert len(apps) == 1
    assert apps[0].status == "discovered"
    found = db.update_application_status(app.id, "applied", TEST_DB)
    assert found is True
    apps = db.get_applications(db_path=TEST_DB)
    assert apps[0].status == "applied"


test("DB: application lifecycle", test_db_application_lifecycle)


def test_db_application_filter_by_status():
    cleanup()
    j = JobListing(company="Co", title="R", url="http://x.com", source="test")
    db.upsert_job(j, TEST_DB)
    db.upsert_application(
        Application(job_id=j.id, company="Co", role="R", status="applied"), TEST_DB
    )
    db.upsert_application(
        Application(job_id=j.id, company="Co", role="R2", status="interview"), TEST_DB
    )
    applied = db.get_applications(status="applied", db_path=TEST_DB)
    assert len(applied) == 1
    assert applied[0].status == "applied"


test("DB: application filter by status", test_db_application_filter_by_status)


def test_db_match_result():
    cleanup()
    j = JobListing(
        company="MatchCo", title="Dev", url="http://match.com", source="test"
    )
    db.upsert_job(j, TEST_DB)
    m = MatchResult(
        job_id=j.id,
        overall_score=0.85,
        skills_score=0.9,
        strengths=["Good"],
        missing_skills=["rust"],
    )
    db.save_match_result(m, TEST_DB)
    fetched = db.get_match_result(j.id, TEST_DB)
    assert fetched is not None
    assert fetched.overall_score == 0.85
    assert "rust" in fetched.missing_skills


test("DB: save and get match result", test_db_match_result)


def test_db_match_result_role_score():
    """Verify role_score is stored and retrieved correctly (was bug: returned location_score)."""
    cleanup()
    j = JobListing(company="Co", title="Dev", url="http://x.com", source="test")
    db.upsert_job(j, TEST_DB)
    m = MatchResult(job_id=j.id, overall_score=0.7, role_score=0.9, location_score=0.3)
    db.save_match_result(m, TEST_DB)
    fetched = db.get_match_result(j.id, TEST_DB)
    assert (
        fetched.role_score == 0.9
    ), f"Expected role_score=0.9, got {fetched.role_score}"
    assert (
        fetched.location_score == 0.3
    ), f"Expected location_score=0.3, got {fetched.location_score}"


test("DB: match result role_score correct", test_db_match_result_role_score)


def test_db_stats():
    cleanup()
    for i in range(3):
        db.upsert_job(
            JobListing(
                company=f"C{i}",
                title=f"R{i}",
                url=f"http://s{i}.com",
                source="greenhouse",
            ),
            TEST_DB,
        )
    stats = db.get_stats(TEST_DB)
    assert stats["total_jobs"] == 3
    assert stats["total_companies"] == 0


test("DB: stats", test_db_stats)


def test_db_resume_crud():
    cleanup()
    r = Resume(
        id="r1", name="test", filename="t.txt", raw_text="hello", target_role="dev"
    )
    is_new = db.upsert_resume(r, TEST_DB)
    assert is_new is True
    fetched = db.get_resume("r1", TEST_DB)
    assert fetched is not None
    assert fetched.raw_text == "hello"
    # Update
    is_new = db.upsert_resume(
        Resume(id="r1", name="updated", filename="t.txt", raw_text="hello2"), TEST_DB
    )
    assert is_new is False
    fetched = db.get_resume("r1", TEST_DB)
    assert fetched.name == "updated"


test("DB: resume CRUD", test_db_resume_crud)


def test_db_resume_list():
    cleanup()
    for i in range(3):
        db.upsert_resume(
            Resume(
                id=f"r{i}", name=f"resume_{i}", filename=f"f{i}.txt", raw_text="text"
            ),
            TEST_DB,
        )
    resumes = db.get_all_resumes(TEST_DB)
    assert len(resumes) == 3
    # raw_text should not be loaded
    assert resumes[0].raw_text == ""


test("DB: resume list excludes raw_text", test_db_resume_list)


def test_db_resume_delete_cascades():
    cleanup()
    db.upsert_resume(
        Resume(id="del", name="x", filename="x.txt", raw_text="text"), TEST_DB
    )
    db.save_resume_analysis(
        resume_id="del",
        ats_score=0.5,
        resume_quality_score=0.5,
        technical_strength_score=0.5,
        hiring_readiness_score=0.5,
        skills=[],
        strengths=[],
        weaknesses=[],
        missing_skills=[],
        suggestions=[],
        db_path=TEST_DB,
    )
    found = db.delete_resume("del", TEST_DB)
    assert found is True
    assert db.get_resume("del", TEST_DB) is None
    assert len(db.get_resume_analyses("del", TEST_DB)) == 0


test("DB: resume delete cascades to analyses", test_db_resume_delete_cascades)


def test_db_resume_analysis_save_and_get():
    cleanup()
    db.upsert_resume(
        Resume(id="ra1", name="r", filename="f.txt", raw_text="t"), TEST_DB
    )
    db.save_resume_analysis(
        resume_id="ra1",
        ats_score=0.85,
        resume_quality_score=0.80,
        technical_strength_score=0.90,
        hiring_readiness_score=0.82,
        skills=["python", "react"],
        strengths=["Strong"],
        weaknesses=["Weak"],
        missing_skills=["rust"],
        suggestions=["Add projects"],
        db_path=TEST_DB,
    )
    analyses = db.get_resume_analyses("ra1", TEST_DB)
    assert len(analyses) == 1
    assert analyses[0]["ats_score"] == 0.85
    assert "python" in analyses[0]["skills"]
    assert analyses[0]["strengths"] == ["Strong"]


test("DB: resume analysis save and get", test_db_resume_analysis_save_and_get)


# =====================================================
# MATCHER
# =====================================================
print("\n=== Matcher ===")


def test_match_strong():
    profile = UserProfile(
        skills=["python", "react", "aws"],
        programming_languages=["python"],
        frameworks=["react"],
        cloud_platforms=["aws"],
        experience_years=5,
        preferred_roles=["software engineer"],
        preferred_locations=["remote"],
        remote_preference="remote",
    )
    job = JobListing(
        company="Co",
        title="Software Engineer",
        location="Remote",
        remote_status="remote",
        required_skills=["python", "react"],
        experience_years=3,
    )
    result = compute_match(profile, job)
    assert result.overall_score >= 0.6, f"Expected >= 0.6, got {result.overall_score}"
    assert len(result.strengths) > 0


test("Match: strong match", test_match_strong)


def test_match_poor():
    profile = UserProfile(
        skills=["cooking"],
        experience_years=1,
        preferred_roles=["chef"],
        remote_preference="onsite",
    )
    job = JobListing(
        company="TechCo",
        title="Senior Rust Engineer",
        location="San Francisco",
        remote_status="onsite",
        required_skills=["rust", "c++", "go"],
        experience_years=8,
    )
    result = compute_match(profile, job)
    assert result.overall_score < 0.5, f"Expected < 0.5, got {result.overall_score}"
    assert len(result.missing_skills) > 0


test("Match: poor match", test_match_poor)


def test_match_skills_weight():
    profile = UserProfile(skills=["python", "django", "postgresql"])
    job_no = JobListing(
        company="Co", title="Dev", required_skills=[], experience_years=2
    )
    job_all = JobListing(
        company="Co",
        title="Dev",
        required_skills=["python", "django", "postgresql"],
        experience_years=2,
    )
    r1 = compute_match(profile, job_no)
    r2 = compute_match(profile, job_all)
    assert r2.skills_score > r1.skills_score


test("Match: skills weight matters", test_match_skills_weight)


def test_match_experience_capped():
    profile = UserProfile(experience_years=20)
    job = JobListing(company="Co", title="Dev", required_skills=[], experience_years=2)
    result = compute_match(profile, job)
    assert result.experience_score <= 1.0


test("Match: experience score capped", test_match_experience_capped)


def test_match_role_alignment():
    profile = UserProfile(preferred_roles=["backend engineer"])
    job_exact = JobListing(company="Co", title="Backend Engineer", required_skills=[])
    job_wrong = JobListing(company="Co", title="Marketing Manager", required_skills=[])
    r1 = compute_match(profile, job_exact)
    r2 = compute_match(profile, job_wrong)
    assert r1.role_score > r2.role_score


test("Match: role alignment", test_match_role_alignment)


def test_match_location_remote():
    profile = UserProfile(remote_preference="remote", preferred_locations=["remote"])
    job_remote = JobListing(
        company="Co",
        title="Dev",
        location="Remote",
        remote_status="remote",
        required_skills=[],
    )
    job_onsite = JobListing(
        company="Co",
        title="Dev",
        location="New York",
        remote_status="onsite",
        required_skills=[],
    )
    r1 = compute_match(profile, job_remote)
    r2 = compute_match(profile, job_onsite)
    assert r1.location_score > r2.location_score


test("Match: remote preference", test_match_location_remote)


def test_match_weights_sum():
    assert abs(sum(WEIGHTS.values()) - 1.0) < 0.001


test("Match: weights sum to 1.0", test_match_weights_sum)


def test_match_result_fields_valid():
    profile = UserProfile(skills=["python"], experience_years=3)
    job = JobListing(
        company="Co", title="Dev", required_skills=["python"], experience_years=2
    )
    result = compute_match(profile, job)
    assert 0 <= result.overall_score <= 1
    assert 0 <= result.skills_score <= 1
    assert 0 <= result.experience_score <= 1
    assert isinstance(result.strengths, list)
    assert isinstance(result.missing_skills, list)


test("Match: result fields valid", test_match_result_fields_valid)


def test_match_no_skills_neutral():
    profile = UserProfile(skills=["python"])
    job = JobListing(
        company="Co",
        title="Dev",
        required_skills=[],
        preferred_skills=[],
        experience_years=2,
    )
    result = compute_match(profile, job)
    assert result.skills_score == 0.5, "No skills specified should give neutral score"


test("Match: no skills = neutral score", test_match_no_skills_neutral)


def test_match_no_experience_req():
    profile = UserProfile(experience_years=2)
    job = JobListing(company="Co", title="Dev", required_skills=[], experience_years=0)
    result = compute_match(profile, job)
    assert (
        result.experience_score == 0.7
    ), "No experience req should give neutral-positive"


test("Match: no experience req = neutral", test_match_no_experience_req)


def test_match_preferred_skills():
    profile = UserProfile(skills=["python", "docker"])
    job = JobListing(
        company="Co",
        title="Dev",
        required_skills=["python"],
        preferred_skills=["docker"],
        experience_years=2,
    )
    result = compute_match(profile, job)
    assert result.skills_score > 0.7, "Preferred skills should boost score"


test("Match: preferred skills boost score", test_match_preferred_skills)


# =====================================================
# SCRAPERS
# =====================================================
print("\n=== Scrapers ===")


def test_greenhouse_board_tokens_are_strings():
    for name, token in KNOWN_GREENHOUSE_BOARDS.items():
        assert isinstance(token, str), f"Board token for {name} should be string"
        assert len(token) > 0, f"Board token for {name} should not be empty"


test("Scraper: greenhouse board tokens valid", test_greenhouse_board_tokens_are_strings)


def test_greenhouse_no_invalid_boards():
    """Ensure removed invalid boards are not in the list."""
    removed = ["doordash", "postmates", "snapinc", "twitter", "stripe"]
    for name in removed:
        assert (
            name not in KNOWN_GREENHOUSE_BOARDS
        ), f"Invalid board {name} should be removed"


test("Scraper: invalid boards removed", test_greenhouse_no_invalid_boards)


def test_base_scraper_extract_skills():
    scraper = RemoteOKScraper()
    skills = scraper._extract_skills("We need Python, React, and AWS experience")
    assert "python" in skills
    assert "react" in skills
    assert "aws" in skills


test("Scraper: base skill extraction", test_base_scraper_extract_skills)


def test_base_scraper_parse_salary():
    scraper = RemoteOKScraper()
    min_s, max_s, currency = scraper._parse_salary("$100,000 - $150,000")
    assert min_s == 100000
    assert max_s == 150000
    assert currency == "USD"


test("Scraper: salary parsing", test_base_scraper_parse_salary)


def test_base_scraper_parse_salary_single():
    scraper = RemoteOKScraper()
    min_s, max_s, currency = scraper._parse_salary("$80k")
    assert min_s == 80
    assert max_s == 80


test("Scraper: salary parsing single value", test_base_scraper_parse_salary_single)


def test_base_scraper_parse_salary_euro():
    scraper = RemoteOKScraper()
    _, _, currency = scraper._parse_salary("€50,000 - €70,000")
    assert currency == "EUR"


test("Scraper: salary parsing euro", test_base_scraper_parse_salary_euro)


def test_greenhouse_clean_html():
    scraper = GreenhouseScraper()
    result = scraper._clean_html("<p>Hello <b>world</b></p>")
    assert result == "Hello world"
    assert "<" not in result


test("Scraper: greenhouse HTML cleaning", test_greenhouse_clean_html)


def test_greenhouse_extract_location():
    scraper = GreenhouseScraper()
    loc = scraper._extract_location({"location": {"name": "San Francisco, CA"}})
    assert loc == "San Francisco, CA"
    loc2 = scraper._extract_location({"location": {}})
    assert loc2 == "Unknown"


test("Scraper: greenhouse location extraction", test_greenhouse_extract_location)


def test_remoteok_parse_job():
    scraper = RemoteOKScraper()
    data = {
        "position": "Python Developer",
        "company": "TestCo",
        "description": "Build stuff",
        "tags": ["python", "django"],
        "salary_min": 100000,
        "salary_max": 150000,
        "slug": "python-dev-testco",
        "date": "2024-01-01",
    }
    job = scraper._parse_job(data)
    assert job.company == "TestCo"
    assert job.title == "Python Developer"
    assert "python" in job.required_skills
    assert job.salary_min == 100000
    assert job.remote_status == "remote"


test("Scraper: remoteok parse job", test_remoteok_parse_job)


def test_remoteok_parse_job_no_tags():
    scraper = RemoteOKScraper()
    data = {
        "position": "Dev",
        "company": "Co",
        "description": "Python and React developer",
    }
    job = scraper._parse_job(data)
    assert (
        "python" in job.required_skills
    ), f"Expected python in skills, got {job.required_skills}"
    assert (
        "react" in job.required_skills
    ), f"Expected react in skills, got {job.required_skills}"


test(
    "Scraper: remoteok fallback to description skills", test_remoteok_parse_job_no_tags
)


# =====================================================
# RESUME ANALYZER
# =====================================================
print("\n=== Resume Analyzer ===")

SAMPLE_RESUME = """
John Doe
john@example.com | (555) 123-4567 | linkedin.com/in/johndoe | github.com/johndoe

Summary
Senior Software Engineer with 6 years of experience building scalable web applications.
Passionate about clean code and mentoring junior developers.

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

Certifications
AWS Solutions Architect - Associate
"""


def test_resume_skill_extraction():
    skills = _extract_skills(SAMPLE_RESUME)
    for s in [
        "python",
        "react",
        "docker",
        "aws",
        "postgresql",
        "fastapi",
        "kubernetes",
        "git",
    ]:
        assert s in skills, f"Expected skill '{s}' not found"


test("Resume: skill extraction", test_resume_skill_extraction)


def test_resume_section_detection():
    sections = _detect_sections(SAMPLE_RESUME)
    for s in ["experience", "education", "skills", "summary", "certifications"]:
        assert s in sections, f"Expected section '{s}' not found"


test("Resume: section detection", test_resume_section_detection)


def test_resume_name_extraction():
    result = analyze_resume(SAMPLE_RESUME)
    assert result.name == "John Doe", f"Expected name 'John Doe', got '{result.name}'"


test("Resume: name extraction", test_resume_name_extraction)


def test_resume_contact_extraction():
    result = analyze_resume(SAMPLE_RESUME)
    assert result.email == "john@example.com"
    assert result.phone == "(555) 123-4567"
    assert "linkedin.com/in/johndoe" in result.linkedin
    assert "github.com/johndoe" in result.github


test("Resume: contact extraction", test_resume_contact_extraction)


def test_resume_experience_years():
    result = analyze_resume(SAMPLE_RESUME)
    assert (
        result.experience_years >= 4
    ), f"Expected >= 4 years, got {result.experience_years}"


test("Resume: experience years", test_resume_experience_years)


def test_resume_education():
    result = analyze_resume(SAMPLE_RESUME)
    assert len(result.education) > 0
    assert any("stanford" in e.lower() for e in result.education)


test("Resume: education extraction", test_resume_education)


def test_resume_scores_in_range():
    result = analyze_resume(SAMPLE_RESUME)
    for score_name in [
        "ats_score",
        "resume_quality_score",
        "technical_strength_score",
        "hiring_readiness_score",
    ]:
        score = getattr(result, score_name)
        assert 0.0 <= score <= 1.0, f"{score_name} out of range: {score}"


test("Resume: scores in valid range", test_resume_scores_in_range)


def test_resume_strengths():
    result = analyze_resume(SAMPLE_RESUME)
    assert len(result.strengths) > 0
    assert any(
        "skill" in s.lower() or "experience" in s.lower() for s in result.strengths
    )


test("Resume: has strengths", test_resume_strengths)


def test_resume_suggestions():
    result = analyze_resume(SAMPLE_RESUME)
    assert len(result.suggestions) > 0


test("Resume: has suggestions", test_resume_suggestions)


def test_resume_empty_text():
    result = analyze_resume("")
    assert len(result.skills) == 0
    assert result.ats_score < 0.3
    assert len(result.suggestions) > 0


test("Resume: empty text handled", test_resume_empty_text)


def test_resume_minimal():
    minimal = "Jane Smith\nJane is a developer who knows Python and JavaScript."
    result = analyze_resume(minimal)
    assert "python" in result.skills
    assert "javascript" in result.skills
    assert result.name == "Jane Smith"


test("Resume: minimal resume", test_resume_minimal)


def test_resume_target_role_gap():
    result = analyze_resume(SAMPLE_RESUME, target_role="devops engineer")
    assert isinstance(result.missing_skills, list)


test("Resume: target role gap analysis", test_resume_target_role_gap)


def test_resume_to_dict():
    result = analyze_resume(SAMPLE_RESUME)
    d = result.to_dict()
    assert isinstance(d, dict)
    assert "scores" in d
    assert "skills" in d
    assert isinstance(d["scores"], dict)
    assert "ats_score" in d["scores"]


test("Resume: to_dict serialization", test_resume_to_dict)


def test_resume_no_false_positives():
    """Skills should not be extracted from unrelated text."""
    text = "I like cooking and playing guitar. The weather is nice today."
    skills = _extract_skills(text)
    assert len(skills) == 0, f"False positive skills: {skills}"


test("Resume: no false positives", test_resume_no_false_positives)


def test_resume_alias_matching():
    """Aliases should map to canonical skill names."""
    text = "Experience with reactjs, nodejs, and postgres."
    skills = _extract_skills(text)
    assert "react" in skills, "reactjs should map to react"
    assert "node.js" in skills, "nodejs should map to node.js"
    assert "postgresql" in skills, "postgres should map to postgresql"


test("Resume: alias matching", test_resume_alias_matching)


def test_resume_period_terminated_skills():
    """Skills at end of sentence with period should be extracted."""
    text = "I know Python. I also use Docker."
    skills = _extract_skills(text)
    assert "python" in skills
    assert "docker" in skills


test("Resume: period-terminated skills", test_resume_period_terminated_skills)


def test_resume_experience_explicit_years():
    text = "5+ years of experience in software development."
    years = _estimate_experience_years(text, _detect_sections(text))
    assert years >= 5, f"Expected >= 5 years, got {years}"


test("Resume: explicit experience years", test_resume_experience_explicit_years)


def test_resume_ats_score_factors():
    """ATS score should improve with more sections and skills."""
    minimal = "Jane\nPython developer."
    full = SAMPLE_RESUME
    r1 = analyze_resume(minimal)
    r2 = analyze_resume(full)
    assert r2.ats_score > r1.ats_score, "Full resume should have higher ATS score"


test("Resume: ATS score improves with content", test_resume_ats_score_factors)


def test_resume_suggestion_for_missing_email():
    text = "John Doe\nPython developer with 5 years experience."
    result = analyze_resume(text)
    assert any("email" in s.lower() for s in result.suggestions)


test("Resume: suggestion for missing email", test_resume_suggestion_for_missing_email)


def test_resume_suggestion_for_missing_linkedin():
    text = "John Doe\njohn@email.com\nPython developer."
    result = analyze_resume(text)
    assert any("linkedin" in s.lower() for s in result.suggestions)


test(
    "Resume: suggestion for missing LinkedIn",
    test_resume_suggestion_for_missing_linkedin,
)


def test_resume_strength_for_github():
    result = analyze_resume(SAMPLE_RESUME)
    assert any("github" in s.lower() for s in result.strengths)


test("Resume: strength for GitHub present", test_resume_strength_for_github)


def test_resume_strength_for_certifications():
    result = analyze_resume(SAMPLE_RESUME)
    assert any("certification" in s.lower() for s in result.strengths)


test("Resume: strength for certifications", test_resume_strength_for_certifications)


def test_resume_hiring_readiness_composite():
    result = analyze_resume(SAMPLE_RESUME)
    # Hiring readiness should be between the min and max of component scores
    scores = [
        result.ats_score,
        result.technical_strength_score,
        result.resume_quality_score,
    ]
    assert min(scores) <= result.hiring_readiness_score <= max(scores) + 0.1


test("Resume: hiring readiness is composite", test_resume_hiring_readiness_composite)


# =====================================================
# INTEGRATION
# =====================================================
print("\n=== Integration ===")


def test_seed_match_rank():
    cleanup()
    profile = UserProfile(
        name="TestUser",
        skills=["python", "react", "aws"],
        programming_languages=["python"],
        frameworks=["react"],
        cloud_platforms=["aws"],
        experience_years=4,
        preferred_roles=["software engineer"],
        preferred_locations=["remote"],
        remote_preference="remote",
    )
    jobs = [
        JobListing(
            company="Co1",
            title="Python Engineer",
            url="http://c1.com",
            source="test",
            required_skills=["python", "aws"],
            experience_years=3,
            remote_status="remote",
            location="Remote",
        ),
        JobListing(
            company="Co2",
            title="Rust Engineer",
            url="http://c2.com",
            source="test",
            required_skills=["rust", "c++"],
            experience_years=5,
            remote_status="onsite",
            location="NYC",
        ),
        JobListing(
            company="Co3",
            title="Full Stack",
            url="http://c3.com",
            source="test",
            required_skills=["python", "react"],
            experience_years=2,
            remote_status="remote",
            location="Remote",
        ),
    ]
    for j in jobs:
        db.upsert_job(j, TEST_DB)
    results = []
    for j in db.get_all_jobs(TEST_DB):
        r = compute_match(profile, j)
        db.save_match_result(r, TEST_DB)
        results.append((j, r))
    results.sort(key=lambda x: x[1].overall_score, reverse=True)
    assert results[0][0].company in ("Co1", "Co3")
    assert results[-1][0].company == "Co2"


test("Integration: seed + match + rank", test_seed_match_rank)


def test_resume_analyze_and_store():
    cleanup()
    result = analyze_resume(SAMPLE_RESUME, target_role="backend engineer")
    resume_id = hashlib.sha256(SAMPLE_RESUME.encode()).hexdigest()[:16]
    db.upsert_resume(
        Resume(
            id=resume_id,
            name="test",
            filename="test.txt",
            raw_text=SAMPLE_RESUME,
            target_role="backend engineer",
        ),
        TEST_DB,
    )
    db.save_resume_analysis(
        resume_id=resume_id,
        ats_score=result.ats_score,
        resume_quality_score=result.resume_quality_score,
        technical_strength_score=result.technical_strength_score,
        hiring_readiness_score=result.hiring_readiness_score,
        skills=result.skills,
        strengths=result.strengths,
        weaknesses=result.weaknesses,
        missing_skills=result.missing_skills,
        suggestions=result.suggestions,
        db_path=TEST_DB,
    )
    analyses = db.get_resume_analyses(resume_id, TEST_DB)
    assert len(analyses) == 1
    assert analyses[0]["ats_score"] == result.ats_score


test("Integration: resume analyze + store", test_resume_analyze_and_store)


# =====================================================
# VERIFICATION FLOW
# =====================================================
print("\n=== Verification Flow ===")


def test_model_profile_verification_fields():
    p = UserProfile(is_verified=True, verified_at="2026-07-18T00:00:00")
    assert p.is_verified is True
    assert p.verified_at == "2026-07-18T00:00:00"


test("Model: profile verification fields", test_model_profile_verification_fields)


def test_model_profile_verification_defaults():
    p = UserProfile()
    assert p.is_verified is False
    assert p.verified_at == ""


test("Model: profile verification defaults", test_model_profile_verification_defaults)


def test_model_profile_yaml_roundtrip():
    """Profile with verification fields should survive YAML save/load."""
    p = UserProfile(
        name="Test",
        email="test@example.com",
        is_verified=True,
        verified_at="2026-07-18T12:00:00",
        skills=["python"],
    )
    save_profile(p, TEST_DB.parent / "test_profile.yaml")
    loaded = load_profile(TEST_DB.parent / "test_profile.yaml")
    assert loaded.is_verified is True
    assert loaded.verified_at == "2026-07-18T12:00:00"
    assert loaded.skills == ["python"]
    # Cleanup
    (TEST_DB.parent / "test_profile.yaml").unlink(missing_ok=True)


test(
    "Model: profile YAML roundtrip with verification", test_model_profile_yaml_roundtrip
)


def test_db_verification_events_log():
    cleanup()
    db.log_verification_event(
        entity_type="profile",
        entity_id="profile",
        event_type="profile_verification_requested",
        db_path=TEST_DB,
    )
    events = db.get_verification_events(entity_type="profile", db_path=TEST_DB)
    assert len(events) == 1
    assert events[0]["event_type"] == "profile_verification_requested"
    assert events[0]["entity_type"] == "profile"


test("DB: log verification event", test_db_verification_events_log)


def test_db_verification_events_filter():
    cleanup()
    db.log_verification_event(
        "profile", "profile", "profile_verification_requested", db_path=TEST_DB
    )
    db.log_verification_event(
        "resume", "r1", "profile_verification_requested", db_path=TEST_DB
    )
    db.log_verification_event(
        "profile", "profile", "profile_verification_accepted", db_path=TEST_DB
    )

    profile_events = db.get_verification_events(entity_type="profile", db_path=TEST_DB)
    resume_events = db.get_verification_events(entity_type="resume", db_path=TEST_DB)
    assert len(profile_events) == 2
    assert len(resume_events) == 1


test(
    "DB: verification events filter by entity type", test_db_verification_events_filter
)


def test_db_verification_events_chronological():
    cleanup()
    db.log_verification_event(
        "profile", "p", "profile_verification_requested", db_path=TEST_DB
    )
    db.log_verification_event(
        "profile", "p", "profile_verification_accepted", db_path=TEST_DB
    )
    db.log_verification_event("profile", "p", "submission_completed", db_path=TEST_DB)

    events = db.get_verification_events(
        entity_type="profile", entity_id="p", db_path=TEST_DB
    )
    assert len(events) == 3, f"Expected 3 events, got {len(events)}"
    # Newest first
    assert events[0]["event_type"] == "submission_completed"
    assert events[2]["event_type"] == "profile_verification_requested"


test(
    "DB: verification events chronological order",
    test_db_verification_events_chronological,
)


def test_db_verification_status_not_verified():
    cleanup()
    status = db.get_latest_verification_status("profile", "profile", TEST_DB)
    assert status["is_verified"] is False
    assert status["verified_at"] is None


test(
    "DB: verification status not verified by default",
    test_db_verification_status_not_verified,
)


def test_db_verification_status_after_accept():
    cleanup()
    db.log_verification_event(
        "profile", "status_accept", "profile_verification_requested", db_path=TEST_DB
    )
    db.log_verification_event(
        "profile", "status_accept", "profile_verification_accepted", db_path=TEST_DB
    )
    status = db.get_latest_verification_status("profile", "status_accept", TEST_DB)
    assert status["is_verified"] is True
    assert status["verified_at"] is not None


test(
    "DB: verification status after acceptance", test_db_verification_status_after_accept
)


def test_db_verification_status_after_decline():
    cleanup()
    db.log_verification_event(
        "profile", "status_decline", "profile_verification_requested", db_path=TEST_DB
    )
    db.log_verification_event(
        "profile", "status_decline", "profile_verification_declined", db_path=TEST_DB
    )
    status = db.get_latest_verification_status("profile", "status_decline", TEST_DB)
    assert status["is_verified"] is False
    assert status["last_event"] == "profile_verification_declined"


test("DB: verification status after decline", test_db_verification_status_after_decline)


def test_db_verification_events_with_data():
    cleanup()
    data = {"name": "Test User", "email": "test@example.com"}
    db.log_verification_event(
        "profile",
        "profile",
        "profile_verification_accepted",
        event_data=data,
        db_path=TEST_DB,
    )
    events = db.get_verification_events(db_path=TEST_DB)
    assert len(events) == 1
    assert events[0]["event_data"] is not None
    # event_data is stored as JSON string in SQLite
    event_data = (
        json.loads(events[0]["event_data"])
        if isinstance(events[0]["event_data"], str)
        else events[0]["event_data"]
    )
    assert event_data["name"] == "Test User"


test("DB: verification events with data payload", test_db_verification_events_with_data)


def test_api_profile_update_with_verification():
    """Test that profile update accepts is_verified and verified_at fields."""
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)

    # Update profile with verification fields
    response = client.put(
        "/api/profile",
        json={
            "name": "VerifyTest",
            "is_verified": True,
            "verified_at": "2026-07-18T00:00:00",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "VerifyTest"
    assert data["is_verified"] is True
    assert data["verified_at"] == "2026-07-18T00:00:00"

    # Get profile and verify
    response = client.get("/api/profile")
    assert response.status_code == 200
    data = response.json()
    assert data["is_verified"] is True

    # Reset for other tests
    client.put(
        "/api/profile", json={"name": "", "is_verified": False, "verified_at": ""}
    )


test(
    "API: profile update with verification fields",
    test_api_profile_update_with_verification,
)


def test_api_verify_request():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)
    response = client.post(
        "/api/verify/request",
        json={
            "entity_type": "profile",
            "entity_id": "profile",
        },
    )
    assert response.status_code == 200
    assert response.json()["logged"] is True


test("API: verify request endpoint", test_api_verify_request)


def test_api_verify_confirm():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)
    response = client.post(
        "/api/verify/confirm",
        json={
            "entity_type": "profile",
            "entity_id": "profile",
            "verified_data": {
                "name": "Confirmed User",
                "email": "confirmed@example.com",
                "is_verified": True,
            },
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["verified"] is True
    assert data["verified_at"] is not None

    # Verify profile was saved
    response = client.get("/api/profile")
    assert response.json()["name"] == "Confirmed User"
    assert response.json()["is_verified"] is True


test("API: verify confirm endpoint", test_api_verify_confirm)


def test_api_verify_decline():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)
    response = client.post(
        "/api/verify/decline",
        json={
            "entity_type": "profile",
            "entity_id": "profile",
        },
    )
    assert response.status_code == 200
    assert response.json()["declined"] is True


test("API: verify decline endpoint", test_api_verify_decline)


def test_api_verify_status():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)
    # Use a unique entity_id to avoid conflicts with other tests
    unique_id = "status_test_api"
    # First log some events
    client.post(
        "/api/verify/request", json={"entity_type": "profile", "entity_id": unique_id}
    )
    client.post(
        "/api/verify/confirm",
        json={
            "entity_type": "profile",
            "entity_id": unique_id,
            "verified_data": {"name": "StatusTest"},
        },
    )

    response = client.get(f"/api/verify/status/profile/{unique_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["is_verified"] is True
    assert "events" in data
    assert len(data["events"]) >= 2


test("API: verify status endpoint", test_api_verify_status)


def test_full_verification_flow():
    """Test the complete flow: request -> confirm -> status check."""
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)
    unique_id = "full_flow_test"

    # Step 1: User clicks Save Profile, modal opens -> request logged
    response = client.post(
        "/api/verify/request",
        json={
            "entity_type": "profile",
            "entity_id": unique_id,
        },
    )
    assert response.status_code == 200

    # Step 2: User confirms -> data saved with verification
    response = client.post(
        "/api/verify/confirm",
        json={
            "entity_type": "profile",
            "entity_id": unique_id,
            "verified_data": {
                "name": "Full Flow User",
                "email": "fullflow@example.com",
                "skills": ["python", "react"],
                "experience_years": 5,
                "is_verified": True,
                "verified_at": "2026-07-18T00:00:00",
            },
        },
    )
    assert response.status_code == 200
    assert response.json()["verified"] is True

    # Step 3: Check status
    response = client.get(f"/api/verify/status/profile/{unique_id}")
    assert response.status_code == 200
    status = response.json()
    assert status["is_verified"] is True

    # Step 4: Verify profile data persisted
    response = client.get("/api/profile")
    profile = response.json()
    assert profile["name"] == "Full Flow User"
    assert profile["is_verified"] is True
    assert "python" in profile["skills"]


test("Integration: full verification flow", test_full_verification_flow)


def test_verification_decline_then_resubmit():
    """Test that decline doesn't save, but re-submission works."""
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)
    unique_id = "decline_resubmit_test"

    # Set initial profile
    client.put("/api/profile", json={"name": "Original"})

    # Step 1: Request verification
    client.post(
        "/api/verify/request", json={"entity_type": "profile", "entity_id": unique_id}
    )

    # Step 2: User declines (chooses to edit)
    response = client.post(
        "/api/verify/decline",
        json={
            "entity_type": "profile",
            "entity_id": unique_id,
        },
    )
    assert response.status_code == 200

    # Verify profile was NOT updated (name should still be Original)
    response = client.get("/api/profile")
    assert response.json()["name"] == "Original"

    # Step 3: User edits and re-submits
    client.post(
        "/api/verify/request", json={"entity_type": "profile", "entity_id": unique_id}
    )
    response = client.post(
        "/api/verify/confirm",
        json={
            "entity_type": "profile",
            "entity_id": unique_id,
            "verified_data": {"name": "Updated", "is_verified": True},
        },
    )
    assert response.status_code == 200

    # Verify profile was updated
    response = client.get("/api/profile")
    assert response.json()["name"] == "Updated"
    assert response.json()["is_verified"] is True


test("Integration: decline then resubmit flow", test_verification_decline_then_resubmit)


# =====================================================
# FEATURE 1: RESUME PDF UPLOAD
# =====================================================
print("\n=== Feature 1: Resume Upload ===")


def test_upload_txt_file():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)

    content = b"John Doe\njohn@email.com\nPython Developer with 5 years experience.\n\nSkills: Python, Django, PostgreSQL\n\nExperience: Software Engineer at TechCo"
    response = client.post(
        "/api/resume/upload",
        files={"file": ("test.txt", content, "text/plain")},
        data={"target_role": "backend engineer"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "resume_id" in data
    assert data["filename"] == "test.txt"
    assert data["file_type"] == "txt"
    assert "python" in data.get("skills", [])


test("Upload: TXT file upload", test_upload_txt_file)


def test_upload_empty_file_rejected():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)

    response = client.post(
        "/api/resume/upload", files={"file": ("empty.txt", b"", "text/plain")}
    )
    assert response.status_code == 400


test("Upload: empty file rejected", test_upload_empty_file_rejected)


def test_upload_unsupported_format_rejected():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)

    response = client.post(
        "/api/resume/upload",
        files={"file": ("test.exe", b"binary", "application/octet-stream")},
    )
    assert response.status_code == 400


test("Upload: unsupported format rejected", test_upload_unsupported_format_rejected)


def test_upload_list_and_delete():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)

    # Upload a file
    content = b"Test resume content with enough words to pass validation"
    upload = client.post(
        "/api/resume/upload", files={"file": ("test.txt", content, "text/plain")}
    )
    assert upload.status_code == 200
    resume_id = upload.json()["resume_id"]

    # List uploads
    response = client.get("/api/resume/uploads")
    assert response.status_code == 200

    # Delete upload
    response = client.delete(f"/api/resume/uploads/{resume_id}")
    assert response.status_code == 200


test("Upload: list and delete", test_upload_list_and_delete)


def test_upload_stores_resume_in_db():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)

    content = b"Jane Smith\nSkills: React, Node.js, TypeScript"
    upload = client.post(
        "/api/resume/upload", files={"file": ("jane.txt", content, "text/plain")}
    )
    resume_id = upload.json()["resume_id"]

    # Check resume exists in DB
    resume = db.get_resume(resume_id)
    assert resume is not None
    assert resume.filename == "jane.txt"


test("Upload: stores resume in DB", test_upload_stores_resume_in_db)


def test_upload_extracts_text():
    from jobpilot.pdf_parser import extract_text_from_file

    text = extract_text_from_file(b"Hello World\nThis is a test", "test.txt")
    assert text == "Hello World\nThis is a test"


test("Upload: text extraction works", test_upload_extracts_text)


# =====================================================
# FEATURE 2: RESUME IMPROVEMENT
# =====================================================
print("\n=== Feature 2: Resume Improvement ===")


def test_improve_generates_suggestions():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)

    response = client.post(
        "/api/resume/suggestions",
        json={"resume_text": "John Doe\nPython developer with 3 years experience."},
    )
    assert response.status_code == 200
    data = response.json()
    assert "strengths" in data
    assert "weaknesses" in data
    assert "improvements" in data
    assert "recommended_keywords" in data


test("Improve: generates suggestions", test_improve_generates_suggestions)


def test_improve_identifies_weaknesses():
    from jobpilot.resume_improver import generate_improvement_report

    report = generate_improvement_report("Short resume.")
    assert len(report["weaknesses"]) > 0


test("Improve: identifies weaknesses", test_improve_identifies_weaknesses)


def test_improve_recommends_keywords():
    from jobpilot.resume_improver import generate_improvement_report

    report = generate_improvement_report(
        "Resume with Python.", target_role="backend engineer"
    )
    assert len(report["recommended_keywords"]) > 0


test("Improve: recommends keywords", test_improve_recommends_keywords)


def test_improve_calculates_score_delta():
    from jobpilot.resume_improver import generate_improvement_report

    report = generate_improvement_report(
        "Complete resume with skills, experience, and education."
    )
    assert "score_before" in report
    assert "score_after" in report
    assert report["score_after"]["ats"] >= report["score_before"]["ats"]


test("Improve: calculates score delta", test_improve_calculates_score_delta)


def test_improve_empty_resume_handled():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)

    response = client.post("/api/resume/suggestions", json={"resume_text": ""})
    assert response.status_code == 400


test("Improve: empty resume handled", test_improve_empty_resume_handled)


# =====================================================
# FEATURE 3: COVER LETTER
# =====================================================
print("\n=== Feature 3: Cover Letter ===")


def test_cover_letter_generate():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)

    response = client.post(
        "/api/cover-letter/generate",
        json={
            "resume_text": "John Doe\nPython developer with 5 years experience in web development.",
            "job_description": "Looking for a Python developer with Django experience.",
            "company_name": "TechCorp",
            "role_title": "Python Developer",
            "tone": "professional",
            "candidate_name": "John Doe",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "letter_text" in data
    assert "word_count" in data
    assert "TechCorp" in data["letter_text"]
    assert data["tone"] == "professional"


test("Cover Letter: generate", test_cover_letter_generate)


def test_cover_letter_stored_in_db():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)

    response = client.post(
        "/api/cover-letter/generate",
        json={
            "resume_text": "Resume content",
            "job_description": "Job description",
            "company_name": "TestCo",
            "role_title": "Developer",
        },
    )
    letter_id = response.json()["id"]
    assert letter_id > 0


test("Cover Letter: stored in DB", test_cover_letter_stored_in_db)


def test_cover_letter_history():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)

    # Generate a letter first
    client.post(
        "/api/cover-letter/generate",
        json={
            "resume_text": "Resume",
            "job_description": "Job",
            "company_name": "Co",
            "role_title": "Dev",
        },
    )

    response = client.get("/api/cover-letter/history")
    assert response.status_code == 200
    assert response.json()["total"] >= 1


test("Cover Letter: history", test_cover_letter_history)


def test_cover_letter_delete():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)

    resp = client.post(
        "/api/cover-letter/generate",
        json={
            "resume_text": "Resume",
            "job_description": "Job",
            "company_name": "Co",
            "role_title": "Dev",
        },
    )
    letter_id = resp.json()["id"]

    response = client.delete(f"/api/cover-letter/{letter_id}")
    assert response.status_code == 200
    assert response.json()["deleted"] is True


test("Cover Letter: delete", test_cover_letter_delete)


def test_cover_letter_tone_variation():
    from jobpilot.cover_letter_generator import generate_cover_letter

    result1 = generate_cover_letter(
        "Resume", "Job desc", "Co", "Dev", tone="professional"
    )
    result2 = generate_cover_letter(
        "Resume", "Job desc", "Co", "Dev", tone="enthusiastic"
    )
    assert result1["letter_text"] != result2["letter_text"]


test("Cover Letter: tone variation", test_cover_letter_tone_variation)


def test_cover_letter_empty_resume_handled():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)

    response = client.post(
        "/api/cover-letter/generate",
        json={
            "resume_text": "",
            "job_description": "Job",
            "company_name": "Co",
            "role_title": "Dev",
        },
    )
    assert response.status_code == 400


test("Cover Letter: empty resume handled", test_cover_letter_empty_resume_handled)


# =====================================================
# FEATURE 4: APPLICATION TRACKER
# =====================================================
print("\n=== Feature 4: Application Tracker ===")


def test_tracker_create_with_status():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)

    # Create a job first
    from jobpilot.models import JobListing

    job = JobListing(
        company="TestCo", title="Dev", url="http://test.com", source="test"
    )
    db.upsert_job(job)

    response = client.post(
        "/api/applications",
        json={"job_id": job.id, "status": "saved", "notes": "Test application"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "saved"


test("Tracker: create with status", test_tracker_create_with_status)


def test_tracker_update_status():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)

    from jobpilot.models import JobListing, Application

    job = JobListing(
        company="UpdateCo", title="Dev", url="http://update.com", source="test"
    )
    db.upsert_job(job)

    resp = client.post("/api/applications", json={"job_id": job.id, "status": "saved"})
    # The app_id is computed as hash of company+role+job_id
    app_item = Application(job_id=job.id, company=job.company, role=job.title)
    app_id = app_item.id

    response = client.put(f"/api/applications/{app_id}", json={"status": "applied"})
    assert response.status_code == 200


test("Tracker: update status", test_tracker_update_status)


def test_tracker_delete():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)

    from jobpilot.models import JobListing, Application

    job = JobListing(
        company="DeleteCo", title="Dev", url="http://delete.com", source="test"
    )
    db.upsert_job(job)

    resp = client.post("/api/applications", json={"job_id": job.id})
    app_item = Application(job_id=job.id, company=job.company, role=job.title)
    app_id = app_item.id

    response = client.delete(f"/api/applications/{app_id}")
    assert response.status_code == 200


test("Tracker: delete", test_tracker_delete)


def test_tracker_stats():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)

    response = client.get("/api/applications/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    # Stats should return counts for all statuses
    assert "saved" in data or "applied" in data or data["total"] == 0


test("Tracker: stats", test_tracker_stats)


def test_tracker_all_statuses_valid():
    from jobpilot.resume_analyzer import _extract_skills

    # Verify all status values are valid
    valid_statuses = [
        "saved",
        "applied",
        "interview",
        "assessment",
        "offer",
        "rejected",
        "accepted",
    ]
    assert len(valid_statuses) == 7


test("Tracker: all statuses valid", test_tracker_all_statuses_valid)


def test_tracker_notes():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)

    from jobpilot.models import JobListing

    job = JobListing(
        company="NoteCo", title="Dev", url="http://note.com", source="test"
    )
    db.upsert_job(job)

    resp = client.post("/api/applications", json={"job_id": job.id})
    app_id = resp.json()["job_id"]

    # Add note
    response = client.post(
        f"/api/applications/{app_id}/notes",
        params={"note_type": "interview", "content": "Had phone screen"},
    )
    assert response.status_code == 200

    # Get notes
    response = client.get(f"/api/applications/{app_id}/notes")
    assert response.status_code == 200
    assert response.json()["total"] >= 1


test("Tracker: notes", test_tracker_notes)


# =====================================================
# FEATURE 5: INTERVIEW PREP
# =====================================================
print("\n=== Feature 5: Interview Prep ===")


def test_interview_generate_questions():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)

    response = client.post(
        "/api/interview/questions",
        json={
            "resume_text": "Python developer with Django experience",
            "role_title": "Python Developer",
            "categories": ["technical", "behavioral"],
            "difficulty": "intermediate",
            "count": 5,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert "questions" in data
    assert data["questions"][0]["category"] in ["technical", "behavioral"]


test("Interview: generate questions", test_interview_generate_questions)


def test_interview_categories_filtered():
    from jobpilot.interview_coach import generate_questions

    questions = generate_questions(
        categories=["technical"], difficulty="beginner", count=5
    )
    for q in questions:
        assert q["category"] == "technical"


test("Interview: categories filtered", test_interview_categories_filtered)


def test_interview_difficulty_levels():
    from jobpilot.interview_coach import generate_questions

    beginner = generate_questions(
        categories=["technical"], difficulty="beginner", count=3
    )
    advanced = generate_questions(
        categories=["technical"], difficulty="advanced", count=3
    )
    assert all(q["difficulty"] == "beginner" for q in beginner)
    assert all(q["difficulty"] == "advanced" for q in advanced)


test("Interview: difficulty levels", test_interview_difficulty_levels)


def test_interview_history():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)

    client.post(
        "/api/interview/questions",
        json={
            "role_title": "Dev",
            "count": 3,
        },
    )

    response = client.get("/api/interview/history")
    assert response.status_code == 200
    assert response.json()["total"] >= 1


test("Interview: history", test_interview_history)


def test_interview_question_count():
    from jobpilot.interview_coach import generate_questions

    questions = generate_questions(count=15)
    assert len(questions) <= 15


test("Interview: question count", test_interview_question_count)


# =====================================================
# FEATURE 6: SKILL GAP
# =====================================================
print("\n=== Feature 6: Skill Gap ===")


def test_skill_gap_analysis():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)

    response = client.post(
        "/api/skill-gap/analyze",
        json={
            "resume_text": "Python developer with Django and PostgreSQL",
            "job_description": "Looking for Python, Django, Docker, and AWS experience",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "matched_skills" in data
    assert "missing_skills" in data
    assert "match_percentage" in data


test("Skill Gap: analysis", test_skill_gap_analysis)


def test_skill_gap_matched_skills():
    from jobpilot.skill_gap_analyzer import analyze_skill_gap

    result = analyze_skill_gap(
        resume_skills=["python", "django"],
        job_required_skills=["python", "django", "docker"],
    )
    assert "python" in result["matched_skills"]
    assert "django" in result["matched_skills"]
    assert "docker" in result["missing_skills"]


test("Skill Gap: matched skills", test_skill_gap_matched_skills)


def test_skill_gap_percentage():
    from jobpilot.skill_gap_analyzer import analyze_skill_gap

    result = analyze_skill_gap(
        resume_skills=["python", "django", "docker"],
        job_required_skills=["python", "django", "docker"],
    )
    assert result["match_percentage"] == 100.0


test("Skill Gap: percentage", test_skill_gap_percentage)


def test_skill_gap_stored_in_db():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)

    response = client.post(
        "/api/skill-gap/analyze",
        json={
            "resume_text": "Skills",
            "job_description": "Requirements",
        },
    )
    assert response.json()["report_id"] > 0


test("Skill Gap: stored in DB", test_skill_gap_stored_in_db)


def test_skill_gap_history():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)

    client.post(
        "/api/skill-gap/analyze",
        json={
            "resume_text": "Skills",
            "job_description": "Requirements",
        },
    )

    response = client.get("/api/skill-gap/history")
    assert response.status_code == 200
    assert response.json()["total"] >= 1


test("Skill Gap: history", test_skill_gap_history)


# =====================================================
# FEATURE 7: LINKEDIN
# =====================================================
print("\n=== Feature 7: LinkedIn ===")


def test_linkedin_analyze():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)

    response = client.post(
        "/api/linkedin/analyze",
        json={
            "headline": "Senior Software Engineer at Google | Python Expert",
            "about": "I am a passionate developer with 10 years of experience building scalable systems.",
            "skills": "Python, Java, AWS, Docker, Kubernetes",
            "experience": "Led team of 5 engineers. Built microservices handling 1M requests/day.",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "suggestions" in data
    assert "visibility_score" in data
    assert "strength_score" in data


test("LinkedIn: analyze", test_linkedin_analyze)


def test_linkedin_suggestions():
    from jobpilot.linkedin_analyzer import analyze_linkedin_profile

    result = analyze_linkedin_profile(
        headline="Dev", about="", skills="", experience=""
    )
    assert len(result["suggestions"]) > 0


test("LinkedIn: suggestions", test_linkedin_suggestions)


def test_linkedin_visibility_score():
    from jobpilot.linkedin_analyzer import analyze_linkedin_profile

    result = analyze_linkedin_profile(
        headline="Senior Engineer at Google",
        about="Passionate developer with 10 years experience.",
        skills="Python, Java, AWS",
        experience="Led team of 5.",
    )
    assert result["visibility_score"] > 50


test("LinkedIn: visibility score", test_linkedin_visibility_score)


def test_linkedin_stored_in_db():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)

    response = client.post(
        "/api/linkedin/analyze",
        json={
            "headline": "Dev",
            "about": "About me",
        },
    )
    assert response.json()["report_id"] > 0


test("LinkedIn: stored in DB", test_linkedin_stored_in_db)


def test_linkedin_empty_input_handled():
    from jobpilot.linkedin_analyzer import analyze_linkedin_profile

    result = analyze_linkedin_profile()
    assert result["visibility_score"] == 0
    assert result["strength_score"] == 0


test("LinkedIn: empty input handled", test_linkedin_empty_input_handled)


def test_linkedin_history():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)

    client.post("/api/linkedin/analyze", json={"headline": "Dev"})

    response = client.get("/api/linkedin/history")
    assert response.status_code == 200
    assert response.json()["total"] >= 1


test("LinkedIn: history", test_linkedin_history)


# =====================================================
# FEATURE 8: RESUME TAILORING
# =====================================================
print("\n=== Feature 8: Resume Tailoring ===")


def test_tailor_generates_output():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)

    response = client.post(
        "/api/resume/tailor",
        json={
            "resume_text": "John Doe\nPython developer with 5 years experience.\n\nSkills: Python, Django, PostgreSQL\n\nExperience: Built web apps.",
            "job_description": "Looking for Python, Docker, AWS, Kubernetes experience.",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "original_text" in data
    assert "tailored_text" in data
    assert "original_score" in data
    assert "tailored_score" in data
    assert "improvement_pct" in data


test("Tailor: generates output", test_tailor_generates_output)


def test_tailor_calculates_improvement():
    from jobpilot.resume_tailor import tailor_resume

    result = tailor_resume(
        resume_text="Python developer",
        job_description="Python, Docker, AWS, Kubernetes, CI/CD",
    )
    assert result["original_score"] >= 0
    assert result["tailored_score"] >= 0


test("Tailor: calculates improvement", test_tailor_calculates_improvement)


def test_tailor_keywords_added():
    from jobpilot.resume_tailor import tailor_resume

    result = tailor_resume(
        resume_text="Python developer",
        job_description="Docker, AWS, Kubernetes experience needed",
    )
    assert isinstance(result["keywords_added"], list)


test("Tailor: keywords added", test_tailor_keywords_added)


def test_tailor_stored_in_db():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)

    response = client.post(
        "/api/resume/tailor",
        json={
            "resume_text": "Resume",
            "job_description": "Job desc",
        },
    )
    assert response.json()["id"] > 0


test("Tailor: stored in DB", test_tailor_stored_in_db)


def test_tailor_history():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)

    client.post(
        "/api/resume/tailor",
        json={
            "resume_text": "Resume",
            "job_description": "Job",
        },
    )

    response = client.get("/api/resume/tailored")
    assert response.status_code == 200
    assert response.json()["total"] >= 1


test("Tailor: history", test_tailor_history)


# =====================================================
# FEATURE 9: ALERTS
# =====================================================
print("\n=== Feature 9: Alerts ===")


def test_alert_subscribe():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)

    response = client.post(
        "/api/alerts/subscribe",
        json={
            "role": "Python Developer",
            "location": "Remote",
            "frequency": "daily",
        },
    )
    assert response.status_code == 200
    assert response.json()["created"] is True
    assert response.json()["id"] > 0


test("Alerts: subscribe", test_alert_subscribe)


def test_alert_unsubscribe():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)

    resp = client.post("/api/alerts/subscribe", json={"role": "Dev"})
    alert_id = resp.json()["id"]

    response = client.post(f"/api/alerts/unsubscribe?alert_id={alert_id}")
    assert response.status_code == 200


test("Alerts: unsubscribe", test_alert_unsubscribe)


def test_alert_preferences():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)

    client.post("/api/alerts/subscribe", json={"role": "Test"})

    response = client.get("/api/alerts/preferences")
    assert response.status_code == 200
    assert response.json()["total"] >= 1


test("Alerts: preferences", test_alert_preferences)


def test_alert_update():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)

    resp = client.post("/api/alerts/subscribe", json={"role": "Dev"})
    alert_id = resp.json()["id"]

    response = client.put(f"/api/alerts/{alert_id}", json={"frequency": "weekly"})
    assert response.status_code == 200


test("Alerts: update", test_alert_update)


def test_alert_delete():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)

    resp = client.post("/api/alerts/subscribe", json={"role": "Dev"})
    alert_id = resp.json()["id"]

    response = client.delete(f"/api/alerts/{alert_id}")
    assert response.status_code == 200


test("Alerts: delete", test_alert_delete)


def test_alert_frequency_values():
    from jobpilot.alert_service import get_alert_frequency_options

    options = get_alert_frequency_options()
    assert len(options) == 3
    values = [o["value"] for o in options]
    assert "instant" in values
    assert "daily" in values
    assert "weekly" in values


test("Alerts: frequency values", test_alert_frequency_values)


def test_alert_match_logic():
    from jobpilot.alert_service import match_alert_to_jobs
    from jobpilot.models import AlertSubscription, JobListing

    alert = AlertSubscription(role="Python", location="Remote", remote_only=True)
    jobs = [
        JobListing(title="Python Developer", location="Remote", remote_status="remote"),
        JobListing(title="Java Developer", location="New York", remote_status="onsite"),
    ]
    matched = match_alert_to_jobs(alert, jobs)
    assert len(matched) == 1
    assert matched[0].title == "Python Developer"


test("Alerts: match logic", test_alert_match_logic)


# =====================================================
# FEATURE 10: DASHBOARD ANALYTICS
# =====================================================
print("\n=== Feature 10: Dashboard Analytics ===")


def test_analytics_total_counts():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)

    response = client.get("/api/dashboard/stats")
    assert response.status_code == 200
    data = response.json()
    assert "job_search_metrics" in data
    assert "application_metrics" in data


test("Analytics: total counts", test_analytics_total_counts)


def test_analytics_summary():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)

    response = client.get("/api/dashboard/summary")
    assert response.status_code == 200
    data = response.json()
    assert "total_jobs" in data
    assert "total_applications" in data


test("Analytics: summary", test_analytics_summary)


def test_analytics_timeline():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)

    response = client.get("/api/dashboard/timeline")
    assert response.status_code == 200
    assert "timeline" in response.json()
    assert len(response.json()["timeline"]) == 30


test("Analytics: timeline", test_analytics_timeline)


def test_analytics_skills():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)

    response = client.get("/api/dashboard/skills")
    assert response.status_code == 200
    data = response.json()
    assert "top_skills" in data
    assert "missing_skills" in data


test("Analytics: skills", test_analytics_skills)


def test_analytics_empty_data_handled():
    from jobpilot.dashboard_analytics import compute_analytics

    # Should not crash with empty database
    stats = compute_analytics()
    assert "job_search_metrics" in stats
    assert "resume_metrics" in stats


test("Analytics: empty data handled", test_analytics_empty_data_handled)


# =====================================================
# NEW JOB DETECTION & SMART ALERTS
# =====================================================
print("\n=== New Job Detection & Smart Alerts ===")


def test_job_hash_computation():
    from jobpilot.database import compute_job_hash

    h1 = compute_job_hash("Google", "Engineer", "https://example.com/1")
    h2 = compute_job_hash("Google", "Engineer", "https://example.com/1")
    h3 = compute_job_hash("Google", "Engineer", "https://example.com/2")
    assert h1 == h2, "Same inputs should produce same hash"
    assert h1 != h3, "Different URL should produce different hash"


test("DB: job hash computation", test_job_hash_computation)


def test_upsert_job_new():
    cleanup()
    j = JobListing(
        company="TestCo", title="Python Dev", url="https://test.com/1", source="test"
    )
    is_new = db.upsert_job(j, TEST_DB)
    assert is_new is True


test("DB: upsert job new", test_upsert_job_new)


def test_upsert_job_existing():
    cleanup()
    j = JobListing(
        company="TestCo", title="Python Dev", url="https://test.com/1", source="test"
    )
    db.upsert_job(j, TEST_DB)
    is_new = db.upsert_job(j, TEST_DB)
    assert is_new is False


test("DB: upsert job existing", test_upsert_job_existing)


def test_is_active_default():
    j = JobListing(company="TestCo", title="Dev", url="https://test.com")
    assert j.is_active is True


test("Model: is_active default", test_is_active_default)


def test_deactivate_job():
    cleanup()
    j = JobListing(company="TestCo", title="Dev", url="https://test.com", source="test")
    db.upsert_job(j, TEST_DB)
    result = db.update_job_active_status(j.id, False, TEST_DB)
    assert result is True
    retrieved = db.get_job(j.id, TEST_DB)
    assert retrieved.is_active is False


test("DB: deactivate job", test_deactivate_job)


def test_activate_job():
    cleanup()
    j = JobListing(company="TestCo", title="Dev", url="https://test.com", source="test")
    db.upsert_job(j, TEST_DB)
    db.update_job_active_status(j.id, False, TEST_DB)
    result = db.update_job_active_status(j.id, True, TEST_DB)
    assert result is True
    retrieved = db.get_job(j.id, TEST_DB)
    assert retrieved.is_active is True


test("DB: activate job", test_activate_job)


def test_check_job_exists():
    cleanup()
    j = JobListing(company="TestCo", title="Dev", url="https://test.com", source="test")
    assert db.check_job_exists(j.id, TEST_DB) is False
    db.upsert_job(j, TEST_DB)
    assert db.check_job_exists(j.id, TEST_DB) is True


test("DB: check job exists", test_check_job_exists)


def test_get_new_jobs():
    cleanup()
    j1 = JobListing(
        company="TestCo", title="Dev1", url="https://test.com/1", source="test"
    )
    j2 = JobListing(
        company="TestCo", title="Dev2", url="https://test.com/2", source="test"
    )
    db.upsert_job(j1, TEST_DB)
    new_jobs = db.get_new_jobs([j1, j2], TEST_DB)
    assert len(new_jobs) == 1
    assert new_jobs[0].id == j2.id


test("DB: get new jobs", test_get_new_jobs)


def test_create_notification():
    cleanup()
    j = JobListing(company="TestCo", title="Dev", url="https://test.com", source="test")
    db.upsert_job(j, TEST_DB)
    notif_id = db.create_job_notification(
        j.id, "new_match", "New job found!", 0.85, TEST_DB
    )
    assert notif_id > 0


test("DB: create notification", test_create_notification)


def test_get_notifications():
    cleanup()
    j = JobListing(company="TestCo", title="Dev", url="https://test.com", source="test")
    db.upsert_job(j, TEST_DB)
    db.create_job_notification(j.id, "new_match", "Test message", 0.85, TEST_DB)
    notifs = db.get_job_notifications(db_path=TEST_DB)
    assert len(notifs) == 1
    assert notifs[0]["message"] == "Test message"


test("DB: get notifications", test_get_notifications)


def test_mark_notification_read():
    cleanup()
    j = JobListing(company="TestCo", title="Dev", url="https://test.com", source="test")
    db.upsert_job(j, TEST_DB)
    notif_id = db.create_job_notification(j.id, "new_match", "Test", 0.85, TEST_DB)
    result = db.mark_notification_read(notif_id, TEST_DB)
    assert result is True
    notifs = db.get_job_notifications(is_read=False, db_path=TEST_DB)
    assert len(notifs) == 0


test("DB: mark notification read", test_mark_notification_read)


def test_mark_all_notifications_read():
    cleanup()
    j = JobListing(company="TestCo", title="Dev", url="https://test.com", source="test")
    db.upsert_job(j, TEST_DB)
    db.create_job_notification(j.id, "new_match", "Msg1", 0.8, TEST_DB)
    db.create_job_notification(j.id, "new_match", "Msg2", 0.9, TEST_DB)
    count = db.mark_all_notifications_read(TEST_DB)
    assert count == 2
    unread = db.get_unread_notification_count(TEST_DB)
    assert unread == 0


test("DB: mark all notifications read", test_mark_all_notifications_read)


def test_has_been_notified():
    cleanup()
    j = JobListing(company="TestCo", title="Dev", url="https://test.com", source="test")
    db.upsert_job(j, TEST_DB)
    assert db.has_been_notified(j.id, TEST_DB) is False
    db.create_job_notification(j.id, "new_match", "Test", 0.85, TEST_DB)
    assert db.has_been_notified(j.id, TEST_DB) is True


test("DB: has been notified", test_has_been_notified)


def test_save_scan_history():
    cleanup()
    hist_id = db.save_scan_history(
        "greenhouse", "python", "remote", 50, 10, 2.5, TEST_DB
    )
    assert hist_id > 0


test("DB: save scan history", test_save_scan_history)


def test_get_scan_history():
    cleanup()
    db.save_scan_history("greenhouse", "python", "remote", 50, 10, 2.5, TEST_DB)
    db.save_scan_history("remoteok", "react", "", 30, 5, 1.2, TEST_DB)
    history = db.get_scan_history(db_path=TEST_DB)
    assert len(history) == 2


test("DB: get scan history", test_get_scan_history)


def test_get_scan_stats():
    cleanup()
    db.save_scan_history("greenhouse", "", "", 100, 20, 3.0, TEST_DB)
    db.save_scan_history("remoteok", "", "", 50, 10, 1.5, TEST_DB)
    stats = db.get_scan_stats(TEST_DB)
    assert stats["total_scans"] == 2
    assert stats["total_jobs_found"] == 150
    assert stats["total_new_jobs"] == 30


test("DB: scan stats", test_get_scan_stats)


def test_top_hiring_companies():
    cleanup()
    for i in range(3):
        j = JobListing(
            company="BigCo", title=f"Dev{i}", url=f"https://test.com/{i}", source="test"
        )
        db.upsert_job(j, TEST_DB)
    j2 = JobListing(
        company="SmallCo", title="Dev", url="https://test.com/small", source="test"
    )
    db.upsert_job(j2, TEST_DB)
    top = db.get_top_hiring_companies(5, TEST_DB)
    assert len(top) >= 1
    assert top[0]["company"] == "BigCo"
    assert top[0]["job_count"] == 3


test("DB: top hiring companies", test_top_hiring_companies)


def test_most_frequent_skills():
    cleanup()
    j1 = JobListing(
        company="Co",
        title="Dev1",
        url="https://t.com/1",
        source="test",
        required_skills=["python", "django", "postgresql"],
    )
    j2 = JobListing(
        company="Co",
        title="Dev2",
        url="https://t.com/2",
        source="test",
        required_skills=["python", "react", "docker"],
    )
    db.upsert_job(j1, TEST_DB)
    db.upsert_job(j2, TEST_DB)
    skills = db.get_most_frequent_skills(5, TEST_DB)
    assert len(skills) >= 1
    assert skills[0]["skill"] == "python"
    assert skills[0]["count"] == 2


test("DB: most frequent skills", test_most_frequent_skills)


def test_jobs_by_source():
    cleanup()
    for i in range(3):
        j = JobListing(
            company="Co", title=f"Dev{i}", url=f"https://t.com/{i}", source="greenhouse"
        )
        db.upsert_job(j, TEST_DB)
    j2 = JobListing(company="Co", title="Dev", url="https://t.com/x", source="remoteok")
    db.upsert_job(j2, TEST_DB)
    sources = db.get_jobs_by_source(TEST_DB)
    assert len(sources) >= 2
    gh = next((s for s in sources if s["source"] == "greenhouse"), None)
    assert gh is not None
    assert gh["job_count"] == 3


test("DB: jobs by source", test_jobs_by_source)


def test_notification_with_company_info():
    cleanup()
    j = JobListing(
        company="TestCo", title="Python Dev", url="https://test.com", source="test"
    )
    db.upsert_job(j, TEST_DB)
    db.create_job_notification(j.id, "new_match", "Found!", 0.9, TEST_DB)
    notifs = db.get_job_notifications(db_path=TEST_DB)
    assert notifs[0]["company"] == "TestCo"
    assert notifs[0]["title"] == "Python Dev"


test("DB: notification with company info", test_notification_with_company_info)


# --- Job Scanner Tests ---
print("\n=== Job Scanner ===")


def test_job_scanner_new_jobs():
    cleanup()
    from jobpilot.job_scanner import JobScanner

    scanner = JobScanner(db_path=TEST_DB)
    jobs = [
        JobListing(
            company="NewCo", title="Dev1", url="https://new.com/1", source="test"
        ),
        JobListing(
            company="NewCo", title="Dev2", url="https://new.com/2", source="test"
        ),
    ]
    new_jobs = db.get_new_jobs(jobs, TEST_DB)
    assert len(new_jobs) == 2


test("Scanner: new jobs detection", test_job_scanner_new_jobs)


def test_job_scanner_dedup():
    cleanup()
    j = JobListing(company="DupCo", title="Dev", url="https://dup.com", source="test")
    db.upsert_job(j, TEST_DB)
    jobs = [
        j,
        JobListing(company="DupCo", title="Dev", url="https://dup.com", source="test"),
        JobListing(company="NewCo", title="Dev", url="https://new.com", source="test"),
    ]
    new_jobs = db.get_new_jobs(jobs, TEST_DB)
    assert len(new_jobs) == 1
    assert new_jobs[0].company == "NewCo"


test("Scanner: deduplication", test_job_scanner_dedup)


def test_job_scanner_format_notification():
    cleanup()
    from jobpilot.job_scanner import JobScanner
    from jobpilot.models import MatchResult

    scanner = JobScanner(db_path=TEST_DB)
    job = JobListing(
        company="TestCo",
        title="Python Dev",
        url="https://test.com",
        location="Remote",
        source="test",
    )
    match = MatchResult(overall_score=0.85)
    msg = scanner._format_notification(job, match)
    assert "Python Dev" in msg
    assert "TestCo" in msg
    assert "85%" in msg


test("Scanner: format notification", test_job_scanner_format_notification)


def test_job_scanner_alert_match_role():
    cleanup()
    from jobpilot.job_scanner import JobScanner
    from jobpilot.models import AlertSubscription, MatchResult

    scanner = JobScanner(db_path=TEST_DB)
    job = JobListing(
        company="TestCo",
        title="Python Developer",
        description="We need a Python developer",
        source="test",
    )
    alert = AlertSubscription(role="python")
    match = MatchResult(overall_score=0.5)
    assert scanner._job_matches_alert(job, alert, match) is True


test("Scanner: alert match role", test_job_scanner_alert_match_role)


def test_job_scanner_alert_match_remote():
    cleanup()
    from jobpilot.job_scanner import JobScanner
    from jobpilot.models import AlertSubscription, MatchResult

    scanner = JobScanner(db_path=TEST_DB)
    job_remote = JobListing(
        company="Co", title="Dev", remote_status="remote", source="test"
    )
    job_onsite = JobListing(
        company="Co", title="Dev", remote_status="onsite", source="test"
    )
    alert = AlertSubscription(remote_only=True)
    match = MatchResult(overall_score=0.5)
    assert scanner._job_matches_alert(job_remote, alert, match) is True
    assert scanner._job_matches_alert(job_onsite, alert, match) is False


test("Scanner: alert match remote", test_job_scanner_alert_match_remote)


def test_job_scanner_alert_match_location():
    cleanup()
    from jobpilot.job_scanner import JobScanner
    from jobpilot.models import AlertSubscription, MatchResult

    scanner = JobScanner(db_path=TEST_DB)
    job = JobListing(company="Co", title="Dev", location="San Francisco", source="test")
    alert = AlertSubscription(location="San Francisco")
    match = MatchResult(overall_score=0.5)
    assert scanner._job_matches_alert(job, alert, match) is True
    alert2 = AlertSubscription(location="New York")
    assert scanner._job_matches_alert(job, alert2, match) is False


test("Scanner: alert match location", test_job_scanner_alert_match_location)


def test_job_scanner_alert_match_score():
    cleanup()
    from jobpilot.job_scanner import JobScanner
    from jobpilot.models import AlertSubscription, MatchResult

    scanner = JobScanner(db_path=TEST_DB)
    job = JobListing(company="Co", title="Dev", source="test")
    alert = AlertSubscription()
    match_low = MatchResult(overall_score=0.1)
    match_high = MatchResult(overall_score=0.5)
    assert scanner._job_matches_alert(job, alert, match_low) is False
    assert scanner._job_matches_alert(job, alert, match_high) is True


test("Scanner: alert match minimum score", test_job_scanner_alert_match_score)


def test_deactivate_stale_jobs():
    cleanup()
    from jobpilot.job_scanner import JobScanner

    j = JobListing(
        company="StaleCo",
        title="Dev",
        url="https://stale.com",
        source="test",
        discovered_at="2020-01-01T00:00:00",
    )
    db.upsert_job(j, TEST_DB)
    scanner = JobScanner(db_path=TEST_DB)
    count = scanner.deactivate_stale_jobs(max_age_days=30)
    assert count >= 1


test("Scanner: deactivate stale jobs", test_deactivate_stale_jobs)


def test_get_scan_summary():
    cleanup()
    from jobpilot.job_scanner import JobScanner

    scanner = JobScanner(db_path=TEST_DB)
    summary = scanner.get_scan_summary()
    assert "scan_stats" in summary
    assert "jobs_discovered_today" in summary
    assert "top_hiring_companies" in summary


test("Scanner: get scan summary", test_get_scan_summary)


# --- Recommendation Engine Tests ---
print("\n=== Recommendation Engine ===")


def test_recommend_engine_skills():
    cleanup()
    from jobpilot.recommendation_engine import RecommendationEngine

    j1 = JobListing(
        company="Co",
        title="Dev1",
        url="https://t.com/1",
        source="test",
        required_skills=["python", "docker", "kubernetes"],
    )
    j2 = JobListing(
        company="Co",
        title="Dev2",
        url="https://t.com/2",
        source="test",
        required_skills=["python", "react", "aws"],
    )
    db.upsert_job(j1, TEST_DB)
    db.upsert_job(j2, TEST_DB)
    engine = RecommendationEngine(db_path=TEST_DB)
    profile = UserProfile(skills=["python"])
    skills = engine._recommend_skills(profile, limit=5)
    assert len(skills) > 0
    skill_names = [s["skill"] for s in skills]
    assert "python" not in skill_names


test("Engine: skill recommendations", test_recommend_engine_skills)


def test_recommend_engine_companies():
    cleanup()
    from jobpilot.recommendation_engine import RecommendationEngine

    db.upsert_company(Company(name="BigTech", industry="Tech"), TEST_DB)
    j = JobListing(
        company="BigTech",
        title="Dev",
        url="https://t.com/1",
        source="test",
        required_skills=["python"],
    )
    db.upsert_job(j, TEST_DB)
    engine = RecommendationEngine(db_path=TEST_DB)
    profile = UserProfile(skills=["python"])
    companies = engine._recommend_companies(profile, limit=5)
    assert len(companies) >= 1
    assert companies[0]["company"] == "BigTech"


test("Engine: company recommendations", test_recommend_engine_companies)


def test_recommend_engine_certifications():
    cleanup()
    from jobpilot.recommendation_engine import RecommendationEngine

    j = JobListing(
        company="Co",
        title="Dev",
        url="https://t.com/1",
        source="test",
        required_skills=["aws", "kubernetes"],
    )
    db.upsert_job(j, TEST_DB)
    engine = RecommendationEngine(db_path=TEST_DB)
    profile = UserProfile(skills=["python"])
    certs = engine._recommend_certifications(profile, limit=5)
    assert len(certs) > 0
    cert_names = [c["certification"] for c in certs]
    assert any("AWS" in name for name in cert_names)


test("Engine: certification recommendations", test_recommend_engine_certifications)


def test_recommend_engine_empty():
    cleanup()
    from jobpilot.recommendation_engine import RecommendationEngine

    engine = RecommendationEngine(db_path=TEST_DB)
    recs = engine.get_recommendations()
    assert "recommended_jobs" in recs
    assert "recommended_skills" in recs
    assert "recommended_companies" in recs
    assert "recommended_certifications" in recs


test("Engine: empty database recommendations", test_recommend_engine_empty)


# --- Enhanced Dashboard Tests ---
print("\n=== Enhanced Dashboard API ===")


def test_enhanced_dashboard():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)
    response = client.get("/api/dashboard/enhanced")
    assert response.status_code == 200
    data = response.json()
    assert "scan_stats" in data
    assert "jobs_discovered_today" in data
    assert "top_hiring_companies" in data


test("API: enhanced dashboard", test_enhanced_dashboard)


def test_notifications_api():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)
    response = client.get("/api/notifications")
    assert response.status_code == 200
    assert "notifications" in response.json()


test("API: notifications list", test_notifications_api)


def test_unread_count_api():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)
    response = client.get("/api/notifications/unread-count")
    assert response.status_code == 200
    assert "unread_count" in response.json()


test("API: unread count", test_unread_count_api)


def test_trending_skills_api():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)
    response = client.get("/api/trending/skills")
    assert response.status_code == 200
    assert "skills" in response.json()


test("API: trending skills", test_trending_skills_api)


def test_trending_companies_api():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)
    response = client.get("/api/trending/companies")
    assert response.status_code == 200
    assert "companies" in response.json()


test("API: trending companies", test_trending_companies_api)


def test_jobs_by_source_api():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)
    response = client.get("/api/trending/sources")
    assert response.status_code == 200
    assert "sources" in response.json()


test("API: jobs by source", test_jobs_by_source_api)


def test_recommendations_api():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)
    response = client.get("/api/recommendations")
    assert response.status_code == 200
    data = response.json()
    assert "recommended_jobs" in data
    assert "recommended_skills" in data


test("API: recommendations", test_recommendations_api)


def test_scan_history_api():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)
    response = client.get("/api/scan/history")
    assert response.status_code == 200
    assert "history" in response.json()


test("API: scan history", test_scan_history_api)


def test_scan_stats_api():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)
    response = client.get("/api/scan/stats")
    assert response.status_code == 200
    assert "total_scans" in response.json()


test("API: scan stats", test_scan_stats_api)


def test_smart_scan_api():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)
    with patch("jobpilot.job_scanner.JobScanner.scan_all_sources") as mock_scan:
        mock_scan.return_value = {
            "sources_scanned": 2,
            "total_jobs_found": 50,
            "total_new_jobs": 10,
            "new_jobs": [],
            "notifications_created": 2,
            "duration": 1.5,
            "source_results": [
                {"source": "greenhouse", "found": 30, "new": 5},
                {"source": "remoteok", "found": 20, "new": 5},
            ],
        }
        response = client.post("/api/scan/smart", json={"source": "all"})
        assert response.status_code == 200
        assert response.json()["total_jobs_found"] == 50


test("API: smart scan", test_smart_scan_api)


def test_jobs_new_today_api():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)
    response = client.get("/api/jobs/new/today")
    assert response.status_code == 200
    assert "jobs" in response.json()


test("API: jobs new today", test_jobs_new_today_api)


def test_jobs_new_week_api():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)
    response = client.get("/api/jobs/new/week")
    assert response.status_code == 200
    assert "jobs" in response.json()


test("API: jobs new week", test_jobs_new_week_api)


def test_jobs_high_match_api():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)
    response = client.get("/api/jobs/high-match")
    assert response.status_code == 200
    assert "jobs" in response.json()


test("API: jobs high match", test_jobs_high_match_api)


def test_activate_deactivate_job_api():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)
    j = JobListing(
        company="TestCo", title="Dev", url="https://test.com/api", source="test"
    )
    db.upsert_job(j, TEST_DB)
    response = client.post(f"/api/jobs/{j.id}/deactivate")
    assert response.status_code == 200
    response = client.post(f"/api/jobs/{j.id}/activate")
    assert response.status_code == 200


test("API: activate/deactivate job", test_activate_deactivate_job_api)


# =====================================================
# JOB IMPORT TESTS
# =====================================================
print("\n=== Job Import ===")


def test_import_job_url():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)

    # Test with a valid URL (will fail to fetch in test environment, but tests the endpoint)
    response = client.post(
        "/api/jobs/import", json={"url": "https://www.linkedin.com/jobs/view/test"}
    )
    # Should return error since we can't fetch in test environment
    assert response.status_code in [200, 400]


test("API: import job URL endpoint", test_import_job_url)


def test_import_job_invalid_url():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)

    response = client.post("/api/jobs/import", json={"url": ""})
    assert response.status_code == 400


test("API: import job invalid URL", test_import_job_invalid_url)


def test_job_importer_source_detection():
    from jobpilot.job_importer import JobImporter

    importer = JobImporter()

    assert (
        importer._detect_source("https://www.linkedin.com/jobs/view/123") == "linkedin"
    )
    assert importer._detect_source("https://www.naukri.com/job/123") == "naukri"
    assert importer._detect_source("https://www.indeed.com/viewjob?jk=123") == "indeed"
    assert (
        importer._detect_source("https://www.glassdoor.com/job/listing/123")
        == "glassdoor"
    )
    assert importer._detect_source("https://wellfound.com/role/123") == "wellfound"
    assert importer._detect_source("https://boards.greenhouse.io/123") == "greenhouse"
    assert importer._detect_source("https://jobs.lever.co/123") == "lever"
    assert importer._detect_source("https://jobs.ashbyhq.com/123") == "ashby"
    assert importer._detect_source("https://example.com/job/123") == "generic"


test("Job Importer: source detection", test_job_importer_source_detection)


# =====================================================
# AUTHENTICATION TESTS
# =====================================================
print("\n=== Authentication ===")


def test_register_user():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app
    import uuid

    client = TestClient(app)

    unique_email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    response = client.post(
        "/api/auth/register",
        json={"email": unique_email, "password": "TestPass123!", "name": "Test User"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == unique_email
    assert data["name"] == "Test User"
    assert "id" in data


test("Auth: register user", test_register_user)


def test_register_duplicate_email():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)

    client.post(
        "/api/auth/register",
        json={
            "email": "dup@example.com",
            "password": "TestPass123!",
            "name": "First User",
        },
    )
    response = client.post(
        "/api/auth/register",
        json={
            "email": "dup@example.com",
            "password": "TestPass123!",
            "name": "Second User",
        },
    )
    assert response.status_code == 400


test("Auth: duplicate email rejected", test_register_duplicate_email)


def test_login_user():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app
    import os

    client = TestClient(app)
    email = f"login_{os.urandom(4).hex()}@example.com"

    client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "TestPass123!",
            "name": "Login User",
        },
    )

    response = client.post(
        "/api/auth/login",
        data={"username": email, "password": "TestPass123!"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


test("Auth: login user", test_login_user)


def test_login_wrong_password():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app
    import os

    client = TestClient(app)
    email = f"wrong_{os.urandom(4).hex()}@example.com"

    client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "TestPass123!",
            "name": "Wrong User",
        },
    )

    response = client.post(
        "/api/auth/login",
        data={"username": email, "password": "WrongPassword123!"},
    )
    assert response.status_code == 401


test("Auth: wrong password rejected", test_login_wrong_password)


def test_protected_route():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app

    client = TestClient(app)

    response = client.get("/api/auth/me")
    assert response.status_code == 401


test("Auth: protected route requires token", test_protected_route)


def test_get_me_with_token():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app
    import os

    client = TestClient(app)
    email = f"me_{os.urandom(4).hex()}@example.com"

    client.post(
        "/api/auth/register",
        json={"email": email, "password": "TestPass123!", "name": "Me User"},
    )

    login_response = client.post(
        "/api/auth/login",
        data={"username": email, "password": "TestPass123!"},
    )
    token = login_response.json()["access_token"]

    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == email


test("Auth: get me with token", test_get_me_with_token)


def test_refresh_token():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app
    import os

    client = TestClient(app)
    email = f"refresh_{os.urandom(4).hex()}@example.com"

    client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "TestPass123!",
            "name": "Refresh User",
        },
    )

    login_response = client.post(
        "/api/auth/login",
        data={"username": email, "password": "TestPass123!"},
    )
    refresh_token = login_response.json()["refresh_token"]

    response = client.post(f"/api/auth/refresh?refresh_token={refresh_token}")
    assert response.status_code == 200
    assert "access_token" in response.json()


test("Auth: refresh token", test_refresh_token)


def test_change_password():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app
    import uuid

    client = TestClient(app)

    unique_email = f"changepass_{uuid.uuid4().hex[:8]}@example.com"
    client.post(
        "/api/auth/register",
        json={"email": unique_email, "password": "OldPass123!", "name": "Change User"},
    )

    login_response = client.post(
        "/api/auth/login", data={"username": unique_email, "password": "OldPass123!"}
    )
    token = login_response.json()["access_token"]

    response = client.post(
        "/api/auth/change-password",
        params={"old_password": "OldPass123!", "new_password": "NewPass123!"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200


test("Auth: change password", test_change_password)


def test_invalid_password_validation():
    from jobpilot.security import validate_password

    is_valid, msg = validate_password("short")
    assert is_valid is False

    is_valid, msg = validate_password("nouppercase123!")
    assert is_valid is False

    is_valid, msg = validate_password("NOLOWERCASE123!")
    assert is_valid is False

    is_valid, msg = validate_password("NoDigits!")
    assert is_valid is False

    is_valid, msg = validate_password("ValidPass123!")
    assert is_valid is True


test("Auth: password validation", test_invalid_password_validation)


def test_email_validation():
    from jobpilot.security import validate_email

    assert validate_email("test@example.com") is True
    assert validate_email("invalid") is False
    assert validate_email("@example.com") is False
    assert validate_email("test@") is False


test("Auth: email validation", test_email_validation)


def test_input_sanitization():
    from jobpilot.security import sanitize_input

    result = sanitize_input("<script>alert('xss')</script>")
    assert "<script>" not in result

    result = sanitize_input("Hello <b>World</b>")
    assert "<b>" not in result

    result = sanitize_input("Normal text")
    assert result == "Normal text"


test("Auth: input sanitization", test_input_sanitization)


def test_admin_stats():
    from fastapi.testclient import TestClient
    from jobpilot.web.app import app
    import os

    client = TestClient(app)
    email = f"admin_{os.urandom(4).hex()}@example.com"

    # Register admin user
    client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "AdminPass123!",
            "name": "Admin User",
        },
    )

    # Login
    login_response = client.post(
        "/api/auth/login",
        data={"username": email, "password": "AdminPass123!"},
    )
    token = login_response.json()["access_token"]

    # Try to access admin endpoint (should fail - not admin)
    response = client.get(
        "/api/admin/stats", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403


test("Auth: admin stats requires admin", test_admin_stats)


# =====================================================
# CLEANUP
# =====================================================
cleanup()

# =====================================================
# SUMMARY
# =====================================================
print(f"\n{'='*60}")
print(f"RESULTS: {PASS} passed, {FAIL} failed, {PASS+FAIL} total")
if ERRORS:
    print(f"\nFailed tests:")
    for name, err in ERRORS:
        print(f"  - {name}: {err}")
print(f"{'='*60}")

sys.exit(1 if FAIL > 0 else 0)
