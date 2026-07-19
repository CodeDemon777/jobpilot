"""Company Career Pages scraper - Direct API integration with major companies."""

import logging
from jobpilot.scraper.base import BaseScraper
from jobpilot.models import JobListing

logger = logging.getLogger(__name__)

# Major companies with direct career APIs or structured job feeds
COMPANY_CAREERS = {
    "google": {
        "name": "Google",
        "api_url": "https://careers.google.com/api/jobs",
        "search_url": "https://careers.google.com/jobs/results/?q={query}&location={location}",
        "has_api": True,
    },
    "microsoft": {
        "name": "Microsoft",
        "api_url": "https://gcsservices.careers.microsoft.com/search/api/v1/search",
        "search_url": "https://careers.microsoft.com/us/en/search-results?keywords={query}",
        "has_api": True,
    },
    "amazon": {
        "name": "Amazon",
        "api_url": "https://www.amazon.jobs/en/search.json?offset=0&result_limit=10&base_query={query}",
        "search_url": "https://www.amazon.jobs/en/search?base_query={query}",
        "has_api": True,
    },
    "apple": {
        "name": "Apple",
        "search_url": "https://jobs.apple.com/en-us/search?search={query}",
        "has_api": False,
    },
    "meta": {
        "name": "Meta",
        "search_url": "https://www.metacareers.com/jobs?q={query}",
        "has_api": False,
    },
    "netflix": {
        "name": "Netflix",
        "search_url": "https://jobs.netflix.com/search?q={query}",
        "has_api": False,
    },
    "spotify": {
        "name": "Spotify",
        "search_url": "https://www.spotifyjobs.com/en/search?q={query}",
        "has_api": False,
    },
    "uber": {
        "name": "Uber",
        "search_url": "https://www.uber.com/careers/list/?search={query}",
        "has_api": False,
    },
    "airbnb": {
        "name": "Airbnb",
        "search_url": "https://careers.airbnb.com/?q={query}",
        "has_api": False,
    },
    "stripe": {
        "name": "Stripe",
        "search_url": "https://stripe.com/jobs/search?q={query}",
        "has_api": False,
    },
    "shopify": {
        "name": "Shopify",
        "search_url": "https://www.shopify.com/careers/search?q={query}",
        "has_api": False,
    },
    "atlassian": {
        "name": "Atlassian",
        "search_url": "https://www.atlassian.com/company/careers/job-boards?query={query}",
        "has_api": False,
    },
    "salesforce": {
        "name": "Salesforce",
        "search_url": "https://careers.salesforce.com/en/jobs/?search={query}",
        "has_api": False,
    },
    "adobe": {
        "name": "Adobe",
        "search_url": "https://careers.adobe.com/us/en/search-results?keywords={query}",
        "has_api": False,
    },
    "twitter": {
        "name": "Twitter/X",
        "search_url": "https://careers.twitter.com/en/search.html?q={query}",
        "has_api": False,
    },
}


class CompanyCareersScraper(BaseScraper):
    """Scrape company career pages directly."""

    source_name = "company_careers"

    async def search(
        self, query: str, location: str = "", **kwargs
    ) -> list[JobListing]:
        """Search across all configured company career pages."""
        companies = kwargs.get("companies", list(COMPANY_CAREERS.keys()))
        query_lower = query.lower()
        all_jobs = []

        for company_key in companies:
            if company_key not in COMPANY_CAREERS:
                continue

            company_info = COMPANY_CAREERS[company_key]
            try:
                if company_info.get("has_api"):
                    jobs = await self._search_api(
                        company_key, company_info, query, location
                    )
                else:
                    jobs = await self._search_webpage(
                        company_key, company_info, query, location
                    )
                all_jobs.extend(jobs)
            except Exception as e:
                logger.warning(f"Failed to search {company_info['name']}: {e}")

        # Filter by query if needed
        if query_lower:
            all_jobs = [
                j
                for j in all_jobs
                if query_lower in j.title.lower()
                or query_lower in j.description.lower()
            ]

        logger.info(
            f"Company Careers: found {len(all_jobs)} jobs across {len(companies)} companies"
        )
        return all_jobs

    async def _search_api(
        self, company_key: str, company_info: dict, query: str, location: str
    ) -> list[JobListing]:
        """Search using company's direct API."""
        jobs = []
        url = company_info["api_url"].format(query=query, location=location)

        try:
            response = await self._fetch(url)
            data = response.json()

            # Parse based on company-specific API structure
            if company_key == "google":
                jobs = self._parse_google_jobs(data, company_info["name"])
            elif company_key == "microsoft":
                jobs = self._parse_microsoft_jobs(data, company_info["name"])
            elif company_key == "amazon":
                jobs = self._parse_amazon_jobs(data, company_info["name"])
        except Exception as e:
            logger.warning(f"API search failed for {company_info['name']}: {e}")

        return jobs

    async def _search_webpage(
        self, company_key: str, company_info: dict, query: str, location: str
    ) -> list[JobListing]:
        """Search by scraping company career webpage."""
        jobs = []
        url = company_info["search_url"].format(query=query, location=location)

        try:
            response = await self._fetch(url)
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(response.text, "html.parser")

            # Generic job card extraction
            for card in soup.select(
                "a[href*='job'], div[class*='job'], tr[class*='job']"
            ):
                title_el = card.select_one(
                    "h2, h3, span[class*='title'], a[class*='title']"
                )
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                if len(title) < 5 or len(title) > 200:
                    continue

                href = card.get("href", "")
                if href and not href.startswith("http"):
                    href = f"{url.rsplit('/', 1)[0]}{href}"

                skills = self._extract_skills(card.get_text())
                jobs.append(
                    JobListing(
                        company=company_info["name"],
                        title=title,
                        location=location or "Various",
                        remote_status="unknown",
                        required_skills=skills,
                        url=href,
                        source="company_careers",
                        tech_stack=skills,
                        application_url=href,
                    )
                )
        except Exception as e:
            logger.warning(f"Webpage search failed for {company_info['name']}: {e}")

        return jobs

    def _parse_google_jobs(self, data: dict, company: str) -> list[JobListing]:
        """Parse Google Careers API response."""
        jobs = []
        for item in data.get("jobs", []):
            title = item.get("title", "")
            location = item.get("location", "")
            desc = item.get("description", "")
            url = item.get("url", "")
            skills = self._extract_skills(desc)
            remote_status = "remote" if "remote" in location.lower() else "onsite"
            jobs.append(
                JobListing(
                    company=company,
                    title=title,
                    location=location,
                    remote_status=remote_status,
                    required_skills=skills,
                    description=desc[:500],
                    url=url,
                    source="company_careers",
                    tech_stack=skills,
                    application_url=url,
                )
            )
        return jobs

    def _parse_microsoft_jobs(self, data: dict, company: str) -> list[JobListing]:
        """Parse Microsoft Careers API response."""
        jobs = []
        for item in data.get("operationResult", {}).get("result", {}).get("jobs", []):
            title = item.get("title", "")
            location = item.get("primaryWorkLocation", "")
            desc = item.get("description", "")
            url = f"https://careers.microsoft.com/us/en/job/{item.get('jobId', '')}"
            skills = self._extract_skills(desc)
            remote_status = "remote" if "remote" in location.lower() else "onsite"
            jobs.append(
                JobListing(
                    company=company,
                    title=title,
                    location=location,
                    remote_status=remote_status,
                    required_skills=skills,
                    description=desc[:500],
                    url=url,
                    source="company_careers",
                    tech_stack=skills,
                    application_url=url,
                )
            )
        return jobs

    def _parse_amazon_jobs(self, data: dict, company: str) -> list[JobListing]:
        """Parse Amazon Jobs API response."""
        jobs = []
        for item in data.get("jobs", []):
            title = item.get("title", "")
            location = item.get("location", "")
            desc = item.get("description", "")
            url = item.get("url", "")
            skills = self._extract_skills(desc)
            remote_status = "remote" if "remote" in location.lower() else "onsite"
            jobs.append(
                JobListing(
                    company=company,
                    title=title,
                    location=location,
                    remote_status=remote_status,
                    required_skills=skills,
                    description=desc[:500],
                    url=url,
                    source="company_careers",
                    tech_stack=skills,
                    application_url=url,
                )
            )
        return jobs
