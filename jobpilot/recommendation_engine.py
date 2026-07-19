"""Personalized Recommendation Engine for JobPilot."""

import json
from collections import Counter
from typing import Optional

from jobpilot import database as db
from jobpilot.config import DB_PATH
from jobpilot.models import UserProfile, JobListing
from jobpilot.profile import load_profile
from jobpilot.matcher import compute_match


class RecommendationEngine:
    """Generates personalized job recommendations."""

    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH

    def _get_profile(self) -> UserProfile:
        """Get user profile."""
        return load_profile()

    def get_recommendations(self) -> dict:
        """
        Generate comprehensive personalized recommendations.

        Returns:
            dict with recommended_jobs, recommended_skills, recommended_companies,
            recommended_certifications
        """
        profile = load_profile()

        recommended_jobs = self._recommend_jobs(profile)
        recommended_skills = self._recommend_skills(profile)
        recommended_companies = self._recommend_companies(profile)
        recommended_certifications = self._recommend_certifications(profile)

        return {
            "recommended_jobs": recommended_jobs,
            "recommended_skills": recommended_skills,
            "recommended_companies": recommended_companies,
            "recommended_certifications": recommended_certifications,
        }

    def _recommend_jobs(self, profile: UserProfile, limit: int = 10) -> list[dict]:
        """Recommend jobs based on profile match scores."""
        jobs = db.get_all_jobs(self.db_path)
        if not jobs:
            return []

        scored_jobs = []
        for job in jobs:
            if not job.is_active:
                continue
            match_result = compute_match(profile, job)
            if match_result.overall_score >= 0.3:
                scored_jobs.append(
                    {
                        "job": job.to_dict(),
                        "match_score": match_result.overall_score,
                        "skills_score": match_result.skills_score,
                        "strengths": match_result.strengths,
                        "missing_skills": match_result.missing_skills,
                    }
                )

        scored_jobs.sort(key=lambda x: x["match_score"], reverse=True)
        return scored_jobs[:limit]

    def _recommend_skills(self, profile: UserProfile, limit: int = 10) -> list[dict]:
        """Recommend skills to learn based on job market demand and skill gaps."""
        user_skills = set(profile.all_skills)

        # Get skills from job listings
        jobs = db.get_all_jobs(self.db_path)
        job_skill_counts: Counter = Counter()
        for job in jobs:
            if not job.is_active:
                continue
            for skill in job.all_required_skills:
                job_skill_counts[skill] += 1
            for skill in job.all_preferred_skills:
                job_skill_counts[skill] += 1

        # Find skills in demand that user doesn't have
        recommendations = []
        for skill, count in job_skill_counts.most_common(50):
            if skill not in user_skills:
                recommendations.append(
                    {
                        "skill": skill,
                        "demand_count": count,
                        "priority": (
                            "high" if count >= 5 else "medium" if count >= 2 else "low"
                        ),
                    }
                )

        # Sort by demand
        recommendations.sort(key=lambda x: x["demand_count"], reverse=True)
        return recommendations[:limit]

    def _recommend_companies(self, profile: UserProfile, limit: int = 10) -> list[dict]:
        """Recommend companies based on job availability and match potential."""
        companies = db.get_companies(self.db_path)
        if not companies:
            return []

        recommendations = []
        for company in companies:
            # Find jobs from this company
            jobs = db.search_jobs(query="", source="", db_path=self.db_path)
            company_jobs = [
                j for j in jobs if j.company == company.name and j.is_active
            ]

            if not company_jobs:
                continue

            # Compute average match score
            total_score = 0
            for job in company_jobs:
                match = compute_match(profile, job)
                total_score += match.overall_score
            avg_score = total_score / len(company_jobs) if company_jobs else 0

            recommendations.append(
                {
                    "company": company.name,
                    "job_count": len(company_jobs),
                    "avg_match_score": round(avg_score, 3),
                    "industry": company.industry,
                    "locations": list(
                        set(j.location for j in company_jobs if j.location)
                    ),
                }
            )

        recommendations.sort(
            key=lambda x: (x["avg_match_score"], x["job_count"]), reverse=True
        )
        return recommendations[:limit]

    def _recommend_certifications(
        self, profile: UserProfile, limit: int = 5
    ) -> list[dict]:
        """Recommend certifications based on skill gaps and job requirements."""
        user_skills = set(profile.all_skills)

        # Get skills from job listings
        jobs = db.get_all_jobs(self.db_path)
        job_skill_counts: Counter = Counter()
        for job in jobs:
            if not job.is_active:
                continue
            for skill in job.all_required_skills:
                job_skill_counts[skill] += 1

        # Map skills to relevant certifications
        skill_cert_map = {
            "aws": {
                "name": "AWS Solutions Architect",
                "provider": "Amazon",
                "relevance": "high",
            },
            "gcp": {
                "name": "Google Cloud Professional",
                "provider": "Google",
                "relevance": "high",
            },
            "azure": {
                "name": "Azure Fundamentals",
                "provider": "Microsoft",
                "relevance": "high",
            },
            "kubernetes": {
                "name": "Certified Kubernetes Administrator",
                "provider": "CNCF",
                "relevance": "high",
            },
            "docker": {
                "name": "Docker Certified Associate",
                "provider": "Docker",
                "relevance": "medium",
            },
            "terraform": {
                "name": "HashiCorp Terraform Associate",
                "provider": "HashiCorp",
                "relevance": "high",
            },
            "python": {
                "name": "Python Professional Certification",
                "provider": "PCEP/PCAP",
                "relevance": "medium",
            },
            "java": {
                "name": "Oracle Certified Professional",
                "provider": "Oracle",
                "relevance": "medium",
            },
            "react": {
                "name": "Meta Front-End Developer",
                "provider": "Meta",
                "relevance": "medium",
            },
            "sql": {
                "name": "Oracle MySQL Certification",
                "provider": "Oracle",
                "relevance": "medium",
            },
            "machine learning": {
                "name": "Google ML Engineer",
                "provider": "Google",
                "relevance": "high",
            },
            "security": {
                "name": "CompTIA Security+",
                "provider": "CompTIA",
                "relevance": "high",
            },
        }

        recommendations = []
        seen = set()

        for skill, count in job_skill_counts.most_common(20):
            if skill in user_skills:
                continue
            if skill in skill_cert_map and skill_cert_map[skill]["name"] not in seen:
                cert = skill_cert_map[skill]
                recommendations.append(
                    {
                        "certification": cert["name"],
                        "provider": cert["provider"],
                        "related_skill": skill,
                        "demand_count": count,
                        "relevance": cert["relevance"],
                    }
                )
                seen.add(cert["name"])

        return recommendations[:limit]
