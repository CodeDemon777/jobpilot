"""Resume Analyzer — ATS scoring, skill extraction, and improvement suggestions."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


# ── Skill database ────────────────────────────────────────────────────────────
# Comprehensive map of known tech skills grouped by category.
# Keys are lowercase canonical names; values are common aliases.

SKILL_DATABASE: dict[str, list[str]] = {
    # Programming Languages
    "python": ["python3", "py"],
    "javascript": ["js", "es6", "es2015", "ecmascript"],
    "typescript": ["ts"],
    "java": [],
    "go": ["golang"],
    "rust": [],
    "c": ["c programming"],
    "c++": ["cpp", "c plus plus"],
    "c#": ["csharp", "c sharp", ".net"],
    "ruby": ["ruby on rails", "rails"],
    "php": [],
    "swift": [],
    "kotlin": ["kt"],
    "scala": [],
    "r": ["r programming"],
    "matlab": [],
    "dart": [],
    "elixir": [],
    "haskell": [],
    "lua": [],
    "perl": [],
    "sql": [],
    "html": ["html5"],
    "css": ["css3", "scss", "sass", "less"],
    "bash": ["shell", "shell scripting", "bash scripting"],
    "powershell": [],

    # Frameworks & Libraries
    "react": ["reactjs", "react.js"],
    "react native": [],
    "next.js": ["nextjs", "next"],
    "vue.js": ["vuejs", "vue"],
    "angular": ["angularjs"],
    "svelte": ["sveltejs"],
    "node.js": ["nodejs", "node"],
    "express": ["expressjs", "express.js"],
    "django": [],
    "flask": [],
    "fastapi": ["fast api"],
    "spring": ["spring boot", "springboot", "spring framework"],
    "laravel": [],
    "rails": ["ruby on rails"],
    "asp.net": ["aspnet", "asp.net core"],
    "graphql": ["gql"],
    "rest api": ["rest", "restful", "rest apis", "restful api"],
    "grpc": ["grpc"],
    "tailwind": ["tailwindcss", "tailwind css"],
    "bootstrap": [],
    "jquery": [],
    "redux": [],
    "vuex": [],
    "pytorch": ["py torch"],
    "tensorflow": ["tf"],
    "keras": [],
    "scikit-learn": ["sklearn", "scikit learn"],
    "pandas": [],
    "numpy": [],
    "opencv": [],
    "hugging face": ["huggingface", "transformers"],
    "langchain": [],
    "llamaindex": ["llama index"],

    # DevOps & Cloud
    "aws": ["amazon web services"],
    "gcp": ["google cloud", "google cloud platform"],
    "azure": ["microsoft azure"],
    "docker": [],
    "kubernetes": ["k8s"],
    "terraform": [],
    "ansible": [],
    "jenkins": [],
    "github actions": ["gh actions", "github action"],
    "gitlab ci": ["gitlab ci/cd", "gitlab cicd"],
    "ci/cd": ["cicd", "continuous integration", "continuous deployment"],
    "nginx": [],
    "apache": [],
    "linux": [],
    "windows server": [],
    "prometheus": [],
    "grafana": [],
    "elk stack": ["elasticsearch", "logstash", "kibana"],
    "cloudflare": [],

    # Databases
    "postgresql": ["postgres", "psql"],
    "mysql": [],
    "mongodb": ["mongo"],
    "redis": [],
    "elasticsearch": ["elastic"],
    "dynamodb": ["dynamo db"],
    "sqlite": ["sqlite3"],
    "cassandra": [],
    "neo4j": [],
    "firebase": [],
    "supabase": [],
    "mariadb": [],
    "couchdb": ["couch db"],

    # Tools & Platforms
    "git": ["git version control"],
    "github": [],
    "gitlab": [],
    "bitbucket": [],
    "jira": [],
    "confluence": [],
    "figma": [],
    "swagger": ["openapi", "open api"],
    "postman": [],
    "vscode": ["visual studio code"],
    "vim": [],
    "neovim": [],

    # AI / ML
    "machine learning": ["ml"],
    "deep learning": ["dl"],
    "natural language processing": ["nlp"],
    "computer vision": ["cv"],
    "neural networks": [],
    "generative ai": ["genai", "gen ai"],
    "large language models": ["llm", "llms"],
    "data science": [],
    "data engineering": [],
    "mlops": [],
    "spark": ["apache spark"],
    "hadoop": ["apache hadoop"],
    "kafka": ["apache kafka"],
    "airflow": ["apache airflow"],
    "dbt": [],
    "snowflake": [],
    "databricks": [],
    "bigquery": ["big query"],
    "etl": [],

    # Soft Skills (detected from context)
    "agile": ["agile methodology", "agile development", "scrum"],
    "leadership": [],
    "communication": [],
    "teamwork": [],
    "problem solving": ["problem-solving"],
    "mentoring": [],
    "code review": [],
    "technical writing": [],
}

# Reverse lookup: alias → canonical name
_ALIAS_MAP: dict[str, str] = {}
for canonical, aliases in SKILL_DATABASE.items():
    _ALIAS_MAP[canonical] = canonical
    for alias in aliases:
        _ALIAS_MAP[alias.lower()] = canonical


# ── Section detection ─────────────────────────────────────────────────────────

SECTION_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("contact", re.compile(r"^\b(contact|personal|info)\b", re.I)),
    ("summary", re.compile(r"^\b(summary|objective|profile|about me|about)\b", re.I)),
    ("experience", re.compile(r"^\b(experience|work experience|employment|work history|professional experience)\b", re.I)),
    ("education", re.compile(r"^\b(education|academic|qualifications|degrees)\b", re.I)),
    ("skills", re.compile(r"^\b(skills|technical skills|technologies|competencies|tech stack)\b", re.I)),
    ("projects", re.compile(r"^\b(projects|personal projects|key projects|side projects)\b", re.I)),
    ("certifications", re.compile(r"^\b(certifications|certificates|licenses|credentials)\b", re.I)),
    ("awards", re.compile(r"^\b(awards|achievements|honors|accomplishments)\b", re.I)),
    ("publications", re.compile(r"^\b(publications|papers|articles)\b", re.I)),
    ("languages", re.compile(r"^\b(languages|spoken languages|foreign languages)\b", re.I)),
    ("volunteer", re.compile(r"^\b(volunteer|volunteering|community service)\b", re.I)),
    ("interests", re.compile(r"^\b(interests|hobbies)\b", re.I)),
]


def _detect_sections(text: str) -> dict[str, str]:
    """Parse resume text into sections based on heading detection."""
    lines = text.split("\n")
    sections: dict[str, str] = {}
    current_section = "header"
    current_content: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            current_content.append("")
            continue

        # Check if this line is a section heading
        matched = False
        for section_name, pattern in SECTION_PATTERNS:
            if pattern.match(stripped):
                # Save previous section
                sections[current_section] = "\n".join(current_content).strip()
                current_section = section_name
                current_content = []
                matched = True
                break

        if not matched:
            current_content.append(line)

    # Save last section
    sections[current_section] = "\n".join(current_content).strip()
    return sections


# ── Contact extraction ────────────────────────────────────────────────────────

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"[\+]?[\d\s\-\(\)]{7,20}")
_URL_RE = re.compile(r"https?://[^\s\)]+")
_LINKEDIN_RE = re.compile(r"linkedin\.com/in/[a-zA-Z0-9_-]+", re.I)
_GITHUB_RE = re.compile(r"github\.com/[a-zA-Z0-9_-]+", re.I)


def _extract_contact(text: str) -> dict[str, str]:
    """Extract contact info from resume text."""
    contact: dict[str, str] = {}

    # Extract name from first non-empty line (typically the header)
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if lines:
        first_line = lines[0]
        # If first line doesn't look like a section header or contact info, treat as name
        is_section = any(p.match(first_line) for _, p in SECTION_PATTERNS)
        has_contact = _EMAIL_RE.search(first_line) or _PHONE_RE.search(first_line)
        if not is_section and not has_contact and len(first_line.split()) <= 5:
            contact["name"] = first_line

    emails = _EMAIL_RE.findall(text)
    if emails:
        contact["email"] = emails[0]
    phones = _PHONE_RE.findall(text)
    if phones:
        contact["phone"] = phones[0].strip()
    linkedin = _LINKEDIN_RE.findall(text)
    if linkedin:
        contact["linkedin"] = f"https://{linkedin[0]}"
    github = _GITHUB_RE.findall(text)
    if github:
        contact["github"] = f"https://{github[0]}"
    urls = [u for u in _URL_RE.findall(text) if "linkedin" not in u and "github" not in u]
    if urls:
        contact["portfolio"] = urls[0]
    return contact


# ── Skill extraction ──────────────────────────────────────────────────────────

def _extract_skills(text: str) -> list[str]:
    """Extract known skills from resume text."""
    text_lower = text.lower()
    found: set[str] = set()

    # Check all aliases against the text
    for alias, canonical in _ALIAS_MAP.items():
        # Use word boundary matching to avoid false positives
        pattern = r"(?:^|[\s,;/\(\)\"'.\-=:+*#@!&])(" + re.escape(alias) + r")(?:$|[\s,;/\(\)\"'.\-=:+*#@!&])"
        if re.search(pattern, text_lower):
            found.add(canonical)

    return sorted(found)


# ── Experience extraction ─────────────────────────────────────────────────────

_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
_DURATION_RE = re.compile(
    r"(?:(\d+)\+?\s*(?:years?|yrs?))\s*(?:of)?\s*(?:experience)?",
    re.I,
)


def _estimate_experience_years(text: str, sections: dict[str, str]) -> int:
    """Estimate total years of experience from resume text."""
    # First check for explicit mentions
    explicit = _DURATION_RE.findall(text)
    if explicit:
        return max(int(y) for y in explicit)

    # Fall back to counting unique year ranges in experience section
    exp_text = sections.get("experience", text)
    years = sorted(set(_YEAR_RE.findall(exp_text)))
    if len(years) >= 2:
        return int(years[-1]) - int(years[0]) + 1
    elif len(years) == 1:
        return 1
    return 0


# ── Education extraction ──────────────────────────────────────────────────────

_DEGREE_RE = re.compile(
    r"\b(bachelor|master|ph\.?d|doctorate|b\.?s\.?|m\.?s\.?|b\.?a\.?|m\.?a\.?|"
    r"b\.?tech|m\.?tech|associate|diploma)\b",
    re.I,
)


def _extract_education(sections: dict[str, str]) -> list[str]:
    """Extract education details from resume."""
    edu_text = sections.get("education", "")
    if not edu_text:
        return []
    lines = [l.strip() for l in edu_text.split("\n") if l.strip()]
    return lines[:5]  # Return up to 5 education entries


# ── ATS scoring ───────────────────────────────────────────────────────────────

def _compute_ats_score(
    text: str,
    sections: dict[str, str],
    skills: list[str],
    contact: dict[str, str],
) -> float:
    """
    Compute an ATS compatibility score (0.0 – 1.0).

    Factors:
    - Contact info completeness (0.15)
    - Section structure (0.25)
    - Skill density (0.25)
    - Text quality — length, formatting (0.20)
    - Keywords / relevance (0.15)
    """
    score = 0.0

    # 1. Contact info (max 0.15)
    contact_fields = ["email", "phone", "linkedin", "github"]
    contact_hits = sum(1 for f in contact_fields if f in contact)
    score += (contact_hits / len(contact_fields)) * 0.15

    # 2. Section structure (max 0.25)
    important_sections = ["experience", "education", "skills"]
    section_hits = sum(1 for s in important_sections if s in sections and sections[s])
    score += (section_hits / len(important_sections)) * 0.25

    # Bonus for having projects or certifications
    if sections.get("projects"):
        score += 0.03
    if sections.get("certifications"):
        score += 0.02

    # 3. Skill density (max 0.25)
    skill_count = len(skills)
    if skill_count >= 10:
        score += 0.25
    elif skill_count >= 6:
        score += 0.20
    elif skill_count >= 3:
        score += 0.15
    elif skill_count >= 1:
        score += 0.10

    # 4. Text quality (max 0.20)
    word_count = len(text.split())
    if 200 <= word_count <= 800:
        score += 0.20
    elif 100 <= word_count < 200 or 800 < word_count <= 1200:
        score += 0.15
    elif word_count > 50:
        score += 0.10
    # Very short resumes get nothing here

    # Penalize excessive special characters (bad ATS formatting)
    special_ratio = len(re.findall(r"[^\w\s.,;:/\-@#&*()']", text)) / max(len(text), 1)
    if special_ratio > 0.1:
        score -= 0.05

    # 5. Keywords (max 0.15)
    # Check for action verbs and quantifiable results
    action_verbs = [
        "built", "developed", "implemented", "designed", "led", "managed",
        "created", "improved", "increased", "reduced", "launched", "deployed",
        "optimized", "automated", "collaborated", "mentored", "architected",
        "delivered", "migrated", "scaled", "integrated", "refactored",
    ]
    verb_count = sum(1 for v in action_verbs if v.lower() in text.lower())
    has_numbers = bool(re.search(r"\d+[%$KkMm]|\$\d+|\d{2,}", text))
    keyword_score = min(verb_count / 5, 1.0) * 0.10 + (0.05 if has_numbers else 0.0)
    score += keyword_score

    return max(0.0, min(1.0, score))


# ── Improvement suggestions ───────────────────────────────────────────────────

def _generate_suggestions(
    sections: dict[str, str],
    skills: list[str],
    contact: dict[str, str],
    experience_years: int,
    ats_score: float,
) -> list[str]:
    """Generate actionable improvement suggestions."""
    suggestions: list[str] = []

    # Contact
    if "email" not in contact:
        suggestions.append("Add your email address — recruiters need a way to contact you.")
    if "phone" not in contact:
        suggestions.append("Add your phone number for recruiter callbacks.")
    if "linkedin" not in contact:
        suggestions.append("Add your LinkedIn profile URL — most recruiters check it.")
    if "github" not in contact:
        suggestions.append("Add your GitHub profile to showcase code projects.")

    # Sections
    if not sections.get("summary"):
        suggestions.append("Add a professional summary (2-3 lines) at the top to hook recruiters.")
    if not sections.get("experience"):
        suggestions.append("Add a work experience section — even internships count.")
    if not sections.get("projects"):
        suggestions.append("Add a projects section to demonstrate hands-on skills.")
    if not sections.get("certifications"):
        suggestions.append("Consider adding relevant certifications (AWS, Google Cloud, etc.).")

    # Skills
    if len(skills) < 5:
        suggestions.append(f"Only {len(skills)} skills detected — add more technical skills to pass ATS filters.")
    if len(skills) > 20:
        suggestions.append("You have many skills listed — consider grouping them by category for readability.")

    # Experience
    if experience_years == 0:
        suggestions.append("No clear experience duration found — quantify your years of experience.")

    # Text quality
    word_count = len(" ".join(sections.values()).split())
    if word_count < 150:
        suggestions.append("Resume is very short — expand with more details, achievements, and metrics.")
    if word_count > 1000:
        suggestions.append("Resume is very long — aim for 1-2 pages. Remove less relevant content.")

    # Action verbs
    action_verbs = [
        "built", "developed", "implemented", "designed", "led", "managed",
        "created", "improved", "increased", "reduced", "launched",
    ]
    text_lower = " ".join(sections.values()).lower()
    verb_count = sum(1 for v in action_verbs if v in text_lower)
    if verb_count < 3:
        suggestions.append("Use more action verbs (built, designed, led, improved) to describe achievements.")

    # Quantifiable results
    has_numbers = bool(re.search(r"\d+[%$KkMm]|\$\d+|\d{3,}", " ".join(sections.values())))
    if not has_numbers:
        suggestions.append("Add quantifiable results (e.g., 'reduced load time by 40%', 'served 10K users').")

    # ATS warnings
    if ats_score < 0.5:
        suggestions.append("Your ATS score is low — ensure standard section headings and no tables/columns.")

    return suggestions


# ── Strengths & weaknesses ────────────────────────────────────────────────────

def _identify_strengths(
    skills: list[str],
    experience_years: int,
    sections: dict[str, str],
    contact: dict[str, str],
) -> list[str]:
    """Identify resume strengths."""
    strengths: list[str] = []

    if len(skills) >= 8:
        strengths.append(f"Strong technical toolkit with {len(skills)} skills identified.")
    if experience_years >= 3:
        strengths.append(f"{experience_years} years of experience — solid professional background.")
    if sections.get("projects"):
        strengths.append("Projects section present — demonstrates practical application of skills.")
    if sections.get("certifications"):
        strengths.append("Certifications listed — shows commitment to professional development.")
    if contact.get("github"):
        strengths.append("GitHub profile included — recruiters can verify your code quality.")
    if contact.get("linkedin"):
        strengths.append("LinkedIn profile included — strengthens professional presence.")

    # Check for popular high-demand skills
    high_demand = {"python", "react", "aws", "docker", "kubernetes", "typescript", "go", "rust"}
    matched_hd = high_demand & set(skills)
    if len(matched_hd) >= 3:
        strengths.append(f"In-demand skills: {', '.join(sorted(matched_hd))}.")

    # Check for cloud skills
    cloud_skills = {"aws", "gcp", "azure"}
    if cloud_skills & set(skills):
        strengths.append("Cloud platform experience — highly valued by employers.")

    # Check for DevOps skills
    devops_skills = {"docker", "kubernetes", "terraform", "ci/cd", "jenkins"}
    if devops_skills & set(skills):
        strengths.append("DevOps/containerization skills — modern engineering practices.")

    return strengths


def _identify_weaknesses(
    skills: list[str],
    experience_years: int,
    sections: dict[str, str],
    contact: dict[str, str],
) -> list[str]:
    """Identify resume weaknesses."""
    weaknesses: list[str] = []

    if len(skills) < 5:
        weaknesses.append(f"Only {len(skills)} skills detected — sparse technical profile.")
    if experience_years == 0:
        weaknesses.append("No clear experience duration — may appear as entry-level.")
    if not sections.get("summary"):
        weaknesses.append("Missing professional summary — first thing recruiters read.")
    if not sections.get("projects"):
        weaknesses.append("No projects section — missed opportunity to show practical skills.")
    if not contact.get("email"):
        weaknesses.append("No email address — essential for recruiter contact.")
    if not contact.get("linkedin"):
        weaknesses.append("No LinkedIn profile — expected by most recruiters.")
    if not contact.get("github"):
        weaknesses.append("No GitHub — important for technical roles.")
    if not sections.get("certifications"):
        weaknesses.append("No certifications listed — can differentiate from other candidates.")

    return weaknesses


# ── Public API ────────────────────────────────────────────────────────────────

@dataclass
class ResumeAnalysisResult:
    """Complete resume analysis output."""

    # Extracted data
    name: str = ""
    email: str = ""
    phone: str = ""
    linkedin: str = ""
    github: str = ""
    skills: list[str] = field(default_factory=list)
    experience_years: int = 0
    education: list[str] = field(default_factory=list)
    sections_detected: list[str] = field(default_factory=list)

    # Scores (0.0 – 1.0)
    ats_score: float = 0.0
    resume_quality_score: float = 0.0
    technical_strength_score: float = 0.0
    hiring_readiness_score: float = 0.0

    # Analysis
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "linkedin": self.linkedin,
            "github": self.github,
            "skills": self.skills,
            "experience_years": self.experience_years,
            "education": self.education,
            "sections_detected": self.sections_detected,
            "scores": {
                "ats_score": round(self.ats_score, 2),
                "resume_quality_score": round(self.resume_quality_score, 2),
                "technical_strength_score": round(self.technical_strength_score, 2),
                "hiring_readiness_score": round(self.hiring_readiness_score, 2),
            },
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "missing_skills": self.missing_skills,
            "suggestions": self.suggestions,
        }


def analyze_resume(text: str, target_role: str = "") -> ResumeAnalysisResult:
    """
    Perform a full resume analysis.

    Args:
        text: Plain text content of the resume.
        target_role: Optional target role for gap analysis.

    Returns:
        ResumeAnalysisResult with scores, strengths, weaknesses, and suggestions.
    """
    sections = _detect_sections(text)
    contact = _extract_contact(text)
    skills = _extract_skills(text)
    experience_years = _estimate_experience_years(text, sections)
    education = _extract_education(sections)

    # Section names present
    sections_detected = [s for s, content in sections.items() if content and s != "header"]

    # ATS score
    ats_score = _compute_ats_score(text, sections, skills, contact)

    # Technical strength (based on skill count and depth)
    tech_score = min(len(skills) / 15, 1.0)  # 15+ skills = max
    if experience_years >= 3:
        tech_score = min(tech_score + 0.15, 1.0)
    if any(s in skills for s in ["aws", "gcp", "azure", "kubernetes", "docker"]):
        tech_score = min(tech_score + 0.1, 1.0)

    # Resume quality (structure + content)
    quality_score = ats_score * 0.6  # Base on ATS
    if sections.get("summary"):
        quality_score += 0.15
    if sections.get("projects"):
        quality_score += 0.15
    word_count = len(text.split())
    if 200 <= word_count <= 800:
        quality_score += 0.10
    quality_score = min(quality_score, 1.0)

    # Hiring readiness (composite)
    hiring_score = (ats_score * 0.30 + tech_score * 0.35 + quality_score * 0.35)

    # Missing skills for target role
    missing_skills: list[str] = []
    if target_role:
        target_lower = target_role.lower()
        role_skill_map = {
            "backend": ["python", "sql", "rest api", "docker", "postgresql"],
            "frontend": ["javascript", "react", "css", "html", "typescript"],
            "full stack": ["javascript", "react", "node.js", "postgresql", "docker"],
            "devops": ["docker", "kubernetes", "terraform", "ci/cd", "aws"],
            "data engineer": ["python", "sql", "spark", "airflow", "kafka"],
            "ml engineer": ["python", "pytorch", "tensorflow", "sql", "docker"],
            "software engineer": ["python", "git", "sql", "docker", "rest api"],
        }
        for role_key, required in role_skill_map.items():
            if role_key in target_lower:
                missing_skills = [s for s in required if s not in skills]
                break

    # Strengths and weaknesses
    strengths = _identify_strengths(skills, experience_years, sections, contact)
    weaknesses = _identify_weaknesses(skills, experience_years, sections, contact)

    # Suggestions
    suggestions = _generate_suggestions(sections, skills, contact, experience_years, ats_score)

    return ResumeAnalysisResult(
        name=contact.get("name", ""),
        email=contact.get("email", ""),
        phone=contact.get("phone", ""),
        linkedin=contact.get("linkedin", ""),
        github=contact.get("github", ""),
        skills=skills,
        experience_years=experience_years,
        education=education,
        sections_detected=sections_detected,
        ats_score=round(ats_score, 2),
        resume_quality_score=round(quality_score, 2),
        technical_strength_score=round(tech_score, 2),
        hiring_readiness_score=round(hiring_score, 2),
        strengths=strengths,
        weaknesses=weaknesses,
        missing_skills=missing_skills,
        suggestions=suggestions,
    )
