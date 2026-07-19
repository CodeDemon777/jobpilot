"""Lever job board scraper (similar to Greenhouse)."""

import logging
from jobpilot.scraper.base import BaseScraper
from jobpilot.models import JobListing

logger = logging.getLogger(__name__)

# Known companies using Lever ATS
KNOWN_LEVER_BOARDS = {
    "lever": "lever",
    "netflix": "netflix",
    "segment": "segment",
    "plaid": "plaid",
    "postmates": "postmates",
    "upstart": "upstart",
    "databricks": "databricks",
    "gitlab": "gitlab",
    "cloudflare": "cloudflare",
    "figma": "figma",
    "discord": "discord",
    "twitch": "twitch",
    "spotify": "spotify",
    "shopify": "shopify",
}


class LeverScraper(BaseScraper):
    source_name = "lever"
    base_url = "https://api.lever.co/v0/postings"

    async def search(self, query: str, location: str = "", **kwargs) -> list[JobListing]:
        board_tokens = kwargs.get("boards", list(KNOWN_LEVER_BOARDS.values()))
        query_lower = query.lower()
        jobs = []
        for token in board_tokens:
            try:
                url = f"{self.base_url}/{token}?mode=json"
                response = await self._fetch(url)
                data = response.json()
                for job_data in data:
                    title = job_data.get("text", "")
                    if query_lower and query_lower not in title.lower():
                        continue
                    categories = job_data.get("categories", {})
                    loc = categories.get("office", "") or categories.get("team", "")
                    if location and location.lower() not in loc.lower():
                        continue
                    job_url = job_data.get("hostedUrl", "")
                    desc = job_data.get("descriptionPlain", "")
                    skills = self._extract_skills(desc)
                    remote_status = "remote" if "remote" in loc.lower() else "onsite"
                    jobs.append(JobListing(
                        company=token.title(), title=title, location=loc,
                        remote_status=remote_status, required_skills=skills,
                        description=desc[:500], url=job_url, source="lever",
                        tech_stack=skills, application_url=job_url,
                    ))
            except Exception as e:
                logger.warning(f"Lever board '{token}' failed: {e}")
        logger.info(f"Lever: found {len(jobs)} jobs")
        return jobs
