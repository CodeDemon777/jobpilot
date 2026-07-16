"""SQLite database layer for JobPilot."""

import json
import sqlite3
from pathlib import Path

from jobpilot.config import DB_PATH
from jobpilot.models import JobListing, MatchResult, Application, Company


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
    """)
    conn.commit()


# --- Jobs ---

def upsert_job(job: JobListing, db_path: Path = DB_PATH) -> bool:
    """Insert or update a job. Returns True if new, False if updated."""
    conn = get_connection(db_path)
    try:
        existing = conn.execute("SELECT id FROM jobs WHERE id = ?", (job.id,)).fetchone()
        conn.execute("""
            INSERT OR REPLACE INTO jobs
            (id, company, title, department, location, remote_status, employment_type,
             salary_min, salary_max, currency, required_skills, preferred_skills,
             experience_years, education, description, url, source, posted_date,
             application_url, tech_stack, visa_required, discovered_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            job.id, job.company, job.title, job.department, job.location,
            job.remote_status, job.employment_type, job.salary_min, job.salary_max,
            job.currency, json.dumps(job.required_skills), json.dumps(job.preferred_skills),
            job.experience_years, job.education, job.description, job.url, job.source,
            job.posted_date, job.application_url, json.dumps(job.tech_stack),
            job.visa_required, job.discovered_at,
        ))
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
        sql = "SELECT j.* FROM jobs j LEFT JOIN match_results m ON j.id = m.job_id WHERE 1=1"
        params = []
        if query:
            sql += " AND (j.title LIKE ? OR j.company LIKE ? OR j.description LIKE ?)"
            params.extend([f"%{query}%"] * 3)
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
    )


# --- Match Results ---

def save_match_result(result: MatchResult, db_path: Path = DB_PATH) -> None:
    """Save a match result."""
    conn = get_connection(db_path)
    try:
        conn.execute("""
            INSERT INTO match_results
            (job_id, overall_score, skills_score, experience_score, relevance_score,
             education_score, role_score, location_score, strengths, weaknesses, missing_skills)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            result.job_id, result.overall_score, result.skills_score,
            result.experience_score, result.relevance_score, result.education_score,
            result.role_score, result.location_score,
            json.dumps(result.strengths), json.dumps(result.weaknesses),
            json.dumps(result.missing_skills),
        ))
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
            role_score=row["location_score"],
            location_score=row["location_score"],
            strengths=json.loads(row["strengths"] or "[]"),
            weaknesses=json.loads(row["weaknesses"] or "[]"),
            missing_skills=json.loads(row["missing_skills"] or "[]"),
        )
    finally:
        conn.close()


def get_top_matches(limit: int = 20, db_path: Path = DB_PATH) -> list[tuple[JobListing, MatchResult]]:
    """Get top matching jobs with their match results."""
    conn = get_connection(db_path)
    try:
        rows = conn.execute("""
            SELECT j.*, m.overall_score, m.skills_score, m.experience_score,
                   m.relevance_score, m.education_score, m.role_score, m.location_score,
                   m.strengths, m.weaknesses, m.missing_skills
            FROM jobs j
            JOIN match_results m ON j.id = m.job_id
            ORDER BY m.overall_score DESC
            LIMIT ?
        """, (limit,)).fetchall()
        results = []
        for row in rows:
            job = _row_to_job(row)
            match = MatchResult(
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
            results.append((job, match))
        return results
    finally:
        conn.close()


# --- Applications ---

def upsert_application(app: Application, db_path: Path = DB_PATH) -> None:
    """Insert or update an application."""
    conn = get_connection(db_path)
    try:
        conn.execute("""
            INSERT OR REPLACE INTO applications
            (id, job_id, company, role, status, match_score, applied_date, updated_date, notes, resume_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            app.id, app.job_id, app.company, app.role, app.status,
            app.match_score, app.applied_date, app.updated_date,
            app.notes, app.resume_version,
        ))
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
            rows = conn.execute("SELECT * FROM applications ORDER BY updated_date DESC").fetchall()
        return [
            Application(
                job_id=r["job_id"], company=r["company"], role=r["role"],
                status=r["status"], match_score=r["match_score"],
                applied_date=r["applied_date"], updated_date=r["updated_date"],
                notes=r["notes"], resume_version=r["resume_version"],
            )
            for r in rows
        ]
    finally:
        conn.close()


def update_application_status(app_id: str, status: str, db_path: Path = DB_PATH) -> bool:
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
        conn.execute("""
            INSERT OR REPLACE INTO companies
            (name, website, industry, size, career_page, job_count, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            company.name, company.website, company.industry,
            company.size, company.career_page, company.job_count, company.notes,
        ))
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
                name=r["name"], website=r["website"], industry=r["industry"],
                size=r["size"], career_page=r["career_page"],
                job_count=r["job_count"], notes=r["notes"],
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
        avg_score = conn.execute("SELECT COALESCE(AVG(overall_score), 0) FROM match_results").fetchone()[0]
        top_sources = conn.execute(
            "SELECT source, COUNT(*) as cnt FROM jobs GROUP BY source ORDER BY cnt DESC"
        ).fetchall()
        return {
            "total_jobs": total_jobs,
            "total_companies": total_companies,
            "total_applications": total_apps,
            "average_match_score": round(avg_score, 3),
            "top_sources": [{"source": r["source"], "count": r["cnt"]} for r in top_sources],
        }
    finally:
        conn.close()
