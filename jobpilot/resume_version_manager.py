"""Resume Version Manager for JobPilot."""

from typing import Optional
from jobpilot import database as db
from jobpilot.config import DB_PATH
from jobpilot.resume_analyzer import analyze_resume


class ResumeVersionManager:
    """Manage multiple resume versions with comparison."""

    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH

    def create_version(self, user_id: int, name: str, raw_text: str,
                       notes: str = "", original_resume_id: str = "") -> dict:
        """
        Create a new resume version.

        Returns dict with version details and analysis.
        """
        # Analyze the resume
        analysis = analyze_resume(raw_text)

        # Get next version number
        existing = db.get_resume_versions(user_id, self.db_path)
        version_number = len(existing) + 1

        # Save to database
        version_id = db.save_resume_version(
            user_id=user_id,
            name=name,
            version_number=version_number,
            original_resume_id=original_resume_id,
            raw_text=raw_text,
            ats_score=analysis.ats_score,
            match_rate=analysis.hiring_readiness_score,
            skills=analysis.skills,
            notes=notes,
            db_path=self.db_path,
        )

        return {
            "id": version_id,
            "name": name,
            "version_number": version_number,
            "ats_score": analysis.ats_score,
            "match_rate": analysis.hiring_readiness_score,
            "skills": analysis.skills,
            "strengths": analysis.strengths,
            "weaknesses": analysis.weaknesses,
            "suggestions": analysis.suggestions,
        }

    def get_versions(self, user_id: int) -> list[dict]:
        """Get all resume versions for a user."""
        return db.get_resume_versions(user_id, self.db_path)

    def compare_versions(self, version_id_1: int, version_id_2: int) -> dict:
        """
        Compare two resume versions.

        Returns dict with comparison results.
        """
        versions = db.get_resume_versions(user_id=1, db_path=self.db_path)

        v1 = next((v for v in versions if v["id"] == version_id_1), None)
        v2 = next((v for v in versions if v["id"] == version_id_2), None)

        if not v1 or not v2:
            return {"error": "One or both versions not found"}

        # Compare ATS scores
        ats_diff = v2["ats_score"] - v1["ats_score"]

        # Compare match rates
        match_diff = v2["match_rate"] - v1["match_rate"]

        # Compare skills
        skills_v1 = set(json.loads(v1["skills"]) if isinstance(v1["skills"], str) else v1["skills"])
        skills_v2 = set(json.loads(v2["skills"]) if isinstance(v2["skills"], str) else v2["skills"])
        new_skills = skills_v2 - skills_v1
        removed_skills = skills_v1 - skills_v2

        return {
            "version_1": {
                "id": v1["id"],
                "name": v1["name"],
                "version": v1["version_number"],
                "ats_score": v1["ats_score"],
                "match_rate": v1["match_rate"],
                "skills_count": len(skills_v1),
            },
            "version_2": {
                "id": v2["id"],
                "name": v2["name"],
                "version": v2["version_number"],
                "ats_score": v2["ats_score"],
                "match_rate": v2["match_rate"],
                "skills_count": len(skills_v2),
            },
            "comparison": {
                "ats_score_change": round(ats_diff, 3),
                "match_rate_change": round(match_diff, 3),
                "new_skills": list(new_skills),
                "removed_skills": list(removed_skills),
                "improved": ats_diff > 0,
            },
            "recommendation": self._generate_comparison_recommendation(ats_diff, match_diff, new_skills),
        }

    def _generate_comparison_recommendation(self, ats_diff: float, match_diff: float,
                                            new_skills: set) -> str:
        """Generate recommendation based on comparison."""
        if ats_diff > 0 and match_diff > 0:
            return "The newer version is better in both ATS score and match rate. Use it!"
        elif ats_diff > 0:
            return "The newer version has a better ATS score but lower match rate. Consider combining strengths."
        elif match_diff > 0:
            return "The newer version has a better match rate but lower ATS score. Review formatting."
        else:
            return "The older version performs better. Consider reverting or making further improvements."

    def delete_version(self, version_id: int) -> bool:
        """Delete a resume version."""
        return db.delete_resume_version(version_id, self.db_path)
