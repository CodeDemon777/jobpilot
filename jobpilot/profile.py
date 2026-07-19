"""User profile management — load, save, and update from YAML."""

from pathlib import Path

import yaml

from jobpilot.config import PROFILE_PATH
from jobpilot.models import UserProfile


def load_profile(path: Path = PROFILE_PATH) -> UserProfile:
    """Load user profile from YAML file."""
    if not path.exists():
        return UserProfile()
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return UserProfile(
        **{k: v for k, v in data.items() if k in UserProfile.__dataclass_fields__}
    )


def save_profile(profile: UserProfile, path: Path = PROFILE_PATH) -> None:
    """Save user profile to YAML file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {k: v for k, v in profile.__dict__.items()}
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(
            data, f, default_flow_style=False, sort_keys=False, allow_unicode=True
        )


def update_profile(**kwargs) -> UserProfile:
    """Update specific fields in the user profile."""
    profile = load_profile()
    for key, value in kwargs.items():
        if hasattr(profile, key):
            setattr(profile, key, value)
    save_profile(profile)
    return profile
