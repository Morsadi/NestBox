import os
import urllib.parse
from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify, current_app
from werkzeug.security import check_password_hash, generate_password_hash
from helpers import login_required, apology, get_db 
from storage_utils import get_flash_drives
import logging

logger = logging.getLogger(__name__)
auth_bp = Blueprint("auth", __name__)

# --- Dashboard Route ---
@auth_bp.route("/")
@login_required
def index():
    """Show the dashboard with connected drives."""
    try:
        from celery_worker import is_celery_indexing
        # Get drive list and current indexing status
        drives = get_flash_drives()
        
    except Exception as e:
        logger.error(f"Failed to get drive list or indexing status: {e}")
        return apology("Failed to get drive list or indexing status")
    
    # Pass data to the template.
    return render_template(
        "dashboard.html", 
        username=session.get("username"), 
        drives=drives,
        is_indexing=is_celery_indexing(),
    )

## Drive Indexing Endpoint
@auth_bp.route("/drive/index/<path:drive_path>", methods=["POST"])
@login_required
def trigger_drive_index(drive_path):
    """Triggers the background indexing task for a specific drive path."""
    from app import redis_client, INDEX_LOCK_KEY, LOCK_EXPIRATION
    
    if not redis_client:
        return jsonify({"status": "error", "message": "Redis connection failed. Cannot set lock."}), 503

    # Normalize and Decode the Path
    path_to_index = urllib.parse.unquote(drive_path)
    path_to_index = os.path.normpath(path_to_index)

    # POSIX (macOS / Linux): fix missing leading slash (e.g. 'Volumes/Mac' -> '/Volumes/Mac')
    if os.name != "nt" and not os.path.isabs(path_to_index):
        # This is exactly your mac case: 'Volumes/Mac'
        path_to_index = "/" + path_to_index  # -> '/Volumes/Mac'

    # Add trailing separator if it's just a drive letter (e.g., 'E:')
    if os.path.splitdrive(path_to_index)[0] and not os.path.splitdrive(path_to_index)[1]:
        path_to_index += os.path.sep
        
    # -----------------------------------------------------------------
    # 🛑 LOCK
    # -----------------------------------------------------------------
    # Set the lock if redis_client.set returns False
    if not redis_client.set(INDEX_LOCK_KEY, "running", nx=True, ex=LOCK_EXPIRATION):
        return jsonify({
            "status": "warning", 
            "message": "Drive is being synced in the background. Please try again later."
        }), 409

    try:
        # Release the lock if the path is invalid
        if not os.path.isdir(path_to_index):
            redis_client.delete(INDEX_LOCK_KEY) # Release the lock if validation fails
            return jsonify({"status": "error", "message": f"Drive not found: {path_to_index}"}), 400

        # Start the Celery task
        from celery_worker import index_drive_path
        index_drive_path.delay(path_to_index)
        
    except Exception as e:
        # If queuing fails, we must release the lock
        logger.error(f"Failed to dispatch index task for {path_to_index}: {e}")
        redis_client.delete(INDEX_LOCK_KEY) # Release lock
        return jsonify({"status": "error", "message": "Failed to queue task on worker."}), 503

    # Success
    # The lock will be released by the Celery worker in the 'finally' block
    return jsonify({
        "status": "Indexing started in background", 
        "path": path_to_index,
        "message": "Indexing has started. This may take several minutes."
    }), 202
    
## 🔑 Authentication Routes
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""
    session.clear()
    
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        # Validate form submission
        if not username:
            return apology("must provide username")
        if not password:
            return apology("must provide password")

        # Fetch user info from database
        try:
            db = get_db()
            rows = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchall()
        except Exception as e:
            logger.error(f"Error fetching user info from database: {e}")
            return apology("error fetching user info from database")

        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], password):
            return apology("invalid username and/or password")

        session["user_id"] = rows[0]["id"]
        session["username"] = rows[0]["username"]

        return redirect(url_for("auth.index"))

    else:
        return render_template("login.html")

@auth_bp.route("/logout")
def logout():
    """Log user out."""
    session.clear()
    return redirect(url_for("auth.login"))

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""

    if request.method == "POST":
        INVITATION_CODE = os.getenv("INVITATION_CODE")
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        invitation_code = request.form.get("invitation_code")

        if not username or not password or not confirmation:
            return apology("All fields are required")

        if password != confirmation:
            return apology("Passwords do not match")

        if not INVITATION_CODE:
            return apology("Registration is disabled. No invitation code set.")
        
        if invitation_code != INVITATION_CODE:
            return apology("Invitation code is invalid!")

        try:
            db = get_db()

            # Check if username exists
            if db.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone():
                return apology("Username already exists")

            # Insert new user
            db.execute(
                "INSERT INTO users (username, hash) VALUES (?, ?)", 
                (username, generate_password_hash(password))
            )
            db.commit()

            # Log in the new user immediately
            rows = db.execute("SELECT id, username FROM users WHERE username = ?", (username,)).fetchone()
            session["user_id"] = rows["id"]
            session["username"] = rows["username"]
            
            return redirect(url_for("auth.index"))

        except Exception as e:
            logger.error(f"Error inserting new user into database: {e}")
            return apology("error inserting new user into database")

    else:
        return render_template("register.html")
    
@auth_bp.route("/api/indexing", methods=["GET"])
@login_required
def indexing_status():
    from celery_worker import is_celery_indexing
    
    try:
        indexing = is_celery_indexing()
        return jsonify({"ok": True, "is_indexing": indexing})
    except Exception as e:
        current_app.logger.exception("Failed to check indexing status")
        return jsonify({"ok": False, "error": str(e)}), 500