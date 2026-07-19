"""Configuration and paths for JobPilot."""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "jobpilot.db"
PROFILE_PATH = DATA_DIR / "profile.yaml"

# API keys (loaded from environment variables — never hardcode)
API_KEY = os.environ.get("JOBPILOT_API_KEY", "")

# Matching thresholds
MATCH_THRESHOLD = 0.5
TOP_MATCH_THRESHOLD = 0.8

# Matching weights
WEIGHTS = {
    "skills": 0.35,
    "experience": 0.20,
    "relevance": 0.20,
    "education": 0.10,
    "role": 0.10,
    "location": 0.05,
}

# Scraper settings
REQUEST_TIMEOUT = 15
MAX_RETRIES = 3
RATE_LIMIT_DELAY = 1.0  # seconds between requests to same source

# Web dashboard
DEFAULT_PORT = 8000

# File upload settings
UPLOAD_DIR = DATA_DIR / "uploads"
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
ALLOWED_UPLOAD_TYPES = {".txt", ".pdf", ".md", ".rtf"}
