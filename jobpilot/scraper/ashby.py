"""Ashby job board scraper."""

import logging
from jobpilot.scraper.base import BaseScraper
from jobpilot.models import JobListing

logger = logging.getLogger(__name__)

KNOWN_ASHBY_BOARDS = {
    "ashby": "ashby",
}


class AshbyScraper(BaseScraper):
    source_name = "ashby"
    base_url = "https://jobs.ashbyhq.com/api/non-user-graphql?op=ApiJobBoardWithTeams"

    async def search(self, query: str, location: str = "", **kwargs) -> list[JobListing]:
        board_tokens = kwargs.get("boards", list(KNOWN_ASHBY_BOARDS.values()))
        query_lower = query.lower()
        jobs = []
        for token in board_tokens:
            try:
                import json
                payload = json.dumps({
                    "operationName": "ApiJobBoardWithTeams",
                    "variables": {"organizationHostedJobsPageName": token},
                    "query": "query ApiJobBoardWithTeams($organizationHostedJobsPageName: String!) { jobBoard: jobBoardWithTeams(organizationHostedJobsPageName: $organizationHostedJobsPageName) { teams { name jobs { id title locationName employmentType descriptionPlain compensationTierSummary } } } }"
                })
                response = await self._fetch(self.base_url, headers={
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0",
                })
                data = response.json()
                board = data.get("data", {}).get("jobBoard", {})
                for team in board.get("teams", []):
                    for job_data in team.get("jobs", []):
                        title = job_data.get("title", "")
                        if query_lower and query_lower not in title.lower():
                            continue
                        loc = job_data.get("locationName", "")
                        if location and location.lower() not in loc.lower():
                            continue
                        desc = job_data.get("descriptionPlain", "")
                        skills = self._extract_skills(desc)
                        remote_status = "remote" if "remote" in loc.lower() else "onsite"
                        job_url = f"https://jobs.ashbyhq.com/{token}/job/{job_data.get('id', '')}"
                        jobs.append(JobListing(
                            company=token.title(), title=title, location=loc,
                            remote_status=remote_status, required_skills=skills,
                            description=desc[:500], url=job_url, source="ashby",
                            tech_stack=skills, application_url=job_url,
                        ))
            except Exception as e:
                logger.warning(f"Ashby board '{token}' failed: {e}")
        logger.info(f"Ashby: found {len(jobs)} jobs")
        return jobs
