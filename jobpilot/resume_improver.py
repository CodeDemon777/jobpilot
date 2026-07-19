"""AI Resume Improvement Suggestions for JobPilot."""

from jobpilot.resume_analyzer import (
    analyze_resume, _extract_skills, _detect_sections, _compute_ats_score,
    _extract_contact, _estimate_experience_years, _generate_suggestions,
    SKILL_DATABASE,
)


def generate_improvement_report(
    resume_text: str,
    target_role: str = "",
) -> dict:
    """
    Generate detailed resume improvement suggestions.

    Returns dict with:
        - strengths: What's working well
        - weaknesses: Areas that need improvement
        - improvements: Specific actionable suggestions
        - recommended_keywords: Keywords to add
        - score_before: Current scores
        - score_after: Projected scores after improvements
        - overall_grade: A-F grade
    """
    # Analyze the resume
    analysis = analyze_resume(resume_text, target_role)

    # Extract detailed information
    sections = _detect_sections(resume_text)
    skills = _extract_skills(resume_text)
    contact = _extract_contact(resume_text)
    experience_years = _estimate_experience_years(resume_text, sections)

    # Generate strengths
    strengths = _identify_strengths(sections, skills, contact, experience_years)

    # Generate weaknesses
    weaknesses = _identify_weaknesses(sections, skills, contact, resume_text)

    # Generate specific improvements
    improvements = _generate_improvements(sections, skills, contact, resume_text, target_role, experience_years)

    # Recommend keywords
    recommended_keywords = _recommend_keywords(skills, target_role, resume_text)

    # Calculate score improvements
    original_scores = {
        "ats": analysis.ats_score,
        "quality": analysis.resume_quality_score,
        "technical": analysis.technical_strength_score,
        "hiring": analysis.hiring_readiness_score,
    }

    # Project scores after improvements
    projected_scores = _project_scores(original_scores, improvements, skills)

    # Calculate overall grade
    overall_grade = _calculate_grade(original_scores["ats"])

    return {
        "strengths": strengths,
        "weaknesses": weaknesses,
        "improvements": improvements,
        "recommended_keywords": recommended_keywords,
        "score_before": original_scores,
        "score_after": projected_scores,
        "overall_grade": overall_grade,
        "resume_stats": {
            "word_count": len(resume_text.split()),
            "line_count": len(resume_text.split("\n")),
            "skills_count": len(skills),
            "sections_found": list(sections.keys()),
            "experience_years": experience_years,
        },
    }


def _identify_strengths(sections: dict, skills: list, contact: dict, experience_years: int) -> list[str]:
    """Identify resume strengths."""
    strengths = []

    # Contact completeness
    contact_fields = ["email", "phone", "linkedin", "github"]
    filled = sum(1 for f in contact_fields if f in contact)
    if filled >= 3:
        strengths.append("Strong contact information with multiple professional links")

    # Section completeness
    important_sections = ["experience", "education", "skills"]
    present = sum(1 for s in important_sections if s in sections)
    if present >= 3:
        strengths.append("Well-structured resume with all essential sections")

    # Skills
    if len(skills) >= 8:
        strengths.append(f"Good skill diversity with {len(skills)} technical skills identified")

    # Experience
    if experience_years >= 3:
        strengths.append(f"Solid experience ({experience_years}+ years)")

    # Projects section
    if "projects" in sections:
        strengths.append("Includes projects section — demonstrates practical experience")

    # Certifications
    if "certifications" in sections:
        strengths.append("Includes certifications — shows commitment to professional development")

    # Summary
    if "summary" in sections:
        strengths.append("Professional summary present — gives context to recruiters")

    return strengths


def _identify_weaknesses(sections: dict, skills: list, contact: dict, resume_text: str) -> list[str]:
    """Identify resume weaknesses."""
    weaknesses = []

    # Missing contact info
    if "email" not in contact:
        weaknesses.append("Missing email address — essential for recruiter contact")
    if "phone" not in contact:
        weaknesses.append("Missing phone number — many recruiters prefer phone screening")
    if "linkedin" not in contact:
        weaknesses.append("Missing LinkedIn profile — expected by most recruiters")

    # Missing sections
    if "summary" not in sections:
        weaknesses.append("No professional summary — first impression is important")
    if "experience" not in sections:
        weaknesses.append("Missing work experience section — critical for most roles")
    if "projects" not in sections:
        weaknesses.append("No projects section — missed opportunity to show practical skills")

    # Skills
    if len(skills) < 5:
        weaknesses.append(f"Only {len(skills)} skills detected — consider adding more relevant technologies")

    # Text quality
    word_count = len(resume_text.split())
    if word_count < 150:
        weaknesses.append("Resume is too short — add more details about experience and skills")
    elif word_count > 800:
        weaknesses.append("Resume is quite long — consider condensing to 1-2 pages")

    # Quantifiable results
    import re
    numbers = re.findall(r'\d+[%x+]?\s*(?:million|billion|k|users|customers|revenue|team|projects?)', resume_text.lower())
    if len(numbers) < 2:
        weaknesses.append("Few quantifiable achievements — add metrics and numbers")

    return weaknesses


def _generate_improvements(sections: dict, skills: list, contact: dict, resume_text: str, target_role: str, experience_years: int = 0) -> list[dict]:
    """Generate specific improvement suggestions."""
    improvements = []

    # ATS improvements
    if "summary" not in sections:
        improvements.append({
            "category": "ats",
            "title": "Add Professional Summary",
            "description": "Add a 2-3 sentence professional summary at the top of your resume. Include your years of experience, key skills, and career objective.",
            "priority": "high",
            "impact": "high",
        })

    if len(skills) < 8:
        improvements.append({
            "category": "skills",
            "title": "Expand Technical Skills",
            "description": "Add more relevant technical skills to your skills section. Include both hard skills (programming languages, frameworks) and soft skills.",
            "priority": "high",
            "impact": "medium",
        })

    # Keyword optimization
    if target_role:
        target_skills = _get_skills_for_role(target_role)
        missing = [s for s in target_skills if s not in skills]
        if missing:
            improvements.append({
                "category": "keywords",
                "title": "Add Role-Specific Keywords",
                "description": f"Add these keywords relevant to {target_role}: {', '.join(missing[:5])}",
                "priority": "high",
                "impact": "high",
            })

    # Formatting
    if not sections.get("summary"):
        improvements.append({
            "category": "formatting",
            "title": "Improve Resume Structure",
            "description": "Ensure consistent section headings and formatting. Use standard section names (Summary, Experience, Education, Skills).",
            "priority": "medium",
            "impact": "medium",
        })

    # Quantifiable results
    import re
    numbers = re.findall(r'\d+', resume_text)
    if len(numbers) < 3:
        improvements.append({
            "category": "content",
            "title": "Add Quantifiable Achievements",
            "description": "Include numbers and metrics in your experience descriptions. For example: 'Increased performance by 40%' or 'Managed team of 5 engineers'.",
            "priority": "high",
            "impact": "high",
        })

    # Action verbs
    action_verbs = ["led", "built", "developed", "implemented", "designed", "managed", "created", "improved", "increased", "reduced", "launched", "optimized"]
    text_lower = text_lower = resume_text.lower()
    verb_count = sum(1 for v in action_verbs if v in text_lower)
    if verb_count < 5:
        improvements.append({
            "category": "content",
            "title": "Use Stronger Action Verbs",
            "description": "Start bullet points with action verbs like 'Led', 'Built', 'Implemented', 'Optimized'. Avoid passive language.",
            "priority": "medium",
            "impact": "medium",
        })

    # Projects section
    if "projects" not in sections and experience_years <= 2:
        improvements.append({
            "category": "content",
            "title": "Add Projects Section",
            "description": "Include a projects section to showcase practical experience, especially if you have limited work experience.",
            "priority": "medium",
            "impact": "medium",
        })

    return improvements


def _recommend_keywords(skills: list, target_role: str, resume_text: str) -> list[str]:
    """Recommend keywords to add to the resume."""
    keywords = []

    # Get role-specific keywords
    if target_role:
        role_keywords = _get_skills_for_role(target_role)
        keywords.extend([k for k in role_keywords if k not in skills])

    # Get high-demand keywords
    high_demand = ["python", "javascript", "react", "aws", "docker", "kubernetes", "typescript", "node.js", "git", "ci/cd", "agile", "sql"]
    text_lower = resume_text.lower()
    keywords.extend([k for k in high_demand if k not in text_lower and k not in keywords])

    # Remove duplicates and limit
    seen = set()
    unique_keywords = []
    for k in keywords:
        if k not in seen:
            seen.add(k)
            unique_keywords.append(k)

    return unique_keywords[:15]


def _get_skills_for_role(role: str) -> list[str]:
    """Get relevant skills for a specific role."""
    role_skills = {
        "backend": ["python", "node.js", "sql", "postgresql", "redis", "docker", "rest api", "graphql"],
        "frontend": ["javascript", "react", "html", "css", "typescript", "vue", "angular", "tailwind"],
        "full stack": ["javascript", "react", "node.js", "python", "sql", "docker", "rest api", "git"],
        "devops": ["docker", "kubernetes", "terraform", "aws", "ci/cd", "linux", "ansible", "jenkins"],
        "data engineer": ["python", "sql", "spark", "airflow", "kafka", "aws", "docker", "etl"],
        "ml engineer": ["python", "pytorch", "tensorflow", "sql", "docker", "kubernetes", "aws", "scikit-learn"],
        "software engineer": ["python", "java", "git", "sql", "docker", "rest api", "agile", "ci/cd"],
    }

    role_lower = role.lower()
    for key, skills in role_skills.items():
        if key in role_lower:
            return skills

    return ["python", "javascript", "git", "sql", "docker", "rest api"]


def _project_scores(original: dict, improvements: list, skills: list) -> dict:
    """Project scores after applying improvements."""
    projected = original.copy()

    # Estimate impact of improvements
    for imp in improvements:
        if imp["priority"] == "high":
            if imp["category"] == "ats":
                projected["ats"] = min(1.0, projected["ats"] + 0.1)
            elif imp["category"] == "keywords":
                projected["ats"] = min(1.0, projected["ats"] + 0.05)
                projected["quality"] = min(1.0, projected["quality"] + 0.05)
            elif imp["category"] == "content":
                projected["quality"] = min(1.0, projected["quality"] + 0.08)
                projected["hiring"] = min(1.0, projected["hiring"] + 0.05)
        elif imp["priority"] == "medium":
            projected["quality"] = min(1.0, projected["quality"] + 0.03)
            projected["hiring"] = min(1.0, projected["hiring"] + 0.02)

    return {k: round(v, 3) for k, v in projected.items()}


def _calculate_grade(ats_score: float) -> str:
    """Calculate an overall grade from ATS score."""
    if ats_score >= 0.9:
        return "A+"
    elif ats_score >= 0.8:
        return "A"
    elif ats_score >= 0.7:
        return "B+"
    elif ats_score >= 0.6:
        return "B"
    elif ats_score >= 0.5:
        return "C+"
    elif ats_score >= 0.4:
        return "C"
    elif ats_score >= 0.3:
        return "D"
    else:
        return "F"
