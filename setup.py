from setuptools import setup, find_packages

setup(
    name="jobpilot",
    version="0.1.0",
    description="AI-powered job scraping and matching system",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "typer>=0.12.0",
        "fastapi>=0.115.0",
        "uvicorn>=0.32.0",
        "httpx>=0.28.0",
        "beautifulsoup4>=4.12.0",
        "pyyaml>=6.0",
        "rich>=13.0",
        "pydantic>=2.0",
        "aiosqlite>=0.20.0",
    ],
    entry_points={
        "console_scripts": [
            "jobpilot=jobpilot.main:app",
        ],
    },
)
