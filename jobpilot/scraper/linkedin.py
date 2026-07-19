"""LinkedIn Jobs scraper using public job search."""

import logging
from jobpilot.scraper.base import BaseScraper
from jobpilot.models import JobListing

logger = logging.getLogger(__name__)


class LinkedInScraper(BaseScraper):
    source_name = "linkedin"
    base_url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"

    async def search(self, query: str, location: str = "", **kwargs) -> list[JobListing]:
        jobs = []
        try:
            start = kwargs.get("start", 0)
            url = f"{self.base_url}?keywords={query}&location={location}&start={start}"
            response = await self._fetch(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, "html.parser")
            for card in soup.select("li"):
                title_el = card.select_one("h3.base-card__full-link")
                company_el = card.select_one("h4.base-search-card__subtitle")
                location_el = card.select_one("span.job-search-card__location")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                company = company_el.get_text(strip=True) if company_el else "Unknown"
                loc = location_el.get_text(strip=True) if location_el else ""
                job_url = title_el.get("href", "").split("?")[0]
                skills = self._extract_skills(card.get_text())
                remote_status = "remote" if "remote" in loc.lower() else ("hybrid" if "hybrid" in loc.lower() else "onsite")
                jobs.append(JobListing(
                    company=company, title=title, location=loc,
                    remote_status=remote_status, required_skills=skills,
                    url=job_url, source="linkedin", tech_stack=skills,
                    application_url=job_url,
                ))
        except Exception as e:
            logger.warning(f"LinkedIn scrape failed: {e}")
        logger.info(f"LinkedIn: found {len(jobs)} jobs")
        return jobs
