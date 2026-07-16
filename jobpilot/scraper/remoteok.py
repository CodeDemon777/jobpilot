"""RemoteOK job board scraper.

RemoteOK provides a public JSON API at: https://remoteok.com/api
"""

import logging

from jobpilot.scraper.base import BaseScraper
from jobpilot.models import JobListing

logger = logging.getLogger(__name__)


class RemoteOKScraper(BaseScraper):
    source_name = "remoteok"
    base_url = "https://remoteok.com/api"

    async def search(self, query: str, location: str = "", **kwargs) -> list[JobListing]:
        """Search RemoteOK for matching remote jobs."""
        try:
            response = await self._fetch(
                self.base_url,
                headers={"User-Agent": "JobPilot/0.1"},
            )
            data = response.json()
            query_lower = query.lower()
            jobs = []

            for item in data:
                # Skip metadata entries
                if not isinstance(item, dict) or "id" not in item:
                    continue

                title = item.get("position", "")
                company = item.get("company", "")

                # Filter by query
                if query_lower:
                    if (query_lower not in title.lower()
                            and query_lower not in company.lower()
                            and query_lower not in item.get("description", "").lower()):
                        continue

                job = self._parse_job(item)
                jobs.append(job)

            logger.info(f"RemoteOK: found {len(jobs)} jobs matching '{query}'")
            return jobs

        except Exception as e:
            logger.warning(f"Failed to scrape RemoteOK: {e}")
            return []

    def _parse_job(self, data: dict) -> JobListing:
        """Parse a RemoteOK job listing into a JobListing."""
        title = data.get("position", "")
        company = data.get("company", "")
        description = data.get("description", "")

        # Extract tags as skills
        tags = data.get("tags", [])
        if isinstance(tags, list):
            skills = [str(t).lower() for t in tags]
        else:
            skills = self._extract_skills(description)

        # Parse salary
        salary_min = data.get("salary_min", 0) or 0
        salary_max = data.get("salary_max", 0) or 0

        # Build URL
        slug = data.get("slug", "")
        job_url = data.get("url", f"https://remoteok.com/remote-jobs/{slug}")

        # Parse date
        date = data.get("date", "")

        return JobListing(
            company=company,
            title=title,
            location="Remote",
            remote_status="remote",
            employment_type="full-time",
            salary_min=salary_min,
            salary_max=salary_max,
            required_skills=skills,
            description=description,
            url=job_url,
            source="remoteok",
            posted_date=date,
            application_url=job_url,
            tech_stack=skills,
        )
