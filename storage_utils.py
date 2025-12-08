import os
import re
import platform
import ctypes
from datetime import datetime
import psutil
from helpers import get_file_index_db

# Shared constants
PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".heic", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".m4v"}

SKIP_PREFIXES = {".", "._"}
SKIP_NAMES = {"Thumbs.db", "desktop.ini", ".DS_Store"}

# --- ICON MAP ---
ICON_MAP = {
    # Documents
    ".pdf":  "fa fa-file-pdf text-danger",
    ".doc":  "fa fa-file-word text-primary",
    ".docx": "fa fa-file-word text-primary",
    ".xls":  "fa fa-file-excel text-success",
    ".xlsx": "fa fa-file-excel text-success",
    ".ppt":  "fa fa-file-powerpoint text-warning",
    ".pptx": "fa fa-file-powerpoint text-warning",
    ".zip":  "fa fa-file-archive text-muted",
    ".rar":  "fa fa-file-archive text-muted",

    # Audio
    ".mp3": "fa fa-file-audio",
    ".wav": "fa fa-file-audio",
    
    "default": "fa fa-file text-muted"
}

# Apply IMAGE style to all photo extensions
ICON_MAP.update({ext: "fa fa-image" for ext in PHOTO_EXTENSIONS})

# Apply VIDEO style to all video extensions
ICON_MAP.update({ext: "fa fa-play" for ext in VIDEO_EXTENSIONS})


def get_icon_class(file_name: str) -> str:
    ext = os.path.splitext(file_name)[1].lower()
    return ICON_MAP.get(ext, ICON_MAP["default"])


# --- Helper Functions ---
def is_hidden_folder(path):
    """Check if a file system path (folder or file) is hidden."""
    if platform.system() == "Windows":
        try:
            # Check for Windows 'Hidden' file attribute (0x2)
            attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))
            return attrs != -1 and bool(attrs & 2)
        except Exception:
            return False
    # Standard Unix-like check (Linux, macOS): starts with '.'
    return os.path.basename(path).startswith('.')

# --- Drive and Space Functions ---
def get_flash_drives():
    """
    Retrieves information about mounted external removable drives.
    """
    drives = []
    
    for part in psutil.disk_partitions(all=False):
        if not part.device or not part.mountpoint:
            continue
        
        is_removable = False

        if platform.system() == "Windows":
            print("-----------------------------------------PART:", part)
            # Check for 'removable' option or if mountpoint is not C:\\
            if 'removable' in part.opts or not part.mountpoint.startswith("C:\\"):
                is_removable = True
        elif platform.system() in ("Darwin", "Linux"):
            # Use common external mount points as a primary filter
            if re.search(r"^/(Volumes|media)/[^/]+|^/mnt/", part.mountpoint):
                # Exclude Volumes/Mac for mac
                if part.mountpoint == "/Volumes/Mac":
                    continue
                is_removable = True
        
        if is_removable:
            try:
                usage = psutil.disk_usage(part.mountpoint)
                total_gb = round(usage.total / 10**9, 2)
                used_percent = round(usage.percent, 1)
                
                # Determine drive name for display
                name = part.device.split('/')[-1] if platform.system() != "Windows" else part.mountpoint

                drives.append({
                    "name": name,
                    "path": part.mountpoint,
                    "size_gb": total_gb,
                    "used_percent": used_percent,
                })
            except Exception as e:
                # Log error for inaccessible drives, but continue
                print(f"[DRIVE ERROR - Usage Check {part.mountpoint}]: {e}")
                continue

    return drives

# --- Directory Listing Function ---
def list_directory_contents(path, offset=0, limit=40, view_mode="files", url_for_func=None, get_thumb_hash_func=None):
    """
    List contents of a directory from the file index database with pagination.
    """
    if not url_for_func or not get_thumb_hash_func:
        raise ValueError("url_for_func and get_thumb_hash_func must be provided.")

    parent_path_value = os.path.normpath(path)

    if not os.path.splitdrive(parent_path_value)[1]:
        parent_path_value = os.path.splitdrive(parent_path_value)[0] + '\\'

    db = get_file_index_db()

    try:
        total_media_asset_count = db.execute(
            "SELECT COUNT(*) FROM file_index WHERE is_folder = 0 AND is_media = 1 AND parent_path = ?",
            (parent_path_value,)
        ).fetchone()[0]

        total_file_count = db.execute(
            "SELECT COUNT(*) FROM file_index WHERE is_folder = 0 AND is_media = 0 AND parent_path = ?",
            (parent_path_value,)
        ).fetchone()[0]

        folders = db.execute(
            "SELECT name, path FROM file_index WHERE parent_path = ? AND is_folder = 1 ORDER BY name ASC",
            (parent_path_value,)
        ).fetchall()
        formatted_folders = [{"name": r[0], "path": r[1], "type": "folder"} for r in folders]

        if view_mode == "files":
            media_clause = "1 = 1"
        elif view_mode == "gallery":
            media_clause = "is_media = 1"
        else:
            return formatted_folders, [], total_file_count, [], total_media_asset_count
        
        # Sort setup
        if view_mode == "files":
            sort_clause = "name ASC"
        elif view_mode == "gallery":
            sort_clause = "created_time DESC"

        items = db.execute(
            f"""
            SELECT name, path, type, size, modified_time, created_time, is_media
            FROM file_index
            WHERE is_folder = 0 AND {media_clause} AND parent_path = ?
            ORDER BY {sort_clause}
            LIMIT ? OFFSET ?
            """,
            (parent_path_value, limit, offset)
        ).fetchall()
        
        paginated_files = []
        paginated_media = []

        for name, file_path, file_type, size, modified_time, created_time, is_media in items:

            file_data = {
                "name": name,
                "path": file_path,
                "type": file_type,
                "size": size,
                "modified": datetime.fromtimestamp(modified_time) if modified_time else None,
                "created": datetime.fromtimestamp(created_time) if created_time else None,
                "thumbnail_url": None,
                "full_imgproxy_url": None,
                "vid_stream_url": None,
                "icon_class": get_icon_class(name)
            }

            if is_media:
                if file_type.lower() in [".mp4", ".mov", ".webm"]:
                    file_data["vid_stream_url"] = url_for_func("media.serve_media", path=file_path)
                else:
                    file_data["full_image_url"] = url_for_func("media.serve_media", path=file_path)
                       
                if view_mode == "gallery":
                    paginated_media.append(file_data)
                else:
                    paginated_files.append(file_data)
            else:
                paginated_files.append(file_data)
        total_items = total_file_count + total_media_asset_count
        if view_mode == "files":
            return formatted_folders, paginated_files, total_items, [], total_media_asset_count
        else:
            return formatted_folders, [], total_items, paginated_media, total_media_asset_count

    except Exception as e:
        print(f"[DB BROWSE ERROR] Failed to query path {path}: {e}")
        return [], [], 0, [], 0