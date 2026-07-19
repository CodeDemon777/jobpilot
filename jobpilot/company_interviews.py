"""Company Interview Experience module for JobPilot."""

import json
from typing import Optional
from jobpilot import database as db
from jobpilot.config import DB_PATH


# Pre-loaded interview experiences for popular companies
PRELOADED_INTERVIEWS = {
    "google": {
        "company": "Google",
        "roles": ["Software Engineer", "SRE", "Data Engineer"],
        "typical_rounds": [
            {"round": 1, "type": "Phone Screen", "duration": "45 min", "topics": ["Coding basics", "Resume discussion"]},
            {"round": 2, "type": "Technical Phone Screen", "duration": "60 min", "topics": ["Data structures", "Algorithms", "System design basics"]},
            {"round": 3, "type": "Onsite - Coding", "duration": "45 min", "topics": ["DSA problems", "Optimization", "Edge cases"]},
            {"round": 4, "type": "Onsite - System Design", "duration": "45 min", "topics": ["Distributed systems", "Scalability", "Trade-offs"]},
            {"round": 5, "type": "Onsite - Behavioral", "duration": "45 min", "topics": ["Leadership", "Googleyness", "Conflict resolution"]},
        ],
        "difficulty": 5,
        "common_questions": [
            "Design a URL shortener like bit.ly",
            "Implement LRU cache",
            "Given a binary tree, find the lowest common ancestor",
            "Design a chat system",
            "How would you scale a notification system?",
        ],
        "tips": [
            "Practice LeetCode medium/hard problems",
            "Study system design fundamentals",
            "Use the STAR method for behavioral questions",
            "Research Google's products and culture",
        ],
        "salary_range": "$150,000 - $250,000",
    },
    "microsoft": {
        "company": "Microsoft",
        "roles": ["Software Engineer", "SDE", "Program Manager"],
        "typical_rounds": [
            {"round": 1, "type": "Phone Screen", "duration": "30 min", "topics": ["Resume review", "Basic technical questions"]},
            {"round": 2, "type": "Technical Interview", "duration": "60 min", "topics": ["Coding problem", "Object-oriented design"]},
            {"round": 3, "type": "Onsite Interviews", "duration": "4-5 hours", "topics": ["Coding", "System design", "Behavioral", "Azure knowledge"]},
        ],
        "difficulty": 4,
        "common_questions": [
            "Design a parking lot system",
            "Implement a producer-consumer pattern",
            "Design a URL shortener",
            "How do you handle technical debt?",
            "Describe a challenging project you worked on",
        ],
        "tips": [
            "Know Microsoft products (Azure, Office 365, Teams)",
            "Practice object-oriented design",
            "Prepare for behavioral questions about collaboration",
            "Show growth mindset",
        ],
        "salary_range": "$120,000 - $200,000",
    },
    "amazon": {
        "company": "Amazon",
        "roles": ["Software Development Engineer", "SDE", "Data Engineer"],
        "typical_rounds": [
            {"round": 1, "type": "Online Assessment", "duration": "90 min", "topics": ["Coding problems", "Work style assessment"]},
            {"round": 2, "type": "Phone Interview", "duration": "60 min", "topics": ["Coding", "Leadership Principles"]},
            {"round": 3, "type": "Onsite (5 rounds)", "duration": "5-6 hours", "topics": ["Coding", "System design", "Behavioral (LP-focused)"]},
        ],
        "difficulty": 4,
        "common_questions": [
            "Tell me about a time you disagreed with a decision",
            "Describe a situation where you had to make a quick decision",
            "Design a distributed cache system",
            "How do you prioritize tasks?",
            "Tell me about a failure and what you learned",
        ],
        "tips": [
            "Study Amazon Leadership Principles thoroughly",
            "Use STAR method for every behavioral answer",
            "Quantify achievements with numbers",
            "Show customer obsession in your examples",
        ],
        "salary_range": "$130,000 - $220,000",
    },
    "meta": {
        "company": "Meta",
        "roles": ["Software Engineer", "Data Scientist", "ML Engineer"],
        "typical_rounds": [
            {"round": 1, "type": "Phone Screen", "duration": "45 min", "topics": ["Technical screening", "Resume discussion"]},
            {"round": 2, "type": "Onsite (4 rounds)", "duration": "4-5 hours", "topics": ["Coding (2 rounds)", "System design", "Behavioral"]},
        ],
        "difficulty": 4,
        "common_questions": [
            "Design a news feed system",
            "Implement a function to find all pairs that sum to a target",
            "Design a messaging system like Messenger",
            "How would you handle a sudden traffic spike?",
            "Describe a time you had to make a difficult technical decision",
        ],
        "tips": [
            "Practice coding problems on LeetCode",
            "Study distributed systems fundamentals",
            "Be ready to discuss your impact and metrics",
            "Show you care about connecting people",
        ],
        "salary_range": "$140,000 - $230,000",
    },
    "apple": {
        "company": "Apple",
        "roles": ["Software Engineer", "iOS Developer", "Backend Engineer"],
        "typical_rounds": [
            {"round": 1, "type": "Phone Screen", "duration": "30 min", "topics": ["Technical basics", "Resume review"]},
            {"round": 2, "type": "Technical Interview", "duration": "60 min", "topics": ["Coding", "System design"]},
            {"round": 3, "type": "Onsite (4-5 rounds)", "duration": "4-5 hours", "topics": ["Coding", "System design", "Behavioral", "Domain-specific"]},
        ],
        "difficulty": 4,
        "common_questions": [
            "Design a file storage system",
            "Implement a thread-safe queue",
            "How would you optimize a slow API?",
            "Describe your most impactful project",
            "How do you handle ambiguity in requirements?",
        ],
        "tips": [
            "Show attention to detail and quality",
            "Demonstrate passion for Apple products",
            "Practice system design problems",
            "Prepare for cross-functional collaboration questions",
        ],
        "salary_range": "$135,000 - $210,000",
    },
}


class CompanyInterviewManager:
    """Manage company interview experiences."""

    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH

    def get_interview_info(self, company: str) -> dict:
        """
        Get interview information for a company.

        Returns pre-loaded data if available, otherwise database records.
        """
        company_lower = company.lower()

        # Check pre-loaded data first
        if company_lower in PRELOADED_INTERVIEWS:
            preloaded = PRELOADED_INTERVIEWS[company_lower]

            # Also get community submissions
            community = db.get_company_interviews(company_lower, self.db_path)

            return {
                "company": preloaded["company"],
                "typical_rounds": preloaded["typical_rounds"],
                "difficulty": preloaded["difficulty"],
                "common_questions": preloaded["common_questions"],
                "tips": preloaded["tips"],
                "salary_range": preloaded["salary_range"],
                "community_experiences": len(community),
                "is_preloaded": True,
            }

        # Fall back to community data
        experiences = db.get_company_interviews(company_lower, self.db_path)

        if not experiences:
            return {
                "company": company,
                "message": "No interview data available for this company yet.",
                "is_preloaded": False,
                "community_experiences": 0,
            }

        # Aggregate community data
        avg_difficulty = sum(e["difficulty"] for e in experiences) / len(experiences)
        all_questions = []
        for e in experiences:
            try:
                questions = json.loads(e["questions"]) if isinstance(e["questions"], str) else e["questions"]
                all_questions.extend(questions)
            except:
                pass

        return {
            "company": company,
            "difficulty": round(avg_difficulty, 1),
            "community_experiences": len(experiences),
            "common_questions": list(set(all_questions))[:10],
            "is_preloaded": False,
        }

    def submit_experience(self, company: str, role: str, difficulty: int,
                          rounds: list, questions: list, experience_text: str,
                          tips: str, salary_range: str, user_id: int) -> int:
        """Submit a new interview experience."""
        return db.save_company_interview(
            company=company.lower(),
            role=role,
            difficulty=difficulty,
            rounds=rounds,
            questions=questions,
            experience_text=experience_text,
            tips=tips,
            salary_range=salary_range,
            user_id=user_id,
            db_path=self.db_path,
        )

    def get_all_companies(self) -> list[dict]:
        """Get list of all companies with interview data."""
        # Combine pre-loaded and community data
        companies = list(PRELOADED_INTERVIEWS.keys())

        # Get community companies
        community = db.get_company_interviews(db_path=self.db_path)
        for exp in community:
            if exp["company"] not in companies:
                companies.append(exp["company"])

        return sorted(companies)
