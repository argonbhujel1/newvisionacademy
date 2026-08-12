import os
from datetime import timedelta
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv()

NEPAL_TZ = ZoneInfo("Asia/Kathmandu")


def get_database_uri():
    """Return a production-ready database URI.

    - Prefer DATABASE_URL (Neon / Postgres on Vercel)
    - Normalize postgres:// → postgresql:// (SQLAlchemy requirement)
    - Never fall back to SQLite on Vercel (read-only filesystem)
    """
    uri = os.environ.get("DATABASE_URL", "").strip()
    if uri:
        if uri.startswith("postgres://"):
            uri = uri.replace("postgres://", "postgresql://", 1)
        return uri

    # Local development only – Vercel has no writable filesystem for SQLite
    if os.environ.get("VERCEL"):
        raise RuntimeError(
            "DATABASE_URL environment variable is required on Vercel. "
            "Set it to your Neon Postgres connection string."
        )
    return "sqlite:///school.db"


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
    SQLALCHEMY_DATABASE_URI = get_database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Recommended for serverless (Neon / Vercel)
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_size": 5,
        "max_overflow": 10,
    }
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
