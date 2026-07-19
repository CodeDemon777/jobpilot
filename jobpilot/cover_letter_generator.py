"""AI Cover Letter Generator for JobPilot."""

import re
from jobpilot.resume_analyzer import _extract_skills, _detect_sections, _extract_contact


# Cover letter templates by tone
TEMPLATES = {
    "professional": {
        "opening": "Dear Hiring Manager,\n\nI am writing to express my strong interest in the {role} position at {company}. With my background in {skills_phrase}, I am confident in my ability to contribute meaningfully to your team.",
        "body": "Throughout my career, I have developed expertise in {skills_list}. {experience_highlight} I am particularly drawn to {company} because of its reputation for {company_quality}, and I believe my skills align well with your requirements.",
        "closing": "I would welcome the opportunity to discuss how my experience and skills can contribute to {company}'s continued success. Thank you for considering my application.\n\nSincerely,\n{candidate_name}",
    },
    "enthusiastic": {
        "opening": "Dear Hiring Manager,\n\nI'm excited to apply for the {role} position at {company}! This opportunity perfectly aligns with my passion for {skills_phrase} and my career aspirations.",
        "body": "My experience with {skills_list} has prepared me well for this role. {experience_highlight} I'm particularly thrilled about {company}'s mission to {company_quality}, and I'm eager to bring my energy and expertise to your team.",
        "closing": "I'd love the chance to discuss how I can contribute to {company}'s exciting future. Looking forward to hearing from you!\n\nBest regards,\n{candidate_name}",
    },
    "formal": {
        "opening": "To the Hiring Committee,\n\nI submit my application for the {role} position at {company}. My qualifications in {skills_phrase} make me a strong candidate for this role.",
        "body": "My professional background includes significant experience in {skills_list}. {experience_highlight} I am impressed by {company}'s commitment to {company_quality} and am prepared to make immediate contributions.",
        "closing": "I am available for an interview at your earliest convenience and can be reached at the contact information provided. Thank you for your time and consideration.\n\nRespectfully,\n{candidate_name}",
    },
}


def generate_cover_letter(
    resume_text: str,
    job_description: str,
    company: str,
    role: str,
    tone: str = "professional",
    candidate_name: str = "",
) -> dict:
    """
    Generate a personalized cover letter.

    Returns dict with:
        - letter_text: The generated cover letter
        - word_count: Word count of the letter
        - tone: The tone used
        - sections: Breakdown of letter sections
    """
    # Extract information from resume
    skills = _extract_skills(resume_text)
    contact = _extract_contact(resume_text)
    sections = _detect_sections(resume_text)

    if not candidate_name:
        candidate_name = contact.get("name", "Candidate")

    # Extract job requirements
    job_skills = _extract_skills(job_description)

    # Find matching skills
    matched_skills = [s for s in skills if s in job_skills]
    if not matched_skills:
        matched_skills = skills[:5]  # Use top resume skills if no match

    # Build skills phrase
    if len(matched_skills) > 3:
        skills_phrase = f"{', '.join(matched_skills[:3])}, and {matched_skills[3]}"
    elif matched_skills:
        skills_phrase = ", ".join(matched_skills)
    else:
        skills_phrase = "software development and technical innovation"

    # Build skills list
    skills_list = ", ".join(matched_skills[:6]) if matched_skills else "relevant technologies"

    # Extract experience highlights
    experience_text = sections.get("experience", "")
    experience_highlight = _extract_experience_highlight(experience_text, matched_skills)

    # Determine company quality (generic but professional)
    company_quality = _determine_company_quality(job_description, company)

    # Get template
    template = TEMPLATES.get(tone, TEMPLATES["professional"])

    # Generate letter sections
    opening = template["opening"].format(
        role=role, company=company, skills_phrase=skills_phrase, candidate_name=candidate_name
    )
    body = template["body"].format(
        skills_list=skills_list, experience_highlight=experience_highlight,
        company=company, company_quality=company_quality
    )
    closing = template["closing"].format(
        company=company, candidate_name=candidate_name
    )

    letter_text = f"{opening}\n\n{body}\n\n{closing}"
    word_count = len(letter_text.split())

    return {
        "letter_text": letter_text,
        "word_count": word_count,
        "tone": tone,
        "sections": {
            "opening": opening,
            "body": body,
            "closing": closing,
        },
        "matched_skills": matched_skills,
        "candidate_name": candidate_name,
    }


def _extract_experience_highlight(experience_text: str, skills: list[str]) -> str:
    """Extract a relevant experience highlight from resume."""
    if not experience_text:
        return "I have a strong track record of delivering results in fast-paced environments."

    # Look for bullet points or lines mentioning skills
    lines = experience_text.split("\n")
    relevant_lines = []
    for line in lines:
        line = line.strip()
        if not line or len(line) < 20:
            continue
        # Check if line mentions any of our skills
        line_lower = line.lower()
        if any(s in line_lower for s in skills[:5]):
            relevant_lines.append(line)

    if relevant_lines:
        # Clean up and return the most relevant line
        highlight = relevant_lines[0]
        # Remove leading bullet points or dashes
        highlight = re.sub(r'^[\-•*]\s*', '', highlight)
        return f"Specifically, {highlight.lower()}"

    return "I have a strong track record of delivering results in fast-paced environments."


def _determine_company_quality(job_description: str, company: str) -> str:
    """Determine a company quality statement based on job description."""
    desc_lower = job_description.lower()

    if any(w in desc_lower for w in ["innovation", "innovative", "cutting-edge", "leading"]):
        return "innovation and cutting-edge technology"
    elif any(w in desc_lower for w in ["growth", "scale", "fast-paced"]):
        return "growth and excellence in technology"
    elif any(w in desc_lower for w in ["mission", "impact", "purpose"]):
        return "making a meaningful impact through technology"
    elif any(w in desc_lower for w in ["quality", "engineering", "craft"]):
        return "engineering excellence and quality"
    else:
        return "excellence in technology and innovation"
