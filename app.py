import os
import re
from datetime import datetime, timedelta
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for, flash,
    session, jsonify, send_from_directory, abort, make_response
)
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

from config import Config, NEPAL_TZ
from utils.timezone import now_nepal, to_nepal, format_date, format_time, format_datetime
from utils.cloudinary import init_cloudinary, upload_image, upload_file, delete_image
from utils.email import send_email, render_template_vars, get_response_time_text

load_dotenv()

app = Flask(__name__)
app.config.from_object(Config)


@app.template_filter("fix_media_url")
def fix_media_url(url):
    """Fix Cloudinary PDF URLs wrongly stored as /image/upload/ → /raw/upload/."""
    if not url:
        return url
    u = str(url)
    low = u.lower()
    if low.endswith(".pdf") or ".pdf?" in low or "/pdf" in low:
        if "/image/upload/" in u:
            u = u.replace("/image/upload/", "/raw/upload/", 1)
        # Also strip transformation segments that break raw PDFs
        # e.g. /raw/upload/c_scale,w_500/v123/... should not apply to PDF
    return u


@app.template_filter("download_url")
def cloudinary_download_url(url):
    """Force download disposition on Cloudinary URLs when possible."""
    if not url:
        return url
    u = fix_media_url(url)
    if "cloudinary.com" not in u:
        return u
    if "/upload/" in u and "fl_attachment" not in u:
        return u.replace("/upload/", "/upload/fl_attachment/", 1)
    return u


db = SQLAlchemy(app)
mail = Mail(app)

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class AdminUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    name = db.Column(db.String(100), default="Administrator")
    role = db.Column(db.String(50), default="admin")
    is_active = db.Column(db.Boolean, default=True)
    last_login = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=lambda: now_nepal())

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class SiteSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text, default="")
    updated_at = db.Column(db.DateTime, default=lambda: now_nepal(), onupdate=lambda: now_nepal())


class SchoolProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    school_name = db.Column(db.String(200), default="New Vision Academy")
    short_name = db.Column(db.String(50), default="NVA")
    logo_url = db.Column(db.String(500), default="")
    favicon_url = db.Column(db.String(500), default="")
    about_image_url = db.Column(db.String(500), default="")
    about_image_public_id = db.Column(db.String(300), default="")
    address = db.Column(db.String(300), default="Urlabari-8, Morang, Koshi Province, Nepal")
    phone = db.Column(db.String(50), default="")
    phone2 = db.Column(db.String(50), default="")
    email = db.Column(db.String(120), default="info@newvisionacademy.edu.np")
    website = db.Column(db.String(200), default="https://newvisionacademy.com.np")
    facebook = db.Column(db.String(300), default="")
    instagram = db.Column(db.String(300), default="")
    youtube = db.Column(db.String(300), default="")
    tiktok = db.Column(db.String(300), default="")
    google_maps = db.Column(db.Text, default="")
    description = db.Column(db.Text, default="")
    motto = db.Column(db.String(300), default="")
    vision = db.Column(db.Text, default="")
    mission = db.Column(db.Text, default="")
    core_values = db.Column(db.Text, default="")
    why_choose_us = db.Column(db.Text, default="")
    history = db.Column(db.Text, default="")
    established_year = db.Column(db.String(20), default="")
    student_count = db.Column(db.String(50), default="228")
    teacher_count = db.Column(db.String(50), default="")
    staff_count = db.Column(db.String(50), default="")
    grades_text = db.Column(db.String(100), default="ECD/Nursery – Grade 10")
    admission_session = db.Column(db.String(50), default="2083 B.S.")
    office_hours = db.Column(db.String(200), default="Sunday – Friday, 9:00 AM – 4:00 PM")
    school_type = db.Column(db.String(100), default="Private, Co-Educational Day School")
    school_code = db.Column(db.String(50), default="050640033")
    municipality = db.Column(db.String(100), default="Urlabari Municipality")
    district = db.Column(db.String(100), default="Morang")
    province = db.Column(db.String(100), default="Koshi Province")
    country = db.Column(db.String(50), default="Nepal")
    admission_open = db.Column(db.Boolean, default=True)
    response_time = db.Column(db.String(50), default="30 minutes")
    custom_response_time = db.Column(db.String(100), default="")
    auto_reply_enabled = db.Column(db.Boolean, default=True)
    show_nepali_date = db.Column(db.Boolean, default=False)
    theme_primary = db.Column(db.String(20), default="#0a2540")
    theme_secondary = db.Column(db.String(20), default="#1e4d8c")
    theme_accent = db.Column(db.String(20), default="#c9a227")
    theme_cta = db.Column(db.String(20), default="#c41e3a")
    footer_text = db.Column(db.Text, default="")
    copyright_text = db.Column(db.String(300), default="")
    updated_at = db.Column(db.DateTime, default=lambda: now_nepal(), onupdate=lambda: now_nepal())


class NavigationItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    url = db.Column(db.String(300), default="#")
    parent_id = db.Column(db.Integer, db.ForeignKey("navigation_item.id"), nullable=True)
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    is_cta = db.Column(db.Boolean, default=False)
    target_blank = db.Column(db.Boolean, default=False)
    children = db.relationship("NavigationItem", backref=db.backref("parent", remote_side=[id]))


class HeroSlide(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), default="")
    subtitle = db.Column(db.String(300), default="")
    description = db.Column(db.Text, default="")
    image_url = db.Column(db.String(500), default="")
    image_public_id = db.Column(db.String(300), default="")
    button1_text = db.Column(db.String(100), default="")
    button1_url = db.Column(db.String(300), default="")
    button2_text = db.Column(db.String(100), default="")
    button2_url = db.Column(db.String(300), default="")
    overlay_opacity = db.Column(db.Float, default=0.5)
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    schedule_start = db.Column(db.DateTime, nullable=True)
    schedule_end = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: now_nepal())


class PrincipalMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), default="")
    designation = db.Column(db.String(100), default="Principal")
    photo_url = db.Column(db.String(500), default="")
    photo_public_id = db.Column(db.String(300), default="")
    short_message = db.Column(db.Text, default="")
    full_message = db.Column(db.Text, default="")
    is_active = db.Column(db.Boolean, default=True)
    updated_at = db.Column(db.DateTime, default=lambda: now_nepal(), onupdate=lambda: now_nepal())


class CoordinatorMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), default="")
    designation = db.Column(db.String(100), default="Academic Coordinator")
    photo_url = db.Column(db.String(500), default="")
    photo_public_id = db.Column(db.String(300), default="")
    message = db.Column(db.Text, default="")
    is_active = db.Column(db.Boolean, default=True)
    updated_at = db.Column(db.DateTime, default=lambda: now_nepal(), onupdate=lambda: now_nepal())


class Grade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, default="")
    class_teacher = db.Column(db.String(100), default="")
    image_url = db.Column(db.String(500), default="")
    image_public_id = db.Column(db.String(300), default="")
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    subjects = db.relationship("Subject", backref="grade", cascade="all, delete-orphan")


class Subject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    grade_id = db.Column(db.Integer, db.ForeignKey("grade.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, default="")
    sort_order = db.Column(db.Integer, default=0)


class Teacher(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    photo_url = db.Column(db.String(500), default="")
    photo_public_id = db.Column(db.String(300), default="")
    position = db.Column(db.String(100), default="")
    department = db.Column(db.String(100), default="")
    qualification = db.Column(db.String(200), default="")
    experience = db.Column(db.String(100), default="")
    short_bio = db.Column(db.Text, default="")
    email = db.Column(db.String(120), default="")
    phone = db.Column(db.String(50), default="")
    facebook = db.Column(db.String(300), default="")
    linkedin = db.Column(db.String(300), default="")
    sort_order = db.Column(db.Integer, default=0)
    is_featured = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: now_nepal())


class Facility(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, default="")
    icon = db.Column(db.String(50), default="fa-building")
    image_url = db.Column(db.String(500), default="")
    image_public_id = db.Column(db.String(300), default="")
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)


class Activity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    image_url = db.Column(db.String(500), default="")
    image_public_id = db.Column(db.String(300), default="")
    category = db.Column(db.String(100), default="General")
    activity_date = db.Column(db.Date, nullable=True)
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: now_nepal())


class GalleryImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), default="")
    description = db.Column(db.Text, default="")
    image_url = db.Column(db.String(500), nullable=False)
    image_public_id = db.Column(db.String(300), default="")
    category = db.Column(db.String(100), default="School Life")
    sort_order = db.Column(db.Integer, default=0)
    is_featured = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: now_nepal())


class News(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    slug = db.Column(db.String(350), unique=True)
    content = db.Column(db.Text, default="")
    excerpt = db.Column(db.Text, default="")
    cover_image = db.Column(db.String(500), default="")
    cover_public_id = db.Column(db.String(300), default="")
    attachment_url = db.Column(db.String(500), default="")
    attachment_public_id = db.Column(db.String(300), default="")
    category = db.Column(db.String(100), default="General")
    author = db.Column(db.String(100), default="Admin")
    status = db.Column(db.String(20), default="draft")  # draft, published
    is_featured = db.Column(db.Boolean, default=False)
    published_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: now_nepal())
    updated_at = db.Column(db.DateTime, default=lambda: now_nepal(), onupdate=lambda: now_nepal())


class Notice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, default="")
    category = db.Column(db.String(100), default="General")
    is_important = db.Column(db.Boolean, default=False)
    pdf_url = db.Column(db.String(500), default="")
    external_url = db.Column(db.String(500), default="")
    published_at = db.Column(db.DateTime, default=lambda: now_nepal())
    expiry_date = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: now_nepal())


class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    event_date = db.Column(db.Date, nullable=True)
    start_time = db.Column(db.String(20), default="")
    end_time = db.Column(db.String(20), default="")
    venue = db.Column(db.String(200), default="")
    image_url = db.Column(db.String(500), default="")
    image_public_id = db.Column(db.String(300), default="")
    organizer = db.Column(db.String(100), default="")
    registration_url = db.Column(db.String(500), default="")
    status = db.Column(db.String(20), default="upcoming")  # upcoming, ongoing, completed, cancelled
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: now_nepal())


class AdmissionApplication(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.String(50), unique=True)
    student_name = db.Column(db.String(150), nullable=False)
    date_of_birth = db.Column(db.Date, nullable=True)
    gender = db.Column(db.String(20), default="")
    applying_grade = db.Column(db.String(50), default="")
    previous_school = db.Column(db.String(200), default="")
    previous_grade = db.Column(db.String(50), default="")
    parent_name = db.Column(db.String(150), nullable=False)
    relationship = db.Column(db.String(50), default="Parent")
    phone = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(120), default="")
    address = db.Column(db.Text, default="")
    message = db.Column(db.Text, default="")
    photo_url = db.Column(db.String(500), default="")
    document_url = db.Column(db.String(500), default="")
    status = db.Column(db.String(30), default="New")  # New, Under Review, Contacted, Approved, Rejected, Completed
    admin_notes = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=lambda: now_nepal())
    updated_at = db.Column(db.DateTime, default=lambda: now_nepal(), onupdate=lambda: now_nepal())


class ContactInquiry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(50), default="")
    email = db.Column(db.String(120), default="")
    subject = db.Column(db.String(200), default="")
    message = db.Column(db.Text, nullable=False)
    document_url = db.Column(db.String(500), default="")
    status = db.Column(db.String(20), default="New")  # New, Read, Replied, Archived
    admin_notes = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=lambda: now_nepal())
    updated_at = db.Column(db.DateTime, default=lambda: now_nepal(), onupdate=lambda: now_nepal())


class NewsletterSubscriber(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: now_nepal())


class EmailTemplate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    subject = db.Column(db.String(300), default="")
    body = db.Column(db.Text, default="")
    is_active = db.Column(db.Boolean, default=True)
    updated_at = db.Column(db.DateTime, default=lambda: now_nepal(), onupdate=lambda: now_nepal())


class SEOSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    page_key = db.Column(db.String(50), unique=True, nullable=False)
    title = db.Column(db.String(200), default="")
    meta_description = db.Column(db.Text, default="")
    og_title = db.Column(db.String(200), default="")
    og_description = db.Column(db.Text, default="")
    og_image = db.Column(db.String(500), default="")
    canonical_url = db.Column(db.String(300), default="")
    updated_at = db.Column(db.DateTime, default=lambda: now_nepal(), onupdate=lambda: now_nepal())


class HomepageSection(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    section_key = db.Column(db.String(50), unique=True, nullable=False)
    title = db.Column(db.String(100), default="")
    is_enabled = db.Column(db.Boolean, default=True)
    sort_order = db.Column(db.Integer, default=0)


class FAQ(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.String(500), nullable=False)
    answer = db.Column(db.Text, default="")
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)


class Download(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    file_url = db.Column(db.String(500), default="")
    category = db.Column(db.String(100), default="General")
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: now_nepal())


class NoticeTickerSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    is_enabled = db.Column(db.Boolean, default=True)
    speed = db.Column(db.Integer, default=40)  # seconds for full scroll
    max_items = db.Column(db.Integer, default=5)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_profile():
    profile = SchoolProfile.query.first()
    if not profile:
        profile = SchoolProfile(
            description=(
                "New Vision Academy is a private school located in Urlabari-8, Morang, "
                "Koshi Province. The school provides education from ECD/Nursery through "
                "Grade 10 and serves students as a co-educational day school."
            ),
            vision="Information coming soon.",
            mission="Information coming soon.",
            core_values="Information coming soon.",
            why_choose_us="Information coming soon.",
            history="Information coming soon.",
            motto="Building Knowledge. Character. Confidence.",
        )
        db.session.add(profile)
        db.session.commit()
    return profile


def get_seo(page_key, defaults=None):
    seo = SEOSetting.query.filter_by(page_key=page_key).first()
    if not seo and defaults:
        seo = SEOSetting(page_key=page_key, **defaults)
        db.session.add(seo)
        db.session.commit()
    return seo


def slugify(text):
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:80]


def notify_subscribers(update_type, title, summary="", link_path="/", file_url=""):
    """Email all active newsletter subscribers about a new update.
    Optional file_url includes view/download links for attached files.
    """
    try:
        subs = NewsletterSubscriber.query.filter_by(is_active=True).all()
        if not subs:
            return 0
        profile = get_profile()
        school = profile.school_name if profile else "New Vision Academy"
        base = (profile.website if profile and profile.website else "").rstrip("/")
        if not base:
            base = request.url_root.rstrip("/") if request else ""
        full_link = f"{base}{link_path}" if link_path.startswith("/") else link_path
        subject = f"[{school}] New {update_type}: {title}"

        file_block = ""
        if file_url:
            file_block = f"""
          <div style="background:#f7fafc;border:1px solid #e2e8f0;border-radius:8px;padding:14px 16px;margin:16px 0">
            <p style="margin:0 0 8px;font-weight:600;color:#0a2540">📎 Attached file</p>
            <p style="margin:0 0 10px;font-size:13px;word-break:break-all;color:#4a5568">{file_url}</p>
            <a href="{file_url}" style="background:#1e4d8c;color:#fff;padding:8px 14px;text-decoration:none;border-radius:6px;display:inline-block;margin-right:8px;font-size:14px">View / Open file</a>
            <a href="{file_url}" style="background:#fff;color:#1e4d8c;padding:8px 14px;text-decoration:none;border-radius:6px;display:inline-block;border:1px solid #1e4d8c;font-size:14px">Download</a>
          </div>
            """

        body = f"""
        <div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto">
          <h2 style="color:#0a2540">{school}</h2>
          <p>A new <strong>{update_type}</strong> has been published:</p>
          <h3 style="color:#1e4d8c">{title}</h3>
          <p>{summary or ''}</p>
          {file_block}
          <p><a href="{full_link}" style="background:#c41e3a;color:#fff;padding:10px 18px;text-decoration:none;border-radius:6px;display:inline-block">View on website</a></p>
          <hr style="border:none;border-top:1px solid #eee;margin:24px 0">
          <p style="font-size:12px;color:#718096">You received this because you subscribed to updates from {school}.</p>
        </div>
        """
        sent = 0
        for s in subs:
            if send_email(subject, s.email, body):
                sent += 1
        return sent
    except Exception as e:
        app.logger.error(f"notify_subscribers error: {e}")
        return 0


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_id"):
            flash("Please log in to access the admin panel.", "warning")
            return redirect(url_for("admin_login"))
        user = AdminUser.query.get(session["admin_id"])
        if not user or not user.is_active:
            session.clear()
            flash("Session expired. Please log in again.", "warning")
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated



def save_local_image(file, folder="uploads"):
    """Save uploaded image to static folder when Cloudinary is unavailable."""
    if not file or not file.filename:
        return None
    import uuid
    from werkzeug.utils import secure_filename
    ext = os.path.splitext(secure_filename(file.filename))[1].lower() or ".jpg"
    if ext not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        return None
    name = f"{uuid.uuid4().hex[:12]}{ext}"
    dest_dir = os.path.join(app.root_path, "static", "images", folder)
    os.makedirs(dest_dir, exist_ok=True)
    path_full = os.path.join(dest_dir, name)
    file.save(path_full)
    return f"/static/images/{folder}/{name}"


def upload_or_local(file, folder="newvisionacademy"):
    """Try Cloudinary first. On Vercel local disk is read-only so Cloudinary is required."""
    if not file or not getattr(file, "filename", None):
        return None
    result = upload_image(file, folder=folder)
    if result and result.get("url"):
        return result
    # Local fallback only works outside Vercel
    if not os.environ.get("VERCEL"):
        local_folder = folder.replace("newvisionacademy/", "").replace("newvisionacademy", "uploads")
        url = save_local_image(file, folder=local_folder or "uploads")
        if url:
            return {"url": url, "public_id": ""}
    return None

def generate_application_id():
    now = now_nepal()
    count = AdmissionApplication.query.count() + 1
    return f"NVA-{now.strftime('%Y%m%d')}-{count:04d}"


# ---------------------------------------------------------------------------
# Context processors
# ---------------------------------------------------------------------------

@app.context_processor
def inject_globals():
    profile = get_profile()
    nav_items = NavigationItem.query.filter_by(is_active=True, parent_id=None).order_by(NavigationItem.sort_order).all()
    ticker = NoticeTickerSetting.query.first()
    notices_ticker = []
    if ticker and ticker.is_enabled:
        notices_ticker = (
            Notice.query.filter_by(is_active=True)
            .order_by(Notice.published_at.desc())
            .limit(ticker.max_items or 5)
            .all()
        )
    return {
        "profile": profile,
        "nav_items": nav_items,
        "notices_ticker": notices_ticker,
        "ticker_setting": ticker,
        "format_date": format_date,
        "format_time": format_time,
        "format_datetime": format_datetime,
        "now_nepal": now_nepal,
        "current_year": now_nepal().year,
    }


# ---------------------------------------------------------------------------
# Public Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    slides = HeroSlide.query.filter_by(is_active=True).order_by(HeroSlide.sort_order).all()
    principal = PrincipalMessage.query.filter_by(is_active=True).first()
    coordinator = CoordinatorMessage.query.filter_by(is_active=True).first()
    facilities = Facility.query.filter_by(is_active=True).order_by(Facility.sort_order).limit(8).all()
    activities = Activity.query.filter_by(is_active=True).order_by(Activity.sort_order).limit(6).all()
    teachers = Teacher.query.filter_by(is_active=True, is_featured=True).order_by(Teacher.sort_order).limit(4).all()
    if not teachers:
        teachers = Teacher.query.filter_by(is_active=True).order_by(Teacher.sort_order).limit(4).all()
    news_list = (
        News.query.filter_by(status="published")
        .order_by(News.published_at.desc())
        .limit(3)
        .all()
    )
    notices = Notice.query.filter_by(is_active=True).order_by(Notice.published_at.desc()).limit(5).all()
    events = (
        Event.query.filter_by(is_active=True, status="upcoming")
        .order_by(Event.event_date.asc())
        .limit(3)
        .all()
    )
    gallery = GalleryImage.query.filter_by(is_active=True, is_featured=True).order_by(GalleryImage.sort_order).limit(8).all()
    if not gallery:
        gallery = GalleryImage.query.filter_by(is_active=True).order_by(GalleryImage.sort_order).limit(8).all()
    grades = Grade.query.filter_by(is_active=True).order_by(Grade.sort_order).all()
    sections = {s.section_key: s for s in HomepageSection.query.all()}
    seo = get_seo("home", {
        "title": "New Vision Academy – Urlabari-8, Morang | ECD to Grade 10",
        "meta_description": "New Vision Academy is a private co-educational day school located at Urlabari-8, Morang, Koshi Province, Nepal, providing education from ECD/Nursery to Grade 10.",
        "og_title": "New Vision Academy – Urlabari-8, Morang | ECD to Grade 10",
        "og_description": "Private Co-Educational Day School | ECD to Grade 10 | Admission Open 2083 B.S. | Urlabari, Morang",
    })
    return render_template(
        "index.html",
        slides=slides,
        principal=principal,
        coordinator=coordinator,
        facilities=facilities,
        activities=activities,
        teachers=teachers,
        news_list=news_list,
        notices=notices,
        events=events,
        gallery=gallery,
        grades=grades,
        sections=sections,
        seo=seo,
    )


@app.route("/about")
def about():
    principal = PrincipalMessage.query.filter_by(is_active=True).first()
    coordinator = CoordinatorMessage.query.filter_by(is_active=True).first()
    seo = get_seo("about", {
        "title": "About Us – New Vision Academy",
        "meta_description": "Learn about New Vision Academy, a private school in Urlabari-8, Morang offering quality education from ECD to Grade 10.",
    })
    return render_template("about.html", principal=principal, coordinator=coordinator, seo=seo)


@app.route("/history")
def history():
    seo = get_seo("history", {"title": "Our History – New Vision Academy"})
    return render_template("history.html", seo=seo)


@app.route("/principal")
def principal_page():
    principal = PrincipalMessage.query.filter_by(is_active=True).first()
    seo = get_seo("principal", {"title": "Principal's Message – New Vision Academy"})
    return render_template("principal.html", principal=principal, seo=seo)


@app.route("/coordinator")
def coordinator_page():
    coordinator = CoordinatorMessage.query.filter_by(is_active=True).first()
    seo = get_seo("coordinator", {"title": "Academic Coordinator – New Vision Academy"})
    return render_template("coordinator.html", coordinator=coordinator, seo=seo)


@app.route("/academics")
def academics():
    grades = Grade.query.filter_by(is_active=True).order_by(Grade.sort_order).all()
    seo = get_seo("academics", {"title": "Academics – New Vision Academy"})
    return render_template("academics.html", grades=grades, seo=seo)


@app.route("/teachers")
def teachers():
    teachers_list = Teacher.query.filter_by(is_active=True).order_by(Teacher.sort_order).all()
    seo = get_seo("teachers", {"title": "Teachers & Staff – New Vision Academy"})
    return render_template("teachers.html", teachers=teachers_list, seo=seo)


@app.route("/classes")
def classes():
    grades = Grade.query.filter_by(is_active=True).order_by(Grade.sort_order).all()
    seo = get_seo("classes", {"title": "Classes – New Vision Academy"})
    return render_template("classes.html", grades=grades, seo=seo)


@app.route("/facilities")
def facilities():
    items = Facility.query.filter_by(is_active=True).order_by(Facility.sort_order).all()
    seo = get_seo("facilities", {"title": "Facilities – New Vision Academy"})
    return render_template("facilities.html", facilities=items, seo=seo)


@app.route("/activities")
def activities():
    items = Activity.query.filter_by(is_active=True).order_by(Activity.sort_order).all()
    seo = get_seo("activities", {"title": "Activities – New Vision Academy"})
    return render_template("activities.html", activities=items, seo=seo)


@app.route("/gallery")
def gallery():
    category = request.args.get("category", "")
    query = GalleryImage.query.filter_by(is_active=True)
    if category:
        query = query.filter_by(category=category)
    images = query.order_by(GalleryImage.sort_order).all()
    categories = db.session.query(GalleryImage.category).distinct().all()
    categories = [c[0] for c in categories if c[0]]
    seo = get_seo("gallery", {"title": "Gallery – New Vision Academy"})
    return render_template("gallery.html", images=images, categories=categories, current_category=category, seo=seo)


@app.route("/news")
def news():
    page = request.args.get("page", 1, type=int)
    pagination = (
        News.query.filter_by(status="published")
        .order_by(News.published_at.desc())
        .paginate(page=page, per_page=9, error_out=False)
    )
    seo = get_seo("news", {"title": "News – New Vision Academy"})
    return render_template("news.html", pagination=pagination, seo=seo)


@app.route("/news/<slug>")
def news_detail(slug):
    item = News.query.filter_by(slug=slug, status="published").first_or_404()
    related = (
        News.query.filter(News.status == "published", News.id != item.id)
        .order_by(News.published_at.desc())
        .limit(3)
        .all()
    )
    seo = SEOSetting(
        page_key="news_detail",
        title=f"{item.title} – New Vision Academy",
        meta_description=item.excerpt or item.title,
        og_title=item.title,
        og_image=item.cover_image,
    )
    return render_template("news_detail.html", news=item, related=related, seo=seo)



@app.route("/media/file")
def media_file():
    """Proxy Cloudinary (or allowed) files with correct Content-Type so PDF/docs open properly."""
    import urllib.request
    import urllib.parse
    from flask import Response, stream_with_context

    raw_url = (request.args.get("url") or "").strip()
    as_download = request.args.get("download") in ("1", "true", "yes")
    if not raw_url:
        abort(400)

    # Security: only allow Cloudinary + our own domain
    parsed = urllib.parse.urlparse(raw_url)
    host = (parsed.hostname or "").lower()
    allowed = (
        host.endswith("cloudinary.com")
        or host.endswith("res.cloudinary.com")
        or host in ("localhost", "127.0.0.1")
    )
    if not allowed:
        abort(403)

    # Fix common broken PDF delivery path
    url = raw_url
    low = url.lower()
    if (low.endswith(".pdf") or ".pdf?" in low) and "/image/upload/" in url:
        url = url.replace("/image/upload/", "/raw/upload/", 1)

    # Guess content-type from path
    path = urllib.parse.urlparse(url).path.lower()
    ctype = "application/octet-stream"
    filename = path.rsplit("/", 1)[-1] or "file"
    if path.endswith(".pdf") or ".pdf" in path:
        ctype = "application/pdf"
        if not filename.lower().endswith(".pdf"):
            filename += ".pdf"
    elif path.endswith((".jpg", ".jpeg")):
        ctype = "image/jpeg"
    elif path.endswith(".png"):
        ctype = "image/png"
    elif path.endswith(".gif"):
        ctype = "image/gif"
    elif path.endswith(".webp"):
        ctype = "image/webp"
    elif path.endswith(".mp4"):
        ctype = "video/mp4"
    elif path.endswith(".webm"):
        ctype = "video/webm"
    elif path.endswith(".mp3"):
        ctype = "audio/mpeg"
    elif path.endswith(".doc"):
        ctype = "application/msword"
    elif path.endswith(".docx"):
        ctype = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif path.endswith(".xls"):
        ctype = "application/vnd.ms-excel"
    elif path.endswith(".xlsx"):
        ctype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif path.endswith(".ppt"):
        ctype = "application/vnd.ms-powerpoint"
    elif path.endswith(".pptx"):
        ctype = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    elif path.endswith(".zip"):
        ctype = "application/zip"

    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "NewVisionAcademyMediaProxy/1.0",
                "Accept": "*/*",
            },
        )
        upstream = urllib.request.urlopen(req, timeout=60)
        upstream_ctype = upstream.headers.get("Content-Type", "")
        # Prefer our guessed type for PDFs (upstream may send text/plain wrongly)
        if ctype == "application/pdf" or (upstream_ctype and "pdf" in upstream_ctype.lower()):
            ctype = "application/pdf"
        elif upstream_ctype and "text/html" not in upstream_ctype.lower() and "text/plain" not in upstream_ctype.lower():
            # use upstream if it looks legitimate
            if not path.endswith(".pdf"):
                ctype = upstream_ctype.split(";")[0].strip() or ctype

        data = upstream.read()
        upstream.close()

        # Validate PDF magic bytes
        if ctype == "application/pdf" and data[:4] != b"%PDF":
            # still serve but log
            app.logger.warning("PDF proxy: missing %%PDF magic for %s", url)

        disp = "attachment" if as_download else "inline"
        # RFC 5987 filename
        safe_name = filename.replace('"', "")
        headers = {
            "Content-Type": ctype,
            "Content-Disposition": f'{disp}; filename="{safe_name}"',
            "Content-Length": str(len(data)),
            "Cache-Control": "public, max-age=86400",
            "X-Content-Type-Options": "nosniff",
        }
        return Response(data, headers=headers)
    except Exception as e:
        app.logger.error("media_file proxy error: %s url=%s", e, url)
        abort(502)


@app.template_filter("proxy_url")
def media_proxy_url(url, download=False):
    """Build same-origin proxy URL so PDF opens with correct Content-Type."""
    if not url:
        return url
    from urllib.parse import quote
    fixed = fix_media_url(url)
    q = quote(str(fixed), safe="")
    base = f"/media/file?url={q}"
    if download:
        base += "&download=1"
    return base



@app.route("/notices")
def notices():
    items = Notice.query.filter_by(is_active=True).order_by(Notice.published_at.desc()).all()
    seo = get_seo("notices", {"title": "Notice Board – New Vision Academy"})
    return render_template("notices.html", notices=items, seo=seo)


@app.route("/notices/<int:notice_id>")
def notice_detail(notice_id):
    item = Notice.query.filter_by(id=notice_id, is_active=True).first_or_404()
    seo = SEOSetting(page_key="notice_detail", title=f"{item.title} – New Vision Academy")
    return render_template("notice_detail.html", notice=item, seo=seo)


@app.route("/events")
def events():
    items = Event.query.filter_by(is_active=True).order_by(Event.event_date.desc()).all()
    seo = get_seo("events", {"title": "Events – New Vision Academy"})
    return render_template("events.html", events=items, seo=seo)


@app.route("/admission", methods=["GET", "POST"])
def admission():
    profile = get_profile()
    grades = Grade.query.filter_by(is_active=True).order_by(Grade.sort_order).all()
    if request.method == "POST":
        try:
            app_id = generate_application_id()
            dob = None
            if request.form.get("date_of_birth"):
                dob = datetime.strptime(request.form["date_of_birth"], "%Y-%m-%d").date()
            application = AdmissionApplication(
                application_id=app_id,
                student_name=request.form.get("student_name", "").strip(),
                date_of_birth=dob,
                gender=request.form.get("gender", ""),
                applying_grade=request.form.get("applying_grade", ""),
                previous_school=request.form.get("previous_school", ""),
                previous_grade=request.form.get("previous_grade", ""),
                parent_name=request.form.get("parent_name", "").strip(),
                relationship=request.form.get("relationship", "Parent"),
                phone=request.form.get("phone", "").strip(),
                email=request.form.get("email", "").strip(),
                address=request.form.get("address", ""),
                message=request.form.get("message", ""),
            )
            # Optional photo upload
            if "photo" in request.files and request.files["photo"].filename:
                result = upload_image(request.files["photo"], folder="newvisionacademy/admissions")
                if result:
                    application.photo_url = result["url"]
            db.session.add(application)
            db.session.commit()

            # Auto-reply
            if profile.auto_reply_enabled and application.email:
                tmpl = EmailTemplate.query.filter_by(slug="admission_received", is_active=True).first()
                rt = get_response_time_text(profile)
                if tmpl:
                    subject = render_template_vars(
                        tmpl.subject,
                        parent_name=application.parent_name,
                        student_name=application.student_name,
                        application_id=app_id,
                        school_name=profile.school_name,
                        response_time=rt,
                    )
                    body = render_template_vars(
                        tmpl.body,
                        parent_name=application.parent_name,
                        student_name=application.student_name,
                        application_id=app_id,
                        school_name=profile.school_name,
                        school_address=profile.address,
                        response_time=rt,
                    )
                else:
                    subject = f"Admission Inquiry Received – {profile.school_name}"
                    body = f"""
                    <p>Dear {application.parent_name},</p>
                    <p>Thank you for submitting an admission inquiry/application to {profile.school_name}.</p>
                    <p>We have received the information successfully. Application ID: <strong>{app_id}</strong></p>
                    <p>Our school administration will review your submission and contact you within {rt}.</p>
                    <p>{profile.school_name}<br>{profile.address}</p>
                    """
                send_email(subject, application.email, body)

            # Notify admin
            if profile.email:
                admin_body = f"""
                <p>New admission application received.</p>
                <p><strong>ID:</strong> {app_id}<br>
                <strong>Student:</strong> {application.student_name}<br>
                <strong>Grade:</strong> {application.applying_grade}<br>
                <strong>Parent:</strong> {application.parent_name}<br>
                <strong>Phone:</strong> {application.phone}</p>
                """
                send_email(f"New Admission Application – {app_id}", profile.email, admin_body)

            flash("Your admission application has been submitted successfully. We will contact you soon.", "success")
            return redirect(url_for("admission"))
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Admission error: {e}")
            flash("Something went wrong. Please try again or contact the school directly.", "danger")
    seo = get_seo("admission", {
        "title": "Admission – New Vision Academy",
        "meta_description": f"Apply for admission to New Vision Academy for session {profile.admission_session}. ECD/Nursery to Grade 10.",
    })
    return render_template("admission.html", grades=grades, seo=seo)


@app.route("/contact", methods=["GET", "POST"])
def contact():
    profile = get_profile()
    if request.method == "POST":
        try:
            inquiry = ContactInquiry(
                name=request.form.get("name", "").strip(),
                phone=request.form.get("phone", "").strip(),
                email=request.form.get("email", "").strip(),
                subject=request.form.get("subject", "").strip(),
                message=request.form.get("message", "").strip(),
            )
            if "document" in request.files and request.files["document"].filename:
                result = upload_file(request.files["document"], folder="newvisionacademy/inquiries")
                if result:
                    inquiry.document_url = result["url"]
            db.session.add(inquiry)
            db.session.commit()

            rt = get_response_time_text(profile)
            if profile.auto_reply_enabled and inquiry.email:
                tmpl = EmailTemplate.query.filter_by(slug="contact_received", is_active=True).first()
                if tmpl:
                    subject = render_template_vars(tmpl.subject, customer_name=inquiry.name, school_name=profile.school_name, response_time=rt)
                    body = render_template_vars(
                        tmpl.body,
                        customer_name=inquiry.name,
                        school_name=profile.school_name,
                        school_address=profile.address,
                        response_time=rt,
                    )
                else:
                    subject = f"We received your message – {profile.school_name}"
                    body = f"""
                    <p>Dear {inquiry.name},</p>
                    <p>Thank you for contacting {profile.school_name}. We have received your message and will respond within {rt}.</p>
                    <p>{profile.school_name}<br>{profile.address}</p>
                    """
                send_email(subject, inquiry.email, body)

            if profile.email:
                doc_line = f'<p>Document: <a href="{inquiry.document_url}">{inquiry.document_url}</a></p>' if inquiry.document_url else ""
                admin_body = f"""
                <p>New contact inquiry from <strong>{inquiry.name}</strong></p>
                <p>Phone: {inquiry.phone}<br>Email: {inquiry.email}<br>Subject: {inquiry.subject}</p>
                <p>{inquiry.message}</p>
                {doc_line}
                """
                send_email(f"Contact Inquiry – {inquiry.subject or inquiry.name}", profile.email, admin_body)

            flash("Thank you! Your message has been sent. We will get back to you soon.", "success")
            return redirect(url_for("contact"))
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Contact error: {e}")
            flash("Something went wrong. Please try again.", "danger")
    seo = get_seo("contact", {"title": "Contact Us – New Vision Academy"})
    return render_template("contact.html", seo=seo)


@app.route("/subscribe", methods=["POST"])
def subscribe():
    email = (request.form.get("email") or (request.json or {}).get("email") or "").strip().lower()
    if not email or "@" not in email:
        if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"ok": False, "message": "Please enter a valid email address."}), 400
        flash("Please enter a valid email address.", "danger")
        return redirect(request.referrer or url_for("index"))
    existing = NewsletterSubscriber.query.filter_by(email=email).first()
    if existing:
        if not existing.is_active:
            existing.is_active = True
            db.session.commit()
        msg = "You are already subscribed. Thank you!"
    else:
        db.session.add(NewsletterSubscriber(email=email, is_active=True))
        db.session.commit()
        msg = "Thank you! You will receive updates about news, notices and events."
    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True, "message": msg})
    flash(msg, "success")
    return redirect(request.referrer or url_for("index"))


@app.route("/faq")
def faq():
    items = FAQ.query.filter_by(is_active=True).order_by(FAQ.sort_order).all()
    seo = get_seo("faq", {"title": "FAQ – New Vision Academy"})
    return render_template("faq.html", faqs=items, seo=seo)


@app.route("/downloads")
def downloads():
    items = Download.query.filter_by(is_active=True).order_by(Download.sort_order).all()
    seo = get_seo("downloads", {"title": "Downloads – New Vision Academy"})
    return render_template("downloads.html", downloads=items, seo=seo)


@app.route("/privacy")
def privacy():
    seo = get_seo("privacy", {"title": "Privacy Policy – New Vision Academy"})
    return render_template("privacy.html", seo=seo)


@app.route("/terms")
def terms():
    seo = get_seo("terms", {"title": "Terms of Use – New Vision Academy"})
    return render_template("terms.html", seo=seo)


@app.route("/sitemap.xml")
def sitemap():
    pages = [
        "/", "/about", "/history", "/principal", "/coordinator", "/academics",
        "/teachers", "/classes", "/facilities", "/activities", "/gallery",
        "/news", "/notices", "/events", "/admission", "/contact", "/faq",
        "/downloads", "/privacy", "/terms",
    ]
    news_items = News.query.filter_by(status="published").all()
    base = request.url_root.rstrip("/")
    xml = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for p in pages:
        xml.append(f"<url><loc>{base}{p}</loc><changefreq>weekly</changefreq></url>")
    for n in news_items:
        xml.append(f"<url><loc>{base}/news/{n.slug}</loc><changefreq>monthly</changefreq></url>")
    xml.append("</urlset>")
    response = make_response("\n".join(xml))
    response.headers["Content-Type"] = "application/xml"
    return response


@app.route("/robots.txt")
def robots():
    content = """User-agent: *
Allow: /
Disallow: /admin
Disallow: /admin/
Sitemap: {}/sitemap.xml
""".format(request.url_root.rstrip("/"))
    response = make_response(content)
    response.headers["Content-Type"] = "text/plain"
    return response


# ---------------------------------------------------------------------------
# Admin Auth
# ---------------------------------------------------------------------------

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("admin_id"):
        return redirect(url_for("admin_dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = AdminUser.query.filter_by(email=email, is_active=True).first()
        if user and user.check_password(password):
            session.permanent = True
            session["admin_id"] = user.id
            session["admin_name"] = user.name
            user.last_login = now_nepal()
            db.session.commit()
            flash("Welcome back!", "success")
            return redirect(url_for("admin_dashboard"))
        flash("Invalid email or password.", "danger")
    return render_template("admin/login.html")


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("admin_login"))


# ---------------------------------------------------------------------------
# Admin Dashboard & CRUD (simplified comprehensive handlers)
# ---------------------------------------------------------------------------

@app.route("/admin/")
@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    stats = {
        "teachers": Teacher.query.count(),
        "news": News.query.count(),
        "notices": Notice.query.count(),
        "events": Event.query.count(),
        "gallery": GalleryImage.query.count(),
        "applications": AdmissionApplication.query.count(),
        "inquiries": ContactInquiry.query.count(),
        "new_applications": AdmissionApplication.query.filter_by(status="New").count(),
        "new_inquiries": ContactInquiry.query.filter_by(status="New").count(),
    }
    recent_apps = AdmissionApplication.query.order_by(AdmissionApplication.created_at.desc()).limit(5).all()
    recent_inquiries = ContactInquiry.query.order_by(ContactInquiry.created_at.desc()).limit(5).all()
    recent_news = News.query.order_by(News.created_at.desc()).limit(5).all()
    upcoming_events = Event.query.filter_by(status="upcoming").order_by(Event.event_date.asc()).limit(5).all()
    return render_template(
        "admin/dashboard.html",
        stats=stats,
        recent_apps=recent_apps,
        recent_inquiries=recent_inquiries,
        recent_news=recent_news,
        upcoming_events=upcoming_events,
    )


@app.route("/admin/settings", methods=["GET", "POST"])
@admin_required
def admin_settings():
    profile = get_profile()
    if request.method == "POST":
        for field in [
            "school_name", "short_name", "address", "phone", "phone2", "email", "website",
            "facebook", "instagram", "youtube", "tiktok", "google_maps", "description",
            "motto", "vision", "mission", "core_values", "why_choose_us", "history",
            "established_year", "student_count", "teacher_count", "staff_count",
            "grades_text", "admission_session", "office_hours", "school_type",
            "school_code", "municipality", "district", "province", "country",
            "response_time", "custom_response_time", "footer_text", "copyright_text",
            "theme_primary", "theme_secondary", "theme_accent", "theme_cta",
        ]:
            if field in request.form:
                setattr(profile, field, request.form.get(field, ""))
        profile.admission_open = "admission_open" in request.form
        profile.auto_reply_enabled = "auto_reply_enabled" in request.form
        profile.show_nepali_date = "show_nepali_date" in request.form
        if "logo" in request.files and request.files["logo"].filename:
            result = upload_image(request.files["logo"], folder="newvisionacademy/branding")
            if result:
                profile.logo_url = result["url"]
        if "favicon" in request.files and request.files["favicon"].filename:
            result = upload_image(request.files["favicon"], folder="newvisionacademy/branding")
            if result:
                profile.favicon_url = result["url"]
        db.session.commit()
        flash("Settings updated successfully.", "success")
        return redirect(url_for("admin_settings"))
    return render_template("admin/settings.html", profile=profile)


@app.route("/admin/homepage", methods=["GET", "POST"])
@admin_required
def admin_homepage():
    sections = HomepageSection.query.order_by(HomepageSection.sort_order).all()
    if request.method == "POST":
        for s in sections:
            s.is_enabled = f"enabled_{s.id}" in request.form
            order = request.form.get(f"order_{s.id}")
            if order is not None:
                s.sort_order = int(order)
        db.session.commit()
        flash("Homepage sections updated.", "success")
        return redirect(url_for("admin_homepage"))
    return render_template("admin/homepage.html", sections=sections)


@app.route("/admin/slider", methods=["GET", "POST"])
@admin_required
def admin_slider():
    slides = HeroSlide.query.order_by(HeroSlide.sort_order).all()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            slide = HeroSlide(
                title=request.form.get("title", ""),
                subtitle=request.form.get("subtitle", ""),
                description=request.form.get("description", ""),
                button1_text=request.form.get("button1_text", ""),
                button1_url=request.form.get("button1_url", ""),
                button2_text=request.form.get("button2_text", ""),
                button2_url=request.form.get("button2_url", ""),
                sort_order=int(request.form.get("sort_order", 0) or 0),
                is_active="is_active" in request.form,
            )
            img = request.files.get("image")
            if img and img.filename:
                result = upload_image(img, folder="newvisionacademy/slider")
                if result and result.get("url"):
                    slide.image_url = result["url"]
                    slide.image_public_id = result.get("public_id", "")
                else:
                    flash("Slide saved but image upload failed. Check Cloudinary credentials.", "warning")
            db.session.add(slide)
            db.session.commit()
            flash("Slide added.", "success")
        elif action == "edit":
            slide = HeroSlide.query.get(request.form.get("id"))
            if slide:
                slide.title = request.form.get("title", "")
                slide.subtitle = request.form.get("subtitle", "")
                slide.description = request.form.get("description", "")
                slide.button1_text = request.form.get("button1_text", "")
                slide.button1_url = request.form.get("button1_url", "")
                slide.button2_text = request.form.get("button2_text", "")
                slide.button2_url = request.form.get("button2_url", "")
                slide.sort_order = int(request.form.get("sort_order", 0) or 0)
                slide.is_active = "is_active" in request.form
                img = request.files.get("image")
                if img and img.filename:
                    # delete old image if present
                    if slide.image_public_id:
                        delete_image(slide.image_public_id)
                    result = upload_image(img, folder="newvisionacademy/slider")
                    if result and result.get("url"):
                        slide.image_url = result["url"]
                        slide.image_public_id = result.get("public_id", "")
                    else:
                        flash("Slide updated but image upload failed. Check Cloudinary credentials.", "warning")
                db.session.commit()
                flash("Slide updated.", "success")
        elif action == "delete":
            slide = HeroSlide.query.get(request.form.get("id"))
            if slide:
                if slide.image_public_id:
                    delete_image(slide.image_public_id)
                db.session.delete(slide)
                db.session.commit()
                flash("Slide deleted.", "success")
        return redirect(url_for("admin_slider"))
    return render_template("admin/slider.html", slides=slides)


@app.route("/admin/about", methods=["GET", "POST"])
@admin_required
def admin_about():
    profile = get_profile()
    if request.method == "POST":
        for field in ["description", "history", "vision", "mission", "core_values", "why_choose_us", "motto"]:
            if field in request.form:
                setattr(profile, field, request.form.get(field, ""))
        if "about_image" in request.files and request.files["about_image"].filename:
            result = upload_or_local(request.files["about_image"], folder="newvisionacademy/about")
            if result:
                if profile.about_image_public_id:
                    try:
                        delete_image(profile.about_image_public_id)
                    except Exception:
                        pass
                profile.about_image_url = result["url"]
                profile.about_image_public_id = result.get("public_id", "")
        if request.form.get("remove_about_image") == "1":
            if profile.about_image_public_id:
                try:
                    delete_image(profile.about_image_public_id)
                except Exception:
                    pass
            profile.about_image_url = ""
            profile.about_image_public_id = ""
        db.session.commit()
        flash("About content updated.", "success")
        return redirect(url_for("admin_about"))
    return render_template("admin/about.html", profile=profile)


@app.route("/admin/principal", methods=["GET", "POST"])
@admin_required
def admin_principal():
    principal = PrincipalMessage.query.first()
    if not principal:
        principal = PrincipalMessage()
        db.session.add(principal)
        db.session.commit()
    if request.method == "POST":
        principal.name = request.form.get("name", "")
        principal.designation = request.form.get("designation", "Principal")
        principal.short_message = request.form.get("short_message", "")
        principal.full_message = request.form.get("full_message", "")
        principal.is_active = "is_active" in request.form
        if "photo" in request.files and request.files["photo"].filename:
            result = upload_or_local(request.files["photo"], folder="newvisionacademy/staff")
            if result:
                principal.photo_url = result["url"]
                principal.photo_public_id = result.get("public_id", "")
        db.session.commit()
        flash("Principal message updated.", "success")
        return redirect(url_for("admin_principal"))
    return render_template("admin/principal.html", principal=principal)


@app.route("/admin/coordinator", methods=["GET", "POST"])
@admin_required
def admin_coordinator():
    coordinator = CoordinatorMessage.query.first()
    if not coordinator:
        coordinator = CoordinatorMessage()
        db.session.add(coordinator)
        db.session.commit()
    if request.method == "POST":
        coordinator.name = request.form.get("name", "")
        coordinator.designation = request.form.get("designation", "Academic Coordinator")
        coordinator.message = request.form.get("message", "")
        coordinator.is_active = "is_active" in request.form
        if "photo" in request.files and request.files["photo"].filename:
            result = upload_or_local(request.files["photo"], folder="newvisionacademy/staff")
            if result:
                coordinator.photo_url = result["url"]
                coordinator.photo_public_id = result.get("public_id", "")
        db.session.commit()
        flash("Coordinator message updated.", "success")
        return redirect(url_for("admin_coordinator"))
    return render_template("admin/coordinator.html", coordinator=coordinator)


@app.route("/admin/teachers", methods=["GET", "POST"])
@admin_required
def admin_teachers():
    teachers_list = Teacher.query.order_by(Teacher.sort_order).all()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            t = Teacher(
                full_name=request.form.get("full_name", ""),
                position=request.form.get("position", ""),
                department=request.form.get("department", ""),
                qualification=request.form.get("qualification", ""),
                experience=request.form.get("experience", ""),
                short_bio=request.form.get("short_bio", ""),
                email=request.form.get("email", ""),
                phone=request.form.get("phone", ""),
                sort_order=int(request.form.get("sort_order", 0) or 0),
                is_featured="is_featured" in request.form,
                is_active="is_active" in request.form,
            )
            if "photo" in request.files and request.files["photo"].filename:
                result = upload_or_local(request.files["photo"], folder="newvisionacademy/teachers")
                if result:
                    t.photo_url = result["url"]
                    t.photo_public_id = result.get("public_id", "")
            db.session.add(t)
            db.session.commit()
            flash("Teacher added.", "success")
        elif action == "edit":
            t = Teacher.query.get(request.form.get("id"))
            if t:
                t.full_name = request.form.get("full_name", "")
                t.position = request.form.get("position", "")
                t.department = request.form.get("department", "")
                t.qualification = request.form.get("qualification", "")
                t.experience = request.form.get("experience", "")
                t.short_bio = request.form.get("short_bio", "")
                t.email = request.form.get("email", "")
                t.phone = request.form.get("phone", "")
                t.sort_order = int(request.form.get("sort_order", 0) or 0)
                t.is_featured = "is_featured" in request.form
                t.is_active = "is_active" in request.form
                if "photo" in request.files and request.files["photo"].filename:
                    result = upload_or_local(request.files["photo"], folder="newvisionacademy/teachers")
                    if result:
                        t.photo_url = result["url"]
                        t.photo_public_id = result.get("public_id", "")
                db.session.commit()
                flash("Teacher updated.", "success")
        elif action == "delete":
            t = Teacher.query.get(request.form.get("id"))
            if t:
                db.session.delete(t)
                db.session.commit()
                flash("Teacher deleted.", "success")
        return redirect(url_for("admin_teachers"))
    return render_template("admin/teachers.html", teachers=teachers_list)


@app.route("/admin/classes", methods=["GET", "POST"])
@admin_required
def admin_classes():
    grades = Grade.query.order_by(Grade.sort_order).all()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            g = Grade(
                name=request.form.get("name", ""),
                description=request.form.get("description", ""),
                class_teacher=request.form.get("class_teacher", ""),
                sort_order=int(request.form.get("sort_order", 0) or 0),
                is_active="is_active" in request.form,
            )
            if "image" in request.files and request.files["image"].filename:
                result = upload_image(request.files["image"], folder="newvisionacademy/classes")
                if result:
                    g.image_url = result["url"]
                    g.image_public_id = result.get("public_id", "")
            db.session.add(g)
            db.session.commit()
            flash("Grade added.", "success")
        elif action == "edit":
            g = Grade.query.get(request.form.get("id"))
            if g:
                g.name = request.form.get("name", "")
                g.description = request.form.get("description", "")
                g.class_teacher = request.form.get("class_teacher", "")
                g.sort_order = int(request.form.get("sort_order", 0) or 0)
                g.is_active = "is_active" in request.form
                if "image" in request.files and request.files["image"].filename:
                    result = upload_image(request.files["image"], folder="newvisionacademy/classes")
                    if result:
                        g.image_url = result["url"]
                        g.image_public_id = result.get("public_id", "")
                db.session.commit()
                flash("Grade updated.", "success")
        elif action == "delete":
            g = Grade.query.get(request.form.get("id"))
            if g:
                db.session.delete(g)
                db.session.commit()
                flash("Grade deleted.", "success")
        return redirect(url_for("admin_classes"))
    return render_template("admin/classes.html", grades=grades)


@app.route("/admin/facilities", methods=["GET", "POST"])
@admin_required
def admin_facilities():
    items = Facility.query.order_by(Facility.sort_order).all()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            f = Facility(
                title=request.form.get("title", ""),
                description=request.form.get("description", ""),
                icon=request.form.get("icon", "fa-building"),
                sort_order=int(request.form.get("sort_order", 0) or 0),
                is_active="is_active" in request.form,
            )
            if "image" in request.files and request.files["image"].filename:
                result = upload_image(request.files["image"], folder="newvisionacademy/facilities")
                if result:
                    f.image_url = result["url"]
                    f.image_public_id = result.get("public_id", "")
            db.session.add(f)
            db.session.commit()
            flash("Facility added.", "success")
        elif action == "edit":
            f = Facility.query.get(request.form.get("id"))
            if f:
                f.title = request.form.get("title", "")
                f.description = request.form.get("description", "")
                f.icon = request.form.get("icon", "fa-building")
                f.sort_order = int(request.form.get("sort_order", 0) or 0)
                f.is_active = "is_active" in request.form
                if "image" in request.files and request.files["image"].filename:
                    result = upload_image(request.files["image"], folder="newvisionacademy/facilities")
                    if result:
                        f.image_url = result["url"]
                        f.image_public_id = result.get("public_id", "")
                db.session.commit()
                flash("Facility updated.", "success")
        elif action == "delete":
            f = Facility.query.get(request.form.get("id"))
            if f:
                db.session.delete(f)
                db.session.commit()
                flash("Facility deleted.", "success")
        return redirect(url_for("admin_facilities"))
    return render_template("admin/facilities.html", facilities=items)


@app.route("/admin/activities", methods=["GET", "POST"])
@admin_required
def admin_activities():
    items = Activity.query.order_by(Activity.sort_order).all()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            title = request.form.get("title", "") or "Activity"
            description = request.form.get("description", "")
            category = request.form.get("category", "General")
            sort_order = int(request.form.get("sort_order", 0) or 0)
            is_active = "is_active" in request.form
            activity_date = None
            if request.form.get("activity_date"):
                try:
                    activity_date = datetime.strptime(request.form["activity_date"], "%Y-%m-%d").date()
                except ValueError:
                    activity_date = None

            files = request.files.getlist("media")
            # Fallback to single "image" field for backward compatibility
            if not any(f and f.filename for f in files) and "image" in request.files:
                files = [request.files["image"]]

            uploaded = 0
            failed = 0
            valid_files = [f for f in files if f and getattr(f, "filename", None)]
            if valid_files:
                for idx, f in enumerate(valid_files):
                    # Reset stream so Cloudinary can read full file
                    try:
                        if hasattr(f, "stream") and hasattr(f.stream, "seek"):
                            f.stream.seek(0)
                        elif hasattr(f, "seek"):
                            f.seek(0)
                    except Exception:
                        pass
                    result = upload_file(f, folder="newvisionacademy/activities")
                    if not result:
                        try:
                            if hasattr(f, "stream") and hasattr(f.stream, "seek"):
                                f.stream.seek(0)
                        except Exception:
                            pass
                        result = upload_image(f, folder="newvisionacademy/activities")
                    a = Activity(
                        title=title if len(valid_files) == 1 else f"{title} ({idx + 1})",
                        description=description,
                        category=category,
                        sort_order=sort_order + idx,
                        is_active=is_active,
                        activity_date=activity_date,
                    )
                    if result:
                        a.image_url = result["url"]
                        a.image_public_id = result.get("public_id", "")
                        uploaded += 1
                    else:
                        failed += 1
                    db.session.add(a)
                db.session.commit()
                msg = f"{uploaded} file(s) uploaded successfully."
                if failed:
                    msg += f" {failed} failed (size/format/Cloudinary limit)."
                flash(msg, "success" if uploaded else "warning")
            else:
                # No media — still create one entry with title/description
                a = Activity(
                    title=title,
                    description=description,
                    category=category,
                    sort_order=sort_order,
                    is_active=is_active,
                    activity_date=activity_date,
                )
                db.session.add(a)
                db.session.commit()
                flash("Activity added (no media).", "success")
        elif action == "edit":
            a = Activity.query.get(request.form.get("id"))
            if a:
                a.title = request.form.get("title", "")
                a.description = request.form.get("description", "")
                a.category = request.form.get("category", "General")
                a.sort_order = int(request.form.get("sort_order", 0) or 0)
                a.is_active = "is_active" in request.form
                if request.form.get("activity_date"):
                    a.activity_date = datetime.strptime(request.form["activity_date"], "%Y-%m-%d").date()
                media = request.files.get("media") or request.files.get("image")
                if media and media.filename:
                    result = upload_file(media, folder="newvisionacademy/activities") or upload_image(media, folder="newvisionacademy/activities")
                    if result:
                        a.image_url = result["url"]
                        a.image_public_id = result.get("public_id", "")
                db.session.commit()
                flash("Activity updated.", "success")
        elif action == "delete":
            a = Activity.query.get(request.form.get("id"))
            if a:
                if a.image_public_id:
                    delete_image(a.image_public_id)
                db.session.delete(a)
                db.session.commit()
                flash("Activity deleted.", "success")
        return redirect(url_for("admin_activities"))
    return render_template("admin/activities.html", activities=items)


@app.route("/admin/gallery", methods=["GET", "POST"])
@admin_required
def admin_gallery():
    images = GalleryImage.query.order_by(GalleryImage.sort_order).all()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            files = request.files.getlist("images")
            for f in files:
                if f and f.filename:
                    result = upload_image(f, folder="newvisionacademy/gallery")
                    if result:
                        img = GalleryImage(
                            title=request.form.get("title", ""),
                            description=request.form.get("description", ""),
                            category=request.form.get("category", "School Life"),
                            image_url=result["url"],
                            image_public_id=result.get("public_id", ""),
                            sort_order=int(request.form.get("sort_order", 0) or 0),
                            is_featured="is_featured" in request.form,
                            is_active=True,
                        )
                        db.session.add(img)
            db.session.commit()
            flash("Images uploaded.", "success")
        elif action == "edit":
            img = GalleryImage.query.get(request.form.get("id"))
            if img:
                img.title = request.form.get("title", "")
                img.description = request.form.get("description", "")
                img.category = request.form.get("category", "School Life")
                img.sort_order = int(request.form.get("sort_order", 0) or 0)
                img.is_featured = "is_featured" in request.form
                img.is_active = "is_active" in request.form
                db.session.commit()
                flash("Image updated.", "success")
        elif action == "delete":
            img = GalleryImage.query.get(request.form.get("id"))
            if img:
                if img.image_public_id:
                    delete_image(img.image_public_id)
                db.session.delete(img)
                db.session.commit()
                flash("Image deleted.", "success")
        return redirect(url_for("admin_gallery"))
    return render_template("admin/gallery.html", images=images)


@app.route("/admin/news", methods=["GET", "POST"])
@admin_required
def admin_news():
    items = News.query.order_by(News.created_at.desc()).all()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            title = request.form.get("title", "")
            n = News(
                title=title,
                slug=slugify(title) + "-" + str(int(now_nepal().timestamp()) % 10000),
                content=request.form.get("content", ""),
                excerpt=request.form.get("excerpt", ""),
                category=request.form.get("category", "General"),
                author=request.form.get("author", "Admin"),
                status=request.form.get("status", "draft"),
                is_featured="is_featured" in request.form,
            )
            if n.status == "published":
                n.published_at = now_nepal()
            if "cover" in request.files and request.files["cover"].filename:
                result = upload_image(request.files["cover"], folder="newvisionacademy/news")
                if not result:
                    result = upload_file(request.files["cover"], folder="newvisionacademy/news")
                if result:
                    n.cover_image = result["url"]
                    n.cover_public_id = result.get("public_id", "")
            # Any file type attachment (PDF, video, doc, etc.)
            att = request.files.get("attachment")
            if att and att.filename:
                result = upload_file(att, folder="newvisionacademy/news")
                if result:
                    n.attachment_url = result["url"]
                    n.attachment_public_id = result.get("public_id", "")
            db.session.add(n)
            db.session.commit()
            if n.status == "published":
                link = url_for("news_detail", slug=n.slug) if getattr(n, "slug", None) else url_for("news")
                notify_subscribers("News", n.title, n.excerpt or "", link, file_url=n.attachment_url or n.cover_image or "")
            flash("News created.", "success")
        elif action == "edit":
            n = News.query.get(request.form.get("id"))
            if n:
                n.title = request.form.get("title", "")
                n.content = request.form.get("content", "")
                n.excerpt = request.form.get("excerpt", "")
                n.category = request.form.get("category", "General")
                n.author = request.form.get("author", "Admin")
                old_status = n.status
                n.status = request.form.get("status", "draft")
                n.is_featured = "is_featured" in request.form
                newly_published = n.status == "published" and old_status != "published"
                if newly_published:
                    n.published_at = now_nepal()
                if "cover" in request.files and request.files["cover"].filename:
                    result = upload_image(request.files["cover"], folder="newvisionacademy/news")
                    if not result:
                        result = upload_file(request.files["cover"], folder="newvisionacademy/news")
                    if result:
                        n.cover_image = result["url"]
                        n.cover_public_id = result.get("public_id", "")
                att = request.files.get("attachment")
                if att and att.filename:
                    result = upload_file(att, folder="newvisionacademy/news")
                    if result:
                        n.attachment_url = result["url"]
                        n.attachment_public_id = result.get("public_id", "")
                db.session.commit()
                if newly_published:
                    link = url_for("news_detail", slug=n.slug) if n.slug else url_for("news")
                    notify_subscribers("News", n.title, n.excerpt or "", link, file_url=n.attachment_url or n.cover_image or "")
                flash("News updated.", "success")
        elif action == "delete":
            n = News.query.get(request.form.get("id"))
            if n:
                db.session.delete(n)
                db.session.commit()
                flash("News deleted.", "success")
        return redirect(url_for("admin_news"))
    return render_template("admin/news.html", news_list=items)



@app.route("/admin/subscribers", methods=["GET", "POST"])
@admin_required
def admin_subscribers():
    """Manage student / parent email list for notice & news auto-mail."""
    import re
    if request.method == "POST":
        action = request.form.get("action")
        if action == "bulk_add":
            raw = request.form.get("emails", "") or ""
            # Split by newline, comma, semicolon, space
            parts = re.split(r"[\s,;]+", raw)
            added = 0
            skipped = 0
            for p in parts:
                email = (p or "").strip().lower()
                if not email or "@" not in email or "." not in email.split("@")[-1]:
                    continue
                if len(email) > 120:
                    continue
                existing = NewsletterSubscriber.query.filter_by(email=email).first()
                if existing:
                    if not existing.is_active:
                        existing.is_active = True
                        added += 1
                    else:
                        skipped += 1
                    continue
                db.session.add(NewsletterSubscriber(email=email, is_active=True))
                added += 1
            db.session.commit()
            flash(f"Saved {added} email(s). {skipped} already existed.", "success")
        elif action == "add_one":
            email = (request.form.get("email") or "").strip().lower()
            if email and "@" in email:
                existing = NewsletterSubscriber.query.filter_by(email=email).first()
                if existing:
                    existing.is_active = True
                    flash("Email already in list (activated).", "info")
                else:
                    db.session.add(NewsletterSubscriber(email=email, is_active=True))
                    flash("Email added.", "success")
                db.session.commit()
            else:
                flash("Invalid email.", "danger")
        elif action == "delete":
            s = NewsletterSubscriber.query.get(request.form.get("id"))
            if s:
                db.session.delete(s)
                db.session.commit()
                flash("Email removed.", "success")
        elif action == "toggle":
            s = NewsletterSubscriber.query.get(request.form.get("id"))
            if s:
                s.is_active = not s.is_active
                db.session.commit()
                flash("Status updated.", "success")
        elif action == "clear_all":
            NewsletterSubscriber.query.delete()
            db.session.commit()
            flash("All emails cleared.", "success")
        return redirect(url_for("admin_subscribers"))
    items = NewsletterSubscriber.query.order_by(NewsletterSubscriber.created_at.desc()).all()
    return render_template("admin/subscribers.html", subscribers=items)


@app.route("/admin/notices", methods=["GET", "POST"])
@admin_required
def admin_notices():
    items = Notice.query.order_by(Notice.published_at.desc()).all()
    ticker = NoticeTickerSetting.query.first()
    if not ticker:
        ticker = NoticeTickerSetting()
        db.session.add(ticker)
        db.session.commit()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            n = Notice(
                title=request.form.get("title", ""),
                description=request.form.get("description", ""),
                category=request.form.get("category", "General"),
                is_important="is_important" in request.form,
                external_url=request.form.get("external_url", ""),
                is_active="is_active" in request.form,
                published_at=now_nepal(),
            )
            if request.form.get("expiry_date"):
                try:
                    n.expiry_date = datetime.strptime(request.form["expiry_date"], "%Y-%m-%d")
                except ValueError:
                    pass
            # PDF / document / image upload for notice
            pdf_file = request.files.get("pdf_file")
            if pdf_file and pdf_file.filename:
                result = upload_file(pdf_file, folder="newvisionacademy/notices")
                if result:
                    n.pdf_url = result["url"]
            db.session.add(n)
            db.session.commit()
            if n.is_active:
                link = url_for("notice_detail", notice_id=n.id) if n.id else url_for("notices")
                notify_subscribers("Notice", n.title, (n.description or "")[:200], link, file_url=n.pdf_url or "")
            flash("Notice added.", "success")
        elif action == "edit":
            n = Notice.query.get(request.form.get("id"))
            if n:
                n.title = request.form.get("title", "")
                n.description = request.form.get("description", "")
                n.category = request.form.get("category", "General")
                n.is_important = "is_important" in request.form
                n.external_url = request.form.get("external_url", "")
                n.is_active = "is_active" in request.form
                db.session.commit()
                flash("Notice updated.", "success")
        elif action == "delete":
            n = Notice.query.get(request.form.get("id"))
            if n:
                db.session.delete(n)
                db.session.commit()
                flash("Notice deleted.", "success")
        elif action == "ticker":
            ticker.is_enabled = "is_enabled" in request.form
            ticker.speed = int(request.form.get("speed", 40) or 40)
            ticker.max_items = int(request.form.get("max_items", 5) or 5)
            db.session.commit()
            flash("Ticker settings updated.", "success")
        return redirect(url_for("admin_notices"))
    return render_template("admin/notices.html", notices=items, ticker=ticker)


@app.route("/admin/events", methods=["GET", "POST"])
@admin_required
def admin_events():
    items = Event.query.order_by(Event.event_date.desc()).all()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            e = Event(
                name=request.form.get("name", ""),
                description=request.form.get("description", ""),
                start_time=request.form.get("start_time", ""),
                end_time=request.form.get("end_time", ""),
                venue=request.form.get("venue", ""),
                organizer=request.form.get("organizer", ""),
                registration_url=request.form.get("registration_url", ""),
                status=request.form.get("status", "upcoming"),
                is_active="is_active" in request.form,
            )
            if request.form.get("event_date"):
                e.event_date = datetime.strptime(request.form["event_date"], "%Y-%m-%d").date()
            if "image" in request.files and request.files["image"].filename:
                result = upload_image(request.files["image"], folder="newvisionacademy/events")
                if result:
                    e.image_url = result["url"]
                    e.image_public_id = result.get("public_id", "")
            db.session.add(e)
            db.session.commit()
            if e.is_active:
                summary = e.description or ""
                if e.event_date:
                    summary = f"Date: {e.event_date}. " + summary
                notify_subscribers("Event", e.name, summary[:200], url_for("events"))
            flash("Event added.", "success")
        elif action == "edit":
            e = Event.query.get(request.form.get("id"))
            if e:
                e.name = request.form.get("name", "")
                e.description = request.form.get("description", "")
                e.start_time = request.form.get("start_time", "")
                e.end_time = request.form.get("end_time", "")
                e.venue = request.form.get("venue", "")
                e.organizer = request.form.get("organizer", "")
                e.registration_url = request.form.get("registration_url", "")
                e.status = request.form.get("status", "upcoming")
                e.is_active = "is_active" in request.form
                if request.form.get("event_date"):
                    e.event_date = datetime.strptime(request.form["event_date"], "%Y-%m-%d").date()
                if "image" in request.files and request.files["image"].filename:
                    result = upload_image(request.files["image"], folder="newvisionacademy/events")
                    if result:
                        e.image_url = result["url"]
                        e.image_public_id = result.get("public_id", "")
                db.session.commit()
                flash("Event updated.", "success")
        elif action == "delete":
            e = Event.query.get(request.form.get("id"))
            if e:
                db.session.delete(e)
                db.session.commit()
                flash("Event deleted.", "success")
        return redirect(url_for("admin_events"))
    return render_template("admin/events.html", events=items)


@app.route("/admin/admissions", methods=["GET", "POST"])
@admin_required
def admin_admissions():
    items = AdmissionApplication.query.order_by(AdmissionApplication.created_at.desc()).all()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "update_status":
            app_obj = AdmissionApplication.query.get(request.form.get("id"))
            if app_obj:
                old = app_obj.status
                app_obj.status = request.form.get("status", "New")
                app_obj.admin_notes = request.form.get("admin_notes", "")
                db.session.commit()
                # Notify parent on status change
                if app_obj.email and old != app_obj.status:
                    profile = get_profile()
                    tmpl = EmailTemplate.query.filter_by(slug="admission_status", is_active=True).first()
                    if tmpl:
                        subject = render_template_vars(
                            tmpl.subject,
                            parent_name=app_obj.parent_name,
                            student_name=app_obj.student_name,
                            application_id=app_obj.application_id,
                            school_name=profile.school_name,
                        )
                        body = render_template_vars(
                            tmpl.body,
                            parent_name=app_obj.parent_name,
                            student_name=app_obj.student_name,
                            application_id=app_obj.application_id,
                            school_name=profile.school_name,
                            school_address=profile.address,
                        )
                        body = body.replace("{{status}}", app_obj.status)
                        send_email(subject, app_obj.email, body)
                flash("Application updated.", "success")
        return redirect(url_for("admin_admissions"))
    return render_template("admin/admissions.html", applications=items)


@app.route("/admin/inquiries", methods=["GET", "POST"])
@admin_required
def admin_inquiries():
    items = ContactInquiry.query.order_by(ContactInquiry.created_at.desc()).all()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "update_status":
            inq = ContactInquiry.query.get(request.form.get("id"))
            if inq:
                inq.status = request.form.get("status", "New")
                inq.admin_notes = request.form.get("admin_notes", "")
                db.session.commit()
                flash("Inquiry updated.", "success")
        elif action == "delete":
            inq = ContactInquiry.query.get(request.form.get("id"))
            if inq:
                db.session.delete(inq)
                db.session.commit()
                flash("Inquiry deleted.", "success")
        return redirect(url_for("admin_inquiries"))
    return render_template("admin/inquiries.html", inquiries=items)


@app.route("/admin/downloads", methods=["GET", "POST"])
@admin_required
def admin_downloads():
    items = Download.query.order_by(Download.sort_order).all()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            d = Download(
                title=request.form.get("title", ""),
                description=request.form.get("description", ""),
                file_url=request.form.get("file_url", ""),
                category=request.form.get("category", "General"),
                sort_order=int(request.form.get("sort_order", 0) or 0),
                is_active="is_active" in request.form,
            )
            db.session.add(d)
            db.session.commit()
            flash("Download added.", "success")
        elif action == "delete":
            d = Download.query.get(request.form.get("id"))
            if d:
                db.session.delete(d)
                db.session.commit()
                flash("Download deleted.", "success")
        return redirect(url_for("admin_downloads"))
    return render_template("admin/downloads.html", downloads=items)


@app.route("/admin/faq", methods=["GET", "POST"])
@admin_required
def admin_faq():
    items = FAQ.query.order_by(FAQ.sort_order).all()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            f = FAQ(
                question=request.form.get("question", ""),
                answer=request.form.get("answer", ""),
                sort_order=int(request.form.get("sort_order", 0) or 0),
                is_active="is_active" in request.form,
            )
            db.session.add(f)
            db.session.commit()
            flash("FAQ added.", "success")
        elif action == "edit":
            f = FAQ.query.get(request.form.get("id"))
            if f:
                f.question = request.form.get("question", "")
                f.answer = request.form.get("answer", "")
                f.sort_order = int(request.form.get("sort_order", 0) or 0)
                f.is_active = "is_active" in request.form
                db.session.commit()
                flash("FAQ updated.", "success")
        elif action == "delete":
            f = FAQ.query.get(request.form.get("id"))
            if f:
                db.session.delete(f)
                db.session.commit()
                flash("FAQ deleted.", "success")
        return redirect(url_for("admin_faq"))
    return render_template("admin/faq.html", faqs=items)


@app.route("/admin/pages", methods=["GET", "POST"])
@admin_required
def admin_pages():
    seo_items = SEOSetting.query.all()
    if request.method == "POST":
        page_key = request.form.get("page_key")
        seo = SEOSetting.query.filter_by(page_key=page_key).first()
        if not seo:
            seo = SEOSetting(page_key=page_key)
            db.session.add(seo)
        seo.title = request.form.get("title", "")
        seo.meta_description = request.form.get("meta_description", "")
        seo.og_title = request.form.get("og_title", "")
        seo.og_description = request.form.get("og_description", "")
        seo.og_image = request.form.get("og_image", "")
        seo.canonical_url = request.form.get("canonical_url", "")
        db.session.commit()
        flash("SEO settings updated.", "success")
        return redirect(url_for("admin_pages"))
    return render_template("admin/pages.html", seo_items=seo_items)


@app.route("/admin/users", methods=["GET", "POST"])
@admin_required
def admin_users():
    users = AdminUser.query.all()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            email = request.form.get("email", "").strip().lower()
            if AdminUser.query.filter_by(email=email).first():
                flash("Email already exists.", "danger")
            else:
                u = AdminUser(
                    email=email,
                    name=request.form.get("name", "Admin"),
                    role=request.form.get("role", "admin"),
                )
                u.set_password(request.form.get("password", "changeme"))
                db.session.add(u)
                db.session.commit()
                flash("User added.", "success")
        elif action == "delete":
            u = AdminUser.query.get(request.form.get("id"))
            if u and u.id != session.get("admin_id"):
                db.session.delete(u)
                db.session.commit()
                flash("User deleted.", "success")
        return redirect(url_for("admin_users"))
    return render_template("admin/users.html", users=users)


@app.route("/admin/email_settings", methods=["GET", "POST"])
@admin_required
def admin_email_settings():
    templates = EmailTemplate.query.all()
    profile = get_profile()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "template":
            tmpl = EmailTemplate.query.get(request.form.get("id"))
            if tmpl:
                tmpl.subject = request.form.get("subject", "")
                tmpl.body = request.form.get("body", "")
                tmpl.is_active = "is_active" in request.form
                db.session.commit()
                flash("Template updated.", "success")
        elif action == "response_time":
            profile.response_time = request.form.get("response_time", "30 minutes")
            profile.custom_response_time = request.form.get("custom_response_time", "")
            profile.auto_reply_enabled = "auto_reply_enabled" in request.form
            db.session.commit()
            flash("Communication settings updated.", "success")
        return redirect(url_for("admin_email_settings"))
    return render_template("admin/email_settings.html", templates=templates, profile=profile)


# ---------------------------------------------------------------------------
# Bootstrap / Seed
# ---------------------------------------------------------------------------

def seed_database():
    """Create tables and seed default data on first run."""
    db.create_all()

    # Lightweight migrations for new columns (Postgres / SQLite)
    try:
        from sqlalchemy import text, inspect
        insp = inspect(db.engine)
        if "contact_inquiry" in insp.get_table_names():
            cols = [c["name"] for c in insp.get_columns("contact_inquiry")]
            if "document_url" not in cols:
                db.session.execute(text("ALTER TABLE contact_inquiry ADD COLUMN document_url VARCHAR(500) DEFAULT ''"))
                db.session.commit()
    except Exception as e:
        app.logger.warning(f"Schema migrate skip: {e}")
        try:
            db.session.rollback()
        except Exception:
            pass

    # Admin user
    admin_email = app.config.get("ADMIN_EMAIL") or "admin@newvisionacademy.com.np"
    admin_pass = app.config.get("ADMIN_PASSWORD")
    if not AdminUser.query.filter_by(email=admin_email).first():
        if not admin_pass:
            admin_pass = "Admin@NVA2083"  # temporary; change via env in production
        user = AdminUser(email=admin_email, name="Administrator")
        user.set_password(admin_pass)
        db.session.add(user)
        app.logger.info(f"Default admin created: {admin_email}")

    # School profile
    if not SchoolProfile.query.first():
        profile = SchoolProfile(
            school_name="New Vision Academy",
            short_name="NVA",
            address="Urlabari-8, Morang, Koshi Province, Nepal",
            phone="+977 9841333476",
            email="info@newvisionacademy.edu.np",
            website="https://newvisionacademy.com.np",
            description=(
                "New Vision Academy is a private, co-educational day school located in "
                "Urlabari-8, Morang, Koshi Province, Nepal. The school provides education "
                "from Early Childhood Development (ECD/Nursery) through Grade 10, with a "
                "focus on creating a supportive and engaging learning environment for students.\n\n"
                "The school aims to provide students with a strong educational foundation while "
                "encouraging academic development, discipline, creativity, confidence and "
                "responsible participation in the community.\n\n"
                "With its focus on school-level education from early childhood through the "
                "secondary level, New Vision Academy provides students with opportunities to "
                "develop knowledge, skills and positive values throughout their academic journey."
            ),
            motto="Building Knowledge. Character. Confidence.",
            vision=(
                "To create a supportive and inspiring learning environment where every student "
                "can develop knowledge, confidence, creativity, discipline and the skills needed "
                "to become a responsible and capable member of society."
            ),
            mission=(
                "Our mission is to provide quality school education in a safe, supportive and "
                "engaging environment where students are encouraged to learn, explore, participate "
                "and grow.\n\n"
                "We aim to:\n"
                "• Build strong academic foundations.\n"
                "• Encourage curiosity and creativity.\n"
                "• Develop discipline, confidence and responsibility.\n"
                "• Support students' personal and social development.\n"
                "• Encourage positive relationships among students, teachers and parents.\n"
                "• Prepare students for their future academic and personal journey."
            ),
            core_values=(
                "Integrity — We encourage students to be honest, responsible and trustworthy.\n"
                "Respect — We promote respect for teachers, parents, classmates and the wider community.\n"
                "Discipline — We encourage positive habits, responsibility and self-discipline.\n"
                "Learning — We believe in continuous learning, curiosity and personal growth.\n"
                "Creativity — We encourage students to think, explore, create and express themselves.\n"
                "Responsibility — We help students understand their responsibilities towards themselves, their school and society.\n"
                "Teamwork — We encourage cooperation, communication and learning together.\n"
                "Confidence — We support students in developing confidence and believing in their abilities.\n"
                "Kindness — We foster care and empathy within the school community.\n"
                "Excellence — We encourage students to strive for their best in learning and conduct."
            ),
            why_choose_us=(
                "New Vision Academy offers education from ECD/Nursery to Grade 10 in a "
                "co-educational day school environment at Urlabari-8, Morang. Students receive "
                "support focused on academic foundations, character development and positive "
                "participation in school life."
            ),
            history=(
                "New Vision Academy is a private educational institution situated in Urlabari-8, "
                "Morang, Koshi Province, Nepal. The school serves students from Early Childhood "
                "Development (ECD/Nursery) through Grade 10.\n\n"
                "As a co-educational day school, New Vision Academy provides an environment where "
                "students can learn, grow and participate in a range of academic and school-based "
                "activities. The school seeks to support students throughout their educational "
                "journey by developing knowledge, confidence, discipline, creativity and positive values.\n\n"
                "The school community includes students, teachers, staff and parents working together "
                "to create a positive learning environment."
            ),
            student_count="228",
            teacher_count="29",
            grades_text="ECD/Nursery – Grade 10",
            admission_session="2083 B.S.",
            school_type="Private, Co-Educational Day School",
            school_code="050640033",
            municipality="Urlabari Municipality",
            district="Morang",
            province="Koshi Province",
            country="Nepal",
            admission_open=True,
            office_hours="Sunday – Friday, 9:00 AM – 4:00 PM",
            response_time="30 minutes",
            auto_reply_enabled=True,
            copyright_text="© {{year}} New Vision Academy. All rights reserved.",
        )
        db.session.add(profile)

    # Navigation
    if not NavigationItem.query.first():
        navs = [
            ("Home", "/", 1),
            ("About Us", "/about", 2),
            ("Academics", "/academics", 3),
            ("Teachers", "/teachers", 4),
            ("Facilities", "/facilities", 5),
            ("Activities", "/activities", 6),
            ("Gallery", "/gallery", 7),
            ("News", "/news", 8),
            ("Notice Board", "/notices", 9),
            ("Events", "/events", 10),
            ("Contact", "/contact", 11),
        ]
        for title, url, order in navs:
            db.session.add(NavigationItem(title=title, url=url, sort_order=order, is_active=True))
        db.session.add(NavigationItem(title="Admission Open", url="/admission", sort_order=99, is_active=True, is_cta=True))

    # Hero slides
    if not HeroSlide.query.first():
        slides = [
            {
                "title": "NEW VISION ACADEMY",
                "subtitle": "Building Knowledge. Character. Confidence.",
                "description": "A caring English-medium learning environment for students from ECD/Nursery to Grade 10.",
                "button1_text": "Explore Our School",
                "button1_url": "/about",
                "button2_text": "Admission Open",
                "button2_url": "/admission",
                "sort_order": 1,
            },
            {
                "title": "ADMISSION OPEN — 2083 B.S.",
                "subtitle": "Give Your Child a Strong Foundation for the Future.",
                "description": "Enrol your child at New Vision Academy for the upcoming academic session.",
                "button1_text": "Apply Now",
                "button1_url": "/admission",
                "button2_text": "",
                "button2_url": "",
                "sort_order": 2,
            },
            {
                "title": "LEARNING BEYOND THE CLASSROOM",
                "subtitle": "Academic excellence, creativity, discipline, sports and practical learning.",
                "description": "Discover a balanced approach to education that nurtures every child.",
                "button1_text": "Discover More",
                "button1_url": "/activities",
                "button2_text": "",
                "button2_url": "",
                "sort_order": 3,
            },
        ]
        for s in slides:
            db.session.add(HeroSlide(**s, is_active=True))

    # Grades
    if not Grade.query.first():
        grade_data = [
            ("ECD / Nursery", "A nurturing beginning to a child's educational journey, focusing on foundational learning, social development and school readiness."),
            ("Grade 1", "Primary level — building core academic skills, communication, creativity and positive learning habits."),
            ("Grade 2", "Primary level — building core academic skills, communication, creativity and positive learning habits."),
            ("Grade 3", "Primary level — building core academic skills, communication, creativity and positive learning habits."),
            ("Grade 4", "Primary level — building core academic skills, communication, creativity and positive learning habits."),
            ("Grade 5", "Primary level — building core academic skills, communication, creativity and positive learning habits."),
            ("Grade 6", "Basic level — strengthening academic knowledge, independent learning skills and participation in school activities."),
            ("Grade 7", "Basic level — strengthening academic knowledge, independent learning skills and participation in school activities."),
            ("Grade 8", "Basic level — strengthening academic knowledge, independent learning skills and participation in school activities."),
            ("Grade 9", "Secondary level — preparing students for secondary-level academic learning and the Grade 10 / SEE pathway."),
            ("Grade 10", "Secondary level — preparing students for secondary-level academic learning and the Grade 10 / SEE pathway."),
        ]
        for i, (name, desc) in enumerate(grade_data):
            db.session.add(Grade(name=name, sort_order=i + 1, is_active=True, description=desc))

    # Facilities
    if not Facility.query.first():
        # Placeholder facilities — school admin should confirm and update actual facilities
        facs = [
            ("Classrooms", "fa-chalkboard", "Learning spaces for students from ECD through Grade 10. Details to be confirmed by the school."),
            ("Library", "fa-book", "Reading and study resources. Details to be confirmed by the school."),
            ("Computer / ICT", "fa-laptop", "Digital learning support. Details to be confirmed by the school."),
            ("Science Learning", "fa-flask", "Science-related learning activities. Details to be confirmed by the school."),
            ("Sports & Playground", "fa-futbol", "Physical education and outdoor activities. Details to be confirmed by the school."),
            ("Safe Environment", "fa-shield-alt", "A secure and caring campus for students."),
            ("Drinking Water", "fa-tint", "Clean drinking water facilities."),
            ("Child-Friendly Environment", "fa-child", "Supportive atmosphere for young learners."),
        ]
        for i, (title, icon, desc) in enumerate(facs):
            db.session.add(Facility(title=title, icon=icon, description=desc, sort_order=i + 1, is_active=True))

    # Homepage sections
    if not HomepageSection.query.first():
        secs = [
            ("hero", "Hero Slider", 1),
            ("stats", "Statistics Bar", 2),
            ("about", "About School", 3),
            ("principal", "Principal Message", 4),
            ("why_choose", "Why Choose Us", 5),
            ("academics", "Academic Programs", 6),
            ("facilities", "Facilities", 7),
            ("activities", "Activities", 8),
            ("teachers", "Featured Teachers", 9),
            ("news", "Latest News", 10),
            ("notices", "Notice Board", 11),
            ("events", "Upcoming Events", 12),
            ("gallery", "Gallery", 13),
            ("admission_cta", "Admission CTA", 14),
            ("contact_map", "Contact / Map", 15),
        ]
        for key, title, order in secs:
            db.session.add(HomepageSection(section_key=key, title=title, sort_order=order, is_enabled=True))

    # Email templates
    if not EmailTemplate.query.first():
        templates = [
            (
                "admission_received",
                "Admission Received",
                "Admission Inquiry Received – {{school_name}}",
                """<p>Dear {{parent_name}},</p>
<p>Thank you for submitting an admission inquiry/application to {{school_name}}.</p>
<p>We have received the information successfully. Application ID: <strong>{{application_id}}</strong></p>
<p>Our school administration will review your submission and contact you within {{response_time}}.</p>
<p>{{school_name}}<br>{{school_address}}</p>""",
            ),
            (
                "contact_received",
                "Contact Received",
                "We received your message – {{school_name}}",
                """<p>Dear {{customer_name}},</p>
<p>Thank you for contacting {{school_name}}. We have received your message and will respond within {{response_time}}.</p>
<p>{{school_name}}<br>{{school_address}}</p>""",
            ),
            (
                "admission_status",
                "Admission Status Updated",
                "Admission Application Update – {{school_name}}",
                """<p>Dear {{parent_name}},</p>
<p>Your admission application ({{application_id}}) for {{student_name}} has been updated.</p>
<p>Current status: <strong>{{status}}</strong></p>
<p>Please contact the school office if you have any questions.</p>
<p>{{school_name}}<br>{{school_address}}</p>""",
            ),
            (
                "event_notification",
                "Event Notification",
                "Upcoming Event – {{school_name}}",
                """<p>Dear Parent/Guardian,</p>
<p>You are invited to an upcoming event at {{school_name}}.</p>
<p>Please check the school website or notice board for details.</p>
<p>{{school_name}}</p>""",
            ),
            (
                "notice_notification",
                "Notice Notification",
                "Important Notice – {{school_name}}",
                """<p>Dear Parent/Guardian,</p>
<p>A new notice has been published by {{school_name}}.</p>
<p>Please visit the Notice Board on our website for full details.</p>
<p>{{school_name}}</p>""",
            ),
            (
                "general_reply",
                "General Inquiry Reply",
                "Re: Your inquiry – {{school_name}}",
                """<p>Dear {{customer_name}},</p>
<p>Thank you for contacting {{school_name}}.</p>
<p>{{school_name}}<br>{{school_address}}</p>""",
            ),
        ]
        for slug, name, subject, body in templates:
            db.session.add(EmailTemplate(slug=slug, name=name, subject=subject, body=body, is_active=True))

    # Notice ticker
    if not NoticeTickerSetting.query.first():
        db.session.add(NoticeTickerSetting(is_enabled=True, speed=40, max_items=5))

    # Principal / Coordinator placeholders
    if not PrincipalMessage.query.first():
        db.session.add(PrincipalMessage(
            name="Ajit Kr. Bhattarai",
            designation="Principal",
            photo_url="/static/images/staff/ajit-kr-bhattarai.jpg",
            short_message="Welcome to New Vision Academy. We are committed to providing a supportive and engaging learning environment for every student from ECD through Grade 10.",
            full_message="Welcome to New Vision Academy.\n\nWe are committed to providing a supportive and engaging learning environment for every student from ECD through Grade 10. Our focus is on building strong academic foundations while encouraging discipline, creativity, confidence and positive values.\n\nTogether with our teachers, staff and parents, we work to help each child grow and succeed. Thank you for trusting us with your child's education.\n\nAjit Kr. Bhattarai\nPrincipal",
            is_active=True,
        ))
    if not CoordinatorMessage.query.first():
        db.session.add(CoordinatorMessage(
            name="Mrs. Dirpa Bhattarai",
            designation="Vice Principal",
            photo_url="/static/images/staff/dirpa-bhattarai.jpg",
            message="At New Vision Academy, we work together to support every student's academic and personal growth. Our team is dedicated to creating a positive and caring learning environment for children from ECD to Grade 10.",
            is_active=True,
        ))

    # Seed real staff list (replace empty DB or old placeholders)
    _placeholder_count = Teacher.query.filter(Teacher.full_name.like("Teacher %")).count()
    if Teacher.query.count() == 0 or (_placeholder_count > 0 and Teacher.query.count() == _placeholder_count):
        Teacher.query.delete()
        db.session.add(Teacher(
            full_name="Ajit Kr. Bhattarai",
            position="Principal",
            department="Administration",
            photo_url="/static/images/staff/ajit-kr-bhattarai.jpg",
            short_bio="",
            sort_order=1,
            is_featured=True,
            is_active=True,
        ))
        db.session.add(Teacher(
            full_name="Mrs. Dirpa Bhattarai",
            position="Vice Principal",
            department="Administration",
            photo_url="/static/images/staff/dirpa-bhattarai.jpg",
            short_bio="",
            sort_order=2,
            is_featured=True,
            is_active=True,
        ))
        db.session.add(Teacher(
            full_name="Asha Dhimal",
            position="Teacher",
            department="Teaching",
            photo_url="/static/images/staff/asha-dhimal.jpg",
            short_bio="",
            sort_order=3,
            is_featured=True,
            is_active=True,
        ))
        db.session.add(Teacher(
            full_name="Dikshya Dhimal",
            position="Teacher",
            department="Teaching",
            photo_url="/static/images/staff/dikshya-dhimal.jpg",
            short_bio="",
            sort_order=4,
            is_featured=True,
            is_active=True,
        ))
        db.session.add(Teacher(
            full_name="Dipa Dhimal",
            position="Teacher",
            department="Teaching",
            photo_url="/static/images/staff/dipa-dhimal.jpg",
            short_bio="",
            sort_order=5,
            is_featured=False,
            is_active=True,
        ))
        db.session.add(Teacher(
            full_name="Durga Yakha",
            position="Teacher",
            department="Teaching",
            photo_url="/static/images/staff/durga-yakha.jpg",
            short_bio="",
            sort_order=6,
            is_featured=False,
            is_active=True,
        ))
        db.session.add(Teacher(
            full_name="Gita Shrestha",
            position="Teacher",
            department="Teaching",
            photo_url="/static/images/staff/gita-shrestha.jpg",
            short_bio="",
            sort_order=7,
            is_featured=False,
            is_active=True,
        ))
        db.session.add(Teacher(
            full_name="Hemsagar Pokhrel",
            position="Teacher",
            department="Teaching",
            photo_url="/static/images/staff/hemsagar-pokhrel.jpg",
            short_bio="",
            sort_order=8,
            is_featured=False,
            is_active=True,
        ))
        db.session.add(Teacher(
            full_name="Januka Darnal",
            position="Teacher",
            department="Teaching",
            photo_url="/static/images/staff/januka-darnal.jpg",
            short_bio="",
            sort_order=9,
            is_featured=False,
            is_active=True,
        ))
        db.session.add(Teacher(
            full_name="Jisha Banya",
            position="Teacher",
            department="Teaching",
            photo_url="/static/images/staff/jisha-banya.jpg",
            short_bio="",
            sort_order=10,
            is_featured=False,
            is_active=True,
        ))
        db.session.add(Teacher(
            full_name="Kamalraj Gautam",
            position="Teacher",
            department="Teaching",
            photo_url="/static/images/staff/kamalraj-gautam.jpg",
            short_bio="",
            sort_order=11,
            is_featured=False,
            is_active=True,
        ))
        db.session.add(Teacher(
            full_name="Kausila Shrestha",
            position="Teacher",
            department="Teaching",
            photo_url="/static/images/staff/kausila-shrestha.jpg",
            short_bio="",
            sort_order=12,
            is_featured=False,
            is_active=True,
        ))
        db.session.add(Teacher(
            full_name="Lokendra Bhandari",
            position="Teacher",
            department="Teaching",
            photo_url="/static/images/staff/lokendra-bhandari.jpg",
            short_bio="",
            sort_order=13,
            is_featured=False,
            is_active=True,
        ))
        db.session.add(Teacher(
            full_name="Manita Bhujel",
            position="Teacher",
            department="Teaching",
            photo_url="/static/images/staff/manita-bhujel.jpg",
            short_bio="",
            sort_order=14,
            is_featured=False,
            is_active=True,
        ))
        db.session.add(Teacher(
            full_name="Manu Rahut",
            position="Teacher",
            department="Teaching",
            photo_url="/static/images/staff/manu-rahut.jpg",
            short_bio="",
            sort_order=15,
            is_featured=False,
            is_active=True,
        ))
        db.session.add(Teacher(
            full_name="Milan Khadka",
            position="Teacher",
            department="Teaching",
            photo_url="/static/images/staff/milan-khadka.jpg",
            short_bio="",
            sort_order=16,
            is_featured=False,
            is_active=True,
        ))
        db.session.add(Teacher(
            full_name="Muskan Chaudhary",
            position="Teacher",
            department="Teaching",
            photo_url="/static/images/staff/muskan-chaudhary.jpg",
            short_bio="",
            sort_order=17,
            is_featured=False,
            is_active=True,
        ))
        db.session.add(Teacher(
            full_name="Narayan Shrestha",
            position="Teacher",
            department="Teaching",
            photo_url="/static/images/staff/narayan-shrestha.jpg",
            short_bio="",
            sort_order=18,
            is_featured=False,
            is_active=True,
        ))
        db.session.add(Teacher(
            full_name="Neelam Rijal",
            position="Teacher",
            department="Teaching",
            photo_url="/static/images/staff/neelam-rijal.jpg",
            short_bio="",
            sort_order=19,
            is_featured=False,
            is_active=True,
        ))
        db.session.add(Teacher(
            full_name="Ram Kr. Shrestha",
            position="Teacher",
            department="Teaching",
            photo_url="/static/images/staff/ram-kr-shrestha.jpg",
            short_bio="",
            sort_order=20,
            is_featured=False,
            is_active=True,
        ))
        db.session.add(Teacher(
            full_name="Rita Timsina",
            position="Teacher",
            department="Teaching",
            photo_url="/static/images/staff/rita-timsina.jpg",
            short_bio="",
            sort_order=21,
            is_featured=False,
            is_active=True,
        ))
        db.session.add(Teacher(
            full_name="Sanjog Subedi",
            position="Teacher",
            department="Teaching",
            photo_url="/static/images/staff/sanjog-subedi.jpg",
            short_bio="",
            sort_order=22,
            is_featured=False,
            is_active=True,
        ))
        db.session.add(Teacher(
            full_name="Sarita Dhimal",
            position="Teacher",
            department="Teaching",
            photo_url="/static/images/staff/sarita-dhimal.jpg",
            short_bio="",
            sort_order=23,
            is_featured=False,
            is_active=True,
        ))
        db.session.add(Teacher(
            full_name="Saroop Sigdel",
            position="Teacher",
            department="Teaching",
            photo_url="/static/images/staff/saroop-sigdel.jpg",
            short_bio="",
            sort_order=24,
            is_featured=False,
            is_active=True,
        ))
        db.session.add(Teacher(
            full_name="Shiv Pd. Bhattarai",
            position="Teacher",
            department="Teaching",
            photo_url="/static/images/staff/shiv-pd-bhattarai.jpg",
            short_bio="",
            sort_order=25,
            is_featured=False,
            is_active=True,
        ))
        db.session.add(Teacher(
            full_name="Sita Gautam",
            position="Teacher",
            department="Teaching",
            photo_url="/static/images/staff/sita-gautam.jpg",
            short_bio="",
            sort_order=26,
            is_featured=False,
            is_active=True,
        ))
        db.session.add(Teacher(
            full_name="Sunila Bhandari",
            position="Teacher",
            department="Teaching",
            photo_url="/static/images/staff/sunila-bhandari.jpg",
            short_bio="",
            sort_order=27,
            is_featured=False,
            is_active=True,
        ))
        db.session.add(Teacher(
            full_name="Tulasha Dhamala",
            position="Teacher",
            department="Teaching",
            photo_url="/static/images/staff/tulasha-dhamala.jpg",
            short_bio="",
            sort_order=28,
            is_featured=False,
            is_active=True,
        ))
        db.session.add(Teacher(
            full_name="Lav Kumar Shrestha",
            position="Driver / Staff",
            department="Support Staff",
            photo_url="/static/images/staff/lav-kumar-stha-driver.jpg",
            short_bio="",
            sort_order=29,
            is_featured=False,
            is_active=True,
        ))

    # Sample FAQs
    if not FAQ.query.first():
        faqs = [
            ("What grades does the school offer?", "New Vision Academy offers education from ECD/Nursery through Grade 10."),
            ("Is the school co-educational?", "Yes, New Vision Academy is a co-educational day school."),
            ("How can I apply for admission?", "You can submit an online admission form on our website or visit the school office during office hours."),
            ("What is the current admission session?", "The current admission session is 2083 B.S."),
        ]
        for i, (q, a) in enumerate(faqs):
            db.session.add(FAQ(question=q, answer=a, sort_order=i + 1, is_active=True))


    # Sync staff photos for existing records missing photos
    photo_map = {
        "Ajit Kr. Bhattarai": "/static/images/staff/ajit-kr-bhattarai.jpg",
        "Mrs. Dirpa Bhattarai": "/static/images/staff/dirpa-bhattarai.jpg",
        "Asha Dhimal": "/static/images/staff/asha-dhimal.jpg",
        "Dikshya Dhimal": "/static/images/staff/dikshya-dhimal.jpg",
        "Dipa Dhimal": "/static/images/staff/dipa-dhimal.jpg",
        "Durga Yakha": "/static/images/staff/durga-yakha.jpg",
        "Gita Shrestha": "/static/images/staff/gita-shrestha.jpg",
        "Hemsagar Pokhrel": "/static/images/staff/hemsagar-pokhrel.jpg",
        "Januka Darnal": "/static/images/staff/januka-darnal.jpg",
        "Jisha Banya": "/static/images/staff/jisha-banya.jpg",
        "Kamalraj Gautam": "/static/images/staff/kamalraj-gautam.jpg",
        "Kausila Shrestha": "/static/images/staff/kausila-shrestha.jpg",
        "Lokendra Bhandari": "/static/images/staff/lokendra-bhandari.jpg",
        "Manita Bhujel": "/static/images/staff/manita-bhujel.jpg",
        "Manu Rahut": "/static/images/staff/manu-rahut.jpg",
        "Milan Khadka": "/static/images/staff/milan-khadka.jpg",
        "Muskan Chaudhary": "/static/images/staff/muskan-chaudhary.jpg",
        "Narayan Shrestha": "/static/images/staff/narayan-shrestha.jpg",
        "Neelam Rijal": "/static/images/staff/neelam-rijal.jpg",
        "Ram Kr. Shrestha": "/static/images/staff/ram-kr-shrestha.jpg",
        "Rita Timsina": "/static/images/staff/rita-timsina.jpg",
        "Sanjog Subedi": "/static/images/staff/sanjog-subedi.jpg",
        "Sarita Dhimal": "/static/images/staff/sarita-dhimal.jpg",
        "Saroop Sigdel": "/static/images/staff/saroop-sigdel.jpg",
        "Shiv Pd. Bhattarai": "/static/images/staff/shiv-pd-bhattarai.jpg",
        "Sita Gautam": "/static/images/staff/sita-gautam.jpg",
        "Sunila Bhandari": "/static/images/staff/sunila-bhandari.jpg",
        "Tulasha Dhamala": "/static/images/staff/tulasha-dhamala.jpg",
        "Lav Kumar Shrestha": "/static/images/staff/lav-kumar-stha-driver.jpg",
    }
    for t in Teacher.query.all():
        if (not t.photo_url) and t.full_name in photo_map:
            t.photo_url = photo_map[t.full_name]
    # Principal photo sync
    prin = PrincipalMessage.query.first()
    if prin and not prin.photo_url:
        prin.name = prin.name or "Ajit Kr. Bhattarai"
        prin.photo_url = "/static/images/staff/ajit-kr-bhattarai.jpg"
        prin.designation = prin.designation or "Principal"
    coord = CoordinatorMessage.query.first()
    if coord and not coord.photo_url:
        coord.name = coord.name or "Mrs. Dirpa Bhattarai"
        coord.photo_url = "/static/images/staff/dirpa-bhattarai.jpg"
        coord.designation = "Vice Principal"


    db.session.commit()


# ---------------------------------------------------------------------------
# App init
# ---------------------------------------------------------------------------


def ensure_schema():
    """Add any missing columns for existing databases."""
    from sqlalchemy import text as sql_text, inspect
    try:
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        alters = []

        if "school_profile" in tables:
            cols = {c["name"] for c in inspector.get_columns("school_profile")}
            if "about_image_url" not in cols:
                alters.append("ALTER TABLE school_profile ADD COLUMN about_image_url VARCHAR(500) DEFAULT ''")
            if "about_image_public_id" not in cols:
                alters.append("ALTER TABLE school_profile ADD COLUMN about_image_public_id VARCHAR(300) DEFAULT ''")
            if "school_code" not in cols:
                alters.append("ALTER TABLE school_profile ADD COLUMN school_code VARCHAR(50) DEFAULT '050640033'")
            if "municipality" not in cols:
                alters.append("ALTER TABLE school_profile ADD COLUMN municipality VARCHAR(100) DEFAULT 'Urlabari Municipality'")
            if "district" not in cols:
                alters.append("ALTER TABLE school_profile ADD COLUMN district VARCHAR(100) DEFAULT 'Morang'")
            if "province" not in cols:
                alters.append("ALTER TABLE school_profile ADD COLUMN province VARCHAR(100) DEFAULT 'Koshi Province'")
            if "country" not in cols:
                alters.append("ALTER TABLE school_profile ADD COLUMN country VARCHAR(50) DEFAULT 'Nepal'")

        # News attachment support
        if "news" in tables:
            cols = {c["name"] for c in inspector.get_columns("news")}
            if "attachment_url" not in cols:
                alters.append("ALTER TABLE news ADD COLUMN attachment_url VARCHAR(500) DEFAULT ''")
            if "attachment_public_id" not in cols:
                alters.append("ALTER TABLE news ADD COLUMN attachment_public_id VARCHAR(300) DEFAULT ''")

        for stmt in alters:
            db.session.execute(sql_text(stmt))
        if alters:
            db.session.commit()
            app.logger.info("Schema migration applied: %s columns" % len(alters))
    except Exception as e:
        app.logger.warning("Schema ensure skipped: %s" % e)


with app.app_context():
    init_cloudinary(app)
    db.create_all()
    ensure_schema()
    seed_database()


# CSRF-like simple token helper (basic protection)
@app.before_request
def basic_security():
    if request.method == "POST" and request.path.startswith("/admin"):
        if not session.get("admin_id") and request.endpoint != "admin_login":
            abort(403)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
