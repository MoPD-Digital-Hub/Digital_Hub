"""Firebase Admin for push notifications.

The service-account key is not in the repository. Put it at
secrets/firebase-service-account.json (repository root, git-ignored) or point
FIREBASE_CREDENTIALS at it. Firebase starts on the first push, so a missing key
fails that push, not the whole site.
"""

from pathlib import Path

import firebase_admin
from decouple import config
from firebase_admin import credentials

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CREDENTIALS = PROJECT_ROOT / "secrets" / "firebase-service-account.json"


def _path(raw: str) -> Path:
    path = Path(raw).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def credentials_path() -> Path:
    """FIREBASE_CREDENTIALS, else secrets/firebase-service-account.json, else the
    old FIRE_BASE_MESSAGES setting (which pointed into the repository)."""
    if config("FIREBASE_CREDENTIALS", default=""):
        return _path(config("FIREBASE_CREDENTIALS"))
    if DEFAULT_CREDENTIALS.is_file() or not config("FIRE_BASE_MESSAGES", default=""):
        return DEFAULT_CREDENTIALS
    return _path(config("FIRE_BASE_MESSAGES"))


def initialize_firebase():
    """The Firebase app, initialised on first use."""
    if firebase_admin._apps:
        return firebase_admin.get_app()
    path = credentials_path()
    if not path.is_file():
        raise RuntimeError(f"Firebase key not found at {path} (set FIREBASE_CREDENTIALS).")
    return firebase_admin.initialize_app(credentials.Certificate(str(path)))
