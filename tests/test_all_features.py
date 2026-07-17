"""Comprehensive feature tests for JobPilot — every feature, every edge case."""

import sys
import json
import hashlib
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobpilot.models import UserProfile, JobListing, MatchResult, Application, Company, Resume, _generate_id
from jobpilot.config import WEIGHTS, MATCH_THRESHOLD
from jobpilot import database as db
from jobpilot.profile import load_profile, save_profile
from jobpilot.matcher import compute_match
from jobpilot.resume_analyzer import (
    analyze_resume, ResumeAnalysisResult, _extract_skills, _detect_sections,
    _compute_ats_score, _extract_contact, _extract_education,
    _estimate_experience_years, _generate_suggestions, _identify_strengths,
    _identify_weaknesses, SKILL_DATABASE, _ALIAS_MAP,
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
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()]
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
    j = JobListing(company="TestCo", title="Engineer", url="http://test.com/1", source="test")
    is_new = db.upsert_job(j, TEST_DB)
    assert is_new is True


test("DB: upsert job new", test_db_upsert_job_new)


def test_db_upsert_job_duplicate():
    cleanup()
    j = JobListing(company="TestCo", title="Engineer", url="http://test.com/1", source="test")
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
        j = JobListing(company=f"Co{i}", title=f"Role{i}", url=f"http://test.com/{i}", source="test")
        db.upsert_job(j, TEST_DB)
    jobs = db.get_all_jobs(TEST_DB)
    assert len(jobs) == 5


test("DB: get all jobs", test_db_get_all_jobs)


def test_db_search_by_query():
    cleanup()
    db.upsert_job(JobListing(company="PythonCo", title="Python Dev", url="http://a.com", source="greenhouse", description="python"), TEST_DB)
    db.upsert_job(JobListing(company="JavaCo", title="Java Dev", url="http://b.com", source="linkedin", description="java"), TEST_DB)
    results = db.search_jobs(query="python", db_path=TEST_DB)
    assert len(results) == 1
    assert results[0].company == "PythonCo"


test("DB: search jobs by query", test_db_search_by_query)


def test_db_search_by_source():
    cleanup()
    db.upsert_job(JobListing(company="A", title="A", url="http://a.com", source="greenhouse"), TEST_DB)
    db.upsert_job(JobListing(company="B", title="B", url="http://b.com", source="linkedin"), TEST_DB)
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
    db.upsert_application(Application(job_id=j.id, company="Co", role="R", status="applied"), TEST_DB)
    db.upsert_application(Application(job_id=j.id, company="Co", role="R2", status="interview"), TEST_DB)
    applied = db.get_applications(status="applied", db_path=TEST_DB)
    assert len(applied) == 1
    assert applied[0].status == "applied"


test("DB: application filter by status", test_db_application_filter_by_status)


def test_db_match_result():
    cleanup()
    j = JobListing(company="MatchCo", title="Dev", url="http://match.com", source="test")
    db.upsert_job(j, TEST_DB)
    m = MatchResult(job_id=j.id, overall_score=0.85, skills_score=0.9, strengths=["Good"], missing_skills=["rust"])
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
    assert fetched.role_score == 0.9, f"Expected role_score=0.9, got {fetched.role_score}"
    assert fetched.location_score == 0.3, f"Expected location_score=0.3, got {fetched.location_score}"


test("DB: match result role_score correct", test_db_match_result_role_score)


def test_db_stats():
    cleanup()
    for i in range(3):
        db.upsert_job(JobListing(company=f"C{i}", title=f"R{i}", url=f"http://s{i}.com", source="greenhouse"), TEST_DB)
    stats = db.get_stats(TEST_DB)
    assert stats["total_jobs"] == 3
    assert stats["total_companies"] == 0


test("DB: stats", test_db_stats)


def test_db_resume_crud():
    cleanup()
    r = Resume(id="r1", name="test", filename="t.txt", raw_text="hello", target_role="dev")
    is_new = db.upsert_resume(r, TEST_DB)
    assert is_new is True
    fetched = db.get_resume("r1", TEST_DB)
    assert fetched is not None
    assert fetched.raw_text == "hello"
    # Update
    is_new = db.upsert_resume(Resume(id="r1", name="updated", filename="t.txt", raw_text="hello2"), TEST_DB)
    assert is_new is False
    fetched = db.get_resume("r1", TEST_DB)
    assert fetched.name == "updated"


test("DB: resume CRUD", test_db_resume_crud)


def test_db_resume_list():
    cleanup()
    for i in range(3):
        db.upsert_resume(Resume(id=f"r{i}", name=f"resume_{i}", filename=f"f{i}.txt", raw_text="text"), TEST_DB)
    resumes = db.get_all_resumes(TEST_DB)
    assert len(resumes) == 3
    # raw_text should not be loaded
    assert resumes[0].raw_text == ""


test("DB: resume list excludes raw_text", test_db_resume_list)


def test_db_resume_delete_cascades():
    cleanup()
    db.upsert_resume(Resume(id="del", name="x", filename="x.txt", raw_text="text"), TEST_DB)
    db.save_resume_analysis(
        resume_id="del", ats_score=0.5, resume_quality_score=0.5,
        technical_strength_score=0.5, hiring_readiness_score=0.5,
        skills=[], strengths=[], weaknesses=[], missing_skills=[], suggestions=[],
        db_path=TEST_DB,
    )
    found = db.delete_resume("del", TEST_DB)
    assert found is True
    assert db.get_resume("del", TEST_DB) is None
    assert len(db.get_resume_analyses("del", TEST_DB)) == 0


test("DB: resume delete cascades to analyses", test_db_resume_delete_cascades)


def test_db_resume_analysis_save_and_get():
    cleanup()
    db.upsert_resume(Resume(id="ra1", name="r", filename="f.txt", raw_text="t"), TEST_DB)
    db.save_resume_analysis(
        resume_id="ra1", ats_score=0.85, resume_quality_score=0.80,
        technical_strength_score=0.90, hiring_readiness_score=0.82,
        skills=["python", "react"], strengths=["Strong"], weaknesses=["Weak"],
        missing_skills=["rust"], suggestions=["Add projects"],
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
        skills=["python", "react", "aws"], programming_languages=["python"],
        frameworks=["react"], cloud_platforms=["aws"], experience_years=5,
        preferred_roles=["software engineer"], preferred_locations=["remote"],
        remote_preference="remote",
    )
    job = JobListing(company="Co", title="Software Engineer", location="Remote",
                     remote_status="remote", required_skills=["python", "react"], experience_years=3)
    result = compute_match(profile, job)
    assert result.overall_score >= 0.6, f"Expected >= 0.6, got {result.overall_score}"
    assert len(result.strengths) > 0


test("Match: strong match", test_match_strong)


def test_match_poor():
    profile = UserProfile(skills=["cooking"], experience_years=1, preferred_roles=["chef"], remote_preference="onsite")
    job = JobListing(company="TechCo", title="Senior Rust Engineer", location="San Francisco",
                     remote_status="onsite", required_skills=["rust", "c++", "go"], experience_years=8)
    result = compute_match(profile, job)
    assert result.overall_score < 0.5, f"Expected < 0.5, got {result.overall_score}"
    assert len(result.missing_skills) > 0


test("Match: poor match", test_match_poor)


def test_match_skills_weight():
    profile = UserProfile(skills=["python", "django", "postgresql"])
    job_no = JobListing(company="Co", title="Dev", required_skills=[], experience_years=2)
    job_all = JobListing(company="Co", title="Dev", required_skills=["python", "django", "postgresql"], experience_years=2)
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
    job_remote = JobListing(company="Co", title="Dev", location="Remote", remote_status="remote", required_skills=[])
    job_onsite = JobListing(company="Co", title="Dev", location="New York", remote_status="onsite", required_skills=[])
    r1 = compute_match(profile, job_remote)
    r2 = compute_match(profile, job_onsite)
    assert r1.location_score > r2.location_score


test("Match: remote preference", test_match_location_remote)


def test_match_weights_sum():
    assert abs(sum(WEIGHTS.values()) - 1.0) < 0.001


test("Match: weights sum to 1.0", test_match_weights_sum)


def test_match_result_fields_valid():
    profile = UserProfile(skills=["python"], experience_years=3)
    job = JobListing(company="Co", title="Dev", required_skills=["python"], experience_years=2)
    result = compute_match(profile, job)
    assert 0 <= result.overall_score <= 1
    assert 0 <= result.skills_score <= 1
    assert 0 <= result.experience_score <= 1
    assert isinstance(result.strengths, list)
    assert isinstance(result.missing_skills, list)


test("Match: result fields valid", test_match_result_fields_valid)


def test_match_no_skills_neutral():
    profile = UserProfile(skills=["python"])
    job = JobListing(company="Co", title="Dev", required_skills=[], preferred_skills=[], experience_years=2)
    result = compute_match(profile, job)
    assert result.skills_score == 0.5, "No skills specified should give neutral score"


test("Match: no skills = neutral score", test_match_no_skills_neutral)


def test_match_no_experience_req():
    profile = UserProfile(experience_years=2)
    job = JobListing(company="Co", title="Dev", required_skills=[], experience_years=0)
    result = compute_match(profile, job)
    assert result.experience_score == 0.7, "No experience req should give neutral-positive"


test("Match: no experience req = neutral", test_match_no_experience_req)


def test_match_preferred_skills():
    profile = UserProfile(skills=["python", "docker"])
    job = JobListing(company="Co", title="Dev", required_skills=["python"], preferred_skills=["docker"], experience_years=2)
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
        assert name not in KNOWN_GREENHOUSE_BOARDS, f"Invalid board {name} should be removed"


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
    data = {"position": "Dev", "company": "Co", "description": "Python and React developer"}
    job = scraper._parse_job(data)
    assert "python" in job.required_skills, f"Expected python in skills, got {job.required_skills}"
    assert "react" in job.required_skills, f"Expected react in skills, got {job.required_skills}"


test("Scraper: remoteok fallback to description skills", test_remoteok_parse_job_no_tags)


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
    for s in ["python", "react", "docker", "aws", "postgresql", "fastapi", "kubernetes", "git"]:
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
    assert result.experience_years >= 4, f"Expected >= 4 years, got {result.experience_years}"


test("Resume: experience years", test_resume_experience_years)


def test_resume_education():
    result = analyze_resume(SAMPLE_RESUME)
    assert len(result.education) > 0
    assert any("stanford" in e.lower() for e in result.education)


test("Resume: education extraction", test_resume_education)


def test_resume_scores_in_range():
    result = analyze_resume(SAMPLE_RESUME)
    for score_name in ["ats_score", "resume_quality_score", "technical_strength_score", "hiring_readiness_score"]:
        score = getattr(result, score_name)
        assert 0.0 <= score <= 1.0, f"{score_name} out of range: {score}"


test("Resume: scores in valid range", test_resume_scores_in_range)


def test_resume_strengths():
    result = analyze_resume(SAMPLE_RESUME)
    assert len(result.strengths) > 0
    assert any("skill" in s.lower() or "experience" in s.lower() for s in result.strengths)


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


test("Resume: suggestion for missing LinkedIn", test_resume_suggestion_for_missing_linkedin)


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
    scores = [result.ats_score, result.technical_strength_score, result.resume_quality_score]
    assert min(scores) <= result.hiring_readiness_score <= max(scores) + 0.1


test("Resume: hiring readiness is composite", test_resume_hiring_readiness_composite)


# =====================================================
# INTEGRATION
# =====================================================
print("\n=== Integration ===")


def test_seed_match_rank():
    cleanup()
    profile = UserProfile(
        name="TestUser", skills=["python", "react", "aws"],
        programming_languages=["python"], frameworks=["react"],
        cloud_platforms=["aws"], experience_years=4,
        preferred_roles=["software engineer"], preferred_locations=["remote"],
        remote_preference="remote",
    )
    jobs = [
        JobListing(company="Co1", title="Python Engineer", url="http://c1.com", source="test",
                   required_skills=["python", "aws"], experience_years=3, remote_status="remote", location="Remote"),
        JobListing(company="Co2", title="Rust Engineer", url="http://c2.com", source="test",
                   required_skills=["rust", "c++"], experience_years=5, remote_status="onsite", location="NYC"),
        JobListing(company="Co3", title="Full Stack", url="http://c3.com", source="test",
                   required_skills=["python", "react"], experience_years=2, remote_status="remote", location="Remote"),
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
    db.upsert_resume(Resume(id=resume_id, name="test", filename="test.txt",
                            raw_text=SAMPLE_RESUME, target_role="backend engineer"), TEST_DB)
    db.save_resume_analysis(
        resume_id=resume_id, ats_score=result.ats_score,
        resume_quality_score=result.resume_quality_score,
        technical_strength_score=result.technical_strength_score,
        hiring_readiness_score=result.hiring_readiness_score,
        skills=result.skills, strengths=result.strengths,
        weaknesses=result.weaknesses, missing_skills=result.missing_skills,
        suggestions=result.suggestions, db_path=TEST_DB,
    )
    analyses = db.get_resume_analyses(resume_id, TEST_DB)
    assert len(analyses) == 1
    assert analyses[0]["ats_score"] == result.ats_score


test("Integration: resume analyze + store", test_resume_analyze_and_store)


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
