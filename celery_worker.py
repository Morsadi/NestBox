# celery_worker.py

import os
import shutil
import logging
from storage_utils import is_hidden_folder, PHOTO_EXTENSIONS, VIDEO_EXTENSIONS
from helpers import get_file_index_db
from app import celery, redis_client, INDEX_LOCK_KEY
import sqlite3
from config import UPLOAD_TMP

# --- Configuration & Logging ---
logger = logging.getLogger(__name__)
os.makedirs(UPLOAD_TMP, exist_ok=True)
logger.info(f"[INIT] Celery using chunk folder: {UPLOAD_TMP}")

# ---------------------------------------------------------
# Celery Task Definitions
# ---------------------------------------------------------
@celery.task
def index_single_file(file_path):
    """
    Indexes a single file (used for uploads/merges).
    Also indexes the parent folder.
    """
    db = get_file_index_db()
    file_path = os.path.normpath(file_path)
    parent_path = os.path.dirname(file_path)

    try:
        # --- 1. Index the Parent Folder ---
        db.execute(
            """
            INSERT OR IGNORE INTO file_index (name, path, parent_path, is_folder, type, modified_time)
            VALUES (?, ?, ?, 1, 'folder', ?)
            """,
            (os.path.basename(parent_path), 
             parent_path, 
             os.path.dirname(parent_path), 
             os.path.getmtime(parent_path))
        )

        # --- 2. Index the File Itself ---
        stat = os.stat(file_path)
        filename = os.path.basename(file_path)
        file_type_ext = os.path.splitext(filename)[1].lower() 
        is_media = 1 if file_type_ext in PHOTO_EXTENSIONS or file_type_ext in VIDEO_EXTENSIONS else 0
        
        db.execute(
            """
            INSERT OR REPLACE INTO file_index 
            (name, path, parent_path, is_folder, is_media, size, modified_time, created_time, type)
            VALUES (?, ?, ?, 0, ?, ?, ?, ?, ?)
            """,
            (filename, file_path, parent_path, is_media, stat.st_size, stat.st_mtime, stat.st_birthtime, file_type_ext)
        )

        db.commit()
        logger.info(f"[INDEX SUCCESS] Indexed single file and parent: {file_path}")
        
        return {'status': 'success'}

    except FileNotFoundError:
        logger.error(f"[INDEX FAIL] File not found for indexing: {file_path}")
        db.rollback()
        return {'status': 'failure', 'error': 'File not found'}
    except sqlite3.Error as e:
        logger.error(f"[DB ERROR] Single file indexing failed for {file_path}: {e}")
        db.rollback()
        return {'status': 'failure', 'error': f"Database error: {e}"}

@celery.task
def index_drive_path(root_path):
    """
    Scans a directory (root_path) and indexes all files and sub-folders,
    clearing existing entries first.
    Releases Redis lock at the end.
    """
    try:
        # Normalize the root path
        root_path = os.path.normpath(root_path)

        # Fix drive roots: "D:" → "D:\"
        drive, tail = os.path.splitdrive(root_path)
        if drive and not tail:
            root_path = drive + os.path.sep

        db = get_file_index_db()
        insert_count = 0

        try:
            # Clear existing index entries for this drive
            logger.info(f"Clearing old index entries for {root_path}")
            db.execute("DELETE FROM file_index WHERE path LIKE ?", (root_path + '%',))
            db.commit()

            logger.info(f"Starting index scan for {root_path}...")

            # ------------------------------------------------------------
            # 1. Insert the ROOT FOLDER unconditionally (this fixes your bug)
            # ------------------------------------------------------------
            try:
                db.execute(
                    """
                    INSERT OR IGNORE INTO file_index 
                    (name, path, parent_path, is_folder, is_media, size, modified_time, type)
                    VALUES (?, ?, ?, 1, 0, 0, ?, 'folder')
                    """,
                    (
                        os.path.basename(root_path) or root_path,
                        root_path,
                        root_path,  # root parent = itself for drive roots
                        os.path.getmtime(root_path)
                    )
                )
                insert_count += 1
            except Exception as e:
                logger.warning(f"Failed to insert root folder {root_path}: {e}")

            # ------------------------------------------------------------
            # 2. Walk the filesystem and index subfolders and files
            # ------------------------------------------------------------
            for current_dir, dirs, files in os.walk(root_path):

                # Remove system/hidden dot-prefixed folders
                dirs[:] = [d for d in dirs if not d.startswith('.')]

                # Skip hidden Windows folders (like System Volume Information)
                if current_dir != root_path and is_hidden_folder(current_dir):
                    dirs[:] = []
                    continue

                # Determine this folder's parent
                parent_path = os.path.dirname(current_dir)
                if parent_path == os.path.splitdrive(current_dir)[0]:
                    parent_path = os.path.splitdrive(current_dir)[0] + os.path.sep

                # --------------------------------------------------------
                # Insert CURRENT DIRECTORY (including empty folders)
                # --------------------------------------------------------
                if current_dir != root_path:  # root already inserted above
                    try:
                        db.execute(
                            """
                            INSERT OR IGNORE INTO file_index
                            (name, path, parent_path, is_folder, is_media, size, modified_time, type)
                            VALUES (?, ?, ?, 1, 0, 0, ?, 'folder')
                            """,
                            (
                                os.path.basename(current_dir),
                                current_dir,
                                parent_path,
                                os.path.getmtime(current_dir)
                            )
                        )
                        insert_count += 1
                    except sqlite3.IntegrityError:
                        logger.warning(f"Duplicate folder skipped: {current_dir}")

                # --------------------------------------------------------
                # Insert FILES within this folder
                # --------------------------------------------------------
                for filename in files:
                    if filename.startswith('.'):
                        continue

                    file_path = os.path.join(current_dir, filename)

                    try:
                        stat = os.stat(file_path)
                        size = stat.st_size
                        modified_time = stat.st_mtime
                        created_time = stat.st_birthtime

                        ext = os.path.splitext(filename)[1].lower()
                        is_media = 1 if ext in PHOTO_EXTENSIONS or ext in VIDEO_EXTENSIONS else 0

                        db.execute(
                            """
                            INSERT OR IGNORE INTO file_index
                            (name, path, parent_path, is_folder, is_media, size, modified_time, created_time, type)
                            VALUES (?, ?, ?, 0, ?, ?, ?, ?, ?)
                            """,
                            (
                                filename,
                                file_path,
                                current_dir,
                                is_media,
                                size,
                                modified_time,
                                created_time,
                                ext
                            )
                        )
                        insert_count += 1

                    except FileNotFoundError:
                        logger.warning(f"File not found during index: {file_path}")
                    except sqlite3.IntegrityError:
                        logger.warning(f"Duplicate file skipped: {file_path}")
                    except Exception as e:
                        logger.error(f"Unexpected error indexing {file_path}: {e}")

            db.commit()
            logger.info(f"[INDEXING COMPLETE] {root_path}: Indexed {insert_count} entries.")
            return {'status': 'success', 'root': root_path, 'count': insert_count}

        except sqlite3.Error as e:
            logger.error(f"[DB ERROR] Indexing failed for {root_path}: {e}")
            db.rollback()
            return {'status': 'failure', 'root': root_path, 'error': f"Database error: {e}"}

        except Exception as e:
            logger.error(f"[INDEXING FAILED] Unexpected exception for {root_path}: {e}")
            db.rollback()
            return {'status': 'failure', 'root': root_path, 'error': f"General error: {e}"}

    finally:
        if redis_client:
            redis_client.delete(INDEX_LOCK_KEY)
            logger.info(f"Released index lock for {root_path}.")
        else:
            logger.error("Could not release index lock (Redis client unavailable).")

    
@celery.task(bind=True, max_retries=3, default_retry_delay=10)
def perform_merge(self, dz_uuid, destination, final_filename, dz_total_chunks=None):
    """
    Merge all .part files for a given UUID into a final file,
    and then queues tasks to index the final file.
    """
    temp_dir = os.path.join(UPLOAD_TMP, dz_uuid)
    final_path = os.path.join(os.path.normpath(destination), final_filename)
    cleanup_on_success = False 
    
    # --- SECONDARY DUPLICATE CHECK ---
    if os.path.exists(final_path):
        logger.warning(f"[MERGE SKIPPED] Duplicate file exists: {final_path}. Cleaning up temp.")
        shutil.rmtree(temp_dir, ignore_errors=True) 
        return {"status": "duplicate_found_fs", "file_path": final_path} 
    
    logger.info(f"[MERGING STARTED] UUID={dz_uuid}. Writing final file to: {final_path}")

    try:
        if not os.path.exists(temp_dir):
            raise FileNotFoundError(f"Temp directory not found: {temp_dir}")

        # --- Merge chunks sequentially ---
        part_files = sorted(
             [f for f in os.listdir(temp_dir) if f.endswith(".part")]
        )
        with open(final_path, "wb") as f_out:
            total_size = 0
            for idx, part in enumerate(sorted(part_files)):
                part_path = os.path.join(temp_dir, part)
                with open(part_path, "rb") as f_in:
                    shutil.copyfileobj(f_in, f_out)
                    total_size += os.path.getsize(part_path)
                logger.debug(f"[MERGE] Appended chunk {idx + 1}/{dz_total_chunks} for {final_filename}")

        logger.info(f"[MERGE COMPLETE] UUID={dz_uuid}, wrote {final_filename} ({total_size/1e6:.2f} MB)")

        # 1. Trigger Single-File Indexing
        index_single_file.delay(final_path)
        logger.info(f"[INDEX QUEUED] Single file indexing started for {final_filename}")
        
        # 2. Set flag for cleanup
        cleanup_on_success = True 
        
        return {"status": "success", "file_path": final_path, "chunks": dz_total_chunks}

    except (OSError, FileNotFoundError) as e:
        logger.error(f"[MERGE ERROR] {type(e).__name__}: {e} for UUID={dz_uuid}")

        if self.request.retries < self.max_retries:
            logger.warning(f"Retrying merge for UUID={dz_uuid} in {self.default_retry_delay}s...")
            raise self.retry(exc=e)
        else:
            logger.error(f"[ABORT] Max retries exceeded for UUID={dz_uuid}")
            return {"status": "failure", "error": str(e)}

    finally:
        # --- CONSOLIDATED CLEANUP LOGIC ---
        should_cleanup = cleanup_on_success or (self.request.retries >= self.max_retries)
        
        if os.path.exists(temp_dir) and should_cleanup:
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.info(f"[CLEANUP] Removed temp folder {temp_dir}")
            
# ---------------------------------------------------------
# Celery Status Utilities
# ---------------------------------------------------------

def is_celery_indexing():
    """
    Inspects Celery queues and returns a bool:
    - True if Celery is currently indexing.
    """
    try:
        i = celery.control.inspect()
        active_tasks = i.active() or {}
        reserved_tasks = i.reserved() or {}
        
        # Combine all active and reserved tasks into one list for easier checking
        all_tasks = []
        for _, tasks in active_tasks.items():
            all_tasks.extend(tasks)
        for _, tasks in reserved_tasks.items():
            all_tasks.extend(tasks)
            
        # Define the task names we're looking for
        drive_index_task_name = 'celery_worker.index_drive_path'
        single_index_task_name = 'celery_worker.index_single_file'
        merge_task_name = 'celery_worker.perform_merge'
        
        # Use any() for an efficient check. Stop as soon as we find one.
        is_indexing_locked = any(task['name'] in [merge_task_name, drive_index_task_name, single_index_task_name] for task in all_tasks)

    except Exception as e:
        logger.error(f"Celery inspection failed: {e}")
        # Return False for both if the worker is offline
        return False, False

    return is_indexing_locked
