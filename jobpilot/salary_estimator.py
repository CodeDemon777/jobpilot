"""AI Salary Estimator for JobPilot."""

import json
from typing import Optional
from jobpilot import database as db
from jobpilot.config import DB_PATH


# Salary data by role, experience level, and location type
SALARY_DATA = {
    "software engineer": {
        "entry": {"min": 60000, "max": 90000},
        "mid": {"min": 90000, "max": 130000},
        "senior": {"min": 130000, "max": 180000},
        "lead": {"min": 160000, "max": 220000},
    },
    "backend developer": {
        "entry": {"min": 55000, "max": 85000},
        "mid": {"min": 85000, "max": 125000},
        "senior": {"min": 125000, "max": 170000},
        "lead": {"min": 150000, "max": 200000},
    },
    "frontend developer": {
        "entry": {"min": 55000, "max": 85000},
        "mid": {"min": 85000, "max": 120000},
        "senior": {"min": 120000, "max": 160000},
        "lead": {"min": 140000, "max": 190000},
    },
    "full stack developer": {
        "entry": {"min": 60000, "max": 90000},
        "mid": {"min": 90000, "max": 130000},
        "senior": {"min": 130000, "max": 175000},
        "lead": {"min": 155000, "max": 210000},
    },
    "devops engineer": {
        "entry": {"min": 65000, "max": 95000},
        "mid": {"min": 95000, "max": 135000},
        "senior": {"min": 135000, "max": 180000},
        "lead": {"min": 165000, "max": 220000},
    },
    "data engineer": {
        "entry": {"min": 70000, "max": 100000},
        "mid": {"min": 100000, "max": 140000},
        "senior": {"min": 140000, "max": 190000},
        "lead": {"min": 170000, "max": 230000},
    },
    "ml engineer": {
        "entry": {"min": 75000, "max": 110000},
        "mid": {"min": 110000, "max": 155000},
        "senior": {"min": 155000, "max": 210000},
        "lead": {"min": 185000, "max": 250000},
    },
    "cloud engineer": {
        "entry": {"min": 65000, "max": 95000},
        "mid": {"min": 95000, "max": 135000},
        "senior": {"min": 135000, "max": 180000},
        "lead": {"min": 165000, "max": 220000},
    },
    "security engineer": {
        "entry": {"min": 70000, "max": 100000},
        "mid": {"min": 100000, "max": 145000},
        "senior": {"min": 145000, "max": 200000},
        "lead": {"min": 175000, "max": 240000},
    },
    "mobile developer": {
        "entry": {"min": 60000, "max": 90000},
        "mid": {"min": 90000, "max": 130000},
        "senior": {"min": 130000, "max": 175000},
        "lead": {"min": 160000, "max": 215000},
    },
}

# Location multipliers
LOCATION_MULTIPLIERS = {
    "san francisco": 1.4,
    "new york": 1.3,
    "seattle": 1.25,
    "boston": 1.2,
    "austin": 1.1,
    "denver": 1.1,
    "chicago": 1.15,
    "los angeles": 1.2,
    "remote": 1.0,
    "onsite": 1.0,
    "hybrid": 1.05,
}

# Company size multipliers
COMPANY_SIZE_MULTIPLIERS = {
    "startup": 0.9,
    "small": 0.95,
    "medium": 1.0,
    "large": 1.1,
    "enterprise": 1.15,
}


class SalaryEstimator:
    """Estimate salary based on skills, experience, location, and company."""

    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH

    def estimate(self, role: str, company: str = "", location: str = "",
                 experience_level: str = "", skills: list = None) -> dict:
        """
        Estimate salary for a given role and profile.

        Returns dict with:
            - role, company, location
            - estimated_min, estimated_max
            - currency
            - confidence_score
            - factors_affecting_salary
            - tips_to_increase
        """
        if skills is None:
            skills = []

        # Get base salary for role
        role_data = self._get_role_data(role)
        base_min = role_data["min"]
        base_max = role_data["max"]

        # Apply location multiplier
        location_mult = self._get_location_multiplier(location)
        adjusted_min = int(base_min * location_mult)
        adjusted_max = int(base_max * location_mult)

        # Apply skill premium
        skill_premium = self._calculate_skill_premium(skills)
        adjusted_min += skill_premium
        adjusted_max += skill_premium

        # Calculate confidence
        confidence = self._calculate_confidence(role, company, location, experience_level)

        # Generate factors
        factors = self._analyze_factors(role, company, location, experience_level, skills)

        # Generate tips
        tips = self._generate_tips(role, skills, experience_level)

        return {
            "role": role,
            "company": company,
            "location": location,
            "experience_level": experience_level,
            "estimated_min": adjusted_min,
            "estimated_max": adjusted_max,
            "currency": "USD",
            "confidence_score": confidence,
            "factors": factors,
            "tips": tips,
            "skill_premium": skill_premium,
            "location_multiplier": location_mult,
        }

    def _get_role_data(self, role: str) -> dict:
        """Get salary data for a role."""
        role_lower = role.lower()
        for key, data in SALARY_DATA.items():
            if key in role_lower or role_lower in key:
                return data["mid"]  # Default to mid-level

        # Default salary range
        return {"min": 70000, "max": 120000}

    def _get_location_multiplier(self, location: str) -> float:
        """Get salary multiplier for a location."""
        if not location:
            return 1.0

        location_lower = location.lower()
        for key, mult in LOCATION_MULTIPLIERS.items():
            if key in location_lower:
                return mult

        return 1.0

    def _calculate_skill_premium(self, skills: list) -> int:
        """Calculate salary premium based on skills."""
        premium_skills = {
            "python": 3000,
            "react": 2000,
            "aws": 5000,
            "kubernetes": 5000,
            "docker": 3000,
            "machine learning": 8000,
            "deep learning": 8000,
            "tensorflow": 5000,
            "pytorch": 5000,
            "terraform": 4000,
            "kafka": 4000,
            "spark": 4000,
            "rust": 5000,
            "go": 4000,
        }

        premium = 0
        for skill in skills:
            skill_lower = skill.lower()
            if skill_lower in premium_skills:
                premium += premium_skills[skill_lower]

        return min(premium, 30000)  # Cap at $30k premium

    def _calculate_confidence(self, role: str, company: str,
                              location: str, experience_level: str) -> float:
        """Calculate confidence score for the estimate."""
        confidence = 0.5  # Base confidence

        # Increase confidence if we have good data
        role_lower = role.lower()
        if any(key in role_lower for key in SALARY_DATA.keys()):
            confidence += 0.2

        if location:
            confidence += 0.1

        if experience_level:
            confidence += 0.1

        if company:
            confidence += 0.1

        return min(confidence, 0.95)

    def _analyze_factors(self, role: str, company: str, location: str,
                         experience_level: str, skills: list) -> list:
        """Analyze factors affecting salary."""
        factors = []

        if experience_level:
            factors.append(f"Experience level ({experience_level}) significantly impacts salary")

        if location:
            factors.append(f"Location ({location}) affects cost of living adjustments")

        premium_skills = ["aws", "kubernetes", "machine learning", "rust", "go"]
        matched_premium = [s for s in skills if s.lower() in premium_skills]
        if matched_premium:
            factors.append(f"Premium skills ({', '.join(matched_premium)}) increase salary")

        if company:
            factors.append(f"Company ({company}) size and industry affect compensation")

        return factors

    def _generate_tips(self, role: str, skills: list, experience_level: str) -> list:
        """Generate tips to increase salary."""
        tips = [
            "Negotiate based on market data and your unique value",
            "Consider total compensation (salary, bonus, equity, benefits)",
            "Get competing offers to strengthen your negotiating position",
            "Highlight specialized skills that are in high demand",
        ]

        if "machine learning" in str(skills).lower() or "ai" in str(skills).lower():
            tips.append("AI/ML skills command premium salaries - emphasize these")

        if "aws" in str(skills).lower() or "cloud" in str(skills).lower():
            tips.append("Cloud certifications can increase salary by 10-15%")

        return tips
