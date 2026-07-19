"""We Work Remotely job board scraper."""

import logging
from jobpilot.scraper.base import BaseScraper
from jobpilot.models import JobListing

logger = logging.getLogger(__name__)


class WeWorkRemotelyScraper(BaseScraper):
    source_name = "weworkremotely"
    base_url = "https://weworkremotely.com/remote-jobs/search"

    async def search(
        self, query: str, location: str = "", **kwargs
    ) -> list[JobListing]:
        jobs = []
        try:
            url = f"{self.base_url}?term={query}"
            response = await self._fetch(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
            )
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(response.text, "html.parser")
            for card in soup.select("li.feature"):
                title_el = card.select_one("a span.company-and-title strong")
                company_el = card.select_one("span.company-and-title span")
                if not title_el:
                    title_el = card.select_one("a span")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                company = company_el.get_text(strip=True) if company_el else "Unknown"
                link = card.select_one("a")
                job_url = (
                    f"https://weworkremotely.com{link['href']}"
                    if link and link.get("href")
                    else ""
                )
                skills = self._extract_skills(card.get_text())
                jobs.append(
                    JobListing(
                        company=company,
                        title=title,
                        location="Remote",
                        remote_status="remote",
                        required_skills=skills,
                        url=job_url,
                        source="weworkremotely",
                        tech_stack=skills,
                        application_url=job_url,
                    )
                )
        except Exception as e:
            logger.warning(f"WeWorkRemotely scrape failed: {e}")
        logger.info(f"WeWorkRemotely: found {len(jobs)} jobs")
        return jobs
