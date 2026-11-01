import os
from datetime import timedelta
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv()

NEPAL_TZ = ZoneInfo("Asia/Kathmandu")


def get_database_uri():
    """Return a production-ready database URI prioritized for Turso (libSQL).

    Priority:
    1. TURSO_DATABASE_URL  → remote Turso / libSQL (recommended for Vercel)
    2. DATABASE_URL        → Neon / Postgres (legacy support)
    3. Local SQLite        → development only (never on Vercel)
    """
    turso_url = os.environ.get("TURSO_DATABASE_URL", "").strip()
    if turso_url:
        # Turso docs: sqlite+libsql://... or sqlite+{libsql://host}?secure=true
        if turso_url.startswith("libsql://"):
            return f"sqlite+{turso_url}?secure=true"
        if turso_url.startswith("sqlite+libsql://") or turso_url.startswith("sqlite+"):
            return turso_url
        # Fallback – treat as host
        return f"sqlite+libsql://{turso_url}?secure=true"

    # Legacy Postgres / Neon support
    uri = os.environ.get("DATABASE_URL", "").strip()
    if uri:
        if uri.startswith("postgres://"):
            uri = uri.replace("postgres://", "postgresql://", 1)
        return uri

    # Local development only – Vercel has no writable filesystem
    if os.environ.get("VERCEL"):
        raise RuntimeError(
            "TURSO_DATABASE_URL (or DATABASE_URL) environment variable is required on Vercel. "
            "Create a Turso database and set TURSO_DATABASE_URL + TURSO_AUTH_TOKEN."
        )
    return "sqlite:///school.db"


def _is_libsql_or_sqlite(uri: str) -> bool:
    """True when the dialect uses SingletonThreadPool (no pool_size / max_overflow)."""
    if not uri:
        return True
    u = uri.lower()
    return (
        u.startswith("sqlite")
        or "libsql" in u
        or u.startswith("sqlite+")
    )


def get_engine_options():
    """Build SQLAlchemy engine options compatible with the active dialect.

    - Turso / libSQL / SQLite → SingletonThreadPool → only connect_args + recycle/pre_ping
    - Postgres → QueuePool → pool_size + max_overflow allowed
    """
    uri = get_database_uri()
    options = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }

    # Turso / libSQL auth token (required for remote databases)
    turso_token = os.environ.get("TURSO_AUTH_TOKEN", "").strip()
    if turso_token:
        options["connect_args"] = {
            "auth_token": turso_token,
        }

    # Only QueuePool dialects accept these kwargs
    if not _is_libsql_or_sqlite(uri):
        options["pool_size"] = 5
        options["max_overflow"] = 10

    return options


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
    SQLALCHEMY_DATABASE_URI = get_database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = get_engine_options()
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)

    # Mail
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() in ("true", "1", "yes")
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_USERNAME", "info@newvisionacademy.edu.np")

    # Cloudinary
    CLOUDINARY_CLOUD_NAME = os.environ.get("CLOUDINARY_CLOUD_NAME", "rznbwjix")
    CLOUDINARY_API_KEY = os.environ.get("CLOUDINARY_API_KEY", "")
    CLOUDINARY_API_SECRET = os.environ.get("CLOUDINARY_API_SECRET", "")
    CLOUDINARY_URL = os.environ.get("CLOUDINARY_URL", "")

    # School
    SCHOOL_NAME = os.environ.get("SCHOOL_NAME", "New Vision Academy")
    SCHOOL_TIMEZONE = os.environ.get("SCHOOL_TIMEZONE", "Asia/Kathmandu")

    # Admin bootstrap
    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@newvisionacademy.com.np")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

    # Upload limits
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100 MB (photos + videos bulk)
