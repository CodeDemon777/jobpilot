"""Job Importer - Import jobs from URLs (LinkedIn, Naukri, Indeed, etc.)."""

import re
import logging
from typing import Optional
import httpx
from bs4 import BeautifulSoup

from jobpilot.models import JobListing
from jobpilot.scraper.base import BaseScraper

logger = logging.getLogger(__name__)


class JobImporter(BaseScraper):
    """Import jobs from URLs without scraping - user-driven workflow."""

    source_name = "import"

    async def search(self, query: str, location: str = "", **kwargs) -> list[JobListing]:
        """Not used - we use import_from_url instead."""
        return []

    async def import_from_url(self, url: str) -> Optional[JobListing]:
        """
        Import a job from a URL.

        This is a user-driven workflow - the user pastes a job URL,
        and we extract the job details using public information.
        """
        try:
            # Detect the source platform
            source = self._detect_source(url)

            # Fetch the page content
            response = await self._fetch(url)
            soup = BeautifulSoup(response.text, "html.parser")

            # Extract job details based on source
            if source == "linkedin":
                return self._extract_linkedin_job(soup, url)
            elif source == "naukri":
                return self._extract_naukri_job(soup, url)
            elif source == "indeed":
                return self._extract_indeed_job(soup, url)
            elif source == "glassdoor":
                return self._extract_glassdoor_job(soup, url)
            elif source == "wellfound":
                return self._extract_wellfound_job(soup, url)
            else:
                # Generic extraction
                return self._extract_generic_job(soup, url, source)

        except Exception as e:
            logger.warning(f"Failed to import job from {url}: {e}")
            return None

    def _detect_source(self, url: str) -> str:
        """Detect the job platform from URL."""
        url_lower = url.lower()
        if "linkedin.com" in url_lower:
            return "linkedin"
        elif "naukri.com" in url_lower:
            return "naukri"
        elif "indeed.com" in url_lower:
            return "indeed"
        elif "glassdoor.com" in url_lower:
            return "glassdoor"
        elif "wellfound.com" in url_lower or "angel.co" in url_lower:
            return "wellfound"
        elif "greenhouse.io" in url_lower:
            return "greenhouse"
        elif "lever.co" in url_lower:
            return "lever"
        elif "ashbyhq.com" in url_lower:
            return "ashby"
        else:
            return "generic"

    def _extract_linkedin_job(self, soup: BeautifulSoup, url: str) -> JobListing:
        """Extract job details from LinkedIn job page."""
        title = ""
        company = ""
        location = ""
        description = ""

        # Try common LinkedIn selectors
        title_el = soup.select_one("h1.top-card-layout__title")
        if title_el:
            title = title_el.get_text(strip=True)

        company_el = soup.select_one("a.topcard__org-name-link")
        if company_el:
            company = company_el.get_text(strip=True)

        location_el = soup.select_one("span.topcard__flavor--bullet")
        if location_el:
            location = location_el.get_text(strip=True)

        desc_el = soup.select_one("div.description__text")
        if desc_el:
            description = desc_el.get_text(strip=True)[:1000]

        skills = self._extract_skills(description)
        remote_status = "remote" if "remote" in (location + description).lower() else "onsite"

        return JobListing(
            company=company or "Unknown Company",
            title=title or "Imported Job",
            location=location,
            remote_status=remote_status,
            required_skills=skills,
            description=description,
            url=url,
            source="linkedin_import",
            tech_stack=skills,
            application_url=url,
        )

    def _extract_naukri_job(self, soup: BeautifulSoup, url: str) -> JobListing:
        """Extract job details from Naukri job page."""
        title = ""
        company = ""
        location = ""
        description = ""

        title_el = soup.select_one("h1.header")
        if title_el:
            title = title_el.get_text(strip=True)

        company_el = soup.select_one("a.jd-header-title")
        if company_el:
            company = company_el.get_text(strip=True)

        location_el = soup.select_one("span.location")
        if location_el:
            location = location_el.get_text(strip=True)

        desc_el = soup.select_one("div.jd-desc")
        if desc_el:
            description = desc_el.get_text(strip=True)[:1000]

        skills = self._extract_skills(description)
        remote_status = "remote" if "remote" in (location + description).lower() else "onsite"

        return JobListing(
            company=company or "Unknown Company",
            title=title or "Imported Job",
            location=location,
            remote_status=remote_status,
            required_skills=skills,
            description=description,
            url=url,
            source="naukri_import",
            tech_stack=skills,
            application_url=url,
        )

    def _extract_indeed_job(self, soup: BeautifulSoup, url: str) -> JobListing:
        """Extract job details from Indeed job page."""
        title = ""
        company = ""
        location = ""
        description = ""

        title_el = soup.select_one("h1.jobsearch-JobInfoHeader-title")
        if title_el:
            title = title_el.get_text(strip=True)

        company_el = soup.select_one("div[data-testid='inlineHeader-companyName']")
        if company_el:
            company = company_el.get_text(strip=True)

        location_el = soup.select_one("div[data-testid='inlineHeader-companyLocation']")
        if location_el:
            location = location_el.get_text(strip=True)

        desc_el = soup.select_one("div#jobDescriptionText")
        if desc_el:
            description = desc_el.get_text(strip=True)[:1000]

        skills = self._extract_skills(description)
        remote_status = "remote" if "remote" in (location + description).lower() else "onsite"

        return JobListing(
            company=company or "Unknown Company",
            title=title or "Imported Job",
            location=location,
            remote_status=remote_status,
            required_skills=skills,
            description=description,
            url=url,
            source="indeed_import",
            tech_stack=skills,
            application_url=url,
        )

    def _extract_glassdoor_job(self, soup: BeautifulSoup, url: str) -> JobListing:
        """Extract job details from Glassdoor job page."""
        title = ""
        company = ""
        location = ""
        description = ""

        title_el = soup.select_one("h1[data-test='job-title']")
        if title_el:
            title = title_el.get_text(strip=True)

        company_el = soup.select_one("div.employer-name")
        if company_el:
            company = company_el.get_text(strip=True)

        location_el = soup.select_one("div.location")
        if location_el:
            location = location_el.get_text(strip=True)

        desc_el = soup.select_one("div.jobDescriptionContent")
        if desc_el:
            description = desc_el.get_text(strip=True)[:1000]

        skills = self._extract_skills(description)
        remote_status = "remote" if "remote" in (location + description).lower() else "onsite"

        return JobListing(
            company=company or "Unknown Company",
            title=title or "Imported Job",
            location=location,
            remote_status=remote_status,
            required_skills=skills,
            description=description,
            url=url,
            source="glassdoor_import",
            tech_stack=skills,
            application_url=url,
        )

    def _extract_wellfound_job(self, soup: BeautifulSoup, url: str) -> JobListing:
        """Extract job details from Wellfound/AngelList job page."""
        title = ""
        company = ""
        location = ""
        description = ""

        title_el = soup.select_one("h1.styles_title__dAoph")
        if title_el:
            title = title_el.get_text(strip=True)

        company_el = soup.select_one("span.styles_companyName__mWtvj")
        if company_el:
            company = company_el.get_text(strip=True)

        location_el = soup.select_one("span.styles_location__BfLkD")
        if location_el:
            location = location_el.get_text(strip=True)

        desc_el = soup.select_one("div.styles_jobDescription__txHWu")
        if desc_el:
            description = desc_el.get_text(strip=True)[:1000]

        skills = self._extract_skills(description)
        remote_status = "remote" if "remote" in (location + description).lower() else "onsite"

        return JobListing(
            company=company or "Unknown Company",
            title=title or "Imported Job",
            location=location,
            remote_status=remote_status,
            required_skills=skills,
            description=description,
            url=url,
            source="wellfound_import",
            tech_stack=skills,
            application_url=url,
        )

    def _extract_generic_job(self, soup: BeautifulSoup, url: str, source: str) -> JobListing:
        """Extract job details from any generic job page."""
        title = ""
        company = ""
        location = ""
        description = ""

        # Try common patterns
        for selector in ["h1", "h2", "h3", "title"]:
            el = soup.select_one(selector)
            if el:
                text = el.get_text(strip=True)
                if len(text) > 5 and len(text) < 200:
                    title = text
                    break

        # Try to find company name
        for selector in ["[class*='company']", "[class*='employer']", "[class*='org']"]:
            el = soup.select_one(selector)
            if el:
                company = el.get_text(strip=True)
                break

        # Try to find location
        for selector in ["[class*='location']", "[class*='place']"]:
            el = soup.select_one(selector)
            if el:
                location = el.get_text(strip=True)
                break

        # Get page text as description
        body_text = soup.get_text(strip=True)[:2000]
        description = body_text[:1000]

        skills = self._extract_skills(description)
        remote_status = "remote" if "remote" in (location + description).lower() else "onsite"

        return JobListing(
            company=company or "Unknown Company",
            title=title or "Imported Job",
            location=location,
            remote_status=remote_status,
            required_skills=skills,
            description=description,
            url=url,
            source=f"{source}_import",
            tech_stack=skills,
            application_url=url,
        )