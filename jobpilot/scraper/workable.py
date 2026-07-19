"""Workable job board scraper."""

import logging
from jobpilot.scraper.base import BaseScraper
from jobpilot.models import JobListing

logger = logging.getLogger(__name__)

KNOWN_WORKABLE_BOARDS = {
    "workable": "workable",
}


class WorkableScraper(BaseScraper):
    source_name = "workable"
    base_url = "https://boards-api.workable.com/v1/accounts"

    async def search(
        self, query: str, location: str = "", **kwargs
    ) -> list[JobListing]:
        board_tokens = kwargs.get("boards", list(KNOWN_WORKABLE_BOARDS.values()))
        query_lower = query.lower()
        jobs = []
        for token in board_tokens:
            try:
                url = f"{self.base_url}/{token}/jobs"
                response = await self._fetch(url)
                data = response.json()
                for job_data in data.get("jobs", []):
                    title = job_data.get("title", "")
                    if query_lower and query_lower not in title.lower():
                        continue
                    loc = job_data.get("location", {})
                    loc_name = (
                        loc.get("city", "") + ", " + loc.get("region", "")
                        if isinstance(loc, dict)
                        else str(loc)
                    )
                    if location and location.lower() not in loc_name.lower():
                        continue
                    job_url = job_data.get("url", "")
                    desc = job_data.get("description", "")
                    skills = self._extract_skills(desc)
                    remote_status = (
                        "remote" if "remote" in loc_name.lower() else "onsite"
                    )
                    jobs.append(
                        JobListing(
                            company=token.title(),
                            title=title,
                            location=loc_name,
                            remote_status=remote_status,
                            required_skills=skills,
                            description=desc[:500],
                            url=job_url,
                            source="workable",
                            tech_stack=skills,
                            application_url=job_url,
                        )
                    )
            except Exception as e:
                logger.warning(f"Workable board '{token}' failed: {e}")
        logger.info(f"Workable: found {len(jobs)} jobs")
        return jobs
