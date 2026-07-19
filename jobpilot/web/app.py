"""FastAPI web application for JobPilot dashboard."""

from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from jobpilot import database as db
from jobpilot.profile import load_profile, save_profile
from jobpilot.matcher import compute_match
from jobpilot.models import (
    UserProfile, Application, Company, Resume,
    CoverLetter, InterviewQuestion, SkillGapReport, LinkedInReport,
    TailoredResume, AlertSubscription, DashboardStats,
)
from jobpilot.config import DATA_DIR
from jobpilot.resume_analyzer import analyze_resume
from jobpilot.auth import (
    UserCreate, UserLogin, UserResponse, Token, TokenData,
    get_password_hash, authenticate_user, register_user,
    create_access_token, create_refresh_token, get_current_user,
    refresh_access_token,
)
from jobpilot.security import validate_email, validate_password
from jobpilot.security import limiter, setup_cors, sanitize_input, get_client_ip

app = FastAPI(title="JobPilot", version="0.3.0", description="AI-powered career assistant")


# ============================================================================
# HEALTH CHECK ENDPOINTS
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    try:
        conn = db.get_connection()
        conn.execute("SELECT 1")
        conn.close()
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "version": "0.3.0",
        "database": db_status,
    }


@app.get("/ready")
async def readiness_check():
    """Readiness check endpoint for load balancers."""
    try:
        conn = db.get_connection()
        conn.execute("SELECT 1")
        conn.close()
        return {"status": "ready"}
    except Exception:
        return {"status": "not ready"}


@app.get("/metrics")
async def metrics():
    """Basic metrics endpoint."""
    try:
        stats = db.get_stats()
        return {
            "total_jobs": stats.get("total_jobs", 0),
            "total_companies": stats.get("total_companies", 0),
            "total_applications": stats.get("total_applications", 0),
        }
    except Exception:
        return {"error": "Failed to fetch metrics"}

# Setup security middleware
setup_cors(app)
app.state.limiter = limiter

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
    is_verified: bool | None = None
    verified_at: str | None = None


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


class ResumeAnalyzeRequest(BaseModel):
    text: str
    target_role: str = ""
    filename: str = "pasted_resume"


# --- Authentication Routes ---

@app.post("/api/auth/register", response_model=UserResponse)
async def register(user: UserCreate):
    """Register a new user."""
    # Validate email
    if not validate_email(user.email):
        raise HTTPException(status_code=400, detail="Invalid email format")

    # Validate password
    is_valid, message = validate_password(user.password)
    if not is_valid:
        raise HTTPException(status_code=400, detail=message)

    # Register user
    new_user = register_user(user.email, user.password, user.name)

    # Log audit event
    db.log_audit(new_user["id"], "register", "user", {"email": user.email})

    return UserResponse(
        id=new_user["id"],
        email=new_user["email"],
        name=new_user["name"],
        is_active=True,
        created_at=datetime.now().isoformat(),
    )


@app.post("/api/auth/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Login with email and password."""
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password",
        )

    # Create tokens
    access_token = create_access_token(data={"sub": user["id"], "email": user["email"]})
    refresh_token = create_refresh_token(data={"sub": user["id"], "email": user["email"]})

    # Log audit event
    db.log_audit(user["id"], "login", "user", {"email": user["email"]})

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@app.post("/api/auth/refresh", response_model=Token)
async def refresh_token(refresh_token: str):
    """Refresh access token using refresh token."""
    new_access_token = refresh_access_token(refresh_token)
    return Token(
        access_token=new_access_token,
        refresh_token=refresh_token,
    )


@app.get("/api/auth/me", response_model=UserResponse)
async def get_me(current_user: TokenData = Depends(get_current_user)):
    """Get current user profile."""
    user = db.get_user_by_id(current_user.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(**user)


@app.put("/api/auth/profile", response_model=UserResponse)
async def update_auth_profile(
    name: str | None = None,
    current_user: TokenData = Depends(get_current_user),
):
    """Update current user's name."""
    updates = {}
    if name is not None:
        updates["name"] = sanitize_input(name)

    if updates:
        db.update_user(current_user.user_id, updates)
        db.log_audit(current_user.user_id, "profile_update", "user")

    user = db.get_user_by_id(current_user.user_id)
    return UserResponse(**user)


@app.post("/api/auth/change-password")
async def change_password(
    old_password: str,
    new_password: str,
    current_user: TokenData = Depends(get_current_user),
):
    """Change user password."""
    user = db.get_user_by_email(current_user.email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    from jobpilot.auth import verify_password, get_password_hash
    if not verify_password(old_password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="Incorrect password")

    is_valid, message = validate_password(new_password)
    if not is_valid:
        raise HTTPException(status_code=400, detail=message)

    hashed = get_password_hash(new_password)
    db.update_user(current_user.user_id, {"password_hash": hashed})
    db.log_audit(current_user.user_id, "password_change", "user")

    return {"message": "Password updated successfully"}


@app.get("/api/auth/audit-logs")
async def get_audit_logs(
    limit: int = 50,
    current_user: TokenData = Depends(get_current_user),
):
    """Get audit logs for current user (admin only for all users)."""
    user = db.get_user_by_id(current_user.user_id)
    if user and user.get("is_admin"):
        logs = db.get_audit_logs(limit=limit)
    else:
        logs = db.get_audit_logs(user_id=current_user.user_id, limit=limit)
    return {"logs": logs, "total": len(logs)}


# --- Admin Routes ---

@app.get("/api/admin/users")
async def admin_list_users(
    limit: int = 50,
    current_user: TokenData = Depends(get_current_user),
):
    """List all users (admin only)."""
    user = db.get_user_by_id(current_user.user_id)
    if not user or not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")

    stats = db.get_user_stats()
    return {"stats": stats, "message": "Admin access granted"}


@app.get("/api/admin/stats")
async def admin_stats(current_user: TokenData = Depends(get_current_user)):
    """Get admin statistics."""
    user = db.get_user_by_id(current_user.user_id)
    if not user or not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")

    return {
        "users": db.get_user_stats(),
        "jobs": db.get_stats(),
        "scan_stats": db.get_scan_stats(),
    }


class VerificationRequest(BaseModel):
    entity_type: str  # 'profile' or 'resume'
    entity_id: str    # 'profile' for profile, resume_id for resume


class VerificationConfirmRequest(BaseModel):
    entity_type: str
    entity_id: str
    verified_data: dict


class VerificationDeclineRequest(BaseModel):
    entity_type: str
    entity_id: str


# --- Feature 2: Resume Suggestions ---

class ResumeSuggestionsRequest(BaseModel):
    resume_id: str = ""
    resume_text: str = ""
    target_role: str = ""


# --- Feature 3: Cover Letter ---

class CoverLetterRequest(BaseModel):
    resume_id: str = ""
    resume_text: str = ""
    job_id: str = ""
    job_description: str = ""
    company_name: str = ""
    role_title: str = ""
    tone: str = "professional"
    candidate_name: str = ""


# --- Job Import ---

class JobImportRequest(BaseModel):
    url: str


# --- Feature 5: Interview Prep ---

class InterviewRequest(BaseModel):
    job_id: str = ""
    resume_id: str = ""
    resume_text: str = ""
    role_title: str = ""
    categories: list[str] = ["technical", "behavioral", "hr"]
    difficulty: str = "intermediate"
    count: int = 10


# --- Feature 6: Skill Gap ---

class SkillGapRequest(BaseModel):
    resume_id: str = ""
    resume_text: str = ""
    job_id: str = ""
    job_description: str = ""
    job_required_skills: list[str] = []
    job_preferred_skills: list[str] = []


# --- Feature 7: LinkedIn ---

class LinkedInRequest(BaseModel):
    headline: str = ""
    about: str = ""
    skills: str = ""
    experience: str = ""


# --- Feature 8: Resume Tailoring ---

class ResumeTailorRequest(BaseModel):
    resume_id: str = ""
    resume_text: str = ""
    job_id: str = ""
    job_description: str = ""
    job_skills: list[str] = []


# --- Feature 9: Alerts ---

class AlertSubscribeRequest(BaseModel):
    role: str = ""
    location: str = ""
    remote_only: bool = False
    experience_level: str = ""
    frequency: str = "daily"


class AlertUpdateRequest(BaseModel):
    role: str | None = None
    location: str | None = None
    remote_only: bool | None = None
    experience_level: str | None = None
    frequency: str | None = None
    is_active: bool | None = None


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


@app.get("/api/jobs/new/today")
async def get_new_jobs_today():
    """Get jobs discovered today."""
    jobs = db.get_jobs_discovered_today()
    return {"jobs": jobs, "total": len(jobs)}


@app.get("/api/jobs/new/week")
async def get_new_jobs_week():
    """Get jobs discovered this week."""
    jobs = db.get_jobs_discovered_this_week()
    return {"jobs": jobs, "total": len(jobs)}


@app.get("/api/jobs/high-match")
async def get_high_match_jobs(limit: int = 10):
    """Get recent jobs with high match scores."""
    jobs = db.get_recent_high_match_jobs(limit)
    return {"jobs": jobs, "total": len(jobs)}


@app.post("/api/jobs/import")
async def import_job_from_url(request: JobImportRequest):
    """Import a job from a URL (LinkedIn, Naukri, Indeed, etc.)."""
    from jobpilot.job_importer import JobImporter

    importer = JobImporter()
    job = await importer.import_from_url(request.url)

    if not job:
        raise HTTPException(status_code=400, detail="Could not extract job details from URL")

    # Store the imported job
    db.upsert_job(job)

    # Compute match score
    profile = load_profile()
    match_result = compute_match(profile, job)
    db.save_match_result(match_result)

    return {
        "job": job.to_dict(),
        "match_score": match_result.overall_score,
        "match_result": {
            "overall_score": match_result.overall_score,
            "skills_score": match_result.skills_score,
            "experience_score": match_result.experience_score,
            "strengths": match_result.strengths,
            "missing_skills": match_result.missing_skills,
        },
        "message": "Job imported successfully"
    }


@app.post("/api/jobs/{job_id}/deactivate")
async def deactivate_job(job_id: str):
    """Mark a job as inactive."""
    found = db.update_job_active_status(job_id, False)
    if not found:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"deactivated": True}


@app.post("/api/jobs/{job_id}/activate")
async def activate_job(job_id: str):
    """Mark a job as active."""
    found = db.update_job_active_status(job_id, True)
    if not found:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"activated": True}


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


# --- Resume Analysis ---

@app.post("/api/resume/analyze")
async def analyze_resume_api(request: ResumeAnalyzeRequest):
    """Analyze a resume from pasted text."""
    import hashlib

    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Resume text is empty")

    result = analyze_resume(request.text, target_role=request.target_role)

    # Save to database
    resume_id = hashlib.sha256(request.text.encode()).hexdigest()[:16]
    resume = Resume(
        id=resume_id,
        name=request.filename,
        filename=request.filename,
        raw_text=request.text,
        target_role=request.target_role,
    )
    db.upsert_resume(resume)
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
    )

    output = result.to_dict()
    output["resume_id"] = resume_id
    return output


@app.get("/api/resume/history")
async def resume_history():
    """List all previously analyzed resumes."""
    resumes = db.get_all_resumes()
    return {"resumes": [r.to_dict() for r in resumes], "total": len(resumes)}


# --- Verification ---

@app.post("/api/verify/request")
async def verification_requested(request: VerificationRequest):
    """Log that verification modal was opened."""
    db.log_verification_event(
        entity_type=request.entity_type,
        entity_id=request.entity_id,
        event_type="profile_verification_requested",
    )
    return {"logged": True}


@app.post("/api/verify/confirm")
async def verification_confirmed(request: VerificationConfirmRequest):
    """Log verification acceptance and mark profile as verified."""
    from datetime import datetime

    verified_at = datetime.now().isoformat()

    # Save profile data with verification flag
    profile = load_profile()
    for key, value in request.verified_data.items():
        if hasattr(profile, key):
            setattr(profile, key, value)
    profile.is_verified = True
    profile.verified_at = verified_at
    save_profile(profile)

    # Log acceptance event
    db.log_verification_event(
        entity_type=request.entity_type,
        entity_id=request.entity_id,
        event_type="profile_verification_accepted",
        event_data={"verified_data": request.verified_data},
    )

    # Log submission completed
    db.log_verification_event(
        entity_type=request.entity_type,
        entity_id=request.entity_id,
        event_type="submission_completed",
    )

    return {"verified": True, "verified_at": verified_at}


@app.post("/api/verify/decline")
async def verification_declined(request: VerificationDeclineRequest):
    """Log verification decline (user chose to edit)."""
    db.log_verification_event(
        entity_type=request.entity_type,
        entity_id=request.entity_id,
        event_type="profile_verification_declined",
    )
    return {"declined": True}


@app.get("/api/verify/status/{entity_type}/{entity_id}")
async def get_verification_status(entity_type: str, entity_id: str):
    """Get current verification status for an entity."""
    status = db.get_latest_verification_status(entity_type, entity_id)
    events = db.get_verification_events(entity_type=entity_type, entity_id=entity_id)
    return {**status, "events": events}


# ============================================================================
# FEATURE 1: Resume PDF Upload
# ============================================================================

@app.post("/api/resume/upload")
async def upload_resume(file: UploadFile = File(...), target_role: str = Form("")):
    """Upload a PDF or TXT resume file."""
    from jobpilot.pdf_parser import extract_text_from_file, validate_upload, generate_resume_id, get_file_type

    # Read file content
    content = await file.read()

    # Validate
    is_valid, error = validate_upload(content, file.filename)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error)

    # Extract text
    try:
        text = extract_text_from_file(content, file.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not text.strip():
        raise HTTPException(status_code=400, detail="Could not extract text from file")

    # Generate ID and save
    resume_id = generate_resume_id(content, file.filename)
    file_type = get_file_type(file.filename)

    # Analyze the resume
    result = analyze_resume(text, target_role=target_role)

    # Save to database
    resume = Resume(
        id=resume_id,
        name=file.filename,
        filename=file.filename,
        raw_text=text,
        target_role=target_role,
    )
    db.upsert_resume(resume)

    # Save upload record
    db.save_uploaded_resume(
        resume_id=resume_id,
        filename=file.filename,
        file_type=file_type,
        file_size=len(content),
        raw_text=text,
        extracted_data={"skills": result.skills, "name": result.name, "email": result.email},
    )

    # Save analysis
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
    )

    output = result.to_dict()
    output["resume_id"] = resume_id
    output["filename"] = file.filename
    output["file_type"] = file_type
    output["file_size"] = len(content)
    return output


@app.get("/api/resume/uploads")
async def list_uploads():
    """List all uploaded resumes."""
    uploads = db.get_all_uploaded_resumes()
    return {"uploads": uploads, "total": len(uploads)}


@app.delete("/api/resume/uploads/{resume_id}")
async def delete_upload(resume_id: str):
    """Delete an uploaded resume."""
    found = db.delete_uploaded_resume(resume_id)
    if not found:
        raise HTTPException(status_code=404, detail="Upload not found")
    return {"deleted": True}


# ============================================================================
# FEATURE 2: AI Resume Improvement Suggestions
# ============================================================================

@app.post("/api/resume/suggestions")
async def get_resume_suggestions(request: ResumeSuggestionsRequest):
    """Get detailed improvement suggestions for a resume."""
    from jobpilot.resume_improver import generate_improvement_report

    # Get resume text
    text = request.resume_text
    if not text and request.resume_id:
        resume = db.get_resume(request.resume_id)
        if resume:
            text = resume.raw_text

    if not text:
        raise HTTPException(status_code=400, detail="No resume text provided")

    report = generate_improvement_report(text, target_role=request.target_role)
    return report


# ============================================================================
# FEATURE 3: Cover Letter Generator
# ============================================================================

@app.post("/api/cover-letter/generate")
async def generate_cover_letter(request: CoverLetterRequest):
    """Generate a personalized cover letter."""
    from jobpilot.cover_letter_generator import generate_cover_letter

    # Get resume text
    text = request.resume_text
    if not text and request.resume_id:
        resume = db.get_resume(request.resume_id)
        if resume:
            text = resume.raw_text

    if not text:
        raise HTTPException(status_code=400, detail="No resume text provided")

    result = generate_cover_letter(
        resume_text=text,
        job_description=request.job_description,
        company=request.company_name,
        role=request.role_title,
        tone=request.tone,
        candidate_name=request.candidate_name,
    )

    # Save to database
    letter = CoverLetter(
        resume_id=request.resume_id,
        job_id=request.job_id,
        company_name=request.company_name,
        role_title=request.role_title,
        job_description=request.job_description,
        letter_text=result["letter_text"],
        tone=request.tone,
        word_count=result["word_count"],
    )
    letter_id = db.save_cover_letter(letter)
    result["id"] = letter_id

    return result


@app.get("/api/cover-letter/history")
async def cover_letter_history():
    """List all saved cover letters."""
    letters = db.get_cover_letters()
    return {"cover_letters": letters, "total": len(letters)}


@app.get("/api/cover-letter/{letter_id}")
async def get_cover_letter(letter_id: int):
    """Get a specific cover letter."""
    letter = db.get_cover_letter(letter_id)
    if not letter:
        raise HTTPException(status_code=404, detail="Cover letter not found")
    return letter


@app.delete("/api/cover-letter/{letter_id}")
async def delete_cover_letter_api(letter_id: int):
    """Delete a cover letter."""
    found = db.delete_cover_letter(letter_id)
    if not found:
        raise HTTPException(status_code=404, detail="Cover letter not found")
    return {"deleted": True}


# ============================================================================
# FEATURE 4: Enhanced Application Tracker
# ============================================================================

@app.get("/api/applications/stats")
async def get_application_stats():
    """Get application status statistics."""
    return db.get_application_stats()


@app.get("/api/applications/{app_id}")
async def get_application_detail(app_id: str):
    """Get a specific application with details."""
    app = db.get_application(app_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    return app.__dict__


@app.put("/api/applications/{app_id}")
async def update_application_full(app_id: str, update: ApplicationUpdate):
    """Update an application with full support."""
    updates = {}
    if update.status is not None:
        updates["status"] = update.status
    if update.notes is not None:
        updates["notes"] = update.notes

    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    found = db.update_application(app_id, updates)
    if not found:
        raise HTTPException(status_code=404, detail="Application not found")
    return {"updated": True}


@app.delete("/api/applications/{app_id}")
async def delete_application_api(app_id: str):
    """Delete an application."""
    found = db.delete_application(app_id)
    if not found:
        raise HTTPException(status_code=404, detail="Application not found")
    return {"deleted": True}


@app.post("/api/applications/{app_id}/notes")
async def add_note(app_id: str, note_type: str = "general", content: str = ""):
    """Add a note to an application."""
    if not content:
        raise HTTPException(status_code=400, detail="Note content required")
    note_id = db.add_application_note(app_id, note_type, content)
    return {"id": note_id, "created": True}


@app.get("/api/applications/{app_id}/notes")
async def get_notes(app_id: str):
    """Get all notes for an application."""
    notes = db.get_application_notes(app_id)
    return {"notes": notes, "total": len(notes)}


# ============================================================================
# FEATURE 5: Interview Preparation
# ============================================================================

@app.post("/api/interview/questions")
async def generate_interview_questions(request: InterviewRequest):
    """Generate interview questions."""
    from jobpilot.interview_coach import generate_questions

    # Get resume text
    text = request.resume_text
    if not text and request.resume_id:
        resume = db.get_resume(request.resume_id)
        if resume:
            text = resume.raw_text

    # Get skills from resume
    skills = []
    if text:
        from jobpilot.resume_analyzer import _extract_skills
        skills = _extract_skills(text)

    questions = generate_questions(
        role=request.role_title,
        skills=skills,
        resume_text=text,
        categories=request.categories,
        difficulty=request.difficulty,
        count=request.count,
    )

    # Save to database
    question_objects = [
        InterviewQuestion(
            job_id=request.job_id,
            resume_id=request.resume_id,
            role_title=request.role_title,
            category=q["category"],
            difficulty=q["difficulty"],
            question=q["question"],
            sample_answer=q["sample_answer"],
            tips=q["tips"],
        )
        for q in questions
    ]
    db.save_interview_questions(question_objects)

    return {"questions": questions, "total": len(questions)}


@app.get("/api/interview/history")
async def interview_history():
    """List past interview question sessions."""
    questions = db.get_interview_questions()
    return {"questions": questions, "total": len(questions)}


@app.delete("/api/interview/{question_id}")
async def delete_interview_questions(question_id: int):
    """Delete interview questions."""
    found = db.delete_interview_questions(question_id)
    if not found:
        raise HTTPException(status_code=404, detail="Question not found")
    return {"deleted": True}


# ============================================================================
# FEATURE 6: Skill Gap Analysis
# ============================================================================

@app.post("/api/skill-gap/analyze")
async def analyze_skill_gap(request: SkillGapRequest):
    """Analyze skill gap between resume and job requirements."""
    from jobpilot.skill_gap_analyzer import analyze_skill_gap

    # Get resume skills
    resume_skills = []
    if request.resume_text:
        from jobpilot.resume_analyzer import _extract_skills
        resume_skills = _extract_skills(request.resume_text)
    elif request.resume_id:
        resume = db.get_resume(request.resume_id)
        if resume:
            from jobpilot.resume_analyzer import _extract_skills
            resume_skills = _extract_skills(resume.raw_text)

    # Get job skills
    job_skills = request.job_required_skills
    if not job_skills and request.job_description:
        from jobpilot.resume_analyzer import _extract_skills
        job_skills = _extract_skills(request.job_description)
    elif not job_skills and request.job_id:
        job = db.get_job(request.job_id)
        if job:
            job_skills = job.all_required_skills

    result = analyze_skill_gap(
        resume_skills=resume_skills,
        job_required_skills=job_skills,
        job_preferred_skills=request.job_preferred_skills,
    )

    # Save report
    report = SkillGapReport(
        resume_id=request.resume_id,
        job_id=request.job_id,
        matched_skills=result["matched_skills"],
        missing_skills=result["missing_skills"],
        extra_skills=result["extra_skills"],
        match_percentage=result["match_percentage"],
        learning_areas=[area["category"] for area in result["learning_areas"]],
        priority_ranking=result["priority_ranking"],
    )
    report_id = db.save_skill_gap_report(report)
    result["report_id"] = report_id

    return result


@app.get("/api/skill-gap/history")
async def skill_gap_history():
    """List past skill gap reports."""
    reports = db.get_skill_gap_reports()
    return {"reports": reports, "total": len(reports)}


@app.get("/api/skill-gap/{report_id}")
async def get_skill_gap_report(report_id: int):
    """Get a specific skill gap report."""
    report = db.get_skill_gap_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


# ============================================================================
# FEATURE 7: LinkedIn Profile Analyzer
# ============================================================================

@app.post("/api/linkedin/analyze")
async def analyze_linkedin(request: LinkedInRequest):
    """Analyze LinkedIn profile content."""
    from jobpilot.linkedin_analyzer import analyze_linkedin_profile

    result = analyze_linkedin_profile(
        headline=request.headline,
        about=request.about,
        skills=request.skills,
        experience=request.experience,
    )

    # Save report
    report = LinkedInReport(
        headline=request.headline,
        about=request.about,
        skills_raw=request.skills,
        experience_raw=request.experience,
        suggestions=result["suggestions"],
        missing_keywords=result["missing_keywords"],
        visibility_score=result["visibility_score"],
        strength_score=result["strength_score"],
    )
    report_id = db.save_linkedin_report(report)
    result["report_id"] = report_id

    return result


@app.get("/api/linkedin/history")
async def linkedin_history():
    """List past LinkedIn analysis reports."""
    reports = db.get_linkedin_reports()
    return {"reports": reports, "total": len(reports)}


@app.get("/api/linkedin/{report_id}")
async def get_linkedin_report(report_id: int):
    """Get a specific LinkedIn report."""
    report = db.get_linkedin_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


# ============================================================================
# FEATURE 8: One-Click Resume Tailoring
# ============================================================================

@app.post("/api/resume/tailor")
async def tailor_resume(request: ResumeTailorRequest):
    """Generate a tailored resume for a specific job."""
    from jobpilot.resume_tailor import tailor_resume

    # Get resume text
    text = request.resume_text
    if not text and request.resume_id:
        resume = db.get_resume(request.resume_id)
        if resume:
            text = resume.raw_text

    if not text:
        raise HTTPException(status_code=400, detail="No resume text provided")

    # Get job description
    job_desc = request.job_description
    if not job_desc and request.job_id:
        job = db.get_job(request.job_id)
        if job:
            job_desc = job.description

    result = tailor_resume(
        resume_text=text,
        job_description=job_desc,
        job_skills=request.job_skills,
    )

    # Save to database
    tailored = TailoredResume(
        original_resume_id=request.resume_id,
        job_id=request.job_id,
        original_text=result["original_text"],
        tailored_text=result["tailored_text"],
        original_score=result["original_score"],
        tailored_score=result["tailored_score"],
        improvement_pct=result["improvement_pct"],
        keywords_added=result["keywords_added"],
    )
    tailored_id = db.save_tailored_resume(tailored)
    result["id"] = tailored_id

    return result


@app.get("/api/resume/tailored")
async def list_tailored_resumes():
    """List all tailored resume versions."""
    resumes = db.get_tailored_resumes()
    return {"tailored_resumes": resumes, "total": len(resumes)}


@app.get("/api/resume/tailored/{resume_id}")
async def get_tailored_resume(resume_id: int):
    """Get a specific tailored resume."""
    resume = db.get_tailored_resume(resume_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Tailored resume not found")
    return resume


@app.delete("/api/resume/tailored/{resume_id}")
async def delete_tailored_resume_api(resume_id: int):
    """Delete a tailored resume."""
    found = db.delete_tailored_resume(resume_id)
    if not found:
        raise HTTPException(status_code=404, detail="Tailored resume not found")
    return {"deleted": True}


# ============================================================================
# FEATURE 9: Email Alerts
# ============================================================================

@app.post("/api/alerts/subscribe")
async def subscribe_alert(request: AlertSubscribeRequest):
    """Create a job alert subscription."""
    alert = AlertSubscription(
        role=request.role,
        location=request.location,
        remote_only=request.remote_only,
        experience_level=request.experience_level,
        frequency=request.frequency,
    )
    alert_id = db.save_alert_subscription(alert)
    return {"id": alert_id, "created": True}


@app.post("/api/alerts/unsubscribe")
async def unsubscribe_alert(alert_id: int):
    """Deactivate a job alert subscription."""
    found = db.update_alert_subscription(alert_id, {"is_active": False})
    if not found:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"unsubscribed": True}


@app.get("/api/alerts/preferences")
async def get_alert_preferences():
    """Get all alert subscriptions."""
    alerts = db.get_alert_subscriptions()
    return {"alerts": alerts, "total": len(alerts)}


@app.put("/api/alerts/{alert_id}")
async def update_alert(alert_id: int, update: AlertUpdateRequest):
    """Update an alert subscription."""
    updates = update.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")
    found = db.update_alert_subscription(alert_id, updates)
    if not found:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"updated": True}


@app.delete("/api/alerts/{alert_id}")
async def delete_alert(alert_id: int):
    """Delete a job alert subscription."""
    found = db.delete_alert_subscription(alert_id)
    if not found:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"deleted": True}


# ============================================================================
# PHASE 1: PRODUCTION ESSENTIALS
# ============================================================================

# --- AI Career Roadmap ---

class RoadmapRequest(BaseModel):
    goal_role: str
    goal_company: str = ""


@app.post("/api/roadmap/generate")
async def generate_roadmap(request: RoadmapRequest, current_user: TokenData = Depends(get_current_user)):
    """Generate a personalized career roadmap."""
    from jobpilot.career_roadmap import CareerRoadmapGenerator

    generator = CareerRoadmapGenerator()
    roadmap = generator.generate_roadmap(
        goal_role=request.goal_role,
        goal_company=request.goal_company,
        user_id=current_user.user_id,
    )

    # Save to database
    roadmap_id = db.save_roadmap(
        user_id=current_user.user_id,
        goal_role=request.goal_role,
        goal_company=request.goal_company,
        current_skills=roadmap["current_skills"],
        missing_skills=roadmap["missing_skills"],
        roadmap_data=roadmap["roadmap_data"],
        estimated_weeks=roadmap["estimated_duration_weeks"],
    )

    roadmap["id"] = roadmap_id
    return roadmap


@app.get("/api/roadmap/history")
async def get_roadmap_history(current_user: TokenData = Depends(get_current_user)):
    """Get user's career roadmaps."""
    roadmaps = db.get_roadmaps(current_user.user_id)
    return {"roadmaps": roadmaps, "total": len(roadmaps)}


@app.put("/api/roadmap/{roadmap_id}/status")
async def update_roadmap_status(roadmap_id: int, status: str):
    """Update roadmap status (active, completed, paused)."""
    found = db.update_roadmap_status(roadmap_id, status)
    if not found:
        raise HTTPException(status_code=404, detail="Roadmap not found")
    return {"updated": True}


# --- AI Career Coach ---

class CoachRequest(BaseModel):
    question: str


@app.post("/api/coach/ask")
async def ask_coach(request: CoachRequest, current_user: TokenData = Depends(get_current_user)):
    """Ask the AI career coach a question."""
    from jobpilot.career_coach import CareerCoach

    coach = CareerCoach()
    answer = coach.ask(request.question, user_id=current_user.user_id)

    # Save conversation
    db.save_coach_conversation(
        user_id=current_user.user_id,
        question=request.question,
        answer=answer["answer"],
        context=answer.get("context", {}),
    )

    return answer


@app.get("/api/coach/history")
async def get_coach_history(limit: int = 20, current_user: TokenData = Depends(get_current_user)):
    """Get career coach conversation history."""
    conversations = db.get_coach_conversations(current_user.user_id, limit)
    return {"conversations": conversations, "total": len(conversations)}


# --- Resume Version Manager ---

class ResumeVersionRequest(BaseModel):
    name: str
    raw_text: str
    notes: str = ""
    original_resume_id: str = ""


@app.post("/api/resume/versions/create")
async def create_resume_version(request: ResumeVersionRequest, current_user: TokenData = Depends(get_current_user)):
    """Create a new resume version."""
    from jobpilot.resume_version_manager import ResumeVersionManager

    manager = ResumeVersionManager()
    result = manager.create_version(
        user_id=current_user.user_id,
        name=request.name,
        raw_text=request.raw_text,
        notes=request.notes,
        original_resume_id=request.original_resume_id,
    )
    return result


@app.get("/api/resume/versions")
async def get_resume_versions(current_user: TokenData = Depends(get_current_user)):
    """Get all resume versions."""
    from jobpilot.resume_version_manager import ResumeVersionManager

    manager = ResumeVersionManager()
    versions = manager.get_versions(current_user.user_id)
    return {"versions": versions, "total": len(versions)}


@app.get("/api/resume/versions/compare")
async def compare_resume_versions(version_id_1: int, version_id_2: int):
    """Compare two resume versions."""
    from jobpilot.resume_version_manager import ResumeVersionManager

    manager = ResumeVersionManager()
    comparison = manager.compare_versions(version_id_1, version_id_2)
    return comparison


@app.delete("/api/resume/versions/{version_id}")
async def delete_resume_version(version_id: int):
    """Delete a resume version."""
    from jobpilot.resume_version_manager import ResumeVersionManager

    manager = ResumeVersionManager()
    found = manager.delete_version(version_id)
    if not found:
        raise HTTPException(status_code=404, detail="Version not found")
    return {"deleted": True}


# --- Company Interview Experience ---

class InterviewExperienceRequest(BaseModel):
    company: str
    role: str
    difficulty: int
    rounds: list
    questions: list
    experience_text: str
    tips: str
    salary_range: str


@app.get("/api/interviews/company/{company}")
async def get_company_interview(company: str):
    """Get interview information for a company."""
    from jobpilot.company_interviews import CompanyInterviewManager

    manager = CompanyInterviewManager()
    info = manager.get_interview_info(company)
    return info


@app.post("/api/interviews/submit")
async def submit_interview_experience(request: InterviewExperienceRequest,
                                      current_user: TokenData = Depends(get_current_user)):
    """Submit a new interview experience."""
    from jobpilot.company_interviews import CompanyInterviewManager

    manager = CompanyInterviewManager()
    exp_id = manager.submit_experience(
        company=request.company,
        role=request.role,
        difficulty=request.difficulty,
        rounds=request.rounds,
        questions=request.questions,
        experience_text=request.experience_text,
        tips=request.tips,
        salary_range=request.salary_range,
        user_id=current_user.user_id,
    )
    return {"id": exp_id, "submitted": True}


@app.get("/api/interviews/companies")
async def list_companies_with_interviews():
    """Get list of companies with interview data."""
    from jobpilot.company_interviews import CompanyInterviewManager

    manager = CompanyInterviewManager()
    companies = manager.get_all_companies()
    return {"companies": companies, "total": len(companies)}


# --- AI Salary Estimator ---

class SalaryEstimateRequest(BaseModel):
    role: str
    company: str = ""
    location: str = ""
    experience_level: str = ""
    skills: list = []


@app.post("/api/salary/estimate")
async def estimate_salary(request: SalaryEstimateRequest):
    """Estimate salary for a given role and profile."""
    from jobpilot.salary_estimator import SalaryEstimator

    estimator = SalaryEstimator()
    estimate = estimator.estimate(
        role=request.role,
        company=request.company,
        location=request.location,
        experience_level=request.experience_level,
        skills=request.skills,
    )
    return estimate


@app.get("/api/salary/estimates")
async def get_salary_estimates(role: str = None, company: str = None):
    """Get salary estimates."""
    estimates = db.get_salary_estimates(role, company)
    return {"estimates": estimates, "total": len(estimates)}


@app.get("/api/alerts/frequencies")
async def get_frequency_options():
    """Get available alert frequency options."""
    from jobpilot.alert_service import get_alert_frequency_options
    return {"options": get_alert_frequency_options()}


@app.get("/api/alerts/experience-levels")
async def get_experience_levels():
    """Get available experience level options."""
    from jobpilot.alert_service import get_experience_level_options
    return {"options": get_experience_level_options()}


# ============================================================================
# FEATURE 10: Dashboard Analytics
# ============================================================================

@app.get("/api/dashboard/stats")
async def get_dashboard_analytics():
    """Get comprehensive dashboard analytics."""
    from jobpilot.dashboard_analytics import compute_analytics
    return compute_analytics()


@app.get("/api/dashboard/summary")
async def get_dashboard_summary():
    """Get quick dashboard summary."""
    from jobpilot.dashboard_analytics import get_dashboard_summary
    return get_dashboard_summary()


@app.get("/api/dashboard/timeline")
async def get_application_timeline():
    """Get application timeline data."""
    from jobpilot.dashboard_analytics import _compute_application_timeline
    return {"timeline": _compute_application_timeline()}


@app.get("/api/dashboard/skills")
async def get_skills_metrics():
    """Get skills coverage breakdown."""
    from jobpilot.dashboard_analytics import _compute_skills_metrics
    return _compute_skills_metrics()


# ============================================================================
# RESUME CATCH-ALL ROUTES (must be last to avoid catching specific paths)
# ============================================================================

@app.get("/api/resume/{resume_id}")
async def get_resume_analysis(resume_id: str):
    """Get analysis details for a specific resume."""
    resume = db.get_resume(resume_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    analyses = db.get_resume_analyses(resume_id)
    return {
        "resume": resume.to_dict(),
        "analyses": analyses,
    }


@app.delete("/api/resume/{resume_id}")
async def delete_resume_api(resume_id: str):
    """Delete a resume and its analyses."""
    found = db.delete_resume(resume_id)
    if not found:
        raise HTTPException(status_code=404, detail="Resume not found")
    return {"deleted": True}


# ============================================================================
# NEW JOB DETECTION & SMART ALERTS
# ============================================================================

@app.post("/api/scan/smart")
async def smart_scan(request: ScanRequest):
    """Run smart scan with duplicate detection and notifications."""
    from jobpilot.job_scanner import JobScanner

    scanner = JobScanner()
    if request.source == "all":
        result = await scanner.scan_all_sources(
            query=request.role, location=request.location, limit=request.limit
        )
    else:
        result = await scanner.scan_source(
            source=request.source, query=request.role,
            location=request.location, limit=request.limit
        )
    return result


@app.get("/api/notifications")
async def get_notifications(is_read: bool | None = None, limit: int = 50):
    """Get job notifications."""
    notifications = db.get_job_notifications(is_read=is_read, limit=limit)
    return {"notifications": notifications, "total": len(notifications)}


@app.get("/api/notifications/unread-count")
async def get_unread_count():
    """Get count of unread notifications."""
    count = db.get_unread_notification_count()
    return {"unread_count": count}


@app.post("/api/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: int):
    """Mark a notification as read."""
    found = db.mark_notification_read(notification_id)
    if not found:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"marked": True}


@app.post("/api/notifications/read-all")
async def mark_all_read():
    """Mark all notifications as read."""
    count = db.mark_all_notifications_read()
    return {"marked_count": count}


@app.get("/api/scan/history")
async def get_scan_history(limit: int = 20):
    """Get scan history."""
    history = db.get_scan_history(limit=limit)
    return {"history": history, "total": len(history)}


@app.get("/api/scan/stats")
async def get_scan_stats():
    """Get scan statistics."""
    return db.get_scan_stats()


@app.get("/api/dashboard/enhanced")
async def get_enhanced_dashboard():
    """Get enhanced dashboard with new job detection and trending analytics."""
    from jobpilot.dashboard_analytics import get_enhanced_dashboard
    return get_enhanced_dashboard()


@app.get("/api/trending/skills")
async def get_trending_skills(limit: int = 10):
    """Get trending skills from job listings."""
    return {"skills": db.get_most_frequent_skills(limit)}


@app.get("/api/trending/companies")
async def get_trending_companies(limit: int = 10):
    """Get top hiring companies."""
    return {"companies": db.get_top_hiring_companies(limit)}


@app.get("/api/trending/sources")
async def get_jobs_by_source():
    """Get job counts by source."""
    return {"sources": db.get_jobs_by_source()}


@app.get("/api/recommendations")
async def get_recommendations():
    """Get personalized job recommendations."""
    from jobpilot.recommendation_engine import RecommendationEngine

    engine = RecommendationEngine()
    return engine.get_recommendations()


@app.get("/api/recommendations/jobs")
async def get_recommended_jobs(limit: int = 10):
    """Get recommended jobs based on profile."""
    from jobpilot.recommendation_engine import RecommendationEngine

    engine = RecommendationEngine()
    return {"jobs": engine._recommend_jobs(engine._get_profile(), limit)}


@app.get("/api/recommendations/skills")
async def get_recommended_skills(limit: int = 10):
    """Get recommended skills to learn."""
    from jobpilot.recommendation_engine import RecommendationEngine

    engine = RecommendationEngine()
    return {"skills": engine._recommend_skills(engine._get_profile(), limit)}


@app.get("/api/recommendations/companies")
async def get_recommended_companies(limit: int = 10):
    """Get recommended companies."""
    from jobpilot.recommendation_engine import RecommendationEngine

    engine = RecommendationEngine()
    return {"companies": engine._recommend_companies(engine._get_profile(), limit)}


@app.get("/api/recommendations/certifications")
async def get_recommended_certifications(limit: int = 5):
    """Get recommended certifications."""
    from jobpilot.recommendation_engine import RecommendationEngine

    engine = RecommendationEngine()
    return {"certifications": engine._recommend_certifications(engine._get_profile(), limit)}
