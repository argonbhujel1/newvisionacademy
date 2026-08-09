import os
from datetime import timedelta
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv()

NEPAL_TZ = ZoneInfo("Asia/Kathmandu")

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///school.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
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
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB
