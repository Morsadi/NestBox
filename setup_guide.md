# NestBox Setup Guide

Welcome to the **NestBox**

This document outlines the technology stack used in the application and
provides step-by-step instructions to get the Flask app running on your
local machine (Windows or macOS).

## 1. Install Python

Choose the installer for your system. Ensure you check the box **"Add
Python to PATH"** during installation on Windows.

-   **Windows:** https://www.python.org/downloads/windows/
-   **macOS:** https://www.python.org/downloads/macos/

> **Tip:** Some systems use `python3` instead of `python`. If a command
> fails, try switching between `python` → `python3` or `pip` → `pip3`.

## 2. Install Redis

Redis is required for Celery task processing.

-   **Windows:**
    https://redis.io/docs/latest/operate/oss_and_stack/install/archive/install-redis/install-redis-on-windows/

-   **macOS (Homebrew):**\
    Install: `brew install redis`\
    Start Redis server: `redis-server`

## 3. Create a New Virtual Environment

Navigate to your `NestBox` project folder in your terminal, then create
the virtual environment (`.venv`).

-   **Windows (PowerShell or CMD):**\
    `py -3 -m venv .venv`

-   **macOS (bash/zsh):**\
    `python3 -m venv .venv`

## 4. Activate the Virtual Environment

-   **Windows (PowerShell):**\
    `.\.venv\Scripts\Activate.ps1`

-   **Windows (CMD):**\
    `.\.venv\Scriptsctivate`

-   **macOS (bash/zsh):**\
    `source .venv/bin/activate`

> You should now see `(.venv)` at the start of your terminal prompt.

## 5. Upgrade pip (Optional but Recommended)

`python -m pip install --upgrade pip`

## 6. Install Requirements

With your venv active:

`pip install -r requirements.txt`

Or:

`pip3 install -r requirements.txt`

## 7. Run the App, Redis, and Celery

`python run_all.py`
