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


def upload_file(file, folder="newvisionacademy/docs"):
    """
    Upload any file (PDF, image, video, doc) to Cloudinary.
    Uses resource_type=auto and chunked upload for large files (videos).
    Returns dict {url, public_id, format, resource_type} or None on failure.
    """
    if not file:
        return None
    filename = getattr(file, "filename", None)
    if filename is not None and not str(filename).strip():
        return None

    # Detect likely resource type from extension for better reliability
    name_l = str(filename).lower()
    video_exts = (".mp4", ".webm", ".mov", ".avi", ".mkv", ".m4v", ".3gp", ".mpeg", ".mpg")
    image_exts = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg", ".heic", ".heif")
    if name_l.endswith(video_exts):
        resource_type = "video"
    elif name_l.endswith(image_exts):
        resource_type = "image"
    else:
        resource_type = "auto"  # pdf, docs, etc.

    payload = _get_file_payload(file)
    if payload is None:
        return None

    try:
        # Estimate size for chunked upload decision
        size = None
        try:
            if hasattr(file, "content_length") and file.content_length:
                size = file.content_length
            elif hasattr(file, "seek") and hasattr(file, "tell"):
                pos = file.tell()
                file.seek(0, 2)
                size = file.tell()
                file.seek(pos)
            stream = getattr(file, "stream", None)
            if size is None and stream is not None and hasattr(stream, "seek"):
                pos = stream.tell()
                stream.seek(0, 2)
                size = stream.tell()
                stream.seek(0)
        except Exception:
            size = None

        options = {
            "folder": folder,
            "resource_type": resource_type,
            "overwrite": True,
            "invalidate": True,
        }

        # Chunked upload for files > ~8MB (videos especially)
        use_large = size is not None and size > 8 * 1024 * 1024
        if use_large or resource_type == "video":
            options["chunk_size"] = 6 * 1024 * 1024  # 6 MB chunks
            result = cloudinary.uploader.upload_large(payload, **options)
        else:
            result = cloudinary.uploader.upload(payload, **options)

        url = result.get("secure_url") or result.get("url")
        if not url:
            current_app.logger.error("Cloudinary returned no URL: %s", result)
            return None

        # Prefer inline-friendly URL for PDFs (avoid forced download when possible)
        fmt = (result.get("format") or "").lower()
        rtype = result.get("resource_type") or resource_type
        return {
            "url": url,
            "public_id": result.get("public_id", ""),
            "format": fmt or result.get("format"),
            "resource_type": rtype,
            "bytes": result.get("bytes"),
        }
    except Exception as e:
        current_app.logger.error("Cloudinary file upload error: %s", e, exc_info=True)
        # Fallback: try simple auto upload without chunking
        try:
            payload2 = _get_file_payload(file)
            result = cloudinary.uploader.upload(
                payload2,
                folder=folder,
                resource_type="auto",
                overwrite=True,
                invalidate=True,
            )
            url = result.get("secure_url") or result.get("url")
            if url:
                return {
                    "url": url,
                    "public_id": result.get("public_id", ""),
                    "format": result.get("format"),
                    "resource_type": result.get("resource_type", "auto"),
                }
        except Exception as e2:
            current_app.logger.error("Cloudinary fallback upload error: %s", e2, exc_info=True)
        return None


def delete_image(public_id, resource_type="image"):
    """Delete a resource from Cloudinary by public_id (image/video/raw)."""
    if not public_id:
        return False
    try:
        result = cloudinary.uploader.destroy(public_id, resource_type=resource_type)
        if result.get("result") == "ok":
            return True
        # Retry as video then raw
        for rt in ("video", "raw", "auto"):
            if rt == resource_type:
                continue
            try:
                result = cloudinary.uploader.destroy(public_id, resource_type=rt)
                if result.get("result") == "ok":
                    return True
            except Exception:
                pass
        return False
    except Exception as e:
        current_app.logger.error("Cloudinary delete error: %s", e)
        return False


def optimize_url(url, width=None, height=None, crop="fill", quality="auto"):
    """Return an optimized Cloudinary URL if possible."""
    if not url or "cloudinary.com" not in url:
        return url
    return url
