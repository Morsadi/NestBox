import os
import urllib.parse
from math import ceil
from flask import Blueprint, render_template, request, abort, url_for, jsonify, current_app
from helpers import login_required
from storage_utils import list_directory_contents
import hashlib

GALLERY_PER_PAGE = 80
FILES_PER_PAGE = 100

browse_bp = Blueprint("browse", __name__)

@browse_bp.route("/browse/<view_mode>")
@login_required
def browse_directory(view_mode):
    from celery_worker import is_celery_indexing
    
    # Get the view mode
    if view_mode == "files":
        asset_list_key = "files"
    elif view_mode == "gallery":
        asset_list_key = "assets"
    else:
        # Abort if the user tries to go to /browse/something_else
        abort(404, f"Invalid view mode: {view_mode}")

    raw_path = request.args.get("path")

    if not raw_path:
        abort(400, "Missing path")
    
    path = os.path.normpath(urllib.parse.unquote(raw_path))
    
    page = max(int(request.args.get("page", 1)), 1)
    per_page = FILES_PER_PAGE

    # Adjust per_page for gallery view      
    if view_mode == "gallery":
        per_page = GALLERY_PER_PAGE

    offset = (page - 1) * per_page
    
    # Call Directory Contents Listing (DB Query) ---
    folders, paginated_files, total_file_count, paginated_media_assets, total_media_asset_count = list_directory_contents(
        path, 
        offset=offset, 
        limit=per_page,
        view_mode=view_mode,
        # Dependency Injection for URL creation and Hashing:
        url_for_func=url_for, 
        get_thumb_hash_func=get_thumb_hash
    )
    
    total_items = total_file_count if view_mode == "files" else total_media_asset_count
    total_pages = max(1, ceil(total_items / per_page))
    
    # Determine parent directory for navigation 
    parent_dir = os.path.normpath(os.path.dirname(path))
    
    # Adjust parent for drive roots
    if parent_dir == path:
        parent_dir = os.path.splitdrive(path)[0] + '\\'

        
    # Prepare Context for Template ---
    context = {
        "view_mode": view_mode,
        "path": path,
        "parent": parent_dir,
        "page": page,
        "total_pages": total_pages,
        "total_file_count": total_file_count,
        "total_media_asset_count": total_media_asset_count,
        "folders": folders,
        "per_page": per_page,
        "is_indexing": is_celery_indexing(),
    }
    
    # Dynamically add the correct list of paginated items
    if view_mode == "files":
        context[asset_list_key] = paginated_files
    else: # gallery mode
        context[asset_list_key] = paginated_media_assets

    # Render the single template
    return render_template("browse/browse.html", **context)

def get_thumb_hash(src: str) -> str:
    """Generates a unique, safe filename (SHA1 hash) based on the source file's full path."""
    # Use the full, normalized path as the unique key
    norm_path = os.path.normpath(src)
    return hashlib.sha1(norm_path.encode('utf-8')).hexdigest()