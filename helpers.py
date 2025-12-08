import sqlite3
import os
import sys
from functools import wraps
from flask import g, session, redirect, render_template
from werkzeug.security import generate_password_hash, check_password_hash

# --- DB Paths ---
INSTANCE_FOLDER = 'instance'
USERS_DB_PATH = os.path.join(INSTANCE_FOLDER, 'users.db')
FILES_DB_PATH = os.path.join(INSTANCE_FOLDER, 'file_index.db')

def _ensure_instance_folder():
    """Internal helper to create the 'instance' folder if it doesn't exist."""
    os.makedirs(INSTANCE_FOLDER, exist_ok=True)

# -----------------------------
# Error handling
# -----------------------------
def apology(message, code=400):
    """Render message as an apology to the user."""
    return render_template("apology.html", message=message), code

# -----------------------------
# Authentication helpers
# -----------------------------
def login_required(f):
    """Decorator to require login for routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


def hash_password(password):
    """Generate a secure password hash."""
    return generate_password_hash(password)


def verify_password(password, hash_value):
    """Verify password against stored hash."""
    return check_password_hash(hash_value, password)


# -----------------------------
# Database helpers
# -----------------------------
def get_db():
    """Get a database connection for the current app context (users.db)."""
    if "db" not in g:
        _ensure_instance_folder() # Create instance folder if missing
        g.db = sqlite3.connect(USERS_DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
        g.db.row_factory = sqlite3.Row
    return g.db

def get_file_index_db():
    """Get a database connection for the file index (file_index.db)."""
    if "file_index_db" not in g:
        _ensure_instance_folder() # Create instance folder if missing
        g.file_index_db = sqlite3.connect(FILES_DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
        g.file_index_db.row_factory = sqlite3.Row
    return g.file_index_db

def close_db(e=None):
    """Close all database connections at the end of the request."""
    # Close the users.db connection
    db = g.pop("db", None)
    if db is not None:
        db.close()
    
    # Close the file_index_db connection
    file_db = g.pop("file_index_db", None)
    if file_db is not None:
        file_db.close()


def init_all_dbs():
    """
    Checks and creates both databases and their tables.
    This is a standalone function safe to run on app startup.
    """
    _ensure_instance_folder() # Create folder first
    
    try:
        # Init users.db
        db = sqlite3.connect(USERS_DB_PATH)
        db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                hash TEXT NOT NULL
            )
        ''')
        db.commit()
        db.close()
        print("[DB] Users table checked/created successfully.")
    except Exception as e:
        print(f"[DB ERROR] Failed to initialize users.db: {e}")

    try:
        # Init file_index.db
        db = sqlite3.connect(FILES_DB_PATH)
        db.execute("""
            CREATE TABLE IF NOT EXISTS file_index (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                path TEXT UNIQUE NOT NULL,
                parent_path TEXT NOT NULL,
                is_folder INTEGER NOT NULL,
                is_media INTEGER NOT NULL, -- 1 for image/video, 0 otherwise
                size INTEGER,
                modified_time REAL,
                created_time REAL,
                type TEXT
            );
        """)
        db.execute("CREATE INDEX IF NOT EXISTS idx_parent_path ON file_index (parent_path);")
        db.execute("CREATE INDEX IF NOT EXISTS idx_is_folder ON file_index (is_folder);")
        db.execute("CREATE INDEX IF NOT EXISTS idx_is_media ON file_index (is_media);")
        db.execute("""
            CREATE INDEX IF NOT EXISTS idx_browse_filter 
            ON file_index (parent_path, is_folder, is_media, name);
        """)
        db.commit()
        db.close()
        print("[DB] File index table checked/created successfully.")
    except Exception as e:
        print(f"[DB ERROR] Failed to initialize file_index.db: {e}")

def is_safe_path(path: str) -> bool:
    """Check if a path is safe to access across platforms."""
    if not path:
        return False

    # Normalize the path
    path = os.path.normpath(path)

    # Block traversal attempts
    if ".." in path.replace("\\", "/"):
        return False

    # ---------- Windows ----------
    if os.name == "nt":
        # Must be like C:\ or D:\...
        drive, tail = os.path.splitdrive(path)
        if not drive or not drive.endswith(":"):
            return False

        # Ensure drive actually exists
        if not os.path.exists(drive + "\\"):
            return False

        return True

    if not os.path.isabs(path):
        return False

    if sys.platform == "darwin":
        allowed_roots = ("/Volumes",)
    else:
        allowed_roots = ("/",)

    try:
        # commonpath will raise ValueError if paths are on different drives, etc.
        if not any(os.path.commonpath([path, root]) == root for root in allowed_roots):
            return False
    except ValueError:
        return False

    return True

