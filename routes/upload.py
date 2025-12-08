import os
import urllib.parse
import logging
from flask import Blueprint, request, jsonify, render_template, redirect, url_for
from werkzeug.exceptions import ClientDisconnected
from helpers import login_required, is_safe_path
from config import UPLOAD_TMP 

# --- Setup ---
upload_bp = Blueprint("upload", __name__)

os.makedirs(UPLOAD_TMP, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

logger.info(f"[INIT] Flask saving chunks to: {UPLOAD_TMP}")

# ---------------------------------------------------------
# Resume status endpoint
# ---------------------------------------------------------
@upload_bp.route("/upload/status")
@login_required
def upload_status():
    uuid = request.args.get("uuid")
    if not uuid:
        return jsonify({"error": "Missing uuid"}), 400

    folder = os.path.join(UPLOAD_TMP, uuid)
    if not os.path.exists(folder):
        return jsonify({"uploaded_chunks": 0})

    count = len([f for f in os.listdir(folder) if f.endswith(".part")])
    return jsonify({"uploaded_chunks": count})

# ---------------------------------------------------------
# Main upload route (Handles Chunk Saving)
# ---------------------------------------------------------
@upload_bp.route("/upload/", methods=["GET", "POST"])
@login_required
def upload():
    # ---------- GET (Render Template) ----------
    if request.method == "GET":
        raw_path = request.args.get("path", "")
        path = urllib.parse.unquote(raw_path).strip()

        if not path or not os.path.isdir(path):
            logger.warning("[SECURITY] Invalid or direct access to /upload — redirecting.")
            return redirect(url_for("auth.index")) 

        path = os.path.normpath(path)
        return render_template("upload.html", path=path)

    # ---------- POST (Handle Chunk Upload) ----------
    try:
        from celery_worker import perform_merge
    except ImportError:
        logger.error("Could not import perform_merge task.")
        return jsonify({"error": "Worker configuration missing"}), 503

    # --- Collect form data ---
    try:
        dz_uuid = request.form.get("dzuuid")
        dz_chunk_index = int(request.form.get("dzchunkindex", 0))
        dz_total_chunks = int(request.form.get("dztotalchunkcount", 1))
        raw_destination = request.form.get("destination", os.getcwd())
        destination = os.path.normpath(urllib.parse.unquote(raw_destination))
        
        # --- Security Checks ---
        if not is_safe_path(destination):
            logger.warning(f"[SECURITY] Path Traversal attempt blocked: {destination}")
            return jsonify({"error": "Forbidden path"}), 403

        file = request.files.get("file")
        if not dz_uuid or not file:
             raise ValueError("Missing essential form data (UUID or file).")

    except Exception as e:
        logger.error(f"[UPLOAD ERROR] Bad form data: {e}")
        return jsonify({"error": "Malformed request"}), 400

    # --- Save Chunk ---
    temp_dir = os.path.join(UPLOAD_TMP, dz_uuid)
    os.makedirs(temp_dir, exist_ok=True)
    chunk_path = os.path.join(temp_dir, f"{dz_chunk_index:05}.part")

    try:
        file.save(chunk_path)
        logger.info(f"[CHUNK] UUID={dz_uuid} index={dz_chunk_index+1}/{dz_total_chunks}")
    except ClientDisconnected:
        logger.warning("[UPLOAD] Client disconnected mid-chunk")
        return "", 499
    except Exception as e:
        logger.error(f"[UPLOAD ERROR] Failed to save chunk: {e}")
        return jsonify({"error": str(e)}), 500

    # --- HANDLE FINAL CHUNK LOGIC ---
    if dz_chunk_index + 1 == dz_total_chunks:
        if verify_all_chunks_present(temp_dir, dz_total_chunks):
            
            final_filename = file.filename

            # 5 seconds for more robust file system I/O completion
            task_result = perform_merge.apply_async(
                args=[dz_uuid, destination, final_filename, dz_total_chunks],
                countdown=5,
            )
            logger.info(f"[QUEUE SUCCESS] UUID={dz_uuid} merge *queued* (Task ID: {task_result.id})")
            return jsonify({
                "status": "complete_queued",
                "uuid": dz_uuid,
                "task_id": task_result.id,
                "filename": final_filename
            }), 200
        else:
            missing = dz_total_chunks - len([f for f in os.listdir(temp_dir) if f.endswith('.part')])
            logger.warning(f"[UPLOAD INCOMPLETE] UUID={dz_uuid} missing {missing} chunks. Waiting for client resume.")
            return jsonify({
                "status": "resume_required",
                "uuid": dz_uuid,
                "missing_chunks": missing,
            }), 409

    # If not the final chunk index
    return jsonify({"status": "ok", "chunk": dz_chunk_index})

# ---------------------------------------------------------
#  Upload Checkpoint Endpoint
# ---------------------------------------------------------
@upload_bp.route('/upload/checkpoint', methods=['POST'])
@login_required
def upload_checkpoint():
    """Checks if the file already exists in the target path before upload."""
    data = request.get_json(silent=True) or {}
    filename = data.get('filename')
    directory = data.get('path')

    if not filename or not directory:
        return jsonify({'exists': False, 'error': 'Missing parameters'}), 400

    # Normalize and secure path
    directory = os.path.normpath(directory)
    
    if not is_safe_path(directory):
        logger.warning(f"[SECURITY] Blocked unsafe path check: {directory}")
        return jsonify({'exists': False, 'error': 'Forbidden path'}), 403

    file_path = os.path.join(directory, filename)
    exists = os.path.exists(file_path)

    logger.info(f"[CHECKPOINT] {filename} {'exists' if exists else 'not found'} in {directory}")
    return jsonify({'exists': exists}), 200

# ---------------------------------------------------------
def verify_all_chunks_present(temp_dir: str, total_chunks: int) -> bool:
    if not os.path.exists(temp_dir):
        return False
    existing = [f for f in os.listdir(temp_dir) if f.endswith(".part")]
    return len(existing) == total_chunks