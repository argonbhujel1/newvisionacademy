import os
import cloudinary
import cloudinary.uploader
import cloudinary.api
from flask import current_app


def init_cloudinary(app):
    """Configure Cloudinary from app config."""
    cloud_name = app.config.get("CLOUDINARY_CLOUD_NAME") or "rznbwjix"
    api_key = app.config.get("CLOUDINARY_API_KEY") or ""
    api_secret = app.config.get("CLOUDINARY_API_SECRET") or ""

    if app.config.get("CLOUDINARY_URL"):
        cloudinary.config(cloudinary_url=app.config["CLOUDINARY_URL"])
    else:
        cloudinary.config(
            cloud_name=cloud_name,
            api_key=api_key,
            api_secret=api_secret,
            secure=True,
        )


def upload_image(file, folder="newvisionacademy", public_id=None, transformation=None):
    """
    Upload an image file to Cloudinary.
    Returns dict with url, public_id, etc. or None on failure.
    """
    if not file:
        return None
    try:
        options = {
            "folder": folder,
            "resource_type": "image",
            "overwrite": True,
        }
        if public_id:
            options["public_id"] = public_id
        if transformation:
            options["transformation"] = transformation

        result = cloudinary.uploader.upload(file, **options)
        return {
            "url": result.get("secure_url"),
            "public_id": result.get("public_id"),
            "width": result.get("width"),
            "height": result.get("height"),
            "format": result.get("format"),
        }
    except Exception as e:
        current_app.logger.error(f"Cloudinary upload error: {e}")
        return None


def delete_image(public_id):
    """Delete an image from Cloudinary by public_id."""
    if not public_id:
        return False
    try:
        result = cloudinary.uploader.destroy(public_id)
        return result.get("result") == "ok"
    except Exception as e:
        current_app.logger.error(f"Cloudinary delete error: {e}")
        return False


def optimize_url(url, width=None, height=None, crop="fill", quality="auto"):
    """Return an optimized Cloudinary URL if possible."""
    if not url or "cloudinary.com" not in url:
        return url
    # Basic optimization via fetch or existing transforms
    return url
