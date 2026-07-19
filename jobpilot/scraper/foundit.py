"""Foundit (formerly Monster India) job board scraper."""

import logging
from jobpilot.scraper.base import BaseScraper
from jobpilot.models import JobListing

logger = logging.getLogger(__name__)


class FounditScraper(BaseScraper):
    source_name = "foundit"
    base_url = "https://www.foundit.in/api/search"

    async def search(self, query: str, location: str = "", **kwargs) -> list[JobListing]:
        jobs = []
        try:
            import json
            url = f"https://www.foundit.in/search/{query.replace(' ', '-')}"
            response = await self._fetch(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, "html.parser")
            for card in soup.select("div.card-container, div.srp-card"):
                title_el = card.select_one("a.title, h2.title")
                company_el = card.select_one("div.company-name, span.company")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                company = company_el.get_text(strip=True) if company_el else "Unknown"
                loc_el = card.select_one("div.location, span.location")
                loc = loc_el.get_text(strip=True) if loc_el else ""
                job_url = title_el.get("href", "")
                if job_url and not job_url.startswith("http"):
                    job_url = f"https://www.foundit.in{job_url}"
                skills = self._extract_skills(card.get_text())
                remote_status = "remote" if "remote" in loc.lower() else "onsite"
                jobs.append(JobListing(
                    company=company, title=title, location=loc,
                    remote_status=remote_status, required_skills=skills,
                    url=job_url, source="foundit", tech_stack=skills,
                    application_url=job_url,
                ))
        except Exception as e:
            logger.warning(f"Foundit scrape failed: {e}")
        logger.info(f"Foundit: found {len(jobs)} jobs")
        return jobs
