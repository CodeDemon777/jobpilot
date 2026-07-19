"""Email Alert Service for JobPilot."""

from datetime import datetime, timedelta
from jobpilot.models import AlertSubscription, JobListing


def match_alert_to_jobs(
    alert: AlertSubscription, jobs: list[JobListing]
) -> list[JobListing]:
    """
    Match an alert subscription against a list of jobs.

    Returns jobs that match the alert criteria.
    """
    matched = []

    for job in jobs:
        if _job_matches_alert(job, alert):
            matched.append(job)

    return matched


def _job_matches_alert(job: JobListing, alert: AlertSubscription) -> bool:
    """Check if a job matches an alert subscription."""
    # Role matching (keyword-based)
    if alert.role:
        role_lower = alert.role.lower()
        job_text = f"{job.title} {job.description} {job.department}".lower()
        if role_lower not in job_text:
            # Check individual words
            role_words = role_lower.split()
            if not any(w in job_text for w in role_words):
                return False

    # Location matching
    if alert.location:
        location_lower = alert.location.lower()
        job_location = job.location.lower()
        if location_lower not in job_location and location_lower != "remote":
            return False

    # Remote preference
    if alert.remote_only:
        if job.remote_status.lower() not in ("remote", "fully remote"):
            return False

    # Experience level matching
    if alert.experience_level:
        exp_map = {
            "entry": (0, 2),
            "junior": (0, 3),
            "mid": (2, 5),
            "senior": (4, 8),
            "lead": (5, 15),
            "executive": (8, 30),
        }
        if alert.experience_level in exp_map:
            min_exp, max_exp = exp_map[alert.experience_level]
            if not (min_exp <= job.experience_years <= max_exp):
                return False

    return True


def evaluate_alerts(
    alerts: list[dict], jobs: list[JobListing]
) -> dict[int, list[JobListing]]:
    """
    Evaluate all active alerts against a job list.

    Returns dict mapping alert_id to matched jobs.
    """
    results = {}

    for alert_data in alerts:
        alert = AlertSubscription(
            id=alert_data["id"],
            role=alert_data.get("role", ""),
            location=alert_data.get("location", ""),
            remote_only=alert_data.get("remote_only", False),
            experience_level=alert_data.get("experience_level", ""),
            frequency=alert_data.get("frequency", "daily"),
        )

        matched_jobs = match_alert_to_jobs(alert, jobs)
        if matched_jobs:
            results[alert.id] = matched_jobs

    return results


def should_notify(alert_data: dict) -> bool:
    """Check if an alert should be notified based on frequency."""
    frequency = alert_data.get("frequency", "daily")
    last_notified = alert_data.get("last_notified_at", "")

    if not last_notified:
        return True

    try:
        last_time = datetime.fromisoformat(last_notified)
    except (ValueError, TypeError):
        return True

    now = datetime.now()
    time_since = now - last_time

    if frequency == "instant":
        return True
    elif frequency == "daily":
        return time_since >= timedelta(days=1)
    elif frequency == "weekly":
        return time_since >= timedelta(weeks=1)
    elif frequency == "monthly":
        return time_since >= timedelta(days=30)

    return True


def generate_alert_message(matched_jobs: list[JobListing], alert_role: str) -> str:
    """Generate a human-readable alert message."""
    if not matched_jobs:
        return "No new matching jobs found."

    count = len(matched_jobs)
    role_text = f" for '{alert_role}'" if alert_role else ""

    lines = [
        f"🔔 {count} new job{'s' if count > 1 else ''} match your alert{role_text}:\n"
    ]

    for i, job in enumerate(matched_jobs[:5], 1):
        lines.append(f"{i}. {job.title} at {job.company}")
        if job.location:
            lines.append(f"   📍 {job.location}")
        if job.salary_min or job.salary_max:
            salary = f"${job.salary_min:,}" if job.salary_min else ""
            if job.salary_max:
                salary += (
                    f" - ${job.salary_max:,}" if salary else f"${job.salary_max:,}"
                )
            if salary:
                lines.append(f"   💰 {salary}")
        lines.append("")

    if count > 5:
        lines.append(f"... and {count - 5} more jobs")

    return "\n".join(lines)


def get_alert_frequency_options() -> list[dict]:
    """Get available frequency options with descriptions."""
    return [
        {
            "value": "instant",
            "label": "Instant",
            "description": "Get notified immediately when a match is found",
        },
        {
            "value": "daily",
            "label": "Daily",
            "description": "Receive a daily digest of matching jobs",
        },
        {
            "value": "weekly",
            "label": "Weekly",
            "description": "Receive a weekly summary of matching jobs",
        },
    ]


def get_experience_level_options() -> list[dict]:
    """Get available experience level options."""
    return [
        {"value": "entry", "label": "Entry Level", "description": "0-2 years"},
        {"value": "junior", "label": "Junior", "description": "0-3 years"},
        {"value": "mid", "label": "Mid Level", "description": "2-5 years"},
        {"value": "senior", "label": "Senior", "description": "4-8 years"},
        {"value": "lead", "label": "Lead/Principal", "description": "5-15 years"},
        {"value": "executive", "label": "Executive", "description": "8+ years"},
    ]
