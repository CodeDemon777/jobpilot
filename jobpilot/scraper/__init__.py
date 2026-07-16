"""JobPilot scrapers package."""

from jobpilot.scraper.base import BaseScraper
from jobpilot.scraper.greenhouse import GreenhouseScraper
from jobpilot.scraper.remoteok import RemoteOKScraper

__all__ = ["BaseScraper", "GreenhouseScraper", "RemoteOKScraper"]

SCRAPERS = {
    "greenhouse": GreenhouseScraper,
    "remoteok": RemoteOKScraper,
}
