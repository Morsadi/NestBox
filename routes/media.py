import os, io
from flask import Blueprint, send_file, abort, request
from helpers import login_required
from PIL import Image, ImageOps
from pillow_heif import register_heif_opener
import urllib.parse

# Add HEIC support
register_heif_opener()

media_bp = Blueprint("media", __name__)

@media_bp.route("/media/<path:path>")
@login_required
def serve_media(path):
    # Decode URL-encoded path (e.g. %2FVolumes%2FMac)
    decoded_path = urllib.parse.unquote(path)

    # Cross-platform path normalization
    if os.name == "nt":
        # Windows: keep using abspath, paths look like "E:\folder\img.jpg"
        full_path = os.path.abspath(decoded_path)
    else:
        # POSIX (macOS / Linux)

        # If it isn't absolute (e.g. "Volumes/Mac/..."), assume it's rooted at /
        if not os.path.isabs(decoded_path):
            decoded_path = "/" + decoded_path  # -> "/Volumes/Mac/..."

        # Now just normalize it
        full_path = os.path.normpath(decoded_path)

    # Optional: you can add a safety check to restrict to certain roots:
    # if os.name != "nt" and not full_path.startswith("/Volumes/"):
    #     return abort(400)

    # Ensure file exists
    if not os.path.exists(full_path) or not os.path.isfile(full_path):
        return abort(404)

    # Query parameters (Imgproxy-style)
    w = request.args.get("w", type=int)
    h = request.args.get("h", type=int)
    q = request.args.get("q", type=int, default=95)
    f = request.args.get("fmt", default="jpeg").lower()

    # If NO resizing parameters → serve original file
    if not w and not h:
        return send_file(full_path)

    # Otherwise serve resized file
    try:
        # Open image
        with Image.open(full_path) as img:
            # Img orientation
            img = ImageOps.exif_transpose(img)

            # Resize if needed
            if w or h:
                img.thumbnail((w or img.width, h or img.height))

            # Save to buffer
            buf = io.BytesIO()
            img.save(buf, format=f, quality=q, optimize=True)
            buf.seek(0)

            # Return file
            return send_file(
                buf,
                mimetype=f"image/{f}",
                as_attachment=False
            )
    except Exception as e:
        print("IMAGE ERROR:", e)
        return abort(500)