"""SQLite database layer for JobPilot."""

import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from jobpilot.config import DB_PATH
from jobpilot.models import (
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
)


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Get a database connection, creating tables if needed."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    _create_tables(conn)
    return conn


def _create_tables(conn: sqlite3.Connection) -> None:
    """Create all tables if they don't exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            company TEXT,
            title TEXT,
            department TEXT,
            location TEXT,
            remote_status TEXT,
            employment_type TEXT,
            salary_min INTEGER DEFAULT 0,
            salary_max INTEGER DEFAULT 0,
            currency TEXT DEFAULT 'USD',
            required_skills TEXT DEFAULT '[]',
            preferred_skills TEXT DEFAULT '[]',
            experience_years INTEGER DEFAULT 0,
            education TEXT DEFAULT '',
            description TEXT DEFAULT '',
            url TEXT DEFAULT '',
            source TEXT DEFAULT '',
            posted_date TEXT DEFAULT '',
            application_url TEXT DEFAULT '',
            tech_stack TEXT DEFAULT '[]',
            visa_required BOOLEAN DEFAULT 0,
            discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(company, title, url)
        );

        CREATE TABLE IF NOT EXISTS match_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT REFERENCES jobs(id),
            overall_score REAL DEFAULT 0,
            skills_score REAL DEFAULT 0,
            experience_score REAL DEFAULT 0,
            relevance_score REAL DEFAULT 0,
            education_score REAL DEFAULT 0,
            role_score REAL DEFAULT 0,
            location_score REAL DEFAULT 0,
            strengths TEXT DEFAULT '[]',
            weaknesses TEXT DEFAULT '[]',
            missing_skills TEXT DEFAULT '[]',
            computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS applications (
            id TEXT PRIMARY KEY,
            job_id TEXT REFERENCES jobs(id),
            company TEXT,
            role TEXT,
            status TEXT DEFAULT 'discovered',
            match_score REAL DEFAULT 0,
            applied_date TEXT DEFAULT '',
            updated_date TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            resume_version TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS companies (
            name TEXT PRIMARY KEY,
            website TEXT DEFAULT '',
            industry TEXT DEFAULT '',
            size TEXT DEFAULT '',
            career_page TEXT DEFAULT '',
            job_count INTEGER DEFAULT 0,
            notes TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS resumes (
            id TEXT PRIMARY KEY,
            name TEXT DEFAULT '',
            filename TEXT DEFAULT '',
            raw_text TEXT DEFAULT '',
            target_role TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS resume_analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resume_id TEXT REFERENCES resumes(id),
            ats_score REAL DEFAULT 0,
            resume_quality_score REAL DEFAULT 0,
            technical_strength_score REAL DEFAULT 0,
            hiring_readiness_score REAL DEFAULT 0,
            skills TEXT DEFAULT '[]',
            strengths TEXT DEFAULT '[]',
            weaknesses TEXT DEFAULT '[]',
            missing_skills TEXT DEFAULT '[]',
            suggestions TEXT DEFAULT '[]',
            analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS verification_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            event_data TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS uploaded_resumes (
            id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            file_type TEXT NOT NULL,
            file_size INTEGER DEFAULT 0,
            raw_text TEXT DEFAULT '',
            extracted_data TEXT DEFAULT '{}',
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS cover_letters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resume_id TEXT DEFAULT '',
            job_id TEXT DEFAULT '',
            company_name TEXT DEFAULT '',
            role_title TEXT DEFAULT '',
            job_description TEXT DEFAULT '',
            letter_text TEXT DEFAULT '',
            tone TEXT DEFAULT 'professional',
            word_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS application_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id TEXT NOT NULL,
            note_type TEXT DEFAULT 'general',
            content TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS interview_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT DEFAULT '',
            resume_id TEXT DEFAULT '',
            role_title TEXT DEFAULT '',
            category TEXT DEFAULT '',
            difficulty TEXT DEFAULT '',
            question TEXT DEFAULT '',
            sample_answer TEXT DEFAULT '',
            tips TEXT DEFAULT '',
            generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS skill_gap_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resume_id TEXT DEFAULT '',
            job_id TEXT DEFAULT '',
            matched_skills TEXT DEFAULT '[]',
            missing_skills TEXT DEFAULT '[]',
            extra_skills TEXT DEFAULT '[]',
            match_percentage REAL DEFAULT 0,
            learning_areas TEXT DEFAULT '[]',
            priority_ranking TEXT DEFAULT '[]',
            analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS linkedin_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            headline TEXT DEFAULT '',
            about TEXT DEFAULT '',
            skills_raw TEXT DEFAULT '',
            experience_raw TEXT DEFAULT '',
            suggestions TEXT DEFAULT '[]',
            missing_keywords TEXT DEFAULT '[]',
            visibility_score REAL DEFAULT 0,
            strength_score REAL DEFAULT 0,
            analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS tailored_resumes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_resume_id TEXT DEFAULT '',
            job_id TEXT DEFAULT '',
            original_text TEXT DEFAULT '',
            tailored_text TEXT DEFAULT '',
            original_score REAL DEFAULT 0,
            tailored_score REAL DEFAULT 0,
            improvement_pct REAL DEFAULT 0,
            keywords_added TEXT DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS alert_subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT DEFAULT '',
            location TEXT DEFAULT '',
            remote_only BOOLEAN DEFAULT 0,
            experience_level TEXT DEFAULT '',
            frequency TEXT DEFAULT 'daily',
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_notified_at TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS dashboard_statistics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            period TEXT DEFAULT 'all',
            total_jobs INTEGER DEFAULT 0,
            total_applications INTEGER DEFAULT 0,
            total_interviews INTEGER DEFAULT 0,
            total_offers INTEGER DEFAULT 0,
            total_rejections INTEGER DEFAULT 0,
            avg_match_score REAL DEFAULT 0,
            avg_ats_score REAL DEFAULT 0,
            application_timeline TEXT DEFAULT '[]',
            skill_coverage TEXT DEFAULT '[]',
            match_trends TEXT DEFAULT '[]',
            computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS job_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL,
            notification_type TEXT DEFAULT 'new_match',
            message TEXT DEFAULT '',
            match_score REAL DEFAULT 0,
            is_read BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (job_id) REFERENCES jobs(id)
        );

        CREATE TABLE IF NOT EXISTS auto_apply_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            job_id TEXT NOT NULL,
            status TEXT DEFAULT 'queued',
            preferences TEXT DEFAULT '{}',
            resume_tailored BOOLEAN DEFAULT 0,
            cover_letter_generated BOOLEAN DEFAULT 0,
            application_ready BOOLEAN DEFAULT 0,
            tailored_resume_id INTEGER,
            cover_letter_id INTEGER,
            application_id TEXT,
            error_message TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS job_scan_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT DEFAULT '',
            query TEXT DEFAULT '',
            location TEXT DEFAULT '',
            scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            jobs_found INTEGER DEFAULT 0,
            new_jobs_found INTEGER DEFAULT 0,
            duration_seconds REAL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS career_roadmaps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            goal_role TEXT DEFAULT '',
            goal_company TEXT DEFAULT '',
            current_skills TEXT DEFAULT '[]',
            missing_skills TEXT DEFAULT '[]',
            roadmap_data TEXT DEFAULT '[]',
            estimated_duration_weeks INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS resume_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT DEFAULT '',
            version_number INTEGER DEFAULT 1,
            original_resume_id TEXT,
            file_path TEXT DEFAULT '',
            raw_text TEXT DEFAULT '',
            ats_score REAL DEFAULT 0,
            match_rate REAL DEFAULT 0,
            skills TEXT DEFAULT '[]',
            notes TEXT DEFAULT '',
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (original_resume_id) REFERENCES resumes(id)
        );

        CREATE TABLE IF NOT EXISTS company_interviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT NOT NULL,
            role TEXT DEFAULT '',
            difficulty INTEGER DEFAULT 0,
            rounds TEXT DEFAULT '[]',
            questions TEXT DEFAULT '[]',
            experience_text TEXT DEFAULT '',
            tips TEXT DEFAULT '',
            salary_range TEXT DEFAULT '',
            user_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS salary_estimates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT DEFAULT '',
            company TEXT DEFAULT '',
            location TEXT DEFAULT '',
            experience_level TEXT DEFAULT '',
            skills TEXT DEFAULT '[]',
            estimated_min INTEGER DEFAULT 0,
            estimated_max INTEGER DEFAULT 0,
            currency TEXT DEFAULT 'USD',
            confidence_score REAL DEFAULT 0,
            data_source TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS career_coach_conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            question TEXT DEFAULT '',
            answer TEXT DEFAULT '',
            context TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_roadmaps_user ON career_roadmaps(user_id);
        CREATE INDEX IF NOT EXISTS idx_resume_versions_user ON resume_versions(user_id);
        CREATE INDEX IF NOT EXISTS idx_company_interviews_company ON company_interviews(company);
        CREATE INDEX IF NOT EXISTS idx_salary_estimates_role ON salary_estimates(role);
    """)

    # User management tables
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT DEFAULT '',
            is_active BOOLEAN DEFAULT 1,
            is_admin BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS user_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            refresh_token TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            resource TEXT,
            details TEXT DEFAULT '{}',
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
        CREATE INDEX IF NOT EXISTS idx_sessions_user ON user_sessions(user_id);
        CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_logs(user_id);
        CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source);
        CREATE INDEX IF NOT EXISTS idx_notifications_read ON job_notifications(is_read);
    """)

    # Safe column additions for existing tables
    for stmt in [
        "ALTER TABLE resumes ADD COLUMN file_type TEXT DEFAULT 'txt'",
        "ALTER TABLE resumes ADD COLUMN file_size INTEGER DEFAULT 0",
        "ALTER TABLE applications ADD COLUMN interview_date TEXT DEFAULT ''",
        "ALTER TABLE applications ADD COLUMN offer_amount TEXT DEFAULT ''",
        "ALTER TABLE applications ADD COLUMN rejection_reason TEXT DEFAULT ''",
        "ALTER TABLE applications ADD COLUMN timeline TEXT DEFAULT '[]'",
        "ALTER TABLE jobs ADD COLUMN job_hash TEXT DEFAULT ''",
        "ALTER TABLE jobs ADD COLUMN is_active BOOLEAN DEFAULT 1",
    ]:
        try:
            conn.execute(stmt)
        except Exception:
            pass  # Column already exists

    # Create indexes after columns exist
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_active ON jobs(is_active)")
    except Exception:
        pass

    conn.commit()


# --- Jobs ---


def upsert_job(job: JobListing, db_path: Path = DB_PATH) -> bool:
    """Insert or update a job. Returns True if new, False if updated."""
    conn = get_connection(db_path)
    try:
        existing = conn.execute(
            "SELECT id FROM jobs WHERE id = ?", (job.id,)
        ).fetchone()
        conn.execute(
            """
            INSERT OR REPLACE INTO jobs
            (id, company, title, department, location, remote_status, employment_type,
             salary_min, salary_max, currency, required_skills, preferred_skills,
             experience_years, education, description, url, source, posted_date,
             application_url, tech_stack, visa_required, discovered_at, job_hash, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                job.id,
                job.company,
                job.title,
                job.department,
                job.location,
                job.remote_status,
                job.employment_type,
                job.salary_min,
                job.salary_max,
                job.currency,
                json.dumps(job.required_skills),
                json.dumps(job.preferred_skills),
                job.experience_years,
                job.education,
                job.description,
                job.url,
                job.source,
                job.posted_date,
                job.application_url,
                json.dumps(job.tech_stack),
                job.visa_required,
                job.discovered_at,
                job.job_hash,
                job.is_active,
            ),
        )
        conn.commit()
        return existing is None
    finally:
        conn.close()


def get_job(job_id: str, db_path: Path = DB_PATH) -> JobListing | None:
    """Get a single job by ID."""
    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return _row_to_job(row) if row else None
    finally:
        conn.close()


def get_all_jobs(db_path: Path = DB_PATH) -> list[JobListing]:
    """Get all jobs."""
    conn = get_connection(db_path)
    try:
        rows = conn.execute("SELECT * FROM jobs ORDER BY discovered_at DESC").fetchall()
        return [_row_to_job(r) for r in rows]
    finally:
        conn.close()


def search_jobs(
    query: str = "",
    source: str = "",
    min_score: float = 0.0,
    db_path: Path = DB_PATH,
) -> list[JobListing]:
    """Search jobs with optional filters."""
    conn = get_connection(db_path)
    try:
        sql = "SELECT j.* FROM jobs j LEFT JOIN match_results m ON j.id = m.job_id WHERE j.is_active = 1"
        params = []
        if query:
            sql += " AND (j.title LIKE ? OR j.company LIKE ? OR j.description LIKE ? OR j.required_skills LIKE ? OR j.tech_stack LIKE ?)"
            params.extend([f"%{query}%"] * 5)
        if source:
            sql += " AND j.source = ?"
            params.append(source)
        if min_score > 0:
            sql += " AND COALESCE(m.overall_score, 0) >= ?"
            params.append(min_score)
        sql += " ORDER BY j.discovered_at DESC"
        rows = conn.execute(sql, params).fetchall()
        return [_row_to_job(r) for r in rows]
    finally:
        conn.close()


def _row_to_job(row: sqlite3.Row) -> JobListing:
    """Convert a database row to a JobListing."""
    return JobListing(
        company=row["company"],
        title=row["title"],
        department=row["department"] or "",
        location=row["location"] or "",
        remote_status=row["remote_status"] or "",
        employment_type=row["employment_type"] or "",
        salary_min=row["salary_min"] or 0,
        salary_max=row["salary_max"] or 0,
        currency=row["currency"] or "USD",
        required_skills=json.loads(row["required_skills"] or "[]"),
        preferred_skills=json.loads(row["preferred_skills"] or "[]"),
        experience_years=row["experience_years"] or 0,
        education=row["education"] or "",
        description=row["description"] or "",
        url=row["url"] or "",
        source=row["source"] or "",
        posted_date=row["posted_date"] or "",
        application_url=row["application_url"] or "",
        tech_stack=json.loads(row["tech_stack"] or "[]"),
        visa_required=bool(row["visa_required"]),
        discovered_at=row["discovered_at"] or "",
        job_hash=row["job_hash"] or "",
        is_active=bool(row["is_active"]),
    )


# --- Match Results ---


def save_match_result(result: MatchResult, db_path: Path = DB_PATH) -> None:
    """Save a match result."""
    conn = get_connection(db_path)
    try:
        conn.execute(
            """
            INSERT INTO match_results
            (job_id, overall_score, skills_score, experience_score, relevance_score,
             education_score, role_score, location_score, strengths, weaknesses, missing_skills)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                result.job_id,
                result.overall_score,
                result.skills_score,
                result.experience_score,
                result.relevance_score,
                result.education_score,
                result.role_score,
                result.location_score,
                json.dumps(result.strengths),
                json.dumps(result.weaknesses),
                json.dumps(result.missing_skills),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_match_result(job_id: str, db_path: Path = DB_PATH) -> MatchResult | None:
    """Get the latest match result for a job."""
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM match_results WHERE job_id = ? ORDER BY computed_at DESC LIMIT 1",
            (job_id,),
        ).fetchone()
        if not row:
            return None
        return MatchResult(
            job_id=row["job_id"],
            overall_score=row["overall_score"],
            skills_score=row["skills_score"],
            experience_score=row["experience_score"],
            relevance_score=row["relevance_score"],
            education_score=row["education_score"],
            role_score=row["role_score"],
            location_score=row["location_score"],
            strengths=json.loads(row["strengths"] or "[]"),
            weaknesses=json.loads(row["weaknesses"] or "[]"),
            missing_skills=json.loads(row["missing_skills"] or "[]"),
        )
    finally:
        conn.close()


def get_top_matches(
    limit: int = 20, db_path: Path = DB_PATH
) -> list[tuple[JobListing, MatchResult]]:
    """Get top matching jobs with their match results."""
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            """
            SELECT j.company, j.title, j.department, j.location, j.remote_status,
                   j.employment_type, j.salary_min, j.salary_max, j.currency, j.required_skills,
                   j.preferred_skills, j.experience_years, j.education, j.description, j.url,
                   j.source, j.posted_date, j.application_url, j.tech_stack, j.visa_required,
                   j.discovered_at, j.job_hash, j.is_active,
                   m.job_id AS m_job_id, m.overall_score, m.skills_score, m.experience_score,
                   m.relevance_score, m.education_score, m.role_score, m.location_score,
                   m.strengths, m.weaknesses, m.missing_skills
            FROM jobs j
            JOIN match_results m ON j.id = m.job_id
            ORDER BY m.overall_score DESC
            LIMIT ?
        """,
            (limit,),
        ).fetchall()
        results = []
        for row in rows:
            job = _row_to_job(row)
            match = MatchResult(
                job_id=row["m_job_id"],
                overall_score=row["overall_score"],
                skills_score=row["skills_score"],
                experience_score=row["experience_score"],
                relevance_score=row["relevance_score"],
                education_score=row["education_score"],
                role_score=row["role_score"],
                location_score=row["location_score"],
                strengths=json.loads(row["strengths"] or "[]"),
                weaknesses=json.loads(row["weaknesses"] or "[]"),
                missing_skills=json.loads(row["missing_skills"] or "[]"),
            )
            results.append((job, match))
        return results
    finally:
        conn.close()


# --- Applications ---


def upsert_application(app: Application, db_path: Path = DB_PATH) -> None:
    """Insert or update an application."""
    conn = get_connection(db_path)
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO applications
            (id, job_id, company, role, status, match_score, applied_date, updated_date, notes, resume_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                app.id,
                app.job_id,
                app.company,
                app.role,
                app.status,
                app.match_score,
                app.applied_date,
                app.updated_date,
                app.notes,
                app.resume_version,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_applications(status: str = "", db_path: Path = DB_PATH) -> list[Application]:
    """Get all applications, optionally filtered by status."""
    conn = get_connection(db_path)
    try:
        if status:
            rows = conn.execute(
                "SELECT * FROM applications WHERE status = ? ORDER BY updated_date DESC",
                (status,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM applications ORDER BY updated_date DESC"
            ).fetchall()
        return [
            Application(
                job_id=r["job_id"],
                company=r["company"],
                role=r["role"],
                status=r["status"],
                match_score=r["match_score"],
                applied_date=r["applied_date"],
                updated_date=r["updated_date"],
                notes=r["notes"],
                resume_version=r["resume_version"],
            )
            for r in rows
        ]
    finally:
        conn.close()


def update_application_status(
    app_id: str, status: str, db_path: Path = DB_PATH
) -> bool:
    """Update an application's status. Returns True if found."""
    conn = get_connection(db_path)
    try:
        cur = conn.execute(
            "UPDATE applications SET status = ?, updated_date = datetime('now') WHERE id = ?",
            (status, app_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


# --- Companies ---


def upsert_company(company: Company, db_path: Path = DB_PATH) -> None:
    """Insert or update a company."""
    conn = get_connection(db_path)
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO companies
            (name, website, industry, size, career_page, job_count, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                company.name,
                company.website,
                company.industry,
                company.size,
                company.career_page,
                company.job_count,
                company.notes,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_companies(db_path: Path = DB_PATH) -> list[Company]:
    """Get all companies."""
    conn = get_connection(db_path)
    try:
        rows = conn.execute("SELECT * FROM companies ORDER BY name").fetchall()
        return [
            Company(
                name=r["name"],
                website=r["website"],
                industry=r["industry"],
                size=r["size"],
                career_page=r["career_page"],
                job_count=r["job_count"],
                notes=r["notes"],
            )
            for r in rows
        ]
    finally:
        conn.close()


def get_stats(db_path: Path = DB_PATH) -> dict:
    """Get dashboard statistics."""
    conn = get_connection(db_path)
    try:
        total_jobs = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        total_companies = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
        total_apps = conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
        avg_score = conn.execute(
            "SELECT COALESCE(AVG(overall_score), 0) FROM match_results"
        ).fetchone()[0]
        top_sources = conn.execute(
            "SELECT source, COUNT(*) as cnt FROM jobs GROUP BY source ORDER BY cnt DESC"
        ).fetchall()
        return {
            "total_jobs": total_jobs,
            "total_companies": total_companies,
            "total_applications": total_apps,
            "average_match_score": round(avg_score, 3),
            "top_sources": [
                {"source": r["source"], "count": r["cnt"]} for r in top_sources
            ],
        }
    finally:
        conn.close()


# --- Resumes ---


def upsert_resume(resume: Resume, db_path: Path = DB_PATH) -> bool:
    """Insert or update a resume. Returns True if new."""
    conn = get_connection(db_path)
    try:
        existing = conn.execute(
            "SELECT id FROM resumes WHERE id = ?", (resume.id,)
        ).fetchone()
        conn.execute(
            """
            INSERT OR REPLACE INTO resumes
            (id, name, filename, raw_text, target_role, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                resume.id,
                resume.name,
                resume.filename,
                resume.raw_text,
                resume.target_role,
                resume.created_at,
            ),
        )
        conn.commit()
        return existing is None
    finally:
        conn.close()


def get_resume(resume_id: str, db_path: Path = DB_PATH) -> Resume | None:
    """Get a resume by ID."""
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM resumes WHERE id = ?", (resume_id,)
        ).fetchone()
        if not row:
            return None
        return Resume(
            id=row["id"],
            name=row["name"],
            filename=row["filename"],
            raw_text=row["raw_text"],
            target_role=row["target_role"],
            created_at=row["created_at"],
        )
    finally:
        conn.close()


def get_all_resumes(db_path: Path = DB_PATH) -> list[Resume]:
    """Get all resumes (without raw_text for efficiency)."""
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT id, name, filename, target_role, created_at FROM resumes ORDER BY created_at DESC"
        ).fetchall()
        return [
            Resume(
                id=r["id"],
                name=r["name"],
                filename=r["filename"],
                target_role=r["target_role"],
                created_at=r["created_at"],
            )
            for r in rows
        ]
    finally:
        conn.close()


def delete_resume(resume_id: str, db_path: Path = DB_PATH) -> bool:
    """Delete a resume. Returns True if found."""
    conn = get_connection(db_path)
    try:
        cur = conn.execute("DELETE FROM resumes WHERE id = ?", (resume_id,))
        conn.execute("DELETE FROM resume_analyses WHERE resume_id = ?", (resume_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def save_resume_analysis(
    resume_id: str,
    ats_score: float,
    resume_quality_score: float,
    technical_strength_score: float,
    hiring_readiness_score: float,
    skills: list[str],
    strengths: list[str],
    weaknesses: list[str],
    missing_skills: list[str],
    suggestions: list[str],
    db_path: Path = DB_PATH,
) -> None:
    """Save a resume analysis result."""
    conn = get_connection(db_path)
    try:
        conn.execute(
            """
            INSERT INTO resume_analyses
            (resume_id, ats_score, resume_quality_score, technical_strength_score,
             hiring_readiness_score, skills, strengths, weaknesses, missing_skills, suggestions)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                resume_id,
                ats_score,
                resume_quality_score,
                technical_strength_score,
                hiring_readiness_score,
                json.dumps(skills),
                json.dumps(strengths),
                json.dumps(weaknesses),
                json.dumps(missing_skills),
                json.dumps(suggestions),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_resume_analyses(resume_id: str, db_path: Path = DB_PATH) -> list[dict]:
    """Get all analyses for a resume."""
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM resume_analyses WHERE resume_id = ? ORDER BY analyzed_at DESC",
            (resume_id,),
        ).fetchall()
        return [
            {
                "id": r["id"],
                "resume_id": r["resume_id"],
                "ats_score": r["ats_score"],
                "resume_quality_score": r["resume_quality_score"],
                "technical_strength_score": r["technical_strength_score"],
                "hiring_readiness_score": r["hiring_readiness_score"],
                "skills": json.loads(r["skills"] or "[]"),
                "strengths": json.loads(r["strengths"] or "[]"),
                "weaknesses": json.loads(r["weaknesses"] or "[]"),
                "missing_skills": json.loads(r["missing_skills"] or "[]"),
                "suggestions": json.loads(r["suggestions"] or "[]"),
                "analyzed_at": r["analyzed_at"],
            }
            for r in rows
        ]
    finally:
        conn.close()


# --- Verification Events ---


def log_verification_event(
    entity_type: str,
    entity_id: str,
    event_type: str,
    event_data: dict | None = None,
    db_path: Path = DB_PATH,
) -> None:
    """Log a verification event."""
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO verification_events (entity_type, entity_id, event_type, event_data) VALUES (?, ?, ?, ?)",
            (entity_type, entity_id, event_type, json.dumps(event_data or {})),
        )
        conn.commit()
    finally:
        conn.close()


def get_verification_events(
    entity_type: str | None = None,
    entity_id: str | None = None,
    db_path: Path = DB_PATH,
) -> list[dict]:
    """Get verification events, optionally filtered by entity."""
    conn = get_connection(db_path)
    try:
        sql = "SELECT * FROM verification_events WHERE 1=1"
        params: list = []
        if entity_type:
            sql += " AND entity_type = ?"
            params.append(entity_type)
        if entity_id:
            sql += " AND entity_id = ?"
            params.append(entity_id)
        sql += " ORDER BY id DESC"
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_latest_verification_status(
    entity_type: str,
    entity_id: str,
    db_path: Path = DB_PATH,
) -> dict:
    """Get the latest verification status for an entity.

    An entity is considered verified if the most recent 'profile_verification_accepted'
    event is newer than the most recent 'profile_verification_declined' event.
    """
    conn = get_connection(db_path)
    try:
        # Get the latest overall event
        latest = conn.execute(
            """SELECT * FROM verification_events
               WHERE entity_type = ? AND entity_id = ?
               ORDER BY id DESC LIMIT 1""",
            (entity_type, entity_id),
        ).fetchone()
        if not latest:
            return {"is_verified": False, "verified_at": None, "last_event": None}

        # Get the latest acceptance event
        accept = conn.execute(
            """SELECT * FROM verification_events
               WHERE entity_type = ? AND entity_id = ?
               AND event_type = 'profile_verification_accepted'
               ORDER BY id DESC LIMIT 1""",
            (entity_type, entity_id),
        ).fetchone()

        # Get the latest decline event
        decline = conn.execute(
            """SELECT * FROM verification_events
               WHERE entity_type = ? AND entity_id = ?
               AND event_type = 'profile_verification_declined'
               ORDER BY id DESC LIMIT 1""",
            (entity_type, entity_id),
        ).fetchone()

        # Entity is verified if there's an acceptance and it's newer than any decline
        is_verified = False
        verified_at = None
        if accept:
            if not decline or accept["id"] > decline["id"]:
                is_verified = True
                verified_at = accept["created_at"]

        return {
            "is_verified": is_verified,
            "verified_at": verified_at,
            "last_event": latest["event_type"],
            "last_event_at": latest["created_at"],
        }
    finally:
        conn.close()


# --- Uploaded Resumes ---


def save_uploaded_resume(
    resume_id: str,
    filename: str,
    file_type: str,
    file_size: int,
    raw_text: str,
    extracted_data: dict,
    db_path: Path = DB_PATH,
) -> None:
    """Save an uploaded resume."""
    conn = get_connection(db_path)
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO uploaded_resumes
            (id, filename, file_type, file_size, raw_text, extracted_data)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                resume_id,
                filename,
                file_type,
                file_size,
                raw_text,
                json.dumps(extracted_data),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_uploaded_resume(resume_id: str, db_path: Path = DB_PATH) -> dict | None:
    """Get an uploaded resume."""
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM uploaded_resumes WHERE id = ?", (resume_id,)
        ).fetchone()
        if not row:
            return None
        return dict(row)
    finally:
        conn.close()


def get_all_uploaded_resumes(db_path: Path = DB_PATH) -> list[dict]:
    """Get all uploaded resumes."""
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM uploaded_resumes ORDER BY upload_date DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def delete_uploaded_resume(resume_id: str, db_path: Path = DB_PATH) -> bool:
    """Delete an uploaded resume."""
    conn = get_connection(db_path)
    try:
        cur = conn.execute("DELETE FROM uploaded_resumes WHERE id = ?", (resume_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


# --- Cover Letters ---


def save_cover_letter(letter: CoverLetter, db_path: Path = DB_PATH) -> int:
    """Save a cover letter. Returns the inserted ID."""
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            """
            INSERT INTO cover_letters
            (resume_id, job_id, company_name, role_title, job_description, letter_text, tone, word_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                letter.resume_id,
                letter.job_id,
                letter.company_name,
                letter.role_title,
                letter.job_description,
                letter.letter_text,
                letter.tone,
                letter.word_count,
            ),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_cover_letters(db_path: Path = DB_PATH) -> list[dict]:
    """Get all cover letters."""
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM cover_letters ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_cover_letter(letter_id: int, db_path: Path = DB_PATH) -> dict | None:
    """Get a specific cover letter."""
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM cover_letters WHERE id = ?", (letter_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def delete_cover_letter(letter_id: int, db_path: Path = DB_PATH) -> bool:
    """Delete a cover letter."""
    conn = get_connection(db_path)
    try:
        cur = conn.execute("DELETE FROM cover_letters WHERE id = ?", (letter_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


# --- Application Notes ---


def add_application_note(
    app_id: str, note_type: str, content: str, db_path: Path = DB_PATH
) -> int:
    """Add a note to an application."""
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            "INSERT INTO application_notes (application_id, note_type, content) VALUES (?, ?, ?)",
            (app_id, note_type, content),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_application_notes(app_id: str, db_path: Path = DB_PATH) -> list[dict]:
    """Get all notes for an application."""
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM application_notes WHERE application_id = ? ORDER BY created_at DESC",
            (app_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def delete_application(app_id: str, db_path: Path = DB_PATH) -> bool:
    """Delete an application and its notes."""
    conn = get_connection(db_path)
    try:
        conn.execute(
            "DELETE FROM application_notes WHERE application_id = ?", (app_id,)
        )
        cur = conn.execute("DELETE FROM applications WHERE id = ?", (app_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def get_application(app_id: str, db_path: Path = DB_PATH) -> Application | None:
    """Get a specific application."""
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM applications WHERE id = ?", (app_id,)
        ).fetchone()
        if not row:
            return None
        return Application(
            job_id=row["job_id"],
            company=row["company"],
            role=row["role"],
            status=row["status"],
            match_score=row["match_score"],
            applied_date=row["applied_date"],
            updated_date=row["updated_date"],
            notes=row["notes"],
            resume_version=row["resume_version"],
        )
    finally:
        conn.close()


def update_application(app_id: str, updates: dict, db_path: Path = DB_PATH) -> bool:
    """Update an application with arbitrary fields."""
    conn = get_connection(db_path)
    try:
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [app_id]
        cur = conn.execute(f"UPDATE applications SET {set_clause} WHERE id = ?", values)
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def get_application_stats(db_path: Path = DB_PATH) -> dict:
    """Get application status counts."""
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM applications GROUP BY status"
        ).fetchall()
        stats = {r["status"]: r["cnt"] for r in rows}
        stats["total"] = sum(stats.values())
        return stats
    finally:
        conn.close()


# --- Interview Questions ---


def save_interview_questions(
    questions: list[InterviewQuestion], db_path: Path = DB_PATH
) -> None:
    """Save interview questions."""
    conn = get_connection(db_path)
    try:
        for q in questions:
            conn.execute(
                """
                INSERT INTO interview_questions
                (job_id, resume_id, role_title, category, difficulty, question, sample_answer, tips)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    q.job_id,
                    q.resume_id,
                    q.role_title,
                    q.category,
                    q.difficulty,
                    q.question,
                    q.sample_answer,
                    q.tips,
                ),
            )
        conn.commit()
    finally:
        conn.close()


def get_interview_questions(
    job_id: str = "", resume_id: str = "", db_path: Path = DB_PATH
) -> list[dict]:
    """Get interview questions, optionally filtered."""
    conn = get_connection(db_path)
    try:
        sql = "SELECT * FROM interview_questions WHERE 1=1"
        params: list = []
        if job_id:
            sql += " AND job_id = ?"
            params.append(job_id)
        if resume_id:
            sql += " AND resume_id = ?"
            params.append(resume_id)
        sql += " ORDER BY generated_at DESC"
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def delete_interview_questions(question_id: int, db_path: Path = DB_PATH) -> bool:
    """Delete interview questions by ID."""
    conn = get_connection(db_path)
    try:
        cur = conn.execute(
            "DELETE FROM interview_questions WHERE id = ?", (question_id,)
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


# --- Skill Gap Reports ---


def save_skill_gap_report(report: SkillGapReport, db_path: Path = DB_PATH) -> int:
    """Save a skill gap report. Returns the inserted ID."""
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            """
            INSERT INTO skill_gap_reports
            (resume_id, job_id, matched_skills, missing_skills, extra_skills,
             match_percentage, learning_areas, priority_ranking)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                report.resume_id,
                report.job_id,
                json.dumps(report.matched_skills),
                json.dumps(report.missing_skills),
                json.dumps(report.extra_skills),
                report.match_percentage,
                json.dumps(report.learning_areas),
                json.dumps(report.priority_ranking),
            ),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_skill_gap_reports(db_path: Path = DB_PATH) -> list[dict]:
    """Get all skill gap reports."""
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM skill_gap_reports ORDER BY analyzed_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_skill_gap_report(report_id: int, db_path: Path = DB_PATH) -> dict | None:
    """Get a specific skill gap report."""
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM skill_gap_reports WHERE id = ?", (report_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# --- LinkedIn Reports ---


def save_linkedin_report(report: LinkedInReport, db_path: Path = DB_PATH) -> int:
    """Save a LinkedIn report. Returns the inserted ID."""
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            """
            INSERT INTO linkedin_reports
            (headline, about, skills_raw, experience_raw, suggestions, missing_keywords,
             visibility_score, strength_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                report.headline,
                report.about,
                report.skills_raw,
                report.experience_raw,
                json.dumps(report.suggestions),
                json.dumps(report.missing_keywords),
                report.visibility_score,
                report.strength_score,
            ),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_linkedin_reports(db_path: Path = DB_PATH) -> list[dict]:
    """Get all LinkedIn reports."""
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM linkedin_reports ORDER BY analyzed_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_linkedin_report(report_id: int, db_path: Path = DB_PATH) -> dict | None:
    """Get a specific LinkedIn report."""
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM linkedin_reports WHERE id = ?", (report_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# --- Tailored Resumes ---


def save_tailored_resume(resume: TailoredResume, db_path: Path = DB_PATH) -> int:
    """Save a tailored resume. Returns the inserted ID."""
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            """
            INSERT INTO tailored_resumes
            (original_resume_id, job_id, original_text, tailored_text,
             original_score, tailored_score, improvement_pct, keywords_added)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                resume.original_resume_id,
                resume.job_id,
                resume.original_text,
                resume.tailored_text,
                resume.original_score,
                resume.tailored_score,
                resume.improvement_pct,
                json.dumps(resume.keywords_added),
            ),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_tailored_resumes(db_path: Path = DB_PATH) -> list[dict]:
    """Get all tailored resumes."""
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM tailored_resumes ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_tailored_resume(resume_id: int, db_path: Path = DB_PATH) -> dict | None:
    """Get a specific tailored resume."""
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM tailored_resumes WHERE id = ?", (resume_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def delete_tailored_resume(resume_id: int, db_path: Path = DB_PATH) -> bool:
    """Delete a tailored resume."""
    conn = get_connection(db_path)
    try:
        cur = conn.execute("DELETE FROM tailored_resumes WHERE id = ?", (resume_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


# --- Alert Subscriptions ---


def save_alert_subscription(alert: AlertSubscription, db_path: Path = DB_PATH) -> int:
    """Save an alert subscription. Returns the inserted ID."""
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            """
            INSERT INTO alert_subscriptions
            (role, location, remote_only, experience_level, frequency, is_active)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                alert.role,
                alert.location,
                alert.remote_only,
                alert.experience_level,
                alert.frequency,
                alert.is_active,
            ),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_alert_subscriptions(db_path: Path = DB_PATH) -> list[dict]:
    """Get all alert subscriptions."""
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM alert_subscriptions ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_active_alerts(db_path: Path = DB_PATH) -> list[dict]:
    """Get active alert subscriptions."""
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM alert_subscriptions WHERE is_active = 1"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def update_alert_subscription(
    alert_id: int, updates: dict, db_path: Path = DB_PATH
) -> bool:
    """Update an alert subscription."""
    conn = get_connection(db_path)
    try:
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [alert_id]
        cur = conn.execute(
            f"UPDATE alert_subscriptions SET {set_clause} WHERE id = ?", values
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def delete_alert_subscription(alert_id: int, db_path: Path = DB_PATH) -> bool:
    """Delete an alert subscription."""
    conn = get_connection(db_path)
    try:
        cur = conn.execute("DELETE FROM alert_subscriptions WHERE id = ?", (alert_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


# --- Dashboard Statistics ---


def save_dashboard_stats(stats: DashboardStats, db_path: Path = DB_PATH) -> None:
    """Save dashboard statistics."""
    conn = get_connection(db_path)
    try:
        conn.execute(
            """
            INSERT INTO dashboard_statistics
            (period, total_jobs, total_applications, total_interviews, total_offers,
             total_rejections, avg_match_score, avg_ats_score, application_timeline,
             skill_coverage, match_trends)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                stats.period,
                stats.total_jobs,
                stats.total_applications,
                stats.total_interviews,
                stats.total_offers,
                stats.total_rejections,
                stats.avg_match_score,
                stats.avg_ats_score,
                json.dumps(stats.application_timeline),
                json.dumps(stats.skill_coverage),
                json.dumps(stats.match_trends),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_latest_dashboard_stats(db_path: Path = DB_PATH) -> dict | None:
    """Get the latest dashboard statistics."""
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM dashboard_statistics ORDER BY computed_at DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# --- Job Notifications ---


def create_job_notification(
    job_id: str,
    notification_type: str,
    message: str,
    match_score: float = 0,
    db_path: Path = DB_PATH,
) -> int:
    """Create a job notification. Returns the notification ID."""
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            """
            INSERT INTO job_notifications (job_id, notification_type, message, match_score)
            VALUES (?, ?, ?, ?)
        """,
            (job_id, notification_type, message, match_score),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_job_notifications(
    is_read: bool | None = None, limit: int = 50, db_path: Path = DB_PATH
) -> list[dict]:
    """Get job notifications, optionally filtered by read status."""
    conn = get_connection(db_path)
    try:
        sql = """
            SELECT n.*, j.company, j.title, j.location, j.url, j.source
            FROM job_notifications n
            LEFT JOIN jobs j ON n.job_id = j.id
        """
        params: list = []
        if is_read is not None:
            sql += " WHERE n.is_read = ?"
            params.append(1 if is_read else 0)
        sql += " ORDER BY n.created_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def mark_notification_read(notification_id: int, db_path: Path = DB_PATH) -> bool:
    """Mark a notification as read."""
    conn = get_connection(db_path)
    try:
        cur = conn.execute(
            "UPDATE job_notifications SET is_read = 1 WHERE id = ?",
            (notification_id,),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def mark_all_notifications_read(db_path: Path = DB_PATH) -> int:
    """Mark all notifications as read. Returns count of updated rows."""
    conn = get_connection(db_path)
    try:
        cur = conn.execute("UPDATE job_notifications SET is_read = 1 WHERE is_read = 0")
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def get_unread_notification_count(db_path: Path = DB_PATH) -> int:
    """Get count of unread notifications."""
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM job_notifications WHERE is_read = 0"
        ).fetchone()
        return row[0]
    finally:
        conn.close()


def has_been_notified(job_id: str, db_path: Path = DB_PATH) -> bool:
    """Check if a job has already generated a notification."""
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM job_notifications WHERE job_id = ?",
            (job_id,),
        ).fetchone()
        return row[0] > 0
    finally:
        conn.close()


# --- Job Scan History ---


def save_scan_history(
    source: str,
    query: str,
    location: str,
    jobs_found: int,
    new_jobs_found: int,
    duration_seconds: float = 0,
    db_path: Path = DB_PATH,
) -> int:
    """Save a scan history record. Returns the ID."""
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            """
            INSERT INTO job_scan_history
            (source, query, location, jobs_found, new_jobs_found, duration_seconds)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (source, query, location, jobs_found, new_jobs_found, duration_seconds),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_scan_history(limit: int = 20, db_path: Path = DB_PATH) -> list[dict]:
    """Get recent scan history."""
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM job_scan_history ORDER BY scanned_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_scan_stats(db_path: Path = DB_PATH) -> dict:
    """Get aggregate scan statistics."""
    conn = get_connection(db_path)
    try:
        total_scans = conn.execute("SELECT COUNT(*) FROM job_scan_history").fetchone()[
            0
        ]
        total_jobs_found = conn.execute(
            "SELECT COALESCE(SUM(jobs_found), 0) FROM job_scan_history"
        ).fetchone()[0]
        total_new_jobs = conn.execute(
            "SELECT COALESCE(SUM(new_jobs_found), 0) FROM job_scan_history"
        ).fetchone()[0]
        avg_duration = conn.execute(
            "SELECT COALESCE(AVG(duration_seconds), 0) FROM job_scan_history"
        ).fetchone()[0]
        scans_today = conn.execute(
            "SELECT COUNT(*) FROM job_scan_history WHERE DATE(scanned_at) = DATE('now')"
        ).fetchone()[0]
        return {
            "total_scans": total_scans,
            "total_jobs_found": total_jobs_found,
            "total_new_jobs": total_new_jobs,
            "avg_duration_seconds": round(avg_duration, 2),
            "scans_today": scans_today,
        }
    finally:
        conn.close()


# --- New Job Detection ---


def compute_job_hash(company: str, title: str, url: str) -> str:
    """Compute a hash for duplicate detection."""
    raw = f"{company.lower().strip()}|{title.lower().strip()}|{url.strip()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def check_job_exists(job_id: str, db_path: Path = DB_PATH) -> bool:
    """Check if a job already exists in the database."""
    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT id FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return row is not None
    finally:
        conn.close()


def get_new_jobs(jobs: list[JobListing], db_path: Path = DB_PATH) -> list[JobListing]:
    """Filter a list of jobs to only those that are new (not in DB)."""
    if not jobs:
        return []
    conn = get_connection(db_path)
    try:
        existing_ids = set()
        for job in jobs:
            row = conn.execute("SELECT id FROM jobs WHERE id = ?", (job.id,)).fetchone()
            if row:
                existing_ids.add(job.id)
        return [job for job in jobs if job.id not in existing_ids]
    finally:
        conn.close()


def update_job_active_status(
    job_id: str, is_active: bool, db_path: Path = DB_PATH
) -> bool:
    """Update a job's active status."""
    conn = get_connection(db_path)
    try:
        cur = conn.execute(
            "UPDATE jobs SET is_active = ? WHERE id = ?",
            (1 if is_active else 0, job_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def get_jobs_discovered_today(db_path: Path = DB_PATH) -> list[dict]:
    """Get jobs discovered today."""
    conn = get_connection(db_path)
    try:
        rows = conn.execute("""
            SELECT id, company, title, location, source, discovered_at
            FROM jobs
            WHERE DATE(discovered_at) = DATE('now')
            ORDER BY discovered_at DESC
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_jobs_discovered_this_week(db_path: Path = DB_PATH) -> list[dict]:
    """Get jobs discovered this week."""
    conn = get_connection(db_path)
    try:
        rows = conn.execute("""
            SELECT id, company, title, location, source, discovered_at
            FROM jobs
            WHERE discovered_at >= DATE('now', '-7 days')
            ORDER BY discovered_at DESC
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_top_hiring_companies(limit: int = 10, db_path: Path = DB_PATH) -> list[dict]:
    """Get companies with most job listings."""
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            """
            SELECT company, COUNT(*) as job_count
            FROM jobs
            WHERE is_active = 1
            GROUP BY company
            ORDER BY job_count DESC
            LIMIT ?
        """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_most_frequent_skills(limit: int = 10, db_path: Path = DB_PATH) -> list[dict]:
    """Get most frequently appearing skills across jobs."""
    conn = get_connection(db_path)
    try:
        rows = conn.execute("""
            SELECT required_skills FROM jobs WHERE is_active = 1
        """).fetchall()
        skill_counts: dict[str, int] = {}
        for row in rows:
            skills = json.loads(row["required_skills"] or "[]")
            for skill in skills:
                skill_lower = skill.lower().strip()
                skill_counts[skill_lower] = skill_counts.get(skill_lower, 0) + 1
        sorted_skills = sorted(skill_counts.items(), key=lambda x: x[1], reverse=True)
        return [{"skill": s, "count": c} for s, c in sorted_skills[:limit]]
    finally:
        conn.close()


def get_jobs_by_source(db_path: Path = DB_PATH) -> list[dict]:
    """Get job counts grouped by source."""
    conn = get_connection(db_path)
    try:
        rows = conn.execute("""
            SELECT source, COUNT(*) as job_count
            FROM jobs
            WHERE is_active = 1
            GROUP BY source
            ORDER BY job_count DESC
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_recent_high_match_jobs(limit: int = 10, db_path: Path = DB_PATH) -> list[dict]:
    """Get recent jobs with high match scores."""
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            """
            SELECT j.id, j.company, j.title, j.location, j.url, j.source,
                   j.posted_date, j.discovered_at,
                   m.overall_score, m.skills_score, m.strengths, m.missing_skills
            FROM jobs j
            JOIN match_results m ON j.id = m.job_id
            WHERE j.is_active = 1
            ORDER BY m.overall_score DESC, j.discovered_at DESC
            LIMIT ?
        """,
            (limit,),
        ).fetchall()
        results = []
        for r in rows:
            results.append(
                {
                    "id": r["id"],
                    "company": r["company"],
                    "title": r["title"],
                    "location": r["location"],
                    "url": r["url"],
                    "source": r["source"],
                    "posted_date": r["posted_date"],
                    "discovered_at": r["discovered_at"],
                    "match_score": r["overall_score"],
                    "skills_score": r["skills_score"],
                    "strengths": json.loads(r["strengths"] or "[]"),
                    "missing_skills": json.loads(r["missing_skills"] or "[]"),
                }
            )
        return results
    finally:
        conn.close()


# --- User Management ---


def create_user(
    email: str, password_hash: str, name: str = "", db_path: Path = DB_PATH
) -> int:
    """Create a new user. Returns the user ID."""
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            "INSERT INTO users (email, password_hash, name) VALUES (?, ?, ?)",
            (email, password_hash, name),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_user_by_email(email: str, db_path: Path = DB_PATH) -> Optional[dict]:
    """Get a user by email."""
    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_user_by_id(user_id: int, db_path: Path = DB_PATH) -> Optional[dict]:
    """Get a user by ID."""
    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if row:
            user = dict(row)
            user.pop("password_hash", None)
            return user
        return None
    finally:
        conn.close()


def update_user(user_id: int, updates: dict, db_path: Path = DB_PATH) -> bool:
    """Update user fields."""
    conn = get_connection(db_path)
    try:
        updates["updated_at"] = datetime.now().isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [user_id]
        cur = conn.execute(f"UPDATE users SET {set_clause} WHERE id = ?", values)
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def log_audit(
    user_id: int,
    action: str,
    resource: str = None,
    details: dict = None,
    ip_address: str = None,
    db_path: Path = DB_PATH,
):
    """Log an audit event."""
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO audit_logs (user_id, action, resource, details, ip_address) VALUES (?, ?, ?, ?, ?)",
            (user_id, action, resource, json.dumps(details or {}), ip_address),
        )
        conn.commit()
    finally:
        conn.close()


def get_audit_logs(
    user_id: int = None, limit: int = 100, db_path: Path = DB_PATH
) -> list[dict]:
    """Get audit logs, optionally filtered by user."""
    conn = get_connection(db_path)
    try:
        if user_id:
            rows = conn.execute(
                "SELECT * FROM audit_logs WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_user_stats(db_path: Path = DB_PATH) -> dict:
    """Get user statistics for admin dashboard."""
    conn = get_connection(db_path)
    try:
        total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        active_users = conn.execute(
            "SELECT COUNT(*) FROM users WHERE is_active = 1"
        ).fetchone()[0]
        recent_users = conn.execute(
            "SELECT COUNT(*) FROM users WHERE created_at >= DATE('now', '-30 days')"
        ).fetchone()[0]
        return {
            "total_users": total_users,
            "active_users": active_users,
            "recent_users": recent_users,
        }
    finally:
        conn.close()


# --- Career Roadmaps ---


def save_roadmap(
    user_id: int,
    goal_role: str,
    goal_company: str,
    current_skills: list,
    missing_skills: list,
    roadmap_data: list,
    estimated_weeks: int,
    db_path: Path = DB_PATH,
) -> int:
    """Save a career roadmap."""
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            """
            INSERT INTO career_roadmaps
            (user_id, goal_role, goal_company, current_skills, missing_skills, roadmap_data, estimated_duration_weeks)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                user_id,
                goal_role,
                goal_company,
                json.dumps(current_skills),
                json.dumps(missing_skills),
                json.dumps(roadmap_data),
                estimated_weeks,
            ),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_roadmaps(user_id: int, db_path: Path = DB_PATH) -> list[dict]:
    """Get all roadmaps for a user."""
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM career_roadmaps WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def update_roadmap_status(
    roadmap_id: int, status: str, db_path: Path = DB_PATH
) -> bool:
    """Update roadmap status."""
    conn = get_connection(db_path)
    try:
        cur = conn.execute(
            "UPDATE career_roadmaps SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, roadmap_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


# --- Resume Versions ---


def save_resume_version(
    user_id: int,
    name: str,
    version_number: int,
    original_resume_id: str,
    raw_text: str,
    ats_score: float,
    match_rate: float,
    skills: list,
    notes: str = "",
    db_path: Path = DB_PATH,
) -> int:
    """Save a resume version."""
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            """
            INSERT INTO resume_versions
            (user_id, name, version_number, original_resume_id, raw_text,
             ats_score, match_rate, skills, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                user_id,
                name,
                version_number,
                original_resume_id,
                raw_text,
                ats_score,
                match_rate,
                json.dumps(skills),
                notes,
            ),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_resume_versions(user_id: int, db_path: Path = DB_PATH) -> list[dict]:
    """Get all resume versions for a user."""
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM resume_versions WHERE user_id = ? ORDER BY version_number DESC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def delete_resume_version(version_id: int, db_path: Path = DB_PATH) -> bool:
    """Delete a resume version."""
    conn = get_connection(db_path)
    try:
        cur = conn.execute("DELETE FROM resume_versions WHERE id = ?", (version_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


# --- Company Interviews ---


def save_company_interview(
    company: str,
    role: str,
    difficulty: int,
    rounds: list,
    questions: list,
    experience_text: str,
    tips: str,
    salary_range: str,
    user_id: int,
    db_path: Path = DB_PATH,
) -> int:
    """Save a company interview experience."""
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            """
            INSERT INTO company_interviews
            (company, role, difficulty, rounds, questions, experience_text, tips, salary_range, user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                company,
                role,
                difficulty,
                json.dumps(rounds),
                json.dumps(questions),
                experience_text,
                tips,
                salary_range,
                user_id,
            ),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_company_interviews(company: str = None, db_path: Path = DB_PATH) -> list[dict]:
    """Get company interview experiences."""
    conn = get_connection(db_path)
    try:
        if company:
            rows = conn.execute(
                "SELECT * FROM company_interviews WHERE company = ? ORDER BY created_at DESC",
                (company,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM company_interviews ORDER BY created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# --- Salary Estimates ---


def save_salary_estimate(
    role: str,
    company: str,
    location: str,
    experience_level: str,
    skills: list,
    estimated_min: int,
    estimated_max: int,
    currency: str,
    confidence: float,
    data_source: str,
    db_path: Path = DB_PATH,
) -> int:
    """Save a salary estimate."""
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            """
            INSERT INTO salary_estimates
            (role, company, location, experience_level, skills,
             estimated_min, estimated_max, currency, confidence_score, data_source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                role,
                company,
                location,
                experience_level,
                json.dumps(skills),
                estimated_min,
                estimated_max,
                currency,
                confidence,
                data_source,
            ),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_salary_estimates(
    role: str = None, company: str = None, db_path: Path = DB_PATH
) -> list[dict]:
    """Get salary estimates."""
    conn = get_connection(db_path)
    try:
        sql = "SELECT * FROM salary_estimates WHERE 1=1"
        params = []
        if role:
            sql += " AND role LIKE ?"
            params.append(f"%{role}%")
        if company:
            sql += " AND company LIKE ?"
            params.append(f"%{company}%")
        sql += " ORDER BY created_at DESC"
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# --- Career Coach ---


def save_coach_conversation(
    user_id: int,
    question: str,
    answer: str,
    context: dict = None,
    db_path: Path = DB_PATH,
) -> int:
    """Save a career coach conversation."""
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            """
            INSERT INTO career_coach_conversations (user_id, question, answer, context)
            VALUES (?, ?, ?, ?)
        """,
            (user_id, question, answer, json.dumps(context or {})),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_coach_conversations(
    user_id: int, limit: int = 50, db_path: Path = DB_PATH
) -> list[dict]:
    """Get career coach conversations."""
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM career_coach_conversations WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# --- Auto Apply Queue ---

def save_auto_apply_item(item: dict, db_path: Path = DB_PATH) -> int:
    """Save an auto-apply queue item. Returns the ID."""
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            """INSERT INTO auto_apply_queue
               (user_id, job_id, status, preferences, resume_tailored,
                cover_letter_generated, application_ready, tailored_resume_id,
                cover_letter_id, application_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                item["user_id"],
                item["job_id"],
                item["status"],
                json.dumps(item.get("preferences", {})),
                item.get("resume_tailored", False),
                item.get("cover_letter_generated", False),
                item.get("application_ready", False),
                item.get("tailored_resume_id"),
                item.get("cover_letter_id"),
                item.get("application_id"),
            ),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_auto_apply_item(item_id: int, db_path: Path = DB_PATH) -> Optional[dict]:
    """Get a specific auto-apply queue item."""
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM auto_apply_queue WHERE id = ?", (item_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_auto_apply_items(
    user_id: int, status: str = None, db_path: Path = DB_PATH
) -> list[dict]:
    """Get all auto-apply items for a user, optionally filtered by status."""
    conn = get_connection(db_path)
    try:
        if status:
            rows = conn.execute(
                "SELECT * FROM auto_apply_queue WHERE user_id = ? AND status = ? ORDER BY created_at DESC",
                (user_id, status),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM auto_apply_queue WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def update_auto_apply_status(item_id: int, status: str, db_path: Path = DB_PATH) -> bool:
    """Update the status of an auto-apply item."""
    conn = get_connection(db_path)
    try:
        cur = conn.execute(
            "UPDATE auto_apply_queue SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, item_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def update_auto_apply_field(item_id: int, field: str, value, db_path: Path = DB_PATH) -> bool:
    """Update a specific field in an auto-apply item."""
    allowed_fields = {
        "resume_tailored", "cover_letter_generated", "application_ready",
        "tailored_resume_id", "cover_letter_id", "application_id", "error_message",
    }
    if field not in allowed_fields:
        return False
    conn = get_connection(db_path)
    try:
        cur = conn.execute(
            f"UPDATE auto_apply_queue SET {field} = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (value, item_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def update_auto_apply_error(item_id: int, error: str, db_path: Path = DB_PATH) -> bool:
    """Update error message for a failed auto-apply item."""
    conn = get_connection(db_path)
    try:
        cur = conn.execute(
            "UPDATE auto_apply_queue SET error_message = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (error, item_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def delete_auto_apply_item(item_id: int, db_path: Path = DB_PATH) -> bool:
    """Delete an auto-apply queue item."""
    conn = get_connection(db_path)
    try:
        cur = conn.execute("DELETE FROM auto_apply_queue WHERE id = ?", (item_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()
