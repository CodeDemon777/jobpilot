"""AI Career Coach for JobPilot - Answers career questions and provides guidance."""

from typing import Optional
from jobpilot import database as db
from jobpilot.config import DB_PATH
from jobpilot.models import UserProfile, JobListing
from jobpilot.profile import load_profile
from jobpilot.matcher import compute_match
from jobpilot.resume_analyzer import analyze_resume
from jobpilot.skill_gap_analyzer import analyze_skill_gap


class CareerCoach:
    """AI-powered career advisor that answers career questions."""

    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH

    def ask(self, question: str, user_id: int = 1) -> dict:
        """
        Answer a career question.

        Returns dict with:
            - question: The original question
            - answer: The generated answer
            - context: Supporting data
            - suggestions: Related actions
        """
        profile = load_profile()

        # Analyze the question
        question_lower = question.lower()

        # Route to appropriate handler
        if any(
            word in question_lower for word in ["ats", "resume score", "resume quality"]
        ):
            return self._handle_ats_question(question, profile)
        elif any(word in question_lower for word in ["project", "portfolio", "github"]):
            return self._handle_project_question(question, profile)
        elif any(word in question_lower for word in ["company", "fit", "match"]):
            return self._handle_company_question(question, profile)
        elif any(word in question_lower for word in ["improve", "better", "enhance"]):
            return self._handle_improvement_question(question, profile)
        elif any(
            word in question_lower for word in ["certificate", "cert", "certification"]
        ):
            return self._handle_certificate_question(question, profile)
        elif any(word in question_lower for word in ["salary", "pay", "compensation"]):
            return self._handle_salary_question(question, profile)
        elif any(
            word in question_lower for word in ["interview", "prepare", "practice"]
        ):
            return self._handle_interview_question(question, profile)
        elif any(word in question_lower for word in ["skill", "learn", "technology"]):
            return self._handle_skill_question(question, profile)
        else:
            return self._handle_general_question(question, profile)

    def _handle_ats_question(self, question: str, profile: UserProfile) -> dict:
        """Handle questions about ATS score."""
        skills = profile.all_skills
        skill_count = len(skills)
        has_email = bool(profile.email)
        has_linkedin = bool(profile.linkedin)
        has_github = bool(profile.github)

        # Analyze ATS factors
        factors = []
        if skill_count < 5:
            factors.append("Your skill list is too short. Add more technical skills.")
        if not has_email:
            factors.append("Missing email address - essential for recruiter contact.")
        if not has_linkedin:
            factors.append("Missing LinkedIn profile - expected by most recruiters.")
        if not has_github:
            factors.append("Missing GitHub profile - important for technical roles.")
        if profile.experience_years == 0:
            factors.append("No experience years specified.")

        answer = f"""Based on your profile, here's your ATS analysis:

**Current Skills:** {skill_count} skills detected
**Contact Info:** {'Complete' if has_email and has_linkedin else 'Incomplete'}

**Key Issues:**
{chr(10).join('- ' + f for f in factors) if factors else '- Your profile looks good!'}

**Recommendations:**
1. Add more relevant technical skills (aim for 10-15)
2. Ensure all contact information is complete
3. Include quantifiable achievements in your experience
4. Use keywords from job descriptions in your profile"""

        return {
            "question": question,
            "answer": answer,
            "context": {
                "skill_count": skill_count,
                "has_email": has_email,
                "has_linkedin": has_linkedin,
            },
            "suggestions": [
                "Add more skills",
                "Complete contact info",
                "Add quantifiable results",
            ],
        }

    def _handle_project_question(self, question: str, profile: UserProfile) -> dict:
        """Handle questions about projects and portfolio."""
        skills = profile.all_skills

        # Suggest projects based on skills
        project_suggestions = []
        if "python" in skills:
            project_suggestions.append(
                {
                    "name": "REST API with FastAPI",
                    "description": "Build a production-ready API with authentication, database, and tests",
                }
            )
        if "react" in skills or "javascript" in skills:
            project_suggestions.append(
                {
                    "name": "Full-Stack Dashboard",
                    "description": "Create a real-time analytics dashboard with React frontend and Node.js backend",
                }
            )
        if "docker" in skills or "kubernetes" in skills:
            project_suggestions.append(
                {
                    "name": "CI/CD Pipeline",
                    "description": "Set up automated testing and deployment with Docker and GitHub Actions",
                }
            )
        if "aws" in skills or "cloud" in str(profile.cloud_platforms).lower():
            project_suggestions.append(
                {
                    "name": "Cloud Architecture",
                    "description": "Deploy a scalable application on AWS with auto-scaling and monitoring",
                }
            )

        answer = f"""Here are project suggestions based on your skills:

**Your Skills:** {', '.join(skills[:10])}

**Recommended Projects:**
{chr(10).join(f"- **{p['name']}**: {p['description']}" for p in project_suggestions[:4])}

**Portfolio Tips:**
1. Include README with project description and setup instructions
2. Add live demos or screenshots
3. Write clean, documented code
4. Include tests
5. Deploy to production (not just localhost)"""

        return {
            "question": question,
            "answer": answer,
            "context": {"skills": skills, "project_count": len(project_suggestions)},
            "suggestions": [
                "Build portfolio projects",
                "Deploy to production",
                "Add documentation",
            ],
        }

    def _handle_company_question(self, question: str, profile: UserProfile) -> dict:
        """Handle questions about company fit."""
        skills = profile.all_skills

        # Analyze job matches
        jobs = db.get_all_jobs(self.db_path)
        matching_jobs = []

        for job in jobs[:50]:  # Check first 50 jobs
            match = compute_match(profile, job)
            if match.overall_score >= 0.5:
                matching_jobs.append(
                    {
                        "company": job.company,
                        "title": job.title,
                        "score": match.overall_score,
                        "missing": match.missing_skills[:3],
                    }
                )

        matching_jobs.sort(key=lambda x: x["score"], reverse=True)

        answer = f"""Based on your profile, here are companies that fit well:

**Top Matching Companies:**
{chr(10).join(f"- **{j['company']}** ({j['title']}) - Match: {j['score']*100:.0f}% - Missing: {', '.join(j['missing'])}" for j in matching_jobs[:5])}

**Your Strengths:**
- {len(skills)} technical skills
- {profile.experience_years} years of experience

**Recommendations:**
1. Focus on companies with {len(skills)}+ matching skills
2. Apply to roles where you match 60%+ of requirements
3. Highlight your strongest skills in applications"""

        return {
            "question": question,
            "answer": answer,
            "context": {"matching_companies": len(matching_jobs)},
            "suggestions": [
                "Apply to top matches",
                "Highlight matching skills",
                "Research company culture",
            ],
        }

    def _handle_improvement_question(self, question: str, profile: UserProfile) -> dict:
        """Handle questions about improvement."""
        skills = profile.all_skills

        improvements = []
        if len(skills) < 10:
            improvements.append("Add more technical skills to your profile")
        if not profile.linkedin:
            improvements.append("Create a LinkedIn profile")
        if not profile.github:
            improvements.append("Set up a GitHub portfolio")
        if profile.experience_years < 2:
            improvements.append(
                "Gain more work experience through internships or projects"
            )

        answer = f"""Here's how you can improve your profile:

**Current Status:**
- {len(skills)} skills
- {profile.experience_years} years experience
- LinkedIn: {'Yes' if profile.linkedin else 'No'}
- GitHub: {'Yes' if profile.github else 'No'}

**Improvement Areas:**
{chr(10).join('- ' + i for i in improvements) if improvements else '- Your profile looks great!'}

**Action Items:**
1. Add 5+ more relevant skills
2. Complete all social profiles
3. Add quantifiable achievements
4. Get relevant certifications"""

        return {
            "question": question,
            "answer": answer,
            "context": {"improvements_count": len(improvements)},
            "suggestions": improvements[:3],
        }

    def _handle_certificate_question(self, question: str, profile: UserProfile) -> dict:
        """Handle questions about certifications."""
        skills = profile.all_skills

        cert_recommendations = []
        if "aws" in skills or "cloud" in str(profile.cloud_platforms).lower():
            cert_recommendations.append(
                {
                    "name": "AWS Solutions Architect",
                    "provider": "Amazon",
                    "value": "High",
                }
            )
        if "python" in skills:
            cert_recommendations.append(
                {
                    "name": "Python Professional",
                    "provider": "PCEP/PCAP",
                    "value": "Medium",
                }
            )
        if "docker" in skills or "kubernetes" in str(skills):
            cert_recommendations.append(
                {
                    "name": "Certified Kubernetes Administrator",
                    "provider": "CNCF",
                    "value": "High",
                }
            )
        if "security" in str(skills).lower():
            cert_recommendations.append(
                {"name": "CompTIA Security+", "provider": "CompTIA", "value": "High"}
            )

        if not cert_recommendations:
            cert_recommendations = [
                {
                    "name": "AWS Cloud Practitioner",
                    "provider": "Amazon",
                    "value": "Entry-level",
                },
                {
                    "name": "Google Cloud Associate",
                    "provider": "Google",
                    "value": "Entry-level",
                },
            ]

        answer = f"""Recommended certifications for your profile:

**Top Recommendations:**
{chr(10).join(f"- **{c['name']}** ({c['provider']}) - Value: {c['value']}" for c in cert_recommendations[:5])}

**Certification Tips:**
1. Start with entry-level certifications
2. Focus on cloud platforms (AWS, GCP, Azure)
3. Get certified in your primary technology stack
4. Certifications complement experience, not replace it"""

        return {
            "question": question,
            "answer": answer,
            "context": {"recommendations": len(cert_recommendations)},
            "suggestions": [
                "Get cloud certification",
                "Add to LinkedIn",
                "Include in resume",
            ],
        }

    def _handle_salary_question(self, question: str, profile: UserProfile) -> dict:
        """Handle questions about salary."""
        skills = profile.all_skills
        exp = profile.experience_years

        # Simple salary estimation
        base_salary = 60000
        if exp >= 5:
            base_salary = 100000
        elif exp >= 3:
            base_salary = 80000
        elif exp >= 1:
            base_salary = 70000

        # Skill premium
        premium_skills = {
            "python",
            "react",
            "aws",
            "kubernetes",
            "docker",
            "machine learning",
        }
        skill_bonus = len(set(skills) & premium_skills) * 5000

        estimated_min = base_salary
        estimated_max = base_salary + skill_bonus + 30000

        answer = f"""Based on your profile:

**Experience:** {exp} years
**Key Skills:** {', '.join(skills[:5])}

**Estimated Salary Range:**
- Minimum: ${estimated_min:,}
- Maximum: ${estimated_max:,}
- Average: ${(estimated_min + estimated_max) // 2:,}

**Factors Affecting Salary:**
- Years of experience
- Technical skills (cloud, DevOps, AI/ML skills command premium)
- Location (remote vs onsite)
- Company size and stage
- Industry

**Tips to Increase Salary:**
1. Negotiate based on market data
2. Highlight unique skills
3. Consider total compensation (bonus, equity, benefits)
4. Get competing offers"""

        return {
            "question": question,
            "answer": answer,
            "context": {"estimated_min": estimated_min, "estimated_max": estimated_max},
            "suggestions": [
                "Research market rates",
                "Negotiate with data",
                "Consider total comp",
            ],
        }

    def _handle_interview_question(self, question: str, profile: UserProfile) -> dict:
        """Handle questions about interview preparation."""
        skills = profile.all_skills

        answer = f"""Here's your interview preparation plan:

**Technical Skills to Review:**
{chr(10).join('- ' + s for s in skills[:8])}

**Preparation Steps:**
1. **Coding Practice**: Solve 2-3 problems daily on LeetCode/HackerRank
2. **System Design**: Practice designing scalable systems
3. **Behavioral**: Prepare STAR method stories for common questions
4. **Projects**: Be ready to explain your projects in detail
5. **Company Research**: Research the company's tech stack and recent news

**Common Interview Topics:**
- Data structures and algorithms
- System design and architecture
- Behavioral questions (leadership, conflict, teamwork)
- Technical deep-dives on your resume projects
- Coding challenges (live or take-home)

**Tips:**
- Practice out loud
- Record yourself and review
- Mock interviews with peers
- Prepare questions to ask interviewers"""

        return {
            "question": question,
            "answer": answer,
            "context": {"skills_count": len(skills)},
            "suggestions": [
                "Practice coding daily",
                "Prepare STAR stories",
                "Research company",
            ],
        }

    def _handle_skill_question(self, question: str, profile: UserProfile) -> dict:
        """Handle questions about skills and learning."""
        skills = profile.all_skills

        # Identify skill gaps based on job market
        market_demand = [
            "python",
            "javascript",
            "react",
            "aws",
            "docker",
            "kubernetes",
            "typescript",
            "node.js",
        ]
        missing_demand = [s for s in market_demand if s not in skills]

        answer = f"""Here's your skill analysis:

**Your Current Skills:** {', '.join(skills[:10])}

**High-Demand Skills You're Missing:**
{chr(10).join('- ' + s for s in missing_demand[:5]) if missing_demand else '- You have all high-demand skills!'}

**Skill Development Priority:**
1. Fill gaps in high-demand skills
2. Deepen expertise in your strongest areas
3. Learn complementary technologies
4. Stay updated with industry trends

**Learning Resources:**
- FreeCodeCamp (free courses)
- Coursera (professional certificates)
- YouTube (tutorials)
- GitHub Projects (hands-on practice)
- Documentation (official resources)"""

        return {
            "question": question,
            "answer": answer,
            "context": {
                "current_skills": len(skills),
                "missing_demand": len(missing_demand),
            },
            "suggestions": missing_demand[:3],
        }

    def _handle_general_question(self, question: str, profile: UserProfile) -> dict:
        """Handle general career questions."""
        answer = f"""Here's my analysis based on your profile:

**Your Profile Summary:**
- {len(profile.all_skills)} technical skills
- {profile.experience_years} years experience
- Preferred roles: {', '.join(profile.preferred_roles) if profile.preferred_roles else 'Not specified'}
- Remote preference: {profile.remote_preference}

**Career Recommendations:**
1. Continue building your skill set
2. Apply to roles that match 60%+ of your skills
3. Network with professionals in your target field
4. Stay updated with industry trends
5. Consider certifications for career advancement

**Next Steps:**
- Use the Resume Analyzer to improve your resume
- Check the Job Search for matching opportunities
- Review the Skill Gap Analysis for improvement areas
- Try the Interview Prep for practice questions"""

        return {
            "question": question,
            "answer": answer,
            "context": {"skills": len(profile.all_skills)},
            "suggestions": ["Improve resume", "Search jobs", "Practice interviews"],
        }
