"""LinkedIn Profile Analyzer for JobPilot."""

import re
from jobpilot.resume_analyzer import _extract_skills, SKILL_DATABASE


def analyze_linkedin_profile(
    headline: str = "",
    about: str = "",
    skills: str = "",
    experience: str = "",
) -> dict:
    """
    Analyze LinkedIn profile content.

    Returns dict with:
        - suggestions: List of optimization suggestions
        - missing_keywords: Keywords missing from profile
        - visibility_score: Score for recruiter visibility (0-100)
        - strength_score: Score for profile strength (0-100)
        - headline_analysis: Analysis of headline
        - about_analysis: Analysis of about section
        - skills_analysis: Analysis of skills section
    """
    suggestions = []
    missing_keywords = []

    # Analyze headline
    headline_score, headline_suggestions = _analyze_headline(headline)
    suggestions.extend(headline_suggestions)

    # Analyze about section
    about_score, about_suggestions = _analyze_about(about)
    suggestions.extend(about_suggestions)

    # Analyze skills
    all_skills_text = f"{headline} {about} {skills}"
    detected_skills = _extract_skills(all_skills_text)
    skills_score, skills_suggestions = _analyze_skills(skills, detected_skills)
    suggestions.extend(skills_suggestions)

    # Analyze experience
    exp_score, exp_suggestions = _analyze_experience(experience)
    suggestions.extend(exp_suggestions)

    # Find missing keywords
    missing_keywords = _find_missing_keywords(all_skills_text)

    # Calculate scores
    visibility_score = _calculate_visibility_score(headline, about, skills, experience)
    strength_score = _calculate_strength_score(
        headline_score, about_score, skills_score, exp_score
    )

    return {
        "suggestions": suggestions,
        "missing_keywords": missing_keywords,
        "visibility_score": round(visibility_score, 1),
        "strength_score": round(strength_score, 1),
        "detected_skills": detected_skills,
        "headline_analysis": {
            "length": len(headline),
            "score": headline_score,
            "has_role": any(
                w in headline.lower()
                for w in ["engineer", "developer", "manager", "analyst", "designer"]
            ),
            "has_company": "|" in headline or "at" in headline.lower(),
        },
        "about_analysis": {
            "length": len(about),
            "score": about_score,
            "has_cta": any(
                w in about.lower()
                for w in ["contact", "reach out", "connect", "message"]
            ),
            "word_count": len(about.split()),
        },
        "skills_analysis": {
            "detected_count": len(detected_skills),
            "score": skills_score,
        },
    }


def _analyze_headline(headline: str) -> tuple[float, list[str]]:
    """Analyze LinkedIn headline."""
    score = 0
    suggestions = []

    if not headline:
        return 0, ["Add a headline to improve visibility"]

    length = len(headline)
    if length < 20:
        suggestions.append(
            "Your headline is too short. Include your role and key skills."
        )
    elif length > 220:
        suggestions.append("Your headline is too long. Keep it under 220 characters.")
    else:
        score += 30

    # Check for keywords
    keywords = [
        "engineer",
        "developer",
        "manager",
        "analyst",
        "designer",
        "architect",
        "lead",
    ]
    if any(kw in headline.lower() for kw in keywords):
        score += 20

    # Check for skills
    skills = _extract_skills(headline)
    if skills:
        score += 20
    else:
        suggestions.append(
            "Add relevant skills to your headline for better searchability"
        )

    # Check for value proposition
    value_words = [
        "helping",
        "building",
        "creating",
        "leading",
        "driving",
        "delivering",
    ]
    if any(w in headline.lower() for w in value_words):
        score += 15

    # Check for separators
    if "|" in headline or "•" in headline or "-" in headline:
        score += 15

    return min(score, 100), suggestions


def _analyze_about(about: str) -> tuple[float, list[str]]:
    """Analyze LinkedIn about section."""
    score = 0
    suggestions = []

    if not about:
        return 0, ["Add an about section to tell your professional story"]

    word_count = len(about.split())
    if word_count < 50:
        suggestions.append("Your about section is too short. Aim for 100-300 words.")
    elif word_count > 500:
        suggestions.append(
            "Your about section is quite long. Consider trimming to 200-400 words."
        )
    else:
        score += 30

    # Check for first person
    first_person = ["I ", "I've", "I'm", "My "]
    if any(fp in about for fp in first_person):
        score += 15
    else:
        suggestions.append(
            "Write in first person to make your about section more personal"
        )

    # Check for quantifiable achievements
    numbers = re.findall(
        r"\d+[%x+]?\s*(?:million|billion|k|users|customers|revenue|team|projects?)",
        about.lower(),
    )
    if numbers:
        score += 20
    else:
        suggestions.append(
            "Add quantifiable achievements (numbers, percentages, metrics)"
        )

    # Check for call to action
    cta_words = ["contact", "reach out", "connect", "message", "email", "linkedin"]
    if any(w in about.lower() for w in cta_words):
        score += 15
    else:
        suggestions.append(
            "Add a call-to-action at the end (e.g., 'Feel free to reach out')"
        )

    # Check for keywords
    skills = _extract_skills(about)
    if len(skills) >= 3:
        score += 20
    else:
        suggestions.append(
            "Include more relevant skills and keywords for better searchability"
        )

    return min(score, 100), suggestions


def _analyze_skills(
    skills_text: str, detected_skills: list[str]
) -> tuple[float, list[str]]:
    """Analyze LinkedIn skills section."""
    score = 0
    suggestions = []

    if not skills_text:
        return 0, ["Add skills to your profile for better matching"]

    skill_count = len(detected_skills)
    if skill_count < 5:
        suggestions.append("Add more skills. Aim for at least 10-15 relevant skills.")
    elif skill_count > 30:
        suggestions.append(
            "You have many skills listed. Focus on the most relevant ones."
        )
    else:
        score += 40

    # Check for endorsements hint
    if "(" in skills_text and ")" in skills_text:
        score += 10  # Likely has endorsement counts

    # Check for skill relevance
    high_demand_skills = [
        "python",
        "javascript",
        "react",
        "aws",
        "docker",
        "kubernetes",
        "typescript",
        "node.js",
    ]
    matched_demand = [s for s in detected_skills if s in high_demand_skills]
    if matched_demand:
        score += 30
    else:
        suggestions.append("Consider adding in-demand skills to your profile")

    # Check for endorsements encouragement
    if skill_count > 0 and score < 60:
        suggestions.append("Ask colleagues to endorse your top skills")

    return min(score, 100), suggestions


def _analyze_experience(experience: str) -> tuple[float, list[str]]:
    """Analyze LinkedIn experience section."""
    score = 0
    suggestions = []

    if not experience:
        return 0, ["Add work experience to strengthen your profile"]

    lines = [l.strip() for l in experience.split("\n") if l.strip()]
    if len(lines) < 2:
        suggestions.append("Add more detail to your experience descriptions")
    else:
        score += 30

    # Check for quantifiable results
    numbers = re.findall(
        r"\d+[%x+]?\s*(?:million|billion|k|users|customers|revenue|team|projects?|percent)",
        experience.lower(),
    )
    if numbers:
        score += 30
    else:
        suggestions.append("Add metrics and numbers to your experience descriptions")

    # Check for action verbs
    action_verbs = [
        "led",
        "built",
        "developed",
        "implemented",
        "designed",
        "managed",
        "created",
        "improved",
        "increased",
        "reduced",
        "launched",
    ]
    verb_count = sum(1 for v in action_verbs if v in experience.lower())
    if verb_count >= 3:
        score += 20
    else:
        suggestions.append("Use more action verbs to describe your accomplishments")

    # Check for technologies
    tech_mentions = _extract_skills(experience)
    if tech_mentions:
        score += 20
    else:
        suggestions.append("Mention specific technologies you used in each role")

    return min(score, 100), suggestions


def _find_missing_keywords(text: str) -> list[str]:
    """Find high-demand keywords missing from the profile."""
    high_demand = [
        "python",
        "javascript",
        "react",
        "node.js",
        "aws",
        "docker",
        "kubernetes",
        "typescript",
        "git",
        "ci/cd",
        "agile",
        "sql",
        "rest api",
        "graphql",
        "machine learning",
        "data analysis",
        "cloud",
        "microservices",
        "api",
        "linux",
        "postgresql",
        "mongodb",
        "redis",
        "terraform",
    ]

    text_lower = text.lower()
    missing = [kw for kw in high_demand if kw not in text_lower]
    return missing[:10]  # Top 10 missing


def _calculate_visibility_score(
    headline: str, about: str, skills: str, experience: str
) -> float:
    """Calculate recruiter visibility score (0-100)."""
    score = 0

    # Headline completeness
    if headline:
        score += 20
        if len(headline) > 30:
            score += 5

    # About section
    if about:
        score += 15
        if len(about.split()) > 50:
            score += 5

    # Skills
    if skills:
        score += 15
        skill_count = len(_extract_skills(skills))
        if skill_count >= 5:
            score += 10

    # Experience
    if experience:
        score += 15
        if len(experience.split("\n")) >= 3:
            score += 5

    # Keywords for search
    all_text = f"{headline} {about} {skills} {experience}"
    keywords = _extract_skills(all_text)
    if len(keywords) >= 5:
        score += 10

    return min(score, 100)


def _calculate_strength_score(
    headline: float, about: float, skills: float, experience: float
) -> float:
    """Calculate overall profile strength score (0-100)."""
    weights = {"headline": 0.2, "about": 0.25, "skills": 0.25, "experience": 0.3}
    scores = {
        "headline": headline,
        "about": about,
        "skills": skills,
        "experience": experience,
    }

    total = sum(scores[k] * weights[k] for k in scores)
    return min(total, 100)
