"""Abstract base class for job scrapers."""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import AsyncIterator

import httpx

from jobpilot.config import REQUEST_TIMEOUT, RATE_LIMIT_DELAY
from jobpilot.models import JobListing

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Base class all scrapers must implement."""

    source_name: str = "unknown"
    base_url: str = ""

    def __init__(self):
        self._last_request_time: float = 0

    @abstractmethod
    async def search(self, query: str, location: str = "", **kwargs) -> list[JobListing]:
        """Search for jobs matching the query."""
        ...

    async def get_details(self, url: str) -> JobListing | None:
        """Get full job details from a URL. Override if supported."""
        return None

    async def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request_time
        if elapsed < RATE_LIMIT_DELAY:
            await asyncio.sleep(RATE_LIMIT_DELAY - elapsed)
        self._last_request_time = asyncio.get_event_loop().time()

    async def _fetch(self, url: str, headers: dict | None = None) -> httpx.Response:
        """Fetch a URL with rate limiting and error handling."""
        await self._rate_limit()
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            try:
                response = await client.get(url, headers=headers or {})
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as e:
                logger.warning(f"HTTP {e.response.status_code} from {url}")
                raise
            except httpx.RequestError as e:
                logger.warning(f"Request failed for {url}: {e}")
                raise

    def _parse_salary(self, text: str) -> tuple[int, int, str]:
        """Parse salary range from text. Returns (min, max, currency)."""
        import re
        text = text.replace(",", "").replace(" ", "")
        currency = "USD"
        if "$" in text:
            currency = "USD"
        elif "€" in text:
            currency = "EUR"
        elif "£" in text:
            currency = "GBP"

        numbers = re.findall(r"\d+", text)
        if len(numbers) >= 2:
            return int(numbers[0]), int(numbers[1]), currency
        elif len(numbers) == 1:
            val = int(numbers[0])
            return val, val, currency
        return 0, 0, currency

    def _extract_skills(self, text: str) -> list[str]:
        """Extract skill keywords from text."""
        import re
        common_skills = [
            "python", "javascript", "typescript", "java", "go", "rust", "c++", "c#",
            "react", "vue", "angular", "node.js", "django", "fastapi", "flask",
            "aws", "gcp", "azure", "docker", "kubernetes", "terraform",
            "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
            "machine learning", "deep learning", "nlp", "computer vision",
            "git", "ci/cd", "agile", "scrum", "rest", "graphql",
            "html", "css", "sass", "tailwind",
            "sql", "nosql", "data analysis", "etl",
            "figma", "sketch", "adobe",
            "tensorflow", "pytorch", "scikit-learn", "pandas", "numpy",
        ]
        text_lower = text.lower()
        found = [skill for skill in common_skills if skill in text_lower]
        return found
