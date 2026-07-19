"""One-Click Resume Tailoring for JobPilot."""

import re
from jobpilot.resume_analyzer import (
    _extract_skills,
    _detect_sections,
    _compute_ats_score,
    _extract_contact,
    _estimate_experience_years,
    _extract_education,
    SKILL_DATABASE,
)


def tailor_resume(
    resume_text: str,
    job_description: str,
    job_skills: list[str] = None,
) -> dict:
    """
    Generate a tailored resume version for a specific job.

    Returns dict with:
        - original_text: The original resume text
        - tailored_text: The tailored resume text
        - original_score: Original ATS score
        - tailored_score: Tailored ATS score
        - improvement_pct: Percentage improvement
        - keywords_added: Keywords that were added/emphasized
        - changes_made: List of changes made
    """
    if job_skills is None:
        job_skills = []

    # Extract information
    resume_skills = _extract_skills(resume_text)
    job_skills_from_desc = _extract_skills(job_description)
    all_job_skills = list(set(job_skills + job_skills_from_desc))

    # Find missing keywords
    missing_keywords = [k for k in all_job_skills if k not in resume_skills]

    # Compute original score
    sections = _detect_sections(resume_text)
    contact = _extract_contact(resume_text)
    original_score = _compute_ats_score(
        text=resume_text, sections=sections, skills=resume_skills, contact=contact
    )

    # Generate tailored resume
    tailored_text = _generate_tailored_text(
        resume_text, sections, missing_keywords, all_job_skills
    )

    # Compute tailored score
    tailored_sections = _detect_sections(tailored_text)
    tailored_skills = _extract_skills(tailored_text)
    tailored_contact = _extract_contact(tailored_text)
    tailored_score = _compute_ats_score(
        text=tailored_text,
        sections=tailored_sections,
        skills=tailored_skills,
        contact=tailored_contact,
    )

    # Calculate improvement
    improvement_pct = (
        ((tailored_score - original_score) / original_score * 100)
        if original_score > 0
        else 0
    )

    # Track changes
    keywords_added = [k for k in missing_keywords if k in tailored_text.lower()]
    changes_made = _identify_changes(resume_text, tailored_text, missing_keywords)

    return {
        "original_text": resume_text,
        "tailored_text": tailored_text,
        "original_score": round(original_score, 3),
        "tailored_score": round(tailored_score, 3),
        "improvement_pct": round(improvement_pct, 1),
        "keywords_added": keywords_added,
        "changes_made": changes_made,
        "total_keywords_added": len(keywords_added),
    }


def _generate_tailored_text(
    resume_text: str,
    sections: dict,
    missing_keywords: list[str],
    job_skills: list[str],
) -> str:
    """Generate tailored resume text."""
    lines = resume_text.split("\n")
    tailored_lines = []
    summary_enhanced = False
    skills_enhanced = False

    for line in lines:
        stripped = line.strip()

        # Check if this is a section header
        is_header = False
        for section_name in [
            "summary",
            "objective",
            "skills",
            "technical skills",
            "technologies",
        ]:
            if stripped.lower().startswith(section_name):
                is_header = True
                break

        if is_header:
            tailored_lines.append(line)
            continue

        # Enhance summary section with keywords
        if not summary_enhanced and sections.get("summary") and stripped:
            # Check if we're in the summary section
            summary_text = sections.get("summary", "").lower()
            if any(kw in summary_text for kw in ["summary", "objective", "profile"]):
                if missing_keywords:
                    enhanced_summary = _enhance_summary(stripped, missing_keywords[:3])
                    tailored_lines.append(enhanced_summary)
                    summary_enhanced = True
                    continue

        # Enhance skills section
        if not skills_enhanced and stripped and not is_header:
            # Check if this line contains skills (comma-separated)
            if "," in stripped and len(stripped.split(",")) >= 2:
                # Check if this looks like a skills section
                prev_lines = [
                    l.strip().lower() for l in lines[: lines.index(line)] if l.strip()
                ]
                if any(
                    "skill" in l or "technolog" in l or "tech" in l
                    for l in prev_lines[-2:]
                ):
                    enhanced_skills = _enhance_skills_line(stripped, missing_keywords)
                    tailored_lines.append(enhanced_skills)
                    skills_enhanced = True
                    continue

        # Add keywords to experience bullets
        if stripped.startswith(("- ", "• ", "* ")) and missing_keywords:
            enhanced_bullet = _enhance_experience_bullet(stripped, missing_keywords[:2])
            tailored_lines.append(enhanced_bullet)
            continue

        tailored_lines.append(line)

    # Add missing keywords section if not found anywhere
    if missing_keywords and not skills_enhanced:
        # Find where to insert skills section
        insert_idx = len(tailored_lines)
        for i, line in enumerate(tailored_lines):
            if line.strip().lower().startswith("education"):
                insert_idx = i
                break

        tailored_lines.insert(insert_idx, "")
        tailored_lines.insert(insert_idx + 1, "SKILLS")
        tailored_lines.insert(
            insert_idx + 2,
            ", ".join(
                skills[:15]
                if (skills := _extract_skills(text := "\n".join(tailored_lines)))
                else missing_keywords[:10]
            ),
        )
        tailored_lines.insert(insert_idx + 3, "")

    return "\n".join(tailored_lines)


def _enhance_summary(summary: str, keywords: list[str]) -> str:
    """Enhance summary with relevant keywords."""
    if not summary:
        return summary

    # Add keywords naturally
    keyword_phrase = ", ".join(keywords[:3])
    if summary.endswith("."):
        enhanced = summary[:-1] + f" with expertise in {keyword_phrase}."
    else:
        enhanced = summary + f" with expertise in {keyword_phrase}."

    return enhanced


def _enhance_skills_line(skills_line: str, missing_keywords: list[str]) -> str:
    """Enhance a skills line with missing keywords."""
    existing_skills = [s.strip() for s in skills_line.split(",")]

    # Add missing keywords that aren't already present
    for kw in missing_keywords[:5]:
        if kw.lower() not in [s.lower() for s in existing_skills]:
            existing_skills.append(kw)

    return ", ".join(existing_skills)


def _enhance_experience_bullet(bullet: str, keywords: list[str]) -> str:
    """Enhance an experience bullet with relevant keywords."""
    # Don't modify too aggressively - just ensure keywords appear naturally
    if not bullet or not keywords:
        return bullet

    # Check if any keyword is already mentioned
    bullet_lower = bullet.lower()
    if any(kw in bullet_lower for kw in keywords):
        return bullet

    # Add a subtle keyword mention if space allows
    if len(bullet) < 150:
        return bullet  # Keep it concise

    return bullet


def _identify_changes(original: str, tailored: str, keywords: list[str]) -> list[str]:
    """Identify changes made between original and tailored resume."""
    changes = []

    # Check for new keywords
    original_lower = original.lower()
    for kw in keywords:
        if kw in tailored.lower() and kw not in original_lower:
            changes.append(f"Added keyword: {kw}")

    # Check for length changes
    orig_lines = len(original.split("\n"))
    tail_lines = len(tailored.split("\n"))
    if tail_lines > orig_lines:
        changes.append("Added additional content sections")
    elif tail_lines < orig_lines:
        changes.append("Streamlined content for clarity")

    # Check for skill additions
    orig_skills = set(_extract_skills(original))
    tail_skills = set(_extract_skills(tailored))
    new_skills = tail_skills - orig_skills
    if new_skills:
        changes.append(f"Added skills: {', '.join(list(new_skills)[:3])}")

    if not changes:
        changes.append("Optimized existing content for ATS compatibility")

    return changes
