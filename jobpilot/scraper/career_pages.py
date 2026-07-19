"""Generic career page scraper for company career sites."""

import logging
from jobpilot.scraper.base import BaseScraper
from jobpilot.models import JobListing

logger = logging.getLogger(__name__)

# Common career page patterns
KNOWN_CAREER_PAGES = {
    "google": "https://www.google.com/about/careers/applications/jobs/results",
    "microsoft": "https://careers.microsoft.com/v2/global/en/search",
    "amazon": "https://www.amazon.jobs/en/search",
    "apple": "https://www.apple.com/careers/us/search.html",
    "meta": "https://www.metacareers.com/jobs",
}


class CareerPagesScraper(BaseScraper):
    source_name = "career_pages"
    base_url = ""

    async def search(
        self, query: str, location: str = "", **kwargs
    ) -> list[JobListing]:
        company_urls = kwargs.get("company_urls", KNOWN_CAREER_PAGES)
        query_lower = query.lower()
        jobs = []
        for company, url in company_urls.items():
            try:
                search_url = (
                    f"{url}?q={query}" if "?" not in url else f"{url}&q={query}"
                )
                response = await self._fetch(
                    search_url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    },
                )
                from bs4 import BeautifulSoup

                soup = BeautifulSoup(response.text, "html.parser")
                for card in soup.select(
                    "a[href*='job'], div[class*='job'], tr[class*='job'], li[class*='job']"
                ):
                    title_el = card.select_one(
                        "h2, h3, span[class*='title'], a[class*='title']"
                    )
                    if not title_el:
                        title_text = card.get_text(strip=True)
                        if len(title_text) < 5 or len(title_text) > 200:
                            continue
                        title = title_text[:100]
                    else:
                        title = title_el.get_text(strip=True)
                    if query_lower and query_lower not in title.lower():
                        continue
                    href = card.get("href", "") or (
                        title_el.get("href", "") if title_el else ""
                    )
                    if href and not href.startswith("http"):
                        href = f"{url.rsplit('/', 1)[0]}{href}"
                    loc = "Unknown"
                    skills = self._extract_skills(card.get_text())
                    jobs.append(
                        JobListing(
                            company=company.title(),
                            title=title,
                            location=loc,
                            remote_status="unknown",
                            required_skills=skills,
                            url=href,
                            source="career_pages",
                            tech_stack=skills,
                            application_url=href,
                        )
                    )
            except Exception as e:
                logger.warning(f"Career page '{company}' failed: {e}")
        logger.info(f"Career Pages: found {len(jobs)} jobs")
        return jobs
