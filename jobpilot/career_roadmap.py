"""AI Career Roadmap Generator for JobPilot."""

import json
from typing import Optional
from jobpilot import database as db
from jobpilot.config import DB_PATH
from jobpilot.models import UserProfile, JobListing
from jobpilot.profile import load_profile
from jobpilot.matcher import compute_match


class CareerRoadmapGenerator:
    """Generate personalized career roadmaps."""

    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH

    def generate_roadmap(self, goal_role: str, goal_company: str = "",
                         user_id: int = 1) -> dict:
        """
        Generate a personalized career roadmap.

        Returns dict with:
            - goal_role, goal_company
            - current_skills, missing_skills
            - roadmap_data (weekly plan)
            - estimated_duration_weeks
            - recommended_resources
        """
        profile = load_profile()

        # Analyze current skills vs goal requirements
        goal_skills = self._get_skills_for_role(goal_role)
        current_skills = set(profile.all_skills)
        missing_skills = set(goal_skills) - current_skills

        # Generate roadmap data
        roadmap_data = self._generate_roadmap_data(
            goal_role, goal_company, list(missing_skills), profile
        )

        # Calculate estimated duration
        estimated_weeks = sum(item.get("duration_weeks", 1) for item in roadmap_data)

        # Get recommended resources
        resources = self._get_recommended_resources(list(missing_skills))

        return {
            "goal_role": goal_role,
            "goal_company": goal_company,
            "current_skills": list(current_skills),
            "missing_skills": list(missing_skills),
            "roadmap_data": roadmap_data,
            "estimated_duration_weeks": estimated_weeks,
            "recommended_resources": resources,
            "match_analysis": self._analyze_goal_match(goal_role, goal_company, profile),
        }

    def _get_skills_for_role(self, role: str) -> list[str]:
        """Get skills required for a specific role."""
        role_skills_map = {
            "backend": ["python", "node.js", "sql", "postgresql", "redis", "docker", "kubernetes", "rest api", "graphql", "git"],
            "frontend": ["javascript", "react", "html", "css", "typescript", "vue", "angular", "tailwind", "redux", "webpack"],
            "full stack": ["javascript", "react", "node.js", "python", "sql", "docker", "rest api", "git", "html", "css"],
            "devops": ["docker", "kubernetes", "terraform", "aws", "ci/cd", "linux", "ansible", "jenkins", "python", "git"],
            "data engineer": ["python", "sql", "spark", "airflow", "kafka", "aws", "docker", "etl", "hadoop", "dbt"],
            "ml engineer": ["python", "pytorch", "tensorflow", "sql", "docker", "kubernetes", "aws", "scikit-learn", "pandas", "numpy"],
            "software engineer": ["python", "java", "git", "sql", "docker", "rest api", "agile", "ci/cd", "linux", "javascript"],
            "cloud engineer": ["aws", "gcp", "azure", "terraform", "docker", "kubernetes", "python", "linux", "networking", "security"],
            "security engineer": ["python", "linux", "networking", "security", "owasp", "penetration testing", "cryptography", "siem"],
            "mobile developer": ["swift", "kotlin", "react native", "flutter", "dart", "ios", "android", "firebase"],
        }

        role_lower = role.lower()
        for key, skills in role_skills_map.items():
            if key in role_lower:
                return skills

        # Default skills for any technical role
        return ["python", "git", "sql", "docker", "rest api", "linux"]

    def _generate_roadmap_data(self, goal_role: str, goal_company: str,
                               missing_skills: list, profile: UserProfile) -> list:
        """Generate weekly roadmap data."""
        roadmap = []

        # Group skills by difficulty/learning time
        beginner_skills = [s for s in missing_skills if s in ["git", "html", "css", "sql", "linux"]]
        intermediate_skills = [s for s in missing_skills if s in ["python", "javascript", "react", "docker", "node.js", "aws"]]
        advanced_skills = [s for s in missing_skills if s in ["kubernetes", "terraform", "spark", "kafka", "pytorch"]]

        week = 1

        # Phase 1: Fundamentals
        if beginner_skills:
            roadmap.append({
                "phase": "Fundamentals",
                "week_start": week,
                "week_end": week + len(beginner_skills) - 1,
                "duration_weeks": len(beginner_skills),
                "skills": beginner_skills,
                "tasks": [f"Learn {skill}" for skill in beginner_skills],
                "milestone": "Complete fundamental skills",
            })
            week += len(beginner_skills)

        # Phase 2: Core Skills
        if intermediate_skills:
            roadmap.append({
                "phase": "Core Skills",
                "week_start": week,
                "week_end": week + len(intermediate_skills) - 1,
                "duration_weeks": len(intermediate_skills),
                "skills": intermediate_skills,
                "tasks": [f"Master {skill}" for skill in intermediate_skills],
                "milestone": "Build projects with core technologies",
            })
            week += len(intermediate_skills)

        # Phase 3: Advanced Topics
        if advanced_skills:
            roadmap.append({
                "phase": "Advanced Topics",
                "week_start": week,
                "week_end": week + len(advanced_skills) - 1,
                "duration_weeks": len(advanced_skills),
                "skills": advanced_skills,
                "tasks": [f"Deep dive into {skill}" for skill in advanced_skills],
                "milestone": "Master advanced concepts",
            })
            week += len(advanced_skills)

        # Phase 4: Projects & Portfolio
        roadmap.append({
            "phase": "Projects & Portfolio",
            "week_start": week,
            "week_end": week + 2,
            "duration_weeks": 2,
            "skills": [],
            "tasks": ["Build 2-3 portfolio projects", "Update GitHub", "Write project documentation"],
            "milestone": "Complete portfolio",
        })
        week += 2

        # Phase 5: Interview Prep
        roadmap.append({
            "phase": "Interview Preparation",
            "week_start": week,
            "week_end": week + 2,
            "duration_weeks": 2,
            "skills": [],
            "tasks": ["Practice coding challenges", "Mock interviews", "System design practice"],
            "milestone": "Ready for interviews",
        })
        week += 2

        # Phase 6: Job Applications
        roadmap.append({
            "phase": "Job Applications",
            "week_start": week,
            "week_end": week + 4,
            "duration_weeks": 4,
            "skills": [],
            "tasks": ["Apply to target companies", "Network with recruiters", "Follow up on applications"],
            "milestone": "Land interview at " + (goal_company or "target company"),
        })

        return roadmap

    def _get_recommended_resources(self, missing_skills: list) -> list[dict]:
        """Get recommended learning resources for missing skills."""
        resources_map = {
            "python": {"platform": "freeCodeCamp", "course": "Python for Everybody", "url": "https://www.freecodecamp.org/learn"},
            "javascript": {"platform": "freeCodeCamp", "course": "JavaScript Algorithms", "url": "https://www.freecodecamp.org/learn"},
            "react": {"platform": "Coursera", "course": "React - The Complete Guide", "url": "https://www.coursera.org"},
            "docker": {"platform": "Udemy", "course": "Docker & Kubernetes: The Practical Guide", "url": "https://www.udemy.com"},
            "kubernetes": {"platform": "Coursera", "course": "Google Cloud: Kubernetes", "url": "https://www.coursera.org"},
            "aws": {"platform": "AWS", "course": "AWS Cloud Practitioner", "url": "https://aws.amazon.com/certification"},
            "sql": {"platform": "freeCodeCamp", "course": "SQL for Data Science", "url": "https://www.freecodecamp.org/learn"},
            "git": {"platform": "GitHub", "course": "Git & GitHub Crash Course", "url": "https://docs.github.com"},
            "terraform": {"platform": "HashiCorp", "course": "Terraform Associate", "url": "https://www.terraform.io/learn"},
            "pytorch": {"platform": "Coursera", "course": "PyTorch for Deep Learning", "url": "https://www.coursera.org"},
        }

        resources = []
        for skill in missing_skills:
            if skill in resources_map:
                resources.append({
                    "skill": skill,
                    **resources_map[skill]
                })
            else:
                resources.append({
                    "skill": skill,
                    "platform": "Various",
                    "course": f"Learn {skill}",
                    "url": "https://www.google.com/search?q=learn+" + skill.replace(" ", "+"),
                })

        return resources

    def _analyze_goal_match(self, goal_role: str, goal_company: str,
                            profile: UserProfile) -> dict:
        """Analyze how well the user's profile matches the goal."""
        # Create a mock job listing for matching
        goal_skills = self._get_skills_for_role(goal_role)
        mock_job = JobListing(
            company=goal_company or "Target Company",
            title=goal_role,
            required_skills=goal_skills,
            experience_years=3,
        )

        match_result = compute_match(profile, mock_job)

        return {
            "overall_score": match_result.overall_score,
            "skills_score": match_result.skills_score,
            "strengths": match_result.strengths,
            "missing_skills": match_result.missing_skills,
        }
