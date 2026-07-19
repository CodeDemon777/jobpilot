"""Dashboard Analytics for JobPilot."""

import json
from datetime import datetime, timedelta
from jobpilot import database as db
from jobpilot.config import DB_PATH
from pathlib import Path


def compute_analytics(db_path: Path = DB_PATH) -> dict:
    """
    Compute comprehensive dashboard analytics.

    Returns dict with:
        - job_search_metrics: Jobs, matches, sources
        - resume_metrics: ATS scores, quality scores
        - application_metrics: Status distribution, rates
        - skills_metrics: Top skills, missing skills
        - timeline: Application timeline data
        - trends: Match score trends
    """
    # Job search metrics
    job_metrics = _compute_job_metrics(db_path)

    # Resume metrics
    resume_metrics = _compute_resume_metrics(db_path)

    # Application metrics
    app_metrics = _compute_application_metrics(db_path)

    # Skills metrics
    skills_metrics = _compute_skills_metrics(db_path)

    # Timeline
    timeline = _compute_application_timeline(db_path)

    # Trends
    trends = _compute_match_trends(db_path)

    return {
        "job_search_metrics": job_metrics,
        "resume_metrics": resume_metrics,
        "application_metrics": app_metrics,
        "skills_metrics": skills_metrics,
        "timeline": timeline,
        "trends": trends,
        "computed_at": datetime.now().isoformat(),
    }


def _compute_job_metrics(db_path: Path) -> dict:
    """Compute job search metrics."""
    conn = db.get_connection(db_path)
    try:
        total_jobs = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        total_companies = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]

        # Jobs by source
        sources = conn.execute(
            "SELECT source, COUNT(*) as cnt FROM jobs GROUP BY source ORDER BY cnt DESC"
        ).fetchall()

        # Jobs by location
        locations = conn.execute(
            "SELECT location, COUNT(*) as cnt FROM jobs WHERE location != '' GROUP BY location ORDER BY cnt DESC LIMIT 10"
        ).fetchall()

        # Average match score
        avg_score = conn.execute(
            "SELECT COALESCE(AVG(overall_score), 0) FROM match_results"
        ).fetchone()[0]

        return {
            "total_jobs": total_jobs,
            "total_companies": total_companies,
            "by_source": [{"source": r["source"], "count": r["cnt"]} for r in sources],
            "by_location": [
                {"location": r["location"], "count": r["cnt"]} for r in locations
            ],
            "avg_match_score": round(avg_score, 3),
        }
    finally:
        conn.close()


def _compute_resume_metrics(db_path: Path) -> dict:
    """Compute resume metrics."""
    conn = db.get_connection(db_path)
    try:
        total_resumes = conn.execute("SELECT COUNT(*) FROM resumes").fetchone()[0]
        total_analyses = conn.execute(
            "SELECT COUNT(*) FROM resume_analyses"
        ).fetchone()[0]

        # Average scores
        avg_ats = conn.execute(
            "SELECT COALESCE(AVG(ats_score), 0) FROM resume_analyses"
        ).fetchone()[0]
        avg_quality = conn.execute(
            "SELECT COALESCE(AVG(resume_quality_score), 0) FROM resume_analyses"
        ).fetchone()[0]
        avg_technical = conn.execute(
            "SELECT COALESCE(AVG(technical_strength_score), 0) FROM resume_analyses"
        ).fetchone()[0]
        avg_hiring = conn.execute(
            "SELECT COALESCE(AVG(hiring_readiness_score), 0) FROM resume_analyses"
        ).fetchone()[0]

        # Score distribution
        score_ranges = conn.execute("""
            SELECT
                CASE
                    WHEN ats_score >= 0.8 THEN 'excellent'
                    WHEN ats_score >= 0.6 THEN 'good'
                    WHEN ats_score >= 0.4 THEN 'fair'
                    ELSE 'poor'
                END as range,
                COUNT(*) as cnt
            FROM resume_analyses
            GROUP BY range
        """).fetchall()

        return {
            "total_resumes": total_resumes,
            "total_analyses": total_analyses,
            "avg_ats_score": round(avg_ats, 3),
            "avg_quality_score": round(avg_quality, 3),
            "avg_technical_score": round(avg_technical, 3),
            "avg_hiring_readiness": round(avg_hiring, 3),
            "score_distribution": [
                {"range": r["range"], "count": r["cnt"]} for r in score_ranges
            ],
        }
    finally:
        conn.close()


def _compute_application_metrics(db_path: Path) -> dict:
    """Compute application metrics."""
    conn = db.get_connection(db_path)
    try:
        total_apps = conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0]

        # Status distribution
        statuses = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM applications GROUP BY status"
        ).fetchall()
        status_dist = {r["status"]: r["cnt"] for r in statuses}

        # Calculate rates
        interview_count = status_dist.get("interview", 0) + status_dist.get(
            "assessment", 0
        )
        offer_count = status_dist.get("offer", 0) + status_dist.get("accepted", 0)
        rejection_count = status_dist.get("rejected", 0)

        interview_rate = (interview_count / total_apps * 100) if total_apps > 0 else 0
        offer_rate = (offer_count / total_apps * 100) if total_apps > 0 else 0
        rejection_rate = (rejection_count / total_apps * 100) if total_apps > 0 else 0

        return {
            "total_applications": total_apps,
            "status_distribution": status_dist,
            "interview_rate": round(interview_rate, 1),
            "offer_rate": round(offer_rate, 1),
            "rejection_rate": round(rejection_rate, 1),
        }
    finally:
        conn.close()


def _compute_skills_metrics(db_path: Path = DB_PATH) -> dict:
    """Compute skills metrics from resume analyses."""
    conn = db.get_connection(db_path)
    try:
        # Get all skills from analyses
        rows = conn.execute("SELECT skills FROM resume_analyses").fetchall()

        skill_counts = {}
        for row in rows:
            try:
                skills = json.loads(row["skills"] or "[]")
                for skill in skills:
                    skill_lower = skill.lower().strip()
                    skill_counts[skill_lower] = skill_counts.get(skill_lower, 0) + 1
            except (json.JSONDecodeError, TypeError):
                continue

        # Top skills
        top_skills = sorted(skill_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        # Get missing skills
        missing_rows = conn.execute(
            "SELECT missing_skills FROM resume_analyses"
        ).fetchall()
        missing_counts = {}
        for row in missing_rows:
            try:
                missing = json.loads(row["missing_skills"] or "[]")
                for skill in missing:
                    skill_lower = skill.lower().strip()
                    missing_counts[skill_lower] = missing_counts.get(skill_lower, 0) + 1
            except (json.JSONDecodeError, TypeError):
                continue

        top_missing = sorted(missing_counts.items(), key=lambda x: x[1], reverse=True)[
            :10
        ]

        return {
            "top_skills": [{"skill": s, "count": c} for s, c in top_skills],
            "missing_skills": [{"skill": s, "count": c} for s, c in top_missing],
            "total_unique_skills": len(skill_counts),
        }
    finally:
        conn.close()


def _compute_application_timeline(db_path: Path = DB_PATH) -> list[dict]:
    """Compute application timeline (last 30 days)."""
    conn = db.get_connection(db_path)
    try:
        thirty_days_ago = (datetime.now() - timedelta(days=30)).isoformat()

        rows = conn.execute(
            """
            SELECT DATE(updated_date) as date, COUNT(*) as cnt
            FROM applications
            WHERE updated_date >= ?
            GROUP BY DATE(updated_date)
            ORDER BY date
        """,
            (thirty_days_ago,),
        ).fetchall()

        # Fill in missing days
        timeline = {}
        for r in rows:
            timeline[r["date"]] = r["cnt"]

        result = []
        for i in range(30):
            date = (datetime.now() - timedelta(days=29 - i)).strftime("%Y-%m-%d")
            result.append(
                {
                    "date": date,
                    "count": timeline.get(date, 0),
                }
            )

        return result
    finally:
        conn.close()


def _compute_match_trends(db_path: Path) -> list[dict]:
    """Compute match score trends (last 30 days)."""
    conn = db.get_connection(db_path)
    try:
        thirty_days_ago = (datetime.now() - timedelta(days=30)).isoformat()

        rows = conn.execute(
            """
            SELECT DATE(computed_at) as date, AVG(overall_score) as avg_score
            FROM match_results
            WHERE computed_at >= ?
            GROUP BY DATE(computed_at)
            ORDER BY date
        """,
            (thirty_days_ago,),
        ).fetchall()

        trends = {}
        for r in rows:
            trends[r["date"]] = round(r["avg_score"], 3)

        result = []
        for i in range(30):
            date = (datetime.now() - timedelta(days=29 - i)).strftime("%Y-%m-%d")
            result.append(
                {
                    "date": date,
                    "avg_score": trends.get(date, 0),
                }
            )

        return result
    finally:
        conn.close()


def get_dashboard_summary(db_path: Path = DB_PATH) -> dict:
    """Get a quick summary for the dashboard."""
    conn = db.get_connection(db_path)
    try:
        total_jobs = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        total_apps = conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
        total_resumes = conn.execute("SELECT COUNT(*) FROM resumes").fetchone()[0]
        avg_match = conn.execute(
            "SELECT COALESCE(AVG(overall_score), 0) FROM match_results"
        ).fetchone()[0]

        # Status counts
        statuses = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM applications GROUP BY status"
        ).fetchall()
        status_counts = {r["status"]: r["cnt"] for r in statuses}

        return {
            "total_jobs": total_jobs,
            "total_applications": total_apps,
            "total_resumes": total_resumes,
            "avg_match_score": round(avg_match, 3),
            "interviews": status_counts.get("interview", 0)
            + status_counts.get("assessment", 0),
            "offers": status_counts.get("offer", 0) + status_counts.get("accepted", 0),
            "rejections": status_counts.get("rejected", 0),
        }
    finally:
        conn.close()


def get_enhanced_dashboard(db_path: Path = DB_PATH) -> dict:
    """
    Get enhanced dashboard with new job detection and trending analytics.
    """
    scan_stats = db.get_scan_stats(db_path)
    jobs_today = db.get_jobs_discovered_today(db_path)
    jobs_week = db.get_jobs_discovered_this_week(db_path)
    top_companies = db.get_top_hiring_companies(10, db_path)
    top_skills = db.get_most_frequent_skills(10, db_path)
    jobs_by_source = db.get_jobs_by_source(db_path)
    recent_high_match = db.get_recent_high_match_jobs(10, db_path)
    unread_count = db.get_unread_notification_count(db_path)
    notifications = db.get_job_notifications(limit=20, db_path=db_path)

    return {
        "scan_stats": scan_stats,
        "jobs_discovered_today": len(jobs_today),
        "jobs_discovered_this_week": len(jobs_week),
        "jobs_today": jobs_today[:10],
        "top_hiring_companies": top_companies,
        "top_skills": top_skills,
        "jobs_by_source": jobs_by_source,
        "recent_high_match": recent_high_match,
        "unread_notifications": unread_count,
        "notifications": notifications,
    }
