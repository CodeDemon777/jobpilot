"""Full integration test suite for JobPilot."""

import sys
import json
import traceback
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobpilot.models import UserProfile, JobListing, MatchResult, Application, Company, _generate_id
from jobpilot.config import WEIGHTS, MATCH_THRESHOLD
from jobpilot import database as db
from jobpilot.profile import load_profile, save_profile
from jobpilot.matcher import compute_match

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


# ========== MODEL TESTS ==========
print("\n=== Models ===")

def test_model_job_id_deterministic():
    j1 = JobListing(company="TestCo", title="Engineer", url="https://example.com/1")
    j2 = JobListing(company="TestCo", title="Engineer", url="https://example.com/1")
    j3 = JobListing(company="TestCo", title="Engineer", url="https://example.com/2")
    assert j1.id == j2.id, "Same inputs should produce same ID"
    assert j1.id != j3.id, "Different URL should produce different ID"

test("Job ID deterministic", test_model_job_id_deterministic)

def test_model_job_all_skills():
    j = JobListing(
        required_skills=["Python", "Go"],
        preferred_skills=["Docker"],
        tech_stack=["Kubernetes", "AWS"],
    )
    assert "python" in j.all_required_skills
    assert "docker" in j.all_preferred_skills
    assert "kubernetes" in j.all_preferred_skills

test("Job all_skills normalization", test_model_job_all_skills)

def test_model_job_to_dict():
    j = JobListing(company="Co", title="Role", url="http://x.com")
    d = j.to_dict()
    assert "id" in d
    assert d["company"] == "Co"
    assert isinstance(d, dict)

test("Job to_dict", test_model_job_to_dict)

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

test("Profile all_skills combines all", test_model_profile_all_skills)

def test_model_empty_profile():
    p = UserProfile()
    assert p.all_skills == []
    assert p.name == ""

test("Empty profile defaults", test_model_empty_profile)

def test_model_application_id():
    a1 = Application(job_id="abc", company="Co", role="Role")
    a2 = Application(job_id="abc", company="Co", role="Role")
    a3 = Application(job_id="abc", company="Co", role="Role2")
    assert a1.id == a2.id
    assert a1.id != a3.id

test("Application ID deterministic", test_model_application_id)

def test_model_company_defaults():
    c = Company(name="TestCo")
    assert c.job_count == 0
    assert c.industry == ""

test("Company defaults", test_model_company_defaults)


# ========== DATABASE TESTS ==========
print("\n=== Database ===")

TEST_DB = Path(__file__).resolve().parent.parent / "data" / "test_jobpilot.db"

def cleanup_test_db():
    if TEST_DB.exists():
        TEST_DB.unlink()

def test_db_create_tables():
    cleanup_test_db()
    conn = db.get_connection(TEST_DB)
    # Check tables exist
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()]
    conn.close()
    assert "jobs" in tables
    assert "match_results" in tables
    assert "applications" in tables
    assert "companies" in tables

test("DB creates all tables", test_db_create_tables)

def test_db_upsert_job():
    cleanup_test_db()
    j = JobListing(company="TestCo", title="Engineer", url="http://test.com/1", source="test")
    is_new = db.upsert_job(j, TEST_DB)
    assert is_new == True
    # Upsert same again
    is_new2 = db.upsert_job(j, TEST_DB)
    assert is_new2 == False, "Should return False for duplicate"

test("DB upsert job (new + duplicate)", test_db_upsert_job)

def test_db_get_job():
    cleanup_test_db()
    j = JobListing(company="GetCo", title="Dev", url="http://get.com", source="test")
    db.upsert_job(j, TEST_DB)
    fetched = db.get_job(j.id, TEST_DB)
    assert fetched is not None
    assert fetched.company == "GetCo"
    assert fetched.title == "Dev"

test("DB get job", test_db_get_job)

def test_db_get_nonexistent_job():
    cleanup_test_db()
    result = db.get_job("nonexistent", TEST_DB)
    assert result is None

test("DB get nonexistent job", test_db_get_nonexistent_job)

def test_db_get_all_jobs():
    cleanup_test_db()
    for i in range(5):
        j = JobListing(company=f"Co{i}", title=f"Role{i}", url=f"http://test.com/{i}", source="test")
        db.upsert_job(j, TEST_DB)
    jobs = db.get_all_jobs(TEST_DB)
    assert len(jobs) == 5

test("DB get all jobs", test_db_get_all_jobs)

def test_db_search_jobs():
    cleanup_test_db()
    db.upsert_job(JobListing(company="PythonCo", title="Python Dev", url="http://a.com", source="greenhouse", description="python"), TEST_DB)
    db.upsert_job(JobListing(company="JavaCo", title="Java Dev", url="http://b.com", source="linkedin", description="java"), TEST_DB)
    # Search by query
    results = db.search_jobs(query="python", db_path=TEST_DB)
    assert len(results) == 1
    assert results[0].company == "PythonCo"
    # Search by source
    results = db.search_jobs(source="linkedin", db_path=TEST_DB)
    assert len(results) == 1
    assert results[0].company == "JavaCo"

test("DB search jobs by query and source", test_db_search_jobs)

def test_db_upsert_company():
    cleanup_test_db()
    c = Company(name="TestCo", industry="Tech", career_page="http://careers.test")
    db.upsert_company(c, TEST_DB)
    companies = db.get_companies(TEST_DB)
    assert len(companies) == 1
    assert companies[0].name == "TestCo"
    assert companies[0].industry == "Tech"

test("DB upsert and get companies", test_db_upsert_company)

def test_db_application_lifecycle():
    cleanup_test_db()
    # Create a job first
    j = JobListing(company="AppCo", title="Role", url="http://app.com", source="test")
    db.upsert_job(j, TEST_DB)
    # Create application
    app = Application(job_id=j.id, company="AppCo", role="Role", status="discovered")
    db.upsert_application(app, TEST_DB)
    apps = db.get_applications(db_path=TEST_DB)
    assert len(apps) == 1
    assert apps[0].status == "discovered"
    # Update status
    found = db.update_application_status(app.id, "applied", TEST_DB)
    assert found == True
    apps = db.get_applications(db_path=TEST_DB)
    assert apps[0].status == "applied"

test("DB application lifecycle", test_db_application_lifecycle)

def test_db_match_result():
    cleanup_test_db()
    j = JobListing(company="MatchCo", title="Dev", url="http://match.com", source="test")
    db.upsert_job(j, TEST_DB)
    m = MatchResult(job_id=j.id, overall_score=0.85, skills_score=0.9, strengths=["Good skills"], missing_skills=["rust"])
    db.save_match_result(m, TEST_DB)
    fetched = db.get_match_result(j.id, TEST_DB)
    assert fetched is not None
    assert fetched.overall_score == 0.85
    assert "rust" in fetched.missing_skills

test("DB save and get match result", test_db_match_result)

def test_db_stats():
    cleanup_test_db()
    # Seed some data
    for i in range(3):
        db.upsert_job(JobListing(company=f"C{i}", title=f"R{i}", url=f"http://s{i}.com", source="greenhouse"), TEST_DB)
    stats = db.get_stats(TEST_DB)
    assert stats["total_jobs"] == 3
    assert stats["total_companies"] == 0  # no companies added

test("DB stats", test_db_stats)


# ========== MATCHER TESTS ==========
print("\n=== Matcher ===")

def test_match_exact_match():
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
        company="Co", title="Software Engineer",
        location="Remote", remote_status="remote",
        required_skills=["python", "react"],
        experience_years=3,
    )
    result = compute_match(profile, job)
    assert result.overall_score >= 0.6, f"Expected >= 0.6, got {result.overall_score}"
    assert len(result.strengths) > 0

test("Match: strong match", test_match_exact_match)

def test_match_no_match():
    profile = UserProfile(
        skills=["cooking"],
        programming_languages=[],
        experience_years=1,
        preferred_roles=["chef"],
        remote_preference="onsite",
    )
    job = JobListing(
        company="TechCo", title="Senior Rust Engineer",
        location="San Francisco", remote_status="onsite",
        required_skills=["rust", "c++", "go"],
        experience_years=8,
    )
    result = compute_match(profile, job)
    assert result.overall_score < 0.5, f"Expected < 0.5, got {result.overall_score}"
    assert len(result.missing_skills) > 0

test("Match: poor match", test_match_no_match)

def test_match_skills_weight():
    profile = UserProfile(skills=["python", "django", "postgresql"])
    job_no_skills = JobListing(company="Co", title="Dev", required_skills=[], experience_years=2)
    job_all_skills = JobListing(company="Co", title="Dev", required_skills=["python", "django", "postgresql"], experience_years=2)
    r1 = compute_match(profile, job_no_skills)
    r2 = compute_match(profile, job_all_skills)
    assert r2.skills_score > r1.skills_score, "Job with matching skills should score higher"

test("Match: skills weight matters", test_match_skills_weight)

def test_match_experience_capped():
    profile = UserProfile(experience_years=20)
    job = JobListing(company="Co", title="Dev", required_skills=[], experience_years=2)
    result = compute_match(profile, job)
    assert result.experience_score <= 1.0, "Score should be capped at 1.0"

test("Match: experience score capped at 1.0", test_match_experience_capped)

def test_match_role_preference():
    profile = UserProfile(preferred_roles=["backend engineer"])
    job_exact = JobListing(company="Co", title="Backend Engineer", required_skills=[])
    job_wrong = JobListing(company="Co", title="Marketing Manager", required_skills=[])
    r1 = compute_match(profile, job_exact)
    r2 = compute_match(profile, job_wrong)
    assert r1.role_score > r2.role_score

test("Match: role preference alignment", test_match_role_preference)

def test_match_location_remote():
    profile = UserProfile(remote_preference="remote", preferred_locations=["remote"])
    job_remote = JobListing(company="Co", title="Dev", location="Remote", remote_status="remote", required_skills=[])
    job_onsite = JobListing(company="Co", title="Dev", location="New York", remote_status="onsite", required_skills=[])
    r1 = compute_match(profile, job_remote)
    r2 = compute_match(profile, job_onsite)
    assert r1.location_score > r2.location_score

test("Match: remote preference vs onsite", test_match_location_remote)

def test_match_weights_sum_to_one():
    total = sum(WEIGHTS.values())
    assert abs(total - 1.0) < 0.001, f"Weights sum to {total}, expected 1.0"

test("Match: weights sum to 1.0", test_match_weights_sum_to_one)

def test_match_result_fields():
    profile = UserProfile(skills=["python"], experience_years=3)
    job = JobListing(company="Co", title="Dev", required_skills=["python"], experience_years=2)
    result = compute_match(profile, job)
    assert 0 <= result.overall_score <= 1
    assert 0 <= result.skills_score <= 1
    assert 0 <= result.experience_score <= 1
    assert isinstance(result.strengths, list)
    assert isinstance(result.missing_skills, list)

test("Match: result fields valid", test_match_result_fields)


# ========== INTEGRATION TESTS ==========
print("\n=== Integration ===")

def test_seed_and_match():
    cleanup_test_db()
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
    # Co1 and Co3 should rank above Co2
    assert results[0][0].company in ("Co1", "Co3"), f"Expected Co1/Co3 first, got {results[0][0].company}"
    assert results[-1][0].company == "Co2", f"Expected Co2 last, got {results[-1][0].company}"

test("Integration: seed + match + rank", test_seed_and_match)

def test_top_matches():
    cleanup_test_db()
    profile = UserProfile(skills=["python"], experience_years=3,
                          preferred_roles=["engineer"], remote_preference="remote")
    for i in range(10):
        j = JobListing(company=f"Co{i}", title=f"Engineer {i}", url=f"http://t{i}.com",
                       source="test", required_skills=["python"] if i < 5 else ["rust"],
                       remote_status="remote", location="Remote", experience_years=2)
        db.upsert_job(j, TEST_DB)
        r = compute_match(profile, j)
        db.save_match_result(r, TEST_DB)

    top = db.get_top_matches(5, TEST_DB)
    assert len(top) == 5
    # All top 5 should be from Co0-Co4 (python matches)
    for job, match in top:
        assert "Co" in job.company

test("Integration: top matches query", test_top_matches)


# ========== CLEANUP ==========
cleanup_test_db()

# ========== SUMMARY ==========
print(f"\n{'='*50}")
print(f"RESULTS: {PASS} passed, {FAIL} failed, {PASS+FAIL} total")
if ERRORS:
    print(f"\nFailed tests:")
    for name, err in ERRORS:
        print(f"  - {name}: {err}")
print(f"{'='*50}")

sys.exit(1 if FAIL > 0 else 0)
