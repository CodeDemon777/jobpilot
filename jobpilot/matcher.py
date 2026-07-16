"""Matching engine — computes weighted match scores between user profile and jobs."""

from jobpilot.config import WEIGHTS
from jobpilot.models import UserProfile, JobListing, MatchResult


def compute_match(profile: UserProfile, job: JobListing) -> MatchResult:
    """Compute a weighted match score between a user profile and a job listing."""
    skills_score = _skills_score(profile, job)
    experience_score = _experience_score(profile, job)
    relevance_score = _relevance_score(profile, job)
    education_score = _education_score(profile, job)
    role_score = _role_score(profile, job)
    location_score = _location_score(profile, job)

    overall = (
        skills_score * WEIGHTS["skills"]
        + experience_score * WEIGHTS["experience"]
        + relevance_score * WEIGHTS["relevance"]
        + education_score * WEIGHTS["education"]
        + role_score * WEIGHTS["role"]
        + location_score * WEIGHTS["location"]
    )

    strengths, weaknesses, missing = _analyze(profile, job, {
        "skills": skills_score,
        "experience": experience_score,
        "relevance": relevance_score,
        "education": education_score,
        "role": role_score,
        "location": location_score,
    })

    return MatchResult(
        job_id=job.id,
        overall_score=round(overall, 3),
        skills_score=round(skills_score, 3),
        experience_score=round(experience_score, 3),
        relevance_score=round(relevance_score, 3),
        education_score=round(education_score, 3),
        role_score=round(role_score, 3),
        location_score=round(location_score, 3),
        strengths=strengths,
        weaknesses=weaknesses,
        missing_skills=missing,
    )


def _skills_score(profile: UserProfile, job: JobListing) -> float:
    """Score based on skill overlap."""
    user_skills = set(profile.all_skills)
    required = job.all_required_skills
    preferred = job.all_preferred_skills

    if not required and not preferred:
        return 0.5  # No skill info — neutral score

    required_score = 0.0
    if required:
        matched = sum(1 for s in required if s in user_skills)
        required_score = matched / len(required)

    preferred_score = 0.0
    if preferred:
        matched = sum(1 for s in preferred if s in user_skills)
        preferred_score = matched / len(preferred)

    return required_score * 0.7 + preferred_score * 0.3


def _experience_score(profile: UserProfile, job: JobListing) -> float:
    """Score based on years of experience."""
    if job.experience_years <= 0:
        return 0.7  # No requirement stated — neutral-positive
    ratio = profile.experience_years / job.experience_years
    return min(1.0, ratio)


def _relevance_score(profile: UserProfile, job: JobListing) -> float:
    """Score based on how relevant the job description is to user's skills."""
    user_skills = set(profile.all_skills)
    if not user_skills:
        return 0.5

    # Look for skill mentions in job description
    desc_lower = job.description.lower()
    mentioned = sum(1 for s in user_skills if s in desc_lower)
    if not user_skills:
        return 0.5
    return min(1.0, mentioned / max(1, len(user_skills) * 0.3))


def _education_score(profile: UserProfile, job: JobListing) -> float:
    """Score based on education requirements."""
    if not job.education:
        return 0.8  # No requirement — slightly positive

    edu_lower = job.education.lower()
    user_edus = [e.get("degree", "").lower() for e in profile.education]

    degree_hierarchy = {"phd": 4, "doctorate": 4, "master": 3, "mba": 3, "bachelor": 2, "bs": 2, "ba": 2, "associate": 1}

    def get_level(degree_str: str) -> int:
        for key, val in degree_hierarchy.items():
            if key in degree_str:
                return val
        return 1

    required_level = get_level(edu_lower)
    user_level = max((get_level(e) for e in user_edus), default=0)

    if user_level >= required_level:
        return 1.0
    elif user_level > 0:
        return 0.6
    return 0.3


def _role_score(profile: UserProfile, job: JobListing) -> float:
    """Score based on role preference alignment."""
    if not profile.preferred_roles:
        return 0.5

    title_lower = job.title.lower()
    for role in profile.preferred_roles:
        if role.lower() in title_lower or title_lower in role.lower():
            return 1.0

    # Check for partial matches
    for role in profile.preferred_roles:
        role_words = set(role.lower().split())
        title_words = set(title_lower.split())
        overlap = role_words & title_words
        if overlap:
            return 0.6

    return 0.1


def _location_score(profile: UserProfile, job: JobListing) -> float:
    """Score based on location preference."""
    job_loc = job.location.lower()
    job_remote = job.remote_status.lower()

    # Remote preference
    if profile.remote_preference in ("remote", "any"):
        if "remote" in job_remote or "remote" in job_loc:
            return 1.0

    # Exact location match
    if profile.location and profile.location.lower() in job_loc:
        return 1.0

    # Country match
    if profile.country and profile.country.lower() in job_loc:
        return 0.7

    # Remote available
    if "remote" in job_remote:
        return 0.9

    # Preferred locations
    if profile.preferred_locations:
        for loc in profile.preferred_locations:
            if loc.lower() in job_loc:
                return 1.0

    return 0.3


def _analyze(
    profile: UserProfile,
    job: JobListing,
    scores: dict[str, float],
) -> tuple[list[str], list[str], list[str]]:
    """Generate strengths, weaknesses, and missing skills."""
    strengths = []
    weaknesses = []
    missing = []

    user_skills = set(profile.all_skills)

    # Skills analysis
    if scores["skills"] >= 0.7:
        strengths.append(f"Strong skill match ({scores['skills']:.0%})")
    elif scores["skills"] < 0.4:
        weaknesses.append(f"Low skill overlap ({scores['skills']:.0%})")

    for s in job.all_required_skills:
        if s not in user_skills:
            missing.append(s)

    # Experience
    if scores["experience"] >= 0.8:
        strengths.append("Meets experience requirements")
    elif scores["experience"] < 0.5:
        weaknesses.append("Below preferred experience level")

    # Role
    if scores["role"] >= 0.8:
        strengths.append("Strong role alignment")
    elif scores["role"] < 0.3:
        weaknesses.append("Role may not match preferences")

    # Location
    if scores["location"] >= 0.8:
        strengths.append("Good location match")
    elif scores["location"] < 0.5:
        weaknesses.append("Location may not be ideal")

    # Education
    if scores["education"] >= 0.8:
        strengths.append("Education requirements met")

    return strengths, weaknesses, missing
