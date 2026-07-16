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
