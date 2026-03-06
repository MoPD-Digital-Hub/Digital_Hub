import firebase_admin
from firebase_admin import credentials, messaging
from decouple import config
import os
from pathlib import Path


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_FIREBASE_JSON_PATH = Path(BASE_DIR) / 'admas-9e2c7-9bcdd20b9461.json'
PROJECT_ROOT = Path(__file__).resolve().parents[3]
_raw_firebase_json_path = config(
    'FIRE_BASE_MESSAGES',
    default=str(DEFAULT_FIREBASE_JSON_PATH)
)

def _resolve_firebase_json_path(raw_path: str) -> str:
    """
    Resolve Firebase credential path consistently regardless of current working dir.
    """
    configured = Path(raw_path).expanduser()

    if configured.is_absolute():
        return str(configured)

    # Try relative to current cwd first, then project root, then push_notification dir.
    candidates = [
        Path.cwd() / configured,
        PROJECT_ROOT / configured,
        Path(BASE_DIR) / configured.name,
    ]

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    # Return a deterministic path for clearer error reporting upstream.
    return str(PROJECT_ROOT / configured)

FIREBASE_JSON_PATH = _resolve_firebase_json_path(_raw_firebase_json_path)

def initialize_firebase():
    """
    Initialize Firebase app with service account JSON.
    Returns the firebase app instance.
    """
    # If already initialized, return the existing app
    if not firebase_admin._apps:
        cred = credentials.Certificate(FIREBASE_JSON_PATH)
        app = firebase_admin.initialize_app(cred)
        return app
    else:
        return firebase_admin.get_app()
