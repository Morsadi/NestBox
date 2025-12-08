import os

# The absolute path to the directory of this file
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# The shared absolute path for chunk storage
UPLOAD_TMP = os.path.join(PROJECT_ROOT, "chunks")