"""Skill Gap Analysis for JobPilot."""

from jobpilot.resume_analyzer import _extract_skills, SKILL_DATABASE


def analyze_skill_gap(
    resume_skills: list[str] = None,
    job_required_skills: list[str] = None,
    job_preferred_skills: list[str] = None,
    resume_text: str = "",
    job_description: str = "",
) -> dict:
    """
    Analyze the gap between resume skills and job requirements.

    Returns dict with:
        - matched_skills: Skills found in both resume and job
        - missing_skills: Skills required by job but not in resume
        - extra_skills: Skills in resume but not required
        - match_percentage: Percentage of required skills matched
        - learning_areas: Grouped missing skills by category
        - priority_ranking: Missing skills ranked by importance
    """
    if resume_skills is None:
        resume_skills = []
    if job_required_skills is None:
        job_required_skills = []
    if job_preferred_skills is None:
        job_preferred_skills = []

    # Extract skills from text if provided
    if resume_text:
        resume_skills = list(set(resume_skills + _extract_skills(resume_text)))
    if job_description:
        job_required_skills = list(
            set(job_required_skills + _extract_skills(job_description))
        )

    # Normalize to lowercase
    resume_set = {s.lower().strip() for s in resume_skills}
    required_set = {s.lower().strip() for s in job_required_skills}
    preferred_set = {s.lower().strip() for s in job_preferred_skills}
    all_job_skills = required_set | preferred_set

    # Find matches (exact and alias)
    matched = set()
    missing = set()
    alias_map = _build_alias_map()

    for skill in required_set:
        found = False
        if skill in resume_set:
            found = True
        else:
            # Check aliases
            for resume_skill in resume_set:
                if alias_map.get(resume_skill) == alias_map.get(skill):
                    found = True
                    break
        if found:
            matched.add(skill)
        else:
            missing.add(skill)

    # Extra skills (in resume but not in job)
    extra = resume_set - all_job_skills

    # Match percentage
    total_required = len(required_set)
    match_pct = (len(matched) / total_required * 100) if total_required > 0 else 100.0

    # Learning areas (group by category)
    learning_areas = _group_skills_by_category(list(missing))

    # Priority ranking (required skills first, then preferred)
    priority_ranking = list(missing)  # All missing are priority
    for skill in preferred_set:
        if skill not in resume_set and skill not in missing:
            priority_ranking.append(skill)

    return {
        "matched_skills": sorted(matched),
        "missing_skills": sorted(missing),
        "extra_skills": sorted(extra),
        "match_percentage": round(match_pct, 1),
        "learning_areas": learning_areas,
        "priority_ranking": priority_ranking[:10],  # Top 10
        "total_required": total_required,
        "total_matched": len(matched),
        "total_missing": len(missing),
    }


def _build_alias_map() -> dict[str, str]:
    """Build a mapping from skill aliases to canonical names."""
    alias_map = {}
    for canonical, aliases in SKILL_DATABASE.items():
        alias_map[canonical.lower()] = canonical.lower()
        for alias in aliases:
            alias_map[alias.lower()] = canonical.lower()
    return alias_map


def _group_skills_by_category(skills: list[str]) -> list[dict]:
    """Group skills by category for learning recommendations."""
    categories = {
        "Programming Languages": [
            "python",
            "javascript",
            "typescript",
            "java",
            "go",
            "rust",
            "c++",
            "c#",
            "ruby",
            "php",
            "swift",
            "kotlin",
            "scala",
            "r",
            "matlab",
        ],
        "Frontend": [
            "react",
            "vue",
            "angular",
            "svelte",
            "next.js",
            "html",
            "css",
            "sass",
            "tailwind",
            "bootstrap",
        ],
        "Backend": [
            "node.js",
            "django",
            "fastapi",
            "flask",
            "express",
            "spring",
            "rails",
            "asp.net",
            "graphql",
            "rest api",
        ],
        "DevOps": [
            "docker",
            "kubernetes",
            "terraform",
            "ansible",
            "jenkins",
            "github actions",
            "ci/cd",
            "nginx",
            "linux",
        ],
        "Cloud": ["aws", "gcp", "azure", "firebase", "heroku", "digitalocean"],
        "Databases": [
            "postgresql",
            "mysql",
            "mongodb",
            "redis",
            "elasticsearch",
            "dynamodb",
            "sqlite",
            "cassandra",
            "neo4j",
        ],
        "Data & ML": [
            "machine learning",
            "deep learning",
            "nlp",
            "computer vision",
            "tensorflow",
            "pytorch",
            "pandas",
            "numpy",
            "spark",
            "hadoop",
        ],
        "Tools": ["git", "github", "gitlab", "jira", "figma", "postman", "vscode"],
    }

    result = []
    for category, category_skills in categories.items():
        matched_in_category = [s for s in skills if s in category_skills]
        if matched_in_category:
            result.append(
                {
                    "category": category,
                    "skills": matched_in_category,
                    "count": len(matched_in_category),
                }
            )

    # Add uncategorized skills
    categorized = set()
    for cat in categories.values():
        categorized.update(cat)
    uncategorized = [s for s in skills if s not in categorized]
    if uncategorized:
        result.append(
            {
                "category": "Other",
                "skills": uncategorized,
                "count": len(uncategorized),
            }
        )

    return result
