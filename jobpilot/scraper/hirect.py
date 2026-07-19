"""Hirect job board scraper."""

import logging
import ssl
from jobpilot.scraper.base import BaseScraper
from jobpilot.models import JobListing

logger = logging.getLogger(__name__)


class HirectScraper(BaseScraper):
    source_name = "hirect"
    base_url = "https://hirect.in/api/v1/search"

    async def search(
        self, query: str, location: str = "", **kwargs
    ) -> list[JobListing]:
        jobs = []
        try:
            url = f"{self.base_url}?query={query}&limit=50"
            response = await self._fetch(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Content-Type": "application/json",
                },
            )
            data = response.json()
            for job_data in data.get("data", data.get("jobs", [])):
                title = job_data.get("title", "")
                company = job_data.get(
                    "companyName", job_data.get("company", "Unknown")
                )
                loc = job_data.get("location", "")
                if location and location.lower() not in loc.lower():
                    continue
                desc = job_data.get("description", "")
                skills = self._extract_skills(desc)
                job_url = f"https://hirect.in/job/{job_data.get('id', '')}"
                remote_status = "remote" if "remote" in loc.lower() else "onsite"
                jobs.append(
                    JobListing(
                        company=company,
                        title=title,
                        location=loc,
                        remote_status=remote_status,
                        required_skills=skills,
                        description=desc[:500],
                        url=job_url,
                        source="hirect",
                        tech_stack=skills,
                        application_url=job_url,
                    )
                )
        except Exception as e:
            logger.warning(f"Hirect scrape failed: {e}")
        logger.info(f"Hirect: found {len(jobs)} jobs")
        return jobs
