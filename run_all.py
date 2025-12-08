#!/usr/bin/env python3
import os
import subprocess
import sys
import platform
import signal
import time

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(PROJECT_DIR)

if platform.system() == "Windows":
    VENV_PYTHON = os.path.join(PROJECT_DIR, ".venv", "Scripts", "python.exe")
    VENV_BIN = os.path.join(PROJECT_DIR, ".venv", "Scripts")
else:
    VENV_PYTHON = os.path.join(PROJECT_DIR, ".venv", "bin", "python")
    VENV_BIN = os.path.join(PROJECT_DIR, ".venv", "bin")

def env_with_venv():
    env = os.environ.copy()
    env["PATH"] = VENV_BIN + os.pathsep + env["PATH"]
    return env

print("Starting Nestbox...")

# Start Redis
if platform.system() == "Windows":
    redis_cmd = r"C:\redis\redis-server.exe"
else:
    redis_cmd = "redis-server"

redis_proc = subprocess.Popen([redis_cmd], env=env_with_venv())

# Start Celery
celery_proc = subprocess.Popen(
    [
        VENV_PYTHON, "-m", "celery",
        "-A", "app.celery",
        "worker",
        "-l", "info",
        "--pool=threads",
        "--concurrency=3"
    ],
    env=env_with_venv()
)

# Start Flask
flask_proc = subprocess.Popen(
    [VENV_PYTHON, "app.py"],
    env=env_with_venv()
)

print("Nestbox running. Press CTRL+C to stop everything.")

try:
    while True:
        time.sleep(1)

except KeyboardInterrupt:
    print("\nStopping Nestbox...")

    # TERM on Unix, CTRL_BREAK_EVENT on Windows for structured kill
    if platform.system() == "Windows":
        flask_proc.send_signal(signal.CTRL_BREAK_EVENT)
        celery_proc.send_signal(signal.CTRL_BREAK_EVENT)
        redis_proc.send_signal(signal.CTRL_BREAK_EVENT)
    else:
        flask_proc.terminate()
        celery_proc.terminate()
        redis_proc.terminate()

    time.sleep(1)
    print("All processes stopped.")
