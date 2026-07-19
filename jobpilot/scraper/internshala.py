"""Internshala job board scraper."""

import logging
from jobpilot.scraper.base import BaseScraper
from jobpilot.models import JobListing

logger = logging.getLogger(__name__)


class InternshalaScraper(BaseScraper):
    source_name = "internshala"
    base_url = "https://internshala.com/jobs"

    async def search(
        self, query: str, location: str = "", **kwargs
    ) -> list[JobListing]:
        jobs = []
        try:
            url = f"{self.base_url}?keyword={query}"
            response = await self._fetch(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
            )
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(response.text, "html.parser")
            for card in soup.select(
                "div.job-internship-card, div.individual_internship"
            ):
                title_el = card.select_one("a.job-title, h3.job-title")
                company_el = card.select_one("p.company-name, div.company-name")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                company = company_el.get_text(strip=True) if company_el else "Unknown"
                job_url = title_el.get("href", "")
                if job_url and not job_url.startswith("http"):
                    job_url = f"https://internshala.com{job_url}"
                loc_el = card.select_one("div.location, span.location")
                loc = loc_el.get_text(strip=True) if loc_el else ""
                skills = self._extract_skills(card.get_text())
                jobs.append(
                    JobListing(
                        company=company,
                        title=title,
                        location=loc or "India",
                        remote_status="remote" if "remote" in loc.lower() else "onsite",
                        employment_type="internship",
                        required_skills=skills,
                        url=job_url,
                        source="internshala",
                        tech_stack=skills,
                        application_url=job_url,
                    )
                )
        except Exception as e:
            logger.warning(f"Internshala scrape failed: {e}")
        logger.info(f"Internshala: found {len(jobs)} jobs")
        return jobs
