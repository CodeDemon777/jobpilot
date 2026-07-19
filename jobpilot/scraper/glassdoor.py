"""Glassdoor job board scraper."""

import logging
from jobpilot.scraper.base import BaseScraper
from jobpilot.models import JobListing

logger = logging.getLogger(__name__)


class GlassdoorScraper(BaseScraper):
    source_name = "glassdoor"
    base_url = "https://www.glassdoor.com/Job/jobs.htm"

    async def search(
        self, query: str, location: str = "", **kwargs
    ) -> list[JobListing]:
        jobs = []
        try:
            url = f"{self.base_url}?sc.keyword={query}&locT=&locId=&locKeyword=&jobAge=0&radius=100"
            if location:
                url += f"&locT=&locId=&locKeyword={location}"
            response = await self._fetch(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
            )
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(response.text, "html.parser")
            for card in soup.select(
                "li.JobsList_jobListItem__wjTH, li[data-test='jobListing']"
            ):
                title_el = card.select_one(
                    "a[data-test='job-title'], a.JobCard_jobTitle__GLyJ"
                )
                company_el = card.select_one(
                    "a.EmployerProfile_compactEmployerName__LE242, span.EmployerProfile_compactEmployerName__LE242"
                )
                location_el = card.select_one(
                    "div[data-test='emp-location'], div.JobCard_location__rCz3x"
                )
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                company = company_el.get_text(strip=True) if company_el else "Unknown"
                loc = location_el.get_text(strip=True) if location_el else ""
                job_url = title_el.get("href", "")
                if job_url and not job_url.startswith("http"):
                    job_url = f"https://www.glassdoor.com{job_url}"
                skills = self._extract_skills(card.get_text())
                remote_status = "remote" if "remote" in loc.lower() else "onsite"
                jobs.append(
                    JobListing(
                        company=company,
                        title=title,
                        location=loc,
                        remote_status=remote_status,
                        required_skills=skills,
                        url=job_url,
                        source="glassdoor",
                        tech_stack=skills,
                        application_url=job_url,
                    )
                )
        except Exception as e:
            logger.warning(f"Glassdoor scrape failed: {e}")
        logger.info(f"Glassdoor: found {len(jobs)} jobs")
        return jobs
