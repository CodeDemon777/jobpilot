"""JobPilot scrapers package."""

from jobpilot.scraper.base import BaseScraper
from jobpilot.scraper.greenhouse import GreenhouseScraper
from jobpilot.scraper.remoteok import RemoteOKScraper
from jobpilot.scraper.indeed import IndeedScraper
from jobpilot.scraper.linkedin import LinkedInScraper
from jobpilot.scraper.wellfound import WellfoundScraper
from jobpilot.scraper.weworkremotely import WeWorkRemotelyScraper
from jobpilot.scraper.yc_jobs import YCJobsScraper
from jobpilot.scraper.lever import LeverScraper
from jobpilot.scraper.ashby import AshbyScraper
from jobpilot.scraper.naukri import NaukriScraper
from jobpilot.scraper.internshala import InternshalaScraper
from jobpilot.scraper.cutshort import CutshortScraper
from jobpilot.scraper.hirect import HirectScraper
from jobpilot.scraper.foundit import FounditScraper
from jobpilot.scraper.glassdoor import GlassdoorScraper
from jobpilot.scraper.workable import WorkableScraper
from jobpilot.scraper.career_pages import CareerPagesScraper
from jobpilot.scraper.company_careers import CompanyCareersScraper
from jobpilot.scraper.rss_feeds import RSSFeedScraper

__all__ = [
    "BaseScraper",
    "GreenhouseScraper",
    "RemoteOKScraper",
    "IndeedScraper",
    "LinkedInScraper",
    "WellfoundScraper",
    "WeWorkRemotelyScraper",
    "YCJobsScraper",
    "LeverScraper",
    "AshbyScraper",
    "NaukriScraper",
    "InternshalaScraper",
    "CutshortScraper",
    "HirectScraper",
    "FounditScraper",
    "GlassdoorScraper",
    "WorkableScraper",
    "CareerPagesScraper",
    "CompanyCareersScraper",
    "RSSFeedScraper",
]

SCRAPERS = {
    "greenhouse": GreenhouseScraper,
    "remoteok": RemoteOKScraper,
    "indeed": IndeedScraper,
    "linkedin": LinkedInScraper,
    "wellfound": WellfoundScraper,
    "weworkremotely": WeWorkRemotelyScraper,
    "yc_jobs": YCJobsScraper,
    "lever": LeverScraper,
    "ashby": AshbyScraper,
    "naukri": NaukriScraper,
    "internshala": InternshalaScraper,
    "cutshort": CutshortScraper,
    "hirect": HirectScraper,
    "foundit": FounditScraper,
    "glassdoor": GlassdoorScraper,
    "workable": WorkableScraper,
    "career_pages": CareerPagesScraper,
    "company_careers": CompanyCareersScraper,
    "rss_feeds": RSSFeedScraper,
}
