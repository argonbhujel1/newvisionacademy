import os
import cloudinary
import cloudinary.uploader
import cloudinary.api
from flask import current_app


def init_cloudinary(app):
    """Configure Cloudinary from app config / environment."""
    cloud_name = (
        app.config.get("CLOUDINARY_CLOUD_NAME")
        or os.environ.get("CLOUDINARY_CLOUD_NAME")
        or "rznbwjix"
    )
    api_key = (
        app.config.get("CLOUDINARY_API_KEY")
        or os.environ.get("CLOUDINARY_API_KEY")
        or ""
    )
    api_secret = (
        app.config.get("CLOUDINARY_API_SECRET")
        or os.environ.get("CLOUDINARY_API_SECRET")
        or ""
    )
    cloudinary_url = app.config.get("CLOUDINARY_URL") or os.environ.get("CLOUDINARY_URL")

    if cloudinary_url:
        cloudinary.config(cloudinary_url=cloudinary_url)
    else:
        cloudinary.config(
            cloud_name=cloud_name,
            api_key=api_key,
            api_secret=api_secret,
            secure=True,
        )

    app.logger.info(
        "Cloudinary configured: cloud_name=%s, has_key=%s, has_secret=%s",
        cloud_name,
        bool(api_key),
        bool(api_secret),
    )


def _get_file_payload(file):
    """Normalize Werkzeug FileStorage / stream / path for Cloudinary."""
    if file is None:
        return None
    # Already a path or bytes
    if isinstance(file, (str, bytes)):
        return file
    # Werkzeug FileStorage
    if hasattr(file, "read"):
        # Prefer the stream; reset pointer if possible
        stream = getattr(file, "stream", file)
        try:
            if hasattr(stream, "seek"):
                stream.seek(0)
        except Exception:
            pass
        return stream
    return file


def upload_image(file, folder="newvisionacademy", public_id=None, transformation=None):
    """
    Upload an image to Cloudinary.
    Returns dict {url, public_id, width, height, format} or None on failure.
    """
    if not file:
        return None

    # Skip empty filename
    filename = getattr(file, "filename", None)
    if filename is not None and not str(filename).strip():
        return None

    payload = _get_file_payload(file)
    if payload is None:
        return None

    try:
        options = {
            "folder": folder,
            "resource_type": "image",
            "overwrite": True,
            "invalidate": True,
        }
        if public_id:
            options["public_id"] = public_id
        if transformation:
            options["transformation"] = transformation

        result = cloudinary.uploader.upload(payload, **options)
        url = result.get("secure_url") or result.get("url")
        if not url:
            current_app.logger.error("Cloudinary returned no URL: %s", result)
            return None
        return {
            "url": url,
            "public_id": result.get("public_id", ""),
            "width": result.get("width"),
            "height": result.get("height"),
            "format": result.get("format"),
        }
    except Exception as e:
        current_app.logger.error("Cloudinary upload error: %s", e, exc_info=True)
        return None


def delete_image(public_id):
    """Delete an image from Cloudinary by public_id."""
    if not public_id:
        return False
    try:
        result = cloudinary.uploader.destroy(public_id)
        return result.get("result") == "ok"
    except Exception as e:
        current_app.logger.error("Cloudinary delete error: %s", e)
        return False


def optimize_url(url, width=None, height=None, crop="fill", quality="auto"):
    """Return an optimized Cloudinary URL if possible."""
    if not url or "cloudinary.com" not in url:
        return url
    return url
