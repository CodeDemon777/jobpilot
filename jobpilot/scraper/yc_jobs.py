"""Y Combinator Jobs scraper."""

import logging
from jobpilot.scraper.base import BaseScraper
from jobpilot.models import JobListing

logger = logging.getLogger(__name__)


class YCJobsScraper(BaseScraper):
    source_name = "yc_jobs"
    base_url = "https://www.workatastartup.com/jobs"

    async def search(
        self, query: str, location: str = "", **kwargs
    ) -> list[JobListing]:
        jobs = []
        try:
            url = f"{self.base_url}?q={query}"
            response = await self._fetch(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
            )
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(response.text, "html.parser")
            for card in soup.select("div.job-listing, div.job-card, tr.job-row"):
                title_el = card.select_one("a, h3, h2")
                company_el = card.select_one("span.company, div.company-name")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                company = company_el.get_text(strip=True) if company_el else "Unknown"
                href = title_el.get("href", "")
                job_url = (
                    f"https://www.workatastartup.com{href}"
                    if href.startswith("/")
                    else href
                )
                skills = self._extract_skills(card.get_text())
                jobs.append(
                    JobListing(
                        company=company,
                        title=title,
                        location=location or "Remote",
                        remote_status="remote",
                        required_skills=skills,
                        url=job_url,
                        source="yc_jobs",
                        tech_stack=skills,
                        application_url=job_url,
                    )
                )
        except Exception as e:
            logger.warning(f"YC Jobs scrape failed: {e}")
        logger.info(f"YC Jobs: found {len(jobs)} jobs")
        return jobs
