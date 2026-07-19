"""Job Scanner — handles job discovery, duplicate detection, and smart alerts."""

import logging
import time
from typing import Optional

from jobpilot import database as db
from jobpilot.config import DB_PATH
from jobpilot.models import JobListing, AlertSubscription, UserProfile, MatchResult
from jobpilot.matcher import compute_match
from jobpilot.profile import load_profile

logger = logging.getLogger(__name__)


class JobScanner:
    """Manages job scanning with duplicate detection and smart alerts."""

    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH

    async def scan_source(
        self,
        source: str,
        query: str = "",
        location: str = "",
        limit: int = 50,
    ) -> dict:
        """
        Scan a single source for jobs.

        Returns:
            dict with keys: source, jobs_found, new_jobs_found, new_jobs, duration
        """
        from jobpilot.scraper import SCRAPERS

        start_time = time.time()
        scraper_cls = SCRAPERS.get(source)
        if not scraper_cls:
            return {
                "source": source,
                "jobs_found": 0,
                "new_jobs_found": 0,
                "new_jobs": [],
                "duration": 0,
            }

        scraper = scraper_cls()
        all_jobs = []

        try:
            jobs = await scraper.search(query=query, location=location)
            all_jobs = jobs[:limit]
        except Exception as e:
            logger.warning(f"Failed to scrape {source}: {e}")

        duration = time.time() - start_time

        # Identify new jobs
        new_jobs = db.get_new_jobs(all_jobs, self.db_path)

        # Store all jobs (upsert handles existing ones)
        for job in all_jobs:
            db.upsert_job(job, self.db_path)

        # Record scan history
        db.save_scan_history(
            source=source,
            query=query,
            location=location,
            jobs_found=len(all_jobs),
            new_jobs_found=len(new_jobs),
            duration_seconds=duration,
            db_path=self.db_path,
        )

        return {
            "source": source,
            "jobs_found": len(all_jobs),
            "new_jobs_found": len(new_jobs),
            "new_jobs": new_jobs,
            "duration": round(duration, 2),
        }

    async def scan_all_sources(
        self,
        query: str = "",
        location: str = "",
        limit: int = 50,
    ) -> dict:
        """
        Scan all registered sources for jobs.

        Returns:
            dict with aggregated results
        """
        from jobpilot.scraper import SCRAPERS

        start_time = time.time()
        results = []

        for source_name in SCRAPERS.keys():
            result = await self.scan_source(source_name, query, location, limit)
            results.append(result)

        total_found = sum(r["jobs_found"] for r in results)
        total_new = sum(r["new_jobs_found"] for r in results)
        all_new_jobs = []
        for r in results:
            all_new_jobs.extend(r["new_jobs"])

        duration = time.time() - start_time

        # Process alerts for new jobs
        notifications_created = self._process_alerts_for_new_jobs(all_new_jobs)

        return {
            "sources_scanned": len(results),
            "total_jobs_found": total_found,
            "total_new_jobs": total_new,
            "new_jobs": [j.to_dict() for j in all_new_jobs],
            "notifications_created": notifications_created,
            "duration": round(duration, 2),
            "source_results": [
                {
                    "source": r["source"],
                    "found": r["jobs_found"],
                    "new": r["new_jobs_found"],
                }
                for r in results
            ],
        }

    def _process_alerts_for_new_jobs(self, new_jobs: list[JobListing]) -> int:
        """
        Process alerts for newly discovered jobs.

        Returns:
            Number of notifications created
        """
        if not new_jobs:
            return 0

        # Get active alerts
        active_alerts = db.get_active_alerts(self.db_path)
        if not active_alerts:
            return 0

        # Load user profile for matching
        profile = load_profile()

        notifications_created = 0

        for job in new_jobs:
            # Compute match score
            match_result = compute_match(profile, job)

            # Check each alert against this job
            for alert_data in active_alerts:
                alert = AlertSubscription(
                    id=alert_data["id"],
                    role=alert_data.get("role", ""),
                    location=alert_data.get("location", ""),
                    remote_only=alert_data.get("remote_only", False),
                    experience_level=alert_data.get("experience_level", ""),
                    frequency=alert_data.get("frequency", "daily"),
                    is_active=alert_data.get("is_active", True),
                    last_notified_at=alert_data.get("last_notified_at", ""),
                )

                if self._job_matches_alert(job, alert, match_result):
                    # Check if already notified
                    if not db.has_been_notified(job.id, self.db_path):
                        message = self._format_notification(job, match_result)
                        db.create_job_notification(
                            job_id=job.id,
                            notification_type="new_match",
                            message=message,
                            match_score=match_result.overall_score,
                            db_path=self.db_path,
                        )
                        notifications_created += 1
                        break  # One notification per job

        return notifications_created

    def _job_matches_alert(
        self, job: JobListing, alert: AlertSubscription, match_result: MatchResult
    ) -> bool:
        """Check if a job matches an alert subscription."""
        # Check role match
        if alert.role:
            role_lower = alert.role.lower()
            if (
                role_lower not in job.title.lower()
                and role_lower not in job.description.lower()
            ):
                return False

        # Check location match
        if alert.location:
            location_lower = alert.location.lower()
            if location_lower not in job.location.lower():
                if not (alert.remote_only and job.remote_status == "remote"):
                    return False

        # Check remote preference
        if alert.remote_only and job.remote_status != "remote":
            return False

        # Check experience level
        if alert.experience_level:
            level_ranges = {
                "entry": (0, 2),
                "mid": (2, 5),
                "senior": (5, 10),
                "lead": (8, 15),
            }
            if alert.experience_level in level_ranges:
                min_exp, max_exp = level_ranges[alert.experience_level]
                if not (min_exp <= job.experience_years <= max_exp):
                    return False

        # Check match score (minimum threshold of 0.3 for alerts)
        if match_result.overall_score < 0.3:
            return False

        return True

    def _format_notification(self, job: JobListing, match_result: MatchResult) -> str:
        """Format a notification message for a job match."""
        score_pct = f"{match_result.overall_score * 100:.0f}%"
        return (
            f"New High-Match Job Found\n"
            f"{job.title}\n"
            f"{job.company}\n"
            f"Match Score: {score_pct}\n"
            f"Location: {job.location}\n"
            f"Apply: {job.url}"
        )

    def deactivate_stale_jobs(self, max_age_days: int = 30) -> int:
        """
        Mark jobs as inactive if they haven't been seen recently.

        Returns:
            Number of jobs deactivated
        """
        conn = db.get_connection(self.db_path)
        try:
            cur = conn.execute(
                """
                UPDATE jobs SET is_active = 0
                WHERE is_active = 1
                AND discovered_at < DATE('now', ?)
            """,
                (f"-{max_age_days} days",),
            )
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()

    def get_scan_summary(self) -> dict:
        """Get a summary of scanning activity and results."""
        scan_stats = db.get_scan_stats(self.db_path)
        jobs_today = db.get_jobs_discovered_today(self.db_path)
        jobs_week = db.get_jobs_discovered_this_week(self.db_path)
        top_companies = db.get_top_hiring_companies(10, self.db_path)
        top_skills = db.get_most_frequent_skills(10, self.db_path)
        jobs_by_source = db.get_jobs_by_source(self.db_path)
        recent_high_match = db.get_recent_high_match_jobs(10, self.db_path)
        unread_count = db.get_unread_notification_count(self.db_path)

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
        }
