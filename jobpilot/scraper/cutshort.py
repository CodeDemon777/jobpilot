"""Cutshort job board scraper."""

import logging
from jobpilot.scraper.base import BaseScraper
from jobpilot.models import JobListing

logger = logging.getLogger(__name__)


class CutshortScraper(BaseScraper):
    source_name = "cutshort"
    base_url = "https://api.cutshort.io/job"

    async def search(
        self, query: str, location: str = "", **kwargs
    ) -> list[JobListing]:
        jobs = []
        try:
            url = f"{self.base_url}?search={query}&limit=50"
            response = await self._fetch(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Content-Type": "application/json",
                },
            )
            data = response.json()
            for job_data in data.get("jobs", data.get("data", [])):
                title = job_data.get("title", "")
                company = (
                    job_data.get("company", {}).get("name", "Unknown")
                    if isinstance(job_data.get("company"), dict)
                    else job_data.get("companyName", "Unknown")
                )
                loc = job_data.get("location", "")
                if location and location.lower() not in loc.lower():
                    continue
                desc = job_data.get("description", "")
                skills = job_data.get("skills", []) or self._extract_skills(desc)
                job_url = job_data.get(
                    "url", f"https://cutshort.io/company/{job_data.get('slug', '')}"
                )
                remote_status = "remote" if "remote" in loc.lower() else "onsite"
                jobs.append(
                    JobListing(
                        company=company,
                        title=title,
                        location=loc,
                        remote_status=remote_status,
                        required_skills=skills if isinstance(skills, list) else [],
                        description=desc[:500],
                        url=job_url,
                        source="cutshort",
                        tech_stack=skills if isinstance(skills, list) else [],
                        application_url=job_url,
                    )
                )
        except Exception as e:
            logger.warning(f"Cutshort scrape failed: {e}")
        logger.info(f"Cutshort: found {len(jobs)} jobs")
        return jobs
