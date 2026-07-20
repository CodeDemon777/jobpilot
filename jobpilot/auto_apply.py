"""AI Auto Apply Queue - Manages job applications from discovery to submission."""

import json
import logging
from datetime import datetime
from typing import Optional

from jobpilot import database as db
from jobpilot.config import DB_PATH
from jobpilot.models import JobListing, UserProfile, MatchResult
from jobpilot.profile import load_profile
from jobpilot.matcher import compute_match
from jobpilot.resume_tailor import tailor_resume
from jobpilot.cover_letter_generator import generate_cover_letter

logger = logging.getLogger(__name__)

# Application queue statuses
QUEUE_STATUSES = {
    "queued": "Queued for processing",
    "preparing": "Generating application materials",
    "ready": "Ready for user review",
    "pending_submission": "Waiting for user to submit",
    "submitted": "Application submitted",
    "failed": "Application failed",
    "cancelled": "Application cancelled",
}


class AutoApplyQueue:
    """
    Manages the auto-apply queue workflow.

    Flow:
    1. User sets preferences (role, location, match threshold, etc.)
    2. System scans supported sources for matching jobs
    3. Jobs are added to the queue
    4. For each queued job, system generates:
       - Tailored resume
       - Cover letter
       - Application answers
    5. User reviews and confirms
    6. System tracks the application
    """

    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH

    def create_queue_item(self, user_id: int, job_id: str, preferences: dict = None) -> dict:
        """
        Add a job to the auto-apply queue.

        Returns the queue item with initial status.
        """
        if preferences is None:
            preferences = {}

        queue_item = {
            "user_id": user_id,
            "job_id": job_id,
            "status": "queued",
            "preferences": preferences,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "resume_tailored": False,
            "cover_letter_generated": False,
            "application_ready": False,
            "tailored_resume_id": None,
            "cover_letter_id": None,
            "application_id": None,
        }

        # Save to database
        queue_id = db.save_auto_apply_item(queue_item, self.db_path)
        queue_item["id"] = queue_id

        logger.info(f"Added job {job_id} to auto-apply queue (ID: {queue_id})")
        return queue_item

    def process_queue_item(self, queue_id: int) -> dict:
        """
        Process a queue item through the preparation pipeline.

        Steps:
        1. Generate tailored resume
        2. Generate cover letter
        3. Prepare application package
        4. Mark as ready for review
        """
        item = db.get_auto_apply_item(queue_id, self.db_path)
        if not item:
            return {"error": "Queue item not found"}

        job = db.get_job(item["job_id"])
        if not job:
            return {"error": "Job not found"}

        profile = load_profile()

        # Update status to preparing
        db.update_auto_apply_status(queue_id, "preparing", self.db_path)

        try:
            # Step 1: Generate tailored resume
            resume_text = self._get_resume_text(profile)
            if resume_text:
                tailor_result = tailor_resume(
                    resume_text=resume_text,
                    job_description=job.description,
                    job_skills=job.required_skills,
                )
                # Save tailored resume
                from jobpilot.models import TailoredResume
                tailored = TailoredResume(
                    original_resume_id="",
                    job_id=item["job_id"],
                    original_text=tailor_result["original_text"],
                    tailored_text=tailor_result["tailored_text"],
                    original_score=tailor_result["original_score"],
                    tailored_score=tailor_result["tailored_score"],
                    improvement_pct=tailor_result["improvement_pct"],
                    keywords_added=tailor_result.get("keywords_added", []),
                )
                tailored_id = db.save_tailored_resume(tailored, self.db_path)
                db.update_auto_apply_field(queue_id, "tailored_resume_id", tailored_id, self.db_path)
                db.update_auto_apply_field(queue_id, "resume_tailored", True, self.db_path)

            # Step 2: Generate cover letter
            cover_result = generate_cover_letter(
                resume_text=resume_text or "",
                job_description=job.description,
                company=job.company,
                role=job.title,
                tone="professional",
                candidate_name=profile.name,
            )
            # Save cover letter
            from jobpilot.models import CoverLetter
            letter = CoverLetter(
                resume_id="",
                job_id=item["job_id"],
                company_name=job.company,
                role_title=job.title,
                job_description=job.description,
                letter_text=cover_result["letter_text"],
                tone="professional",
                word_count=cover_result["word_count"],
            )
            letter_id = db.save_cover_letter(letter, self.db_path)
            db.update_auto_apply_field(queue_id, "cover_letter_id", letter_id, self.db_path)
            db.update_auto_apply_field(queue_id, "cover_letter_generated", True, self.db_path)

            # Step 3: Create application record
            from jobpilot.models import Application
            match_result = compute_match(profile, job)
            application = Application(
                job_id=item["job_id"],
                company=job.company,
                role=job.title,
                status="discovered",
                match_score=match_result.overall_score,
            )
            app_id = db.upsert_application(application, self.db_path)
            db.update_auto_apply_field(queue_id, "application_id", app_id, self.db_path)

            # Step 4: Mark as ready
            db.update_auto_apply_status(queue_id, "ready", self.db_path)
            db.update_auto_apply_field(queue_id, "application_ready", True, self.db_path)

            return {
                "status": "ready",
                "job": job.to_dict(),
                "tailored_resume": tailor_result if resume_text else None,
                "cover_letter": cover_result,
                "match_score": match_result.overall_score,
                "application_url": job.application_url or job.url,
            }

        except Exception as e:
            logger.error(f"Error processing queue item {queue_id}: {e}")
            db.update_auto_apply_status(queue_id, "failed", self.db_path)
            db.update_auto_apply_error(queue_id, str(e), self.db_path)
            return {"error": str(e), "status": "failed"}

    def approve_application(self, queue_id: int) -> dict:
        """User approves the application for submission."""
        item = db.get_auto_apply_item(queue_id, self.db_path)
        if not item:
            return {"error": "Queue item not found"}

        if item["status"] != "ready":
            return {"error": "Application not ready for submission"}

        db.update_auto_apply_status(queue_id, "pending_submission", self.db_path)
        return {"status": "pending_submission", "message": "Application ready for submission"}

    def submit_application(self, queue_id: int) -> dict:
        """Mark application as submitted."""
        item = db.get_auto_apply_item(queue_id, self.db_path)
        if not item:
            return {"error": "Queue item not found"}

        # Update application status
        if item.get("application_id"):
            db.update_application_status(item["application_id"], "applied", self.db_path)

        db.update_auto_apply_status(queue_id, "submitted", self.db_path)
        return {"status": "submitted", "message": "Application marked as submitted"}

    def cancel_application(self, queue_id: int) -> dict:
        """Cancel an application in the queue."""
        item = db.get_auto_apply_item(queue_id, self.db_path)
        if not item:
            return {"error": "Queue item not found"}

        db.update_auto_apply_status(queue_id, "cancelled", self.db_path)
        return {"status": "cancelled", "message": "Application cancelled"}

    def get_queue_item(self, queue_id: int) -> Optional[dict]:
        """Get a specific queue item."""
        return db.get_auto_apply_item(queue_id, self.db_path)

    def get_user_queue(self, user_id: int, status: str = None) -> list[dict]:
        """Get all queue items for a user, optionally filtered by status."""
        return db.get_auto_apply_items(user_id, status, self.db_path)

    def get_queue_stats(self, user_id: int) -> dict:
        """Get queue statistics for a user."""
        items = db.get_auto_apply_items(user_id, db_path=self.db_path)
        stats = {
            "total": len(items),
            "queued": sum(1 for i in items if i["status"] == "queued"),
            "preparing": sum(1 for i in items if i["status"] == "preparing"),
            "ready": sum(1 for i in items if i["status"] == "ready"),
            "pending_submission": sum(1 for i in items if i["status"] == "pending_submission"),
            "submitted": sum(1 for i in items if i["status"] == "submitted"),
            "failed": sum(1 for i in items if i["status"] == "failed"),
            "cancelled": sum(1 for i in items if i["status"] == "cancelled"),
        }
        return stats

    def _get_resume_text(self, profile: UserProfile) -> str:
        """Get resume text from profile or uploaded resumes."""
        # Try to get from uploaded resumes
        uploads = db.get_all_uploaded_resumes(self.db_path)
        if uploads:
            # Get the most recent upload
            latest = uploads[0]
            resume = db.get_uploaded_resume(latest["id"], self.db_path)
            if resume:
                return resume.get("raw_text", "")

        # Try to get from resumes table
        resumes = db.get_all_resumes(self.db_path)
        if resumes:
            resume = db.get_resume(resumes[0]["id"], self.db_path)
            if resume:
                return resume.raw_text

        # Build a basic resume from profile
        lines = [
            profile.name or "Professional",
            profile.email or "",
            profile.phone or "",
            f"Skills: {', '.join(profile.all_skills[:10])}",
            f"Experience: {profile.experience_years} years",
        ]
        if profile.education:
            for edu in profile.education:
                if isinstance(edu, dict):
                    lines.append(f"Education: {edu.get('degree', '')} - {edu.get('school', '')}")
                else:
                    lines.append(f"Education: {edu}")
        return "\n".join(lines)
