"""Greenhouse job board scraper.

Many companies use Greenhouse for their ATS. Jobs are available via
public JSON APIs at: https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs
"""

import logging
from html import unescape

from jobpilot.scraper.base import BaseScraper
from jobpilot.models import JobListing

logger = logging.getLogger(__name__)

# Popular companies on Greenhouse — verified board tokens (2024-07)
KNOWN_GREENHOUSE_BOARDS = {
    "discord": "discord",
    "figma": "figma",
    "gitlab": "gitlab",
    "twitch": "twitch",
    "airbnb": "airbnb",
    "databricks": "databricks",
    "lyft": "lyft",
    "pinterest": "pinterest",
    "ubiquiti": "ubiquiti",
    "waymo": "waymo",
}


class GreenhouseScraper(BaseScraper):
    source_name = "greenhouse"
    base_url = "https://boards-api.greenhouse.io/v1/boards"

    async def search(self, query: str, location: str = "", **kwargs) -> list[JobListing]:
        """Search all known Greenhouse boards for matching jobs."""
        board_tokens = kwargs.get("boards", list(KNOWN_GREENHOUSE_BOARDS.values()))
        query_lower = query.lower()
        jobs = []

        for token in board_tokens:
            try:
                url = f"{self.base_url}/{token}/jobs"
                response = await self._fetch(url)
                data = response.json()

                for job_data in data.get("jobs", []):
                    title = job_data.get("title", "")
                    location_name = self._extract_location(job_data)

                    # Filter by query
                    if query_lower and query_lower not in title.lower():
                        # Also check department name
                        dept = job_data.get("departments", [{}])
                        dept_name = dept[0].get("name", "") if dept else ""
                        if query_lower not in dept_name.lower():
                            continue

                    # Filter by location
                    if location and location.lower() not in location_name.lower():
                        if "remote" not in location.lower() or "remote" not in location_name.lower():
                            continue

                    job = self._parse_job(token, job_data, location_name)
                    jobs.append(job)

            except Exception as e:
                logger.warning(f"Failed to scrape Greenhouse board '{token}': {e}")
                continue

        logger.info(f"Greenhouse: found {len(jobs)} jobs matching '{query}'")
        return jobs

    async def get_details(self, url: str) -> JobListing | None:
        """Fetch full job details from a Greenhouse job URL."""
        # URL format: https://boards.greenhouse.io/{board}/jobs/{job_id}
        # API format: https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job_id}
        try:
            parts = url.rstrip("/").split("/")
            board_token = parts[-3] if len(parts) >= 3 else ""
            job_id = parts[-1] if parts else ""
            if not board_token or not job_id:
                return None

            api_url = f"{self.base_url}/{board_token}/jobs/{job_id}"
            response = await self._fetch(api_url)
            data = response.json()
            location_name = self._extract_location(data)
            return self._parse_job(board_token, data, location_name)
        except Exception as e:
            logger.warning(f"Failed to fetch Greenhouse job details: {e}")
            return None

    def _parse_job(self, board_token: str, data: dict, location: str) -> JobListing:
        """Parse a Greenhouse job listing into a JobListing."""
        title = data.get("title", "")
        description = self._clean_html(data.get("content", ""))

        # Extract skills from description
        skills = self._extract_skills(description)

        # Determine remote status
        remote_status = "unknown"
        if "remote" in location.lower():
            remote_status = "remote"
        elif "hybrid" in location.lower():
            remote_status = "hybrid"
        else:
            remote_status = "onsite"

        # Extract department
        departments = data.get("departments", [])
        department = departments[0].get("name", "") if departments else ""

        # Build application URL
        job_id = data.get("id", "")
        application_url = data.get("absolute_url", f"https://boards.greenhouse.io/{board_token}/jobs/{job_id}")

        return JobListing(
            company=board_token.replace("-", " ").title(),
            title=title,
            department=department,
            location=location,
            remote_status=remote_status,
            employment_type="full-time",
            required_skills=skills,
            preferred_skills=[],
            description=description,
            url=application_url,
            source="greenhouse",
            application_url=application_url,
            tech_stack=skills,
        )

    def _extract_location(self, data: dict) -> str:
        """Extract location from job data."""
        locations = data.get("location", {})
        if isinstance(locations, dict):
            return locations.get("name", "Unknown")
        return str(locations) if locations else "Unknown"

    def _clean_html(self, html: str) -> str:
        """Remove HTML tags from content."""
        import re
        text = re.sub(r"<[^>]+>", " ", html)
        text = unescape(text)
        text = re.sub(r"\s+", " ", text).strip()
        return text
