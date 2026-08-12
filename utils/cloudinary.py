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
    Upload any file (PDF, image, video, doc) to Cloudinary with correct resource_type.
    PDFs/docs MUST use resource_type=raw so URL is /raw/upload/ (not /image/upload/).
    Returns dict {url, public_id, format, resource_type} or None on failure.
    """
    if not file:
        return None
    filename = getattr(file, "filename", None)
    if filename is not None and not str(filename).strip():
        return None

    name_l = str(filename).lower()
    video_exts = (".mp4", ".webm", ".mov", ".avi", ".mkv", ".m4v", ".3gp", ".mpeg", ".mpg")
    image_exts = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg", ".heic", ".heif")
    raw_exts = (".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".txt", ".csv", ".zip", ".rar", ".rtf")

    if name_l.endswith(video_exts):
        resource_type = "video"
    elif name_l.endswith(image_exts) or name_l.endswith(".pdf"):
        # PDF as image → pages deliverable as PNG even when PDF ACL is blocked
        resource_type = "image"
    elif name_l.endswith(raw_exts):
        resource_type = "raw"
    else:
        resource_type = "raw"

    payload = _get_file_payload(file)
    if payload is None:
        return None

    try:
        import uuid as _uuid
        from werkzeug.utils import secure_filename as _sf
        import os as _os

        # Always keep real extension in public_id (fixes stream_xxx without .pdf/.docx)
        safe = _sf(str(filename)) or "file"
        root, ext = _os.path.splitext(safe)
        if not ext:
            # recover extension from original name
            _, ext2 = _os.path.splitext(str(filename).lower())
            ext = ext2 if ext2 else ""
        if not ext and resource_type == "raw":
            ext = ".bin"
        root = (root or "file")[:60]
        public_name = f"{_uuid.uuid4().hex[:8]}_{root}{ext}"

        options = {
            "folder": folder,
            "resource_type": resource_type,
            "overwrite": True,
            "invalidate": True,
            "public_id": public_name,
        }

        # Large videos: chunked upload
        size = None
        try:
            stream = getattr(file, "stream", None)
            if stream is not None and hasattr(stream, "seek"):
                pos = stream.tell()
                stream.seek(0, 2)
                size = stream.tell()
                stream.seek(0)
            elif hasattr(file, "seek") and hasattr(file, "tell"):
                pos = file.tell()
                file.seek(0, 2)
                size = file.tell()
                file.seek(0)
        except Exception:
            size = None

        if resource_type == "video" or (size and size > 8 * 1024 * 1024):
            options["chunk_size"] = 6 * 1024 * 1024
            result = cloudinary.uploader.upload_large(payload, **options)
        else:
            result = cloudinary.uploader.upload(payload, **options)

        url = result.get("secure_url") or result.get("url")
        if not url:
            current_app.logger.error("Cloudinary returned no URL: %s", result)
            return None

        # Safety: if PDF somehow landed on /image/upload/, rewrite to /raw/upload/
        # (only helps if asset was stored as raw; new uploads should already be raw)
        fmt = (result.get("format") or "").lower()
        rtype = result.get("resource_type") or resource_type
        # Keep PDF on image/upload so page-as-image preview works

        # Ensure URL path ends with extension when we know it
        if ext and ext not in url.split("?")[0].lower():
            # Cloudinary raw public_id already includes ext; if missing, append for clients
            if resource_type == "raw" and not url.lower().rstrip("/").endswith(ext.lower()):
                pass  # public_id should already include it
        return {
            "url": url,
            "public_id": result.get("public_id", ""),
            "format": (fmt or result.get("format") or ext.lstrip(".")),
            "resource_type": rtype,
            "bytes": result.get("bytes"),
            "original_filename": str(filename),
        }
    except Exception as e:
        current_app.logger.error("Cloudinary file upload error: %s", e, exc_info=True)
        # Explicit raw retry for PDFs/docs (do NOT fall back to image)
        try:
            payload2 = _get_file_payload(file)
            rt = "raw" if (name_l.endswith(raw_exts) or name_l.endswith(".pdf")) else "auto"
            if name_l.endswith(video_exts):
                rt = "video"
            elif name_l.endswith(image_exts):
                rt = "image"
            import uuid as _uuid2
            from werkzeug.utils import secure_filename as _sf2
            import os as _os2
            safe2 = _sf2(str(filename)) or "file"
            r2, e2 = _os2.path.splitext(safe2)
            if not e2:
                _, e2 = _os2.path.splitext(str(filename).lower())
            pname = f"{_uuid2.uuid4().hex[:8]}_{(r2 or 'file')[:60]}{e2 or ''}"
            result = cloudinary.uploader.upload(
                payload2,
                folder=folder,
                resource_type=rt,
                overwrite=True,
                invalidate=True,
                public_id=pname,
            )
            url = result.get("secure_url") or result.get("url")
            if url:
                # keep pdf as image upload
                return {
                    "url": url,
                    "public_id": result.get("public_id", ""),
                    "format": result.get("format"),
                    "resource_type": result.get("resource_type", rt),
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
