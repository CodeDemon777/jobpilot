"""Naukri.com job board scraper."""

import logging
from jobpilot.scraper.base import BaseScraper
from jobpilot.models import JobListing

logger = logging.getLogger(__name__)


class NaukriScraper(BaseScraper):
    source_name = "naukri"
    base_url = "https://www.naukri.com/jobapi/v3/search"

    async def search(
        self, query: str, location: str = "", **kwargs
    ) -> list[JobListing]:
        jobs = []
        try:
            import json

            url = f"{self.base_url}?noOfResults=20&urlType=search_by_key_loc&searchType=adv&keyword={query}&location={location}"
            response = await self._fetch(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "appId": "109",
                    "systemid": "109",
                },
            )
            data = response.json()
            for job_data in data.get("jobDetails", []):
                title = job_data.get("title", "")
                company = job_data.get("companyName", "Unknown")
                loc = (
                    job_data.get("placeholders", [{}])[0].get("label", "")
                    if job_data.get("placeholders")
                    else ""
                )
                job_url = (
                    f"https://www.naukri.com/jobapi/v3/job/{job_data.get('jobId', '')}"
                )
                skills = self._extract_skills(
                    job_data.get("skillDetails", "") or job_data.get("title", "")
                )
                remote_status = "remote" if "remote" in loc.lower() else "onsite"
                jobs.append(
                    JobListing(
                        company=company,
                        title=title,
                        location=loc,
                        remote_status=remote_status,
                        required_skills=skills,
                        url=job_url,
                        source="naukri",
                        tech_stack=skills,
                        application_url=job_url,
                    )
                )
        except Exception as e:
            logger.warning(f"Naukri scrape failed: {e}")
        logger.info(f"Naukri: found {len(jobs)} jobs")
        return jobs
