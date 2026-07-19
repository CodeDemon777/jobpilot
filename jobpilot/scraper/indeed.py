"""Indeed job board scraper."""

import logging
from jobpilot.scraper.base import BaseScraper
from jobpilot.models import JobListing

logger = logging.getLogger(__name__)


class IndeedScraper(BaseScraper):
    source_name = "indeed"
    base_url = "https://www.indeed.com/jobs"

    async def search(
        self, query: str, location: str = "", **kwargs
    ) -> list[JobListing]:
        jobs = []
        try:
            params = {"q": query, "l": location, "limit": kwargs.get("limit", 50)}
            url = f"{self.base_url}?q={params['q']}&l={params['l']}"
            response = await self._fetch(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
            )
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(response.text, "html.parser")
            for card in soup.select("div.job_seen_beacon"):
                title_el = card.select_one("h2.jobTitle a")
                company_el = card.select_one("span.companyName")
                location_el = card.select_one("div.companyLocation")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                company = company_el.get_text(strip=True) if company_el else "Unknown"
                loc = location_el.get_text(strip=True) if location_el else ""
                href = title_el.get("href", "")
                job_url = (
                    f"https://www.indeed.com{href}" if href.startswith("/") else href
                )
                skills = self._extract_skills(card.get_text())
                remote_status = (
                    "remote"
                    if "remote" in loc.lower()
                    else ("hybrid" if "hybrid" in loc.lower() else "onsite")
                )
                jobs.append(
                    JobListing(
                        company=company,
                        title=title,
                        location=loc,
                        remote_status=remote_status,
                        required_skills=skills,
                        url=job_url,
                        source="indeed",
                        tech_stack=skills,
                        application_url=job_url,
                    )
                )
        except Exception as e:
            logger.warning(f"Indeed scrape failed: {e}")
        logger.info(f"Indeed: found {len(jobs)} jobs")
        return jobs
