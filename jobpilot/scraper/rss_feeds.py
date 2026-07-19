"""RSS Feeds scraper - Parse job feeds from RSS/Atom sources."""

import logging
import re
from datetime import datetime
from jobpilot.scraper.base import BaseScraper
from jobpilot.models import JobListing

logger = logging.getLogger(__name__)

# Known RSS job feeds
KNOWN_RSS_FEEDS = {
    "stackoverflow": {
        "name": "Stack Overflow Jobs",
        "url": "https://stackoverflow.com/jobs/feed",
        "format": "rss",
    },
    "remoteok": {
        "name": "RemoteOK RSS",
        "url": "https://remoteok.com/remote-jobs.rss",
        "format": "rss",
    },
    "weworkremotely": {
        "name": "We Work Remotely RSS",
        "url": "https://weworkremotely.com/remote-jobs.rss",
        "format": "rss",
    },
    "hackernews": {
        "name": "Hacker News Who's Hiring",
        "url": "https://hnrss.org/newest?q=hiring",
        "format": "rss",
    },
    "remoteok_api": {
        "name": "RemoteOK API",
        "url": "https://remoteok.com/api",
        "format": "json",
    },
}


class RSSFeedScraper(BaseScraper):
    """Scrape job feeds from RSS/Atom sources."""

    source_name = "rss_feeds"

    async def search(
        self, query: str, location: str = "", **kwargs
    ) -> list[JobListing]:
        """Search across all configured RSS feeds."""
        feeds = kwargs.get("feeds", list(KNOWN_RSS_FEEDS.keys()))
        query_lower = query.lower()
        all_jobs = []

        for feed_key in feeds:
            if feed_key not in KNOWN_RSS_FEEDS:
                continue

            feed_info = KNOWN_RSS_FEEDS[feed_key]
            try:
                if feed_info["format"] == "json":
                    jobs = await self._parse_json_feed(feed_info, query)
                else:
                    jobs = await self._parse_rss_feed(feed_info, query)
                all_jobs.extend(jobs)
            except Exception as e:
                logger.warning(f"Failed to parse feed {feed_info['name']}: {e}")

        # Filter by query if needed
        if query_lower:
            all_jobs = [
                j
                for j in all_jobs
                if query_lower in j.title.lower()
                or query_lower in j.description.lower()
            ]

        logger.info(f"RSS Feeds: found {len(all_jobs)} jobs across {len(feeds)} feeds")
        return all_jobs

    async def _parse_rss_feed(self, feed_info: dict, query: str) -> list[JobListing]:
        """Parse an RSS feed."""
        jobs = []
        try:
            response = await self._fetch(feed_info["url"])
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(response.text, "xml")

            # Find all items/entries
            items = soup.find_all("item") or soup.find_all("entry")

            for item in items:
                title = ""
                link = ""
                description = ""
                pub_date = ""

                # Extract title
                title_el = item.find("title")
                if title_el:
                    title = title_el.get_text(strip=True)

                # Extract link
                link_el = item.find("link")
                if link_el:
                    link = link_el.get("href", "") or link_el.get_text(strip=True)

                # Extract description
                desc_el = (
                    item.find("description")
                    or item.find("summary")
                    or item.find("content")
                )
                if desc_el:
                    description = desc_el.get_text(strip=True)[:1000]

                # Extract date
                date_el = (
                    item.find("pubDate")
                    or item.find("published")
                    or item.find("updated")
                )
                if date_el:
                    pub_date = date_el.get_text(strip=True)

                if not title:
                    continue

                skills = self._extract_skills(description)
                remote_status = (
                    "remote" if "remote" in (title + description).lower() else "unknown"
                )

                jobs.append(
                    JobListing(
                        company=feed_info["name"],
                        title=title,
                        location="Remote" if remote_status == "remote" else "Various",
                        remote_status=remote_status,
                        required_skills=skills,
                        description=description,
                        url=link,
                        source="rss_feed",
                        posted_date=pub_date,
                        tech_stack=skills,
                        application_url=link,
                    )
                )

        except Exception as e:
            logger.warning(f"RSS parse failed for {feed_info['name']}: {e}")

        return jobs

    async def _parse_json_feed(self, feed_info: dict, query: str) -> list[JobListing]:
        """Parse a JSON job feed."""
        jobs = []
        try:
            response = await self._fetch(feed_info["url"])
            data = response.json()

            # RemoteOK format
            if isinstance(data, list):
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    title = item.get("position", "")
                    company = item.get("company", feed_info["name"])
                    desc = item.get("description", "")
                    url = item.get("url", "")
                    tags = item.get("tags", [])

                    if not title:
                        continue

                    skills = tags if tags else self._extract_skills(desc)
                    remote_status = "remote" if item.get("remote", True) else "onsite"

                    jobs.append(
                        JobListing(
                            company=company,
                            title=title,
                            location=(
                                "Remote" if remote_status == "remote" else "Various"
                            ),
                            remote_status=remote_status,
                            required_skills=skills,
                            description=desc[:500],
                            url=url,
                            source="rss_feed",
                            tech_stack=skills,
                            application_url=url,
                        )
                    )

        except Exception as e:
            logger.warning(f"JSON feed parse failed for {feed_info['name']}: {e}")

        return jobs
