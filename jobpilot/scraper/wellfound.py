"""Wellfound (AngelList) job board scraper."""

import logging
from jobpilot.scraper.base import BaseScraper
from jobpilot.models import JobListing

logger = logging.getLogger(__name__)


class WellfoundScraper(BaseScraper):
    source_name = "wellfound"
    base_url = "https://wellfound.com/role/r"

    async def search(
        self, query: str, location: str = "", **kwargs
    ) -> list[JobListing]:
        jobs = []
        try:
            url = f"https://wellfound.com/role/r/{query.replace(' ', '-')}"
            if location:
                url += f"/{location.replace(' ', '-')}"
            response = await self._fetch(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
            )
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(response.text, "html.parser")
            for card in soup.select(
                "div.styles_jobList__lqjPr a, div[data-test=JobListing]"
            ):
                title_el = card.select_one("h2, span.styles_title__dAoph")
                company_el = card.select_one(
                    "span.styles_companyName__mWtvj, span[data-test=company-name]"
                )
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                company = company_el.get_text(strip=True) if company_el else "Unknown"
                job_url = card.get("href", "")
                if job_url and not job_url.startswith("http"):
                    job_url = f"https://wellfound.com{job_url}"
                skills = self._extract_skills(card.get_text())
                jobs.append(
                    JobListing(
                        company=company,
                        title=title,
                        location=location or "Remote",
                        remote_status="remote",
                        required_skills=skills,
                        url=job_url,
                        source="wellfound",
                        tech_stack=skills,
                        application_url=job_url,
                    )
                )
        except Exception as e:
            logger.warning(f"Wellfound scrape failed: {e}")
        logger.info(f"Wellfound: found {len(jobs)} jobs")
        return jobs
