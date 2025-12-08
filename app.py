import logging
import os
from datetime import timedelta

import redis
from celery import Celery
from flask import Flask, session
from flask_session import Session
from cert_utils import ensure_self_signed_cert
from helpers import close_db, init_all_dbs

# === Constants ===
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = 6379
REDIS_DB = 0
REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"

INDEX_LOCK_KEY = "full_scan_lock"
LOCK_EXPIRATION = 3600  # 1 hour (seconds)

SESSION_LIFETIME_MINUTES = 60

# === Logging ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === Flask App ===
app = Flask(__name__)

# Session config
app.config.update(
    SESSION_TYPE="filesystem",
    SESSION_PERMANENT=False,
    PERMANENT_SESSION_LIFETIME=timedelta(minutes=SESSION_LIFETIME_MINUTES),
    SESSION_COOKIE_SECURE=False,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)

Session(app)

# === Initialize Redis Client ===
def create_redis_client() -> redis.Redis | None:
    try:
        client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            decode_responses=True,
        )
        client.ping()
        logger.info("Connected to Redis successfully.")
        return client
    except Exception as exc:  # noqa: BLE001
        logger.error("Could not connect to Redis: %s", exc)
        return None


redis_client = create_redis_client()

# === Initialize Celery ===
def make_celery(flask_app: Flask) -> Celery:
    """Configure and return a Celery instance bound to the Flask app."""
    celery = Celery(
        flask_app.import_name,
        broker=REDIS_URL,
        backend=REDIS_URL,
        include=["celery_worker"],
    )
    celery.conf.update(
        task_track_started=True,
        result_expires=3600,
    )

    class ContextTask(celery.Task):
        """Celery Task that runs inside the Flask app context."""

        def __call__(self, *args, **kwargs):  # noqa: D401
            with flask_app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery


celery = make_celery(app)

# === Request Hooks ===
@app.before_request
def refresh_session():
    """Keep the session alive by marking it as permanent."""
    session.permanent = True


@app.after_request
def disable_caching(response):
    """Ensure browsers do not cache responses."""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = "0"
    response.headers["Pragma"] = "no-cache"
    return response


@app.teardown_appcontext
def teardown_db(exception):
    """Close DB connection at the end of the request."""
    close_db(exception)
    
@app.template_filter('simplify_size')
def simplify_size_filter(size):
    """Converts bytes to a human-readable string (KB, MB, GB)."""
    if size is None:
        return ""
    
    # Iterate through units, dividing by 1024 until the number is small enough
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    
    return f"{size:.1f} PB"

# === Blueprints ===
from routes import auth_bp, browse_bp, media_bp, upload_bp

app.register_blueprint(auth_bp)
app.register_blueprint(browse_bp)
app.register_blueprint(media_bp)
app.register_blueprint(upload_bp)

# === Initial DB Setup ===
with app.app_context():
    init_all_dbs()

# === Run App ===
if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cert_dir = os.path.join(base_dir, "certs")
    cert_path = os.path.join(cert_dir, "nestbox.crt")
    key_path = os.path.join(cert_dir, "nestbox.key")

    # Use env var so you can change IP without touching code
    ip_for_cert = os.getenv("NESTBOX_IP", "127.0.0.1")

    ensure_self_signed_cert(ip_for_cert, cert_path, key_path)
    
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True,
        threaded=True,
        use_reloader=False,
        ssl_context=(cert_path, key_path),
    )
