"""Core data models for JobPilot."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime


def _generate_id(company: str, title: str, url: str) -> str:
    """Generate a deterministic ID from job fields."""
    raw = f"{company.lower().strip()}|{title.lower().strip()}|{url.strip()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


@dataclass
class UserProfile:
    name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    country: str = ""
    linkedin: str = ""
    github: str = ""
    portfolio: str = ""
    skills: list[str] = field(default_factory=list)
    programming_languages: list[str] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=list)
    cloud_platforms: list[str] = field(default_factory=list)
    experience_years: int = 0
    education: list[dict] = field(default_factory=list)
    preferred_roles: list[str] = field(default_factory=list)
    preferred_locations: list[str] = field(default_factory=list)
    remote_preference: str = "remote"
    expected_salary: str = ""
    visa_sponsorship: bool = False
    work_authorization: str = ""
    is_verified: bool = False
    verified_at: str = ""

    @property
    def all_skills(self) -> list[str]:
        """Return combined list of all user skills."""
        combined = set()
        for s in self.skills:
            combined.add(s.lower().strip())
        for s in self.programming_languages:
            combined.add(s.lower().strip())
        for s in self.frameworks:
            combined.add(s.lower().strip())
        for s in self.cloud_platforms:
            combined.add(s.lower().strip())
        return sorted(combined)


@dataclass
class JobListing:
    company: str = ""
    title: str = ""
    department: str = ""
    location: str = ""
    remote_status: str = ""
    employment_type: str = ""
    salary_min: int = 0
    salary_max: int = 0
    currency: str = "USD"
    required_skills: list[str] = field(default_factory=list)
    preferred_skills: list[str] = field(default_factory=list)
    experience_years: int = 0
    education: str = ""
    description: str = ""
    url: str = ""
    source: str = ""
    posted_date: str = ""
    application_url: str = ""
    tech_stack: list[str] = field(default_factory=list)
    visa_required: bool = False
    discovered_at: str = field(default_factory=lambda: datetime.now().isoformat())
    job_hash: str = ""
    is_active: bool = True

    @property
    def id(self) -> str:
        return _generate_id(self.company, self.title, self.url)

    @property
    def all_required_skills(self) -> list[str]:
        return [s.lower().strip() for s in self.required_skills]

    @property
    def all_preferred_skills(self) -> list[str]:
        return [s.lower().strip() for s in self.preferred_skills + self.tech_stack]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["id"] = self.id
        return d


@dataclass
class MatchResult:
    job_id: str = ""
    overall_score: float = 0.0
    skills_score: float = 0.0
    experience_score: float = 0.0
    relevance_score: float = 0.0
    education_score: float = 0.0
    role_score: float = 0.0
    location_score: float = 0.0
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    computed_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class Application:
    job_id: str = ""
    company: str = ""
    role: str = ""
    status: str = "discovered"
    match_score: float = 0.0
    applied_date: str = ""
    updated_date: str = field(default_factory=lambda: datetime.now().isoformat())
    notes: str = ""
    resume_version: str = ""

    @property
    def id(self) -> str:
        return _generate_id(self.company, self.role, self.job_id)


@dataclass
class Company:
    name: str = ""
    website: str = ""
    industry: str = ""
    size: str = ""
    career_page: str = ""
    job_count: int = 0
    notes: str = ""


@dataclass
class Resume:
    """A stored resume record."""
    id: str = ""
    name: str = ""
    filename: str = ""
    raw_text: str = ""
    target_role: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        d = asdict(self)
        # Don't include raw_text in default serialization (too large)
        d.pop("raw_text", None)
        return d


@dataclass
class CoverLetter:
    """A generated cover letter."""
    id: int = 0
    resume_id: str = ""
    job_id: str = ""
    company_name: str = ""
    role_title: str = ""
    job_description: str = ""
    letter_text: str = ""
    tone: str = "professional"
    word_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class InterviewQuestion:
    """A generated interview question."""
    id: int = 0
    job_id: str = ""
    resume_id: str = ""
    role_title: str = ""
    category: str = ""
    difficulty: str = ""
    question: str = ""
    sample_answer: str = ""
    tips: str = ""
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class SkillGapReport:
    """A skill gap analysis report."""
    id: int = 0
    resume_id: str = ""
    job_id: str = ""
    matched_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    extra_skills: list[str] = field(default_factory=list)
    match_percentage: float = 0.0
    learning_areas: list[str] = field(default_factory=list)
    priority_ranking: list[str] = field(default_factory=list)
    analyzed_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class LinkedInReport:
    """A LinkedIn profile analysis report."""
    id: int = 0
    headline: str = ""
    about: str = ""
    skills_raw: str = ""
    experience_raw: str = ""
    suggestions: list[str] = field(default_factory=list)
    missing_keywords: list[str] = field(default_factory=list)
    visibility_score: float = 0.0
    strength_score: float = 0.0
    analyzed_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class TailoredResume:
    """A tailored resume version."""
    id: int = 0
    original_resume_id: str = ""
    job_id: str = ""
    original_text: str = ""
    tailored_text: str = ""
    original_score: float = 0.0
    tailored_score: float = 0.0
    improvement_pct: float = 0.0
    keywords_added: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class AlertSubscription:
    """A job alert subscription."""
    id: int = 0
    role: str = ""
    location: str = ""
    remote_only: bool = False
    experience_level: str = ""
    frequency: str = "daily"
    is_active: bool = True
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_notified_at: str = ""


@dataclass
class ImprovementReport:
    """A resume improvement report."""
    resume_id: str = ""
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    improvements: list[dict] = field(default_factory=list)
    recommended_keywords: list[str] = field(default_factory=list)
    score_before: dict = field(default_factory=dict)
    score_after: dict = field(default_factory=dict)


@dataclass
class DashboardStats:
    """Dashboard statistics."""
    id: int = 0
    period: str = "all"
    total_jobs: int = 0
    total_applications: int = 0
    total_interviews: int = 0
    total_offers: int = 0
    total_rejections: int = 0
    avg_match_score: float = 0.0
    avg_ats_score: float = 0.0
    application_timeline: list[dict] = field(default_factory=list)
    skill_coverage: list[dict] = field(default_factory=list)
    match_trends: list[dict] = field(default_factory=list)
    computed_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class JobNotification:
    """A job notification for smart alerts."""
    id: int = 0
    job_id: str = ""
    notification_type: str = "new_match"
    message: str = ""
    match_score: float = 0.0
    is_read: bool = False
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class JobScanHistory:
    """Record of a job scan operation."""
    id: int = 0
    source: str = ""
    query: str = ""
    location: str = ""
    scanned_at: str = field(default_factory=lambda: datetime.now().isoformat())
    jobs_found: int = 0
    new_jobs_found: int = 0
    duration_seconds: float = 0.0
