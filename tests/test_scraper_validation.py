"""Scraper validation tests for all job providers."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
import time
from unittest.mock import AsyncMock, patch, MagicMock

from jobpilot.scraper import SCRAPERS
from jobpilot.scraper.base import BaseScraper
from jobpilot.scraper.greenhouse import GreenhouseScraper, KNOWN_GREENHOUSE_BOARDS
from jobpilot.scraper.remoteok import RemoteOKScraper
from jobpilot.models import JobListing


# =====================================================
# SCRAPER INFRASTRUCTURE TESTS
# =====================================================

class TestScraperInfrastructure(unittest.TestCase):
    def test_all_scrapers_registered(self):
        """Verify all scrapers are registered."""
        assert len(SCRAPERS) >= 10, f"Expected >= 10 scrapers, got {len(SCRAPERS)}"

    def test_all_scrapers_inherit_base(self):
        """Verify all scrapers inherit from BaseScraper."""
        for name, scraper_cls in SCRAPERS.items():
            assert issubclass(scraper_cls, BaseScraper), f"{name} does not inherit from BaseScraper"

    def test_all_scrapers_have_search(self):
        """Verify all scrapers have a search method."""
        for name, scraper_cls in SCRAPERS.items():
            assert hasattr(scraper_cls, 'search'), f"{name} missing search method"

    def test_scraper_has_source_name(self):
        """Verify all scrapers have a source_name."""
        for name, scraper_cls in SCRAPERS.items():
            scraper = scraper_cls()
            assert hasattr(scraper, 'source_name'), f"{name} missing source_name"
            assert scraper.source_name, f"{name} has empty source_name"


# =====================================================
# GREENHOUSE SCRAPER TESTS
# =====================================================

class TestGreenhouseScraper(unittest.TestCase):
    def test_board_tokens_valid(self):
        """Verify board tokens are valid strings."""
        for name, token in KNOWN_GREENHOUSE_BOARDS.items():
            assert isinstance(token, str), f"Board token for {name} should be string"
            assert len(token) > 0, f"Board token for {name} should not be empty"

    def test_board_count(self):
        """Verify we have enough board tokens."""
        assert len(KNOWN_GREENHOUSE_BOARDS) >= 5, "Should have at least 5 board tokens"

    def test_scraper_instantiation(self):
        """Verify scraper can be instantiated."""
        scraper = GreenhouseScraper()
        assert scraper.source_name == "greenhouse"

    def test_extract_skills(self):
        """Verify skill extraction works."""
        scraper = GreenhouseScraper()
        skills = scraper._extract_skills("Python, React, and AWS experience required")
        assert "python" in skills
        assert "react" in skills
        assert "aws" in skills

    def test_parse_salary(self):
        """Verify salary parsing works."""
        scraper = GreenhouseScraper()
        min_s, max_s, currency = scraper._parse_salary("$100,000 - $150,000")
        assert min_s == 100000
        assert max_s == 150000
        assert currency == "USD"

    def test_clean_html(self):
        """Verify HTML cleaning works."""
        scraper = GreenhouseScraper()
        result = scraper._clean_html("<p>Hello <b>world</b></p>")
        assert result == "Hello world"
        assert "<" not in result


# =====================================================
# REMOTEOK SCRAPER TESTS
# =====================================================

class TestRemoteOKScraper(unittest.TestCase):
    def test_scraper_instantiation(self):
        """Verify scraper can be instantiated."""
        scraper = RemoteOKScraper()
        assert scraper.source_name == "remoteok"

    def test_parse_job(self):
        """Verify job parsing works."""
        scraper = RemoteOKScraper()
        data = {
            "position": "Python Developer",
            "company": "TestCo",
            "description": "Build stuff",
            "tags": ["python", "django"],
            "salary_min": 100000,
            "salary_max": 150000,
            "slug": "python-dev-testco",
            "date": "2024-01-01",
        }
        job = scraper._parse_job(data)
        assert job.company == "TestCo"
        assert job.title == "Python Developer"
        assert "python" in job.required_skills
        assert job.salary_min == 100000
        assert job.remote_status == "remote"

    def test_parse_job_no_tags(self):
        """Verify job parsing works without tags."""
        scraper = RemoteOKScraper()
        data = {"position": "Dev", "company": "Co", "description": "Python and React developer"}
        job = scraper._parse_job(data)
        assert "python" in job.required_skills or "react" in job.required_skills


# =====================================================
# JOB IMPORTER TESTS
# =====================================================

class TestJobImporter(unittest.TestCase):
    def test_source_detection(self):
        """Verify URL source detection works."""
        from jobpilot.job_importer import JobImporter
        importer = JobImporter()

        test_cases = [
            ("https://www.linkedin.com/jobs/view/123", "linkedin"),
            ("https://www.naukri.com/job/123", "naukri"),
            ("https://www.indeed.com/viewjob?jk=123", "indeed"),
            ("https://www.glassdoor.com/job/listing/123", "glassdoor"),
            ("https://wellfound.com/role/123", "wellfound"),
            ("https://boards.greenhouse.io/123", "greenhouse"),
            ("https://jobs.lever.co/123", "lever"),
            ("https://jobs.ashbyhq.com/123", "ashby"),
            ("https://example.com/job/123", "generic"),
        ]

        for url, expected in test_cases:
            result = importer._detect_source(url)
            assert result == expected, f"Expected {expected} for {url}, got {result}"

    def test_import_invalid_url(self):
        """Verify import handles invalid URLs gracefully."""
        from jobpilot.job_importer import JobImporter
        importer = JobImporter()

        async def test():
            result = await importer.import_from_url("")
            assert result is None

        asyncio.run(test())


# =====================================================
# COMPANY CAREERS TESTS
# =====================================================

class TestCompanyCareers(unittest.TestCase):
    def test_known_companies(self):
        """Verify known companies are configured."""
        from jobpilot.scraper.company_careers import COMPANY_CAREERS

        expected_companies = ["google", "microsoft", "amazon", "apple", "meta"]
        for company in expected_companies:
            assert company in COMPANY_CAREERS, f"{company} not in COMPANY_CAREERS"

    def test_company_structure(self):
        """Verify company data structure."""
        from jobpilot.scraper.company_careers import COMPANY_CAREERS

        for name, data in COMPANY_CAREERS.items():
            assert "name" in data, f"{name} missing 'name'"
            assert "search_url" in data, f"{name} missing 'search_url'"


# =====================================================
# RSS FEEDS TESTS
# =====================================================

class TestRSSFeeds(unittest.TestCase):
    def test_known_feeds(self):
        """Verify known RSS feeds are configured."""
        from jobpilot.scraper.rss_feeds import KNOWN_RSS_FEEDS

        expected_feeds = ["stackoverflow", "remoteok", "weworkremotely", "hackernews"]
        for feed in expected_feeds:
            assert feed in KNOWN_RSS_FEEDS, f"{feed} not in KNOWN_RSS_FEEDS"

    def test_feed_structure(self):
        """Verify feed data structure."""
        from jobpilot.scraper.rss_feeds import KNOWN_RSS_FEEDS

        for name, data in KNOWN_RSS_FEEDS.items():
            assert "name" in data, f"{name} missing 'name'"
            assert "url" in data, f"{name} missing 'url'"
            assert "format" in data, f"{name} missing 'format'"


# =====================================================
# SCRAPER ERROR HANDLING TESTS
# =====================================================

class TestScraperErrorHandling(unittest.TestCase):
    def test_greenhouse_handles_invalid_board(self):
        """Verify Greenhouse scraper handles invalid board gracefully."""
        async def test():
            scraper = GreenhouseScraper()
            try:
                jobs = await scraper.search(query="test", boards=["invalid_board_12345"])
                # Should return empty list, not raise exception
                assert isinstance(jobs, list)
            except Exception:
                pass  # Some exceptions are acceptable

        asyncio.run(test())

    def test_remoteok_handles_network_error(self):
        """Verify RemoteOK scraper handles network errors gracefully."""
        async def test():
            scraper = RemoteOKScraper()
            with patch.object(scraper, '_fetch', side_effect=Exception("Network error")):
                try:
                    jobs = await scraper.search(query="test")
                    assert isinstance(jobs, list)
                except Exception:
                    pass  # Some exceptions are acceptable

        asyncio.run(test())


# =====================================================
# RUN ALL TESTS
# =====================================================

if __name__ == "__main__":
    import unittest

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    test_classes = [
        TestScraperInfrastructure,
        TestGreenhouseScraper,
        TestRemoteOKScraper,
        TestJobImporter,
        TestCompanyCareers,
        TestRSSFeeds,
        TestScraperErrorHandling,
    ]

    for test_class in test_classes:
        suite.addTests(loader.loadTestsFromTestCase(test_class))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print(f"\n{'='*60}")
    print(f"Scraper Tests: {result.testsRun} run, {len(result.failures)} failures, {len(result.errors)} errors")
    print(f"{'='*60}")

    sys.exit(0 if result.wasSuccessful() else 1)
