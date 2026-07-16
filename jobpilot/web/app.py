"""FastAPI web application for JobPilot dashboard."""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from jobpilot import database as db
from jobpilot.profile import load_profile, save_profile
from jobpilot.matcher import compute_match
from jobpilot.models import UserProfile, Application, Company
from jobpilot.config import DATA_DIR

app = FastAPI(title="JobPilot", version="0.1.0")

# Mount static files
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# --- Pydantic models for API ---

class ProfileUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    country: str | None = None
    linkedin: str | None = None
    github: str | None = None
    portfolio: str | None = None
    skills: list[str] | None = None
    programming_languages: list[str] | None = None
    frameworks: list[str] | None = None
    cloud_platforms: list[str] | None = None
    experience_years: int | None = None
    preferred_roles: list[str] | None = None
    preferred_locations: list[str] | None = None
    remote_preference: str | None = None
    expected_salary: str | None = None


class ApplicationCreate(BaseModel):
    job_id: str
    status: str = "discovered"
    notes: str = ""


class ApplicationUpdate(BaseModel):
    status: str | None = None
    notes: str | None = None


class ScanRequest(BaseModel):
    source: str = "all"
    role: str = ""
    location: str = ""
    limit: int = 50


class MatchRequest(BaseModel):
    min_score: float = 0.5
    limit: int = 20


# --- Routes ---

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Serve the dashboard SPA."""
    index_path = static_dir / "index.html"
    return HTMLResponse(content=index_path.read_text(encoding="utf-8"))


@app.get("/api/jobs")
async def list_jobs(
    q: str = "",
    source: str = "",
    min_score: float = 0.0,
):
    """List jobs with optional filters."""
    jobs = db.search_jobs(query=q, source=source, min_score=min_score)
    results = []
    for job in jobs:
        match = db.get_match_result(job.id)
        job_dict = job.to_dict()
        if match:
            job_dict["match_score"] = match.overall_score
            job_dict["strengths"] = match.strengths
            job_dict["missing_skills"] = match.missing_skills
        results.append(job_dict)
    return {"jobs": results, "total": len(results)}


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    """Get a single job with match details."""
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    match = db.get_match_result(job.id)
    result = job.to_dict()
    if match:
        result["match"] = {
            "overall_score": match.overall_score,
            "skills_score": match.skills_score,
            "experience_score": match.experience_score,
            "relevance_score": match.relevance_score,
            "education_score": match.education_score,
            "role_score": match.role_score,
            "location_score": match.location_score,
            "strengths": match.strengths,
            "weaknesses": match.weaknesses,
            "missing_skills": match.missing_skills,
        }
    return result


@app.post("/api/scan")
async def trigger_scan(request: ScanRequest):
    """Trigger a job scan."""
    import asyncio
    from jobpilot.scraper import SCRAPERS

    scrapers_to_run = SCRAPERS if request.source == "all" else {request.source: SCRAPERS[request.source]}
    all_jobs = []

    for name, scraper_cls in scrapers_to_run.items():
        try:
            scraper = scraper_cls()
            jobs = await scraper.search(query=request.role, location=request.location)
            jobs = jobs[:request.limit]
            all_jobs.extend(jobs)
            for job in jobs:
                db.upsert_job(job)
                db.upsert_company(Company(name=job.company))
        except Exception as e:
            continue

    return {"jobs_found": len(all_jobs), "sources": list(scrapers_to_run.keys())}


@app.post("/api/match/run")
async def run_matching(request: MatchRequest):
    """Run matching against all jobs."""
    profile = load_profile()
    if not profile.name:
        raise HTTPException(status_code=400, detail="No profile configured")

    jobs = db.get_all_jobs()
    matched = []
    for job in jobs:
        result = compute_match(profile, job)
        if result.overall_score >= request.min_score:
            db.save_match_result(result)
            matched.append({
                "job_id": result.job_id,
                "company": job.company,
                "title": job.title,
                "overall_score": result.overall_score,
                "strengths": result.strengths,
                "missing_skills": result.missing_skills,
            })

    matched.sort(key=lambda x: x["overall_score"], reverse=True)
    return {"matched": matched[:request.limit], "total": len(matched)}


@app.get("/api/profile")
async def get_profile():
    """Get user profile."""
    profile = load_profile()
    return profile.__dict__


@app.put("/api/profile")
async def update_profile_api(update: ProfileUpdate):
    """Update user profile."""
    profile = load_profile()
    update_data = update.model_dump(exclude_none=True)
    for key, value in update_data.items():
        if hasattr(profile, key):
            setattr(profile, key, value)
    save_profile(profile)
    return profile.__dict__


@app.get("/api/applications")
async def list_applications(status: str = ""):
    """List tracked applications."""
    apps = db.get_applications(status=status)
    return {"applications": [a.__dict__ for a in apps], "total": len(apps)}


@app.post("/api/applications")
async def create_application(request: ApplicationCreate):
    """Add a job to the tracker."""
    job = db.get_job(request.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    profile = load_profile()
    match = compute_match(profile, job)

    app_item = Application(
        job_id=job.id,
        company=job.company,
        role=job.title,
        status=request.status,
        match_score=match.overall_score,
        notes=request.notes,
    )
    db.upsert_application(app_item)
    return app_item.__dict__


@app.patch("/api/applications/{app_id}")
async def update_application(app_id: str, update: ApplicationUpdate):
    """Update an application."""
    if update.status:
        found = db.update_application_status(app_id, update.status)
        if not found:
            raise HTTPException(status_code=404, detail="Application not found")
    return {"updated": True}


@app.get("/api/stats")
async def get_stats():
    """Get dashboard statistics."""
    return db.get_stats()


@app.get("/api/companies")
async def list_companies():
    """List tracked companies."""
    companies = db.get_companies()
    return {"companies": [c.__dict__ for c in companies], "total": len(companies)}
